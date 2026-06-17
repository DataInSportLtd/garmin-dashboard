"""Sleep & recovery deep-dive — hypnogram, score factors, overnight physiology, HRV."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import common
import theme
from garmin_data import fmt_duration

st.set_page_config(page_title="DIS · Sleep & Recovery", page_icon="😴", layout="wide")
theme.inject()

st.sidebar.markdown("### 😴 Sleep & Recovery")
day = st.sidebar.date_input("Night of", value=date.today() - timedelta(days=1),
                            max_value=date.today())
common.refresh_button()
common.ensure_auth()

iso = day.isoformat()
theme.page_header("Sleep & Recovery", f"Night of {iso}", "😴")

d = common.sleep_detail(iso)
if not d:
    st.info(f"No sleep data recorded for the night of {iso}. Pick another date in the sidebar.")
    st.stop()

QUAL_COLOR = {"EXCELLENT": theme.COLORS["cyan"], "GOOD": theme.COLORS["sky"],
              "FAIR": theme.COLORS["orange"], "POOR": theme.COLORS["red"]}

# ---- KPIs -------------------------------------------------------------------
c1, c2, c3, c4, c5, c6 = st.columns(6)
theme.kpi(c1, "Sleep score", d["score"], f" · {(d['score_qualifier'] or '').title()}")
theme.kpi(c2, "Time asleep", fmt_duration(d["sleep_h"] * 3600))
theme.kpi(c3, "Deep", f"{d['deep_h']:.1f}", " h")
theme.kpi(c4, "REM", f"{d['rem_h']:.1f}", " h")
theme.kpi(c5, "Resting HR", d["resting_hr"], " bpm")
theme.kpi(c6, "Overnight HRV", round(d["overnight_hrv"]) if d["overnight_hrv"] else None,
          f" · {(d['hrv_status'] or '').title()}")

if d.get("feedback"):
    st.caption(f"💬 {d['feedback']}")

st.write("")

# ---- Hypnogram + stage breakdown -------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("🌙 Hypnogram")
    sdf = d["stages"]
    if not sdf.empty:
        # Staircase: two points per segment for a clean step line.
        xs, ys = [], []
        for r in sdf.itertuples():
            xs += [r.start, r.end]
            ys += [r.rank, r.rank]
        fig = go.Figure()
        fig.add_scatter(x=xs, y=ys, mode="lines", line=dict(color=theme.COLORS["cyan"], width=2),
                        fill="tozeroy", fillcolor="rgba(27,202,202,0.08)")
        fig = theme.style_fig(fig, height=300)
        fig.update_layout(yaxis=dict(tickmode="array", tickvals=[0, 1, 2, 3],
                                     ticktext=["Deep", "Light", "REM", "Awake"]),
                          xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No stage timeline.")

with right:
    st.subheader("🧬 Stage split")
    stage_h = {"Deep": d["deep_h"], "Light": d["light_h"], "REM": d["rem_h"], "Awake": d["awake_h"]}
    stage_h = {k: v for k, v in stage_h.items() if v}
    if stage_h:
        fig = px.pie(values=list(stage_h.values()), names=list(stage_h.keys()), hole=0.6,
                     color=list(stage_h.keys()),
                     color_discrete_map={"Deep": "#116dff", "Light": "#4eb7f5",
                                         "REM": "#9b59b6", "Awake": "#df3131"})
        fig = theme.style_fig(fig, height=300)
        st.plotly_chart(fig, use_container_width=True)

# ---- Score factor chips -----------------------------------------------------
st.subheader("📊 Sleep score factors")
quals = d.get("qualifiers", {})
labels = {"totalDuration": "Duration", "deepPercentage": "Deep %", "remPercentage": "REM %",
          "lightPercentage": "Light %", "restlessness": "Restlessness", "stress": "Stress",
          "awakeCount": "Awakenings"}
items = [(labels[k], quals[k]) for k in labels if k in quals]
cols = st.columns(len(items) or 1)
for col, (lbl, q) in zip(cols, items):
    color = QUAL_COLOR.get(q, theme.COLORS["muted"])
    col.markdown(
        f'<div class="kpi"><div class="label">{lbl}</div>'
        f'<div class="value" style="font-size:1.1rem;color:{color}">{(q or "").title()}</div></div>',
        unsafe_allow_html=True)

st.write("")

# ---- Overnight physiology ---------------------------------------------------
st.subheader("📉 Overnight physiology")
hr, stress, bb = d["hr_series"], d["stress_series"], d["bb_series"]
if not hr.empty or not stress.empty or not bb.empty:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=("Heart rate (bpm)", "Stress", "Body Battery"))
    if not hr.empty:
        fig.add_scatter(x=hr["time"], y=hr["value"], line=dict(color=theme.COLORS["orange"]),
                        name="HR", row=1, col=1)
    if not stress.empty:
        fig.add_scatter(x=stress["time"], y=stress["value"], line=dict(color=theme.COLORS["electric"]),
                        name="Stress", row=2, col=1)
    if not bb.empty:
        fig.add_scatter(x=bb["time"], y=bb["value"], line=dict(color=theme.COLORS["cyan"]),
                        fill="tozeroy", fillcolor="rgba(27,202,202,0.1)", name="Body Battery", row=3, col=1)
    fig.update_layout(height=520, showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(color=theme.COLORS["text"]),
                      margin=dict(t=30, b=0))
    fig.update_xaxes(gridcolor="rgba(78,183,245,0.08)")
    fig.update_yaxes(gridcolor="rgba(78,183,245,0.08)")
    st.plotly_chart(fig, use_container_width=True)
    rc1, rc2, rc3 = st.columns(3)
    theme.kpi(rc1, "Avg respiration", d["respiration"], " brpm")
    theme.kpi(rc2, "Body Battery change", f"+{d['bb_change']}" if (d['bb_change'] or 0) > 0 else d["bb_change"])
    theme.kpi(rc3, "Skin temp deviation", d["skin_temp_dev_c"], " °C")

st.write("")

# ---- HRV recovery -----------------------------------------------------------
st.subheader("💗 HRV & recovery")
hrv = common.hrv_detail(iso)
hcol, rcol = st.columns([2, 3])
base = hrv["baseline"]
summ = hrv["summary"]
with hcol:
    if base and summ.get("lastNightAvg"):
        # Range bar: balanced zone with last-night marker.
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[base.get("balancedUpper", 0) - base.get("balancedLow", 0)],
                             base=[base.get("balancedLow", 0)], y=["HRV"], orientation="h",
                             marker_color="rgba(27,202,202,0.25)", name="Balanced range",
                             hovertemplate="Balanced %{base}–%{x}<extra></extra>"))
        fig.add_scatter(x=[summ["lastNightAvg"]], y=["HRV"], mode="markers",
                        marker=dict(color=theme.COLORS["cyan"], size=18, symbol="diamond"),
                        name=f"Last night {summ['lastNightAvg']}ms")
        fig = theme.style_fig(fig, height=160)
        fig.update_layout(xaxis_title="ms", barmode="overlay")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Status: **{summ.get('status','').title()}** · weekly avg {summ.get('weeklyAvg')} ms · "
                   f"balanced {base.get('balancedLow')}–{base.get('balancedUpper')} ms")
    else:
        st.info("No HRV baseline yet.")
with rcol:
    if not hrv["readings"].empty:
        fig = px.line(hrv["readings"], x="time", y="value", markers=True)
        fig.update_traces(line_color=theme.COLORS["cyan"])
        fig = theme.style_fig(fig, height=220)
        fig.update_layout(yaxis_title="HRV (ms)", title="Overnight HRV readings")
        st.plotly_chart(fig, use_container_width=True)

# ---- Window trends ----------------------------------------------------------
st.subheader("📈 Recent trends")
n = st.select_slider("Window (days)", [7, 14, 30, 60, 90], value=30)
end = date.today()
trend = common.daily(end - timedelta(days=n - 1), end)
tleft, tright = st.columns(2)
with tleft:
    stage_cols = ["deep_hours", "light_hours", "rem_hours", "awake_hours"]
    if trend[stage_cols].notna().any().any():
        sl = trend.melt("date", stage_cols, "stage", "hours").dropna(subset=["hours"])
        sl["stage"] = sl["stage"].str.replace("_hours", "").str.title()
        fig = px.bar(sl, x="date", y="hours", color="stage",
                     color_discrete_map={"Deep": "#116dff", "Light": "#4eb7f5",
                                         "Rem": "#9b59b6", "Awake": "#df3131"})
        fig = theme.style_fig(fig, height=280)
        fig.update_layout(title="Sleep duration & stages")
        st.plotly_chart(fig, use_container_width=True)
with tright:
    if trend["hrv_avg"].notna().any() or trend["sleep_score"].notna().any():
        fig = go.Figure()
        if trend["sleep_score"].notna().any():
            fig.add_scatter(x=trend["date"], y=trend["sleep_score"], name="Sleep score",
                            line=dict(color=theme.COLORS["sky"]))
        if trend["hrv_avg"].notna().any():
            fig.add_scatter(x=trend["date"], y=trend["hrv_avg"], name="HRV", yaxis="y2",
                            line=dict(color=theme.COLORS["cyan"]))
        fig = theme.style_fig(fig, height=280)
        fig.update_layout(title="Sleep score & HRV",
                          yaxis2=dict(title="HRV", overlaying="y", side="right",
                                      gridcolor="rgba(0,0,0,0)"))
        st.plotly_chart(fig, use_container_width=True)
