#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron — Module 1: 프로젝트 스케줄러 (Project Scheduler)
============================================================

조직(Organisation) → 프로젝트(Project) → 스프린트(Sprint) → 태스크(Task) 계층의
태스크 의존성 그래프를 입력받아 다음 세 가지를 산출한다.

  1) 의존성을 지키는 "우선순위 인지 실행 순서"  — 칸(Kahn) 위상정렬 + 최소힙
  2) "임계경로(critical path)"와 태스크별 여유시간(slack) — DAG 최장경로 DP
  3) 임계경로 길이를 프로젝트 마감일(deadline)에 정렬한 "달력 타임라인"

또한 사이클(순환 의존성)을 검출하여 문제 태스크를 지목한다.
(tasks.json 은 DAG 보장, tasks_broken.json 은 사이클 1개가 주입되어 있음.)

----------------------------------------------------------------
사용 자료구조 (Data structures)  ── 과목 요구사항: ≥2개
  · 인접 리스트 (adjacency list)           : 태스크 의존성 그래프 (graph)
  · 최소 힙 / 우선순위 큐 (min-heap)        : 위상정렬의 ready-set 정렬 (heapq)
  · 해시맵 (hash map / dict)               : 진입차수·ES/EF/LS/LF·slack 등 속성표
  · 큐 / 데크 (deque)                       : 단순 위상정렬·DFS 스택

사용 알고리즘 (Algorithms)  ── 과목 요구사항: ≥2개, 대표 알고리즘은 서로 다른 계열
  · [대표·그래프]      우선순위 인지 위상정렬 = 칸(Kahn) 알고리즘 + 최소힙
  · [대표·동적계획법]  임계경로 = DAG 최장경로 DP (전진/후진 패스 + slack)
  · [보조·그래프 탐색] 사이클 검출 = 칸 잔여(진입차수>0) + DFS 역간선 복원

----------------------------------------------------------------
실행 환경 (Run environment)
  · Python 3.8+ — 표준 라이브러리만 사용 (third-party 의존성 없음, requirements.txt 불필요)
  · 사용 모듈: argparse, datetime, heapq, json, os, collections, dataclasses, typing

실행 예시
  $ python scheduler.py                                  # tasks.json 전체 + 사이클 검사
  $ python scheduler.py --project P1                     # P1 만 상세 출력
  $ python scheduler.py --tasks data/tasks.json
  $ python scheduler.py --check-only data/tasks_broken.json   # 사이클 검사만
"""

from __future__ import annotations

import argparse
import datetime as dt
import heapq
import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ───────────────────────── 상수 / 기본값 ─────────────────────────
# 한 스프린트를 2주(영업일 10일)로 가정 → 프로젝트 속도(velocity) 추정에 사용.
WORKDAYS_PER_SPRINT = 10
DATE_FMT = "%Y-%m-%d"


# ════════════════════════════════════════════════════════════════════
#  데이터 모델 (결과 컨테이너)
# ════════════════════════════════════════════════════════════════════
@dataclass
class CriticalPathResult:
    """한 프로젝트의 임계경로 분석 결과 (CPM: Critical Path Method)."""

    project: str
    makespan_points: int                 # 임계경로 길이(스토리포인트) = 프로젝트 최소 완료기간
    critical_path: List[str]             # slack==0 태스크를 순서대로 이은 경로
    has_cycle: bool = False              # 이 프로젝트가 사이클을 포함하면 True(임계경로/슬랙 무의미)
    es: Dict[str, int] = field(default_factory=dict)   # earliest start  (이른 시작)
    ef: Dict[str, int] = field(default_factory=dict)   # earliest finish (이른 완료)
    ls: Dict[str, int] = field(default_factory=dict)   # latest start    (늦은 시작)
    lf: Dict[str, int] = field(default_factory=dict)   # latest finish   (늦은 완료)
    slack: Dict[str, int] = field(default_factory=dict)  # 여유 = LS-ES = LF-EF


@dataclass
class CycleResult:
    """사이클(순환 의존성) 검출 결과."""

    has_cycle: bool
    cycle: List[str] = field(default_factory=list)          # 대표 순환 경로 1개(DFS 역간선 복원)
    cycles: List[List[str]] = field(default_factory=list)   # 검출된 '모든' 사이클(여러 개일 수 있음)
    unschedulable: List[str] = field(default_factory=list)  # 칸 잔여(사이클∪하류) 전체
    downstream_blocked: List[str] = field(default_factory=list)  # 사이클은 아니나 막힌 하류


@dataclass
class ScheduledTask:
    """달력 매핑까지 끝난 태스크 1건의 일정(타임라인 한 행)."""

    id: str
    project: str
    estimate: int
    priority: int
    slack_points: int
    slack_days: int
    on_critical_path: bool
    early_start: dt.date
    early_finish: dt.date
    late_start: dt.date
    late_finish: dt.date


# ════════════════════════════════════════════════════════════════════
#  스케줄러 본체
# ════════════════════════════════════════════════════════════════════
class Scheduler:
    """
    태스크 리스트(딕셔너리들의 리스트)를 받아 의존성 그래프를 구성하고
    위상정렬·임계경로·사이클검출·달력매핑을 제공한다.

    그래프 간선 규약:
        태스크 B 가 A 에 의존(B.depends_on == [A]) → "A 가 먼저" → 방향간선 A ─► B.
        즉 adj[A] 는 'A 가 끝나야 풀리는 후속 태스크들'(direct successors)을 담는다.
        진입차수 indeg[B] = 아직 끝나지 않은 선행(prerequisite) 개수.
    """

    def __init__(self, tasks: List[dict], projects: Optional[List[dict]] = None,
                 sprints: Optional[List[dict]] = None):
        # ── 자료구조: 해시맵 id → task ──
        self.tasks: Dict[str, dict] = {t["id"]: t for t in tasks}
        self.projects: Dict[str, dict] = {p["id"]: p for p in (projects or [])}
        self.sprints: List[dict] = sprints or []

        # ── 자료구조: 인접 리스트(그래프) + 진입차수 해시맵 ──
        self.adj: Dict[str, List[str]] = defaultdict(list)   # A ─► [후속들]
        self.indeg: Dict[str, int] = {tid: 0 for tid in self.tasks}
        self._build_graph()

        # 임계경로 결과 캐시. slack 은 위상정렬 힙 키에 쓰이므로 미리 채워둔다.
        self._cp: Dict[str, CriticalPathResult] = {}
        self.slack: Dict[str, int] = {}        # 전역 slack 표(모든 프로젝트 합산)
        self._analyse_all_projects()

    # ───────────────────────── 그래프 구성 ─────────────────────────
    def _build_graph(self) -> None:
        """depends_on 간선으로 인접 리스트와 진입차수를 만든다. 누락 참조는 무시(방어적)."""
        for tid, t in self.tasks.items():
            # dict.fromkeys: 같은 선행을 두 번 적은 경우(중복 간선) 제거 → 진입차수·out_degree 왜곡 방지.
            for dep in dict.fromkeys(t.get("depends_on", [])):
                if dep not in self.tasks:
                    continue                       # 존재하지 않는 선행 id 는 제외
                self.adj[dep].append(tid)          # dep ─► tid
                self.indeg[tid] += 1
        for u in self.adj:                         # 결정적 출력을 위해 인접 리스트 정렬
            self.adj[u].sort()

    def _analyse_all_projects(self) -> None:
        """모든 프로젝트의 임계경로를 미리 계산해 전역 slack 표를 채운다."""
        for pid in sorted({t["project"] for t in self.tasks.values()}):
            self.critical_path(pid)

    def project_ids(self) -> List[str]:
        return sorted({t["project"] for t in self.tasks.values()})

    def _project_task_ids(self, project: str) -> List[str]:
        return sorted(tid for tid, t in self.tasks.items() if t["project"] == project)

    # ════════════════════════════════════════════════════════════════
    #  스프린트 스케줄 순서 (Module 2 연동 지점)
    #  ── 자원 배정기(Module 2)가 '어느 스프린트부터 용량을 소진하며 배정할지'의
    #     기준 순서를 스케줄러가 소유한다(스케줄은 Module 1 의 책임).
    #     정렬 키: (프로젝트 마감 이른 순, 스프린트 번호, id)
    #       └ 마감 이른 프로젝트가 talent(개발자 용량)를 먼저 가져간다(우선순위 인지).
    # ════════════════════════════════════════════════════════════════
    def sprint_order(self) -> List[str]:
        """스프린트 id 들을 '스케줄 순서'로 반환. sprints.json 이 없으면 태스크에서 유추."""
        # 자료구조: 집합 — 스프린트 id 수집(중복 제거)
        sids = {s["id"] for s in self.sprints if s.get("id")}
        sids |= {t.get("sprint") for t in self.tasks.values() if t.get("sprint")}
        sids.discard(None)

        sproj = {s["id"]: s.get("project") for s in self.sprints if s.get("id")}

        def proj_of(sid: str) -> str:
            if sproj.get(sid):
                return sproj[sid]
            for t in self.tasks.values():          # sprints.json 누락 시 태스크에서 프로젝트 유추
                if t.get("sprint") == sid:
                    return t["project"]
            return sid.split("-")[0]               # 최후수단: 'P1-S4' → 'P1'

        def seqnum(sid: str) -> int:
            tail = sid.rsplit("-S", 1)             # 'P1-S4' → ['P1','4']
            return int(tail[1]) if len(tail) == 2 and tail[1].isdigit() else 0

        return sorted(sids, key=lambda sid: (self._deadline_ordinal(proj_of(sid)),
                                             seqnum(sid), sid))

    # ════════════════════════════════════════════════════════════════
    #  [대표 알고리즘 ①·그래프] 우선순위 인지 위상정렬
    #  ── 위상정렬: 칸(Kahn) 알고리즘. 단, ready-queue 를 '최소 힙'으로 교체.
    #     · 의존성(진입차수)이 '언제' 풀리는지를 결정하고,
    #     · 힙 키가 풀린 것들 중 '무엇을' 먼저 내보낼지를 결정한다.
    #  힙 키(작을수록 먼저):
    #     (slack, priority, deadline, -out_degree, id)
    #      └ slack       : 임계도(criticality). 0이면 임계경로 → 최우선
    #      └ priority    : 1(최상)~4(최하). 비즈니스 우선순위
    #      └ deadline    : 마감 이른 프로젝트 먼저
    #      └ -out_degree : 더 많은 후속을 막고 있는(blocking factor 큰) 것 먼저
    #      └ id          : 완전한 결정성(tie-break)
    # ════════════════════════════════════════════════════════════════
    def priority_topo_sort(self, project: Optional[str] = None
                           ) -> Tuple[List[str], CycleResult]:
        """
        의존성을 지키는 실행 순서를 반환한다. project 지정 시 해당 프로젝트만.
        반환: (실행순서 리스트, 사이클검출결과)
        모든 태스크가 배출되지 못하면(=잔여 진입차수>0) 사이클이 존재한다.
        """
        nodes = (self._project_task_ids(project) if project else sorted(self.tasks))
        nodeset = set(nodes)

        # 부분 그래프 기준 진입차수 재계산(프로젝트 필터 시 외부 간선 제외).
        indeg = {n: 0 for n in nodes}
        for u in nodes:
            for v in self.adj[u]:
                if v in nodeset:
                    indeg[v] += 1

        # ── 최소 힙: 진입차수 0(=선행 없음)인 태스크부터 ready-set 에 적재 ──
        heap: List[Tuple] = []
        for n in nodes:
            if indeg[n] == 0:
                heapq.heappush(heap, (self._heap_key(n), n))

        order: List[str] = []
        seen = set()
        while heap:
            _, u = heapq.heappop(heap)      # 가장 '임계/시급'한 ready 태스크 선택
            order.append(u)
            seen.add(u)
            for v in self.adj[u]:           # u 완료 → 후속들의 진입차수 감소
                if v not in nodeset:
                    continue
                indeg[v] -= 1
                if indeg[v] == 0:           # 선행이 모두 끝난 순간 ready-set 진입
                    heapq.heappush(heap, (self._heap_key(v), v))

        # ── 사이클 검출: 한 번도 배출되지 못한(진입차수>0) 태스크가 남으면 순환 ──
        if len(order) < len(nodes):
            leftover = [n for n in nodes if n not in seen]
            cyc = self._detect_cycle(nodeset)
            cyc.unschedulable = sorted(leftover)
            cyc.downstream_blocked = sorted(set(leftover) - set(cyc.cycle))
            return order, cyc
        return order, CycleResult(has_cycle=False)

    def _heap_key(self, tid: str) -> Tuple[int, int, int, int, str]:
        """위상정렬 최소힙의 정렬 키. 작을수록 먼저 실행."""
        t = self.tasks[tid]
        slack = self.slack.get(tid, 0)                   # 임계도(작을수록 임계)
        priority = t.get("priority", 4)                  # 1 최상 ~ 4 최하
        deadline = self._deadline_ordinal(t["project"])  # 마감 이른 순
        out_degree = len(self.adj[tid])                  # 막고 있는 후속 수(클수록 먼저 → 음수화)
        return (slack, priority, deadline, -out_degree, tid)

    def _deadline_ordinal(self, project: str) -> int:
        p = self.projects.get(project)
        if not p or not p.get("deadline"):
            return 10 ** 9
        return dt.datetime.strptime(p["deadline"], DATE_FMT).date().toordinal()

    # ════════════════════════════════════════════════════════════════
    #  [대표 알고리즘 ②·동적계획법] 임계경로 = DAG 최장경로 DP
    #  ── 위상순서대로 1회 전진 패스 + 1회 후진 패스 = O(V+E).
    #     전진:  ES[v] = max(EF[선행]),  EF[v] = ES[v] + dur[v]     (이른 일정)
    #     후진:  LF[v] = min(LS[후속]),  LS[v] = LF[v] - dur[v]     (늦은 일정)
    #     여유:  slack[v] = LS[v]-ES[v] = LF[v]-EF[v]
    #     임계경로 = slack==0 인 태스크들(지연되면 프로젝트 전체가 지연).
    #  ※ 프로젝트 간 간선이 없으므로 프로젝트별로 독립 계산하며,
    #     각 프로젝트의 makespan(최대 EF)을 그 프로젝트 sink 들의 LF 기준으로 삼는다.
    # ════════════════════════════════════════════════════════════════
    def critical_path(self, project: str) -> CriticalPathResult:
        if project in self._cp:
            return self._cp[project]

        nodes = self._project_task_ids(project)
        nodeset = set(nodes)
        dur = {n: int(self.tasks[n].get("estimate", 0)) for n in nodes}   # 노드 가중치 = 작업량

        topo = self._plain_topo(nodes, nodeset)   # DP 의 전제: 위상순서
        # 사이클이 있으면 위상순서가 전체 노드를 담지 못한다 → 최장경로(임계경로)는 정의되지 않음.
        proj_has_cycle = len(topo) < len(nodes)

        # ── 전진 패스: 이른 시작/완료 (sources 로부터의 최장경로) ──
        es = {n: 0 for n in nodes}
        ef = {n: 0 for n in nodes}
        for u in topo:
            preds = [p for p in self.tasks[u].get("depends_on", []) if p in nodeset]
            es[u] = max((ef[p] for p in preds), default=0)
            ef[u] = es[u] + dur[u]

        makespan = max((ef[n] for n in nodes), default=0)          # 프로젝트 최소 완료기간

        # ── 후진 패스: 늦은 완료/시작 (모든 sink 의 LF = makespan) ──
        lf = {n: makespan for n in nodes}
        ls = {n: makespan for n in nodes}
        for u in reversed(topo):
            succs = [v for v in self.adj[u] if v in nodeset]
            lf[u] = min((ls[v] for v in succs), default=makespan)
            ls[u] = lf[u] - dur[u]

        slack = {n: ls[n] - es[n] for n in nodes}
        self.slack.update(slack)                                   # 전역 slack 표 갱신

        # 사이클을 포함한 프로젝트는 임계경로 복원을 건너뛴다(무한루프 방지·의미상 미정의).
        # 사이클 자체의 보고는 priority_topo_sort / detect_cycles 가 담당한다.
        cp = [] if proj_has_cycle else self._reconstruct_critical_path(nodes, nodeset, es, ef, slack)

        res = CriticalPathResult(project=project, makespan_points=makespan,
                                 critical_path=cp, has_cycle=proj_has_cycle,
                                 es=es, ef=ef, ls=ls, lf=lf, slack=slack)
        self._cp[project] = res
        return res

    def _plain_topo(self, nodes: List[str], nodeset: set) -> List[str]:
        """가중치 DP의 전제가 되는 단순 위상순서(데크 기반 칸). 결정적 정렬."""
        indeg = {n: 0 for n in nodes}
        for u in nodes:
            for v in self.adj[u]:
                if v in nodeset:
                    indeg[v] += 1
        q = deque(sorted(n for n in nodes if indeg[n] == 0))
        order: List[str] = []
        while q:
            u = q.popleft()
            order.append(u)
            for v in self.adj[u]:
                if v in nodeset:
                    indeg[v] -= 1
                    if indeg[v] == 0:
                        q.append(v)
        return order

    def _reconstruct_critical_path(self, nodes, nodeset, es, ef, slack) -> List[str]:
        """
        임계 노드(slack==0)만으로 부분그래프를 만들고, 임계 source 에서 시작해
        '딱 이어지는(EF[선행]==ES[후속])' 임계 간선을 따라 최장 사슬 하나를 복원한다.
        ※ 임계경로가 여러 개의 분리된 사슬일 수 있으나 여기서는 '대표 사슬 1개'만 반환한다.
          (리포트의 ★ 표시는 모든 slack==0 태스크를 따로 열거하므로 둘의 개수가 다를 수 있다.)
        """
        critical = [n for n in nodes if slack[n] == 0]
        if not critical:
            return []
        cset = set(critical)

        # 임계 부분그래프의 후속 맵: n→m (m 이 n 에 의존, 둘 다 임계, EF[n]==ES[m])
        csucc: Dict[str, List[str]] = defaultdict(list)
        cindeg = {n: 0 for n in critical}
        for m in critical:
            for p in self.tasks[m].get("depends_on", []):
                if p in cset and ef[p] == es[m]:
                    csucc[p].append(m)
                    cindeg[m] += 1

        # source(임계 진입차수 0) 중 EF 가 가장 멀리 가는 사슬을 탐욕적으로 따라간다.
        sources = sorted([n for n in critical if cindeg[n] == 0], key=lambda n: (es[n], n))
        start = sources[0] if sources else sorted(critical, key=lambda n: (es[n], n))[0]
        chain = [start]
        cur = start
        walked = {start}                       # 방문집합: 만일 임계 부분그래프에 사이클이 있어도 무한루프 방지
        while csucc[cur]:
            cur = max(csucc[cur], key=lambda m: (ef[m], m))   # 가장 멀리 가는 임계 후속
            if cur in walked:
                break
            walked.add(cur)
            chain.append(cur)
        return chain

    # ════════════════════════════════════════════════════════════════
    #  [보조 알고리즘·그래프 탐색] 사이클 검출 — DFS 역간선(back-edge) 복원
    #  ── 칸 정렬이 '사이클의 존재'를 알려주면(잔여 진입차수>0), 여기서 구체적
    #     순환 경로 1개를 색칠 DFS 로 복원한다.
    #     WHITE(미방문)/GRAY(현재 재귀스택)/BLACK(완료). GRAY 노드로 가는 간선=역간선=사이클.
    #     재귀 대신 명시적 스택(데크)으로 구현해 깊은 그래프에서도 안전.
    # ════════════════════════════════════════════════════════════════
    def _detect_cycle(self, nodeset: Optional[set] = None) -> CycleResult:
        if nodeset is None:
            nodeset = set(self.tasks)
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in nodeset}
        parent: Dict[str, Optional[str]] = {n: None for n in nodeset}

        for s in sorted(nodeset):
            if color[s] != WHITE:
                continue
            # 명시적 스택 DFS. 프레임 = (노드, 다음에 볼 후속 인덱스)
            stack: deque = deque([(s, 0)])
            color[s] = GRAY
            while stack:
                u, i = stack[-1]
                succs = [v for v in self.adj[u] if v in nodeset]
                if i < len(succs):
                    stack[-1] = (u, i + 1)
                    v = succs[i]
                    if color[v] == WHITE:
                        color[v] = GRAY
                        parent[v] = u
                        stack.append((v, 0))
                    elif color[v] == GRAY:
                        # 역간선 발견 → u..v 로 거슬러 올라가 사이클 복원
                        if v == u:                      # 자기참조(self-loop)는 단일 노드 사이클
                            return CycleResult(has_cycle=True, cycle=[u])
                        cycle = [u]
                        x = u
                        while x != v and x is not None:
                            x = parent[x]
                            cycle.append(x)
                        cycle.reverse()                 # v ─► ... ─► u
                        cycle.append(v)                 # 닫힘: ... ─► u ─► v
                        return CycleResult(has_cycle=True, cycle=cycle)
                    # BLACK 이면 이미 완료된 분기 → 무시
                else:
                    color[u] = BLACK
                    stack.pop()
        return CycleResult(has_cycle=False)

    def detect_cycles(self) -> CycleResult:
        """공개 API: 전체 그래프의 '모든' 사이클을 검출하고 (사이클∪하류) 분류까지 채운다."""
        first = self._detect_cycle(set(self.tasks))
        if not first.has_cycle:
            return first

        # 칸 정렬(힙 없는 단순 위상정렬)로 '스케줄 불가(사이클∪하류)' 집합 전체를 구한다.
        order = self._plain_topo(sorted(self.tasks), set(self.tasks))
        leftover = set(self.tasks) - set(order)

        # 잔여 부분그래프에서 사이클을 하나씩 찾아 그 노드들을 빼며 '모든' 사이클을 수집한다.
        cycles: List[List[str]] = []
        cycle_nodes: set = set()
        working = set(leftover)
        while working:
            c = self._detect_cycle(working)
            if not c.has_cycle:
                break
            cycles.append(c.cycle)
            members = set(c.cycle)
            cycle_nodes |= members
            working -= members                  # 이 사이클 노드 제거 후 다음 사이클 탐색

        res = CycleResult(has_cycle=True, cycle=cycles[0] if cycles else first.cycle)
        res.cycles = cycles
        res.unschedulable = sorted(leftover)
        res.downstream_blocked = sorted(leftover - cycle_nodes)   # 사이클 멤버를 제외한 '진짜 하류'만
        return res

    # ════════════════════════════════════════════════════════════════
    #  달력 매핑 (Calendar timeline)
    #  ── 임계경로(스토리포인트) 길이를 프로젝트 마감일에 맞춰 영업일 달력으로 환산.
    #     velocity(영업일당 처리 포인트) = Σ스프린트용량 / (스프린트수 × 영업일/스프린트).
    #     프로젝트 완료(makespan)를 deadline 에 고정 → 착수일(kickoff) 역산 후
    #     각 태스크의 ES/EF/LS/LF 포인트를 영업일 날짜로 변환(주말 제외).
    # ════════════════════════════════════════════════════════════════
    def project_velocity(self, project: str) -> float:
        """데이터에 근거한 영업일당 속도. 스프린트 용량 합 / (스프린트수×10영업일)."""
        caps = [s["capacity"] for s in self.sprints if s.get("project") == project]
        total = sum(caps)
        if not caps or total <= 0:             # 스프린트 없음/용량 합 0 → 안전한 기본값
            return 1.0
        return total / (len(caps) * WORKDAYS_PER_SPRINT)

    @staticmethod
    def _add_business_days(start: dt.date, n: int) -> dt.date:
        """start 로부터 영업일(월~금) n 일 이동(음수 가능). 주말은 건너뜀."""
        if n == 0:
            return start
        step = 1 if n > 0 else -1
        remaining = abs(n)
        d = start
        while remaining > 0:
            d += dt.timedelta(days=step)
            if d.weekday() < 5:        # 0=월 ... 4=금
                remaining -= 1
        return d

    def build_timeline(self, project: str, velocity: Optional[float] = None
                       ) -> Tuple[List[ScheduledTask], dt.date, dt.date, float]:
        """
        프로젝트의 각 태스크에 달력 날짜를 부여한다.
        반환: (타임라인 행 리스트, 착수일 kickoff, 마감일 deadline, 사용한 velocity)
        """
        cp = self.critical_path(project)
        v = velocity if velocity is not None else self.project_velocity(project)
        if v is None or v <= 0:                # 0·음수 속도 방어(date 오버플로/무한루프 방지)
            v = 1.0

        # 포인트 → 영업일 변환(반올림). 프로젝트 makespan 을 deadline 에 고정.
        def day_of(points: float) -> int:
            return int(round(points / v))

        deadline = self._project_deadline(project)
        while deadline.weekday() >= 5:         # 마감일이 주말이면 직전 영업일로 당겨 앵커 정합성 유지
            deadline -= dt.timedelta(days=1)
        makespan_days = day_of(cp.makespan_points)
        kickoff = self._add_business_days(deadline, -makespan_days)

        rows: List[ScheduledTask] = []
        for tid in self._project_task_ids(project):
            t = self.tasks[tid]
            rows.append(ScheduledTask(
                id=tid, project=project, estimate=int(t["estimate"]),
                priority=t.get("priority", 4),
                slack_points=cp.slack[tid], slack_days=day_of(cp.slack[tid]),
                on_critical_path=(cp.slack[tid] == 0),
                early_start=self._add_business_days(kickoff, day_of(cp.es[tid])),
                early_finish=self._add_business_days(kickoff, day_of(cp.ef[tid])),
                late_start=self._add_business_days(kickoff, day_of(cp.ls[tid])),
                late_finish=self._add_business_days(kickoff, day_of(cp.lf[tid])),
            ))
        # 이른 시작 → 여유 → id 순으로 정렬(타임라인 보기 좋게).
        rows.sort(key=lambda r: (r.early_start, r.slack_points, r.id))
        return rows, kickoff, deadline, v

    def _project_deadline(self, project: str) -> dt.date:
        p = self.projects.get(project)
        if p and p.get("deadline"):
            return dt.datetime.strptime(p["deadline"], DATE_FMT).date()
        return dt.date.today()


# ════════════════════════════════════════════════════════════════════
#  데이터 로딩
# ════════════════════════════════════════════════════════════════════
def _load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_store(tasks_path: str) -> Tuple[List[dict], List[dict], List[dict]]:
    """tasks.json 경로를 받아 같은 폴더의 projects/sprints 도 함께 로드(있으면)."""
    data_dir = os.path.dirname(os.path.abspath(tasks_path))
    tasks = _load_json(tasks_path)
    projects, sprints = [], []
    p_path = os.path.join(data_dir, "projects.json")
    s_path = os.path.join(data_dir, "sprints.json")
    if os.path.exists(p_path):
        projects = _load_json(p_path)
    if os.path.exists(s_path):
        sprints = _load_json(s_path)
    return tasks, projects, sprints


# ════════════════════════════════════════════════════════════════════
#  출력(리포트) 헬퍼
# ════════════════════════════════════════════════════════════════════
def _rule(title: str = "", ch: str = "─", width: int = 78) -> str:
    if not title:
        return ch * width
    pad = width - len(title) - 2
    return f"{ch * 2} {title} {ch * max(pad - 2, 0)}"


def print_cycle_report(label: str, cyc: CycleResult) -> None:
    print(_rule(f"사이클 검사: {label}", "═"))
    if not cyc.has_cycle:
        print("  ✔ 사이클 없음 — 유효한 DAG. 모든 태스크 스케줄 가능.\n")
        return
    cycles = cyc.cycles or ([cyc.cycle] if cyc.cycle else [])
    print(f"  ✘ 사이클(순환 의존성) {len(cycles)}개 검출!")
    for i, chain in enumerate(cycles, 1):
        tag = f"#{i} " if len(cycles) > 1 else ""
        print(f"    • 순환 경로 {tag}({len(set(chain))}개 태스크): " + " → ".join(chain))
    print(f"    • 스케줄 불가 태스크 총 {len(cyc.unschedulable)}개: "
          + ", ".join(cyc.unschedulable))
    if cyc.downstream_blocked:
        print(f"    • 그중 사이클 하류(원인은 아니나 막힘): "
              + ", ".join(cyc.downstream_blocked))
    print()


def print_project_report(sch: Scheduler, project: str, velocity: Optional[float],
                         max_rows: int) -> None:
    cp = sch.critical_path(project)
    pname = sch.projects.get(project, {}).get("name", project)
    rows, kickoff, deadline, v = sch.build_timeline(project, velocity)
    ncrit = sum(1 for r in rows if r.on_critical_path)

    print(_rule(f"프로젝트 {project} ({pname}) — {len(rows)} tasks", "═"))

    # 1) 임계경로
    print(f"  [임계경로] 길이 {cp.makespan_points} pts  ·  임계 태스크 {ncrit}개")
    chain_str = " → ".join(
        f"{tid}({sch.tasks[tid]['estimate']})" for tid in cp.critical_path)
    print(f"    {chain_str}")
    print(f"    └ velocity≈{v:.2f} pts/영업일 → 약 {int(round(cp.makespan_points / max(v,1e-9)))}"
          f" 영업일  |  착수 {kickoff.isoformat()} → 마감 {deadline.isoformat()}")

    # 2) slack 요약(여유 적은 순)
    by_slack = sorted(rows, key=lambda r: (r.slack_points, r.id))
    print("\n  [여유시간(slack) — 적은 순]   "
          "S=slack(pts) · ★=임계경로")
    print(f"    {'task':<7}{'pri':>4}{'est':>5}{'ES':>4}{'EF':>4}{'LS':>4}{'LF':>4}"
          f"{'S':>4}  {'early_start':>12} {'early_finish':>12}")
    cpr = sch.critical_path(project)
    for r in by_slack[:max_rows]:
        mark = "★" if r.on_critical_path else " "
        print(f"  {mark} {r.id:<7}{r.priority:>4}{r.estimate:>5}"
              f"{cpr.es[r.id]:>4}{cpr.ef[r.id]:>4}{cpr.ls[r.id]:>4}{cpr.lf[r.id]:>4}"
              f"{r.slack_points:>4}  {r.early_start.isoformat():>12} "
              f"{r.early_finish.isoformat():>12}")
    if len(by_slack) > max_rows:
        print(f"    … 외 {len(by_slack) - max_rows}개 (전체는 --max-rows 로 조정)")
    print()


def print_execution_order(sch: Scheduler, project: Optional[str], max_rows: int) -> None:
    order, cyc = sch.priority_topo_sort(project)
    scope = project if project else "전체 조직(ORG)"
    print(_rule(f"우선순위 인지 실행 순서 — {scope}", "═"))
    if cyc.has_cycle:
        print("  ✘ 사이클로 인해 완전한 순서를 만들 수 없음(아래 일부만 배출).")
    print(f"    (정렬 키: slack↑, priority↑, deadline↑, out_degree↓, id)")
    print(f"    {'#':>4}  {'task':<7}{'proj':>5}{'pri':>4}{'slack':>6}{'est':>5}"
          f"{'deg':>5}  title")
    for i, tid in enumerate(order[:max_rows], 1):
        t = sch.tasks[tid]
        deg = len(sch.adj[tid])
        print(f"    {i:>4}  {tid:<7}{t['project']:>5}{t.get('priority',4):>4}"
              f"{sch.slack.get(tid,0):>6}{t['estimate']:>5}{deg:>5}  "
              f"{t['title'][:38]}")
    if len(order) > max_rows:
        print(f"    … 외 {len(order) - max_rows}개")
    print()


# ════════════════════════════════════════════════════════════════════
#  메인(CLI)
# ════════════════════════════════════════════════════════════════════
def main(argv: Optional[List[str]] = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    default_tasks = os.path.join(here, "data", "tasks.json")
    default_broken = os.path.join(here, "data", "tasks_broken.json")

    ap = argparse.ArgumentParser(
        description="Squadron Module 1 — 프로젝트 스케줄러 (위상정렬 · 임계경로 · 사이클검출)")
    ap.add_argument("--tasks", default=default_tasks,
                    help="태스크 JSON 경로 (기본: data/tasks.json)")
    ap.add_argument("--project", default=None,
                    help="특정 프로젝트만 상세 출력 (예: P1)")
    ap.add_argument("--velocity", type=float, default=None,
                    help="영업일당 속도(pts/day) 강제 지정. 미지정 시 스프린트 용량에서 추정")
    ap.add_argument("--max-rows", type=int, default=15,
                    help="표에 출력할 최대 행 수 (기본 15)")
    ap.add_argument("--check-only", nargs="?", const=default_broken, default=None,
                    metavar="TASKS_JSON",
                    help="사이클 검사만 수행(기본 대상: tasks_broken.json)")
    args = ap.parse_args(argv)
    if args.velocity is not None and args.velocity <= 0:    # 잘못된 입력은 깔끔히 거절
        ap.error("--velocity 는 0보다 커야 합니다.")

    def _safe_load(path: str):
        """로딩 실패 시 트레이스백 대신 한 줄 오류로 종료."""
        try:
            return load_store(path)
        except FileNotFoundError:
            ap.error(f"파일을 찾을 수 없습니다: {path}")
        except json.JSONDecodeError as e:
            ap.error(f"JSON 파싱 실패: {path} ({e})")

    # ── 사이클 검사 전용 모드 ──
    if args.check_only is not None:
        tasks, projects, sprints = _safe_load(args.check_only)
        sch = Scheduler(tasks, projects, sprints)
        print_cycle_report(os.path.basename(args.check_only), sch.detect_cycles())
        return 0

    # ── 일반 모드: tasks.json 스케줄링 + 사이클 자가검증 + 깨진 파일 데모 ──
    tasks, projects, sprints = _safe_load(args.tasks)
    sch = Scheduler(tasks, projects, sprints)
    print(_rule("SQUADRON · Module 1 — Project Scheduler", "═"))
    print(f"  입력: {os.path.relpath(args.tasks)}  ·  태스크 {len(tasks)}개  ·  "
          f"프로젝트 {len(sch.project_ids())}개\n")

    if args.project and args.project not in sch.project_ids():   # 존재하지 않는 프로젝트 거절
        ap.error(f"알 수 없는 프로젝트 {args.project!r}. "
                 f"유효한 ID: {', '.join(sch.project_ids())}")

    targets = [args.project] if args.project else sch.project_ids()
    for pid in targets:
        print_project_report(sch, pid, args.velocity, args.max_rows)

    print_execution_order(sch, args.project, args.max_rows)

    # 입력(tasks.json)이 DAG 임을 자가검증
    print_cycle_report(os.path.basename(args.tasks), sch.detect_cycles())

    # 사이클 검출 데모: tasks_broken.json (있으면 자동 실행)
    if os.path.exists(default_broken) and os.path.abspath(args.tasks) != os.path.abspath(default_broken):
        b_tasks, b_proj, b_spr = load_store(default_broken)
        bsch = Scheduler(b_tasks, b_proj, b_spr)
        print_cycle_report(os.path.basename(default_broken), bsch.detect_cycles())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
