"""
Local SQLite cache for daily Garmin metrics.

Daily history rarely changes once a day is over, so we fetch each day from
Garmin ONCE and store it in a local SQLite file. Subsequent loads read from disk
(instant) and only the most recent days are re-fetched live (today's totals are
still accumulating). This turns "long history is slow every time" into "slow once".

Rows are stored as JSON keyed by ISO date, so the schema can evolve freely.
"""

import json
import os
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from io import StringIO

import pandas as pd

import garmin_data as gd

DB_PATH = os.getenv("GARMIN_DB", os.path.join(os.path.dirname(__file__), "garmin.db"))
FRESH_DAYS = 2  # always re-fetch the most recent N days (today/yesterday still change)


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS daily (date TEXT PRIMARY KEY, data TEXT)")
    # Generic blob store for immutable per-activity data (streams/splits/sets).
    conn.execute("CREATE TABLE IF NOT EXISTS blobs (key TEXT PRIMARY KEY, data TEXT)")
    return conn


def _cached_df(g, key: str, fetch):
    """Return a DataFrame for `key` from the blob cache, fetching+storing on miss.

    Used for activity data that never changes once recorded, so we cache forever.
    """
    with closing(_conn()) as conn:
        row = conn.execute("SELECT data FROM blobs WHERE key = ?", (key,)).fetchone()
        if row is not None:
            return pd.read_json(StringIO(row[0]), orient="split")
        df = fetch()
        conn.execute("INSERT OR REPLACE INTO blobs(key, data) VALUES (?, ?)",
                     (key, df.to_json(orient="split")))
        conn.commit()
        return df


def cached_streams(g, activity_id: int):
    return _cached_df(g, f"streams:{activity_id}",
                      lambda: gd.fetch_activity_streams(g, activity_id))


def cached_splits(g, activity_id: int):
    return _cached_df(g, f"splits:{activity_id}",
                      lambda: gd.fetch_splits(g, activity_id))


def cached_exercise_sets(g, activity_id: int):
    return _cached_df(g, f"sets:{activity_id}",
                      lambda: gd.fetch_exercise_sets(g, activity_id))


def _date_list(start: date, end: date):
    out, d = [], start
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def cached_daily(g, start: date, end: date):
    """Return the daily metrics frame for [start, end], fetching only missing/stale days."""
    days = _date_list(start, end)
    # Anything on/after this date is considered "fresh" and re-fetched live.
    fresh_from = (date.today() - timedelta(days=FRESH_DAYS - 1)).isoformat()

    with closing(_conn()) as conn:
        placeholders = ",".join("?" * len(days))
        cached = {d: json.loads(j) for d, j in conn.execute(
            f"SELECT date, data FROM daily WHERE date IN ({placeholders})", days).fetchall()}

        rows, to_store = {}, []
        for d in days:
            if d in cached and d < fresh_from:
                rows[d] = cached[d]            # frozen past day → use cache
            else:
                row = gd.fetch_daily_one(g, d)  # missing or recent → fetch live
                rows[d] = row
                to_store.append((d, json.dumps(row)))

        if to_store:
            conn.executemany("INSERT OR REPLACE INTO daily(date, data) VALUES (?, ?)", to_store)
            conn.commit()

    return gd.daily_frame([rows[d] for d in days])


def cache_stats():
    """(row_count, min_date, max_date) for the daily cache — for diagnostics/UI."""
    with closing(_conn()) as conn:
        n = conn.execute("SELECT COUNT(*) FROM daily").fetchone()[0]
        rng = conn.execute("SELECT MIN(date), MAX(date) FROM daily").fetchone()
    return n, rng[0], rng[1]


def clear_cache():
    with closing(_conn()) as conn:
        conn.execute("DELETE FROM daily")
        conn.execute("DELETE FROM blobs")
        conn.commit()


if __name__ == "__main__":
    from garmin_client import get_client
    g = get_client()
    end = date.today()
    df = cached_daily(g, end - timedelta(days=13), end)
    print(df[["date", "resting_hr", "hrv_avg", "sleep_hours"]].tail().to_string(index=False))
    print("cache:", cache_stats())
