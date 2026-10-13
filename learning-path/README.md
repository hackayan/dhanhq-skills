# Dhan Algo Trading: Learning Path

Learn each piece of the 4 repos one at a time, compare the alternatives, then
automate only what has proven itself.

```
Learn (lessons 1-6) ──► Compare strategies (7) ──► Paper trade (8) ──► Live, 1 lot (9) ──► Automate (10)
     read-only             no money at risk          no money at risk     small money        unattended
```

| Repo | Role in this path |
|---|---|
| **DhanHQ-py** (`pip install dhanhq`) | The engine. Every script here uses it. |
| **dhanhq-skills** | Ask Claude Code questions while learning ("explain this order response", "add a stop-loss to lesson 9"). Its `references/` are the API manual. |
| **tradehull-dhan-live-algo-skills** | The `Dhan-Tradehull` wrapper style. Lessons 1-3 show it side by side with raw `dhanhq`; its `examples/` are bigger algos to study after lesson 9. |
| **DhanHQ-js** | Skip. Old (v1 API), much smaller feature set. Use only if you must use Node.js. |

---

## Lesson 0: Setup (once)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install Dhan-Tradehull          # optional, for the side-by-side comparisons

export DHAN_CLIENT_ID=1100000000
export DHAN_ACCESS_TOKEN=eyJ...     # Dhan web -> My Profile -> Access DhanHQ APIs (expires daily)
```

- Data lessons (2, 3, 6, 7 with `--symbol`) need an active **Data Plan**.
- Order lessons (4, 9) need a **whitelisted static IP**: run them from that machine.
- Install the agent skills so Claude Code can help you while learning:
  ```bash
  npx skills add hackayan/dhanhq-skills --skill dhanhq
  npx skills add hackayan/tradehull-dhan-live-algo-skills --skill dhan-tradehull
  ```

**Safety built in:** every script is read-only or **dry-run by default**. Real
orders need `--live` **and** typing `YES`. Lesson 4 orders are priced 5% below
market, so they will never fill.

---

## The lessons

Tick each box when done. Each script prints a "WHAT YOU LEARNED" summary at the end.

| # | Run | Learn | Risk |
|---|---|---|---|
| [ ] 1 | `python 01_connect.py` | Token, response format, funds, positions | none |
| [ ] 2 | `python 02_market_data.py --symbol RELIANCE --interval 5` | LTP, daily + intraday candles; saves CSVs | none |
| [ ] 3 | `python 03_option_chain.py --underlying NIFTY` | Expiries, ATM, OI, PCR, max pain | none |
| [ ] 4 | `python 04_order_types.py --type plain` then `super`, `forever`, `conditional` | The 4 order types; then add `--live` to see each one in your order book and cancelled | ~none (never fills) |
| [ ] 5 | `python 05_risk_controls.py` | Positions, P&L exit, kill switch | none |
| [ ] 6 | `python 06_live_feed.py --seconds 20` (market hours) | WebSocket vs polling | none |
| [ ] 7 | `python 07_backtest_compare.py --demo`, then `--csv data_RELIANCE_daily.csv` | **Which strategy is better**, with costs, out-of-sample | none |
| [ ] 8 | `python 08_paper_trade.py --strategy <winner>` for 2+ weeks | Does it work on live data? | none |
| [ ] 9 | `python 09_live_algo.py --strategy <winner> --qty 1` | Real execution, slippage, discipline | small |
| [ ] 10 | `10_automation/` | Token refresh, cron, systemd | as lesson 9 |

Suggested pace: lessons 1-6 in week 1, 7 in week 2, 8 for weeks 3-4, 9 after that only if 8 holds up.

---

## Which works better? Head-to-head comparisons

### Raw `dhanhq` vs `Dhan-Tradehull` wrapper (lessons 1-3)

| | Raw `dhanhq` | `Dhan-Tradehull` |
|---|---|---|
| Instrument input | security_id + segment | symbol name (`"NIFTY 19 DEC 24400 CALL"`) |
| Output | dict `{status, remarks, data}` | DataFrame / float |
| Code length | longer | ~3x shorter |
| Error visibility | explicit (you see every rejection) | hidden inside the wrapper |
| New Dhan features | immediately | when the wrapper is updated |
| Strike selection | DIY from the chain | `ATM_Strike_Selection()` one-liner |
| **Use when** | production engines, anything you must debug at 10 AM | fast prototyping, options strike picking, learning |

**Verdict:** prototype in Tradehull, run production on raw `dhanhq` (this path's
engine does). Either is fine if you understand what it does under the hood.

### Order types (lesson 4)

| Order | Exit managed by | Survives script crash? | Best for |
|---|---|---|---|
| plain LIMIT | your code | no | simple entries/exits; when the algo decides exits |
| **super** | Dhan server (target + SL + trailing) | **yes** | **intraday algos** |
| **forever / GTT** | Dhan server, multi-day | **yes** | **swing / positional**, OCO exits |
| conditional | Dhan server watches 1 indicator | yes, no script needed | simple "buy when RSI < 30"; equity/index only |

Rule from 1 Apr 2026: **F&O MARKET orders are banned**. Use LIMIT, BUY slightly above LTP, SELL slightly below.

### Signal logic: Dhan conditional orders vs Python signals

| | Conditional order | Python (this engine / TA-Lib) |
|---|---|---|
| Infrastructure | none | a running script / server |
| Logic | one condition | anything: multi-indicator, filters, sizing |
| Backtestable with same code | no | **yes** |
| **Use when** | one simple alert-to-order rule | any real strategy |

### Market data: polling vs WebSocket (lessons 2, 6)

- **Candle-close strategies** (5m, 15m, daily): REST candles once per candle. Simple, reliable.
- **Tick-driven** (scalping, own trailing SL, dashboards): WebSocket. Polling hits the 1 req/sec quote limit.

### Auth modes

| Mode | Valid | Use |
|---|---|---|
| access token (copy from web) | 1 day | learning, manual runs |
| PIN + TOTP (`10_automation/refresh_token.py`) | refresh daily, no human | **unattended automation** |
| OAuth / API key | browser each time | apps for other users |

### Strategies (lesson 7): decided by YOUR data, not by opinion

`07_backtest_compare.py` runs `buy_hold`, `ema_cross`, `rsi_reversion`,
`breakout` and `supertrend` on the same candles with costs, then applies a pass bar:

- out-of-sample return > 0
- out-of-sample Sharpe > max(buy_hold, 0.5)
- at least 20 trades (fewer could just be luck)

Typical patterns to expect (and verify):

| Market regime | Tends to work | Tends to fail |
|---|---|---|
| Trending (strong index moves) | ema_cross, breakout, supertrend | rsi_reversion |
| Range-bound / choppy | rsi_reversion | trend followers (many small losses) |
| Intraday, high costs | fewer-trade strategies | anything trading 10+ times a day |

If **nothing passes**, the correct decision is **don't automate it**. That is a
successful result, and it saves you money.

To add your own idea: write a function in `strategies.py` that returns 0/1 per
candle and add it to `STRATEGIES`. Backtest, paper and live all pick it up automatically.

---

## When and how to automate each thing

Automate in this order. Each step is safe on its own, and you never automate
something you haven't run by hand first.

| Stage | Automate | When | How |
|---|---|---|---|
| 1 | Token refresh | from week 1 | `refresh_token.py` @ 08:30 (cron) |
| 2 | Morning health check | from week 1 | `01_connect.py` @ 08:45; fails loudly if token/funds wrong |
| 3 | Daily data collection | from week 1 | `02_market_data.py` @ 15:45, builds your backtest dataset |
| 4 | Backtest re-run | weekly (weekend) | `07_backtest_compare.py --csv ...`; is the edge still alive? |
| 5 | Paper trading | after a strategy passes lesson 7 | `08_paper_trade.py --once` every 5 min via cron |
| 6 | Server-side risk limits | before the first live day | `05_risk_controls.py --set-pnl-exit` @ 09:10 |
| 7 | Live algo, 1 lot | after 2+ weeks of paper matching the backtest | `dhan-algo.service` (systemd) or cron with `09_live_algo.py --once` |
| 8 | Scale size | after 1-2 months live, matching paper | raise `--qty` slowly; keep `--max-notional` |

**Never automate** strategies that failed lesson 7. Never automate without a
server-side P&L exit, or without logs you read every day.

Ready-made schedules are in `10_automation/crontab.txt` and the systemd unit
files. Set the server timezone to `Asia/Kolkata`, and `mkdir logs` first.

### Daily routine once live

| Time | What | Automated by |
|---|---|---|
| 08:30 | new token | cron |
| 08:45 | health check | cron |
| 09:10 | P&L exit set | cron |
| 09:15-15:15 | algo trades on completed candles | systemd / cron |
| 15:15 | intraday square-off | engine |
| 15:45 | save candles | cron |
| 16:00 | **you** read `journal_live.csv` + logs (10 minutes, every day) | you |

---

## Files

```
common.py               credentials, safety prompt, helpers
strategies.py           ONE strategy library shared by 07 / 08 / 09
engine.py               paper + live trading loop (position reconcile, limits, journal)
01..09_*.py             the lessons
10_automation/          refresh_token.py, crontab.txt, dhan-algo.service, dhan-algo-start.timer
```

## Limits of this code (read before going live)

- Long-only, single symbol, equity. For options, study the Tradehull skill's
  `algo-intraday-options.md` and `examples/` once you've done lesson 9.
- Backtest costs are rough per-side estimates. Compare paper fills to calculate yours.
- Security IDs in `common.py` are the well-known ones. Verify any new symbol in the instrument master.
- This is educational code, not financial advice. Algo trading, especially F&O, can lose money quickly.
