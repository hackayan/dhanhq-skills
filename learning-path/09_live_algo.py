"""
Lesson 9 - Go live, small. Same engine as paper, real LIMIT orders.

Pre-flight checklist (the script refuses to start without the confirmation):
  [ ] strategy PASSED lesson 7 out-of-sample
  [ ] paper traded 2+ weeks, results similar to backtest
  [ ] static IP whitelisted on Dhan, script runs FROM that machine
  [ ] P&L exit set for today (lesson 5) - server-side seat belt
  [ ] qty = 1 share / 1 lot to start

    python 09_live_algo.py --strategy supertrend --symbol RELIANCE --qty 1
    # unattended (systemd/cron): export DHAN_LIVE_CONFIRM=YES  and add --once for timers
"""

import argparse
import os

from engine import Bot
from strategies import STRATEGIES

p = argparse.ArgumentParser()
p.add_argument("--strategy", choices=STRATEGIES, required=True)
p.add_argument("--symbol", default="RELIANCE", choices=["RELIANCE", "HDFCBANK"])
p.add_argument("--interval", type=int, default=5, choices=[1, 5, 15, 25, 60])
p.add_argument("--qty", type=int, default=1)
p.add_argument("--product", default="INTRADAY", choices=["INTRADAY", "CNC"])
p.add_argument("--max-trades", type=int, default=2)
p.add_argument("--max-notional", type=float, default=50000)
p.add_argument("--once", action="store_true")
args = p.parse_args()

if os.environ.get("DHAN_LIVE_CONFIRM") != "YES":
    print(__doc__)
    if input("Real money. Type YES to start live trading: ").strip() != "YES":
        raise SystemExit("aborted")

Bot(args.symbol, args.strategy, args.interval, args.qty, args.product,
    args.max_trades, args.max_notional, live=True, journal="journal_live.csv").run(once=args.once)
