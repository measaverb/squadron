#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron - Module 3: 스프린트 플래너 (Sprint Planner)
======================================================

스프린트 용량(Capacity) 제한 하에서 비즈니스 가치(Value)의 합을 극대화하는 태스크를 선택한다.
프로젝트 스케줄러(Module 1)의 의존성(DAG) 정보를 준수하고, 
계획된 결과를 개발자 배정기(Module 2)로 전달하여 유기적으로 연동한다.

----------------------------------------------------------------
사용 자료구조 (Data structures)  -- 과목 요구사항: >=2개
  · 2D DP 테이블 (2-D List)               : 0/1 배낭 DP 알고리즘용 점화식 테이블 수립에 활용.
  · 해시맵 (dict)                         : 태스크 속성 조회, 결과 매핑, 스프린트별 태스크 분류.
  · 집합 (set)                            : 완료된 태스크 추적 및 O(1) 시간 내 의존성 검사에 활용.

사용 알고리즘 (Algorithms)  -- 과목 요구사항: >=2개, 대표 알고리즘은 서로 다른 계열
  · [대표·동적계획법]  0/1 배낭 DP (Knapsack Dynamic Programming) -- 최적해 산출
  · [대표·백트래킹]    백트래킹 탐색 (Backtracking with Fractional Bound) -- 최적해 산출
  · [보조·그리디]      가치 밀도 그리디 (Value Density Greedy) -- 비교 기준선

----------------------------------------------------------------
실행 환경 (Run environment)
  · Python 3.8+ -- 표준 라이브러리만 사용 (third-party 의존성 없음)
  · 사용 모듈: argparse, json, os, time, dataclasses, typing

실행 예시
  $ python planner.py                         # 전체 글로벌 일정 플래닝 실행
  $ python planner.py --demo-only             # README.md 에 제시된 P3-S4 배낭 반례 검증
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# ====================================================================
#  데이터 모델 (결과 컨테이너)
# ====================================================================
@dataclass
class SprintResult:
    """한 스프린트의 배낭 문제 최적화 결과."""
    sprint_id: str
    method: str
    selected_tasks: List[str]            # 선택된 태스크 ID 목록
    carried_tasks: List[str]             # 용량 초과로 이월(Carry forward)된 태스크 ID 목록
    total_value: int                     # 획득한 비즈니스 가치 합
    used_capacity: int                   # 소진한 스토리포인트 합
    elapsed_ms: float = 0.0              # 알고리즘 수행 시간 (ms)


@dataclass
class GlobalPlanResult:
    """전체 조직/프로젝트의 글로벌 스프린트 플래닝 결과."""
    method: str
    sprint_plans: Dict[str, SprintResult]  # 스프린트 ID -> 결과 맵
    total_value: int                     # 모든 스프린트의 가치 합
    total_capacity_used: int             # 모든 스프린트의 소진 용량 합
    carried_forward_total: int           # 이월된 누적 태스크 수
    unplanned_tasks: List[str]           # 모든 스프린트가 끝나고도 결국 선택되지 못한 태스크


# ====================================================================
#  스프린트 플래너 본체
# ====================================================================
class SprintPlanner:
    """
    스프린트 내의 스토리포인트 용량 제한 하에서 가치가 최대화되도록 
    다양한 알고리즘(DP, Backtracking, Greedy)을 사용하여 태스크를 설계 및 선별한다.
    """

    def __init__(self, tasks: List[dict], sprints: Optional[List[dict]] = None,
                 projects: Optional[List[dict]] = None):
        # 자료구조: 해시맵 id -> task. 빠른 접근을 위해 활용. (자료구조 1)
        self.tasks: Dict[str, dict] = {t["id"]: t for t in tasks}
        self.sprints: List[dict] = sprints or []
        self.projects: List[dict] = projects or []

    # ================================================================
    #  [대표 알고리즘 ①·동적계획법] 0/1 배낭 DP (Knapsack DP)
    #  -- 점화식을 기반으로 2차원 DP 테이블을 채워 최적의 태스크 묶음을 구한다.
    #     시간복잡도: O(N * W), 공간복잡도: O(N * W)
    # ================================================================
    def plan_dp(self, tasks_subset: List[dict], capacity: int) -> Tuple[List[str], int, int]:
        """
        0/1 배낭 DP 알고리즘을 사용해 용량 내 최대 가치를 갖는 태스크를 선택한다.
        반환: (선택된 태스크 ID 목록, 소진 용량 합, 획득 가치 합)
        """
        N = len(tasks_subset)
        W = capacity
        if N == 0 or W <= 0:
            return [], 0, 0

        # 자료구조: 2D DP 테이블 (2-D List). (자료구조 2)
        # dp[i][w] : i번째 태스크까지 고려하고 남은 용량이 w일 때의 최대 가치
        dp = [[0] * (W + 1) for _ in range(N + 1)]

        # DP 테이블 채우기 (동적계획법 상향식 계산)
        for i in range(1, N + 1):
            t = tasks_subset[i - 1]
            wt = int(t.get("estimate", 0))
            val = int(t.get("value", 0))
            for w in range(W + 1):
                if wt <= w:
                    # 점화식: i번째 아이템을 포함하지 않는 경우 vs 포함하는 경우 중 최댓값 선택
                    dp[i][w] = max(dp[i - 1][w], dp[i - 1][w - wt] + val)
                else:
                    dp[i][w] = dp[i - 1][w]

        # DP 테이블 역추적 (Backtracking DP table)을 통해 선택된 아이템 식별
        selected = []
        w = W
        for i in range(N, 0, -1):
            t = tasks_subset[i - 1]
            wt = int(t.get("estimate", 0))
            # dp[i][w] 값이 이전 행의 같은 열 값과 다르다면, i번째 아이템이 포함된 것임
            if dp[i][w] != dp[i - 1][w]:
                selected.append(t["id"])
                w -= wt

        selected.reverse()
        total_value = dp[N][W]
        total_estimate = W - w

        return selected, total_estimate, total_value

    # ================================================================
    #  [대표 알고리즘 ②·백트래킹] 백트래킹 (Backtracking)
    #  -- DFS 탐색 트리를 타고 내려가며, 용량 초과 및 분수 배낭(Fractional Knapsack)
    #     바운드를 이용해 유망하지 않은 노드를 가지치기(Pruning)하여 최적해를 구한다.
    #     시간복잡도: 최악 O(2^N)
    # ================================================================
    def plan_backtracking(self, tasks_subset: List[dict], capacity: int) -> Tuple[List[str], int, int]:
        """
        백트래킹과 Fractional Knapsack 상한선(Bound) 가지치기를 사용하여 최적해를 도출한다.
        반환: (선택된 태스크 ID 목록, 소진 용량 합, 획득 가치 합)
        """
        N = len(tasks_subset)
        W = capacity
        if N == 0 or W <= 0:
            return [], 0, 0

        # 가지치기 성능 극대화를 위해 가치 밀도(value / estimate) 기준 내림차순 정렬
        sorted_tasks = sorted(
            tasks_subset,
            key=lambda x: (int(x.get("value", 0)) / max(int(x.get("estimate", 1)), 1)),
            reverse=True
        )

        best_value = 0
        best_selection: List[str] = []
        best_weight = 0

        # Fractional Knapsack을 이용해 현재 노드 하류에서 얻을 수 있는 최대 가치의 상한(Bound)을 계산
        def get_bound(idx: int, current_w: int, current_v: int) -> float:
            if current_w >= W:
                return 0.0
            
            bound = float(current_v)
            total_w = current_w
            
            # 남은 용량을 탐욕적으로 채우며 분수 부분만큼 소수로 가산
            for i in range(idx, N):
                t = sorted_tasks[i]
                wt = int(t.get("estimate", 0))
                val = int(t.get("value", 0))
                
                if total_w + wt <= W:
                    total_w += wt
                    bound += val
                else:
                    # 남은 공간만큼 자른 가치(fractional) 더하고 루프 탈출
                    remain = W - total_w
                    bound += val * (remain / max(wt, 1))
                    break
            return bound

        # DFS 백트래킹 수행 함수
        def dfs(idx: int, current_w: int, current_v: int, current_sel: List[str]) -> None:
            nonlocal best_value, best_selection, best_weight
            
            # 현재까지 찾은 최대 가치보다 더 큰 경우 최적해 갱신
            if current_v > best_value:
                best_value = current_v
                best_selection = list(current_sel)
                best_weight = current_w
                
            if idx == N:
                return

            # 가지치기 (Bounding): 분수 배낭으로 구한 최대 가치 상한이 현재의 최적값 이하라면 유망하지 않음
            if get_bound(idx, current_w, current_v) <= best_value:
                return

            # 분기 1: 현재 태스크를 포함하는 경우 (용량 한도 내에서만)
            t = sorted_tasks[idx]
            wt = int(t.get("estimate", 0))
            val = int(t.get("value", 0))
            if current_w + wt <= W:
                current_sel.append(t["id"])
                dfs(idx + 1, current_w + wt, current_v + val, current_sel)
                current_sel.pop() # 백트래킹 원복

            # 분기 2: 현재 태스크를 포함하지 않는 경우
            dfs(idx + 1, current_w, current_v, current_sel)

        dfs(idx=0, current_w=0, current_v=0, current_sel=[])
        return best_selection, best_weight, best_value

    # ================================================================
    #  [보조 알고리즘] 가치 밀도 그리디 (Value Density Greedy)
    #  -- 가치 대비 공수 비율(value / estimate)이 높은 순으로 정렬하여 
    #     용량이 허용하는 만큼 탐욕적으로 담는다.
    #     시간복잡도: O(N log N)
    # ================================================================
    def plan_greedy(self, tasks_subset: List[dict], capacity: int) -> Tuple[List[str], int, int]:
        """
        가치 밀도 기준 그리디 알고리즘을 수행한다.
        반환: (선택된 태스크 ID 목록, 소진 용량 합, 획득 가치 합)
        """
        # 밀도 = value / estimate. estimate가 0인 극단적인 경우를 대비해 1로 보정.
        sorted_tasks = sorted(
            tasks_subset,
            key=lambda x: (int(x.get("value", 0)) / max(int(x.get("estimate", 1)), 1)),
            reverse=True
        )

        selected = []
        total_value = 0
        total_estimate = 0

        for t in sorted_tasks:
            wt = int(t.get("estimate", 0))
            val = int(t.get("value", 0))
            if total_estimate + wt <= capacity:
                selected.append(t["id"])
                total_estimate += wt
                total_value += val

        return selected, total_estimate, total_value

    # ====================================================================
    #  [유기적 연동] 글로벌 의존성 인지 스프린트 플래닝 (Global Planning)
    #  -- Module 1(스케줄러)의 스프린트 스케줄 순서대로 루프를 돌면서,
    #     1) 의존성이 풀린(선행 완료된) 태스크들만 Eligible Candidates로 상정
    #     2) 밀린 태스크는 다음 스프린트로 이월(Carry-Forward)
    #     3) 배낭 DP 혹은 백트래킹을 활용해 각 스프린트 가치 최적화
    # ====================================================================
    def plan_global(self, method: str = "dp") -> GlobalPlanResult:
        """
        의존성을 준수하며 전체 스프린트를 가로질러 가치를 극대화하는 글로벌 스프린트 계획을 수립한다.
        method: 'dp' | 'backtracking' | 'greedy'
        """
        # 1. Module 1 연동: 스케줄러를 활용해 마감일이 이른 스프린트 순서 획득
        try:
            import scheduler as S
            sch = S.Scheduler(list(self.tasks.values()), self.projects, self.sprints)
            sprint_order = sch.sprint_order()
        except Exception:
            # 폴백: 스케줄러가 없을 경우 sprints.json의 순서를 사용
            sprint_order = [s["id"] for s in self.sprints]

        # 2. 자료구조: 집합(Set) — 완료된 태스크 추적용 (자료구조 3)
        completed_tasks: Set[str] = set()

        # 프로젝트별 이월(Carry-forward) 목록 관리용 해시맵
        # 프로젝트 ID -> 아직 미완료된 채 이월된 태스크 딕셔너리 목록
        carry_forward_buckets: Dict[str, List[dict]] = {}

        sprint_plans: Dict[str, SprintResult] = {}
        total_value = 0
        total_capacity_used = 0
        carried_forward_total = 0

        # 스프린트 용량 조회를 위해 해시맵 구성
        sprint_caps = {s["id"]: int(s.get("capacity", 0)) for s in self.sprints}
        sprint_projs = {s["id"]: s.get("project") for s in self.sprints}

        # 스프린트별로 분류하여 원래 할당된 태스크 수집
        sprint_task_buckets: Dict[str, List[dict]] = {}
        for t in self.tasks.values():
            sp = t.get("sprint")
            if sp:
                sprint_task_buckets.setdefault(sp, []).append(t)

        # 3. 마감 이른 스프린트 순서대로 최적화 루프 수행
        for sp_id in sprint_order:
            sp_proj = sprint_projs.get(sp_id, sp_id.split("-")[0])
            cap = sprint_caps.get(sp_id, 0)

            # 후보군: (원래 이번 스프린트에 속한 태스크) + (해당 프로젝트에서 이전까지 밀려 이월된 태스크)
            original_tasks = sprint_task_buckets.get(sp_id, [])
            carried_tasks = carry_forward_buckets.get(sp_proj, [])
            candidates = original_tasks + carried_tasks

            # 의존성 검사(Dependency Gate): 선행 태스크가 모두 completed_tasks에 있는 것만 Eligible
            eligible: List[dict] = []
            not_eligible: List[dict] = []
            
            for t in candidates:
                # depends_on의 모든 선행 태스크가 완료되었는지 Set O(1) 조회로 검사
                deps = t.get("depends_on", [])
                # 선행 중 존재하지 않는 참조 ID나 외부 참조는 completed로 간주(방어적)
                deps_satisfied = all((dep in completed_tasks or dep not in self.tasks) for dep in deps)
                
                if deps_satisfied:
                    eligible.append(t)
                else:
                    not_eligible.append(t)

            # 최적화 선택 수행 (선택된 방식에 따라 대표 알고리즘 분기)
            start_time = time.perf_counter()
            if method == "dp":
                selected, used_cap, val = self.plan_dp(eligible, cap)
            elif method == "backtracking":
                selected, used_cap, val = self.plan_backtracking(eligible, cap)
            else:
                selected, used_cap, val = self.plan_greedy(eligible, cap)
            end_time = time.perf_counter()
            elapsed_ms = (end_time - start_time) * 1000.0

            selected_set = set(selected)
            completed_tasks.update(selected)

            # 미선택 태스크들은 다음 스프린트로 이월(Carry forward) 버킷에 적재
            unselected = [t for t in eligible if t["id"] not in selected_set]
            new_carry = unselected + not_eligible  # 의존성 미충족 건과 용량 초과 건 모두 이월됨
            carry_forward_buckets[sp_proj] = new_carry

            # 결과 객체 생성
            sprint_plans[sp_id] = SprintResult(
                sprint_id=sp_id,
                method=method,
                selected_tasks=selected,
                carried_tasks=[t["id"] for t in new_carry],
                total_value=val,
                used_capacity=used_cap,
                elapsed_ms=elapsed_ms
            )

            total_value += val
            total_capacity_used += used_cap
            carried_forward_total += len(new_carry)

        # 4. 모든 스프린트 완료 후에도 최종 미완료로 남아있는 백로그 수집
        unplanned = []
        for proj_id, p_list in carry_forward_buckets.items():
            for t in p_list:
                unplanned.append(t["id"])
        unplanned.sort()

        return GlobalPlanResult(
            method=method,
            sprint_plans=sprint_plans,
            total_value=total_value,
            total_capacity_used=total_capacity_used,
            carried_forward_total=carried_forward_total,
            unplanned_tasks=unplanned
        )


# ====================================================================
#  데이터 로더
# ====================================================================
def _load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_store(tasks_path: str) -> Tuple[List[dict], List[dict], List[dict]]:
    data_dir = os.path.dirname(os.path.abspath(tasks_path))
    tasks = _load_json(tasks_path)
    projects, sprints = [], []
    p_path = os.path.join(data_dir, "projects.json")
    s_path = os.path.join(data_dir, "sprints.json")
    if os.path.exists(p_path):
        projects = _load_json(p_path)
    if os.path.exists(s_path):
        sprints = _load_json(s_path)
    return tasks, sprints, projects


# ====================================================================
#  출력(리포트) 헬퍼
# ====================================================================
def _rule(title: str = "", ch: str = "-", width: int = 78) -> str:
    if not title:
        return ch * width
    pad = width - len(title) - 2
    return f"{ch * 2} {title} {ch * max(pad - 2, 0)}"


# ====================================================================
#  메인(CLI)
# ====================================================================
def main(argv: Optional[List[str]] = None) -> int:
    import sys
    # 윈도우 터미널 인코딩 에러 방지를 위해 UTF-8 출력 강제 시도
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    default_tasks = os.path.join(here, "data", "tasks.json")

    ap = argparse.ArgumentParser(
        description="Squadron Module 3 - 스프린트 플래너 (0/1 배낭 DP, 백트래킹, 그리디)")
    ap.add_argument("--tasks", default=default_tasks,
                    help="태스크 JSON 경로 (기본: data/tasks.json)")
    ap.add_argument("--demo-only", action="store_true",
                    help="README.md 에 제시된 P3-S4 배낭 반례 검증 실행")
    args = ap.parse_args(argv)

    if not os.path.exists(args.tasks):
        print(f"Error: 태스크 파일을 찾을 수 없습니다. ({args.tasks})")
        return 1

    tasks, sprints, projects = load_store(args.tasks)
    planner = SprintPlanner(tasks, sprints, projects)

    # ── 1) README 반례 검증 데모 모드 ──
    if args.demo_only:
        print(_rule("README.md 스프린트 플래너 반례 검증 (P3-S4 데모)", "="))
        # 반례 데이터 구성: A(6,60), B(5,40), C(5,40)
        demo_tasks = [
            {"id": "T0151", "estimate": 6, "value": 60, "title": "Knapsack Item A"},
            {"id": "T0152", "estimate": 5, "value": 40, "title": "Knapsack Item B"},
            {"id": "T0153", "estimate": 5, "value": 40, "title": "Knapsack Item C"}
        ]
        capacity = 10
        print(f"스프린트 용량: {capacity}")
        for t in demo_tasks:
            print(f"  태스크 {t['id']}: estimate={t['estimate']}, value={t['value']} ({t['title']})")
        print()

        # 각 알고리즘별 결과 도출
        g_sel, g_est, g_val = planner.plan_greedy(demo_tasks, capacity)
        dp_sel, dp_est, dp_val = planner.plan_dp(demo_tasks, capacity)
        bt_sel, bt_est, bt_val = planner.plan_backtracking(demo_tasks, capacity)

        print(f"  * 가치밀도 그리디: 선택 {g_sel} | 소진용량: {g_est} | 총 가치: {g_val}")
        print(f"  * 0/1 배낭 DP    : 선택 {dp_sel} | 소진용량: {dp_est} | 총 가치: {dp_val} (최적)")
        print(f"  * 백트래킹 탐색   : 선택 {bt_sel} | 소진용량: {bt_est} | 총 가치: {bt_val} (최적)")
        print()
        print("  -> 결과 요약: 그리디(가치 60)보다 DP/백트래킹 최적화(가치 80)의 가치가 더 높음을 증명함.")
        print()
        return 0

    # ── 2) 글로벌 일정 플래닝 전체 결과 비교 ──
    print(_rule("SQUADRON - Module 3 - Sprint Planner", "="))
    print(f"  입력: {os.path.relpath(args.tasks)}  *  태스크 {len(tasks)}개  *  "
          f"스프린트 {len(sprints)}개\n")

    methods = ["greedy", "dp", "backtracking"]
    results: Dict[str, GlobalPlanResult] = {}
    
    for m in methods:
        results[m] = planner.plan_global(method=m)

    print(f"  {'방식':<15}{'총 비즈니스 가치':>16}{'총 소진 용량':>14}{'총 이월 횟수':>12}{'최종 미계획':>12}")
    for m in methods:
        r = results[m]
        print(f"  {m.upper():<15}{r.total_value:>16}{r.total_capacity_used:>14}{r.carried_forward_total:>12}{len(r.unplanned_tasks):>12}")

    dp_r = results["dp"]
    gr_r = results["greedy"]
    val_diff = dp_r.total_value - gr_r.total_value
    print(f"\n  -> 글로벌 계획에서 배낭 DP를 적용했을 때 그리디 대비 총 비즈니스 가치 +{val_diff} 향상.")
    print(f"  -> 최종 미계획 태스크 수: {len(dp_r.unplanned_tasks)}개\n")

    # 세부 스프린트별 결과 예시 (DP 기준)
    print(_rule("글로벌 스프린트 플랜 세부 요약 (DP 기준)", "-"))
    print(f"    {'스프린트':<10}{'용량':>6}{'소진':>6}{'선택수':>8}{'이월수':>8}{'가치합':>8}  {'선택된 태스크들'}")
    sprint_caps = {s["id"]: int(s.get("capacity", 0)) for s in sprints}
    
    for sp_id, plan in sorted(dp_r.sprint_plans.items()):
        sel_str = ",".join(plan.selected_tasks[:6])
        if len(plan.selected_tasks) > 6:
            sel_str += " …"
        print(f"    {sp_id:<10}{sprint_caps.get(sp_id, 0):>6}{plan.used_capacity:>6}"
              f"{len(plan.selected_tasks):>8}{len(plan.carried_tasks):>8}{plan.total_value:>8}  {sel_str}")
    print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
