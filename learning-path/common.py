"""
Shared helpers for every lesson.

Credentials come ONLY from environment variables (never hardcode them):
    export DHAN_CLIENT_ID=1100000000
    export DHAN_ACCESS_TOKEN=eyJ...

Safety: nothing in this folder places a real order unless you pass --live
AND type YES at the prompt. Default is DRY RUN (prints what would be sent).
"""

import os
import sys
import time
from datetime import datetime, time as dtime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

# Well-known security IDs (verify in the instrument master before going live)
SECURITY = {
    "NIFTY":     {"id": "13",   "segment": "IDX_I",  "type": "INDEX"},
    "BANKNIFTY": {"id": "25",   "segment": "IDX_I",  "type": "INDEX"},
    "RELIANCE":  {"id": "2885", "segment": "NSE_EQ", "type": "EQUITY"},
    "HDFCBANK":  {"id": "1333", "segment": "NSE_EQ", "type": "EQUITY"},
}


def env(name, required=True):
    value = os.environ.get(name, "").strip()
    if required and not value:
        sys.exit(f"Missing environment variable {name}. See learning-path/README.md -> Lesson 0.")
    return value


TOKEN_FILE = os.path.expanduser(os.environ.get("DHAN_TOKEN_FILE", "~/.dhan_token"))


def access_token():
    """DHAN_ACCESS_TOKEN env var, else the file written by 10_automation/refresh_token.py."""
    token = env("DHAN_ACCESS_TOKEN", required=False)
    if not token and os.path.exists(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()
    if not token:
        sys.exit("No access token. Set DHAN_ACCESS_TOKEN or run 10_automation/refresh_token.py")
    return token


def dhan_context():
    from dhanhq import DhanContext
    return DhanContext(env("DHAN_CLIENT_ID"), access_token())


def dhan_client():
    """Raw official SDK (DhanHQ-py)."""
    from dhanhq import dhanhq
    return dhanhq(dhan_context())


def tradehull_client():
    """Tradehull wrapper. Returns None if the package is not installed."""
    try:
        from Dhan_Tradehull import Tradehull
    except ImportError:
        print("  (Dhan-Tradehull not installed: pip install Dhan-Tradehull -> skipping wrapper side)")
        return None
    return Tradehull(env("DHAN_CLIENT_ID"), access_token())


def unwrap(resp):
    """
    DhanHQ-py returns {'status', 'remarks', 'data'}. Some endpoints nest
    another {'data': ...} inside. Return the innermost payload or raise.
    """
    if resp.get("status") != "success":
        raise RuntimeError(f"Dhan API error: {resp.get('remarks')}")
    data = resp.get("data")
    if isinstance(data, dict) and "data" in data and len(data) <= 3:
        return data["data"]
    return data


def timed(label, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    print(f"  [{label}] {1000 * (time.perf_counter() - start):.0f} ms")
    return result


def now_ist():
    return datetime.now(IST)


def market_open(ts=None):
    ts = ts or now_ist()
    return ts.weekday() < 5 and dtime(9, 15) <= ts.time() <= dtime(15, 30)


def confirm_live(args):
    """Return True only if --live was passed and the user typed YES."""
    if not getattr(args, "live", False):
        print("\n  DRY RUN - no order sent. Re-run with --live to send for real.\n")
        return False
    if os.environ.get("DHAN_LIVE_CONFIRM") == "YES":       # unattended (cron/systemd)
        return True
    answer = input("\n  LIVE ORDER. Real money. Type YES to send: ").strip()
    return answer == "YES"


def candles_to_df(payload):
    """Dhan historical payload (dict of lists) -> pandas DataFrame indexed by IST time."""
    import pandas as pd
    df = pd.DataFrame({k: payload[k] for k in ("open", "high", "low", "close", "volume") if k in payload})
    df.index = pd.to_datetime(payload["timestamp"], unit="s", utc=True).tz_convert("Asia/Kolkata")
    df.index.name = "time"
    return df
