"""
Pull a single day of Garmin data to confirm the connection and inspect available fields.

Usage:
    ./.venv/bin/python peek.py            # today
    ./.venv/bin/python peek.py 2026-06-15 # a specific day
"""

import json
import sys
from datetime import date

from garmin_client import get_client


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    g = get_client()
    print(f"Connected as: {g.get_full_name()}\n")

    # A grab-bag of the most useful daily endpoints. Each is wrapped so one
    # failing (e.g. no device data that day) doesn't kill the rest.
    pulls = {
        "stats (steps/calories/etc)": lambda: g.get_stats(day),
        "heart_rate": lambda: g.get_heart_rates(day),
        "sleep": lambda: g.get_sleep_data(day),
        "stress": lambda: g.get_stress_data(day),
        "body_battery": lambda: g.get_body_battery(day, day),
        "hrv": lambda: g.get_hrv_data(day),
        "steps_intraday": lambda: g.get_steps_data(day),
        "activities (last 5)": lambda: g.get_activities(0, 5),
    }

    for label, fn in pulls.items():
        try:
            data = fn()
            preview = json.dumps(data, indent=2, default=str)
            if len(preview) > 1500:
                preview = preview[:1500] + "\n  ... (truncated)"
            print(f"===== {label} =====\n{preview}\n")
        except Exception as e:
            print(f"===== {label} =====\n  (unavailable: {e})\n")


if __name__ == "__main__":
    main()
