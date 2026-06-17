"""Print the STRUCTURE (keys + types) of key Garmin endpoints — not the values.

Used during development to build pages against real field names without dumping
personal data into logs. Values are replaced with their type/length.
"""

from datetime import date, timedelta
from garmin_client import get_client


def shape(obj, depth=0, maxd=3):
    pad = "  " * depth
    if isinstance(obj, dict):
        if depth >= maxd:
            return f"{{...{len(obj)} keys...}}"
        lines = []
        for k, v in list(obj.items())[:40]:
            lines.append(f"\n{pad}  {k}: {shape(v, depth+1, maxd)}")
        return "{" + "".join(lines) + "\n" + pad + "}"
    if isinstance(obj, list):
        head = shape(obj[0], depth+1, maxd) if obj else "empty"
        return f"[list len={len(obj)} of {head}]"
    if isinstance(obj, str):
        return f"str(len {len(obj)})"
    return type(obj).__name__


def main():
    g = get_client()
    today = date.today().isoformat()

    # Find a recent activity id to drill into.
    acts = g.get_activities(0, 1)
    act_id = acts[0]["activityId"] if acts else None

    probes = {
        "get_max_metrics(today)": lambda: g.get_max_metrics(today),
        "get_race_predictions()": lambda: g.get_race_predictions(),
        "get_training_status(today)": lambda: g.get_training_status(today),
        "get_training_readiness(today)": lambda: g.get_training_readiness(today),
        "get_activities(0,1)[0]": lambda: acts[0] if acts else None,
        "get_activity_splits(id)": lambda: g.get_activity_splits(act_id) if act_id else None,
    }
    for label, fn in probes.items():
        print(f"\n===== {label} =====")
        try:
            print(shape(fn()))
        except Exception as e:
            print(f"(error: {e})")

    # Activity details: show metric descriptor names only (the time-series keys).
    if act_id:
        print(f"\n===== get_activity_details(id) metric descriptors =====")
        try:
            det = g.get_activity_details(act_id, maxchart=1, maxpoly=1)
            descs = det.get("metricDescriptors", [])
            print("top-level keys:", list(det.keys()))
            print("metrics:", [d.get("key") for d in descs])
        except Exception as e:
            print(f"(error: {e})")


if __name__ == "__main__":
    main()
