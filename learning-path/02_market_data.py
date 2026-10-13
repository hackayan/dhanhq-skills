"""
Lesson 2 - Market data: LTP, OHLC, historical candles (read-only).

Learn: snapshot quotes vs historical candles; how timeframe choice works.
Compare: raw dhanhq (security IDs, epoch timestamps) vs Tradehull (symbol names, DataFrames).

    python 02_market_data.py
    python 02_market_data.py --symbol HDFCBANK --interval 15
"""

import argparse
from datetime import date, timedelta

from common import SECURITY, candles_to_df, dhan_client, timed, tradehull_client, unwrap

p = argparse.ArgumentParser()
p.add_argument("--symbol", default="RELIANCE", choices=SECURITY.keys())
p.add_argument("--interval", type=int, default=5, choices=[1, 5, 15, 25, 60])
args = p.parse_args()

sec   = SECURITY[args.symbol]
dhan  = dhan_client()
today = date.today()

print(f"\n=== RAW dhanhq: {args.symbol} (security_id={sec['id']}, segment={sec['segment']}) ===")

# 1) Snapshot LTP - quote APIs are limited to 1 request/second
ltp = unwrap(timed("ticker_data", dhan.ticker_data, {sec["segment"]: [int(sec["id"])]}))
print("  LTP payload:", ltp)

# 2) Daily candles - for swing/positional strategies and backtests
daily = unwrap(timed("historical_daily_data", dhan.historical_daily_data,
                     sec["id"], sec["segment"], sec["type"],
                     str(today - timedelta(days=365)), str(today)))
ddf = candles_to_df(daily)
print(f"  daily candles: {len(ddf)} rows, last close {ddf['close'].iloc[-1]}")

# 3) Intraday candles - for intraday strategies
intra = unwrap(timed("intraday_minute_data", dhan.intraday_minute_data,
                     sec["id"], sec["segment"], sec["type"],
                     str(today - timedelta(days=5)), str(today), args.interval))
idf = candles_to_df(intra)
print(f"  {args.interval}-min candles: {len(idf)} rows")
print(idf.tail(3))

ddf.to_csv(f"data_{args.symbol}_daily.csv")
idf.to_csv(f"data_{args.symbol}_{args.interval}m.csv")
print(f"  saved data_{args.symbol}_daily.csv and data_{args.symbol}_{args.interval}m.csv (used by lesson 7)")

print("\n=== TRADEHULL wrapper ===")
tsl = tradehull_client()
if tsl:
    name = args.symbol
    exch = "INDEX" if sec["type"] == "INDEX" else "NSE"
    print("  LTP:", timed("get_ltp_data", tsl.get_ltp_data, names=[name]))
    chart = timed("get_historical_data", tsl.get_historical_data,
                  tradingsymbol=name, exchange=exch, timeframe=str(args.interval))
    print(chart.tail(3) if chart is not None else "  no data")

print("""
WHAT YOU LEARNED
- Raw: you need security IDs + segments; timestamps are epoch -> convert to IST.
- Tradehull: pass symbol names, get DataFrames back; resolves IDs for you.
- Decide the TIMEFRAME first: it sets how often your algo acts (a 5-min
  algo should act once per new 5-min candle, not every second).
- Automate: daily download of candles after close (15:45) to build your own
  dataset for backtests. Polling LTP in a loop is NOT how you watch live
  prices - use the WebSocket (lesson 6).
""")
