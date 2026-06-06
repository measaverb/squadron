#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron — Module 2: 특성기반 배정기 (Trait-based Allocator)
=============================================================

Module 1(스케줄러)이 정한 "무엇을 먼저 할지"를 받아, 각 태스크를 가장 잘 맞는
개발자에게 1:1로 배정한다. '잘 맞는다'는 것은 스킬·레벨·프로젝트 친숙도·잔여
용량을 종합한 친화도(affinity)로 정량화한다.

핵심 메시지(데모): 희소 스킬(rust·spark·terraform·flutter; 각 3명만 보유)을 가진
개발자는 평범한 태스크에도 매력적이라, 우선순위대로 욕심껏 배정하는 그리디는 그
희소 인력을 엉뚱한 곳에 써버려 정작 희소 스킬 태스크를 '미배정'으로 남긴다.
헝가리안(Hungarian/Kuhn–Munkres) 알고리즘은 배정을 '전역 최적'으로 풀어 이를 피한다.

----------------------------------------------------------------
사용 자료구조 (Data structures)  ── 과목 요구사항: ≥2개
  · 비용 행렬 (cost matrix, 2-D 리스트)     : 태스크×개발자 배정 비용 (헝가리안 입력)
  · 집합 (set)                              : 스킬 보유/요구 비교(부분집합·교집합) O(1)
  · 해시맵 (dict)                           : id→레코드, 잠재값(potential), 배정표
  · 리스트/배열                              : 잠재값 u/v, 증가경로 way/p 등 헝가리안 내부 상태

사용 알고리즘 (Algorithms)  ── 과목 요구사항: ≥2개, 대표 알고리즘은 서로 다른 계열
  · [대표·조합최적화]  헝가리안(쿤–먼크레스) 배정 알고리즘 = 전역 최소비용 완전매칭 O(n²m)
  · [보조·그리디]      우선순위 그리디 배정(각 태스크에 그 순간 최적 개발자) — 비교 기준선
  · [보조·점수화]      trait→affinity 점수 함수(스킬 게이트 + 레벨/친숙/용량 가중합)

Module 1 연동: scheduler.py 의 우선순위 인지 위상정렬 순서를 그리디의 처리 순서로
사용한다(임계도·우선순위 우선). scheduler 임포트가 불가하면 priority,id 순으로 대체.

----------------------------------------------------------------
실행 환경 (Run environment)
  · Python 3.8+ — 표준 라이브러리만 사용(third-party 의존성 없음)
  · 사용 모듈: argparse, json, os, itertools, dataclasses, typing, (선택) scheduler

실행 예시
  $ python allocator.py                 # 희소 스킬 데모 + 스프린트 배정(그리디 vs 헝가리안)
  $ python allocator.py --sprint P2-S1  # 특정 스프린트의 태스크를 배정
  $ python allocator.py --demo-only      # 희소 스킬 최소 사례만
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ───────────────────────── 친화도(affinity) 가중치 ─────────────────────────
# trait→affinity 점수표. 필수 스킬은 '하드 게이트'(미충족 시 배정 불가)이고,
# 나머지 특성(레벨/친숙도/용량)은 가중합으로 적합도를 더한다. 값이 클수록 잘 맞음.
BASE_SCORE   = 50      # 필수 스킬을 모두 갖췄을 때의 기본 점수
W_LEVEL_OK   = 12      # 레벨 ≥ 난이도일 때 적합 보너스
W_OVERQUAL   = 3       # 레벨이 난이도보다 1 높을 때마다 감점(고급 인력 낭비 방지)
W_UNDERQUAL  = 10      # 레벨이 난이도보다 1 낮을 때마다 감점(난이도 못 미침)
W_FAMILIAR   = 15      # 담당 프로젝트에 친숙하면 보너스(램프업 비용 절감)
W_CAP_OK     = 10      # 잔여 용량으로 estimate 를 소화 가능하면 보너스
W_OVERLOAD   = 4       # 용량 초과 1포인트마다 감점
W_SKILL_SURP = 2       # 태스크 태그와 겹치는 추가 보유 스킬 1개마다 소폭 보너스

SCORE_CEIL   = 200     # 비용 변환 상한(cost = CEIL − score, 항상 양수 보장)
# BIG 은 배정 불가(필수 스킬 미충족) 비용. 계약(contract): n × (실현 가능한 최대 실비용) < BIG.
# 이 조건이 지켜져야 '총비용 최소화'가 '배정 성공 수 최대화'와 일치한다(실데이터에서 여유롭게 성립).
BIG          = 10 ** 7

SCARCE_SKILLS = ("rust", "spark", "terraform", "flutter")  # 데이터셋에 설계된 희소 스킬


# ════════════════════════════════════════════════════════════════════
#  결과 컨테이너
# ════════════════════════════════════════════════════════════════════
@dataclass
class Assignment:
    """태스크 1건의 배정 결과."""
    task: str
    dev: Optional[str]            # None 이면 미배정(자격 있는 개발자 없음)
    score: int                    # 친화도 점수(미배정이면 0)
    feasible: bool                # 자격 충족 여부


@dataclass
class AllocationResult:
    """한 번의 배정(그리디 또는 헝가리안) 전체 결과."""
    method: str
    assignments: List[Assignment] = field(default_factory=list)
    total_score: int = 0
    unstaffed: List[str] = field(default_factory=list)        # 미배정 태스크
    scarce_staffed: int = 0                                   # 희소 스킬 태스크 중 배정 성공 수
    scarce_total: int = 0


@dataclass
class ScheduleAllocation:
    """전체 일정(모든 스프린트)을 가로질러 자동 배정한 결과 — Module 1↔2 유기적 연동의 산출물."""
    method: str
    assignments: List[Assignment] = field(default_factory=list)   # 태스크 1건당 1행(dev=None=미배정)
    by_dev: Dict[str, List[str]] = field(default_factory=dict)     # 개발자 → 맡은 태스크 id(스케줄 순)
    dev_load: Dict[str, int] = field(default_factory=dict)         # 개발자 → 확정 소진 스토리포인트
    dev_cap: Dict[str, int] = field(default_factory=dict)          # 개발자 → 가용 용량(capacity−load)
    total_score: int = 0
    unstaffed: List[str] = field(default_factory=list)
    sprint_order: List[str] = field(default_factory=list)         # 사용한 스케줄(스프린트) 순서
    critical_total: int = 0                                       # 임계경로 태스크 수
    critical_staffed: int = 0                                     # 그중 배정 성공 수


# ════════════════════════════════════════════════════════════════════
#  [보조 알고리즘·점수화] trait → affinity
# ════════════════════════════════════════════════════════════════════
def required_skills(task: dict) -> set:
    return set(task.get("required_skills", []))


def affinity(dev: dict, task: dict) -> Optional[int]:
    """
    개발자–태스크 친화도. 필수 스킬을 모두 보유하지 않으면 None(배정 불가).
    그 외에는 BASE + (레벨적합 + 친숙도 + 용량여유 + 스킬surplus) 가중합.
    """
    have = set(dev.get("skills", []))           # 자료구조: 집합 — 부분집합/교집합 O(1)
    req = required_skills(task)
    if not req <= have:                          # 하드 게이트: 필수 스킬 미충족
        return None

    score = BASE_SCORE
    # 레벨 vs 난이도
    lvl, dif = dev.get("level", 1), task.get("difficulty", 1)
    if lvl >= dif:
        score += W_LEVEL_OK - W_OVERQUAL * (lvl - dif)
    else:
        score -= W_UNDERQUAL * (dif - lvl)
    # 프로젝트 친숙도
    if task.get("project") in dev.get("familiar_projects", []):
        score += W_FAMILIAR
    # 잔여 용량(capacity − current_load) 으로 estimate 소화 가능?
    avail = dev.get("capacity", 0) - dev.get("current_load", 0)
    if avail >= task.get("estimate", 0):
        score += W_CAP_OK
    else:
        score -= W_OVERLOAD * (task.get("estimate", 0) - avail)
    # 필수 외 관련 스킬(태그 일치) 소폭 가산
    score += W_SKILL_SURP * len(have & set(task.get("tags", [])))
    return score


def _cost(dev: dict, task: dict) -> int:
    """헝가리안용 비용. 친화도가 높을수록 비용은 낮음. 배정 불가는 BIG."""
    s = affinity(dev, task)
    if s is None:
        return BIG
    c = SCORE_CEIL - s
    assert c < BIG, "실현 가능한 비용이 BIG 에 도달 — BIG 상수를 키우거나 점수 범위를 점검하세요."
    return c


def _cap_cost(dev: dict, task: dict, remaining_cap: int) -> int:
    """
    전체 일정 배정(rolling)용 비용. 스킬 게이트(_cost)에 더해 '잔여 용량' 게이트를 추가한다.
    개발자의 남은 용량이 이 태스크의 estimate 보다 작으면 이번 라운드 배정 불가(BIG).
    이것이 Module 1 의 스케줄을 따라 용량을 소진(carry-forward)시키는 핵심 제약이다.
    """
    if remaining_cap < int(task.get("estimate", 0)):   # 용량 부족 → 이번엔 못 맡음
        return BIG
    return _cost(dev, task)


def is_scarce_task(task: dict) -> bool:
    return any(s in SCARCE_SKILLS for s in task.get("required_skills", []))


# ════════════════════════════════════════════════════════════════════
#  [대표 알고리즘·조합최적화] 헝가리안(쿤–먼크레스) 배정
#  ── 비용행렬 cost[n][m] (n 태스크 ≤ m 개발자)에서 모든 태스크를 서로 다른
#     개발자에게 배정하되 총비용을 최소화(=총 친화도 최대화)하는 완전매칭.
#     잠재값(potential) u(행)·v(열) 과 증가경로(augmenting path)로 O(n²m).
#     (참고: e-maxx Hungarian; 1-인덱스 내부 상태를 사용.)
# ════════════════════════════════════════════════════════════════════
def hungarian(cost: Sequence[Sequence[int]]) -> Tuple[List[int], int]:
    """
    반환: (assign, total) — assign[i] = 행 i(태스크)에 배정된 열(개발자) 인덱스, 총비용.
    전제: n = 행 수 ≤ m = 열 수. (열을 패딩하지 않아도 n≤m 이면 동작.)
    """
    n = len(cost)
    if n == 0:
        return [], 0
    m = len(cost[0])
    if n > m:                               # 전제 위반 시 무한루프 대신 명확히 실패
        raise ValueError("hungarian: 행(n) ≤ 열(m) 이어야 합니다. 호출부에서 열을 패딩하세요.")
    INF = float("inf")
    # 1-인덱스 내부 배열(리스트). p[j]=열 j 에 매칭된 행, u/v=잠재값, way=증가경로 역추적.
    u = [0] * (n + 1)
    v = [0] * (m + 1)
    p = [0] * (m + 1)
    way = [0] * (m + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        # 한 행(태스크 i)을 매칭에 추가하는 증가경로 탐색
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = -1
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(m + 1):       # 잠재값 갱신(모든 라벨을 delta 만큼 이동)
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:               # 자유 열 도달 → 증가경로 완성
                break
        while True:                      # 역추적하며 매칭 갱신
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    assign = [0] * n                         # n ≤ m 이므로 모든 행이 매칭됨(미할당 잔여 없음)
    for j in range(1, m + 1):
        if p[j] > 0:
            assign[p[j] - 1] = j - 1
    total = sum(cost[i][assign[i]] for i in range(n))
    return assign, total


# ════════════════════════════════════════════════════════════════════
#  배정기 본체
# ════════════════════════════════════════════════════════════════════
class Allocator:
    def __init__(self, developers: List[dict]):
        # 자료구조: 해시맵 id→개발자 레코드
        self.devs: Dict[str, dict] = {d["id"]: d for d in developers}
        self.dev_ids: List[str] = sorted(self.devs)

    # ── 헝가리안 기반 전역 최적 배정 ──────────────────────────────────
    def allocate_hungarian(self, tasks: List[dict],
                           dev_pool: Optional[List[str]] = None) -> AllocationResult:
        """태스크 배치를 개발자 풀에 전역 최소비용으로 1:1 배정한다."""
        pool = dev_pool if dev_pool is not None else self.dev_ids
        res = AllocationResult(method="Hungarian (Kuhn–Munkres)")
        if not tasks:
            return res
        # n 태스크 ≤ m 개발자가 되도록 보장(부족하면 가상 개발자=항상 BIG 로 패딩).
        n, m = len(tasks), len(pool)
        # 자료구조: 비용 행렬(2-D 리스트)
        cost = [[_cost(self.devs[dv], t) for dv in pool] for t in tasks]
        pad = pool[:]
        if m < n:                                   # 개발자가 부족하면 가상 열 추가
            cost = [row + [BIG] * (n - m) for row in cost]
            pad = pool + [None] * (n - m)
        assign, _ = hungarian(cost)
        return self._finalise(res, tasks, assign, pad)

    # ── 우선순위 그리디 배정(비교 기준선) ─────────────────────────────
    def allocate_greedy(self, tasks: List[dict],
                        dev_pool: Optional[List[str]] = None) -> AllocationResult:
        """
        태스크를 주어진 순서(Module 1 우선순위 순)대로 처리하며, 각 태스크에
        '그 순간' 친화도가 가장 높은 미사용 개발자를 배정한다. 전역 최적은 아님.
        """
        pool = list(dev_pool if dev_pool is not None else self.dev_ids)
        # 'priority-ordered' 는 호출부가 넘기는 순서에 의해 결정된다(여기서는 Module 1 우선순위 순).
        res = AllocationResult(method="Greedy (caller-ordered = Module 1 priority)")
        used: set = set()                           # 자료구조: 집합 — 사용된 개발자 O(1) 조회
        for t in tasks:
            best_dev, best_score = None, None
            for dv in pool:
                if dv in used:
                    continue
                s = affinity(self.devs[dv], t)
                if s is None:
                    continue
                if best_score is None or s > best_score or (s == best_score and dv < best_dev):
                    best_dev, best_score = dv, s
            if best_dev is not None:
                used.add(best_dev)
                res.assignments.append(Assignment(t["id"], best_dev, best_score, True))
            else:
                res.assignments.append(Assignment(t["id"], None, 0, False))
        return self._tally(res, tasks)

    # ════════════════════════════════════════════════════════════════
    #  [핵심·Module 1↔2 유기적 연동] 전체 일정 기반 자동 배정 (rolling, capacity-aware)
    #  ── Module 1 이 정한 '스프린트 스케줄 순서'대로 진행하며, 각 스프린트 안에서
    #     임계경로 태스크부터(slack↑) 헝가리안으로 '그 순간 최적' 1:1 매칭을 반복(round)한다.
    #     한 개발자는 잔여 용량이 남는 한 여러 태스크를 맡을 수 있고(라운드 누적),
    #     소진된 용량은 다음 스프린트로 '이월(carry-forward)'되어 전 일정에 걸쳐 누적된다.
    #
    #     자료구조: remaining(해시맵 dev→잔여용량) · buckets(해시맵 sprint→태스크들) ·
    #               used(집합) · 비용행렬(2-D 리스트)
    #     알고리즘: [대표] 라운드별 헝가리안 최적매칭  /  [보조] 라운드별 그리디(비교 기준선)
    # ════════════════════════════════════════════════════════════════
    def allocate_schedule(self, tasks: List[dict], slack: Dict[str, int],
                          critical: Dict[str, bool], sprint_order: List[str],
                          method: str = "hungarian") -> ScheduleAllocation:
        """
        모든 태스크를 스케줄(스프린트) 순서로 개발자에게 자동 배정한다.
        slack/critical 은 Module 1(스케줄러)에서 추출한 임계도 정보(intra-sprint 우선순위).
        method: 'hungarian'(전역최적 라운드) | 'greedy'(기준선 라운드).
        """
        label = ("Schedule · Hungarian rolling" if method == "hungarian"
                 else "Schedule · Greedy rolling")
        res = ScheduleAllocation(method=label)

        # 잔여 용량(remaining) = capacity − current_load. 전 일정에 걸친 '전역 예산'.
        remaining: Dict[str, int] = {
            d: int(self.devs[d].get("capacity", 0)) - int(self.devs[d].get("current_load", 0))
            for d in self.dev_ids}
        res.dev_cap = dict(remaining)                 # 시작 시점 가용 용량(util% 계산용)

        by_id = {t["id"]: t for t in tasks}

        # 자료구조: 해시맵 sprint→[태스크]. 스프린트 없는 태스크는 '_backlog' 버킷.
        buckets: Dict[str, List[dict]] = {}
        for t in tasks:
            buckets.setdefault(t.get("sprint") or "_backlog", []).append(t)

        # Module 1 스케줄 순서를 우선 적용하고, 거기에 없는 스프린트는 뒤에(결정적).
        order = [s for s in sprint_order if s in buckets]
        order += [s for s in sorted(buckets) if s not in order]
        res.sprint_order = order

        by_dev: Dict[str, List[str]] = {d: [] for d in self.dev_ids}
        dev_load: Dict[str, int] = {d: 0 for d in self.dev_ids}

        for sp in order:
            pend = buckets[sp]
            # intra-sprint 우선순위 = Module 1 임계도: 임계경로 먼저 → slack↑ → priority↑ → id
            pend = sorted(pend, key=lambda t: (0 if critical.get(t["id"]) else 1,
                                               slack.get(t["id"], 0),
                                               t.get("priority", 4), t["id"]))
            for a in self._roll_sprint(pend, remaining, method):
                res.assignments.append(a)
                if a.dev:
                    by_dev[a.dev].append(a.task)
                    dev_load[a.dev] += int(by_id[a.task].get("estimate", 0))

        # 집계
        res.by_dev = {d: ts for d, ts in by_dev.items() if ts}      # 실제 배정된 개발자만
        res.dev_load = {d: dev_load[d] for d in res.by_dev}
        res.total_score = sum(a.score for a in res.assignments if a.dev)
        res.unstaffed = [a.task for a in res.assignments if not a.dev]
        crit_ids = {tid for tid in by_id if critical.get(tid)}
        res.critical_total = len(crit_ids)
        res.critical_staffed = sum(1 for a in res.assignments if a.dev and a.task in crit_ids)
        return res

    def _roll_sprint(self, pend: List[dict], remaining: Dict[str, int],
                     method: str) -> List[Assignment]:
        """
        한 스프린트의 태스크들을 '라운드 반복'으로 배정한다. 각 라운드는 (헝가리안/그리디)로
        가용 개발자에게 1태스크씩 매칭하고, 배정된 만큼 remaining 을 깎는다. 한 개발자가
        용량이 남으면 다음 라운드에서 또 맡을 수 있다(스프린트 내 다중 배정). 더 이상 아무도
        못 맡으면(round 가 0건 커밋) 남은 태스크는 미배정으로 종료.
        """
        out: List[Assignment] = []
        todo = list(pend)
        while todo:
            free = [d for d in self.dev_ids if remaining[d] > 0]   # 용량 남은 개발자만
            if not free:
                out += [Assignment(t["id"], None, 0, False) for t in todo]
                break
            chosen = (self._round_hungarian(todo, free, remaining) if method == "hungarian"
                      else self._round_greedy(todo, free, remaining))
            if not chosen:                                          # 이번 라운드 0건 → 더는 불가
                out += [Assignment(t["id"], None, 0, False) for t in todo]
                break
            nxt: List[dict] = []
            for t in todo:
                d = chosen.get(t["id"])
                if d is not None:
                    s = affinity(self.devs[d], t)
                    out.append(Assignment(t["id"], d, s if s is not None else 0, True))
                    remaining[d] -= int(t.get("estimate", 0))      # 용량 소진(이월)
                else:
                    nxt.append(t)                                  # 이번 라운드엔 못 받음 → 다음 라운드
            todo = nxt
        return out

    def _round_hungarian(self, todo: List[dict], free: List[str],
                         remaining: Dict[str, int]) -> Dict[str, str]:
        """한 라운드: 용량-인지 비용행렬에 헝가리안을 돌려 task→dev 최적 1:1 매칭(실현가능분만)."""
        # 자료구조: 비용 행렬(2-D 리스트). n 태스크 > m 개발자면 가상 열(BIG)로 패딩.
        cost = [[_cap_cost(self.devs[d], t, remaining[d]) for d in free] for t in todo]
        n, m = len(todo), len(free)
        pad: List[Optional[str]] = list(free)
        if m < n:
            cost = [row + [BIG] * (n - m) for row in cost]
            pad = list(free) + [None] * (n - m)
        assign, _ = hungarian(cost)
        chosen: Dict[str, str] = {}
        for i, t in enumerate(todo):
            col = assign[i]
            d = pad[col] if 0 <= col < len(pad) else None
            if d is not None and cost[i][col] < BIG:               # 실현 가능(스킬·용량 충족)만 커밋
                chosen[t["id"]] = d
        return chosen

    def _round_greedy(self, todo: List[dict], free: List[str],
                      remaining: Dict[str, int]) -> Dict[str, str]:
        """한 라운드(기준선): 태스크 순서대로 '그 순간' 친화도 최고인 미사용·용량충분 개발자 선택."""
        used: set = set()                                          # 자료구조: 집합 — 라운드 내 사용 개발자
        chosen: Dict[str, str] = {}
        for t in todo:
            best, best_s = None, None
            est = int(t.get("estimate", 0))
            for d in free:
                if d in used or remaining[d] < est:
                    continue
                s = affinity(self.devs[d], t)
                if s is None:
                    continue
                if best_s is None or s > best_s or (s == best_s and d < best):
                    best, best_s = d, s
            if best is not None:
                used.add(best)
                chosen[t["id"]] = best
        return chosen

    # ── 결과 정리 헬퍼 ───────────────────────────────────────────────
    def _finalise(self, res: AllocationResult, tasks: List[dict],
                  assign: List[int], pad: List[Optional[str]]) -> AllocationResult:
        for i, t in enumerate(tasks):
            col = assign[i]
            dv = pad[col] if 0 <= col < len(pad) else None
            s = affinity(self.devs[dv], t) if dv is not None else None
            if dv is None or s is None:             # 가상 개발자/자격 미달 → 미배정
                res.assignments.append(Assignment(t["id"], None, 0, False))
            else:
                res.assignments.append(Assignment(t["id"], dv, s, True))
        return self._tally(res, tasks)

    @staticmethod
    def _tally(res: AllocationResult, tasks: List[dict]) -> AllocationResult:
        by_id = {t["id"]: t for t in tasks}
        res.total_score = sum(a.score for a in res.assignments if a.dev)
        res.unstaffed = [a.task for a in res.assignments if not a.dev]
        scarce_ids = {t["id"] for t in tasks if is_scarce_task(t)}
        res.scarce_total = len(scarce_ids)
        res.scarce_staffed = sum(1 for a in res.assignments if a.dev and a.task in scarce_ids)
        return res


# ════════════════════════════════════════════════════════════════════
#  데이터 로딩 + Module 1 연동(처리 순서)
# ════════════════════════════════════════════════════════════════════
def _load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_store(data_dir: str):
    devs = _load_json(os.path.join(data_dir, "developers.json"))
    tasks = _load_json(os.path.join(data_dir, "tasks.json"))
    projects, sprints = [], []
    if os.path.exists(os.path.join(data_dir, "projects.json")):
        projects = _load_json(os.path.join(data_dir, "projects.json"))
    if os.path.exists(os.path.join(data_dir, "sprints.json")):
        sprints = _load_json(os.path.join(data_dir, "sprints.json"))
    return devs, tasks, projects, sprints


def module1_order(tasks: List[dict], projects: List[dict], sprints: List[dict]) -> List[str]:
    """Module 1(scheduler)의 우선순위 인지 위상정렬 순서. 임포트 실패 시 priority,id 순 대체."""
    try:
        import scheduler  # noqa: 동일 폴더의 Module 1
        sch = scheduler.Scheduler(tasks, projects, sprints)
        order, _ = sch.priority_topo_sort()
        return order
    except Exception:
        return [t["id"] for t in sorted(tasks, key=lambda t: (t.get("priority", 4), t["id"]))]


def schedule_view(tasks: List[dict], projects: List[dict], sprints: List[dict]
                  ) -> Tuple[Dict[str, int], Dict[str, bool], List[str]]:
    """
    Module 1↔2 연동 지점. 스케줄러에서 전체 일정 배정에 필요한 세 가지를 추출한다.
      · slack[tid]      : 태스크별 여유(임계도). 작을수록 임계 → 스프린트 내 우선 배정.
      · critical[tid]   : 임계경로(slack==0) 여부. True 면 '먼저 배정'.
      · sprint_order[]  : 스프린트 스케줄 순서(마감 이른 프로젝트 먼저).
    스케줄러 임포트 실패 시: priority 를 임계도 proxy 로, 스프린트 순서는 (프로젝트,번호)로 대체.
    """
    try:
        import scheduler  # noqa: 동일 폴더의 Module 1
        sch = scheduler.Scheduler(tasks, projects, sprints)
        slack: Dict[str, int] = {}
        critical: Dict[str, bool] = {}
        for pid in sch.project_ids():
            cp = sch.critical_path(pid)
            slack.update(cp.slack)
            for tid in cp.slack:                       # 사이클 프로젝트는 임계경로 미정의 → critical=False
                critical[tid] = (cp.slack[tid] == 0) and not cp.has_cycle
        return slack, critical, sch.sprint_order()
    except Exception:
        # 폴백: scheduler 없이도 동작. priority(1최상)를 임계도 proxy 로 사용.
        slack = {t["id"]: t.get("priority", 4) for t in tasks}
        critical = {t["id"]: (t.get("priority", 4) == 1) for t in tasks}
        sids = sorted({t.get("sprint") for t in tasks if t.get("sprint")})
        return slack, critical, sids


def order_tasks(tasks: List[dict], order_ids: List[str]) -> List[dict]:
    # Module 1 순서에 없는 태스크(예: 사이클로 배출되지 못한 것)는 (priority, id) 로 안정 정렬해 꼬리에.
    rank = {tid: i for i, tid in enumerate(order_ids)}
    return sorted(tasks, key=lambda t: (rank.get(t["id"], 10 ** 9),
                                        t.get("priority", 4), t["id"]))


# ════════════════════════════════════════════════════════════════════
#  출력(리포트)
# ════════════════════════════════════════════════════════════════════
def _rule(title: str = "", ch: str = "─", width: int = 80) -> str:
    if not title:
        return ch * width
    return f"{ch * 2} {title} {ch * max(width - len(title) - 4, 0)}"


def qualified_devs(task: dict, devs: Dict[str, dict]) -> List[str]:
    """이 태스크의 필수 스킬을 '모두' 보유한 개발자 id 목록(affinity 하드 게이트와 동일 기준)."""
    req = required_skills(task)
    return sorted(d for d, dev in devs.items() if req <= set(dev.get("skills", [])))


def classify_unstaffed(unstaffed: List[str], by_id: Dict[str, dict],
                       devs: Dict[str, dict]) -> Tuple[List[str], List[str], Dict[str, int]]:
    """
    미배정 태스크를 두 부류로 나눈다(조직적 의미가 다름).
      · unstaffable : 필수 스킬 조합을 가진 개발자가 '아예 없음' → 채용/교육 신호.
      · contended   : 자격자는 있으나 모두 용량 소진 → 병목 전문가 재배치/증원 신호.
    또한 contended 태스크의 '병목 전문가'별 적체 건수를 센다. 단, 병목으로 집계하는 자격자는
    '시작 시점 가용 용량(capacity−current_load)이 양수'인 개발자로 한정한다 — 처음부터 과부하
    상태였던 개발자는 애초에 배정 불가였으므로 '재배치하면 해결될 병목'으로 오인하지 않는다.
    """
    unstaffable: List[str] = []
    contended: List[str] = []
    bottleneck: Dict[str, int] = {}
    for tid in unstaffed:
        q = qualified_devs(by_id[tid], devs)
        if not q:
            unstaffable.append(tid)
        else:
            contended.append(tid)
            for d in q:                              # 자격자 중 '가용 용량이 있었던' 개발자만 병목으로
                if devs[d].get("capacity", 0) - devs[d].get("current_load", 0) > 0:
                    bottleneck[d] = bottleneck.get(d, 0) + 1
    return unstaffable, contended, bottleneck


def print_schedule_allocation(title: str, tasks: List[dict],
                              greedy: ScheduleAllocation, hung: ScheduleAllocation,
                              devs: Dict[str, dict], max_rows: int = 20) -> None:
    """전체 일정 자동 배정 결과 리포트 — 개발자별 워크로드 + 그리디 vs 헝가리안 조직 집계."""
    print(_rule(title, "═"))
    by_id = {t["id"]: t for t in tasks}
    n_proj = len({t.get("project") for t in tasks})
    print(f"  태스크 {len(tasks)}개 · 프로젝트 {n_proj}개 · 스프린트 {len(hung.sprint_order)}개")
    print(f"  스케줄 순서(Module 1): {' → '.join(hung.sprint_order)}\n")

    # ── 조직 집계: 그리디 vs 헝가리안 ──
    print(f"  {'방식':<26}{'총 친화도':>10}{'배정':>8}{'미배정':>8}{'임계 배정':>12}{'사용 개발자':>12}")
    for r in (greedy, hung):
        staffed = len(r.assignments) - len(r.unstaffed)
        print(f"  {r.method:<26}{r.total_score:>10}{staffed:>8}{len(r.unstaffed):>8}"
              f"{f'{r.critical_staffed}/{r.critical_total}':>12}{len(r.by_dev):>12}")
    gap = hung.total_score - greedy.total_score
    print(f"\n  → 헝가리안이 전 일정에서 총 친화도 +{gap}, "
          f"미배정 {len(greedy.unstaffed)}→{len(hung.unstaffed)}, "
          f"임계경로 커버리지 {greedy.critical_staffed}/{greedy.critical_total}"
          f"→{hung.critical_staffed}/{hung.critical_total}.")

    # ── 미배정 진단: '스킬 부재(채용)' vs '병목 전문가 적체(재배치)' ──
    if hung.unstaffed:
        unstaffable, contended, bottleneck = classify_unstaffed(hung.unstaffed, by_id, devs)
        print(f"\n  [미배정 진단] 총 {len(hung.unstaffed)}개")
        if unstaffable:
            s = ", ".join(unstaffable[:10]) + (" …" if len(unstaffable) > 10 else "")
            print(f"    · 스킬 부재 {len(unstaffable)}개 — 필수 스킬 조합 보유자가 0명(채용/교육 필요): {s}")
        if contended:
            s = ", ".join(contended[:10]) + (" …" if len(contended) > 10 else "")
            print(f"    · 전문가 적체 {len(contended)}개 — 자격자는 있으나 용량 소진(재배치/증원 필요): {s}")
            ranked = sorted(bottleneck.items(), key=lambda kv: (-kv[1], kv[0]))
            top = ranked[:4]
            if top:
                names = ", ".join(f"{d}({n}건)" for d, n in top)
                more = " …" if len(ranked) > 4 else ""     # 잘렸음을 다른 목록과 동일하게 표기
                print(f"      └ 병목 전문가(적체 태스크의 자격자): {names}{more}")

    # ── 개발자별 워크로드(헝가리안), 부하 큰 순 ──
    # 'avail' = 가용용량(capacity − current_load), 즉 스케줄러가 채울 수 있는 잔여 예산.
    # util = load / avail = '가용 용량 중 이번 일정이 소진한 비율'.
    print(f"\n  [개발자별 워크로드 — 헝가리안, 부하 큰 순]   util = load / avail(가용용량)")
    print(f"    {'dev':<7}{'lvl':>4}{'tasks':>6}{'load':>6}{'avail':>6}{'util':>7}  {'projects'}")
    rows = sorted(hung.by_dev.items(),
                  key=lambda kv: (-hung.dev_load[kv[0]], kv[0]))
    for d, ts in rows[:max_rows]:
        dev = devs[d]
        avail = hung.dev_cap.get(d, dev.get("capacity", 0))
        load = hung.dev_load[d]
        util = (load / avail * 100) if avail > 0 else 0.0
        projs = ",".join(sorted({by_id[t]["project"] for t in ts}))
        print(f"    {d:<7}{dev.get('level',1):>4}{len(ts):>6}{load:>6}{avail:>6}"
              f"{util:>6.0f}%  {projs}")
    if len(rows) > max_rows:
        print(f"    … 외 {len(rows) - max_rows}명")
    # 워크로드 분포 한 줄 요약
    if hung.by_dev:
        loads = sorted(hung.dev_load.values())
        caps_used = [hung.dev_load[d] / hung.dev_cap[d] for d in hung.by_dev if hung.dev_cap[d] > 0]
        avg_util = sum(caps_used) / len(caps_used) * 100 if caps_used else 0.0
        idle = len(devs) - len(hung.by_dev)
        print(f"\n    분포: 사용 개발자 {len(hung.by_dev)}/{len(devs)}명(유휴 {idle}) · "
              f"load 최소 {loads[0]}~최대 {loads[-1]} · 평균 가용용량 소진율 {avg_util:.0f}%")
    print()


def print_comparison(title: str, tasks: List[dict],
                     greedy: AllocationResult, hung: AllocationResult,
                     devs: Dict[str, dict]) -> None:
    print(_rule(title, "═"))
    by_id = {t["id"]: t for t in tasks}
    gmap = {a.task: a for a in greedy.assignments}
    hmap = {a.task: a for a in hung.assignments}

    print(f"  태스크 {len(tasks)}개  ·  희소 스킬 태스크 {greedy.scarce_total}개")
    print(f"    {'task':<7}{'pri':>4}{'req_skills':>26}   {'GREEDY':>14}   {'HUNGARIAN':>14}")
    for t in tasks:
        tid = t["id"]
        g, h = gmap[tid], hmap[tid]
        scarce = "✦" if is_scarce_task(t) else " "
        req = ",".join(t.get("required_skills", []))[:24]
        gtxt = f"{g.dev}({g.score})" if g.dev else "── 미배정 ──"
        htxt = f"{h.dev}({h.score})" if h.dev else "── 미배정 ──"
        flag = "  ◄ 차이" if (g.dev != h.dev) else ""
        print(f"  {scarce} {tid:<7}{t.get('priority',4):>4}{req:>26}   "
              f"{gtxt:>14}   {htxt:>14}{flag}")

    print()
    print(f"  {'':12}{'총 친화도':>10}{'미배정':>8}{'희소 배정':>12}")
    print(f"  {'GREEDY':<12}{greedy.total_score:>10}{len(greedy.unstaffed):>8}"
          f"{f'{greedy.scarce_staffed}/{greedy.scarce_total}':>12}")
    print(f"  {'HUNGARIAN':<12}{hung.total_score:>10}{len(hung.unstaffed):>8}"
          f"{f'{hung.scarce_staffed}/{hung.scarce_total}':>12}")
    gap = hung.total_score - greedy.total_score
    print(f"\n  → 헝가리안이 그리디 대비 총 친화도 +{gap}, "
          f"미배정 {len(greedy.unstaffed)}→{len(hung.unstaffed)}, "
          f"희소 배정 {greedy.scarce_staffed}→{hung.scarce_staffed}.")
    if greedy.unstaffed and not hung.unstaffed:
        print(f"     그리디가 남긴 미배정: {', '.join(greedy.unstaffed)} "
              f"— 희소 인력을 평범한 태스크에 써버린 결과.")
    print()


# ════════════════════════════════════════════════════════════════════
#  데모: 희소 스킬 최소 사례 구성
# ════════════════════════════════════════════════════════════════════
def _scarce_skill_of(task: dict) -> Optional[str]:
    for s in task.get("required_skills", []):
        if s in SCARCE_SKILLS:
            return s
    return None


def build_scarce_demo(alloc: "Allocator", tasks: List[dict]
                      ) -> Tuple[List[dict], List[str], str]:
    """
    실제 데이터에서 '그리디는 희소 태스크를 미배정으로 남기지만 헝가리안은 전부 배정하는'
    최소 반례(stranding instance)를 탐색·검증해 구성한다. 핵심 짝(pair):
        S = 희소 태스크(자격자 H 가 극소수),
        O = 평범한 태스크(H + 대체개발자 D_alt 가 자격, 단 D_alt 는 S 자격 없음).
    배치를 [O, S] 순서로 두면 그리디는 O 에 H 를 먼저 써버려 S 를 못 채운다.
    헝가리안은 O→D_alt, S→H 로 전부 채운다. 서로 다른 희소 스킬의 짝을 '검증하며'
    합쳐(merge) 풀이 겹치지 않게 한다. 그래도 합친 사례가 여전히 반례임을 재확인한다.
    반환: (태스크 배치, 개발자 풀, 설명)
    """
    devmap = alloc.devs
    devs = [devmap[d] for d in alloc.dev_ids]

    def quals(t):                               # 이 태스크 자격이 되는 모든 개발자
        return [d["id"] for d in devs if affinity(devmap[d["id"]], t) is not None]

    scarce_tasks = sorted(
        (t for t in tasks if is_scarce_task(t) and len(quals(t)) >= 1),
        key=lambda t: (len(quals(t)), t.get("priority", 4), t["id"]))   # 자격자 적은 것 우선
    ordinary = [t for t in tasks if not is_scarce_task(t)]
    ordinary.sort(key=lambda t: (t.get("priority", 4), t["id"]))

    def strands_all_scarce(batch, pool):
        """그리디가 배치 내 모든 희소 태스크를 미배정으로 남기고, 헝가리안은 전부 배정?"""
        g = alloc.allocate_greedy(batch, pool)
        h = alloc.allocate_hungarian(batch, pool)
        scarce_ids = {t["id"] for t in batch if is_scarce_task(t)}
        g_unstaffed = set(g.unstaffed)
        return scarce_ids and scarce_ids <= g_unstaffed and not h.unstaffed

    batch: List[dict] = []
    pool: set = set()
    used_skills: set = set()

    for S in scarce_tasks:
        sk = _scarce_skill_of(S)
        if sk in used_skills:                   # 희소 스킬당 한 짝만(다양성)
            continue
        Hs = [h for h in quals(S) if h not in pool]
        found = False
        for H in Hs:
            for O in ordinary:
                if O in batch or affinity(devmap[H], O) is None:
                    continue
                # 대체 개발자: O 자격 + 미사용 + S 자격 없음(그래야 S 는 H 만 채울 수 있음)
                alts = [d for d in quals(O)
                        if d != H and d not in pool
                        and affinity(devmap[d], S) is None]
                for D_alt in alts:
                    cand_batch = batch + [O, S]
                    cand_pool = sorted(pool | {H, D_alt})
                    if strands_all_scarce(cand_batch, cand_pool):
                        batch, pool = cand_batch, set(cand_pool)
                        used_skills.add(sk)
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if len(used_skills) >= 3:               # 3개 희소 스킬이면 충분히 인상적
            break

    verified = bool(batch)                      # 검증된 stranding 반례를 찾았는가?
    if not batch:                               # 안전망: 반례를 못 찾은 경우
        if not scarce_tasks:                    # 희소 스킬 태스크 자체가 없는 데이터셋
            return [], alloc.dev_ids[:1], "이 데이터셋에는 자격자가 있는 희소 스킬 태스크가 없습니다."
        S = scarce_tasks[0]                     # 가장 희소한 태스크라도 참고용으로 표시
        batch = [S]
        pool = set(quals(S)[:1]) or {alloc.dev_ids[0]}

    if verified:
        desc = ("희소 스킬 태스크(✦)는 자격자가 극소수다. [평범 태스크 O, 희소 태스크 S] 순서로 "
                "처리하는 그리디는 O 에 희소 인력 H 를 먼저 써버려 S 를 '미배정'으로 남긴다. "
                "헝가리안은 O 를 대체 개발자에게 주고 H 를 S 에 배정해 전부 채운다.")
    else:
        desc = "데이터에서 stranding 반례를 찾지 못해, 가장 희소한 태스크만 참고용으로 표시합니다."
    return batch, sorted(pool), desc


# ════════════════════════════════════════════════════════════════════
#  메인(CLI)
# ════════════════════════════════════════════════════════════════════
def main(argv: Optional[List[str]] = None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    default_data = os.path.join(here, "data")

    ap = argparse.ArgumentParser(
        description="Squadron Module 2 — 특성기반 배정기 (헝가리안 vs 그리디)")
    ap.add_argument("--data", default=default_data, help="데이터 폴더 (기본: data)")
    ap.add_argument("--sprint", default=None, help="이 스프린트의 태스크만 상세 배정 (예: P2-S1)")
    ap.add_argument("--demo-only", action="store_true", help="희소 스킬 최소 사례만 출력")
    ap.add_argument("--full-only", action="store_true", help="전체 일정 자동 배정만 출력")
    ap.add_argument("--max-rows", type=int, default=20,
                    help="개발자별 워크로드 표의 최대 행 수 (기본 20)")
    ap.add_argument("--max-devs", type=int, default=30,
                    help="--sprint 상세 배정 시 사용할 개발자 풀 최대 크기 (기본 30)")
    args = ap.parse_args(argv)

    try:
        devs, tasks, projects, sprints = load_store(args.data)
    except FileNotFoundError as e:
        ap.error(f"데이터 파일을 찾을 수 없습니다: {e}")

    alloc = Allocator(devs)
    by_id = {t["id"]: t for t in tasks}
    order_ids = module1_order(tasks, projects, sprints)

    print(_rule("SQUADRON · Module 2 — Trait-based Allocator", "═"))
    print(f"  개발자 {len(devs)}명  ·  태스크 {len(tasks)}개  ·  "
          f"희소 스킬 {', '.join(SCARCE_SKILLS)}\n")

    # ── ① 전체 일정 자동 배정 (Module 1↔2 유기적 연동, 핵심 산출물) ──
    # Module 1 에서 임계도(slack·임계여부)와 스프린트 스케줄 순서를 받아, 그 순서대로
    # 용량을 소진하며 전 backlog 를 개발자에게 자동 배정한다. 그리디 vs 헝가리안 비교.
    if not args.demo_only:
        slack, critical, sprint_ord = schedule_view(tasks, projects, sprints)
        sg = alloc.allocate_schedule(tasks, slack, critical, sprint_ord, method="greedy")
        sh = alloc.allocate_schedule(tasks, slack, critical, sprint_ord, method="hungarian")
        print_schedule_allocation(
            "① 전체 일정 자동 배정 — 스케줄 순서대로 용량 소진 (그리디 vs 헝가리안)",
            tasks, sg, sh, alloc.devs, max_rows=args.max_rows)

    if args.full_only:
        return 0

    # ── ② 희소 스킬 최소 사례 — 검증된 stranding 순서를 유지하므로 재정렬하지 않는다 ──
    # '왜 전역 최적(헝가리안)인가'를 1:1 배정 최소 반례로 선명히 보여주는 보조 데모.
    batch, pool, desc = build_scarce_demo(alloc, tasks)
    g = alloc.allocate_greedy(batch, pool)
    h = alloc.allocate_hungarian(batch, pool)
    print("  " + desc + f"\n  (개발자 풀 {len(pool)}명: {', '.join(pool)})\n")
    print_comparison("② 희소 스킬 배정 — 그리디 vs 헝가리안 (1:1 최소 반례)", batch, g, h, alloc.devs)

    if args.demo_only:
        return 0

    # ── ③ (선택) 특정 스프린트 상세 배정 — --sprint 지정 시에만 ──
    if args.sprint:
        s_tasks = [by_id[t["id"]] for t in tasks if t.get("sprint") == args.sprint]
        if not s_tasks:
            print(f"  (스프린트 {args.sprint} 에 태스크가 없습니다.)")
            return 0
        s_tasks = order_tasks(s_tasks, order_ids)
        pool2 = alloc.dev_ids[:args.max_devs]
        g2 = alloc.allocate_greedy(s_tasks, pool2)
        h2 = alloc.allocate_hungarian(s_tasks, pool2)
        print_comparison(f"③ 스프린트 {args.sprint} 상세 배정 — 그리디 vs 헝가리안 "
                         f"(개발자 {len(pool2)}명)", s_tasks, g2, h2, alloc.devs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
