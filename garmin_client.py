"""
Reusable Garmin Connect client (garminconnect >= 0.3.x).

Auth strategy:
  1. Try to resume from a cached token (~/.garminconnect by default) -> no password.
  2. If that fails, log in with email + password (prompted, never stored in code).
     MFA, if the account requires it, is handled via the prompt_mfa callback.
     login() then auto-persists the token to the tokenstore for next time.

Usage:
    from garmin_client import get_client
    g = get_client()
    print(g.get_full_name())
"""

import os
from getpass import getpass

from garminconnect import Garmin

TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))


def _mfa_prompt() -> str:
    return input("MFA one-time code: ").strip()


def get_client(tokenstore: str = TOKENSTORE) -> Garmin:
    """Return an authenticated Garmin client, reusing a cached token if available."""
    # 1) Try cached tokens only (no credentials needed).
    try:
        garmin = Garmin()
        garmin.login(tokenstore)
        garmin.get_full_name()  # cheap call to confirm the token is still valid
        return garmin
    except Exception:
        pass

    # 2) Fall back to a full credential login (token is auto-saved by login()).
    print("No valid cached session — logging in with credentials.")
    email = os.environ.get("GARMIN_EMAIL") or input("Garmin email: ")
    password = os.environ.get("GARMIN_PASSWORD") or getpass("Garmin password: ")

    garmin = Garmin(email=email, password=password, prompt_mfa=_mfa_prompt)
    garmin.login(tokenstore)  # persists tokens to `tokenstore` on success
    print(f"Logged in and saved session token to {tokenstore}")
    return garmin


if __name__ == "__main__":
    g = get_client()
    print(f"Connected as: {g.get_full_name()}")
