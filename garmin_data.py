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
            "activity_id": a.get("activityId"),
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


def fetch_activity_streams(g, activity_id: int) -> pd.DataFrame:
    """Per-sample time-series for one activity (GPS, HR, pace, cadence, power…).

    Garmin returns rows of raw metric arrays aligned to `metricDescriptors`;
    we pivot them into named columns and derive friendly fields.
    """
    det = _safe(lambda: g.get_activity_details(activity_id, maxchart=4000, maxpoly=8000), {}) or {}
    descs = det.get("metricDescriptors", []) or []
    rows = det.get("activityDetailMetrics", []) or []
    if not descs or not rows:
        return pd.DataFrame()

    idx_to_key = {d["metricsIndex"]: d.get("key") for d in descs}
    n = max(idx_to_key) + 1
    cols = [idx_to_key.get(i, f"m{i}") for i in range(n)]
    df = pd.DataFrame([r.get("metrics", []) for r in rows], columns=cols)

    # Derive friendly columns (guarding against missing raw fields).
    def col(name):
        return df[name] if name in df else pd.Series([None] * len(df))

    out = pd.DataFrame({
        "distance_km": pd.to_numeric(col("sumDistance"), errors="coerce") / 1000,
        "elapsed_s": pd.to_numeric(col("sumElapsedDuration"), errors="coerce"),
        "hr": pd.to_numeric(col("directHeartRate"), errors="coerce"),
        "elevation_m": pd.to_numeric(col("directElevation"), errors="coerce"),
        "speed_mps": pd.to_numeric(col("directSpeed"), errors="coerce"),
        "cadence_spm": pd.to_numeric(col("directRunCadence"), errors="coerce"),
        "power_w": pd.to_numeric(col("directPower"), errors="coerce"),
        "stride_cm": pd.to_numeric(col("directStrideLength"), errors="coerce"),
        "gct_ms": pd.to_numeric(col("directGroundContactTime"), errors="coerce"),
        "vert_osc_cm": pd.to_numeric(col("directVerticalOscillation"), errors="coerce"),
        "stamina": pd.to_numeric(col("directAvailableStamina"), errors="coerce"),
        "lat": pd.to_numeric(col("directLatitude"), errors="coerce"),
        "lon": pd.to_numeric(col("directLongitude"), errors="coerce"),
    })
    # Pace (min/km) from speed; ignore near-zero speed to avoid infinities.
    out["pace_min_km"] = out["speed_mps"].where(out["speed_mps"] > 0.3).rdiv(1000 / 60)
    return out


def fetch_splits(g, activity_id: int) -> pd.DataFrame:
    """Per-km / per-lap splits for one activity."""
    data = _safe(lambda: g.get_activity_splits(activity_id), {}) or {}
    laps = data.get("lapDTOs") or data.get("splits") or []
    rows = []
    for i, lap in enumerate(laps, 1):
        dist = lap.get("distance") or 0
        dur = lap.get("duration") or lap.get("movingDuration") or 0
        rows.append({
            "lap": i,
            "distance_km": dist / 1000 if dist else None,
            "duration_min": dur / 60 if dur else None,
            "pace_min_km": (dur / 60) / (dist / 1000) if dist and dur else None,
            "avg_hr": lap.get("averageHR"),
            "max_hr": lap.get("maxHR"),
            "avg_cadence": lap.get("averageRunCadence"),
            "elev_gain_m": lap.get("elevationGain"),
            "avg_power_w": lap.get("averagePower"),
        })
    return pd.DataFrame(rows)


_STAGE_LABEL = {0.0: "Deep", 1.0: "Light", 2.0: "REM", 3.0: "Awake"}
_STAGE_RANK = {"Deep": 0, "Light": 1, "REM": 2, "Awake": 3}


def _series_df(items, offset_ms=0):
    """Convert Garmin [{'value':v,'startGMT':ms}, ...] to a time/value frame."""
    if not items:
        return pd.DataFrame(columns=["time", "value"])
    df = pd.DataFrame(items)
    if "startGMT" in df:
        df["time"] = pd.to_datetime(df["startGMT"] + offset_ms, unit="ms")
    df["value"] = pd.to_numeric(df.get("value"), errors="coerce")
    return df[["time", "value"]].dropna()


def fetch_sleep_detail(g, day: str) -> dict:
    """Full single-night sleep breakdown: stages, scores, overnight physiology."""
    s = _safe(lambda: g.get_sleep_data(day), {}) or {}
    dto = s.get("dailySleepDTO") or {}
    if not dto.get("sleepTimeSeconds"):
        return {}

    # Local-clock offset (timestamps come back as GMT epoch ms).
    try:
        offset = int(dto["sleepStartTimestampLocal"]) - int(dto["sleepStartTimestampGMT"])
    except Exception:
        offset = 0

    scores = dto.get("sleepScores") or {}

    # Hypnogram from sleepLevels.
    stages = []
    for lvl in s.get("sleepLevels") or []:
        label = _STAGE_LABEL.get(lvl.get("activityLevel"))
        if not label:
            continue
        start = pd.to_datetime(lvl["startGMT"]) + pd.Timedelta(milliseconds=offset)
        end = pd.to_datetime(lvl["endGMT"]) + pd.Timedelta(milliseconds=offset)
        stages.append({"start": start, "end": end, "stage": label,
                       "rank": _STAGE_RANK[label]})
    stages_df = pd.DataFrame(stages)

    return {
        "score": (scores.get("overall") or {}).get("value"),
        "score_qualifier": (scores.get("overall") or {}).get("qualifierKey"),
        "qualifiers": {k: (v or {}).get("qualifierKey")
                       for k, v in scores.items() if isinstance(v, dict)},
        "sleep_h": (dto.get("sleepTimeSeconds") or 0) / 3600,
        "deep_h": (dto.get("deepSleepSeconds") or 0) / 3600,
        "light_h": (dto.get("lightSleepSeconds") or 0) / 3600,
        "rem_h": (dto.get("remSleepSeconds") or 0) / 3600,
        "awake_h": (dto.get("awakeSleepSeconds") or 0) / 3600,
        "resting_hr": dto.get("restingHeartRate"),
        "avg_hr": dto.get("avgHeartRate"),
        "avg_stress": dto.get("avgSleepStress"),
        "respiration": dto.get("averageRespirationValue"),
        "resp_low": dto.get("lowestRespirationValue"),
        "resp_high": dto.get("highestRespirationValue"),
        "awake_count": dto.get("awakeCount"),
        "overnight_hrv": s.get("avgOvernightHrv"),
        "hrv_status": s.get("hrvStatus"),
        "bb_change": s.get("bodyBatteryChange"),
        "skin_temp_dev_c": s.get("avgSkinTempDeviationC"),
        "sleep_need_actual": (dto.get("sleepNeed") or {}).get("actual"),
        "sleep_need_baseline": (dto.get("sleepNeed") or {}).get("baseline"),
        "feedback": (dto.get("sleepScoreFeedback") or "").replace("_", " ").title(),
        "stages": stages_df,
        "hr_series": _series_df(s.get("sleepHeartRate"), offset),
        "stress_series": _series_df(s.get("sleepStress"), offset),
        "bb_series": _series_df(s.get("sleepBodyBattery"), offset),
    }


def fetch_hrv_detail(g, day: str) -> dict:
    """Overnight HRV: summary, baseline range, and per-reading series."""
    h = _safe(lambda: g.get_hrv_data(day), {}) or {}
    summary = h.get("hrvSummary") or {}
    readings = h.get("hrvReadings") or []
    rdf = pd.DataFrame(readings)
    if not rdf.empty:
        rdf["time"] = pd.to_datetime(rdf["readingTimeLocal"], errors="coerce")
        rdf = rdf.rename(columns={"hrvValue": "value"})[["time", "value"]].dropna()
    return {"summary": summary, "baseline": summary.get("baseline") or {}, "readings": rdf}


def _pretty(cat) -> str:
    return (cat or "Unknown").replace("_", " ").title()


def fetch_strength(g, limit: int = 60) -> dict:
    """All strength sessions + per-category breakdowns from one activities pull.

    summarizedExerciseSets is embedded in each activity, so no per-session calls.
    """
    acts = _safe(lambda: g.get_activities(0, limit), []) or []
    strength = [a for a in acts
                if "strength" in (a.get("activityType") or {}).get("typeKey", "")]

    sessions, by_session, all_cats = [], {}, []
    for a in strength:
        aid = a.get("activityId")
        sessions.append({
            "activity_id": aid,
            "name": a.get("activityName"),
            "start": a.get("startTimeLocal"),
            "duration_min": (a.get("duration") or 0) / 60 or None,
            "total_sets": a.get("totalSets"),
            "active_sets": a.get("activeSets"),
            "total_reps": a.get("totalReps"),
            "training_load": a.get("activityTrainingLoad"),
            "calories": a.get("calories"),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            **{f"z{i}": a.get(f"hrTimeInZone_{i}") for i in range(1, 6)},
        })
        rows = []
        for s in a.get("summarizedExerciseSets") or []:
            cat = _pretty(s.get("subCategory") or s.get("category"))
            row = {
                "category": cat,
                "reps": s.get("reps") or 0,
                "sets": s.get("sets") or 0,
                "duration_min": (s.get("duration") or 0) / 60000,  # ms -> min
                "max_weight": s.get("maxWeight") or 0,
            }
            rows.append(row)
            all_cats.append({**row, "activity_id": aid})
        by_session[aid] = pd.DataFrame(rows)

    sdf = pd.DataFrame(sessions)
    if not sdf.empty:
        sdf["start"] = pd.to_datetime(sdf["start"], errors="coerce")
        sdf = sdf.sort_values("start", ascending=False).reset_index(drop=True)

    cat_df = pd.DataFrame(all_cats)
    if not cat_df.empty:
        cat_totals = (cat_df.groupby("category", as_index=False)
                      .agg(reps=("reps", "sum"), sets=("sets", "sum"),
                           sessions=("activity_id", "nunique"))
                      .sort_values("reps", ascending=False))
    else:
        cat_totals = pd.DataFrame(columns=["category", "reps", "sets", "sessions"])

    return {"sessions": sdf, "by_session": by_session, "category_totals": cat_totals}


def fetch_exercise_sets(g, activity_id: int) -> pd.DataFrame:
    """Set-by-set log for one strength session (active + rest)."""
    es = _safe(lambda: g.get_activity_exercise_sets(activity_id), {}) or {}
    rows = []
    for i, s in enumerate(es.get("exerciseSets") or [], 1):
        ex = (s.get("exercises") or [{}])[0]
        cat = ex.get("category")
        rows.append({
            "set": i,
            "type": s.get("setType"),
            "exercise": _pretty(ex.get("name") or cat) if cat and cat != "UNKNOWN" else "—",
            "reps": s.get("repetitionCount"),
            "weight_kg": s.get("weight"),
            "duration_s": s.get("duration"),
        })
    return pd.DataFrame(rows)


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
