"""
One strategy library used by backtest (07), paper trading (08) and live (09).

Every strategy takes an OHLCV DataFrame of COMPLETED candles and returns a
Series of desired position per bar: 1 = long, 0 = flat.
The engine acts on the signal at the NEXT bar's open, so there is no look-ahead.

Pure pandas, no TA-Lib needed, so it runs anywhere.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- indicators
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(close, n=14):
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def atr(df, n=10):
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _hold(entries, exits, index):
    """Turn entry/exit booleans into a 0/1 position that stays on between them."""
    state = pd.Series(np.nan, index=index)
    state[entries] = 1
    state[exits & ~entries] = 0
    return state.ffill().fillna(0).astype(int)


# ---------------------------------------------------------------- strategies
def buy_hold(df):
    """Benchmark. If a strategy can't beat this after costs, don't trade it."""
    return pd.Series(1, index=df.index)


def ema_cross(df, fast=9, slow=21):
    """Trend following: long while fast EMA > slow EMA."""
    return (ema(df["close"], fast) > ema(df["close"], slow)).astype(int)


def rsi_reversion(df, period=14, low=30, high=70):
    """Mean reversion: buy oversold, exit when overbought."""
    r = rsi(df["close"], period)
    return _hold(r < low, r > high, df.index)


def breakout(df, lookback=20, exit_lookback=10):
    """Donchian breakout: buy new N-bar high, exit on M-bar low."""
    upper = df["high"].rolling(lookback).max().shift(1)
    lower = df["low"].rolling(exit_lookback).min().shift(1)
    return _hold(df["close"] > upper, df["close"] < lower, df.index)


def supertrend(df, period=10, mult=3.0):
    """Supertrend (the indicator Tradehull's intraday example uses)."""
    a     = atr(df, period)
    hl2   = (df["high"] + df["low"]) / 2
    upper = (hl2 + mult * a).to_numpy().copy()
    lower = (hl2 - mult * a).to_numpy().copy()
    close = df["close"].to_numpy()
    trend = np.ones(len(df), dtype=int)
    for i in range(1, len(df)):
        # bands only tighten while price stays on the same side
        if not (upper[i] < upper[i - 1] or close[i - 1] > upper[i - 1]):
            upper[i] = upper[i - 1]
        if not (lower[i] > lower[i - 1] or close[i - 1] < lower[i - 1]):
            lower[i] = lower[i - 1]
        if trend[i - 1] == 0 and close[i] > upper[i]:
            trend[i] = 1
        elif trend[i - 1] == 1 and close[i] < lower[i]:
            trend[i] = 0
        else:
            trend[i] = trend[i - 1]
    return pd.Series(trend, index=df.index)


STRATEGIES = {
    "buy_hold":      buy_hold,
    "ema_cross":     ema_cross,
    "rsi_reversion": rsi_reversion,
    "breakout":      breakout,
    "supertrend":    supertrend,
}


def latest_signal(name, df, **params):
    """Desired position (0/1) computed on the last COMPLETED candle."""
    return int(STRATEGIES[name](df, **params).iloc[-1])
