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
            "options": {"temperature": temperature, "num_ctx": 8192, "num_predict": 2048},
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


def list_models():
    """Names of models installed in the local Ollama instance (for the UI picker)."""
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3).json()
        return sorted(m.get("name", "") for m in tags.get("models", []) if m.get("name"))
    except Exception:
        return [MODEL]


def format_prefs(prefs: dict) -> str:
    """Render the user's stated goals/preferences for a plan into a prompt block."""
    if not prefs:
        return "(none specified)"
    lines = []
    for k, v in prefs.items():
        if v in (None, "", [], False):
            continue
        if isinstance(v, list):
            v = ", ".join(map(str, v))
        if v is True:
            v = "yes"
        lines.append(f"- {k}: {v}")
    return "\n".join(lines) if lines else "(none specified)"


# --- Coaching prompts --------------------------------------------------------
_SYSTEM = (
    "You are an elite endurance, strength and rehabilitation coach with a sports-science "
    "PhD and decades of practice. You design specific, individualised, evidence-based plans. "
    "PRINCIPLES: progressive overload, specificity, periodisation, polarised (80/20) "
    "endurance distribution, adequate recovery and deloads. You ALWAYS honour the athlete's "
    "stated goals and constraints (days available, equipment, target race/date, focus areas) "
    "EXACTLY — never schedule more sessions than they asked for. You ground decisions in the "
    "athlete's data: derive running paces from their race predictors and recent runs; respect "
    "recovery when readiness/HRV/sleep are poor or training status is 'Strained'/'Overreaching'. "
    "Be concrete: real paces (min/km), real sets×reps×intensity, week-to-week progression. "
    "Output clean GitHub markdown: a short summary line, tables for schedules, brief rationale. "
    "Never invent data you weren't given. You are not a doctor; for pain or injury, recommend "
    "assessment by a qualified physiotherapist or doctor."
)

_PROMPTS = {
    "running": (
        "Design a personalised **running plan** for this athlete.\n\n"
        "REQUIREMENTS:\n"
        "1. One-line **today verdict** (train hard / easy / recovery / rest) from their readiness data.\n"
        "2. A **pace zones** table (Easy, Marathon, Threshold, Interval/VO2, Repetition) with actual "
        "min/km ranges derived from their race predictors and recent runs.\n"
        "3. A **next-7-days** table: Day | Session | Distance/Time | Target pace | Purpose — using "
        "EXACTLY the number of running days they asked for, with rest/easy days otherwise, and a "
        "long run on their preferred day if given. Add cross-training only if they opted in.\n"
        "4. A short **build-up** note: how the coming weeks progress toward their goal/target race "
        "and date (include a deload if appropriate).\n"
        "5. 2-3 **coaching notes** tailored to their goal and current training status.\n\n"
        "ATHLETE GOALS & PREFERENCES:\n{prefs}\n\nATHLETE DATA:\n{ctx}"
    ),
    "gym": (
        "Design a personalised **gym / strength plan** for this athlete that complements their "
        "running.\n\nREQUIREMENTS:\n"
        "1. Choose a sensible **split** for EXACTLY the number of days they asked for (e.g. full-body, "
        "upper/lower, or push/pull/legs) matched to their goal and experience.\n"
        "2. A **weekly table**: Day | Focus | Exercises (Sets×Reps×intensity/RPE) | Notes — using ONLY "
        "their available equipment and fitting their session length.\n"
        "3. Prioritise their stated **focus areas** and address likely imbalances from their most-trained "
        "exercises in the data.\n"
        "4. A **progression scheme** (how to add load/reps over the coming weeks) plus when to deload.\n"
        "5. Schedule so heavy leg work doesn't collide with key running days; lighten if recovery is poor.\n"
        "6. A brief **warm-up / mobility** note.\n\n"
        "ATHLETE GOALS & PREFERENCES:\n{prefs}\n\nATHLETE DATA:\n{ctx}"
    ),
    "rehab": (
        "Provide a **general rehabilitation & return-to-activity guide** for the area/issue the "
        "athlete describes. This is educational guidance, NOT a diagnosis or medical treatment.\n\n"
        "REQUIREMENTS:\n"
        "1. Open with a clear **safety note**: this isn't medical advice; if pain is high/worsening, "
        "there's swelling, instability, numbness or it followed trauma, see a physio/doctor first.\n"
        "2. A **stage-appropriate approach** for their reported stage (acute / early / mid / late / "
        "return-to-sport) and pain level — protect & calm early, progressively load later.\n"
        "3. A **phased exercise progression** table: Phase | Goal | Exercises (sets×reps/hold) | "
        "Progression criteria — appropriate to the body area and their available equipment/days.\n"
        "4. A **pain-monitoring** rule (e.g. traffic-light: keep pain ≤3/10 during & settled by next day).\n"
        "5. **Red flags** to stop and seek assessment, and **return-to-activity criteria**.\n"
        "Keep it general and conservative; do not name a specific diagnosis.\n\n"
        "ATHLETE'S REHAB DETAILS:\n{prefs}\n\nATHLETE DATA:\n{ctx}"
    ),
    "readiness": (
        "Give **today's training recommendation** from the data.\n"
        "- Start with a bold one-line verdict: TRAIN HARD / TRAIN EASY / ACTIVE RECOVERY / REST.\n"
        "- 3-5 bullets explaining the call from readiness score, HRV status, sleep, recovery time and "
        "training status.\n- Suggest one concrete session (or rest) for today with specifics.\n"
        "- Note the single biggest lever to improve tomorrow's readiness.\n\nATHLETE DATA:\n{ctx}"
    ),
}

_TEMPERATURE = {"running": 0.4, "gym": 0.4, "rehab": 0.3, "readiness": 0.5}


def generate(kind: str, ctx: dict, prefs: dict = None, model: str = MODEL) -> str:
    """Generate a coaching output. kind in {'running','gym','rehab','readiness'}."""
    prompt = _PROMPTS[kind].format(ctx=format_context(ctx), prefs=format_prefs(prefs or {}))
    out = chat(_SYSTEM, prompt, model=model, temperature=_TEMPERATURE.get(kind, 0.5))
    return f"{out}\n\n---\n{DISCLAIMER}"
