"""Shared, cached data loaders used across all dashboard pages."""

from datetime import date

import streamlit as st

import garmin_data as gd
from garmin_client import get_client


@st.cache_resource(show_spinner=False)
def client():
    return get_client()


def ensure_auth():
    """Verify we're logged in; show a friendly message + stop if not."""
    try:
        return client().get_full_name()
    except Exception as e:
        st.error(
            "Could not authenticate with Garmin. Run a login first:\n\n"
            "```\ncd ~/garmin-dashboard\n./.venv/bin/python garmin_client.py\n```\n\n"
            f"Details: {e}"
        )
        st.stop()


@st.cache_data(ttl=900, show_spinner="Fetching daily metrics…")
def daily(start: date, end: date):
    return gd.fetch_daily(client(), start, end)


@st.cache_data(ttl=900, show_spinner="Fetching activities…")
def activities(limit: int = 50):
    return gd.fetch_activities(client(), limit)


@st.cache_data(ttl=900, show_spinner="Fetching runs…")
def runs(limit: int = 50):
    return gd.fetch_runs(client(), limit)


@st.cache_data(ttl=900, show_spinner="Fetching training status…")
def running_summary(day: str):
    return gd.fetch_running_summary(client(), day)


@st.cache_data(ttl=900, show_spinner="Fetching race predictions…")
def race_predictions():
    return gd.fetch_race_predictions(client())


@st.cache_data(ttl=900, show_spinner="Fetching training readiness…")
def training_readiness(day: str):
    return gd.fetch_training_readiness(client(), day)


@st.cache_data(ttl=1800, show_spinner="Loading run streams…")
def streams(activity_id: int):
    return gd.fetch_activity_streams(client(), activity_id)


@st.cache_data(ttl=1800, show_spinner="Loading splits…")
def splits(activity_id: int):
    return gd.fetch_splits(client(), activity_id)


@st.cache_data(ttl=1800, show_spinner="Loading sleep…")
def sleep_detail(day: str):
    return gd.fetch_sleep_detail(client(), day)


@st.cache_data(ttl=1800, show_spinner="Loading HRV…")
def hrv_detail(day: str):
    return gd.fetch_hrv_detail(client(), day)


@st.cache_data(ttl=1800, show_spinner="Loading strength sessions…")
def strength(limit: int = 60):
    return gd.fetch_strength(client(), limit)


@st.cache_data(ttl=1800, show_spinner="Loading set log…")
def exercise_sets(activity_id: int):
    return gd.fetch_exercise_sets(client(), activity_id)


def refresh_button(sidebar=True):
    target = st.sidebar if sidebar else st
    if target.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()
