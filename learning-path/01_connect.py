"""
Lesson 1 - Connect and read your account (read-only, safe any time).

Learn: credentials, the response format, funds, and whether your token works.
Compare: raw dhanhq vs Tradehull wrapper for the same calls.

    python 01_connect.py
"""

from common import dhan_client, tradehull_client, timed, unwrap

print("\n=== RAW dhanhq ===")
dhan  = dhan_client()
funds = timed("get_fund_limits", dhan.get_fund_limits)
print("  full response keys:", list(funds.keys()))           # status / remarks / data
if funds["status"] != "success":
    print("  FAILED:", funds["remarks"])
    print("  -> token expired? regenerate it in Dhan web -> My Profile -> Access DhanHQ APIs")
    raise SystemExit(1)

f = unwrap(funds)
print(f"  available balance : {f.get('availabelBalance', f.get('availableBalance'))}")
print(f"  utilized amount   : {f.get('utilizedAmount')}")

positions = unwrap(timed("get_positions", dhan.get_positions)) or []
holdings  = dhan.get_holdings()
print(f"  open positions    : {len(positions)}")
print(f"  holdings status   : {holdings['status']}  (failure is normal if you hold no stock)")

print("\n=== TRADEHULL wrapper ===")
tsl = tradehull_client()
if tsl:
    print("  balance  :", timed("get_balance", tsl.get_balance))
    print("  live P&L :", timed("get_live_pnl", tsl.get_live_pnl))

print("""
WHAT YOU LEARNED
- Raw SDK returns a dict {status, remarks, data}; ALWAYS check status before using data.
- Tradehull returns plain values (float / DataFrame); shorter code, less control over errors.
- Access tokens expire. Automating this check every morning (08:45) is the
  FIRST thing worth automating: it tells you before market open if the algo can run.
""")
