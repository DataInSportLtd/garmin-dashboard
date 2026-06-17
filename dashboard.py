"""
Personal Garmin dashboard.

Run with:
    cd ~/garmin-dashboard
    ./.venv/bin/streamlit run dashboard.py
"""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from garmin_client import get_client
from garmin_data import fetch_daily, fetch_activities

st.set_page_config(page_title="Garmin Dashboard", page_icon="⌚", layout="wide")


@st.cache_resource
def client():
    return get_client()


@st.cache_data(ttl=900, show_spinner="Fetching from Garmin…")
def load_daily(start: date, end: date) -> pd.DataFrame:
    return fetch_daily(client(), start, end)


@st.cache_data(ttl=900, show_spinner="Fetching activities…")
def load_activities(limit: int) -> pd.DataFrame:
    return fetch_activities(client(), limit)


def metric(col, label, value, fmt="{:.0f}", suffix=""):
    """Render a metric, gracefully handling all-NaN columns."""
    if value is None or pd.isna(value):
        col.metric(label, "—")
    else:
        col.metric(label, fmt.format(value) + suffix)


# ---- Sidebar controls -------------------------------------------------------
st.sidebar.header("⌚ Garmin Dashboard")
window = st.sidebar.selectbox("Time window", [7, 14, 30, 60, 90], index=2,
                              format_func=lambda d: f"Last {d} days")
end = date.today()
start = end - timedelta(days=window - 1)
st.sidebar.caption(f"{start.isoformat()} → {end.isoformat()}")
if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

# ---- Load -------------------------------------------------------------------
try:
    name = client().get_full_name()
except Exception as e:
    st.error(
        "Could not authenticate with Garmin. Run a login first:\n\n"
        "```\ncd ~/garmin-dashboard\n./.venv/bin/python garmin_client.py\n```\n\n"
        f"Details: {e}"
    )
    st.stop()

df = load_daily(start, end)
acts = load_activities(30)

st.title(f"Hi {name.split()[0] if name else ''} — your Garmin overview")

# ---- Headline metrics (most recent non-NaN per column) ----------------------
def latest(col):
    s = df[col].dropna()
    return s.iloc[-1] if not s.empty else None

def avg(col):
    s = df[col].dropna()
    return s.mean() if not s.empty else None

c1, c2, c3, c4, c5 = st.columns(5)
metric(c1, "Resting HR (latest)", latest("resting_hr"), suffix=" bpm")
metric(c2, "HRV (latest)", latest("hrv_avg"), suffix=" ms")
metric(c3, "Sleep (avg)", avg("sleep_hours"), fmt="{:.1f}", suffix=" h")
metric(c4, "Steps (avg)", avg("steps"))
metric(c5, "Stress (avg)", avg("avg_stress"))

st.divider()

# ---- Charts -----------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("😴 Sleep stages")
    stage_cols = ["deep_hours", "light_hours", "rem_hours", "awake_hours"]
    if df[stage_cols].notna().any().any():
        sleep_long = df.melt("date", stage_cols, "stage", "hours").dropna(subset=["hours"])
        sleep_long["stage"] = sleep_long["stage"].str.replace("_hours", "").str.title()
        fig = px.bar(sleep_long, x="date", y="hours", color="stage",
                     color_discrete_map={"Deep": "#1f3a93", "Light": "#6699cc",
                                         "Rem": "#9b59b6", "Awake": "#e74c3c"})
        fig.update_layout(height=320, margin=dict(t=10, b=0), legend_title="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No sleep data in this window.")

    st.subheader("❤️ Resting heart rate")
    if df["resting_hr"].notna().any():
        fig = px.line(df, x="date", y="resting_hr", markers=True)
        fig.update_traces(line_color="#e74c3c")
        fig.update_layout(height=300, margin=dict(t=10, b=0), yaxis_title="bpm")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No resting HR data in this window.")

with right:
    st.subheader("📈 HRV trend")
    if df["hrv_avg"].notna().any():
        fig = px.line(df, x="date", y="hrv_avg", markers=True)
        fig.update_traces(line_color="#27ae60")
        fig.update_layout(height=320, margin=dict(t=10, b=0), yaxis_title="ms")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No HRV data (needs a compatible device worn overnight).")

    st.subheader("👟 Steps vs goal")
    if df["steps"].notna().any():
        fig = go.Figure()
        fig.add_bar(x=df["date"], y=df["steps"], name="Steps", marker_color="#3498db")
        if df["step_goal"].notna().any():
            fig.add_scatter(x=df["date"], y=df["step_goal"], name="Goal",
                            mode="lines", line=dict(color="#95a5a6", dash="dash"))
        fig.update_layout(height=300, margin=dict(t=10, b=0), legend_title="")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No step data in this window.")

# ---- Stress / Body Battery --------------------------------------------------
st.subheader("🔋 Body Battery & stress")
if df["bb_high"].notna().any() or df["avg_stress"].notna().any():
    fig = go.Figure()
    if df["bb_high"].notna().any():
        fig.add_scatter(x=df["date"], y=df["bb_high"], name="BB high",
                        line=dict(color="#2ecc71"))
        fig.add_scatter(x=df["date"], y=df["bb_low"], name="BB low",
                        line=dict(color="#e67e22"), fill="tonexty")
    if df["avg_stress"].notna().any():
        fig.add_scatter(x=df["date"], y=df["avg_stress"], name="Avg stress",
                        yaxis="y2", line=dict(color="#9b59b6", dash="dot"))
    fig.update_layout(height=320, margin=dict(t=10, b=0),
                      yaxis=dict(title="Body Battery"),
                      yaxis2=dict(title="Stress", overlaying="y", side="right"))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No Body Battery / stress data in this window.")

# ---- Activities -------------------------------------------------------------
st.subheader("🏃 Recent activities")
if not acts.empty:
    show = acts.copy()
    show["start"] = show["start"].dt.strftime("%Y-%m-%d %H:%M")
    show = show.round({"duration_min": 0, "distance_km": 2, "elev_gain_m": 0})
    st.dataframe(show, use_container_width=True, hide_index=True)
else:
    st.info("No recent activities found.")

# ---- Raw data ---------------------------------------------------------------
with st.expander("🔎 Raw daily data"):
    st.dataframe(df, use_container_width=True, hide_index=True)

st.caption("Data via unofficial Garmin Connect endpoints · cached 15 min · "
           "click Refresh to re-pull.")
