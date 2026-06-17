"""
Data In Sport · Garmin Performance Dashboard — Home / overview.

Run with:
    cd ~/garmin-dashboard
    ./.venv/bin/streamlit run Home.py
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common
import theme

st.set_page_config(page_title="DIS · Performance", page_icon="⚡", layout="wide")
theme.inject()

# ---- Sidebar ----------------------------------------------------------------
st.sidebar.markdown("### ⚡ Data In Sport")
window = st.sidebar.selectbox("Time window", [7, 14, 30, 60, 90], index=2,
                              format_func=lambda d: f"Last {d} days")
end = date.today()
start = end - timedelta(days=window - 1)
st.sidebar.caption(f"{start.isoformat()} → {end.isoformat()}")
common.refresh_button()

# ---- Auth + load ------------------------------------------------------------
name = common.ensure_auth()
df = common.daily(start, end)
acts = common.activities(30)

theme.page_header("Performance Overview", f"Welcome back, {name.split()[0] if name else ''} · {start.isoformat()} → {end.isoformat()}", "⚡")


def latest(col):
    s = df[col].dropna()
    return s.iloc[-1] if not s.empty else None

def avg(col):
    s = df[col].dropna()
    return round(s.mean(), 1) if not s.empty else None

# ---- KPI row ----------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
theme.kpi(c1, "Resting HR", round(latest("resting_hr")) if latest("resting_hr") else None, " bpm")
theme.kpi(c2, "HRV (last night)", round(latest("hrv_avg")) if latest("hrv_avg") else None, " ms")
theme.kpi(c3, "Sleep (avg)", avg("sleep_hours"), " h")
theme.kpi(c4, "Steps (avg)", f"{int(avg('steps')):,}" if avg("steps") else None)
theme.kpi(c5, "Stress (avg)", avg("avg_stress"))

st.write("")

# ---- Charts -----------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("😴 Sleep stages")
    stage_cols = ["deep_hours", "light_hours", "rem_hours", "awake_hours"]
    if df[stage_cols].notna().any().any():
        sl = df.melt("date", stage_cols, "stage", "hours").dropna(subset=["hours"])
        sl["stage"] = sl["stage"].str.replace("_hours", "").str.title()
        st.plotly_chart(theme.style_fig(px.bar(sl, x="date", y="hours", color="stage")),
                        use_container_width=True)
    else:
        st.info("No sleep data in this window.")

    st.subheader("❤️ Resting heart rate")
    if df["resting_hr"].notna().any():
        st.plotly_chart(theme.style_fig(px.line(df, x="date", y="resting_hr", markers=True)),
                        use_container_width=True)
    else:
        st.info("No resting HR data in this window.")

with right:
    st.subheader("📈 HRV trend")
    if df["hrv_avg"].notna().any():
        st.plotly_chart(theme.style_fig(px.line(df, x="date", y="hrv_avg", markers=True)),
                        use_container_width=True)
    else:
        st.info("No HRV data in this window.")

    st.subheader("👟 Steps vs goal")
    if df["steps"].notna().any():
        fig = go.Figure()
        fig.add_bar(x=df["date"], y=df["steps"], name="Steps", marker_color=theme.COLORS["sky"])
        if df["step_goal"].notna().any():
            fig.add_scatter(x=df["date"], y=df["step_goal"], name="Goal", mode="lines",
                            line=dict(color=theme.COLORS["muted"], dash="dash"))
        st.plotly_chart(theme.style_fig(fig), use_container_width=True)
    else:
        st.info("No step data in this window.")

# ---- Body Battery / stress --------------------------------------------------
st.subheader("🔋 Body Battery & stress")
if df["bb_high"].notna().any() or df["avg_stress"].notna().any():
    fig = go.Figure()
    if df["bb_high"].notna().any():
        fig.add_scatter(x=df["date"], y=df["bb_high"], name="BB high", line=dict(color=theme.COLORS["cyan"]))
        fig.add_scatter(x=df["date"], y=df["bb_low"], name="BB low",
                        line=dict(color=theme.COLORS["orange"]), fill="tonexty")
    if df["avg_stress"].notna().any():
        fig.add_scatter(x=df["date"], y=df["avg_stress"], name="Avg stress", yaxis="y2",
                        line=dict(color=theme.COLORS["electric"], dash="dot"))
    fig = theme.style_fig(fig)
    fig.update_layout(yaxis2=dict(title="Stress", overlaying="y", side="right",
                                  gridcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No Body Battery / stress data in this window.")

st.caption("Data via unofficial Garmin Connect endpoints · cached 15 min · "
           "explore Running and more in the sidebar →")
