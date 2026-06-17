# Personal Garmin Dashboard

A self-hosted Streamlit dashboard for **your own** Garmin Connect data — sleep,
HRV, resting HR, steps, Body Battery, stress, and recent activities.

You run it on your own machine with your own Garmin login. **Your credentials
never leave your computer** — there's no shared server, no account to create
here, nothing sent to anyone else.

## Quick start

You need **Python 3.10+** and **git** installed.

```bash
git clone <REPO_URL> garmin-dashboard
cd garmin-dashboard
./run.sh
```

`run.sh` does everything on first run:
1. Creates a local Python environment and installs dependencies.
2. Asks for your **Garmin email + password** (and an MFA code if you use 2FA).
   The password is typed invisibly and is **not** stored — only a session token
   is cached, in `~/.garminconnect`.
3. Opens the dashboard in your browser (usually <http://localhost:8501>).

Every run after that skips straight to the dashboard. Stop it with **Ctrl + C**.

> **Windows:** run the steps in `run.sh` manually, or use Git Bash / WSL.
> Roughly: `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`,
> `.venv\Scripts\python garmin_client.py`, then
> `.venv\Scripts\streamlit run dashboard.py`.

## A note on how login works

This uses the community **`garminconnect`** library, which signs in with your
Garmin email + password (there is no official "Sign in with Garmin" for personal
projects). That's why this is distributed as **self-hosted code** rather than a
public website: a public site would mean trusting someone else with your Garmin
password. Running it yourself keeps your credentials on your own machine.

Because it uses unofficial endpoints, a metric can occasionally break when Garmin
changes their site. If a panel shows an error, run `peek.py` (below) to see the
current field names.

## AI Coach (optional, fully local)

The **AI Coach** page generates running / gym-rehab / daily-readiness guidance from
your data using a **local** model — nothing is sent to any cloud service. It needs
[Ollama](https://ollama.com):

```bash
# one-time: install Ollama (download the app from ollama.com), then pull a model
ollama pull qwen2.5:14b   # default — best plans (needs ~16GB RAM)
ollama pull llama3.1:8b   # lighter/faster alternative (~8GB RAM)
```

`run.sh` auto-starts the Ollama server if it's installed. Pick the model from the
sidebar on the AI Coach page, or set a default with `OLLAMA_MODEL`
(e.g. `export OLLAMA_MODEL=llama3.1:8b`). The other pages work fine without Ollama —
only the AI Coach page requires it.

## Files

| File | Purpose |
|------|---------|
| `run.sh`          | One-command setup + login + launch |
| `dashboard.py`    | The Streamlit UI |
| `garmin_data.py`  | Pulls a date range into tidy pandas DataFrames |
| `garmin_client.py`| Auth + token caching + MFA |
| `peek.py`         | CLI: dump one day of raw data to inspect fields |
| `requirements.txt`| Pinned dependencies |

## Handy commands

```bash
./.venv/bin/python garmin_client.py        # log in / refresh token
./.venv/bin/python peek.py 2026-06-15      # raw data for one day
./.venv/bin/python garmin_data.py          # 7-day frame smoke test
./.venv/bin/streamlit run dashboard.py     # launch UI directly
```

Avoid prompts by exporting credentials before running:

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="…"
./run.sh
```

Data is cached in-app for 15 minutes; use the **Refresh** button in the sidebar
to re-pull.

## License / disclaimer

For personal use. Not affiliated with or endorsed by Garmin. Use of the
unofficial Connect endpoints is at your own risk and subject to Garmin's terms.
