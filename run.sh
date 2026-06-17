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

# 3) Start the local AI server (Ollama) if installed and not already running.
OLLAMA="${OLLAMA_BIN:-$HOME/.local/bin/ollama}"
[ -x "$OLLAMA" ] || OLLAMA="$(command -v ollama || true)"
if [ -n "$OLLAMA" ] && ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Starting local AI server (Ollama)…"
  nohup "$OLLAMA" serve > "${TMPDIR:-/tmp}/ollama.log" 2>&1 &
fi

# 4) Launch.
exec ./.venv/bin/streamlit run Home.py
