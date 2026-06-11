#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron - 일정 검색 엔진 (Search Engine)
======================================================================
Module 3(통합 플래너)가 확정한 전체 스프린트 일정을 바탕으로,
'담당자(개발자)' 또는 '스프린트' 기준으로 세부 일정을 검색합니다.
"""

import os
import pandas as pd

# 작성하신 Module 3 파일 이름에 맞게 import 하세요.
# (예: 파일명이 module3_planner.py 라면 아래와 같이 작성)
# 만약 파일명이 다르다면 그에 맞게 수정해 주세요.
try:
    from dynamicSprintPlanner import IntegratedSprintPlanner
except ImportError:
    print("❌ 오류: 'module3_integrated_planner.py' 파일을 찾을 수 없거나 이름이 다릅니다.")
    print("import 문을 실제 파일명에 맞게 수정해 주세요.")
    exit(1)

class SquadronSearchEngine:
    def __init__(self, data_dir: str):
        print("⏳ 전체 일정을 분석하고 최적화 배정을 수행 중입니다... (잠시만 기다려주세요)")
        
        # 통합 플래너를 실행하여 전체 시간표(DataFrame)를 메모리에 올려둡니다.
        planner = IntegratedSprintPlanner(data_dir)
        self.schedule_df = planner.get_planning_data()
        
        print("✅ 일정 데이터 로딩 완료!\n")

    def search_by_developer(self, dev_id: str):
        """사람 이름(담당자 ID)으로 검색: 언제 어떤 스프린트를 진행하는지 출력"""
        print(f"\n{'='*60}\n 👤 담당자 '{dev_id}' 검색 결과\n{'='*60}")
        
        # 해당 담당자의 데이터만 필터링
        df_dev = self.schedule_df[self.schedule_df['담당자'] == dev_id]
        
        if df_dev.empty:
            print(f"⚠️ '{dev_id}' 담당자에게 배정된 일정이 없습니다. (ID를 확인하세요)")
            return

        # 스프린트 순서대로 정렬
        df_dev = df_dev.sort_values(by=['스프린트', '태스크ID'])
        
        print(f" {'스프린트(언제)':<12} | {'태스크ID':<8} | {'공수':<4} | {'상태':<12} | {'제목'}")
        print("-" * 60)
        
        for _, row in df_dev.iterrows():
            print(f" {row['스프린트']:<13} | {row['태스크ID']:<8} | {row['공수(pts)']:<4} | {row['상태']:<12} | {row['제목'][:20]}")
        
        # 총 소진 공수 계산
        confirmed = df_dev[df_dev['상태'] == '✅ 확정']
        total_pts = confirmed['공수(pts)'].sum()
        print("-" * 60)
        print(f" 💡 총 확정 공수: {total_pts} pts (총 {len(confirmed)}개 태스크 확정)")
        print("=" * 60)

    def search_by_sprint(self, sprint_id: str):
        """스프린트로 검색: 누가 언제 어떤 태스크를 진행하는지 출력"""
        print(f"\n{'='*70}\n 📅 스프린트 '{sprint_id}' 검색 결과\n{'='*70}")
        
        # 해당 스프린트의 데이터만 필터링
        df_sp = self.schedule_df[self.schedule_df['스프린트'] == sprint_id]
        
        if df_sp.empty:
            print(f"⚠️ '{sprint_id}' 스프린트에 계획된 일정이 없습니다. (대소문자 및 하이픈 확인)")
            return

        # 담당자 기준으로 정렬하여 보기 좋게 출력
        df_sp = df_sp.sort_values(by=['상태', '담당자', '태스크ID'], ascending=[False, True, True])
        
        print(f" {'담당자(누가)':<10} | {'태스크ID':<8} | {'공수':<4} | {'상태':<12} | {'제목'}")
        print("-" * 70)
        
        for _, row in df_sp.iterrows():
            dev = row['담당자'] if row['담당자'] != "None" else "배정안됨"
            print(f" {dev:<10} | {row['태스크ID']:<8} | {row['공수(pts)']:<4} | {row['상태']:<12} | {row['제목'][:25]}")
        
        # 요약 정보
        confirmed_pts = df_sp[df_sp['상태'] == '✅ 확정']['공수(pts)'].sum()
        print("-" * 70)
        print(f" 💡 이 스프린트의 총 소진 공수: {confirmed_pts} pts / 배정 시도 태스크: {len(df_sp)}개")
        print("=" * 70)


def main():
    # 데이터 폴더 경로 설정
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(here, "data")
    
    # 검색 엔진 초기화 (여기서 플래너가 1회 돕니다)
    search_engine = SquadronSearchEngine(data_dir)
    
    # 대화형 검색 루프
    while True:
        print("\n[ Squadron 일정 검색 시스템 ]")
        print(" 1. 담당자(개발자) 로 검색")
        print(" 2. 스프린트 로 검색")
        print(" 0. 종료")
        
        choice = input("\n👉 메뉴를 선택하세요 (0~2): ").strip()
        
        if choice == '1':
            dev_id = input("🔍 검색할 담당자 ID를 입력하세요 (예: D039): ").strip()
            search_engine.search_by_developer(dev_id)
            
        elif choice == '2':
            sprint_id = input("🔍 검색할 스프린트 ID를 입력하세요 (예: P1-S1): ").strip()
            search_engine.search_by_sprint(sprint_id)
            
        elif choice == '0':
            print("시스템을 종료합니다.")
            break
            
        else:
            print("⚠️ 올바른 번호를 입력해 주세요.")

if __name__ == "__main__":
    main()