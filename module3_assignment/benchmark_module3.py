#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module 3 assignment benchmark runner.

This script imports the existing SprintPlanner implementation without changing it,
runs the two selected algorithms on executable raw input data, and writes CSV
results for the report.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
import tracemalloc
from typing import Callable, Dict, List, Tuple


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from planner import SprintPlanner  # noqa: E402


Task = Dict[str, object]
PlanFn = Callable[[List[Task], int], Tuple[List[str], int, int]]


def load_json(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def measure(fn: Callable[[], object], runs: int = 30) -> Tuple[float, float, int]:
    """Return average ms, median ms, and peak bytes over repeated runs."""
    elapsed = []
    peak_bytes = 0
    for _ in range(runs):
        tracemalloc.start()
        start = time.perf_counter()
        fn()
        elapsed.append((time.perf_counter() - start) * 1000.0)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak_bytes = max(peak_bytes, peak)
    return statistics.mean(elapsed), statistics.median(elapsed), peak_bytes


def write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def benchmark_single_knapsack(planner: SprintPlanner, tasks: List[Task]) -> List[Dict[str, object]]:
    """Measure DP and Backtracking on real task subsets with increasing input size."""
    rows: List[Dict[str, object]] = []
    sizes = [5, 10, 15, 20, 25, 30]
    for n in sizes:
        subset = tasks[:n]
        capacity = max(10, int(sum(int(t.get("estimate", 0)) for t in subset) * 0.40))
        for name, fn in [
            ("DP", planner.plan_dp),
            ("Backtracking", planner.plan_backtracking),
        ]:
            avg_ms, median_ms, peak_bytes = measure(lambda fn=fn: fn(subset, capacity), runs=30)
            selected, used, value = fn(subset, capacity)
            rows.append({
                "scenario": "single_knapsack_scaling",
                "algorithm": name,
                "task_count": n,
                "capacity": capacity,
                "selected_count": len(selected),
                "used_capacity": used,
                "total_value": value,
                "avg_ms": round(avg_ms, 5),
                "median_ms": round(median_ms, 5),
                "peak_kb": round(peak_bytes / 1024, 2),
            })
    return rows


def benchmark_demo(planner: SprintPlanner) -> List[Dict[str, object]]:
    """Measure the P3-S4 demo case described in README and the report."""
    demo_tasks = [
        {"id": "T0151", "estimate": 6, "value": 60, "title": "Knapsack Item A"},
        {"id": "T0152", "estimate": 5, "value": 40, "title": "Knapsack Item B"},
        {"id": "T0153", "estimate": 5, "value": 40, "title": "Knapsack Item C"},
    ]
    rows: List[Dict[str, object]] = []
    for name, fn in [
        ("Greedy baseline", planner.plan_greedy),
        ("DP", planner.plan_dp),
        ("Backtracking", planner.plan_backtracking),
    ]:
        avg_ms, median_ms, peak_bytes = measure(lambda fn=fn: fn(demo_tasks, 10), runs=100)
        selected, used, value = fn(demo_tasks, 10)
        rows.append({
            "scenario": "P3-S4_demo",
            "algorithm": name,
            "task_count": len(demo_tasks),
            "capacity": 10,
            "selected_tasks": " ".join(selected),
            "used_capacity": used,
            "total_value": value,
            "avg_ms": round(avg_ms, 5),
            "median_ms": round(median_ms, 5),
            "peak_kb": round(peak_bytes / 1024, 2),
        })
    return rows


def benchmark_global(tasks: List[Task], sprints: list, projects: list) -> List[Dict[str, object]]:
    """Measure global planning on the executable Squadron input data."""
    rows: List[Dict[str, object]] = []
    for method in ["greedy", "dp", "backtracking"]:
        def run(method: str = method):
            local_planner = SprintPlanner(tasks, sprints, projects)
            return local_planner.plan_global(method=method)

        avg_ms, median_ms, peak_bytes = measure(run, runs=20)
        result = run()
        rows.append({
            "scenario": "global_sprint_planning",
            "algorithm": method.upper(),
            "task_count": len(tasks),
            "sprint_count": len(sprints),
            "selected_count": sum(len(p.selected_tasks) for p in result.sprint_plans.values()),
            "total_capacity_used": result.total_capacity_used,
            "total_value": result.total_value,
            "carried_forward_total": result.carried_forward_total,
            "unplanned_tasks": len(result.unplanned_tasks),
            "avg_ms": round(avg_ms, 5),
            "median_ms": round(median_ms, 5),
            "peak_kb": round(peak_bytes / 1024, 2),
        })
    return rows


def main() -> int:
    data_dir = os.path.join(ROOT, "data")
    tasks = load_json(os.path.join(data_dir, "tasks.json"))
    sprints = load_json(os.path.join(data_dir, "sprints.json"))
    projects = load_json(os.path.join(data_dir, "projects.json"))

    planner = SprintPlanner(tasks, sprints, projects)

    demo_rows = benchmark_demo(planner)
    scaling_rows = benchmark_single_knapsack(planner, tasks)
    global_rows = benchmark_global(tasks, sprints, projects)

    write_csv(os.path.join(OUT_DIR, "benchmark_demo.csv"), demo_rows)
    write_csv(os.path.join(OUT_DIR, "benchmark_scaling.csv"), scaling_rows)
    write_csv(os.path.join(OUT_DIR, "benchmark_global.csv"), global_rows)

    print("Benchmark complete.")
    print(f"- demo rows: {len(demo_rows)}")
    print(f"- scaling rows: {len(scaling_rows)}")
    print(f"- global rows: {len(global_rows)}")
    print(f"CSV output directory: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
