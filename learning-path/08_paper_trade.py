"""
Lesson 8 - Paper trade: the SAME strategy code as the backtest, on live
candles, with simulated fills. No real orders. Run it for 2+ weeks.

    python 08_paper_trade.py --strategy supertrend --symbol RELIANCE --interval 5
    python 08_paper_trade.py --strategy supertrend --once     # single step (for cron / systemd timer)
    python 08_paper_trade.py --summary                        # P&L from journal.csv

Graduate to lesson 9 only if paper results look like the backtest
(similar win %, avg win/loss). If they don't, the backtest was too optimistic.
"""

import argparse

from engine import Bot, journal_summary
from strategies import STRATEGIES

p = argparse.ArgumentParser()
p.add_argument("--strategy", choices=STRATEGIES, default="supertrend")
p.add_argument("--symbol", default="RELIANCE", choices=["RELIANCE", "HDFCBANK"])
p.add_argument("--interval", type=int, default=5, choices=[1, 5, 15, 25, 60])
p.add_argument("--qty", type=int, default=1)
p.add_argument("--product", default="INTRADAY", choices=["INTRADAY", "CNC"])
p.add_argument("--max-trades", type=int, default=3)
p.add_argument("--once", action="store_true")
p.add_argument("--summary", action="store_true")
args = p.parse_args()

if args.summary:
    journal_summary()
else:
    Bot(args.symbol, args.strategy, args.interval, args.qty, args.product,
        args.max_trades, max_notional=10**9, live=False).run(once=args.once)
