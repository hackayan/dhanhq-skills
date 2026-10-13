"""
Lesson 3 - Option chain: expiries, ATM strike, OI, PCR, max pain (read-only).

Learn: reading the chain, picking strikes, reading sentiment from OI.
Compare: raw dhanhq (nested dict keyed by strike string) vs Tradehull (one DataFrame + ATM).

    python 03_option_chain.py --underlying NIFTY
Rate limit: 1 option-chain request per 3 seconds.
"""

import argparse
import time

import pandas as pd

from common import SECURITY, dhan_client, timed, tradehull_client, unwrap

p = argparse.ArgumentParser()
p.add_argument("--underlying", default="NIFTY", choices=["NIFTY", "BANKNIFTY"])
p.add_argument("--strikes", type=int, default=10, help="strikes each side of ATM to show")
args = p.parse_args()

sec  = SECURITY[args.underlying]
dhan = dhan_client()

print(f"\n=== RAW dhanhq: {args.underlying} ===")
expiries = unwrap(timed("expiry_list", dhan.expiry_list, int(sec["id"]), sec["segment"]))
expiry   = expiries[0]
print("  nearest expiries:", expiries[:4])
time.sleep(3)

chain = unwrap(timed("option_chain", dhan.option_chain, int(sec["id"]), sec["segment"], expiry))
spot  = chain["last_price"]

rows = []
for strike, legs in chain["oc"].items():
    ce, pe = legs.get("ce", {}), legs.get("pe", {})
    rows.append({
        "strike":   float(strike),
        "ce_ltp":   ce.get("last_price"), "ce_oi": ce.get("oi", 0), "ce_iv": ce.get("implied_volatility"),
        "ce_delta": ce.get("greeks", {}).get("delta"),
        "pe_ltp":   pe.get("last_price"), "pe_oi": pe.get("oi", 0), "pe_iv": pe.get("implied_volatility"),
        "pe_delta": pe.get("greeks", {}).get("delta"),
    })
df  = pd.DataFrame(rows).sort_values("strike").reset_index(drop=True)
atm = df.loc[(df["strike"] - spot).abs().idxmin(), "strike"]

# Max pain = strike where option writers pay out the least at expiry
pain = {k: ((k - df["strike"]).clip(lower=0) * df["ce_oi"]).sum()
           + ((df["strike"] - k).clip(lower=0) * df["pe_oi"]).sum() for k in df["strike"]}

i    = df.index[df["strike"] == atm][0]
view = df.iloc[max(0, i - args.strikes): i + args.strikes + 1]
print(f"  spot {spot}  ATM {atm}  expiry {expiry}")
print(view.to_string(index=False))
print(f"  PCR (put OI / call OI) : {df['pe_oi'].sum() / max(df['ce_oi'].sum(), 1):.2f}")
print(f"  resistance (max CE OI) : {df.loc[df['ce_oi'].idxmax(), 'strike']}")
print(f"  support    (max PE OI) : {df.loc[df['pe_oi'].idxmax(), 'strike']}")
print(f"  max pain               : {min(pain, key=pain.get)}")

print("\n=== TRADEHULL wrapper ===")
tsl = tradehull_client()
if tsl:
    atm_t, chain_t = timed("get_option_chain", tsl.get_option_chain,
                           Underlying=args.underlying, exchange="INDEX", expiry=0, num_strikes=args.strikes)
    print("  ATM:", atm_t)
    print(chain_t[["CE OI", "CE LTP", "Strike Price", "PE LTP", "PE OI"]].to_string(index=False))
    print("  ATM symbols:", tsl.ATM_Strike_Selection(Underlying=args.underlying, Expiry=0))

print("""
WHAT YOU LEARNED
- PCR > 1.2 often read as bullish (put writers confident), < 0.7 bearish. It is
  context, not a signal on its own - backtest before trusting it.
- Strike selection (ATM/OTM/ITM) is where Tradehull saves the most code:
  ATM_Strike_Selection() returns tradable symbol names directly.
- Automate: a 09:20 and 14:30 snapshot of PCR / max pain / support-resistance
  saved to CSV. Building option-buying/selling algos comes AFTER you have
  a backtested edge (lesson 7) - options lose money fast without one.
""")
