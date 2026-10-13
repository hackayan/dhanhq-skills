"""
Lesson 7 - Find what works BETTER: backtest every strategy on the same data,
with costs, and check it on data it has never seen (out-of-sample).

    python 07_backtest_compare.py --demo                        # no account needed (synthetic data)
    python 07_backtest_compare.py --csv data_RELIANCE_daily.csv # file saved by lesson 2
    python 07_backtest_compare.py --symbol RELIANCE --years 3   # download daily candles from Dhan
    python 07_backtest_compare.py --csv data_RELIANCE_5m.csv --cost intraday

How to read the result:
  - Compare against buy_hold. A strategy that loses to buy_hold after costs is not worth automating.
  - Trust OUT-OF-SAMPLE columns more than in-sample. Big drop from IS -> OOS = overfit.
  - Prefer lower max drawdown at similar return: you have to survive the losing streaks.
"""

import argparse
from datetime import date, timedelta

import numpy as np
import pandas as pd

from strategies import STRATEGIES

# Round-trip friction per SIDE as a fraction of trade value (brokerage + STT +
# exchange + GST + stamp + slippage). Rough, conservative presets.
COSTS = {"delivery": 0.0015, "intraday": 0.0006, "options": 0.0030, "zero": 0.0}


def load(args):
    if args.demo:
        rng   = np.random.default_rng(7)
        n     = 1500
        drift = np.concatenate([np.full(n // 3, 0.0008), np.full(n // 3, -0.0004), np.full(n - 2 * (n // 3), 0.0005)])
        close = 1000 * np.exp(np.cumsum(drift + rng.normal(0, 0.014, n)))
        open_ = close * (1 + rng.normal(0, 0.003, n))
        high  = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
        low   = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
        idx   = pd.bdate_range("2020-01-01", periods=n, tz="Asia/Kolkata")
        return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": 1}, index=idx)
    if args.csv:
        return pd.read_csv(args.csv, index_col=0, parse_dates=True)
    from common import SECURITY, candles_to_df, dhan_client, unwrap
    sec, dhan, frames = SECURITY[args.symbol], dhan_client(), []
    end = date.today()
    for _ in range(args.years):                       # fetch 1 year per request
        start = end - timedelta(days=365)
        frames.append(candles_to_df(unwrap(dhan.historical_daily_data(
            sec["id"], sec["segment"], sec["type"], str(start), str(end)))))
        end = start
    return pd.concat(frames).sort_index().loc[lambda d: ~d.index.duplicated()]


def bars_per_year(index):
    step = pd.Series(index).diff().median()
    return 252 if step >= pd.Timedelta(hours=20) else int(252 * 375 / (step.total_seconds() / 60))


def run(df, signal, cost):
    """Signal at bar t close -> trade at bar t+1 open.
    Returns per-bar net returns, per-trade returns (indexed by entry time) and position."""
    pos    = signal.shift(1).fillna(0)                    # position held during bar
    ret    = df["open"].shift(-1) / df["open"] - 1        # open -> next open
    turn   = pos.diff().abs().fillna(pos.abs())
    net    = (pos * ret - turn * cost).dropna()
    held   = pos.reindex(net.index) == 1
    starts = held & ~held.shift(1, fill_value=False)
    tid    = starts.cumsum().where(held)
    trades = net[held].groupby(tid[held]).apply(lambda r: (1 + r).prod() - 1)
    trades.index = net.index[starts]                    # key each trade by its entry time
    return net, trades, pos


def metrics(net, trades, pos, bpy):
    if len(net) == 0:
        return {}
    equity = (1 + net).cumprod()
    years  = len(net) / bpy
    dd     = (equity / equity.cummax() - 1).min()
    gains, losses = trades[trades > 0].sum(), -trades[trades < 0].sum()
    return {
        "return %":   100 * (equity.iloc[-1] - 1),
        "CAGR %":     100 * (equity.iloc[-1] ** (1 / years) - 1) if years > 0 else np.nan,
        "max DD %":   100 * dd,
        "sharpe":     np.sqrt(bpy) * net.mean() / net.std() if net.std() > 0 else 0,
        "trades":     len(trades),
        "win %":      100 * (trades > 0).mean() if len(trades) else 0,
        "profit fac": gains / losses if losses > 0 else np.inf,
        "time in %":  100 * pos.reindex(net.index).mean(),
    }


def main():
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--demo", action="store_true")
    src.add_argument("--csv")
    src.add_argument("--symbol")
    p.add_argument("--years", type=int, default=3)
    p.add_argument("--cost", default="delivery", choices=COSTS)
    p.add_argument("--split", type=float, default=0.7, help="in-sample fraction")
    args = p.parse_args()

    df    = load(args)
    cost  = COSTS[args.cost]
    bpy   = bars_per_year(df.index)
    cut   = df.index[int(len(df) * args.split)]
    print(f"\n{len(df)} bars  {df.index[0]} -> {df.index[-1]}   cost/side {cost:.4%}   "
          f"in-sample until {cut}")

    if bpy > 252:                                       # intraday bars: be flat by 15:10, no overnight
        late = pd.Series(df.index.time >= pd.Timestamp("15:10").time(), index=df.index)
        STRATS = {n: (lambda f: lambda d: f(d).where(~late.reindex(d.index), 0))(f) for n, f in STRATEGIES.items()}
    else:
        STRATS = STRATEGIES

    rows = []
    for name, fn in STRATS.items():
        net, trades, pos = run(df, fn(df), cost)
        is_m  = metrics(*run(df.loc[:cut], fn(df.loc[:cut]), cost), bpy)
        # OOS: signal uses full history (indicator warm-up), evaluated only after the cut
        oos_m = metrics(net.loc[net.index > cut], trades[trades.index > cut], pos, bpy)
        rows.append({"strategy": name,
                     "IS return %":  is_m.get("return %"),
                     "OOS return %": oos_m.get("return %"),
                     "OOS max DD %": oos_m.get("max DD %"),
                     "OOS sharpe":   oos_m.get("sharpe"),
                     **{f"ALL {k}": v for k, v in metrics(net, trades, pos, bpy).items()
                        if k in ("CAGR %", "max DD %", "trades", "win %", "profit fac")}})

    table = pd.DataFrame(rows).set_index("strategy").sort_values("OOS sharpe", ascending=False)
    pd.set_option("display.width", 200)
    print(table.round(2).to_string())

    bh   = table.loc["buy_hold", "OOS sharpe"]
    # Pass bar: positive out-of-sample, beats buy & hold, enough trades to not be luck
    ok   = table[(table.index != "buy_hold") & (table["OOS return %"] > 0)
                 & (table["OOS sharpe"] > max(bh, 0.5)) & (table["ALL trades"] >= 20)]
    print(f"\nbuy_hold OOS sharpe {bh:.2f}. Pass bar: OOS return > 0, OOS sharpe > max(buy_hold, 0.5), >= 20 trades.")
    if ok.empty:
        print("-> Nothing passed. Do NOT automate these here. Try another instrument/timeframe or idea.")
    else:
        best = ok.index[0]
        print(f"-> PASSED: {', '.join(ok.index)}.  Next: python 08_paper_trade.py --strategy {best}")
    table.to_csv("backtest_results.csv")
    print("saved backtest_results.csv")


if __name__ == "__main__":
    main()
