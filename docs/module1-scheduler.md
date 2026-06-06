# Module 1 — 프로젝트 스케줄러: 알고리즘 설명

> 파일: [`scheduler.py`](../scheduler.py) · 표준 라이브러리만 사용 (Python 3.8+)
> 대표 알고리즘: **우선순위 인지 위상정렬**(그래프) · **임계경로 DAG 최장경로 DP**(동적계획법)
> 보조 알고리즘: **DFS 역간선 사이클 검출**(그래프 탐색)

---

## 0. 개요 — 무엇을 입력받아 무엇을 내는가

**입력:** 태스크 리스트(`tasks.json`). 각 태스크는 `depends_on[]`(선행 태스크) 간선으로
의존성 그래프를 이룬다. 프로젝트 간 간선은 없으므로 **프로젝트별로 독립 처리**한다.

**출력 세 가지**

| 출력 | 알고리즘 | 의미 |
|---|---|---|
| 우선순위 인지 실행 순서 | 칸(Kahn) 위상정렬 + 최소힙 | 의존성을 어기지 않으면서 "임계/시급한" 것을 먼저 |
| 임계경로 + 여유시간(slack) | DAG 최장경로 DP | 지연되면 프로젝트 전체가 밀리는 무여유 사슬 |
| 달력 타임라인 | velocity 기반 영업일 매핑 | 임계경로 길이를 마감일에 정렬 |

그리고 **사이클(순환 의존성)** 이 있으면 검출해 문제 태스크를 지목한다.

---

## 1. 그래프 모델과 자료구조

**간선 규약 (중요):** 태스크 `B`가 `A`에 의존하면(`B.depends_on == [A]`) "A가 먼저"이므로
**방향 간선 `A ─► B`** 를 만든다.

```
adj[A]      = A가 끝나야 풀리는 후속(direct successors) 목록
indeg[B]    = 아직 끝나지 않은 선행(prerequisite) 개수
```

**사용 자료구조**

| 자료구조 | 쓰임 |
|---|---|
| 인접 리스트 `adj: dict[str, list]` | 의존성 그래프 (graph) |
| 진입차수 해시맵 `indeg: dict[str, int]` | 위상정렬의 ready 판정 |
| 최소 힙 `heapq` | 우선순위 ready-set |
| 해시맵 `es/ef/ls/lf/slack` | DP 속성표 |
| 데크 `deque` | 단순 위상정렬 큐 · DFS 명시적 스택 |

> 그래프 구성 시 `dict.fromkeys(depends_on)`로 **중복 간선을 제거**해 진입차수·out-degree
> 왜곡을 막고, 인접 리스트를 정렬해 **결정적(deterministic) 출력**을 보장한다.

---

## 2. 알고리즘 ① — 우선순위 인지 위상정렬 (Kahn + 최소힙)

### 2.1 핵심 아이디어

표준 칸(Kahn) 알고리즘은 진입차수 0인 노드를 **FIFO 큐**에 넣고 하나씩 빼며 후속의 진입차수를
줄인다. Squadron은 그 큐를 **최소 힙**으로 바꾼다.

> **의존성(진입차수)** 은 태스크가 *언제* 가능해지는지를 결정하고,
> **힙 키** 는 가능한 것들 중 *무엇을* 먼저 내보낼지를 결정한다.

### 2.2 힙 키 설계 (작을수록 먼저)

```
key(t) = (slack, priority, deadline_ordinal, -out_degree, id)
```

| 요소 | 의미 | 정렬 방향 |
|---|---|---|
| `slack` | 임계도. 0이면 임계경로 위 → 최우선 | 작을수록 ↑ |
| `priority` | 비즈니스 우선순위 1(최상)~4(최하) | 작을수록 ↑ |
| `deadline_ordinal` | 프로젝트 마감일 | 이른 것 ↑ |
| `-out_degree` | 막고 있는 후속 수(blocking factor) | 많을수록 ↑ |
| `id` | 완전한 결정성(tie-break) | — |

`slack`은 임계경로 DP가 먼저 채워야 하므로, 생성자에서 모든 프로젝트의
`critical_path()`를 미리 계산해 전역 `slack` 표를 채운다.

### 2.3 의사코드

```text
priority_topo_sort(project):
    nodes  = project 의 태스크들
    indeg  = 부분그래프 기준 진입차수 재계산        # 프로젝트 필터 시 외부 간선 제외
    heap   = [ (key(n), n) for n in nodes if indeg[n]==0 ]   # 최소 힙
    order  = []
    while heap:
        _, u = heappop(heap)                       # 가장 임계/시급한 ready 태스크
        order.append(u)
        for v in adj[u]:                           # u 완료 → 후속 해제
            indeg[v] -= 1
            if indeg[v] == 0:
                heappush(heap, (key(v), v))
    if len(order) < len(nodes):                    # 배출되지 못한 노드 = 사이클
        return order, detect_cycle(...)
    return order, NO_CYCLE
```

### 2.4 동작 예시

태스크 A,B,C,D, 간선 `A→B, A→C, B→D, C→D`, 작업량 `A=3,B=5,C=2,D=4`.
(아래 §3에서 계산한) slack은 `A0, B0, C3, D0`.

```
ready {A}            → pop A,  unlock B,C       order=[A]
ready {B(0),C(3)}    → pop B  (slack 0 < 3)     order=[A,B]   (D indeg 2→1)
ready {C(3)}         → pop C,  unlock D          order=[A,B,C]
ready {D(0)}         → pop D                      order=[A,B,C,D]
```

임계경로(slack 0) 태스크 B가 슬랙 3짜리 C보다 먼저 나간다 — 의존성은 지키되 임계도가 순서를 지배.

### 2.5 복잡도

각 노드/간선을 1회 처리하고 힙 연산이 `O(log V)`:

$$ O\big((V + E)\log V\big) $$

### 2.6 사이클 검출(1차 판정)

위상정렬이 끝났는데 `len(order) < len(nodes)` 이면, 배출되지 못한(진입차수>0) 태스크가
남아 있다는 뜻 → **사이클 존재**. 이때 `priority_topo_sort`는 §4의 DFS(`_detect_cycle`)에
**프로젝트 전체 노드 집합**을 넘겨 구체적 순환 경로 1개를 복원하고, 배출되지 못한 잔여
집합은 '스케줄 불가'로 보고한다. (모든 사이클을 수집하는 공개 API `detect_cycles()`는
DFS 대상을 잔여 집합으로 좁혀 반복한다.)

---

## 3. 알고리즘 ② — 임계경로 = DAG 최장경로 DP

CPM(Critical Path Method)을 DAG 위 동적계획법으로 구현한다. 노드 가중치 = 작업량(`estimate`).

### 3.1 전진 패스 — 이른 일정 (ES/EF)

위상순서대로 한 번 훑으며 **소스에서의 최장경로**를 누적한다.

```
ES[u] = max( EF[p] for p in 선행(u) )   (선행 없으면 0)
EF[u] = ES[u] + dur[u]
makespan = max EF[u]                     # 프로젝트 최소 완료기간
```

### 3.2 후진 패스 — 늦은 일정 (LS/LF)

역위상순서로 훑으며, 모든 sink의 LF를 makespan으로 두고 거꾸로 좁힌다.

```
LF[u] = min( LS[v] for v in 후속(u) )   (후속 없으면 makespan)
LS[u] = LF[u] - dur[u]
```

### 3.3 여유시간과 임계경로

```
slack[u] = LS[u] - ES[u] = LF[u] - EF[u]
임계경로  = slack[u] == 0 인 태스크들  (지연되면 프로젝트 전체가 지연)
```

`_reconstruct_critical_path`는 slack 0 노드들로 부분그래프를 만들고, 임계 source에서
`EF[선행]==ES[후속]`인 임계 간선을 따라 **대표 사슬 1개**를 복원한다. (임계경로가 여러
갈래일 수 있으므로 ★ 표시는 slack 0 전체를, 화살표 사슬은 대표 1개를 보여준다.)

### 3.4 왜 위상순서가 DP를 가능하게 하나

전진 패스에서 `ES[u]`는 모든 선행의 `EF`가 **이미 확정**되어 있어야 계산된다. 위상순서는
"모든 선행이 u보다 앞에 온다"를 보장하므로, 한 번의 선형 훑기로 정확히 계산된다(메모이제이션 불필요).

### 3.5 예시 (위 A,B,C,D)

```
전진:  ES/EF  A 0/3,  B 3/8,  C 3/5,  D 8/12   → makespan 12
후진:  LS/LF  D 8/12, B 3/8,  C 6/8,  A 0/3
slack:        A 0,    B 0,    C 3,    D 0       → 임계경로 A→B→D (12)
```

### 3.6 실데이터 검증값

```
P1 (Apollo)   89 pts:  T0001 → … → T0007 → T0011 → T0014
P2 (Borealis) 56 pts:  T0055 → T0057 → … → T0089
P3 (Cirrus)   30 pts:  T0116 → T0119 → … → T0144
```

> 설계된 무거운 사슬은 `T0001…T0008`이지만, 실제 최장경로는 `T0008`(여유 있음)을 건너뛰고
> `T0011 → T0014`로 빠진다. 스케줄러는 기대치가 아니라 **데이터가 말하는 진짜 임계경로**를 보고한다.

### 3.7 복잡도

전진·후진 각 1회 선형 패스: **`O(V + E)`** (위상정렬 비용 별도).

---

## 4. 알고리즘 ③ — 사이클 검출 (DFS 역간선 복원)

칸 정렬이 "사이클이 있다"를 알려주면, 여기서 **구체적 순환 경로**를 색칠 DFS로 복원한다.

```
WHITE(미방문) / GRAY(현재 재귀스택 위) / BLACK(완료)
GRAY 노드로 향하는 간선 = 역간선(back-edge) = 사이클
```

깊은 그래프에서도 안전하도록 **재귀 대신 명시적 스택(deque)** 으로 구현한다. 역간선을 만나면
`parent[]`를 거슬러 올라가 순환 경로를 닫는다(자기참조는 단일 노드 사이클).

`detect_cycles()`는 한 발 더 나아가:
1. 잔여(스케줄 불가) 집합 전체를 단순 위상정렬로 구하고,
2. 그 안에서 사이클을 하나씩 찾아 노드를 제거하며 **모든 사이클**을 수집하고,
3. **사이클 구성원** vs **사이클 하류(원인은 아니나 막힌 태스크)** 를 구분한다.

**검증값:** `tasks_broken.json`은 사이클 `T0001 → … → T0008 → T0001` 1개를 주입했고,
검출 결과는 **스케줄 불가 태스크 22개**(사이클 8 + 하류 14)이다.

---

## 5. 달력 매핑 (Calendar timeline)

임계경로 길이(스토리포인트)를 프로젝트 마감일에 맞춰 **영업일 달력**으로 환산한다.

```
velocity = Σ(스프린트 용량) / (스프린트 수 × 영업일 10)     # 데이터 근거 속도
makespan_days = round(makespan_points / velocity)
kickoff = 마감일에서 영업일 makespan_days 만큼 역산        # 주말 제외
```

각 태스크의 `ES/EF/LS/LF`(포인트)를 `_add_business_days`로 날짜에 매핑한다. `velocity ≤ 0`,
주말 마감, 음수 일수 등 경계는 모두 방어 처리한다.

---

## 6. 복잡도 요약

| 단계 | 시간 | 공간 |
|---|---|---|
| 그래프 구성 | `O(V + E)` | `O(V + E)` |
| 우선순위 위상정렬 | `O((V+E) log V)` | `O(V)` |
| 임계경로 DP(전진+후진) | `O(V + E)` | `O(V)` |
| 사이클 검출 DFS | `O(V + E)` | `O(V)` |

`V` = 태스크 수(프로젝트별), `E` = 의존성 간선 수.

---

## 7. Module 2 와의 연결점

`Scheduler.sprint_order()`는 스프린트를 **(프로젝트 마감 이른 순, 스프린트 번호)** 로 정렬해
"스케줄 순서"를 돌려준다. Module 2(배정기)가 이 순서와 태스크별 `slack`을 받아 전 일정을
배정한다 — 자세한 내용은 [`algorithms-overview.md`](./algorithms-overview.md)와
[`module2-allocator.md`](./module2-allocator.md) 참조.
