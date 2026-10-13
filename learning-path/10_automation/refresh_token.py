"""
Daily token refresh with PIN + TOTP, so nothing needs a human each morning.

One-time setup on Dhan web: enable TOTP for API login and copy the TOTP secret.
    export DHAN_CLIENT_ID=...  DHAN_PIN=...  DHAN_TOTP_SECRET=...
    pip install pyotp
    python refresh_token.py        # writes ~/.dhan_token (chmod 600); lessons read it automatically

Schedule at 08:30 on weekdays (see crontab.txt).
"""

import os
import sys

import pyotp
from dhanhq import DhanLogin

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import TOKEN_FILE, env  # noqa: E402

resp  = DhanLogin(env("DHAN_CLIENT_ID")).generate_token(env("DHAN_PIN"), pyotp.TOTP(env("DHAN_TOTP_SECRET")).now())
token = resp.get("accessToken") or resp.get("access_token")
if not token:
    sys.exit(f"token refresh failed: {resp}")

fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(token)
print(f"token saved to {TOKEN_FILE}")
