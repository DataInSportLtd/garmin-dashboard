#!/usr/bin/env bash
# Launch the Garmin dashboard.
#   - Creates a local virtualenv + installs deps on first run.
#   - Logs in to Garmin on first run (prompts for credentials), then reuses the
#     cached token in ~/.garminconnect.
# Works from wherever this repo is cloned — no hardcoded paths.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

# 1) Bootstrap the virtualenv if it doesn't exist yet.
if [ ! -d ".venv" ]; then
  echo "Setting up Python environment (one-time)…"
  "$PY" -m venv .venv
  ./.venv/bin/python -m pip install --quiet --upgrade pip
  ./.venv/bin/python -m pip install --quiet -r requirements.txt
fi

# 2) Ensure we have a Garmin session token before launching the UI.
TOKENSTORE="${GARMINTOKENS:-$HOME/.garminconnect}"
if [ ! -d "$TOKENSTORE" ]; then
  echo "First run — logging in to Garmin Connect…"
  ./.venv/bin/python garmin_client.py
fi

# 3) Launch.
exec ./.venv/bin/streamlit run Home.py
