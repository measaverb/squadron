#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron - Module 4: 백로그 검색·자동완성 (Backlog Search & Autocomplete)
=========================================================================

153개의 태스크 백로그를 대상으로 정확 검색, 자동완성, 오타 보정 퍼지 검색을 제공한다.
입력 데이터(tasks.json)는 Module 1~3과 동일한 공유 스토어를 사용하며,
searcher.py 자체는 다른 모듈과 코드 결합 없이 독립적으로 동작한다.

----------------------------------------------------------------
사용 자료구조 (Data structures)  -- 과목 요구사항: >=2개
  · 트라이 (Trie, 트리 자료구조)         : 단어 사전 구축 + 접두어 자동완성 탐색.
  · 해시맵 (dict)                         : 역인덱스(단어->태스크ID), 라빈-카프 해시 버킷.
  · 리스트 (1D Array)                     : KMP 실패 함수(π 배열) 테이블.

사용 알고리즘 (Algorithms)  -- 과목 요구사항: >=2개, 대표 알고리즘은 서로 다른 계열
  · [대표·문자열매칭] KMP (Knuth-Morris-Pratt)        -- 정확 부분 문자열 탐색 O(N+M)
  · [대표·문자열매칭] 라빈-카프 (Rabin-Karp)          -- 롤링 해시 기반 고속 검색 O(N+M) avg
  · [보조·트리탐색]   트라이 (Trie)                   -- 접두어 자동완성 O(M + 결과수)
  · [보조·동적계획법] 편집거리 (Levenshtein Distance)  -- 오타 보정 퍼지 검색 O(M*N)

----------------------------------------------------------------
실행 환경 (Run environment)
  · Python 3.8+ -- 표준 라이브러리만 사용
  · 사용 모듈: argparse, json, os, sys, dataclasses, typing

실행 예시
  $ python searcher.py                              # 빌트인 데모 실행
  $ python searcher.py --query "deploy"             # KMP 정확 검색
  $ python searcher.py --query "dep" --mode auto    # 트라이 자동완성
  $ python searcher.py --query "depoly" --mode fuzzy --threshold 2  # 오타 보정
  $ python searcher.py --query "API auth" --mode rabin              # 라빈-카프 다중 키워드
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ====================================================================
#  자료구조 1: 트라이 (Trie)
#  -- 단어를 문자 단위로 트리에 저장하여 접두어 탐색을 O(M)에 수행한다.
#     각 노드는 자식 딕셔너리(해시맵)와 완성 여부 플래그를 가진다.
# ====================================================================
class TrieNode:
    """트라이의 단일 노드. 자식 노드들을 해시맵으로 관리한다."""

    def __init__(self) -> None:
        # 자료구조: 해시맵 (자식 문자 -> TrieNode). 평균 O(1) 접근.
        self.children: Dict[str, "TrieNode"] = {}
        self.is_end: bool = False          # 이 노드에서 단어가 끝나는지 여부
        self.task_ids: List[str] = []      # 이 단어와 연결된 태스크 ID 목록


class Trie:
    """
    접두어 자동완성을 위한 트라이(Trie) 자료구조.
    태스크 제목의 단어들을 삽입하고, 접두어 입력 시 일치하는 후보를 반환한다.
    """

    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, word: str, task_id: str) -> None:
        """
        트라이에 단어를 삽입한다.
        단어의 각 문자를 따라 노드를 생성하고, 끝 노드에 태스크 ID를 기록한다.
        시간복잡도: O(M) -- M=단어 길이
        """
        node = self.root
        for ch in word.lower():            # 소문자 정규화
            if ch not in node.children:
                node.children[ch] = TrieNode()
            node = node.children[ch]
        node.is_end = True
        if task_id not in node.task_ids:
            node.task_ids.append(task_id)

    def _collect_all(self, node: TrieNode, prefix: str,
                     results: List[Tuple[str, List[str]]]) -> None:
        """접두어 노드 하위의 모든 완성 단어와 태스크 ID를 재귀적으로 수집한다."""
        if node.is_end:
            results.append((prefix, list(node.task_ids)))
        for ch, child in node.children.items():
            self._collect_all(child, prefix + ch, results)

    def autocomplete(self, prefix: str, top_k: int = 10
                     ) -> List[Tuple[str, List[str]]]:
        """
        트라이 접두어 탐색 (자동완성).
        prefix 로 시작하는 모든 단어와 연결된 태스크 ID 목록을 반환한다.
        시간복잡도: O(M + 결과수) -- M=접두어 길이
        """
        node = self.root
        # 1단계: 접두어 끝까지 트라이를 따라 내려간다
        for ch in prefix.lower():
            if ch not in node.children:
                return []               # 접두어 자체가 없으면 빈 결과
            node = node.children[ch]

        # 2단계: 해당 노드 하위의 모든 단어를 수집
        results: List[Tuple[str, List[str]]] = []
        self._collect_all(node, prefix.lower(), results)

        # 알파벳 순 정렬 후 상위 top_k개만 반환
        results.sort(key=lambda x: x[0])
        return results[:top_k]


# ====================================================================
#  결과 컨테이너
# ====================================================================
@dataclass
class SearchResult:
    """검색 1건의 결과."""
    task_id: str
    title: str
    project: str
    sprint: str
    tags: List[str]
    match_field: str          # 어느 필드에서 일치했는지 (title / description / tags / id)
    match_positions: List[int]  # KMP/라빈-카프 매칭 시작 위치 목록 (퍼지 검색은 빈 리스트)
    edit_distance: Optional[int] = None  # 퍼지 검색 시 편집거리


# ====================================================================
#  백로그 검색기 본체
# ====================================================================
class BacklogSearcher:
    """
    태스크 백로그를 색인(Index)화하고 4가지 검색 방식을 제공한다.

    색인 구조:
      · 트라이(Trie)         : 단어 -> 태스크ID 자동완성 탐색
      · 역인덱스(dict)       : 단어 -> [태스크ID 목록] 빠른 역조회
      · tasks_by_id(dict)   : 태스크ID -> 태스크 레코드 O(1) 접근
    """

    def __init__(self, tasks: List[dict]) -> None:
        # 자료구조: 해시맵 id -> task 레코드 (자료구조 2)
        self.tasks_by_id: Dict[str, dict] = {t["id"]: t for t in tasks}
        self.tasks: List[dict] = tasks

        # 자료구조: 트라이 (자료구조 1)
        self.trie = Trie()

        # 자료구조: 역인덱스 해시맵 -- 단어 -> [태스크ID 목록] (자료구조 2 추가 활용)
        self.inverted_index: Dict[str, List[str]] = {}

        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        """텍스트를 공백/특수문자 기준으로 분리하여 단어 토큰 리스트를 반환한다."""
        import re
        # 영문자·한글·숫자만 남기고 분리
        tokens = re.findall(r"[a-zA-Z가-힣0-9]+", text.lower())
        return tokens

    def _build_index(self) -> None:
        """
        트라이와 역인덱스를 구축한다.
        모든 태스크의 title, tags, description에서 단어를 추출하여 색인화한다.
        """
        for task in self.tasks:
            tid = task["id"]
            # 색인 대상 필드: title + tags + description(첫 50자) + id
            texts = [
                task.get("title", ""),
                " ".join(task.get("tags", [])),
                task.get("description", "")[:100],
                tid,
            ]
            for text in texts:
                for word in self._tokenize(text):
                    if len(word) < 2:        # 1글자 단어는 색인 제외
                        continue
                    # 트라이에 삽입
                    self.trie.insert(word, tid)
                    # 역인덱스에 추가
                    self.inverted_index.setdefault(word, [])
                    if tid not in self.inverted_index[word]:
                        self.inverted_index[word].append(tid)

    # ================================================================
    #  [대표 알고리즘 ①·문자열매칭] KMP (Knuth-Morris-Pratt)
    #  -- 실패 함수(π 배열)를 미리 계산하여 불일치 시 최대한 앞으로 건너뜀.
    #     시간복잡도: O(N + M)  N=텍스트 길이, M=패턴 길이
    # ================================================================
    @staticmethod
    def _kmp_failure(pattern: str) -> List[int]:
        """
        KMP 실패 함수(failure function, π 배열)를 계산한다.
        π[i] = pattern[0..i]의 접두사이자 접미사인 가장 긴 문자열의 길이.
        자료구조: 1D 리스트 (자료구조 3)
        """
        m = len(pattern)
        # 자료구조: 리스트 -- KMP 실패 함수 테이블 (자료구조 3)
        pi: List[int] = [0] * m
        k = 0
        for i in range(1, m):
            # 불일치 시 이전 접두사-접미사 길이로 되돌아감 (핵심 아이디어)
            while k > 0 and pattern[k] != pattern[i]:
                k = pi[k - 1]
            if pattern[k] == pattern[i]:
                k += 1
            pi[i] = k
        return pi

    def _kmp_search(self, text: str, pattern: str) -> List[int]:
        """
        KMP 알고리즘으로 text 안에서 pattern의 모든 시작 위치를 반환한다.
        시간복잡도: O(N + M)
        """
        n, m = len(text), len(pattern)
        if m == 0 or n < m:
            return []

        pi = self._kmp_failure(pattern)
        positions: List[int] = []
        k = 0

        for i in range(n):
            # 불일치 시 실패 함수를 참조하여 k를 되돌림 (선형 시간 보장)
            while k > 0 and pattern[k] != text[i]:
                k = pi[k - 1]
            if pattern[k] == text[i]:
                k += 1
            if k == m:
                # 패턴 전체 일치: 시작 위치 기록
                positions.append(i - m + 1)
                k = pi[k - 1]          # 다음 매칭을 위해 되돌림

        return positions

    def search_kmp(self, pattern: str) -> List[SearchResult]:
        """
        KMP 알고리즘을 사용해 모든 태스크의 title, description, tags에서
        pattern을 포함하는 태스크를 찾아 반환한다.
        """
        pattern_lower = pattern.lower()
        results: List[SearchResult] = []
        seen: set = set()              # 중복 제거용 집합

        for task in self.tasks:
            tid = task["id"]
            if tid in seen:
                continue

            # 검색 대상 필드별로 KMP 실행
            fields = {
                "title": task.get("title", ""),
                "description": task.get("description", ""),
                "tags": " ".join(task.get("tags", [])),
                "id": tid,
            }

            for field_name, text in fields.items():
                positions = self._kmp_search(text.lower(), pattern_lower)
                if positions:
                    results.append(SearchResult(
                        task_id=tid,
                        title=task.get("title", ""),
                        project=task.get("project", ""),
                        sprint=task.get("sprint", ""),
                        tags=task.get("tags", []),
                        match_field=field_name,
                        match_positions=positions,
                    ))
                    seen.add(tid)
                    break               # 한 태스크에 하나의 결과만

        return results

    # ================================================================
    #  [대표 알고리즘 ②·문자열매칭] 라빈-카프 (Rabin-Karp)
    #  -- 롤링 해시(Rolling Hash)로 슬라이딩 윈도우를 이동하며 패턴과 비교.
    #     해시 일치 시에만 실제 문자 비교를 수행하여 평균 O(N+M).
    #     여러 키워드를 공백으로 구분하여 각각 탐색 후 OR 결합한다.
    # ================================================================
    @staticmethod
    def _rabin_karp_search(text: str, pattern: str,
                           base: int = 31, mod: int = 10**9 + 7) -> List[int]:
        """
        라빈-카프 롤링 해시 알고리즘으로 text에서 pattern의 시작 위치를 반환.
        시간복잡도: 평균 O(N+M), 최악 O(NM)
        """
        n, m = len(text), len(pattern)
        if m == 0 or n < m:
            return []

        positions: List[int] = []

        # 패턴의 해시값 미리 계산
        pat_hash = 0
        for ch in pattern:
            pat_hash = (pat_hash * base + ord(ch)) % mod

        # 텍스트 첫 윈도우의 해시값 계산
        win_hash = 0
        for ch in text[:m]:
            win_hash = (win_hash * base + ord(ch)) % mod

        # base^(m-1) mod mod -- 롤링 해시에서 맨 앞 문자 제거 시 사용
        power = pow(base, m - 1, mod)

        for i in range(n - m + 1):
            # 해시값 일치 시에만 실제 문자열 비교 (해시 충돌 방지)
            if win_hash == pat_hash and text[i:i + m] == pattern:
                positions.append(i)

            # 롤링 해시: 윈도우를 한 칸 오른쪽으로 이동
            if i < n - m:
                win_hash = (win_hash - ord(text[i]) * power) % mod
                win_hash = (win_hash * base + ord(text[i + m])) % mod
                win_hash = (win_hash + mod) % mod  # 음수 방지

        return positions

    def search_rabin_karp(self, query: str) -> List[SearchResult]:
        """
        라빈-카프 알고리즘을 사용해 여러 키워드를 동시에 검색한다.
        query를 공백으로 분리하여 각 키워드를 개별 탐색 후 합집합(OR)으로 결과를 반환.
        """
        keywords = [k.lower() for k in query.split() if k.strip()]
        if not keywords:
            return []

        results: List[SearchResult] = []
        seen: set = set()

        for task in self.tasks:
            tid = task["id"]
            if tid in seen:
                continue

            fields = {
                "title": task.get("title", "").lower(),
                "description": task.get("description", "").lower(),
                "tags": " ".join(task.get("tags", [])).lower(),
            }

            for keyword in keywords:
                matched = False
                for field_name, text in fields.items():
                    positions = self._rabin_karp_search(text, keyword)
                    if positions:
                        results.append(SearchResult(
                            task_id=tid,
                            title=task.get("title", ""),
                            project=task.get("project", ""),
                            sprint=task.get("sprint", ""),
                            tags=task.get("tags", []),
                            match_field=f"{field_name}[keyword={keyword}]",
                            match_positions=positions,
                        ))
                        seen.add(tid)
                        matched = True
                        break
                if matched:
                    break

        return results

    # ================================================================
    #  [보조 알고리즘] 트라이 자동완성 (Trie Autocomplete)
    #  -- 트라이에 색인된 단어를 접두어로 탐색하여 후보 단어 목록을 반환.
    # ================================================================
    def autocomplete(self, prefix: str, top_k: int = 8) -> List[Tuple[str, List[str]]]:
        """
        트라이 접두어 자동완성.
        prefix 로 시작하는 단어와 연결된 태스크 ID 목록을 반환한다.
        반환: [(단어, [태스크ID, ...]), ...]
        """
        return self.trie.autocomplete(prefix, top_k)

    # ================================================================
    #  [보조 알고리즘] 편집거리 DP (Levenshtein Distance)
    #  -- 두 문자열 간의 삽입/삭제/교체 최솟값을 2D DP로 계산.
    #     사용자 쿼리와 모든 태스크 title 간의 편집거리를 계산하여
    #     threshold 이하인 태스크를 거리 오름차순으로 반환한다.
    #     시간복잡도: O(M * N) per pair
    # ================================================================
    @staticmethod
    def _edit_distance(a: str, b: str) -> int:
        """
        편집거리(Levenshtein Distance)를 동적계획법으로 계산한다.
        삽입/삭제/교체 각 1회 연산으로 a를 b로 변환하는 최솟값.
        공간 최적화: 2개의 1D 리스트만 사용하여 O(min(M,N)) 공간.
        """
        if len(a) < len(b):
            a, b = b, a
        m, n = len(a), len(b)

        # 이전 행과 현재 행만 유지 (공간 최적화된 DP)
        prev = list(range(n + 1))
        curr = [0] * (n + 1)

        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    # 문자 일치: 대각선 값 그대로
                    curr[j] = prev[j - 1]
                else:
                    # 삽입, 삭제, 교체 중 최솟값 + 1
                    curr[j] = 1 + min(prev[j],      # 삭제
                                      curr[j - 1],  # 삽입
                                      prev[j - 1])  # 교체
            prev, curr = curr, prev

        return prev[n]

    def fuzzy_search(self, query: str, threshold: int = 2) -> List[SearchResult]:
        """
        편집거리 DP를 이용한 오타 보정 퍼지 검색.
        query와 편집거리가 threshold 이하인 태스크를 거리 오름차순으로 반환한다.
        """
        query_lower = query.lower()
        candidates: List[Tuple[int, SearchResult]] = []

        for task in self.tasks:
            tid = task["id"]
            title = task.get("title", "")

            # 제목 전체 vs 쿼리
            dist_full = self._edit_distance(query_lower, title.lower())

            # 제목의 각 단어 vs 쿼리 (단어 단위 매칭이 더 직관적)
            words = self._tokenize(title)
            dist_word = min(
                (self._edit_distance(query_lower, w) for w in words),
                default=dist_full
            )

            dist = min(dist_full, dist_word)

            if dist <= threshold:
                candidates.append((dist, SearchResult(
                    task_id=tid,
                    title=title,
                    project=task.get("project", ""),
                    sprint=task.get("sprint", ""),
                    tags=task.get("tags", []),
                    match_field="title(fuzzy)",
                    match_positions=[],
                    edit_distance=dist,
                )))

        # 편집거리 오름차순 정렬
        candidates.sort(key=lambda x: (x[0], x[1].task_id))
        return [r for _, r in candidates]


# ====================================================================
#  데이터 로더
# ====================================================================
def _load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks(tasks_path: str) -> List[dict]:
    return _load_json(tasks_path)


# ====================================================================
#  출력 헬퍼
# ====================================================================
def _rule(title: str = "", ch: str = "-", width: int = 78) -> str:
    if not title:
        return ch * width
    pad = width - len(title) - 4
    return f"{ch * 2} {title} {ch * max(pad, 0)}"


def _print_results(results: List[SearchResult], label: str, max_rows: int = 10) -> None:
    print(f"\n  [{label}] 결과 {len(results)}건")
    if not results:
        print("    (없음)")
        return
    print(f"    {'태스크ID':<8}{'프로젝트':<6}{'스프린트':<10}{'매칭필드':<25} 제목")
    for r in results[:max_rows]:
        field_info = r.match_field
        if r.edit_distance is not None:
            field_info += f" (거리={r.edit_distance})"
        elif r.match_positions:
            field_info += f" @{r.match_positions[:3]}"
        print(f"    {r.task_id:<8}{r.project:<6}{r.sprint:<10}{field_info:<25} {r.title[:38]}")
    if len(results) > max_rows:
        print(f"    ... 외 {len(results) - max_rows}건")


# ====================================================================
#  메인(CLI)
# ====================================================================
def main(argv: Optional[List[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    default_tasks = os.path.join(here, "data", "tasks.json")

    ap = argparse.ArgumentParser(
        description="Squadron Module 4 - 백로그 검색·자동완성 (KMP, 라빈-카프, 트라이, 편집거리)")
    ap.add_argument("--tasks", default=default_tasks,
                    help="태스크 JSON 경로 (기본: data/tasks.json)")
    ap.add_argument("--query", "-q", default=None,
                    help="검색 쿼리 문자열")
    ap.add_argument("--mode", "-m",
                    choices=["kmp", "rabin", "auto", "fuzzy", "all"],
                    default="all",
                    help="검색 모드: kmp(정확), rabin(다중키워드), auto(자동완성), fuzzy(오타보정), all(데모)")
    ap.add_argument("--threshold", "-t", type=int, default=2,
                    help="퍼지 검색 편집거리 임계값 (기본 2)")
    ap.add_argument("--top-k", type=int, default=8,
                    help="자동완성 최대 후보 수 (기본 8)")
    ap.add_argument("--max-rows", type=int, default=10,
                    help="결과 출력 최대 행수 (기본 10)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.tasks):
        print(f"Error: 태스크 파일을 찾을 수 없습니다. ({args.tasks})")
        return 1

    tasks = load_tasks(args.tasks)
    searcher = BacklogSearcher(tasks)

    print(_rule("SQUADRON - Module 4 - 백로그 검색·자동완성", "="))
    print(f"  색인 완료: 태스크 {len(tasks)}개 | 역인덱스 단어 {len(searcher.inverted_index)}개\n")

    # -- 쿼리 없이 실행 시: 빌트인 데모 --
    if args.query is None or args.mode == "all":
        print(_rule("빌트인 데모 (모든 검색 모드)", "="))

        # 데모 1: KMP 정확 검색
        demo_kmp = searcher.search_kmp("search")
        _print_results(demo_kmp, "KMP 정확검색: 'search'", args.max_rows)

        # 데모 2: 라빈-카프 다중 키워드
        demo_rk = searcher.search_rabin_karp("API auth")
        _print_results(demo_rk, "라빈-카프 다중키워드: 'API auth'", args.max_rows)

        # 데모 3: 트라이 자동완성
        prefix = "sch"
        auto_res = searcher.autocomplete(prefix, args.top_k)
        print(f"\n  [트라이 자동완성: '{prefix}'] 후보 {len(auto_res)}개")
        for word, tids in auto_res:
            print(f"    '{word}' -> 태스크 {len(tids)}개: {tids[:4]}")

        # 데모 4: 퍼지 오타 보정 -- 'dashbord'는 'dashboard'의 오타 (편집거리 1)
        demo_fuzzy = searcher.fuzzy_search("dashbord", threshold=2)
        _print_results(demo_fuzzy, "편집거리 퍼지검색: 'dashbord' (오타->dashboard, threshold=2)", args.max_rows)

        print()
        return 0

    # -- 쿼리 지정 시 --
    if args.mode == "kmp":
        res = searcher.search_kmp(args.query)
        _print_results(res, f"KMP 정확검색: '{args.query}'", args.max_rows)

    elif args.mode == "rabin":
        res = searcher.search_rabin_karp(args.query)
        _print_results(res, f"라빈-카프 다중키워드: '{args.query}'", args.max_rows)

    elif args.mode == "auto":
        res = searcher.autocomplete(args.query, args.top_k)
        print(f"\n  [트라이 자동완성: '{args.query}'] 후보 {len(res)}개")
        for word, tids in res:
            titles = [searcher.tasks_by_id[tid]["title"][:30]
                      for tid in tids[:2] if tid in searcher.tasks_by_id]
            print(f"    '{word}' ({len(tids)}개) -> {', '.join(titles)}")

    elif args.mode == "fuzzy":
        res = searcher.fuzzy_search(args.query, threshold=args.threshold)
        _print_results(res, f"편집거리 퍼지검색: '{args.query}' (threshold={args.threshold})",
                       args.max_rows)

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
