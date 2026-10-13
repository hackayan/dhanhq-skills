"""
Lesson 6 - Live prices: WebSocket stream vs REST polling.

Learn: why live algos should stream, not poll. Runs each method for N seconds
and counts how many price updates you got.

    python 06_live_feed.py --seconds 20       # run during market hours
"""

import argparse
import time

from common import SECURITY, dhan_client, dhan_context, unwrap

p = argparse.ArgumentParser()
p.add_argument("--symbol", default="RELIANCE", choices=["RELIANCE", "HDFCBANK"])
p.add_argument("--seconds", type=int, default=20)
args = p.parse_args()
sec = SECURITY[args.symbol]

# ---- 1) REST polling (quote APIs allow ~1 request / second)
dhan, polls, last = dhan_client(), 0, None
end = time.time() + args.seconds
while time.time() < end:
    data  = unwrap(dhan.ticker_data({sec["segment"]: [int(sec["id"])]}))
    last  = data[sec["segment"]][sec["id"]]["last_price"]
    polls += 1
    time.sleep(1.05)
print(f"\nPOLLING  : {polls} updates in {args.seconds}s, last {last}")

# ---- 2) WebSocket stream
from dhanhq import MarketFeed

feed  = MarketFeed(dhan_context(), [(MarketFeed.NSE, sec["id"], MarketFeed.Ticker)], "v2")
ticks = 0
end   = time.time() + args.seconds
try:
    while time.time() < end:
        feed.run_forever()
        msg = feed.get_data()
        if msg and msg.get("type") == "Ticker Data":
            ticks, last = ticks + 1, msg["LTP"]
finally:
    feed.close_connection()
print(f"WEBSOCKET: {ticks} updates in {args.seconds}s, last {last}")

print("""
WHAT YOU LEARNED
- WebSocket pushes every trade tick; polling is capped by rate limits and
  burns your quota. Use WebSocket for anything tick-driven (trailing SL,
  scalping, live dashboards); use REST candles for candle-close strategies.
- Up to 5 WebSocket connections per user. Also see OrderUpdate (order fills
  pushed to you) in DhanHQ-py/examples.
- Automate: reconnect logic (wrap in try/except + retry) is mandatory for
  anything running all day.
""")
