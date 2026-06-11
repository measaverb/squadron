#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Squadron — 시각화 대시보드 (Streamlit)
=======================================

Module 1(스케줄러)·Module 2(배정기)의 결과를 한눈에 보여주는 프레젠테이션 레이어.
graded 알고리즘 코드(scheduler.py, allocator.py)는 표준 라이브러리만 쓰며 그대로 재사용한다.
이 앱만 streamlit/pandas/altair 를 사용한다(requirements.txt 참고).

실행:
    pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import os
import datetime as dt
from typing import List, Dict, Optional

import pandas as pd
import altair as alt
import streamlit as st

import scheduler as S          # Module 1 (표준 라이브러리만)
import allocator as A          # Module 2 (표준 라이브러리만)
import planner as P            # Module 3 (표준 라이브러리만)
import searcher as SR          # Module 4 (표준 라이브러리만)
from searchSprint import IntegratedSprintPlanner       # Module 4 (스프린트 검색 엔진) --- IGNORE ---

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

st.set_page_config(page_title="Squadron 스케줄러·배정기", page_icon="🛰️", layout="wide")

# 색상 팔레트
C_CRIT = "#e4572e"     # 임계경로(빨강)
C_NORM = "#4c78a8"     # 일반(파랑)
C_SLACK = "#cfd8e3"    # 여유(연회색)
C_HUNG = "#2e7d32"     # 헝가리안(초록)
C_GREEDY = "#b8860b"   # 그리디(황토)
C_BAD = "#c62828"      # 미배정(빨강)


# ──────────────────────────── 데이터 로딩 ────────────────────────────
@st.cache_data(show_spinner=False)
def load_raw(tasks_filename: str):
    """원본 JSON 로드(캐시). tasks 파일명만 바꿔 정상/사이클 데이터 전환."""
    tasks = S._load_json(os.path.join(DATA_DIR, tasks_filename))
    projects = S._load_json(os.path.join(DATA_DIR, "projects.json"))
    sprints = S._load_json(os.path.join(DATA_DIR, "sprints.json"))
    developers = S._load_json(os.path.join(DATA_DIR, "developers.json"))
    
    return tasks, projects, sprints, developers

@st.cache_data(show_spinner=False)
def get_integrated_schedule_data(data_path):
    # 4개의 데이터 대신 경로(data_path) 1개만 플래너로 보냅니다!
    planner = IntegratedSprintPlanner(data_path)
    return planner.get_planning_data()


def build_scheduler(tasks, projects, sprints) -> S.Scheduler:
    return S.Scheduler(tasks, projects, sprints)


# ──────────────────────────── 사이드바 ────────────────────────────
st.sidebar.title("🛰️ Squadron")
st.sidebar.caption("조직 단위 엔지니어링 리소스 매니저·검색기")
data_choice = st.sidebar.radio(
    "데이터셋",
    ["tasks.json (정상 DAG)", "tasks_broken.json (사이클 주입)"],
    help="Module 1 의 사이클 검출을 보려면 broken 을 선택하세요.",
)
tasks_filename = "tasks.json" if data_choice.startswith("tasks.json") else "tasks_broken.json"

tasks, projects, sprints, developers = load_raw(tasks_filename)
sch = build_scheduler(tasks, projects, sprints)
alloc = A.Allocator(developers)
proj_name = {p["id"]: p["name"] for p in projects}
task_by_id = {t["id"]: t for t in tasks}

st.sidebar.metric("태스크", len(tasks))
st.sidebar.metric("개발자", len(developers))
st.sidebar.metric("프로젝트", len(projects))

st.title("Squadron — 프로젝트 스케줄러 · 특성기반 배정기")

tab1, tab2, tab_alloc, tab_planner, tab3, tab4, tab_search = st.tabs([
    "📅 Module 1 · 스케줄/임계경로",
    "🔁 Module 1 · 사이클 검출",
    "🗺️ Module 1→2 · 전체 일정 배정",
    "📦 Module 3 · 스프린트 플래너",
    "👥 Module 2 · 배정 (헝가리안 vs 그리디)",
    "🔍 Module 4 · 백로그 검색",
    "🔎 전체 일정 상세 검색"
])

# ════════════════════════════════════════════════════════════════════
#  TAB 1 — 스케줄 / 임계경로 / 타임라인
# ════════════════════════════════════════════════════════════════════
with tab1:
    pid = st.selectbox("프로젝트", sch.project_ids(),
                       format_func=lambda p: f"{p} · {proj_name.get(p, p)}")
    cp = sch.critical_path(pid)

if cp.has_cycle:
    # 사이클을 포함한 프로젝트는 임계경로/타임라인이 정의되지 않는다 → 잘못된 수치를 그리지 않는다.
    with tab1:
        st.error(f"프로젝트 **{pid}** 는 순환 의존성(사이클)을 포함하여 임계경로·타임라인이 "
                 f"정의되지 않습니다. ‘🔁 사이클 검출’ 탭에서 원인을 확인하세요. "
                 f"(다른 프로젝트나 tasks.json 을 선택하면 정상 표시됩니다.)")
else:
  with tab1:
    velocity = st.slider("속도 velocity (pts/영업일)", 1.0, 10.0,
                         float(round(sch.project_velocity(pid), 2)), 0.25,
                         help="임계경로 길이를 마감일에 맞춰 달력으로 환산할 때의 처리 속도")
    rows, kickoff, deadline, vused = sch.build_timeline(pid, velocity)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("임계경로 길이", f"{cp.makespan_points} pts")
    c2.metric("임계 태스크 수", f"{sum(r.on_critical_path for r in rows)} / {len(rows)}")
    c3.metric("착수일 (kickoff)", kickoff.isoformat())
    c4.metric("마감일 (deadline)", deadline.isoformat())

    st.markdown("**임계경로(Critical Path)** — 지연되면 프로젝트 전체가 지연되는 무여유 사슬")
    st.markdown(
        " → ".join(f"`{tid}`({sch.tasks[tid]['estimate']})" for tid in cp.critical_path)
        or "_없음_"
    )

    # ── Gantt 차트 (Altair) : ES~EF 막대 + EF~LF 여유(slack) 막대 ──
    st.subheader("타임라인 (Gantt)")
    gantt_rows = []
    for r in rows:
        gantt_rows.append({
            "task": r.id,
            "start": pd.Timestamp(r.early_start),
            "finish": pd.Timestamp(r.early_finish),
            "slack_finish": pd.Timestamp(r.late_finish),
            "kind": "임계경로" if r.on_critical_path else "일반",
            "priority": r.priority,
            "estimate": r.estimate,
            "slack_pts": r.slack_points,
            "ES": cp.es[r.id], "EF": cp.ef[r.id],
            "LS": cp.ls[r.id], "LF": cp.lf[r.id],
        })
    gdf = pd.DataFrame(gantt_rows)
    only_critical = st.checkbox("임계경로만 보기", value=False)
    show = gdf[gdf["kind"] == "임계경로"] if only_critical else gdf
    order_field = alt.SortField(field="start", order="ascending")

    base = alt.Chart(show)
    slack_bars = base.mark_bar(opacity=0.35, color=C_SLACK).encode(
        x=alt.X("finish:T", title="날짜"),
        x2="slack_finish:T",
        y=alt.Y("task:N", sort=order_field, title=None),
    ).transform_filter(alt.datum.slack_finish > alt.datum.finish)   # 일(day) 해상도에서 보이는 여유만
    work_bars = base.mark_bar().encode(
        x=alt.X("start:T", title="날짜"),
        x2="finish:T",
        y=alt.Y("task:N", sort=order_field, title=None),
        color=alt.Color("kind:N",
                        scale=alt.Scale(domain=["임계경로", "일반"], range=[C_CRIT, C_NORM]),
                        legend=alt.Legend(title="구분")),
        tooltip=["task", "kind", "priority", "estimate", "slack_pts",
                 "ES", "EF", "LS", "LF",
                 alt.Tooltip("start:T", title="이른시작"),
                 alt.Tooltip("finish:T", title="이른완료")],
    )
    height = max(220, 18 * len(show))
    st.altair_chart((slack_bars + work_bars).properties(height=height).interactive(),
                    width="stretch")
    st.caption("막대=작업기간(ES→EF), 연회색=여유(slack, EF→LF). 빨강=임계경로.")

    colA, colB = st.columns(2)
    with colA:
        st.subheader("여유시간(slack) 표")
        sdf = gdf[["task", "priority", "estimate", "ES", "EF", "LS", "LF", "slack_pts", "kind"]] \
            .sort_values(["slack_pts", "task"]).reset_index(drop=True)
        st.dataframe(sdf, width="stretch", height=360)
    with colB:
        st.subheader("우선순위 인지 실행 순서")
        order, _cyc = sch.priority_topo_sort(pid)
        odf = pd.DataFrame([{
            "#": i + 1, "task": tid, "priority": sch.tasks[tid].get("priority", 4),
            "slack": sch.slack.get(tid, 0), "estimate": sch.tasks[tid]["estimate"],
            "out_deg": len(sch.adj[tid]), "title": sch.tasks[tid]["title"],
        } for i, tid in enumerate(order)])
        st.dataframe(odf, width="stretch", height=360, hide_index=True)
        st.caption("정렬 키: slack↑, priority↑, deadline↑, out_degree↓, id")

    # ── 의존성 DAG (graphviz DOT) : 임계경로 강조 ──
    with st.expander("의존성 그래프(DAG) 보기 — 임계경로 빨강 강조", expanded=False):
        # 노드 강조는 Gantt·지표와 동일하게 'slack==0 전체 집합'으로, 굵은 빨강 간선만 대표 사슬로.
        critset = {r.id for r in rows if r.on_critical_path}
        crit_edges = set(zip(cp.critical_path, cp.critical_path[1:]))
        ids = sch._project_task_ids(pid)
        dot = ["digraph G { rankdir=LR; node [shape=box,style=rounded,fontsize=10];"]
        for tid in ids:
            color = C_CRIT if tid in critset else "#dddddd"
            font = "white" if tid in critset else "black"
            dot.append(f'"{tid}" [label="{tid}\\n{sch.tasks[tid]["estimate"]}p",'
                       f'fillcolor="{color}",style="rounded,filled",fontcolor="{font}"];')
        for u in ids:
            for v in sch.adj[u]:
                if v in set(ids):
                    if (u, v) in crit_edges:
                        dot.append(f'"{u}" -> "{v}" [color="{C_CRIT}",penwidth=2.4];')
                    else:
                        dot.append(f'"{u}" -> "{v}" [color="#bbbbbb"];')
        dot.append("}")
        st.graphviz_chart("\n".join(dot), width="stretch")


# ════════════════════════════════════════════════════════════════════
#  TAB 2 — 사이클 검출
# ════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("사이클(순환 의존성) 검출 — 칸(Kahn) 잔여 + DFS 역간선 복원")
    cyc = sch.detect_cycles()
    if not cyc.has_cycle:
        st.success(f"✔ **{tasks_filename}** 은 유효한 DAG 입니다. 모든 태스크가 스케줄 가능합니다.")
        st.info("사이클 검출을 보려면 사이드바에서 **tasks_broken.json** 을 선택하세요.")
    else:
        cycles = cyc.cycles or ([cyc.cycle] if cyc.cycle else [])
        st.error(f"✘ 사이클 {len(cycles)}개 검출 — 스케줄 불가 태스크 {len(cyc.unschedulable)}개")
        for i, chain in enumerate(cycles, 1):
            st.markdown(f"**순환 #{i}** ({len(set(chain))}개): "
                        + " → ".join(f"`{c}`" for c in chain))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**스케줄 불가 태스크**")
            st.write(", ".join(f"`{t}`" for t in cyc.unschedulable))
            st.markdown("**그중 사이클 하류(원인 아님, 막힘)**")
            st.write(", ".join(f"`{t}`" for t in cyc.downstream_blocked) or "_없음_")
        with c2:
            # 사이클 + 직접 하류를 그래프로 강조
            cyc_nodes = set()
            for ch in cycles:
                cyc_nodes |= set(ch)
            highlight = cyc_nodes | set(cyc.downstream_blocked)
            cyc_edges = set()
            for ch in cycles:
                cyc_edges |= set(zip(ch, ch[1:]))
            dot = ["digraph G { rankdir=LR; node [shape=box,style=rounded,fontsize=10];"]
            for tid in sorted(highlight):
                in_cycle = tid in cyc_nodes
                dot.append(f'"{tid}" [fillcolor="{C_BAD if in_cycle else "#ffd9b3"}",'
                           f'style="rounded,filled",'
                           f'fontcolor="{"white" if in_cycle else "black"}"];')
            for u in sorted(highlight):
                for v in sch.adj[u]:
                    if v in highlight:
                        red = (u, v) in cyc_edges
                        dot.append(f'"{u}" -> "{v}" '
                                   f'[color="{C_BAD if red else "#999999"}",'
                                   f'penwidth={2.6 if red else 1}];')
            dot.append("}")
            st.graphviz_chart("\n".join(dot), width="stretch")
        st.caption("빨강 노드/간선 = 사이클 구성원, 주황 = 사이클 하류(막힌 태스크).")


# ════════════════════════════════════════════════════════════════════
#  TAB (Module 1→2) — 전체 일정 자동 배정 (rolling, capacity-aware)
#  ── Module 1 의 임계도(slack)·스프린트 스케줄 순서가 배정을 구동한다.
#     스케줄 순서대로, 임계경로 태스크부터 헝가리안으로 최적 배정하며 개발자
#     용량을 전 일정에 걸쳐 누적 소진(carry-forward)한다.
# ════════════════════════════════════════════════════════════════════
with tab_alloc:
    st.subheader("전체 일정 자동 배정 — 스케줄 순서대로 용량 소진 (Module 1 → Module 2)")
    st.caption("Module 1 이 정한 임계도와 스프린트 순서가 Module 2 의 배정을 구동한다. "
               "각 스프린트에서 임계경로 태스크부터 헝가리안으로 1:1 최적 배정을 반복하고, "
               "한 개발자는 잔여 용량이 남는 한 여러 태스크를 맡으며, 소진된 용량은 다음 "
               "스프린트로 이월된다(전 일정 누적).")

    # Module 1 → Module 2 연동: 임계도(slack)·임계여부·스프린트 스케줄 순서 추출
    slack_v, crit_v, sprint_ord = A.schedule_view(tasks, projects, sprints)
    sg = alloc.allocate_schedule(tasks, slack_v, crit_v, sprint_ord, method="greedy")
    sh = alloc.allocate_schedule(tasks, slack_v, crit_v, sprint_ord, method="hungarian")

    any_cycle = any(sch.critical_path(p).has_cycle for p in sch.project_ids())
    if any_cycle:
        st.warning("선택된 데이터셋에 사이클 프로젝트가 있어 해당 프로젝트의 임계경로는 "
                   "정의되지 않습니다(임계도=비임계 처리). 배정 자체는 정상 수행됩니다.")

    st.markdown("**스케줄 순서(Module 1):** " + " → ".join(f"`{s}`" for s in sh.sprint_order))

    # ── 조직 집계: 그리디 vs 헝가리안 ──
    staffed_h = len(sh.assignments) - len(sh.unstaffed)
    staffed_g = len(sg.assignments) - len(sg.unstaffed)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 친화도", sh.total_score, delta=sh.total_score - sg.total_score,
              help=f"그리디 {sg.total_score} → 헝가리안 {sh.total_score}")
    m2.metric("배정 완료", f"{staffed_h}/{len(tasks)}", delta=staffed_h - staffed_g,
              help=f"그리디 {staffed_g} → 헝가리안 {staffed_h}")
    m3.metric("미배정", len(sh.unstaffed), delta=len(sh.unstaffed) - len(sg.unstaffed),
              delta_color="inverse", help=f"그리디 {len(sg.unstaffed)} → 헝가리안 {len(sh.unstaffed)}")
    m4.metric("임계경로 커버리지", f"{sh.critical_staffed}/{sh.critical_total}",
              delta=sh.critical_staffed - sg.critical_staffed,
              help="임계경로 태스크 중 인력 배정된 비율(헝가리안)")

    # ── 미배정 진단: 스킬 부재(채용) vs 전문가 적체(재배치) ──
    if sh.unstaffed:
        unstaffable, contended, bottleneck = A.classify_unstaffed(sh.unstaffed, task_by_id, alloc.devs)
        st.markdown("#### 미배정 진단")
        d1, d2 = st.columns(2)
        with d1:
            st.markdown(f"**스킬 부재 {len(unstaffable)}개** — 필수 스킬 조합 보유자 0명 "
                        f"<span style='color:#888'>(채용·교육 신호)</span>", unsafe_allow_html=True)
            st.write(", ".join(f"`{t}`" for t in unstaffable) or "_없음_")
        with d2:
            st.markdown(f"**전문가 적체 {len(contended)}개** — 자격자는 있으나 용량 소진 "
                        f"<span style='color:#888'>(재배치·증원 신호)</span>", unsafe_allow_html=True)
            st.write(", ".join(f"`{t}`" for t in contended) or "_없음_")
            top = sorted(bottleneck.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
            if top:
                st.caption("병목 전문가(적체 태스크의 자격자): "
                           + ", ".join(f"**{d}**({n}건)" for d, n in top))

    # ── 스프린트별 배정/미배정 (스택 막대) ──
    st.markdown("#### 스프린트별 배정 현황")
    h_un = set(sh.unstaffed)
    sp_rows = []
    for sp in sh.sprint_order:
        ids = [t["id"] for t in tasks if (t.get("sprint") or "_backlog") == sp]
        staffed = sum(1 for i in ids if i not in h_un)
        sp_rows.append({"sprint": sp, "배정": staffed, "미배정": len(ids) - staffed})
    spdf = pd.DataFrame(sp_rows).melt("sprint", var_name="상태", value_name="개수")
    sp_chart = alt.Chart(spdf).mark_bar().encode(
        x=alt.X("sprint:N", sort=sh.sprint_order, title=None),
        y=alt.Y("개수:Q", stack="zero", title="태스크 수"),
        color=alt.Color("상태:N",
                        scale=alt.Scale(domain=["배정", "미배정"], range=[C_HUNG, C_BAD]),
                        legend=alt.Legend(title=None)),
        tooltip=["sprint", "상태", "개수"],
    )
    st.altair_chart(sp_chart.properties(height=240), width="stretch")

    # ── 개발자별 워크로드 표 + 가동률(util) 막대 ──
    st.markdown("#### 개발자별 워크로드 (헝가리안)")
    wrows = []
    for d, ts in sh.by_dev.items():
        dev = alloc.devs[d]
        cap = sh.dev_cap.get(d, 0)
        load = sh.dev_load.get(d, 0)
        wrows.append({
            "dev": d, "level": dev.get("level", 1), "tasks": len(ts),
            "load": load, "avail": cap,   # avail = 가용용량(capacity−current_load)
            "util%": round(load / cap * 100) if cap > 0 else 0,
            "projects": ",".join(sorted({task_by_id[t]["project"] for t in ts})),
        })
    wdf = pd.DataFrame(wrows).sort_values(["load", "dev"], ascending=[False, True]).reset_index(drop=True)

    wc1, wc2 = st.columns([3, 2])
    with wc1:
        bar = alt.Chart(wdf).mark_bar().encode(
            y=alt.Y("dev:N", sort="-x", title=None),
            x=alt.X("load:Q", title="확정 부하(load, pts)"),
            color=alt.Color("util%:Q", scale=alt.Scale(scheme="greenblue", domain=[0, 100]),
                            legend=alt.Legend(title="가동률%")),
            tooltip=["dev", "level", "tasks", "load", "avail", "util%", "projects"],
        )
        cap_tick = alt.Chart(wdf).mark_tick(color=C_BAD, thickness=2, size=14).encode(
            y=alt.Y("dev:N", sort="-x"), x=alt.X("avail:Q"),
            tooltip=["dev", "avail"],
        )
        st.altair_chart((bar + cap_tick).properties(height=max(260, 15 * len(wdf))), width="stretch")
        st.caption("막대=확정 부하, 빨강 눈금=가용 용량(capacity−current_load). 색 진할수록 가동률↑.")
    with wc2:
        used = len(sh.by_dev)
        idle = len(developers) - used
        utils = [r["util%"] for r in wrows if r["util%"] > 0]
        avg_u = round(sum(utils) / len(utils)) if utils else 0
        st.metric("사용 개발자", f"{used}/{len(developers)}", help=f"유휴 {idle}명")
        st.metric("평균 가용용량 소진율", f"{avg_u}%",
                  help="util = 신규 배정 load / 가용용량(capacity−current_load). 총 용량 대비가 아님.")
        st.metric("배정 태스크", f"{staffed_h}")
        st.dataframe(wdf, width="stretch", hide_index=True, height=300)

    # ── 개발자 드릴다운: 한 개발자가 맡은 태스크 ──
    st.markdown("#### 개발자 드릴다운 — 맡은 태스크 (스케줄 순)")
    used_devs = sorted(sh.by_dev, key=lambda d: (-sh.dev_load.get(d, 0), d))
    if used_devs:
        sel = st.selectbox(
            "개발자 선택", used_devs,
            format_func=lambda d: f"{d} · load {sh.dev_load.get(d,0)}/{sh.dev_cap.get(d,0)}"
                                  f" · {len(sh.by_dev[d])} tasks")
        sp_rank = {s: i for i, s in enumerate(sh.sprint_order)}
        dtasks = sorted(
            sh.by_dev[sel],
            key=lambda tid: (sp_rank.get(task_by_id[tid].get("sprint") or "_backlog", 10**9),
                             0 if crit_v.get(tid) else 1, slack_v.get(tid, 0), tid))
        drows = [{
            "task": tid, "sprint": task_by_id[tid].get("sprint"),
            "project": task_by_id[tid].get("project"),
            "critical": "★" if crit_v.get(tid) else "",
            "priority": task_by_id[tid].get("priority", 4),
            "estimate": task_by_id[tid].get("estimate", 0),
            "affinity": A.affinity(alloc.devs[sel], task_by_id[tid]),
            "title": task_by_id[tid].get("title", "")[:50],
        } for tid in dtasks]
        st.dataframe(pd.DataFrame(drows), width="stretch", hide_index=True)
        sk = ", ".join(alloc.devs[sel].get("skills", []))
        st.caption(f"**{sel}** 보유 스킬: {sk}")


# ════════════════════════════════════════════════════════════════════
#  TAB 3 — 배정 (헝가리안 vs 그리디)
# ════════════════════════════════════════════════════════════════════
def assignment_table(batch: List[dict], greedy: A.AllocationResult,
                     hung: A.AllocationResult) -> pd.DataFrame:
    gmap = {a.task: a for a in greedy.assignments}
    hmap = {a.task: a for a in hung.assignments}
    out = []
    for t in batch:
        tid = t["id"]
        g, h = gmap[tid], hmap[tid]
        out.append({
            "scarce": "✦" if A.is_scarce_task(t) else "",
            "task": tid,
            "priority": t.get("priority", 4),
            "required_skills": ", ".join(t.get("required_skills", [])),
            "greedy": f"{g.dev} ({g.score})" if g.dev else "── 미배정 ──",
            "hungarian": f"{h.dev} ({h.score})" if h.dev else "── 미배정 ──",
            "diff": "◄" if g.dev != h.dev else "",
        })
    return pd.DataFrame(out)


def metrics_block(greedy: A.AllocationResult, hung: A.AllocationResult):
    c1, c2, c3 = st.columns(3)
    c1.metric("총 친화도", hung.total_score, delta=hung.total_score - greedy.total_score,
              help=f"그리디 {greedy.total_score} → 헝가리안 {hung.total_score}")
    c2.metric("미배정", len(hung.unstaffed),
              delta=len(hung.unstaffed) - len(greedy.unstaffed),
              delta_color="inverse",
              help=f"그리디 {len(greedy.unstaffed)} → 헝가리안 {len(hung.unstaffed)}")
    c3.metric("희소 스킬 배정", f"{hung.scarce_staffed}/{hung.scarce_total}",
              delta=hung.scarce_staffed - greedy.scarce_staffed,
              help=f"그리디 {greedy.scarce_staffed} → 헝가리안 {hung.scarce_staffed}")


def bipartite_dot(batch, res: A.AllocationResult, title_color: str) -> str:
    """태스크→개발자 배정 이분그래프 DOT. 희소 태스크/미배정 강조."""
    bid = {t["id"]: t for t in batch}
    dot = ['digraph G { rankdir=LR; node [shape=box,style="rounded,filled",fontsize=10];']
    for t in batch:
        tid = t["id"]
        scarce = A.is_scarce_task(t)
        dot.append(f'"{tid}" [fillcolor="{"#ffe0b2" if scarce else "#eef2f7"}"];')
    devs_used = sorted({a.dev for a in res.assignments if a.dev})
    for d in devs_used:
        dot.append(f'"{d}" [fillcolor="#e8f5e9"];')
    dot.append('"미배정" [fillcolor="#ffcdd2",fontcolor="#000"];')
    for a in res.assignments:
        if a.dev:
            scarce = A.is_scarce_task(bid[a.task])
            dot.append(f'"{a.task}" -> "{a.dev}" '
                       f'[label="{a.score}",color="{title_color}",'
                       f'penwidth={2.4 if scarce else 1.2},fontsize=9];')
        else:
            dot.append(f'"{a.task}" -> "미배정" [color="{C_BAD}",style=dashed];')
    dot.append("}")
    return "\n".join(dot)


def affinity_heatmap(batch, pool, res: A.AllocationResult):
    """태스크×개발자 친화도 히트맵(Altair). 배정 셀에 테두리 강조."""
    devmap = alloc.devs
    cells = []
    assigned = {(a.task, a.dev) for a in res.assignments if a.dev}
    for t in batch:
        for d in pool:
            s = A.affinity(devmap[d], t)
            cells.append({
                "task": t["id"], "dev": d,
                "affinity": s if s is not None else None,
                "feasible": "가능" if s is not None else "불가",
                "assigned": (t["id"], d) in assigned,
            })
    df = pd.DataFrame(cells)
    base = alt.Chart(df)
    heat = base.mark_rect().encode(
        x=alt.X("dev:N", title="개발자"),
        y=alt.Y("task:N", title="태스크"),
        color=alt.Color("affinity:Q", scale=alt.Scale(scheme="blues"),
                        legend=alt.Legend(title="친화도")),
        tooltip=["task", "dev", "affinity", "feasible"],
    )
    marks = base.transform_filter(alt.datum.assigned).mark_point(
        shape="circle", size=80, filled=True, color=C_HUNG).encode(
        x="dev:N", y="task:N")
    h = max(220, 22 * len(batch))
    st.altair_chart((heat + marks).properties(height=h), width="stretch")
    st.caption("색이 진할수록 친화도 높음(흰칸=자격 미달). 초록 점=실제 배정된 셀.")


with tab3:
    st.subheader("특성기반 배정 — 헝가리안(쿤–먼크레스) vs 우선순위 그리디")
    st.caption("친화도 = 스킬게이트 + 레벨/난이도 + 프로젝트 친숙도 + 잔여용량. "
               f"희소 스킬: {', '.join(A.SCARCE_SKILLS)} (각 3명만 보유)")

    mode = st.radio("보기", ["희소 스킬 반례 데모", "스프린트 단위 배정"], horizontal=True)
    order_ids = A.module1_order(tasks, projects, sprints)   # Module 1 → Module 2 연동

    if mode == "희소 스킬 반례 데모":
        batch, pool, desc = A.build_scarce_demo(alloc, tasks)
        g = alloc.allocate_greedy(batch, pool)
        h = alloc.allocate_hungarian(batch, pool)
        st.info(desc + f"  \n**개발자 풀({len(pool)}명):** {', '.join(pool)}")
        metrics_block(g, h)
        if g.unstaffed and not h.unstaffed:
            st.error("그리디가 남긴 미배정: "
                     + ", ".join(f"`{t}`" for t in g.unstaffed)
                     + " — 희소 인력을 평범한 태스크에 써버린 결과. 헝가리안은 전부 배정.")
        st.dataframe(assignment_table(batch, g, h), width="stretch", hide_index=True)
        st.subheader("친화도 히트맵 (헝가리안 배정 강조)")
        affinity_heatmap(batch, pool, h)
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**그리디 배정**")
            st.graphviz_chart(bipartite_dot(batch, g, C_GREEDY), width="stretch")
        with cc2:
            st.markdown("**헝가리안 배정**")
            st.graphviz_chart(bipartite_dot(batch, h, C_HUNG), width="stretch")

    else:
        sprint_ids = [s["id"] for s in sprints]
        sc1, sc2 = st.columns(2)
        sprint_id = sc1.selectbox("스프린트", sprint_ids, index=sprint_ids.index("P2-S1")
                                  if "P2-S1" in sprint_ids else 0)
        pool_size = sc2.slider("개발자 풀 크기", 5, len(developers), min(30, len(developers)), 1)
        s_tasks = [task_by_id[t["id"]] for t in tasks if t.get("sprint") == sprint_id]
        s_tasks = A.order_tasks(s_tasks, order_ids)
        pool = alloc.dev_ids[:pool_size]
        if not s_tasks:
            st.warning("이 스프린트에는 태스크가 없습니다.")
        else:
            g = alloc.allocate_greedy(s_tasks, pool)
            h = alloc.allocate_hungarian(s_tasks, pool)
            st.markdown(f"**{sprint_id}** · 태스크 {len(s_tasks)}개 · 개발자 풀 {len(pool)}명 "
                        f"· 희소 태스크 {h.scarce_total}개")
            metrics_block(g, h)
            st.dataframe(assignment_table(s_tasks, g, h),
                         width="stretch", hide_index=True, height=420)
            st.subheader("친화도 히트맵 (헝가리안 배정 강조)")
            affinity_heatmap(s_tasks, pool, h)

# ════════════════════════════════════════════════════════════════════
#  TAB 4 — 스프린트 플래너 (0/1 배낭 DP · 백트래킹 · 그리디)
# ════════════════════════════════════════════════════════════════════
with tab_planner:
    st.subheader("Module 3 · 스프린트에 담을 일을 고르는 플래너")
    st.caption("스프린트 용량은 가방 크기, 태스크 estimate는 필요한 공간, value는 얻는 가치입니다. "
               "같은 용량 안에서 더 가치 있는 조합을 찾는 과정을 보여줍니다.")

    mode_m3 = st.sidebar.radio("플래너 보기 모드", ["단일 스프린트 배낭 시연 (P3-S4)", "글로벌 의존성 인지 플래닝 & 배정 연동"], horizontal=False)

    if mode_m3 == "단일 스프린트 배낭 시연 (P3-S4)":
        st.markdown("#### 작은 예제로 보기: 용량 10짜리 스프린트")
        st.info("세 가지 일을 놓고 비교합니다. A는 하나만 해도 가치가 크지만 6pt를 차지하고, "
                "B와 C는 각각 5pt라서 둘을 같이 담으면 용량 10을 정확히 채웁니다.")

        demo_tasks = [
            {"id": "T0151", "estimate": 6, "value": 60, "title": "Knapsack Item A (T0151)"},
            {"id": "T0152", "estimate": 5, "value": 40, "title": "Knapsack Item B (T0152)"},
            {"id": "T0153", "estimate": 5, "value": 40, "title": "Knapsack Item C (T0153)"}
        ]
        demo_planner = P.SprintPlanner(demo_tasks)

        t1_start = dt.datetime.now()
        g_sel, g_est, g_val = demo_planner.plan_greedy(demo_tasks, 10)
        t1_elapsed = (dt.datetime.now() - t1_start).total_seconds() * 1000.0

        t2_start = dt.datetime.now()
        dp_sel, dp_est, dp_val = demo_planner.plan_dp(demo_tasks, 10)
        t2_elapsed = (dt.datetime.now() - t2_start).total_seconds() * 1000.0

        t3_start = dt.datetime.now()
        bt_sel, bt_est, bt_val = demo_planner.plan_backtracking(demo_tasks, 10)
        t3_elapsed = (dt.datetime.now() - t3_start).total_seconds() * 1000.0

        task_intro = pd.DataFrame([
            {
                "태스크": t["title"].replace("Knapsack Item ", "").replace(" (", "\n("),
                "필요 용량": t["estimate"],
                "얻는 가치": t["value"],
                "1pt당 가치": round(t["value"] / t["estimate"], 2),
            }
            for t in demo_tasks
        ])
        st.write("##### 후보 태스크")
        st.dataframe(task_intro, hide_index=True, width="stretch")

        c1, c2, c3 = st.columns(3)
        c1.metric("Greedy가 얻은 가치", f"{g_val} pts", help=f"선택: {', '.join(g_sel)} / 사용 용량: {g_est}pt")
        c2.metric("DP가 얻은 가치", f"{dp_val} pts", delta=int(dp_val - g_val), help=f"선택: {', '.join(dp_sel)} / 사용 용량: {dp_est}pt")
        c3.metric("Backtracking 결과", f"{bt_val} pts", delta=int(bt_val - g_val), help=f"선택: {', '.join(bt_sel)} / 사용 용량: {bt_est}pt")

        demo_df = pd.DataFrame([
            {"방법": "Greedy", "쉽게 말하면": "1pt당 가치가 높은 것부터 담기", "담은 태스크": ", ".join(g_sel), "사용 용량": g_est, "남은 용량": 10 - g_est, "얻은 가치": g_val, "시간(ms)": round(t1_elapsed, 4)},
            {"방법": "DP", "쉽게 말하면": "가능한 조합을 표로 쌓아 최선 찾기", "담은 태스크": ", ".join(dp_sel), "사용 용량": dp_est, "남은 용량": 10 - dp_est, "얻은 가치": dp_val, "시간(ms)": round(t2_elapsed, 4)},
            {"방법": "Backtracking", "쉽게 말하면": "담기/안 담기를 탐색하며 최선 찾기", "담은 태스크": ", ".join(bt_sel), "사용 용량": bt_est, "남은 용량": 10 - bt_est, "얻은 가치": bt_val, "시간(ms)": round(t3_elapsed, 4)}
        ])
        st.write("##### 결과 비교")
        st.dataframe(demo_df, hide_index=True, width="stretch")

        capacity_rows = []
        for method, used, value in [("Greedy", g_est, g_val), ("DP", dp_est, dp_val), ("Backtracking", bt_est, bt_val)]:
            capacity_rows.append({"방법": method, "구분": "사용한 용량", "용량": used, "얻은 가치": value})
            capacity_rows.append({"방법": method, "구분": "남은 용량", "용량": 10 - used, "얻은 가치": value})
        cdf = pd.DataFrame(capacity_rows)

        capacity_chart = alt.Chart(cdf).mark_bar(size=34).encode(
            x=alt.X("용량:Q", stack="zero", title="스프린트 용량 10pt"),
            y=alt.Y("방법:N", sort=["Greedy", "DP", "Backtracking"], title=None),
            color=alt.Color("구분:N", scale=alt.Scale(domain=["사용한 용량", "남은 용량"], range=["#4c78a8", "#d7dee8"]), legend=alt.Legend(title=None)),
            tooltip=["방법", "구분", "용량", "얻은 가치"],
        )
        value_chart = alt.Chart(demo_df).mark_bar(size=34).encode(
            x=alt.X("얻은 가치:Q", title="비즈니스 가치"),
            y=alt.Y("방법:N", sort=["Greedy", "DP", "Backtracking"], title=None),
            color=alt.Color("방법:N", scale=alt.Scale(domain=["Greedy", "DP", "Backtracking"], range=["#b8860b", "#2e7d32", "#2e7d32"]), legend=None),
            tooltip=["방법", "담은 태스크", "사용 용량", "얻은 가치"],
        )
        st.write("##### 한눈에 읽기")
        vc1, vc2 = st.columns(2)
        with vc1:
            st.altair_chart(capacity_chart.properties(height=170, title="용량을 얼마나 채웠나"), width="stretch")
        with vc2:
            st.altair_chart(value_chart.properties(height=170, title="그래서 가치를 얼마나 얻었나"), width="stretch")

        choice_rows = []
        for method, selected in [("Greedy", g_sel), ("DP", dp_sel), ("Backtracking", bt_sel)]:
            for t in demo_tasks:
                label = t["title"].split()[2]
                choice_rows.append({
                    "방법": method,
                    "태스크": f"{label} ({t['estimate']}pt / {t['value']}가치)",
                    "선택": "담음" if t["id"] in selected else "안 담음",
                })
        choice_chart = alt.Chart(pd.DataFrame(choice_rows)).mark_rect(stroke="white").encode(
            x=alt.X("태스크:N", title=None),
            y=alt.Y("방법:N", sort=["Greedy", "DP", "Backtracking"], title=None),
            color=alt.Color("선택:N", scale=alt.Scale(domain=["담음", "안 담음"], range=["#2e7d32", "#cfd8e3"]), legend=alt.Legend(title=None)),
            tooltip=["방법", "태스크", "선택"],
        )
        choice_text = alt.Chart(pd.DataFrame(choice_rows)).mark_text(fontWeight="bold").encode(
            x=alt.X("태스크:N", title=None),
            y=alt.Y("방법:N", sort=["Greedy", "DP", "Backtracking"], title=None),
            text=alt.Text("선택:N"),
            color=alt.condition(alt.datum["선택"] == "담음", alt.value("white"), alt.value("#2b3440")),
        )
        st.altair_chart((choice_chart + choice_text).properties(height=150, title="각 방법이 실제로 담은 태스크"), width="stretch")
        st.success("결론: Greedy는 A 하나를 먼저 담아 60가치에서 멈추지만, DP와 Backtracking은 B+C 조합을 찾아 80가치를 얻습니다.")

    else:
        st.markdown("#### 전체 프로젝트에 적용해 보기")
        st.caption("앞선 작은 예제를 모든 스프린트에 반복 적용합니다. 단, 선행 태스크가 끝나야 다음 태스크를 후보로 넣고, "
                   "이번 스프린트에 못 담은 일은 다음 스프린트 후보로 넘깁니다.")

        plan_method = st.selectbox("플래너 알고리즘 선택", ["DP", "Backtracking", "Greedy"])
        
        m3_planner = P.SprintPlanner(tasks, sprints, projects)
        g_plan = m3_planner.plan_global(method=plan_method.lower())
        sprint_caps = {s["id"]: int(s.get("capacity", 0)) for s in sprints}
        sprint_projs = {s["id"]: s.get("project") for s in sprints}

        g1, g2, g3, g4 = st.columns(4)
        g1.metric("선택한 일의 총 가치", f"{g_plan.total_value} pts")
        g2.metric("사용한 총 용량", f"{g_plan.total_capacity_used} pts")
        g3.metric("다음으로 넘긴 횟수", f"{g_plan.carried_forward_total}건")
        g4.metric("끝까지 못 넣은 일", f"{len(g_plan.unplanned_tasks)}개")

        st.write("##### 알고리즘별 성적")
        full_cmp = []
        for m_name in ["greedy", "dp", "backtracking"]:
            r = m3_planner.plan_global(method=m_name)
            full_cmp.append({
                "알고리즘": m_name.upper(),
                "얻은 가치": r.total_value,
                "사용 용량": r.total_capacity_used,
                "1pt당 가치": round(r.total_value / r.total_capacity_used, 2) if r.total_capacity_used else 0,
                "다음으로 넘긴 횟수": r.carried_forward_total,
                "끝까지 못 넣은 일": len(r.unplanned_tasks),
                "현재 선택": "선택됨" if m_name == plan_method.lower() else ""
            })
        cmp_df = pd.DataFrame(full_cmp)
        cmp_chart = alt.Chart(cmp_df).mark_bar(size=38).encode(
            x=alt.X("얻은 가치:Q", title="총 비즈니스 가치"),
            y=alt.Y("알고리즘:N", sort="-x", title=None),
            color=alt.condition(alt.datum["현재 선택"] == "선택됨", alt.value("#2e7d32"), alt.value("#7f8fa6")),
            tooltip=["알고리즘", "얻은 가치", "사용 용량", "1pt당 가치", "다음으로 넘긴 횟수", "끝까지 못 넣은 일"],
        )
        st.altair_chart(cmp_chart.properties(height=170), width="stretch")
        st.dataframe(cmp_df, hide_index=True, width="stretch")

        st.markdown("---")
        st.markdown("#### 스프린트별로 무엇이 일어났나")

        sp_rows = []
        for sp_id, plan in sorted(g_plan.sprint_plans.items()):
            sp_proj = sprint_projs.get(sp_id, sp_id.split("-")[0])
            cap = sprint_caps.get(sp_id, 0)
            sp_rows.append({
                "스프린트": sp_id,
                "프로젝트": sp_proj,
                "용량": cap,
                "사용": plan.used_capacity,
                "남음": max(cap - plan.used_capacity, 0),
                "사용률(%)": round(plan.used_capacity / cap * 100) if cap else 0,
                "담은 일": len(plan.selected_tasks),
                "다음으로 넘긴 일": len(plan.carried_tasks),
                "얻은 가치": plan.total_value,
                "시간(ms)": round(plan.elapsed_ms, 3)
            })
        sp_df = pd.DataFrame(sp_rows)

        usage_chart = alt.Chart(sp_df).mark_bar(size=18).encode(
            x=alt.X("사용률(%):Q", title="용량 사용률", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("스프린트:N", sort=list(sp_df["스프린트"]), title=None),
            color=alt.Color("얻은 가치:Q", scale=alt.Scale(scheme="tealblues"), legend=alt.Legend(title="가치")),
            tooltip=["스프린트", "프로젝트", "용량", "사용", "남음", "담은 일", "다음으로 넘긴 일", "얻은 가치"],
        )
        count_rows = []
        for row in sp_rows:
            count_rows.append({"스프린트": row["스프린트"], "구분": "담은 일", "개수": row["담은 일"]})
            count_rows.append({"스프린트": row["스프린트"], "구분": "다음으로 넘긴 일", "개수": row["다음으로 넘긴 일"]})
        count_chart = alt.Chart(pd.DataFrame(count_rows)).mark_bar(size=18).encode(
            x=alt.X("개수:Q", stack="zero", title="태스크 수"),
            y=alt.Y("스프린트:N", sort=list(sp_df["스프린트"]), title=None),
            color=alt.Color("구분:N", scale=alt.Scale(domain=["담은 일", "다음으로 넘긴 일"], range=["#2e7d32", "#d9912b"]), legend=alt.Legend(title=None)),
            tooltip=["스프린트", "구분", "개수"],
        )
        sc1, sc2 = st.columns(2)
        with sc1:
            st.altair_chart(usage_chart.properties(height=max(220, 24 * len(sp_df)), title="각 스프린트가 용량을 얼마나 썼는지"), width="stretch")
        with sc2:
            st.altair_chart(count_chart.properties(height=max(220, 24 * len(sp_df)), title="담은 일과 다음으로 넘긴 일"), width="stretch")
        st.dataframe(sp_df, hide_index=True, width="stretch")

        sel_sp = st.selectbox("스프린트 세부 조회", sorted(g_plan.sprint_plans.keys()))
        s_plan = g_plan.sprint_plans[sel_sp]
        
        st.write(f"##### {sel_sp} 자세히 보기")
        st.caption(f"이 스프린트는 {sprint_caps.get(sel_sp, 0)}pt 중 {s_plan.used_capacity}pt를 사용했고, "
                   f"{len(s_plan.selected_tasks)}개를 담고 {len(s_plan.carried_tasks)}개를 다음 후보로 넘겼습니다.")
        selected_tab, carried_tab = st.tabs(["이번에 담은 일", "다음으로 넘긴 일"])
        with selected_tab:
            if s_plan.selected_tasks:
                sel_tasks_data = [
                    {
                        "ID": tid, 
                        "필요 용량": task_by_id[tid]["estimate"], 
                        "가치": task_by_id[tid]["value"], 
                        "1pt당 가치": round(task_by_id[tid]["value"] / task_by_id[tid]["estimate"], 2) if task_by_id[tid]["estimate"] else 0,
                        "우선순위": task_by_id[tid].get("priority", 4),
                        "제목": task_by_id[tid]["title"]
                    } for tid in s_plan.selected_tasks
                ]
                st.dataframe(pd.DataFrame(sel_tasks_data), hide_index=True, width="stretch")
            else:
                st.write("선택된 태스크가 없습니다.")
        with carried_tab:
            if s_plan.carried_tasks:
                car_tasks_data = [
                    {
                        "ID": tid, 
                        "필요 용량": task_by_id[tid]["estimate"], 
                        "가치": task_by_id[tid]["value"], 
                        "1pt당 가치": round(task_by_id[tid]["value"] / task_by_id[tid]["estimate"], 2) if task_by_id[tid]["estimate"] else 0,
                        "우선순위": task_by_id[tid].get("priority", 4),
                        "제목": task_by_id[tid]["title"]
                    } for tid in s_plan.carried_tasks
                ]
                st.dataframe(pd.DataFrame(car_tasks_data), hide_index=True, width="stretch")
            else:
                st.write("이월된 태스크가 없습니다.")

        st.markdown("---")
        st.markdown("#### 고른 일을 실제 개발자에게 배정하면")
        st.caption("Module 3가 담기로 결정한 태스크만 Module 2 배정기에 넘겨서, 누가 맡을 수 있는지 확인합니다.")

        selected_global_tids = []
        for plan in g_plan.sprint_plans.values():
            selected_global_tids.extend(plan.selected_tasks)
        selected_tasks_subset = [task_by_id[tid] for tid in selected_global_tids]

        slack_v, crit_v, sprint_ord = A.schedule_view(selected_tasks_subset, projects, sprints)
        sh_m3 = alloc.allocate_schedule(selected_tasks_subset, slack_v, crit_v, sprint_ord, method="hungarian")
        sg_m3 = alloc.allocate_schedule(selected_tasks_subset, slack_v, crit_v, sprint_ord, method="greedy")

        st.write(f"**배정 대상 태스크 수:** {len(selected_tasks_subset)}개 (전체 153개 중 용량 내 선별 건)")
        
        m1, m2, m3 = st.columns(3)
        staffed_h_m3 = len(sh_m3.assignments) - len(sh_m3.unstaffed)
        staffed_g_m3 = len(sg_m3.assignments) - len(sg_m3.unstaffed)
        m1.metric("개발자-태스크 적합도", sh_m3.total_score, delta=int(sh_m3.total_score - sg_m3.total_score))
        m2.metric("사람이 배정된 일", f"{staffed_h_m3} / {len(selected_tasks_subset)}", delta=int(staffed_h_m3 - staffed_g_m3))
        m3.metric("아직 담당자 없는 일", len(sh_m3.unstaffed), delta=int(len(sh_m3.unstaffed) - len(sg_m3.unstaffed)), delta_color="inverse")

        st.write("##### 개발자별 맡은 양")
        wrows_m3 = []
        for d, ts in sh_m3.by_dev.items():
            dev = alloc.devs[d]
            cap = sh_m3.dev_cap.get(d, 0)
            load = sh_m3.dev_load.get(d, 0)
            wrows_m3.append({
                "dev": d, "level": dev.get("level", 1), "tasks": len(ts),
                "load": load, "avail": cap,
                "util%": round(load / cap * 100) if cap > 0 else 0,
            })
        wdf_m3 = pd.DataFrame(wrows_m3).sort_values("load", ascending=False).reset_index(drop=True)
        
        bar_m3 = alt.Chart(wdf_m3).mark_bar().encode(
            y=alt.Y("dev:N", sort="-x", title=None),
            x=alt.X("load:Q", title="맡은 작업량(pts)"),
            color=alt.Color("util%:Q", scale=alt.Scale(scheme="greenblue", domain=[0, 100]), legend=alt.Legend(title="가동률")),
            tooltip=["dev", "level", "tasks", "load", "avail", "util%"],
        )
        cap_tick_m3 = alt.Chart(wdf_m3).mark_tick(color="#c62828", thickness=2, size=18).encode(
            y=alt.Y("dev:N", sort="-x", title=None),
            x=alt.X("avail:Q", title="맡은 작업량(pts)"),
            tooltip=["dev", "avail"],
        )
        st.altair_chart((bar_m3 + cap_tick_m3).properties(height=max(220, 16 * len(wdf_m3))), width="stretch")
        st.caption("막대는 실제로 맡은 작업량, 빨간 눈금은 해당 개발자가 감당 가능한 용량입니다.")


# ════════════════════════════════════════════════════════════════════
#  TAB 5 — Module 4 · 백로그 검색·자동완성
#  ── KMP(정확검색) / 라빈-카프(다중키워드) / 트라이(자동완성) / 편집거리(퍼지)
# ════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def build_searcher(tasks_key: str):
    """BacklogSearcher 색인을 캐시한다 (태스크 데이터 변경 시 재빌드)."""
    t = SR.load_tasks(os.path.join(DATA_DIR, tasks_key))
    return SR.BacklogSearcher(t)

searcher_inst = build_searcher(tasks_filename)

with tab4:
    st.subheader("Module 4 · 백로그 검색·자동완성")
    st.caption(
        f"153개 태스크를 대상으로 4가지 검색 방식을 비교합니다. "
        f"역인덱스 단어 수: **{len(searcher_inst.inverted_index)}개**"
    )

    # ── 알고리즘 설명 expander ──
    with st.expander("📖 알고리즘 & 자료구조 설명", expanded=False):
        st.markdown("""
| 구분 | 알고리즘 / 자료구조 | 역할 | 시간복잡도 |
|---|---|---|---|
| **자료구조 ①** | **트라이 (Trie)** | 단어를 트리에 저장, 접두어 탐색 | 삽입/탐색 O(M) |
| **자료구조 ②** | **해시맵 (Dict)** | 역인덱스·라빈-카프 버킷·id 조회 | 평균 O(1) |
| **자료구조 ③** | **리스트 (Array)** | KMP π 테이블 저장 | O(M) 공간 |
| **알고리즘 ①** | **KMP** | 실패 함수로 텍스트 정확 탐색 | O(N+M) |
| **알고리즘 ②** | **라빈-카프** | 롤링 해시로 다중 키워드 탐색 | O(N+M) avg |
| **보조 ①** | **트라이 탐색** | 접두어 입력 → 자동완성 후보 제안 | O(M+결과수) |
| **보조 ②** | **편집거리 DP** | Levenshtein 거리로 오타 보정 | O(M×N) |
""")

    # ── 검색 모드 선택 ──
    search_mode = st.radio(
        "검색 모드",
        ["🔤 KMP — 정확 검색", "🔢 라빈-카프 — 다중 키워드",
         "💡 트라이 — 자동완성", "🔮 편집거리 — 오타 보정"],
        horizontal=True,
    )

    # ════════ KMP ════════
    if search_mode.startswith("🔤"):
        st.markdown("#### KMP — 실패 함수(π 배열) 기반 정확 부분 문자열 탐색")
        st.info("패턴을 한 번 읽어 실패 함수(π 배열)를 만들어두면, 불일치가 나도 처음으로 돌아가지 않고 "
                "최대한 앞으로 건너뜁니다. O(N+M) 보장.")
        kmp_q = st.text_input("검색 패턴", value="search", key="kmp_q",
                              placeholder="예: deploy, auth, scheduler ...")
        if kmp_q:
            results = searcher_inst.search_kmp(kmp_q)
            st.metric("KMP 검색 결과", f"{len(results)}건")
            if results:
                df_kmp = pd.DataFrame([{
                    "태스크ID": r.task_id,
                    "프로젝트": r.project,
                    "스프린트": r.sprint,
                    "매칭 필드": r.match_field,
                    "매칭 위치": str(r.match_positions[:5]),
                    "제목": r.title,
                    "태그": ", ".join(r.tags),
                } for r in results])
                st.dataframe(df_kmp, hide_index=True, width="stretch")

                # π 배열 시각화
                with st.expander("실패 함수(π 배열) 확인"):
                    pi = SR.BacklogSearcher._kmp_failure(kmp_q.lower())
                    pi_df = pd.DataFrame({
                        "인덱스": list(range(len(kmp_q))),
                        "문자": list(kmp_q.lower()),
                        "π[i]": pi,
                    })
                    st.dataframe(pi_df, hide_index=True)
                    st.caption("π[i] = 패턴 앞부분 중 접두사이자 접미사인 최장 문자열 길이. "
                               "불일치 시 이 값만큼 뒤로 돌아가 재탐색합니다.")
            else:
                st.warning("결과가 없습니다. 다른 키워드를 입력해보세요.")

    # ════════ 라빈-카프 ════════
    elif search_mode.startswith("🔢"):
        st.markdown("#### 라빈-카프 — 롤링 해시(Rolling Hash) 다중 키워드 탐색")
        st.info("각 키워드의 해시값을 미리 계산하고, 텍스트를 슬라이딩 윈도우로 이동하며 해시값을 비교합니다. "
                "해시가 일치할 때만 실제 문자 비교를 수행하여 평균 O(N+M).")
        rk_q = st.text_input("키워드 (공백 구분)", value="API auth", key="rk_q",
                             placeholder="예: API auth / backend scheduler / mobile export")
        if rk_q:
            results = searcher_inst.search_rabin_karp(rk_q)
            keywords = [k for k in rk_q.split() if k.strip()]
            st.metric("라빈-카프 검색 결과", f"{len(results)}건",
                      help=f"검색 키워드: {keywords}")
            if results:
                df_rk = pd.DataFrame([{
                    "태스크ID": r.task_id,
                    "프로젝트": r.project,
                    "스프린트": r.sprint,
                    "매칭 키워드": r.match_field.split("keyword=")[-1].rstrip("]") if "keyword=" in r.match_field else r.match_field,
                    "매칭 위치": str(r.match_positions[:5]),
                    "제목": r.title,
                    "태그": ", ".join(r.tags),
                } for r in results])

                # 키워드별 히트 수 차트
                kw_counts = {}
                for r in results:
                    kw = r.match_field.split("keyword=")[-1].rstrip("]")
                    kw_counts[kw] = kw_counts.get(kw, 0) + 1
                if kw_counts:
                    kw_df = pd.DataFrame(
                        [{"키워드": k, "매칭 태스크 수": v} for k, v in kw_counts.items()])
                    kw_chart = alt.Chart(kw_df).mark_bar(color=C_NORM).encode(
                        x=alt.X("키워드:N", title=None),
                        y=alt.Y("매칭 태스크 수:Q"),
                        tooltip=["키워드", "매칭 태스크 수"],
                    )
                    st.altair_chart(kw_chart.properties(height=160, title="키워드별 히트 수"),
                                    width="stretch")
                st.dataframe(df_rk, hide_index=True, width="stretch")
            else:
                st.warning("결과가 없습니다. 다른 키워드를 입력해보세요.")

    # ════════ 트라이 자동완성 ════════
    elif search_mode.startswith("💡"):
        st.markdown("#### 트라이(Trie) — 접두어 기반 자동완성")
        st.info("모든 태스크 제목·태그의 단어를 트라이(트리)에 삽입해두고, "
                "접두어를 루트에서 따라 내려가면 해당 접두어로 시작하는 모든 단어를 O(M+결과수)에 수집합니다.")
        auto_q = st.text_input("접두어 입력", value="sch", key="auto_q",
                               placeholder="예: sch / back / not / dep")
        top_k = st.slider("최대 후보 수", 3, 20, 8)
        if auto_q:
            results = searcher_inst.autocomplete(auto_q, top_k)
            st.metric("자동완성 후보", f"{len(results)}개")
            if results:
                auto_rows = []
                for word, tids in results:
                    titles = [searcher_inst.tasks_by_id[tid]["title"][:35]
                              for tid in tids[:3] if tid in searcher_inst.tasks_by_id]
                    auto_rows.append({
                        "완성 단어": word,
                        "연결 태스크 수": len(tids),
                        "태스크 ID (최대3)": ", ".join(tids[:3]),
                        "대표 태스크 제목": " / ".join(titles),
                    })
                st.dataframe(pd.DataFrame(auto_rows), hide_index=True, width="stretch")

                # 후보 단어 막대차트
                word_chart = alt.Chart(pd.DataFrame(auto_rows)).mark_bar(color="#5b7fa6").encode(
                    x=alt.X("연결 태스크 수:Q", title="연결된 태스크 수"),
                    y=alt.Y("완성 단어:N", sort="-x", title=None),
                    tooltip=["완성 단어", "연결 태스크 수"],
                )
                st.altair_chart(word_chart.properties(height=max(160, 30 * len(auto_rows)),
                                                       title=f"접두어 '{auto_q}'의 자동완성 후보"),
                                width="stretch")
            else:
                st.warning(f"'{auto_q}'로 시작하는 단어가 색인에 없습니다. 다른 접두어를 시도해보세요.")

    # ════════ 편집거리 퍼지 검색 ════════
    else:
        st.markdown("#### 편집거리(Levenshtein DP) — 오타 보정 퍼지 검색")
        st.info("두 문자열 간의 **삽입·삭제·교체** 최솟값을 2D DP로 계산합니다. "
                "임계값(threshold) 이하의 편집거리를 가진 태스크를 거리 오름차순으로 반환합니다.")
        c1, c2 = st.columns([3, 1])
        fuzzy_q = c1.text_input("검색어 (오타 허용)", value="dashbord", key="fuzzy_q",
                                placeholder="예: dashbord / schedular / authentification")
        threshold = c2.number_input("편집거리 임계값", min_value=1, max_value=5, value=2)
        if fuzzy_q:
            results = searcher_inst.fuzzy_search(fuzzy_q, threshold=int(threshold))
            st.metric("퍼지 검색 결과", f"{len(results)}건",
                      help=f"'{fuzzy_q}'와 편집거리 ≤ {threshold}인 태스크")
            if results:
                df_fz = pd.DataFrame([{
                    "태스크ID": r.task_id,
                    "프로젝트": r.project,
                    "스프린트": r.sprint,
                    "편집거리": r.edit_distance,
                    "제목": r.title,
                    "태그": ", ".join(r.tags),
                } for r in results])

                # 편집거리별 분포 차트
                dist_counts = {}
                for r in results:
                    dist_counts[r.edit_distance] = dist_counts.get(r.edit_distance, 0) + 1
                dist_df = pd.DataFrame([{"편집거리": k, "태스크 수": v}
                                        for k, v in sorted(dist_counts.items())])
                dist_chart = alt.Chart(dist_df).mark_bar(color=C_HUNG).encode(
                    x=alt.X("편집거리:O", title="편집거리"),
                    y=alt.Y("태스크 수:Q"),
                    tooltip=["편집거리", "태스크 수"],
                )
                st.altair_chart(dist_chart.properties(height=150,
                                                       title="편집거리별 결과 분포"),
                                width="stretch")
                st.dataframe(df_fz, hide_index=True, width="stretch")

                # DP 테이블 시각화 (첫 번째 결과 기준)
                with st.expander("DP 테이블 확인 (첫 번째 결과)"):
                    top_title = results[0].title.lower()
                    q_lower = fuzzy_q.lower()
                    # DP 테이블 재계산 (시각화용)
                    m2, n2 = len(q_lower), len(top_title[:20])
                    t_short = top_title[:20]
                    dp_table = [[0] * (n2 + 1) for _ in range(m2 + 1)]
                    for i in range(m2 + 1):
                        dp_table[i][0] = i
                    for j in range(n2 + 1):
                        dp_table[0][j] = j
                    for i in range(1, m2 + 1):
                        for j in range(1, n2 + 1):
                            if q_lower[i-1] == t_short[j-1]:
                                dp_table[i][j] = dp_table[i-1][j-1]
                            else:
                                dp_table[i][j] = 1 + min(
                                    dp_table[i-1][j], dp_table[i][j-1], dp_table[i-1][j-1])
                    cols = [""] + list(t_short)
                    rows_data = {"쿼리\\후보": [""] + list(q_lower)}
                    for j, c in enumerate(cols):
                        rows_data[c if c else "∅"] = [dp_table[i][j] for i in range(m2 + 1)]
                    st.dataframe(pd.DataFrame(rows_data), hide_index=True)
                    st.caption(f"쿼리: '{q_lower}' vs 후보: '{t_short}' "
                               f"(우하단 값={dp_table[m2][n2]} = 편집거리)")
            else:
                st.warning(f"임계값 {threshold} 이하의 유사 태스크가 없습니다. "
                           "임계값을 높이거나 다른 쿼리를 입력해보세요.")
    
# ════════════════════════════════════════════════════════════════════
#  [NEW] TAB 7 — Module 3 · 세부 일정 검색 (담당자/스프린트)
# ════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("🔎 전체 일정 상세 검색 (담당자 / 스프린트)")
    st.caption("Module 3(통합 플래너)가 확정한 전체 시간표를 바탕으로 누가 언제 어떤 일을 하는지 조회합니다.")
    
    with st.spinner("전체 일정 배정 및 시간표 생성 중..."):
        try:
            # 👉 [핵심 해결] 위에서 수정한 함수에 tasks, projects, sprints, developers 4개를 넘겨줍니다!
            schedule_df = get_integrated_schedule_data(DATA_DIR)
            
            # 방어 코드: 에러로 인해 데이터가 완전히 비었을 경우 빈 뼈대 생성
            if schedule_df.empty or '담당자' not in schedule_df.columns:
                schedule_df = pd.DataFrame(columns=["프로젝트", "스프린트", "태스크ID", "제목", "담당자", "상태", "공수(pts)", "가치"])
            
            # 상태에 따른 색상 함수
            def color_status(val):
                if val == '✅ 확정': return 'color: green'
                elif '⚠️' in val or '❌' in val: return 'color: red'
                return ''

            search_type = st.radio("검색 기준", ["👤 담당자(개발자)로 검색", "📅 스프린트로 검색"], horizontal=True)

            if "담당자" in search_type:
                # None을 제외한 개발자 목록 추출
                dev_list = sorted([d for d in schedule_df['담당자'].unique() if d != "None"])
                
                if not dev_list:
                    st.warning("현재 배정된 담당자가 없습니다.")
                else:
                    selected_dev = st.selectbox("🔍 검색할 담당자 선택", dev_list)

                    if selected_dev:
                        df_dev = schedule_df[schedule_df['담당자'] == selected_dev].copy()
                        
                        if df_dev.empty:
                            st.warning("이 담당자에게 배정된 태스크가 없습니다.")
                        else:
                            df_dev = df_dev.sort_values(by=['스프린트', '태스크ID']) # type: ignore
                            confirmed_pts = df_dev[df_dev['상태'] == '✅ 확정']['공수(pts)'].sum()
                            
                            st.metric("총 확정 공수", f"{confirmed_pts} pts", f"배정된 태스크 {len(df_dev)}개")
                            
                            try:
                                st.dataframe(df_dev[['스프린트', '태스크ID', '공수(pts)', '상태', '제목']].style.map(color_status, subset=['상태']), hide_index=True, use_container_width=True)
                            except AttributeError:
                                st.dataframe(df_dev[['스프린트', '태스크ID', '공수(pts)', '상태', '제목']].style.applymap(color_status, subset=['상태']), hide_index=True, use_container_width=True)

            else:
                # 스프린트 목록 추출
                sprint_list = sorted(schedule_df['스프린트'].unique())
                
                if not sprint_list:
                    st.warning("현재 배정된 스프린트 일정이 없습니다.")
                else:
                    selected_sprint = st.selectbox("🔍 검색할 스프린트 선택", sprint_list)

                    if selected_sprint:
                        df_sp = schedule_df[schedule_df['스프린트'] == selected_sprint].copy()
                        
                        if df_sp.empty:
                            st.warning("이 스프린트에 배정된 태스크가 없습니다.")
                        else:
                            df_sp = df_sp.sort_values(by=['상태', '담당자', '태스크ID'], ascending=[False, True, True]) # type: ignore
                            confirmed_pts = df_sp[df_sp['상태'] == '✅ 확정']['공수(pts)'].sum()
                            
                            st.metric("스프린트 소진 공수", f"{confirmed_pts} pts", f"시도된 태스크 {len(df_sp)}개")
                            
                            try:
                                st.dataframe(df_sp[['담당자', '태스크ID', '공수(pts)', '상태', '제목']].style.map(color_status, subset=['상태']), hide_index=True, use_container_width=True)
                            except AttributeError:
                                st.dataframe(df_sp[['담당자', '태스크ID', '공수(pts)', '상태', '제목']].style.applymap(color_status, subset=['상태']), hide_index=True, use_container_width=True)
                            
        except Exception as e:
            st.error("플래너 데이터를 불러오는 중 오류가 발생했습니다.")
            st.exception(e)

st.sidebar.markdown("---")
st.sidebar.caption("Module 1: 위상정렬 · Module 2: 헝가리안 · Module 3: 배낭DP · Module 4: KMP+트라이")

