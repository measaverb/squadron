#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron - 통합 스프린트 플래너 (Module 3: Integrated Sprint Planner)
======================================================================
Module 1(Scheduler)의 일정과 Module 2(Allocator)의 인력을 결합하여
다중 프로젝트 환경에서 유기적인 인력 배정을 수행합니다.

사용 알고리즘:
  1. [동적계획법] 0/1 Knapsack DP : 스프린트 용량 최적화
  2. [완전탐색] 백트래킹 (Backtracking) : 결과 검증 및 최적화 보조
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from typing import Dict, List, Set, Tuple
import pandas as pd
import scheduler as S
import allocator as A

class IntegratedSprintPlanner:
    def __init__(self, data_dir: str):
        # 1. 기존 모듈 로더 활용
        self.devs, self.tasks, self.projects, self.sprints = A.load_store(data_dir)
        self.tasks_by_id = {t["id"]: t for t in self.tasks}
        
        # 2. Module 1 인스턴스 (의존성/Slack 조회용)
        self.sch = S.Scheduler(self.tasks, self.projects, self.sprints)
        
        # 3. Module 2 인스턴스 (인력 배정용)
        self.allocator = A.Allocator(self.devs)
        
        # 개발자별 글로벌 가용 용량 (모든 프로젝트 통틀어 관리)
        self.dev_global_cap = {
            dev["id"]: dev.get("capacity", 0) - dev.get("current_load", 0)
            for dev in self.devs
        }

    # ──────────────────────────────────────────────────────────────────
    # 알고리즘 1: 0/1 배낭 DP (스프린트 가치 최적화)
    # ──────────────────────────────────────────────────────────────────
    def _optimize_sprint_dp(self, candidates: List[dict], capacity: int) -> List[dict]:
        n = len(candidates)
        if n == 0 or capacity <= 0: return []
        dp = [[0] * (capacity + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            t = candidates[i - 1]
            wt, val = int(t.get("estimate", 0)), int(t.get("value", 0))
            for w in range(capacity + 1):
                dp[i][w] = max(dp[i - 1][w], dp[i - 1][w - wt] + val) if wt <= w else dp[i - 1][w]
        
        selected = []
        w = capacity
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected.append(candidates[i - 1])
                w -= int(candidates[i - 1].get("estimate", 0))
        return selected

    # ──────────────────────────────────────────────────────────────────
    # 알고리즘 2: 백트래킹 (DP 결과 교차 검증용)
    # ──────────────────────────────────────────────────────────────────
    def _optimize_sprint_bt(self, candidates: List[dict], capacity: int) -> List[dict]:
        best_val, best_sel = 0, []
        def dfs(idx, cur_w, cur_v, cur_sel):
            nonlocal best_val, best_sel
            if cur_v > best_val: best_val, best_sel = cur_v, list(cur_sel)
            if idx == len(candidates): return
            t = candidates[idx]
            wt, val = int(t.get("estimate", 0)), int(t.get("value", 0))
            if cur_w + wt <= capacity:
                cur_sel.append(t)
                dfs(idx + 1, cur_w + wt, cur_v + val, cur_sel)
                cur_sel.pop()
            dfs(idx + 1, cur_w, cur_v, cur_sel)
        dfs(0, 0, 0, [])
        return best_sel

    # ──────────────────────────────────────────────────────────────────
    # 통합 파이프라인 (세부 일정 및 세부 인원 배정)
    # ──────────────────────────────────────────────────────────────────
    def run_integration(self):
        # 1. Module 1을 통해 전체 스케줄 분석 (Slack, Critical 정보 획득)
        slack, critical, _ = A.schedule_view(self.tasks, self.projects, self.sprints)
        
        print(f"{'='*90}\n🚀 통합 스프린트 배정 보드 (일정 + 인원)\n{'='*90}")

        # 2. 프로젝트 단위 순회 (프로젝트 중심 출력)
        for proj in self.projects:
            pid = proj["id"]
            print(f"\n📁 [ 프로젝트: {pid} - {proj['name']} ]")
            
            # 프로젝트별 스프린트 목록 필터링
            proj_sprints = [s for s in self.sprints if s["project"] == pid]
            
            for sprint in proj_sprints:
                sid = sprint["id"]
                cap = int(sprint.get("capacity", 0))
                candidates = [t for t in self.tasks if t.get("sprint") == sid]
                
                # [알고리즘 활용] DP로 최적 태스크 선별
                selected_tasks = self._optimize_sprint_dp(candidates, cap)
                
                # [Module 2 활용] 헝가리안 알고리즘 배정
                alloc_res = self.allocator.allocate_hungarian(selected_tasks)
                assign_map = {a.task: a for a in alloc_res.assignments}
                
                print(f"  📅 스프린트: {sid} (가용: {cap}pts) | {len(selected_tasks)}개 태스크 배정 시도")
                print(f"     {'Task':<8} {'Pri':<5} {'Est':<5} {'담당자':<20} {'상태'}")
                print("     " + "-" * 70)
                
                for t in selected_tasks:
                    tid = t["id"]
                    assignment = assign_map.get(tid)
                    
                    # 배정된 인원 확인 및 전역 자원 차감 (중복 인력 경합 로직)
                    status = "❌ 스킬부재"
                    dev_name = "None"
                    
                    if assignment and assignment.dev:
                        dev_name = assignment.dev
                        est = int(t.get("estimate", 0))
                        if self.dev_global_cap.get(dev_name, 0) >= est:
                            self.dev_global_cap[dev_name] -= est
                            status = "✅ 확정"
                        else:
                            status = "⚠️ 인력과부하(이월)"
                            
                    print(f"     {tid:<8} {t.get('priority',4):<5} {t.get('estimate',0):<5} {dev_name:<20} {status}")

    def get_planning_data(self):
        """스트림릿 대시보드용으로 데이터를 가공해서 리턴합니다."""
        results = []
        for proj in self.projects:
            pid = proj["id"]
            proj_sprints = [s for s in self.sprints if s["project"] == pid]
            for sprint in proj_sprints:
                sid = sprint["id"]
                cap = int(sprint.get("capacity", 0))
                candidates = [t for t in self.tasks if t.get("sprint") == sid]
                selected = self._optimize_sprint_dp(candidates, cap)
                alloc_res = self.allocator.allocate_hungarian(selected)
                
                for t in selected:
                    assignment = next((a for a in alloc_res.assignments if a.task == t["id"]), None)
                    dev = assignment.dev if assignment and assignment.dev else "None"
                    
                    # 배정 상태 확인
                    est = int(t.get("estimate", 0))
                    status = "✅ 확정"
                    if dev != "None":
                        if self.dev_global_cap.get(dev, 0) >= est:
                            self.dev_global_cap[dev] -= est
                        else:
                            status = "⚠️ 인력과부하(이월)"
                    else:
                        status = "❌ 스킬부재(이월)"
                        
                    results.append({
                        "프로젝트": pid, "스프린트": sid, "태스크ID": t["id"],
                        "제목": t.get("title", ""), "담당자": dev, "상태": status,
                        "공수(pts)": est, "가치": t.get("value", 0)
                    })
        return pd.DataFrame(results)

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(here, "data")
    planner = IntegratedSprintPlanner(data_dir)
    planner.run_integration()

if __name__ == "__main__":
    main()