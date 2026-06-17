"""Longitudinal trends + full searchable, exportable session log."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import common
import db
import theme

st.set_page_config(page_title="DIS · Longitudinal & Logs", page_icon="📚", layout="wide")
theme.inject()

st.sidebar.markdown("### 📚 Longitudinal & Logs")
common.refresh_button()
common.ensure_auth()

theme.page_header("Longitudinal & Session Logs", "Long-range trends · full activity history", "📚")

tab_trends, tab_log = st.tabs(["📈 Longitudinal trends", "📋 Session log"])

# =============================================================================
# Longitudinal trends
# =============================================================================
with tab_trends:
    window = st.select_slider(
        "Window (days)", [30, 60, 90, 180, 365], value=90,
        help="Larger windows take longer to load the first time (then cached 30 min).")
    n, dmin, dmax = db.cache_stats()
    cap = st.columns([4, 1])
    cap[0].caption(
        f"🗄️ Local cache: {n} days stored ({dmin}–{dmax})." if n else
        "🗄️ Local cache empty — first load will populate it.")
    if cap[1].button("Clear cache"):
        db.clear_cache(); st.cache_data.clear(); st.rerun()
    if window >= 180:
        st.caption("⏳ Long window — first load pulls uncached days from Garmin; cached days are instant.")
    end = date.today()
    start = end - timedelta(days=window - 1)

    df = common.daily(start, end)
    steps = common.daily_steps(start, end)
    roll = st.checkbox("Show 7-day rolling average", value=True)

    def trend(col, title, color, unit=""):
        s = df[["date", col]].dropna()
        if s.empty:
            st.info(f"No {title.lower()} data in this window.")
            return
        fig = go.Figure()
        fig.add_scatter(x=s["date"], y=s[col], mode="lines", name=title,
                        line=dict(color=color, width=1), opacity=0.45 if roll else 1)
        if roll and len(s) >= 7:
            fig.add_scatter(x=s["date"], y=s[col].rolling(7, min_periods=1).mean(),
                            mode="lines", name="7-day avg", line=dict(color=color, width=3))
        fig = theme.style_fig(fig, height=240)
        fig.update_layout(title=title, yaxis_title=unit, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Summary KPIs (window averages + deltas vs first half)
    def half_delta(col):
        s = df[col].dropna()
        if len(s) < 4:
            return None, None
        mid = len(s) // 2
        first, second = s.iloc[:mid].mean(), s.iloc[mid:].mean()
        return round(second, 1), round(second - first, 1)

    k = st.columns(5)
    for col, (label, unit, ccol) in {
        "resting_hr": ("Resting HR", "bpm", 0),
        "hrv_avg": ("HRV", "ms", 1),
        "sleep_hours": ("Sleep", "h", 2),
        "avg_stress": ("Stress", "", 3),
        "steps": ("Steps", "", 4),
    }.items():
        val, delta = half_delta(col)
        dstr = (f"{'+' if delta and delta > 0 else ''}{delta}" if delta is not None else "")
        theme.kpi(k[ccol], label, val if val is not None else None, f" {unit}".rstrip(), dstr)

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        trend("resting_hr", "Resting heart rate", theme.COLORS["red"], "bpm")
        trend("sleep_hours", "Sleep duration", theme.COLORS["sky"], "h")
        trend("avg_stress", "Average stress", theme.COLORS["electric"])
    with c2:
        trend("hrv_avg", "HRV", theme.COLORS["cyan"], "ms")
        # Steps from the bulk endpoint (more complete than per-day stats).
        if not steps.empty and steps["totalSteps"].notna().any():
            fig = go.Figure()
            fig.add_bar(x=steps["date"], y=steps["totalSteps"], name="Steps",
                        marker_color=theme.COLORS["steel"])
            if roll and len(steps) >= 7:
                fig.add_scatter(x=steps["date"],
                                y=steps["totalSteps"].rolling(7, min_periods=1).mean(),
                                name="7-day avg", line=dict(color=theme.COLORS["cyan"], width=3))
            fig = theme.style_fig(fig, height=240)
            fig.update_layout(title="Daily steps", showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        trend("max_hr", "Max heart rate", theme.COLORS["orange"], "bpm")

    with st.expander("⬇️ Export daily data (CSV)"):
        st.download_button("Download daily metrics CSV", df.to_csv(index=False),
                           file_name=f"garmin_daily_{start}_{end}.csv", mime="text/csv")
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)

# =============================================================================
# Session log
# =============================================================================
with tab_log:
    acts = common.activities(200)
    if acts.empty:
        st.info("No activities found.")
        st.stop()

    acts = acts.copy()
    acts["start"] = pd.to_datetime(acts["start"], errors="coerce")

    f1, f2, f3 = st.columns([2, 2, 3])
    types = sorted(acts["type"].dropna().unique())
    pick_types = f1.multiselect("Activity type", types, default=types)
    days_back = f2.selectbox("Period", [30, 90, 180, 365, 100000],
                             format_func=lambda d: "All time" if d > 9999 else f"Last {d} days")
    search = f3.text_input("Search name", "")

    cutoff = pd.Timestamp(date.today() - timedelta(days=days_back))
    view = acts[acts["type"].isin(pick_types) & (acts["start"] >= cutoff)]
    if search:
        view = view[view["name"].fillna("").str.contains(search, case=False)]

    # Summary
    s1, s2, s3, s4 = st.columns(4)
    theme.kpi(s1, "Activities", len(view))
    theme.kpi(s2, "Total distance", f"{view['distance_km'].fillna(0).sum():.1f}", " km")
    theme.kpi(s3, "Total time", f"{view['duration_min'].fillna(0).sum()/60:.1f}", " h")
    theme.kpi(s4, "Total load", round(view["training_load"].fillna(0).sum())
              if "training_load" in view else None)

    st.write("")
    show = view.copy()
    show["When"] = show["start"].dt.strftime("%Y-%m-%d %H:%M")
    show = show[["When", "name", "type", "distance_km", "duration_min", "avg_hr",
                 "max_hr", "calories", "elev_gain_m", "training_load"]].round(
        {"distance_km": 2, "duration_min": 0, "elev_gain_m": 0, "training_load": 1})
    show.columns = ["When", "Name", "Type", "Dist (km)", "Time (min)", "Avg HR",
                    "Max HR", "Cal", "Elev (m)", "Load"]
    st.dataframe(show, use_container_width=True, hide_index=True, height=460)

    st.download_button("⬇️ Download session log CSV", show.to_csv(index=False),
                       file_name="garmin_session_log.csv", mime="text/csv")

    # Activity-type breakdown
    st.subheader("Activity mix")
    mix = view.groupby("type").size().reset_index(name="count").sort_values("count")
    if not mix.empty:
        fig = px.bar(mix, x="count", y="type", orientation="h")
        fig.update_traces(marker_color=theme.COLORS["cyan"])
        fig = theme.style_fig(fig, height=max(200, 36 * len(mix)))
        fig.update_layout(yaxis_title="", xaxis_title="Activities")
        st.plotly_chart(fig, use_container_width=True)
