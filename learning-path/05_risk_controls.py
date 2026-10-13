"""
Lesson 5 - Risk controls that run on Dhan's server (not in your script).

Learn: positions, live P&L, P&L-based auto exit, kill switch.
These are your seat belt: they still protect you if your laptop/VPS dies.

    python 05_risk_controls.py                                   # read-only status
    python 05_risk_controls.py --set-pnl-exit 1000 800 --live    # +1000 / -800 auto square-off
"""

import argparse

from common import confirm_live, dhan_client, unwrap

p = argparse.ArgumentParser()
p.add_argument("--set-pnl-exit", nargs=2, type=float, metavar=("PROFIT", "LOSS"))
p.add_argument("--live", action="store_true")
args = p.parse_args()

dhan = dhan_client()

positions = unwrap(dhan.get_positions()) or []
total     = 0.0
print("\nOPEN POSITIONS")
for pos in positions:
    pnl    = float(pos.get("realizedProfit", 0)) + float(pos.get("unrealizedProfit", 0))
    total += pnl
    print(f"  {pos.get('tradingSymbol'):<30} qty {pos.get('netQty'):>6}  P&L {pnl:>10.2f}")
print(f"  TOTAL P&L today: {total:.2f}")

print("\nKILL SWITCH status :", dhan.status_kill_switch().get("data"))
print("P&L EXIT  status   :", dhan.get_pnl_exit().get("data"))

if args.set_pnl_exit:
    profit, loss = args.set_pnl_exit
    print(f"\nWould set: exit all INTRADAY when P&L >= +{profit} or <= -{loss}, then kill switch ON")
    if confirm_live(args):
        print(dhan.set_pnl_exit(profit, loss, ["INTRADAY"], enable_kill_switch=True))

print("""
WHAT YOU LEARNED
- Server-side protections (P&L exit, kill switch, super-order SL) beat
  script-side checks: they work even when your code crashes or loses internet.
- Tradehull equivalent: tsl.enable_pnl_based_exit(profit_value=..., loss_value=...,
  product_types=("INTRADAY",), enable_kill_switch=True)
- Automate: set the P&L exit EVERY MORNING (09:10) before your algo starts.
  Make "max daily loss" a rule you decide once, not in the heat of the moment.
""")
