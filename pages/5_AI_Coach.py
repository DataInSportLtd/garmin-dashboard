"""AI Coach — local-LLM running / gym-rehab / readiness guidance from your data."""

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

theme.page_header("AI Coach", "Local-model coaching grounded in your Garmin data", "🧠")

# ---- Model status -----------------------------------------------------------
up, ready = ai.server_up(), ai.model_ready()
if not up:
    st.error(
        "Local AI server isn't running. Start it in a terminal:\n\n"
        "```\n~/.local/bin/ollama serve\n```\n\nthen click **Refresh data**."
    )
    st.stop()
if not ready:
    st.warning(
        f"Model `{ai.MODEL}` not found. Pull it once:\n\n"
        f"```\n~/.local/bin/ollama pull {ai.MODEL}\n```"
    )
    st.stop()
st.success(f"🟢 Local model `{ai.MODEL}` ready · runs entirely on your machine", icon="✅")


# ---- Build athlete context (cached loaders) ---------------------------------
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

st.caption("Generation runs locally and takes ~15–60s. Output is cached until you regenerate.")

# ---- Coaching tabs ----------------------------------------------------------
TABS = [("readiness", "🎯 Today's readiness"), ("running", "🏃 Running plan"),
        ("gym", "🏋️ Gym & rehab plan")]
tabs = st.tabs([label for _, label in TABS])

for tab, (kind, label) in zip(tabs, TABS):
    with tab:
        key = f"ai_{kind}"
        btn_label = f"Generate {label.split(' ',1)[1].lower()}" if key not in st.session_state \
            else "Regenerate"
        if st.button(btn_label, key=f"btn_{kind}", type="primary"):
            with st.spinner(f"Coaching ({ai.MODEL})…"):
                try:
                    st.session_state[key] = ai.generate(kind, ctx)
                except Exception as e:
                    st.session_state[key] = f"⚠️ Generation failed: {e}"
        if key in st.session_state:
            st.markdown(st.session_state[key])
        else:
            st.info("Click the button to generate guidance from your latest data.")
