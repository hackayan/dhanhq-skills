"""
The trading loop shared by lesson 8 (paper) and lesson 9 (live).
Same strategy code as the backtest -> what you tested is what runs.

Each step (one per completed candle):
  1. fetch candles, drop the still-forming one
  2. desired = strategy signal on the last completed candle
  3. read current position (paper: state file; live: Dhan positions = source of truth)
  4. if they differ -> BUY or SELL with a LIMIT order near LTP
  5. 15:15 -> square off intraday; log everything to a CSV journal
"""

import csv
import json
import os
import time
from datetime import timedelta

import pandas as pd

from common import SECURITY, candles_to_df, dhan_client, market_open, now_ist, unwrap
from strategies import latest_signal

ENTRY_CUTOFF  = (15, 0)     # no new entries after 15:00
SQUARE_OFF    = (15, 15)    # flatten intraday positions


class PaperBroker:
    """Simulated fills at LTP +/- slippage. Position kept in a JSON state file."""

    def __init__(self, dhan, state_file, slippage=0.0005):
        self.dhan, self.state_file, self.slippage = dhan, state_file, slippage
        self.state = json.load(open(state_file)) if os.path.exists(state_file) else {"qty": 0}

    def position(self, sec):
        return self.state["qty"]

    def pending(self, sec):
        return False

    def order(self, sec, side, qty, ltp, product):
        price = ltp * (1 + self.slippage if side == "BUY" else 1 - self.slippage)
        self.state["qty"] += qty if side == "BUY" else -qty
        json.dump(self.state, open(self.state_file, "w"))
        return "PAPER", round(price, 2)


class LiveBroker:
    """Real LIMIT orders. Position is always re-read from Dhan (never trust local memory)."""

    def __init__(self, dhan):
        self.dhan = dhan

    def position(self, sec):
        for p in unwrap(self.dhan.get_positions()) or []:
            if str(p.get("securityId")) == sec["id"]:
                return int(p.get("netQty", 0))
        return 0

    def pending(self, sec):
        """True if an order for this security is still open (avoid double entries)."""
        for o in unwrap(self.dhan.get_order_list()) or []:
            if str(o.get("securityId")) == sec["id"] and o.get("orderStatus") in ("PENDING", "TRANSIT", "PART_TRADED"):
                return True
        return False

    def order(self, sec, side, qty, ltp, product):
        # Marketable limit: BUY a bit above LTP, SELL a bit below -> fills now, but capped
        price = round(ltp * (1.002 if side == "BUY" else 0.998), 1)
        resp  = self.dhan.place_order(sec["id"], sec["segment"], side, qty, "LIMIT", product, price)
        if resp["status"] != "success":
            raise RuntimeError(f"order rejected: {resp['remarks']}")
        return unwrap(resp).get("orderId"), price


class Bot:
    def __init__(self, symbol, strategy, interval, qty, product, max_trades, max_notional,
                 live=False, journal="journal.csv"):
        self.sec, self.symbol = SECURITY[symbol], symbol
        self.strategy, self.interval, self.qty, self.product = strategy, interval, qty, product
        self.max_trades, self.max_notional, self.journal = max_trades, max_notional, journal
        self.dhan   = dhan_client()
        self.broker = LiveBroker(self.dhan) if live else PaperBroker(self.dhan, f"paper_state_{symbol}.json")
        self.mode   = "LIVE" if live else "PAPER"
        self.trades_today, self.day = 0, now_ist().date()

    # ---------------------------------------------------------------- data
    def candles(self):
        today = now_ist().date()
        raw   = unwrap(self.dhan.intraday_minute_data(self.sec["id"], self.sec["segment"], self.sec["type"],
                                                      str(today - timedelta(days=7)), str(today), self.interval))
        df    = candles_to_df(raw)
        # drop the candle that is still forming (start + interval > now)
        done  = df.index + pd.Timedelta(minutes=self.interval) <= pd.Timestamp(now_ist())
        return df[done]

    def ltp(self):
        data = unwrap(self.dhan.ticker_data({self.sec["segment"]: [int(self.sec["id"])]}))
        return float(data[self.sec["segment"]][self.sec["id"]]["last_price"])

    # ---------------------------------------------------------------- journal
    def log(self, side, qty, price, reason, order_id=""):
        new = not os.path.exists(self.journal)
        with open(self.journal, "a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "mode", "symbol", "strategy", "side", "qty", "price", "reason", "order_id"])
            w.writerow([now_ist().isoformat(timespec="seconds"), self.mode, self.symbol, self.strategy,
                        side, qty, price, reason, order_id])
        print(f"  {self.mode} {side} {qty} {self.symbol} @ {price}  ({reason})")

    # ---------------------------------------------------------------- one decision
    def step(self):
        now = now_ist()
        if now.date() != self.day:
            self.trades_today, self.day = 0, now.date()
        if not market_open(now):
            print(f"{now:%H:%M:%S} market closed")
            return

        if self.broker.pending(self.sec):
            return print(f"{now:%H:%M:%S} order still pending on exchange - waiting")

        held = self.broker.position(self.sec)
        hm   = (now.hour, now.minute)

        if self.product == "INTRADAY" and hm >= SQUARE_OFF:
            if held > 0:
                oid, px = self.broker.order(self.sec, "SELL", held, self.ltp(), self.product)
                self.log("SELL", held, px, "15:15 square-off", oid)
            return

        df      = self.candles()
        desired = latest_signal(self.strategy, df)
        print(f"{now:%H:%M:%S} last candle {df.index[-1]:%H:%M} close {df['close'].iloc[-1]}  "
              f"signal {desired}  holding {held}")

        if desired == 1 and held == 0:
            if hm >= ENTRY_CUTOFF:
                return print("  entry skipped: after 15:00")
            if self.trades_today >= self.max_trades:
                return print(f"  entry skipped: max {self.max_trades} trades/day reached")
            ltp = self.ltp()
            if ltp * self.qty > self.max_notional:
                return print(f"  entry skipped: {ltp * self.qty:.0f} > max notional {self.max_notional}")
            oid, px = self.broker.order(self.sec, "BUY", self.qty, ltp, self.product)
            self.trades_today += 1
            self.log("BUY", self.qty, px, f"{self.strategy} signal", oid)
        elif desired == 0 and held > 0:
            oid, px = self.broker.order(self.sec, "SELL", held, self.ltp(), self.product)
            self.log("SELL", held, px, f"{self.strategy} exit", oid)

    # ---------------------------------------------------------------- loop
    def run(self, once=False):
        print(f"{self.mode} | {self.symbol} | {self.strategy} | {self.interval}m | qty {self.qty} | {self.product}")
        while True:
            try:
                self.step()
            except Exception as e:                  # one bad call must not kill the algo
                print(f"  ERROR: {e}")
            if once:
                return
            # wake 5s after the next candle closes
            now   = now_ist()
            nxt   = now.replace(second=0, microsecond=0) + timedelta(minutes=self.interval - now.minute % self.interval)
            time.sleep(max(5, (nxt - now).total_seconds() + 5))


def journal_summary(path="journal.csv"):
    """Pair BUY->SELL rows into round trips and print P&L stats."""
    if not os.path.exists(path):
        return print("no journal yet")
    df, trips, entry = pd.read_csv(path), [], None
    for _, r in df.iterrows():
        if r["side"] == "BUY":
            entry = r
        elif entry is not None:
            trips.append((r["price"] - entry["price"]) * r["qty"])
            entry = None
    if not trips:
        return print("no completed round trips yet")
    s = pd.Series(trips)
    print(f"round trips {len(s)}  total P&L {s.sum():.2f}  win % {100 * (s > 0).mean():.0f}  "
          f"avg win {s[s > 0].mean():.2f}  avg loss {s[s <= 0].mean():.2f}")
