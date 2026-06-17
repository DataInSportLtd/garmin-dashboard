"""Run drill-down — GPS map, per-sample streams, advanced form metrics, splits."""

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

import common
import theme
from garmin_data import fmt_duration

st.set_page_config(page_title="DIS · Run Detail", page_icon="🗺️", layout="wide")
theme.inject()

st.sidebar.markdown("### 🗺️ Run Detail")
common.refresh_button()
common.ensure_auth()

theme.page_header("Run Detail", "Everything Garmin recorded — map, streams, splits", "🗺️")

runs = common.runs(50)
if runs.empty:
    st.info("No runs found.")
    st.stop()

# ---- Pick a run -------------------------------------------------------------
runs = runs.copy()
runs["when"] = pd.to_datetime(runs["start"]).dt.strftime("%a %d %b %Y · %H:%M")
labels = [
    f"{w} · {n} · {d:.2f} km"
    for w, n, d in zip(runs["when"], runs["name"], runs["distance_km"].fillna(0))
]
# Support deep-link via ?run=<activityId> (set when we add click-through later).
qp_id = st.query_params.get("run")
default = 0
if qp_id:
    match = runs.index[runs["activity_id"] == int(qp_id)] if "activity_id" in runs else []
    default = int(match[0]) if len(match) else 0

choice = st.selectbox("Select a run", range(len(runs)),
                      format_func=lambda i: labels[i], index=default)
run = runs.iloc[choice]
activity_id = int(run["activity_id"])

# ---- Headline KPIs ----------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
theme.kpi(c1, "Distance", f"{run['distance_km']:.2f}", " km")
pace = run.get("pace_min_km")
theme.kpi(c2, "Avg pace", f"{int(pace)}:{int((pace % 1)*60):02d}" if pd.notna(pace) else None, " /km")
theme.kpi(c3, "Time", fmt_duration((run.get("duration_min") or 0) * 60))
theme.kpi(c4, "Avg HR", int(run["avg_hr"]) if pd.notna(run.get("avg_hr")) else None, " bpm")
theme.kpi(c5, "Elev gain", int(run["elev_gain_m"]) if pd.notna(run.get("elev_gain_m")) else None, " m")

st.write("")

s = common.streams(activity_id)
if s.empty:
    st.warning("No detailed streams available for this run.")
    st.stop()

# ---- GPS route map ----------------------------------------------------------
gps = s.dropna(subset=["lat", "lon"])
left, right = st.columns([3, 2])
with left:
    st.subheader("🗺️ Route")
    if not gps.empty:
        path = [[lon, lat] for lat, lon in zip(gps["lat"], gps["lon"])]
        layer = pdk.Layer(
            "PathLayer",
            data=[{"path": path}],
            get_path="path",
            get_color=[71, 201, 201],
            width_min_pixels=4,
            get_width=5,
        )
        view = pdk.ViewState(
            latitude=float(gps["lat"].mean()),
            longitude=float(gps["lon"].mean()),
            zoom=12.5, pitch=0,
        )
        st.pydeck_chart(pdk.Deck(
            layers=[layer], initial_view_state=view,
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        ), use_container_width=True)
    else:
        st.info("No GPS data for this run (treadmill?).")

with right:
    st.subheader("⛰️ Elevation")
    fig = go.Figure()
    fig.add_scatter(x=s["distance_km"], y=s["elevation_m"], fill="tozeroy",
                    line=dict(color=theme.COLORS["steel"]), name="Elevation")
    fig = theme.style_fig(fig, height=260)
    fig.update_layout(xaxis_title="km", yaxis_title="m")
    st.plotly_chart(fig, use_container_width=True)

# ---- Pace + HR headline chart ----------------------------------------------
st.subheader("🏃 Pace & heart rate")
fig = go.Figure()
fig.add_scatter(x=s["distance_km"], y=s["pace_min_km"], name="Pace (min/km)",
                line=dict(color=theme.COLORS["cyan"]))
fig.add_scatter(x=s["distance_km"], y=s["hr"], name="HR (bpm)", yaxis="y2",
                line=dict(color=theme.COLORS["orange"]))
fig = theme.style_fig(fig, height=340)
fig.update_layout(
    xaxis_title="Distance (km)",
    yaxis=dict(title="Pace (min/km)", autorange="reversed"),  # faster = higher
    yaxis2=dict(title="HR (bpm)", overlaying="y", side="right", gridcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig, use_container_width=True)

# ---- Advanced form metrics --------------------------------------------------
st.subheader("🔬 Advanced metrics")
metric_opts = {
    "Cadence (spm)": "cadence_spm",
    "Power (W)": "power_w",
    "Stride length (cm)": "stride_cm",
    "Ground contact (ms)": "gct_ms",
    "Vertical oscillation (cm)": "vert_osc_cm",
    "Stamina": "stamina",
}
available = {k: v for k, v in metric_opts.items() if v in s and s[v].notna().any()}
picked = st.multiselect("Metrics", list(available), default=list(available)[:3])
cols = st.columns(min(3, len(picked)) or 1)
for i, label in enumerate(picked):
    fig = go.Figure()
    fig.add_scatter(x=s["distance_km"], y=s[available[label]],
                    line=dict(color=theme.CHART_SEQUENCE[i % len(theme.CHART_SEQUENCE)]))
    fig = theme.style_fig(fig, height=220)
    fig.update_layout(title=label, xaxis_title="km")
    cols[i % len(cols)].plotly_chart(fig, use_container_width=True)

# ---- Splits -----------------------------------------------------------------
st.subheader("📊 Splits")
sp = common.splits(activity_id)
if not sp.empty:
    show = sp.copy()
    show["pace"] = show["pace_min_km"].apply(
        lambda p: f"{int(p)}:{int((p % 1)*60):02d}" if pd.notna(p) else "—")
    show = show[["lap", "distance_km", "pace", "avg_hr", "max_hr", "avg_cadence",
                 "avg_power_w", "elev_gain_m"]].round(
        {"distance_km": 2, "elev_gain_m": 0, "avg_power_w": 0})
    show.columns = ["Lap", "Dist (km)", "Pace /km", "Avg HR", "Max HR", "Cadence",
                    "Power (W)", "Elev (m)"]
    st.dataframe(show, use_container_width=True, hide_index=True)
else:
    st.info("No split data for this run.")
