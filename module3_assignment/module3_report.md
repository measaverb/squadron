# Module 3 스프린트 플래너 보고서

## 0. 과제 요구사항 대응표

| 이미지 항목 | 보고서 반영 위치 | 핵심 내용 |
|---|---|---|
| ① 원리 | 2장, 3장 | 스프린트 용량 제한에서 value 합을 최대화하는 0/1 배낭 문제로 정의 |
| ② 동작방식 | 2.2, 3.2 | DP 테이블 채우기/역추적, DFS 분기/상한 기반 가지치기 |
| ③ 핵심 코드 | 2.3, 3.3 | `planner.py`의 `plan_dp`, `plan_backtracking` 핵심 부분 |
| ④ 예제 코드 | 4장 | `P3-S4` 반례 A(6,60), B(5,40), C(5,40) 실행 코드 |
| ⑤ 실제 성능 | 7장 | `benchmark_module3.py`로 측정한 실행시간, 메모리, 입력 크기별 결과 |
| ⑥ 사용 자료구조 | 5장 | 2차원 리스트 DP 테이블, 해시맵 `dict` |
| ⑦ 실행할 Input Data | 6장 | `data/tasks.json`, `data/sprints.json`, `data/projects.json`와 출처 |

## 1. 문제 정의

Module 3는 조직의 스프린트 백로그에서 "이번 스프린트에 어떤 태스크를 담을지" 결정한다.
스프린트에는 수행 가능한 스토리 포인트 용량이 있고, 각 태스크에는 필요한 공수 `estimate`와
얻을 수 있는 비즈니스 가치 `value`가 있다. 따라서 문제는 다음과 같이 정의할 수 있다.

- 입력: 태스크 목록 `tasks`, 스프린트 용량 `capacity`
- 제약: 선택한 태스크들의 `estimate` 합이 `capacity` 이하여야 함
- 목표: 선택한 태스크들의 `value` 합을 최대화
- 추가 조건: 글로벌 플래닝에서는 선행 태스크 `depends_on`이 완료된 태스크만 후보로 사용

즉, 단일 스프린트 선택 문제는 대표적인 **0/1 배낭 문제**이다. 각 태스크는 쪼갤 수 없으므로
선택하거나 선택하지 않는 두 가지 경우만 가능하다.

## 2. 알고리즘 1: 0/1 배낭 동적계획법(DP)

### 2.1 원리

0/1 배낭 DP는 큰 문제를 작은 부분 문제로 나눈다. `i`번째 태스크까지 고려했을 때,
용량 `w` 안에서 얻을 수 있는 최대 가치를 저장하면 같은 계산을 반복하지 않아도 된다.

점화식은 다음과 같다.

```text
dp[i][w] = i번째 태스크까지 고려하고, 용량 w일 때 얻을 수 있는 최대 가치

태스크 i의 공수 = wt, 가치 = val

if wt <= w:
    dp[i][w] = max(dp[i-1][w], dp[i-1][w-wt] + val)
else:
    dp[i][w] = dp[i-1][w]
```

이 점화식이 맞는 이유는 `i`번째 태스크에 대해 가능한 선택이 딱 두 가지이기 때문이다.
첫째, 태스크를 담지 않으면 이전 결과 `dp[i-1][w]`를 그대로 쓴다.
둘째, 태스크를 담으면 해당 태스크의 공수만큼 용량이 줄고 가치가 더해진다.
두 경우 중 큰 값을 고르면 항상 현재 상태의 최적값이 된다.

### 2.2 동작방식

1. 행은 태스크 개수 `N+1`, 열은 용량 `W+1`인 2차원 DP 테이블을 만든다.
2. 첫 행과 첫 열은 태스크가 없거나 용량이 0인 경우이므로 0으로 둔다.
3. 각 태스크를 하나씩 보며 모든 용량 `0..W`에 대해 점화식을 적용한다.
4. 테이블이 완성되면 `dp[N][W]`가 최대 가치이다.
5. 마지막 칸에서 위로 올라가며 값이 달라지는 지점을 찾아 실제 선택된 태스크를 복원한다.

### 2.3 핵심 코드

아래 코드는 `planner.py`의 `plan_dp` 핵심 부분이다.

```python
dp = [[0] * (W + 1) for _ in range(N + 1)]

for i in range(1, N + 1):
    t = tasks_subset[i - 1]
    wt = int(t.get("estimate", 0))
    val = int(t.get("value", 0))
    for w in range(W + 1):
        if wt <= w:
            dp[i][w] = max(dp[i - 1][w], dp[i - 1][w - wt] + val)
        else:
            dp[i][w] = dp[i - 1][w]
```

선택된 태스크 복원은 아래처럼 진행한다.

```python
selected = []
w = W
for i in range(N, 0, -1):
    t = tasks_subset[i - 1]
    wt = int(t.get("estimate", 0))
    if dp[i][w] != dp[i - 1][w]:
        selected.append(t["id"])
        w -= wt
selected.reverse()
```

### 2.4 시간/공간 복잡도

| 항목 | 분석 |
|---|---|
| 시간복잡도 | `N`개 태스크와 `W`개 용량 칸을 모두 채우므로 `O(NW)` |
| 공간복잡도 | `(N+1) x (W+1)` 테이블을 저장하므로 `O(NW)` |
| 장점 | 항상 최적해를 보장하고 결과를 역추적할 수 있음 |
| 단점 | 용량 `W`가 커지면 메모리와 시간이 함께 증가 |

## 3. 알고리즘 2: 백트래킹 + Fractional Bound

### 3.1 원리

백트래킹은 각 태스크를 "담는다 / 담지 않는다"로 나누어 모든 가능한 조합을 탐색한다.
단순히 전부 탐색하면 경우의 수가 최대 `2^N`이므로 입력이 커지면 매우 느려진다.
그래서 본 구현은 **분수 배낭 상한(Fractional Knapsack Bound)** 을 사용해 유망하지 않은 가지를
일찍 버린다.

현재 상태에서 앞으로 아무리 잘 골라도 현재 최적값보다 좋아질 수 없다면, 그 아래 조합은 더 볼
필요가 없다. 이 판단을 `get_bound`가 수행한다.

### 3.2 동작방식

1. 태스크를 `value / estimate`가 높은 순서로 정렬한다.
2. DFS로 현재 태스크를 담는 경우와 담지 않는 경우를 재귀 탐색한다.
3. 현재 무게가 용량을 넘으면 해당 분기는 진행하지 않는다.
4. `get_bound`로 앞으로 얻을 수 있는 최대 가능 가치를 계산한다.
5. 상한값이 이미 찾은 `best_value` 이하이면 해당 분기를 가지치기한다.
6. 더 좋은 조합을 찾으면 `best_selection`, `best_weight`, `best_value`를 갱신한다.

### 3.3 핵심 코드

아래 코드는 `planner.py`의 `plan_backtracking` 핵심 부분이다.

```python
def get_bound(idx: int, current_w: int, current_v: int) -> float:
    if current_w >= W:
        return 0.0

    bound = float(current_v)
    total_w = current_w

    for i in range(idx, N):
        t = sorted_tasks[i]
        wt = int(t.get("estimate", 0))
        val = int(t.get("value", 0))
        if total_w + wt <= W:
            total_w += wt
            bound += val
        else:
            remain = W - total_w
            bound += val * (remain / max(wt, 1))
            break
    return bound
```

```python
def dfs(idx: int, current_w: int, current_v: int, current_sel: List[str]) -> None:
    nonlocal best_value, best_selection, best_weight

    if current_v > best_value:
        best_value = current_v
        best_selection = list(current_sel)
        best_weight = current_w

    if idx == N:
        return

    if get_bound(idx, current_w, current_v) <= best_value:
        return

    t = sorted_tasks[idx]
    wt = int(t.get("estimate", 0))
    val = int(t.get("value", 0))

    if current_w + wt <= W:
        current_sel.append(t["id"])
        dfs(idx + 1, current_w + wt, current_v + val, current_sel)
        current_sel.pop()

    dfs(idx + 1, current_w, current_v, current_sel)
```

### 3.4 시간/공간 복잡도

| 항목 | 분석 |
|---|---|
| 시간복잡도 | 최악의 경우 모든 선택/비선택 조합을 보므로 `O(2^N)` |
| 실제 동작 | bound 가지치기가 잘 작동하면 많은 분기를 생략해 훨씬 빠르게 실행 |
| 공간복잡도 | 재귀 깊이와 현재 선택 목록이 최대 `N`이므로 `O(N)` |
| 장점 | DP처럼 최적해를 찾으면서, 작은/중간 입력에서는 메모리 사용량이 작음 |
| 단점 | 가지치기가 잘 안 되는 입력에서는 지수 시간이 걸릴 수 있음 |

## 4. 예제 코드: P3-S4 배낭 반례

아래 예제는 README와 `data/README.md`에 명시된 스프린트 플래너 반례이다.
용량은 10이고 후보는 A(6,60), B(5,40), C(5,40)이다.

```python
from planner import SprintPlanner

demo_tasks = [
    {"id": "T0151", "estimate": 6, "value": 60, "title": "Knapsack Item A"},
    {"id": "T0152", "estimate": 5, "value": 40, "title": "Knapsack Item B"},
    {"id": "T0153", "estimate": 5, "value": 40, "title": "Knapsack Item C"},
]

planner = SprintPlanner(demo_tasks)

print(planner.plan_greedy(demo_tasks, 10))
print(planner.plan_dp(demo_tasks, 10))
print(planner.plan_backtracking(demo_tasks, 10))
```

실행 명령:

```powershell
python planner.py --demo-only
```

실행 결과 요약:

| 알고리즘 | 선택 태스크 | 사용 용량 | 총 가치 |
|---|---|---:|---:|
| Greedy baseline | T0151 | 6 | 60 |
| DP | T0152, T0153 | 10 | 80 |
| Backtracking | T0152, T0153 | 10 | 80 |

Greedy는 1pt당 가치가 가장 높은 A를 먼저 담지만, 남은 용량 4에는 B나 C를 담을 수 없다.
반면 DP와 Backtracking은 B+C 조합을 찾아 용량 10을 정확히 채우고 가치 80을 얻는다.

## 5. 사용 자료구조 2개

### 5.1 2차원 리스트 DP 테이블

| 항목 | 설명 |
|---|---|
| 소개 | 행은 고려한 태스크 수, 열은 사용 가능한 용량을 뜻하는 표 |
| 구조 | `dp[i][w]` 형태의 list of lists |
| 핵심 연산 | 인덱스 접근 `O(1)`, 값 갱신 `O(1)` |
| 선택 이유 | DP 점화식이 바로 이전 행의 값을 참조하므로 2차원 테이블이 가장 직관적이고 역추적도 가능 |
| 사용 위치 | `planner.py`의 `plan_dp` |

### 5.2 해시맵(dict)

| 항목 | 설명 |
|---|---|
| 소개 | 키를 이용해 값을 빠르게 찾는 해시 기반 자료구조 |
| 구조 | `task_id -> task`, `sprint_id -> capacity`, `project_id -> carry_forward_list` |
| 핵심 연산 | 삽입/조회/갱신 평균 `O(1)` |
| 선택 이유 | 글로벌 플래닝에서 태스크 속성, 스프린트 용량, 프로젝트별 이월 목록을 반복 조회해야 하므로 빠른 접근이 필요 |
| 사용 위치 | `self.tasks`, `sprint_caps`, `sprint_task_buckets`, `carry_forward_buckets` |

보조적으로 `set`도 사용한다. `completed_tasks` 집합은 선행 태스크가 완료되었는지 평균 `O(1)`로
검사하기 위해 사용된다.

## 6. 실행할 Input Data

성능 분석에는 실행 가능한 Raw 데이터인 `data/` 폴더의 JSON 파일을 사용했다.

| 파일 | 크기/개수 | 역할 |
|---|---:|---|
| `data/tasks.json` | 153개 태스크 | `estimate`, `value`, `depends_on`, `sprint`, `project` 포함 |
| `data/sprints.json` | 12개 스프린트 | 각 스프린트의 `capacity` 제공 |
| `data/projects.json` | 3개 프로젝트 | 프로젝트 id, 이름, 마감 정보 제공 |

데이터는 완전 합성 데이터이지만 실제 소프트웨어 조직 백로그를 모사한다. `data/README.md`에 따르면
스킬/연차 분포는 Stack Overflow 개발자 설문을 참고했고, 작업 제목과 공수 추정치는 Apache Jira 같은
공개 이슈 트래커의 관례를 따랐다. 생성 시드는 42로 고정되어 재현 가능하다.

성능 측정 실행 명령:

```powershell
python module3_assignment\benchmark_module3.py
```

생성되는 결과 파일:

- `module3_assignment/benchmark_demo.csv`
- `module3_assignment/benchmark_scaling.csv`
- `module3_assignment/benchmark_global.csv`

## 7. 실제 성능 분석

측정 환경은 현재 프로젝트의 `pplan` 가상환경, Python 3.13이다. 실행시간은 `time.perf_counter`,
메모리는 `tracemalloc`의 peak 값을 사용했다.

### 7.1 P3-S4 단일 반례 성능

| 알고리즘 | 평균 시간(ms) | 중앙값(ms) | Peak KB | 총 가치 |
|---|---:|---:|---:|---:|
| Greedy baseline | 0.00588 | 0.00495 | 0.87 | 60 |
| DP | 0.01662 | 0.01385 | 0.84 | 80 |
| Backtracking | 0.01952 | 0.01885 | 1.79 | 80 |

해석: 입력이 작기 때문에 세 알고리즘 모두 매우 빠르다. 하지만 결과 품질은 다르다.
Greedy가 가장 빠르지만 최적해를 놓치고, DP와 Backtracking은 약간 더 오래 걸리지만 최적 가치 80을 찾는다.

### 7.2 입력 크기별 성능

실제 `tasks.json`의 앞부분 태스크를 사용해 `N=5,10,15,20,25,30`으로 증가시키며 측정했다.
용량은 각 부분집합 estimate 합의 약 40%로 설정했다.

| N | Capacity | DP 평균(ms) | Backtracking 평균(ms) | DP Peak KB | Backtracking Peak KB |
|---:|---:|---:|---:|---:|---:|
| 5 | 22 | 0.02552 | 0.02167 | 1.41 | 1.21 |
| 10 | 38 | 0.08294 | 0.09481 | 4.69 | 1.33 |
| 15 | 52 | 0.26261 | 0.16927 | 11.22 | 1.38 |
| 20 | 62 | 0.68050 | 0.18476 | 18.35 | 1.61 |
| 25 | 70 | 0.84621 | 0.16441 | 32.77 | 1.83 |
| 30 | 80 | 1.27054 | 0.13514 | 48.99 | 2.00 |

해석:

- DP는 이론대로 `N x W` 테이블이 커지며 시간과 메모리가 함께 증가한다.
- Backtracking은 최악의 경우 `2^N`이지만, 이 데이터에서는 가치 밀도 정렬과 bound 가지치기가 잘 작동해
  작은 메모리로 빠르게 끝났다.
- 따라서 안정적인 최적해 보장은 DP가 좋고, 메모리 절약과 가지치기 효과를 보여주기에는 Backtracking이 좋다.

### 7.3 전체 글로벌 플래닝 성능

전체 입력 `tasks.json` 153개, `sprints.json` 12개를 사용했다.

| 알고리즘 | 선택 태스크 | 사용 용량 | 총 가치 | 이월 합계 | 최종 미계획 | 평균 시간(ms) | Peak KB |
|---|---:|---:|---:|---:|---:|---:|---:|
| GREEDY | 91 | 408 | 4527 | 213 | 62 | 6.35152 | 560.03 |
| DP | 91 | 417 | 4506 | 213 | 62 | 8.40063 | 99.95 |
| BACKTRACKING | 91 | 417 | 4506 | 213 | 62 | 9.10701 | 81.70 |

해석:

- 단일 스프린트 배낭 문제에서는 DP와 Backtracking이 최적해를 보장한다.
- 전체 글로벌 플래닝은 여러 스프린트가 이어지고 이월(Carry Forward)이 발생하는 rolling 과정이다.
  이 때문에 "각 스프린트의 현재 후보 집합에서 최적"인 선택이 전체 rolling 결과의 총 가치 최대와 항상 같지는 않다.
- 실제 데이터에서는 Greedy가 총 가치 4527로 DP/Backtracking보다 약간 높게 나왔다. 이는 Greedy가 최적 알고리즘이라는
  뜻이 아니라, 이월과 의존성 상호작용으로 이후 스프린트 후보 구성이 달라졌기 때문이다.
- 따라서 보고서의 핵심 비교는 단일 스프린트 0/1 배낭 문제에서 DP/Backtracking이 Greedy 반례를 해결한다는 점이고,
  글로벌 결과는 실제 서비스 흐름에서 알고리즘 선택이 후속 입력까지 바꿀 수 있음을 보여주는 추가 분석이다.

## 8. 제출 파일 및 실행 방법

| 제출 요소 | 파일 |
|---|---|
| Module 3 핵심 코드 | `planner.py` |
| 실행 가능한 Input Data | `data/tasks.json`, `data/sprints.json`, `data/projects.json` |
| 성능 측정 코드 | `module3_assignment/benchmark_module3.py` |
| 성능 결과 Raw CSV | `module3_assignment/benchmark_demo.csv`, `benchmark_scaling.csv`, `benchmark_global.csv` |
| 보고서 원문 | `module3_assignment/module3_report.md` |

실행 순서:

```powershell
python planner.py --demo-only
python planner.py
python module3_assignment\benchmark_module3.py
```

