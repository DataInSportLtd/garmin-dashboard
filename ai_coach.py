"""
AI coaching engine — turns the athlete's Garmin data into running / gym-rehab /
readiness guidance using a LOCAL model via Ollama (no data leaves the machine).

Backend is pluggable (`OLLAMA` today; a Claude API path can slot in later).
The page gathers a context dict from cached Garmin loaders and passes it here,
so this module stays free of Streamlit / network-to-Garmin concerns.
"""

import os
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

DISCLAIMER = (
    "_AI-generated from your Garmin data for general fitness guidance only — "
    "not medical advice. For pain, injury or illness, consult a qualified "
    "professional._"
)


# --- Backend -----------------------------------------------------------------
def server_up() -> bool:
    try:
        requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).raise_for_status()
        return True
    except Exception:
        return False


def model_ready(model: str = MODEL) -> bool:
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json()
        names = [m.get("name", "") for m in tags.get("models", [])]
        return any(n == model or n.startswith(model.split(":")[0]) for n in names)
    except Exception:
        return False


def chat(system: str, user: str, model: str = MODEL, temperature: float = 0.6) -> str:
    """Single-shot chat completion against the local Ollama server."""
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": 8192},
        },
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


# --- Context formatting ------------------------------------------------------
def format_context(ctx: dict) -> str:
    """Render the athlete context dict into a compact text block for the prompt."""
    lines = []
    r = ctx.get("readiness") or {}
    if r:
        lines.append(
            f"TODAY'S READINESS: score {r.get('score')}/100 ({r.get('level','').title()}). "
            f"Factors — sleep {r.get('sleepScoreFactorPercent')}%, "
            f"recovery {r.get('recoveryTimeFactorPercent')}%, "
            f"ACWR/load {r.get('acwrFactorPercent')}%, HRV {r.get('hrvFactorPercent')}%, "
            f"stress {r.get('stressHistoryFactorPercent')}%. "
            f"Recovery time remaining: {r.get('recoveryTime')} h."
        )
    rs = ctx.get("running") or {}
    if rs:
        lines.append(
            f"FITNESS: VO2max {rs.get('vo2max')}, training status '{rs.get('training_status')}'."
        )
    races = ctx.get("races") or {}
    if races and any(races.get(k) for k in ["5K", "10K", "Half Marathon", "Marathon"]):
        from garmin_data import fmt_duration
        lines.append("RACE PREDICTORS: " + ", ".join(
            f"{k} {fmt_duration(v)}" for k, v in races.items() if k != "date" and v))
    runs = ctx.get("recent_runs")
    if runs is not None and not runs.empty:
        rl = []
        for r_ in runs.head(8).itertuples():
            pace = getattr(r_, "pace_min_km", None)
            pace_s = f"{int(pace)}:{int((pace%1)*60):02d}/km" if pace and pace == pace else "?"
            rl.append(f"{getattr(r_,'distance_km',0):.1f}km @ {pace_s} (HR {getattr(r_,'avg_hr','?')})")
        lines.append("RECENT RUNS (newest first): " + "; ".join(rl))
    sl = ctx.get("sleep") or {}
    if sl:
        lines.append(
            f"LAST NIGHT SLEEP: {sl.get('sleep_h',0):.1f}h, score {sl.get('score')} "
            f"({(sl.get('score_qualifier') or '').title()}), overnight HRV "
            f"{sl.get('overnight_hrv')} ({(sl.get('hrv_status') or '').title()})."
        )
    st = ctx.get("strength") or {}
    if st:
        lines.append(
            f"STRENGTH (recent): {st.get('sessions')} sessions, {st.get('total_reps')} reps, "
            f"avg load {st.get('avg_load')}. Most trained: {st.get('top_exercises')}."
        )
    sleep_trend = ctx.get("sleep_trend") or {}
    if sleep_trend:
        lines.append(
            f"7-DAY AVERAGES: sleep {sleep_trend.get('avg_sleep_h')}h, "
            f"HRV {sleep_trend.get('avg_hrv')}, resting HR {sleep_trend.get('avg_rhr')}."
        )
    return "\n".join(lines) if lines else "No recent data available."


# --- Coaching prompts --------------------------------------------------------
_SYSTEM = (
    "You are an elite endurance and strength coach with a sports-science PhD. "
    "You give specific, safe, evidence-based guidance grounded ONLY in the athlete's "
    "data provided. Respect recovery: if readiness is low, HRV is low/unbalanced, "
    "sleep is poor, or training status is 'Strained'/'Overreaching', prioritise rest "
    "and easy work over hard sessions. Be concise and practical. Output clean GitHub "
    "markdown with short sections and tables where useful. Never invent data you "
    "weren't given. You are not a doctor; for pain/injury, advise seeing a professional."
)

_PROMPTS = {
    "running": (
        "Using the data below, write a personalised **7-day running plan**.\n"
        "- Open with a one-line readiness verdict (train / easy / rest today).\n"
        "- Give a day-by-day table: Day | Session | Distance | Target pace | Purpose.\n"
        "- Base paces on the race predictors and recent runs; set easy/threshold/interval "
        "zones accordingly.\n- Adapt volume to training status & readiness; include at least "
        "one rest/recovery day.\n- End with 2-3 bullet coaching notes.\n\nATHLETE DATA:\n{ctx}"
    ),
    "gym": (
        "Using the data below, write a personalised **7-day gym + mobility/rehab plan** that "
        "complements the running load.\n- Balance push/pull/legs/core and address likely "
        "imbalances from the most-trained exercises.\n- Day-by-day table: Day | Focus | Key work | "
        "Sets×Reps | Notes.\n- Fit strength around running so hard days don't collide; lighten if "
        "readiness/recovery is poor.\n- Include a short **mobility/prehab** block (no diagnosis) "
        "for common runner areas (hips, calves, ankles).\n- End with 2-3 recovery bullets.\n\n"
        "ATHLETE DATA:\n{ctx}"
    ),
    "readiness": (
        "Using the data below, give **today's training recommendation**.\n"
        "- Start with a bold one-line verdict: TRAIN HARD / TRAIN EASY / ACTIVE RECOVERY / REST.\n"
        "- 3-5 bullets explaining the call from readiness score, HRV status, sleep, recovery time "
        "and training status.\n- Suggest one concrete session (or rest) for today with specifics.\n"
        "- Note the single biggest lever to improve tomorrow's readiness.\n\nATHLETE DATA:\n{ctx}"
    ),
}


def generate(kind: str, ctx: dict, model: str = MODEL) -> str:
    """Generate a coaching output. kind in {'running','gym','readiness'}."""
    prompt = _PROMPTS[kind].format(ctx=format_context(ctx))
    out = chat(_SYSTEM, prompt, model=model)
    return f"{out}\n\n---\n{DISCLAIMER}"
