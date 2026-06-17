"""AI Coach — local-LLM coaching from your data + your stated goals/preferences."""

from datetime import date, timedelta

import streamlit as st

import ai_coach as ai
import common
import theme

st.set_page_config(page_title="DIS · AI Coach", page_icon="🧠", layout="wide")
theme.inject()

st.sidebar.markdown("### 🧠 AI Coach")
common.refresh_button()
common.ensure_auth()

theme.page_header("AI Coach", "Coaching grounded in your data — and what you want to achieve", "🧠")

# ---- Model status + picker --------------------------------------------------
if not ai.server_up():
    st.error("Local AI server isn't running. Start it:\n\n```\n~/.local/bin/ollama serve\n```\n\n"
             "then click **Refresh data**.")
    st.stop()
models = ai.list_models()
model = st.sidebar.selectbox("Model", models,
                             index=models.index(ai.MODEL) if ai.MODEL in models else 0,
                             help="Bigger models give better plans but run slower. "
                                  "Pull more with e.g. `ollama pull qwen2.5:14b`.")
st.sidebar.caption("Runs 100% locally · nothing leaves your machine")


# ---- Athlete context (cached) ----------------------------------------------
@st.cache_data(ttl=900, show_spinner="Gathering your data…")
def build_context():
    today = date.today().isoformat()
    yest = (date.today() - timedelta(days=1)).isoformat()
    end = date.today()
    trend = common.daily(end - timedelta(days=6), end)

    def tavg(col):
        s = trend[col].dropna()
        return round(s.mean(), 1) if not s.empty else None

    strength = common.strength(60)
    s = strength["sessions"]
    cats = strength["category_totals"]
    top = ", ".join(cats[cats["category"] != "Unknown"]["category"].head(4)) if not cats.empty else ""
    sleep = common.sleep_detail(yest) or common.sleep_detail(
        (date.today() - timedelta(days=2)).isoformat())
    return {
        "readiness": common.training_readiness(today),
        "running": common.running_summary(today),
        "races": common.race_predictions(),
        "recent_runs": common.runs(15),
        "sleep": sleep,
        "strength": {
            "sessions": int(len(s)),
            "total_reps": int(s["total_reps"].fillna(0).sum()) if not s.empty else 0,
            "avg_load": round(s["training_load"].dropna().mean(), 1)
            if not s.empty and s["training_load"].notna().any() else None,
            "top_exercises": top,
        },
        "sleep_trend": {"avg_sleep_h": tavg("sleep_hours"), "avg_hrv": tavg("hrv_avg"),
                        "avg_rhr": tavg("resting_hr")},
    }


ctx = build_context()
with st.expander("🔎 Data the coach is using"):
    st.code(ai.format_context(ctx), language="text")
st.caption(f"Generation runs locally on `{model}` (~15–90s depending on model & plan length).")

DAYS = ["No preference", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def run_and_store(kind, prefs):
    key = f"ai_{kind}"
    with st.spinner(f"Coaching on {model}…"):
        try:
            st.session_state[key] = ai.generate(kind, ctx, prefs, model=model)
        except Exception as e:
            st.session_state[key] = f"⚠️ Generation failed: {e}"


def show(kind):
    key = f"ai_{kind}"
    if key in st.session_state:
        st.markdown(st.session_state[key])


tab_r, tab_run, tab_gym, tab_rehab = st.tabs(
    ["🎯 Today's readiness", "🏃 Running plan", "🏋️ Gym plan", "🩹 Rehab guide"])

# ---- Readiness (no inputs needed) ------------------------------------------
with tab_r:
    st.write("Instant read on whether to train hard, easy, or rest today.")
    if st.button("Generate today's recommendation", type="primary", key="b_read"):
        run_and_store("readiness", {})
    show("readiness")

# ---- Running plan -----------------------------------------------------------
with tab_run:
    with st.form("running_form"):
        c1, c2, c3 = st.columns(3)
        goal = c1.selectbox("Primary goal", [
            "General fitness", "Build aerobic base", "Improve PB / get faster",
            "Race: 5K", "Race: 10K", "Race: Half Marathon", "Race: Marathon",
            "Race: Ultra", "Return to running"])
        days = c2.slider("Days/week to run", 1, 7, 4)
        long_day = c3.selectbox("Preferred long-run day", DAYS)
        c4, c5, c6 = st.columns(3)
        weekly_km = c4.number_input("Current weekly volume (km)", 0, 250, 30)
        longest_km = c5.number_input("Longest recent run (km)", 0, 100, 10)
        race_date = c6.date_input("Target race date (if any)", value=None)
        c7, c8 = st.columns(2)
        target_time = c7.text_input("Target time (optional)", placeholder="e.g. sub-40 10K")
        cross = c8.checkbox("Include cross-training (bike/swim)")
        notes = st.text_area("Anything else?", placeholder="injuries, terrain, schedule constraints…")
        submitted = st.form_submit_button("Generate running plan", type="primary")
    if submitted:
        run_and_store("running", {
            "goal": goal, "days_per_week": days,
            "preferred_long_run_day": None if long_day == "No preference" else long_day,
            "current_weekly_km": weekly_km, "longest_recent_km": longest_km,
            "target_race_date": race_date.isoformat() if race_date else None,
            "target_time": target_time, "include_cross_training": cross, "notes": notes})
    show("running")

# ---- Gym plan ---------------------------------------------------------------
with tab_gym:
    with st.form("gym_form"):
        c1, c2, c3 = st.columns(3)
        goal = c1.selectbox("Primary goal", [
            "Support my running", "General fitness", "Build muscle (hypertrophy)",
            "Maximal strength", "Power / explosiveness", "Muscular endurance"])
        days = c2.slider("Days/week in the gym", 1, 7, 3)
        length = c3.selectbox("Session length", ["30 min", "45 min", "60 min", "90 min"], index=2)
        c4, c5 = st.columns(2)
        experience = c4.selectbox("Experience", ["Beginner", "Intermediate", "Advanced"], index=1)
        equipment = c5.multiselect("Equipment available", [
            "Full commercial gym", "Barbell", "Dumbbells", "Kettlebells", "Machines",
            "Cables", "Resistance bands", "Bodyweight only"], default=["Full commercial gym"])
        focus = st.multiselect("Focus / priority areas", [
            "Legs", "Glutes", "Posterior chain", "Core", "Upper body", "Back",
            "Chest", "Shoulders", "Arms", "Single-leg stability"])
        notes = st.text_area("Anything else?", placeholder="niggles, preferences, time of day…",
                             key="gym_notes")
        submitted = st.form_submit_button("Generate gym plan", type="primary")
    if submitted:
        run_and_store("gym", {
            "goal": goal, "days_per_week": days, "session_length": length,
            "experience": experience, "equipment": equipment, "focus_areas": focus,
            "notes": notes})
    show("gym")

# ---- Rehab guide ------------------------------------------------------------
with tab_rehab:
    st.warning("General educational guidance only — not a diagnosis. For significant or worsening "
               "pain, swelling, instability or post-trauma injury, see a physiotherapist or doctor first.")
    with st.form("rehab_form"):
        c1, c2 = st.columns(2)
        area = c1.multiselect("Area(s) affected", [
            "Knee", "Achilles", "Calf", "Hamstring", "Quad", "Hip", "Glute",
            "Lower back", "Ankle", "Foot / plantar", "Shin", "IT band", "Groin",
            "Shoulder", "Other"])
        stage = c2.selectbox("Current stage", [
            "Acute (0-3 days)", "Early (1-2 weeks)", "Mid (recovering)",
            "Late (nearly back)", "Return to sport"])
        c3, c4 = st.columns(2)
        pain = c3.slider("Current pain (0-10)", 0, 10, 3)
        days = c4.slider("Days/week you can do rehab", 1, 7, 5)
        equipment = st.multiselect("Equipment available", [
            "Bodyweight only", "Resistance bands", "Dumbbells", "Kettlebells",
            "Full gym", "Foam roller"], default=["Bodyweight only", "Resistance bands"])
        desc = st.text_area("What happened / how it feels",
                            placeholder="e.g. tight right achilles, worse after fast runs, no swelling")
        aggravating = st.text_input("What aggravates it?", placeholder="e.g. hills, fast pace, stairs")
        submitted = st.form_submit_button("Generate rehab guide", type="primary")
    if submitted:
        if not area and not desc:
            st.error("Tell me at least the area or a short description so I can tailor it.")
        else:
            run_and_store("rehab", {
                "area": area, "stage": stage, "pain_level_0_10": pain,
                "days_per_week": days, "equipment": equipment,
                "description": desc, "aggravating_activities": aggravating})
    show("rehab")
