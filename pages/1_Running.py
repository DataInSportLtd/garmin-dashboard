"""Running hub — VO2max, race predictors, training status & readiness, run log."""

from datetime import date

import pandas as pd
import streamlit as st

import common
import theme
from garmin_data import fmt_duration

st.set_page_config(page_title="DIS · Running", page_icon="🏃", layout="wide")
theme.inject()

st.sidebar.markdown("### 🏃 Running")
common.refresh_button()

common.ensure_auth()
today = date.today().isoformat()

theme.page_header("Running", "VO₂max · race predictors · training status · run log", "🏃")

summary = common.running_summary(today)
races = common.race_predictions()
readiness = common.training_readiness(today)

# ---- Top KPIs ---------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
vo2 = summary.get("vo2max")
theme.kpi(c1, "VO₂max", round(vo2, 1) if vo2 else None, " ml/kg/min")
theme.kpi(c2, "Fitness age", summary.get("fitness_age"))
theme.kpi(c3, "Training status", (summary.get("training_status") or "—"))
theme.kpi(c4, "Readiness", readiness.get("score"), f" · {readiness.get('level','').title()}")

st.write("")

# ---- Race predictors --------------------------------------------------------
st.subheader("🏁 Race predictors")
if any(races.get(k) for k in ["5K", "10K", "Half Marathon", "Marathon"]):
    cols = st.columns(4)
    for col, dist in zip(cols, ["5K", "10K", "Half Marathon", "Marathon"]):
        theme.kpi(col, dist, fmt_duration(races.get(dist)))
    if races.get("date"):
        st.caption(f"Garmin estimate as of {races['date']}")
else:
    st.info("No race predictions yet — these appear after enough recent runs.")

st.write("")

# ---- Training readiness breakdown ------------------------------------------
st.subheader("🔬 Training readiness factors")
if readiness:
    st.caption(readiness.get("feedbackLong", "").replace("_", " "))
    factors = [
        ("Sleep", "sleepScoreFactorPercent"),
        ("Recovery time", "recoveryTimeFactorPercent"),
        ("ACWR (load ratio)", "acwrFactorPercent"),
        ("HRV", "hrvFactorPercent"),
        ("Stress history", "stressHistoryFactorPercent"),
        ("Sleep history", "sleepHistoryFactorPercent"),
    ]
    fcols = st.columns(len(factors))
    for col, (lbl, key) in zip(fcols, factors):
        theme.kpi(col, lbl, readiness.get(key), "%")
else:
    st.info("No training readiness data for today.")

st.write("")

# ---- Run log ----------------------------------------------------------------
st.subheader("📋 Recent runs")
runs = common.runs(50)
if not runs.empty:
    show = runs.copy()
    show["when"] = pd.to_datetime(show["start"]).dt.strftime("%a %d %b · %H:%M")
    show["pace"] = show["pace_min_km"].apply(
        lambda p: f"{int(p)}:{int((p % 1) * 60):02d} /km" if pd.notna(p) else "—")
    show = show[["when", "name", "distance_km", "pace", "duration_min", "avg_hr",
                 "max_hr", "calories", "elev_gain_m"]].round(
        {"distance_km": 2, "duration_min": 0, "elev_gain_m": 0})
    show.columns = ["When", "Name", "Dist (km)", "Pace", "Time (min)", "Avg HR",
                    "Max HR", "Cal", "Elev (m)"]
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.caption("Per-run drill-down (maps, splits, per-second streams) lands in the next phase.")
else:
    st.info("No running activities found.")
