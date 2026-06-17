"""Gym & strength — sessions, exercise profile, HR zones, set logs, progression."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import common
import theme
from garmin_data import fmt_duration

st.set_page_config(page_title="DIS · Gym & Strength", page_icon="🏋️", layout="wide")
theme.inject()

st.sidebar.markdown("### 🏋️ Gym & Strength")
common.refresh_button()
common.ensure_auth()

theme.page_header("Gym & Strength", "Sessions · exercise profile · set logs · progression", "🏋️")

data = common.strength(60)
sessions = data["sessions"]
if sessions.empty:
    st.info("No strength sessions found.")
    st.stop()

# ---- Overview KPIs ----------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
theme.kpi(c1, "Sessions", len(sessions))
theme.kpi(c2, "Total sets", int(sessions["total_sets"].fillna(0).sum()))
theme.kpi(c3, "Total reps", f"{int(sessions['total_reps'].fillna(0).sum()):,}")
theme.kpi(c4, "Avg load", round(sessions["training_load"].dropna().mean(), 1)
          if sessions["training_load"].notna().any() else None)
theme.kpi(c5, "Avg duration", fmt_duration(sessions["duration_min"].dropna().mean() * 60)
          if sessions["duration_min"].notna().any() else None)

st.write("")

# ---- Exercise profile + frequency ------------------------------------------
left, right = st.columns(2)
with left:
    st.subheader("💪 Most-trained exercises")
    cats = data["category_totals"]
    cats = cats[cats["category"] != "Unknown"].head(12)
    if not cats.empty:
        fig = px.bar(cats.sort_values("reps"), x="reps", y="category", orientation="h",
                     hover_data=["sets", "sessions"])
        fig.update_traces(marker_color=theme.COLORS["cyan"])
        fig = theme.style_fig(fig, height=360)
        fig.update_layout(yaxis_title="", xaxis_title="Total reps")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No categorised exercises.")

with right:
    st.subheader("📅 Sessions per week")
    sw = sessions.dropna(subset=["start"]).copy()
    if not sw.empty:
        sw["week"] = sw["start"].dt.to_period("W").dt.start_time
        wk = sw.groupby("week").size().reset_index(name="sessions")
        fig = px.bar(wk, x="week", y="sessions")
        fig.update_traces(marker_color=theme.COLORS["sky"])
        fig = theme.style_fig(fig, height=360)
        fig.update_layout(xaxis_title="", yaxis_title="Sessions")
        st.plotly_chart(fig, use_container_width=True)

# ---- Progression ------------------------------------------------------------
st.subheader("📈 Progression")
prog = sessions.dropna(subset=["start"]).sort_values("start")
if not prog.empty:
    fig = go.Figure()
    fig.add_bar(x=prog["start"], y=prog["total_reps"], name="Reps", marker_color=theme.COLORS["steel"])
    if prog["training_load"].notna().any():
        fig.add_scatter(x=prog["start"], y=prog["training_load"], name="Training load",
                        yaxis="y2", line=dict(color=theme.COLORS["orange"]))
    fig = theme.style_fig(fig, height=300)
    fig.update_layout(yaxis_title="Reps",
                      yaxis2=dict(title="Load", overlaying="y", side="right",
                                  gridcolor="rgba(0,0,0,0)"))
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---- Session drill-down -----------------------------------------------------
st.subheader("🔎 Session detail")
labels = [f"{d:%a %d %b %Y · %H:%M} · {int(r or 0)} reps"
          for d, r in zip(sessions["start"], sessions["total_reps"].fillna(0))]
idx = st.selectbox("Select a session", range(len(sessions)),
                   format_func=lambda i: labels[i])
sess = sessions.iloc[idx]
aid = int(sess["activity_id"])

k = st.columns(6)
theme.kpi(k[0], "Duration", fmt_duration((sess["duration_min"] or 0) * 60))
theme.kpi(k[1], "Sets", int(sess["total_sets"]) if pd.notna(sess["total_sets"]) else None)
theme.kpi(k[2], "Reps", int(sess["total_reps"]) if pd.notna(sess["total_reps"]) else None)
theme.kpi(k[3], "Load", round(sess["training_load"], 1) if pd.notna(sess["training_load"]) else None)
theme.kpi(k[4], "Avg HR", int(sess["avg_hr"]) if pd.notna(sess["avg_hr"]) else None, " bpm")
theme.kpi(k[5], "Calories", int(sess["calories"]) if pd.notna(sess["calories"]) else None)

st.write("")
dleft, dright = st.columns(2)

with dleft:
    st.markdown("**❤️ HR time in zones**")
    zones = [(f"Zone {i}", sess.get(f"z{i}")) for i in range(1, 6)]
    zones = [(z, (v or 0) / 60) for z, v in zones]  # seconds -> minutes
    if any(v for _, v in zones):
        zdf = pd.DataFrame(zones, columns=["zone", "minutes"])
        fig = px.bar(zdf, x="minutes", y="zone", orientation="h",
                     color="zone", color_discrete_sequence=theme.CHART_SEQUENCE)
        fig = theme.style_fig(fig, height=260)
        fig.update_layout(showlegend=False, yaxis_title="", xaxis_title="Minutes")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No HR zone data.")

with dright:
    st.markdown("**🧩 Exercises this session**")
    bys = data["by_session"].get(aid, pd.DataFrame())
    bys = bys[bys["category"] != "Unknown"] if not bys.empty else bys
    if not bys.empty:
        show = bys[["category", "sets", "reps"]].sort_values("reps", ascending=False)
        show.columns = ["Exercise", "Sets", "Reps"]
        st.dataframe(show, use_container_width=True, hide_index=True, height=260)
    else:
        st.info("No categorised exercises for this session.")

# ---- Set-by-set log ---------------------------------------------------------
st.markdown("**📋 Set-by-set log**")
sets = common.exercise_sets(aid)
if not sets.empty:
    show_rest = st.checkbox("Show rest periods", value=False)
    view = sets if show_rest else sets[sets["type"] == "ACTIVE"]
    view = view.copy()
    view["duration"] = view["duration_s"].apply(lambda s: fmt_duration(s) if pd.notna(s) else "—")
    view = view[["set", "type", "exercise", "reps", "weight_kg", "duration"]]
    view.columns = ["Set", "Type", "Exercise", "Reps", "Weight (kg)", "Duration"]
    st.dataframe(view, use_container_width=True, hide_index=True)
    st.caption("Weights show only if your device logged them; exercise names are watch-detected.")
else:
    st.info("No set-level data for this session.")
