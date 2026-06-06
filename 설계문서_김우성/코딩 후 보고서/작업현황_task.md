# 작업 목록 (Task List)

스프린트 플래너(Module 3)의 구현 및 Module 1, 2와의 연동, 그리고 Streamlit 시각화 연동을 진행합니다.

- `[x]` 스프린트 플래너 모듈 (`planner.py`) 구현
    - `[x]` 데이터 구조 클래스 정의 (`SprintResult` 등)
    - `[x]` 0/1 배낭 DP 알고리즘 (`plan_dp`) 구현 (한글 주석 포함)
    - `[x]` 백트래킹 알고리즘 (`plan_backtracking`) 구현 (Fractional Knapsack Bound 및 한글 주석 포함)
    - `[x]` 그리디 밀도 알고리즘 (`plan_greedy`) 구현 (한글 주석 포함)
    - `[x]` 글로벌 의존성 인지 계획 알고리즘 (`plan_global`) 구현
    - `[x]` CLI 환경 구현 (자가 검증 및 데모 실행)
- `[x]` Streamlit 시각화 대시보드 (`app.py`) 연동 및 수정
    - `[x]` Module 3 탭 추가
    - `[x]` 단일 스프린트 데모 (`P3-S4`) 렌더링
    - `[x]` 글로벌 플래닝 결과 및 Carry Forward 표시
    - `[x]` 플래너 적용 전후 비즈니스 가치/활용률 비교 차트 추가
    - `[x]` 플래너 결과를 Module 2(배정기)의 배정 입력으로 연동하여 결과 확인
- `[x]` 최종 검증 실행
    - `[x]` `python planner.py --demo-only` 실행 및 검증
    - `[x]` `python planner.py` 실행 및 검증
    - `[x]` `streamlit run app.py` 수동 테스트 및 렌더링 검증
