"""
Data layer: pull a range of days from Garmin Connect into tidy pandas frames.

Every extractor uses .get() with defaults so a missing metric (device didn't
record it that day) yields NaN rather than crashing the whole pull.
"""

from datetime import date, timedelta

import pandas as pd

from garmin_client import get_client


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def fetch_daily(g, start: date, end: date) -> pd.DataFrame:
    """One row per day of summary, sleep, HRV and stress metrics."""
    rows = []
    for d in _daterange(start, end):
        iso = d.isoformat()
        stats = _safe(lambda: g.get_stats(iso), {}) or {}
        sleep = _safe(lambda: g.get_sleep_data(iso), {}) or {}
        hrv = _safe(lambda: g.get_hrv_data(iso), {}) or {}

        sleep_dto = (sleep or {}).get("dailySleepDTO", {}) or {}
        sleep_scores = sleep_dto.get("sleepScores", {}) or {}
        hrv_summary = (hrv or {}).get("hrvSummary", {}) or {}

        rows.append({
            "date": pd.Timestamp(d),
            "steps": stats.get("totalSteps"),
            "step_goal": stats.get("dailyStepGoal"),
            "calories": stats.get("totalKilocalories"),
            "active_calories": stats.get("activeKilocalories"),
            "resting_hr": stats.get("restingHeartRate"),
            "min_hr": stats.get("minHeartRate"),
            "max_hr": stats.get("maxHeartRate"),
            "floors": stats.get("floorsAscended"),
            "moderate_min": stats.get("moderateIntensityMinutes"),
            "vigorous_min": stats.get("vigorousIntensityMinutes"),
            "avg_stress": stats.get("averageStressLevel"),
            "max_stress": stats.get("maxStressLevel"),
            "bb_high": stats.get("bodyBatteryHighestValue"),
            "bb_low": stats.get("bodyBatteryLowestValue"),
            "sleep_hours": (sleep_dto.get("sleepTimeSeconds") or 0) / 3600 or None,
            "deep_hours": (sleep_dto.get("deepSleepSeconds") or 0) / 3600 or None,
            "light_hours": (sleep_dto.get("lightSleepSeconds") or 0) / 3600 or None,
            "rem_hours": (sleep_dto.get("remSleepSeconds") or 0) / 3600 or None,
            "awake_hours": (sleep_dto.get("awakeSleepSeconds") or 0) / 3600 or None,
            "sleep_score": (sleep_scores.get("overall") or {}).get("value"),
            "hrv_avg": hrv_summary.get("lastNightAvg"),
            "hrv_status": hrv_summary.get("status"),
        })

    df = pd.DataFrame(rows)
    # Coerce numeric columns (everything except date / hrv_status).
    for col in df.columns:
        if col not in ("date", "hrv_status"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def fetch_activities(g, limit: int = 30) -> pd.DataFrame:
    """Recent activities as a tidy frame."""
    acts = _safe(lambda: g.get_activities(0, limit), []) or []
    rows = []
    for a in acts:
        rows.append({
            "name": a.get("activityName"),
            "type": (a.get("activityType") or {}).get("typeKey"),
            "start": a.get("startTimeLocal"),
            "duration_min": (a.get("duration") or 0) / 60 or None,
            "distance_km": (a.get("distance") or 0) / 1000 or None,
            "calories": a.get("calories"),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "elev_gain_m": a.get("elevationGain"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["start"] = pd.to_datetime(df["start"], errors="coerce")
        df = df.sort_values("start", ascending=False).reset_index(drop=True)
    return df


def _first_value(d):
    """Garmin nests some data under a dynamic device-id key; grab the first value."""
    if isinstance(d, dict) and d:
        return next(iter(d.values()))
    return {}


def fetch_running_summary(g, day: str) -> dict:
    """VO2max, fitness age, training status & load for a given day."""
    ts = _safe(lambda: g.get_training_status(day), {}) or {}
    vo2 = ((ts.get("mostRecentVO2Max") or {}).get("generic") or {})
    status_map = ((ts.get("mostRecentTrainingStatus") or {})
                  .get("latestTrainingStatusData") or {})
    status = _first_value(status_map)
    load_map = ((ts.get("mostRecentTrainingLoadBalance") or {})
                .get("metricsTrainingLoadBalanceDTOMap") or {})
    load = _first_value(load_map)
    # trainingStatus is a numeric code; the feedback phrase (e.g. "PRODUCTIVE_1")
    # is the human-readable source — clean it into "Productive".
    phrase = status.get("trainingStatusFeedbackPhrase") or ""
    label = phrase.split("_")[0].title() if phrase else None
    return {
        "vo2max": vo2.get("vo2MaxValue"),
        "fitness_age": vo2.get("fitnessAge"),
        "training_status": label or status.get("trainingStatus"),
        "training_status_key": phrase,
        "acute_load": load.get("monthlyLoadAerobicLow", None),
        "load_balance": load,
        "status_raw": status,
    }


def fetch_race_predictions(g) -> dict:
    """Predicted race times (seconds) for 5K / 10K / HM / Marathon."""
    rp = _safe(lambda: g.get_race_predictions(), {}) or {}
    return {
        "5K": rp.get("time5K"),
        "10K": rp.get("time10K"),
        "Half Marathon": rp.get("timeHalfMarathon"),
        "Marathon": rp.get("timeMarathon"),
        "date": rp.get("calendarDate"),
    }


def fetch_training_readiness(g, day: str) -> dict:
    """Today's training readiness score + contributing factors."""
    tr = _safe(lambda: g.get_training_readiness(day), []) or []
    return tr[0] if tr else {}


def fetch_runs(g, limit: int = 50) -> pd.DataFrame:
    """Recent running activities only, as a tidy frame."""
    acts = fetch_activities(g, limit)
    if acts.empty:
        return acts
    runs = acts[acts["type"].fillna("").str.contains("running", case=False)].copy()
    if not runs.empty and runs["distance_km"].notna().any():
        # pace in min/km
        runs["pace_min_km"] = runs["duration_min"] / runs["distance_km"]
    return runs.reset_index(drop=True)


def fmt_duration(seconds) -> str:
    """Seconds -> H:MM:SS or M:SS, for race-time display."""
    if seconds is None or pd.isna(seconds):
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


if __name__ == "__main__":
    # Smoke test from the CLI: last 7 days.
    g = get_client()
    end = date.today()
    start = end - timedelta(days=6)
    print(fetch_daily(g, start, end).to_string())
    print()
    print(fetch_activities(g, 10).to_string())
