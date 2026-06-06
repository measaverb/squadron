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
<<<<<<< HEAD
import planner as P            # Module 3 (표준 라이브러리만)
=======
>>>>>>> 0e670f4d13acf5e78fc45abda606f1c1b0f221b6

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


def build_scheduler(tasks, projects, sprints) -> S.Scheduler:
    return S.Scheduler(tasks, projects, sprints)


# ──────────────────────────── 사이드바 ────────────────────────────
st.sidebar.title("🛰️ Squadron")
st.sidebar.caption("조직 단위 엔지니어링 리소스 매니저")
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

<<<<<<< HEAD
tab1, tab2, tab_alloc, tab_planner, tab3 = st.tabs([
    "📅 Module 1 · 스케줄/임계경로",
    "🔁 Module 1 · 사이클 검출",
    "🗺️ Module 1→2 · 전체 일정 배정",
    "📦 Module 3 · 스프린트 플래너",
=======
tab1, tab2, tab_alloc, tab3 = st.tabs([
    "📅 Module 1 · 스케줄/임계경로",
    "🔁 Module 1 · 사이클 검출",
    "🗺️ Module 1→2 · 전체 일정 배정",
>>>>>>> 0e670f4d13acf5e78fc45abda606f1c1b0f221b6
    "👥 Module 2 · 배정 (헝가리안 vs 그리디)",
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

<<<<<<< HEAD
# ════════════════════════════════════════════════════════════════════
#  TAB 4 — 스프린트 플래너 (0/1 배낭 DP · 백트래킹 · 그리디)
# ════════════════════════════════════════════════════════════════════
with tab_planner:
    st.subheader("스프린트 플래너 — 제한된 용량 내 비즈니스 가치 극대화 (Module 3)")
    st.caption("Module 3 에서는 각 스프린트의 용량(Capacity) 한도 내에서 "
               "비즈니스 가치(Value)의 합을 최대화하는 태스크를 선택합니다. "
               "DP(동적계획법), 백트래킹, 가치밀도 그리디 세 가지 알고리즘으로 최적화를 수행합니다.")

    mode_m3 = st.sidebar.radio("플래너 보기 모드", ["단일 스프린트 배낭 시연 (P3-S4)", "글로벌 의존성 인지 플래닝 & 배정 연동"], horizontal=False)

    if mode_m3 == "단일 스프린트 배낭 시연 (P3-S4)":
        st.markdown("#### README.md 배낭 반례 검증 데모")
        st.info("스프린트 `P3-S4` 용량은 **10**이며, 포함된 태스크 A(6,60), B(5,40), C(5,40)를 대상으로 "
                "가치 밀도 기준 그리디와 동적계획법(DP)/백트래킹의 결과를 대조합니다.")

        # 데모 데이터 및 플래너 실행
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

        # 카드 메트릭으로 요약
        c1, c2, c3 = st.columns(3)
        c1.metric("가치밀도 그리디", f"{g_val} pts", help=f"선택: {g_sel} (소진용량: {g_est})")
        c2.metric("0/1 배낭 DP (최적)", f"{dp_val} pts", delta=int(dp_val - g_val), help=f"선택: {dp_sel} (소진용량: {dp_est})")
        c3.metric("백트래킹 탐색 (최적)", f"{bt_val} pts", delta=int(bt_val - g_val), help=f"선택: {bt_sel} (소진용량: {bt_est})")

        # 비교 표 시각화
        demo_df = pd.DataFrame([
            {"알고리즘": "Greedy", "선택된 태스크": ", ".join(g_sel), "소진 용량": g_est, "총 가치": g_val, "수행시간(ms)": round(t1_elapsed, 4)},
            {"알고리즘": "DP (Optimal)", "선택된 태스크": ", ".join(dp_sel), "소진 용량": dp_est, "총 가치": dp_val, "수행시간(ms)": round(t2_elapsed, 4)},
            {"알고리즘": "Backtracking (Optimal)", "선택된 태스크": ", ".join(bt_sel), "소진 용량": bt_est, "총 가치": bt_val, "수행시간(ms)": round(t3_elapsed, 4)}
        ])
        st.table(demo_df)

        # 바 차트 시각화
        bar_data = []
        for t in demo_tasks:
            bar_data.append({"태스크": t["title"], "estimate": t["estimate"], "value": t["value"], 
                             "Greedy 선택": t["id"] in g_sel, "Optimal 선택": t["id"] in dp_sel})
        bdf = pd.DataFrame(bar_data)

        st.write("##### 태스크 속성 및 선택 여부 비교")
        b1 = alt.Chart(bdf).mark_bar().encode(
            x=alt.X("value:Q", title="비즈니스 가치"),
            y=alt.Y("태스크:N", title=None),
            color=alt.condition(alt.datum["Optimal 선택"], alt.value("#2e7d32"), alt.value("#c62828"))
        ).properties(title="Optimal(DP/백트래킹) 선택 태스크 (초록=선택, 빨강=미선택)", height=150)
        
        b2 = alt.Chart(bdf).mark_bar().encode(
            x=alt.X("value:Q", title="비즈니스 가치"),
            y=alt.Y("태스크:N", title=None),
            color=alt.condition(alt.datum["Greedy 선택"], alt.value("#b8860b"), alt.value("#c62828"))
        ).properties(title="Greedy 선택 태스크 (황토=선택, 빨강=미선택)", height=150)

        st.altair_chart(b1 & b2, width="stretch")

    else:
        st.markdown("#### 글로벌 의존성 인지 플래닝 및 Carry Forward")
        st.caption("DAG 의존성을 만족하는 태스크들만 스프린트 후보군으로 구성하며, "
                   "용량이 모자라 계획에 포함되지 못한 태스크들은 다음 스프린트로 이월(Carry-Forward)됩니다.")

        plan_method = st.selectbox("플래너 알고리즘 선택", ["DP", "Backtracking", "Greedy"])
        
        # 글로벌 플래닝 실행
        m3_planner = P.SprintPlanner(tasks, sprints, projects)
        g_plan = m3_planner.plan_global(method=plan_method.lower())

        # 요약 메트릭
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("총 비즈니스 가치", f"{g_plan.total_value} pts")
        g2.metric("총 소진 용량", f"{g_plan.total_capacity_used} pts")
        g3.metric("누적 이월(Carry-forward) 수", f"{g_plan.carried_forward_total}건")
        g4.metric("최종 미계획 백로그", f"{len(g_plan.unplanned_tasks)}개")

        # 비교군 설명 추가
        st.write("##### 방식별 글로벌 플랜 성적 대조")
        full_cmp = []
        for m_name in ["greedy", "dp", "backtracking"]:
            r = m3_planner.plan_global(method=m_name)
            full_cmp.append({
                "알고리즘": m_name.upper(),
                "총 비즈니스 가치": r.total_value,
                "총 소진 용량": r.total_capacity_used,
                "누적 이월 수": r.carried_forward_total,
                "최종 미계획 백로그": len(r.unplanned_tasks)
            })
        st.dataframe(pd.DataFrame(full_cmp), hide_index=True)

        st.markdown("---")
        st.markdown("#### 스프린트별 상세 실행 계획")

        # 스프린트별 결과 표
        sp_rows = []
        for sp_id, plan in sorted(g_plan.sprint_plans.items()):
            sp_proj = sprint_projs.get(sp_id, sp_id.split("-")[0])
            sp_rows.append({
                "스프린트": sp_id,
                "프로젝트": sp_proj,
                "스프린트 용량": sprint_caps.get(sp_id, 0),
                "실제 소진": plan.used_capacity,
                "선택된 태스크수": len(plan.selected_tasks),
                "이월된 태스크수": len(plan.carried_tasks),
                "가치합": plan.total_value,
                "수행시간(ms)": round(plan.elapsed_ms, 3)
            })
        
        st.dataframe(pd.DataFrame(sp_rows), hide_index=True, width="stretch")

        # 스프린트별 아코디언 상세
        sel_sp = st.selectbox("스프린트 세부 조회", sorted(g_plan.sprint_plans.keys()))
        s_plan = g_plan.sprint_plans[sel_sp]
        
        sa1, sa2 = st.columns(2)
        with sa1:
            st.markdown(f"**선택된 태스크 ({len(s_plan.selected_tasks)}개)**")
            if s_plan.selected_tasks:
                sel_tasks_data = [
                    {
                        "ID": tid, 
                        "estimate": task_by_id[tid]["estimate"], 
                        "value": task_by_id[tid]["value"], 
                        "우선순위": task_by_id[tid].get("priority", 4),
                        "제목": task_by_id[tid]["title"]
                    } for tid in s_plan.selected_tasks
                ]
                st.dataframe(pd.DataFrame(sel_tasks_data), hide_index=True)
            else:
                st.write("선택된 태스크가 없습니다.")
        with sa2:
            st.markdown(f"**이월(Carry forward)된 태스크 ({len(s_plan.carried_tasks)}개)**")
            if s_plan.carried_tasks:
                car_tasks_data = [
                    {
                        "ID": tid, 
                        "estimate": task_by_id[tid]["estimate"], 
                        "value": task_by_id[tid]["value"], 
                        "우선순위": task_by_id[tid].get("priority", 4),
                        "제목": task_by_id[tid]["title"]
                    } for tid in s_plan.carried_tasks
                ]
                st.dataframe(pd.DataFrame(car_tasks_data), hide_index=True)
            else:
                st.write("이월된 태스크가 없습니다.")

        st.markdown("---")
        st.markdown("#### Module 3 ↔ Module 2 유기적 배정 연동 결과")
        st.caption("스프린트 플래너가 용량 내로 가치 극대화한 **선택 태스크들만** 대상으로 Module 2 배정기를 실행합니다.")

        # 스프린트 플래너에서 선택된 태스크들 필터링
        selected_global_tids = []
        for plan in g_plan.sprint_plans.values():
            selected_global_tids.extend(plan.selected_tasks)
        selected_tasks_subset = [task_by_id[tid] for tid in selected_global_tids]

        # 배정기 실행
        slack_v, crit_v, sprint_ord = A.schedule_view(selected_tasks_subset, projects, sprints)
        sh_m3 = alloc.allocate_schedule(selected_tasks_subset, slack_v, crit_v, sprint_ord, method="hungarian")
        sg_m3 = alloc.allocate_schedule(selected_tasks_subset, slack_v, crit_v, sprint_ord, method="greedy")

        st.write(f"**배정 대상 태스크 수:** {len(selected_tasks_subset)}개 (전체 153개 중 용량 내 선별 건)")
        
        # 배정 결과 메트릭
        m1, m2, m3 = st.columns(3)
        staffed_h_m3 = len(sh_m3.assignments) - len(sh_m3.unstaffed)
        staffed_g_m3 = len(sg_m3.assignments) - len(sg_m3.unstaffed)
        m1.metric("총 배정 친화도 (헝가리안)", sh_m3.total_score, delta=int(sh_m3.total_score - sg_m3.total_score))
        m2.metric("배정 완료율", f"{staffed_h_m3} / {len(selected_tasks_subset)}", delta=int(staffed_h_m3 - staffed_g_m3))
        m3.metric("인력 미배정", len(sh_m3.unstaffed), delta=int(len(sh_m3.unstaffed) - len(sg_m3.unstaffed)), delta_color="inverse")

        # 개발자 워크로드 시각화
        st.write("##### 플래너 결과 연동 개발자 워크로드 분포")
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
            x=alt.X("load:Q", title="확정 부하(load, pts)"),
            color=alt.Color("util%:Q", scale=alt.Scale(scheme="greenblue", domain=[0, 100]), legend=alt.Legend(title="가동률%")),
            tooltip=["dev", "level", "tasks", "load", "avail", "util%"],
        )
        st.altair_chart(bar_m3.properties(height=max(200, 15 * len(wdf_m3))), width="stretch")

st.sidebar.markdown("---")
st.sidebar.caption("Module 1: 위상정렬 · Module 2: 헝가리안 · Module 3: 배낭DP")
=======
st.sidebar.markdown("---")
st.sidebar.caption("Module 1: 위상정렬+임계경로 · Module 2: 헝가리안+그리디")
>>>>>>> 0e670f4d13acf5e78fc45abda606f1c1b0f221b6
