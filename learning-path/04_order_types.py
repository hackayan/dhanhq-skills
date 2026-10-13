"""
Lesson 4 - The 4 order types and when each one wins.

Learning trick: every order here is a BUY of 1 share placed ~5% BELOW the
market, so it will NOT fill. You see it in the order book, then cancel it.
Default is DRY RUN. --live sends it (after you type YES). Needs a whitelisted IP.

    python 04_order_types.py --type plain          # place -> status -> modify -> cancel
    python 04_order_types.py --type super          # entry + target + stop-loss in one order
    python 04_order_types.py --type forever        # GTT, lives across days
    python 04_order_types.py --type conditional    # Dhan watches an indicator for you
    python 04_order_types.py --type plain --live
"""

import argparse
import json
import time

from common import SECURITY, confirm_live, dhan_client, unwrap

p = argparse.ArgumentParser()
p.add_argument("--type", required=True, choices=["plain", "super", "forever", "conditional"])
p.add_argument("--symbol", default="HDFCBANK", choices=["RELIANCE", "HDFCBANK"])
p.add_argument("--live", action="store_true")
args = p.parse_args()

sec  = SECURITY[args.symbol]
dhan = dhan_client()
ltp  = unwrap(dhan.ticker_data({sec["segment"]: [int(sec["id"])]}))[sec["segment"]][sec["id"]]["last_price"]
far  = round(ltp * 0.95, 1)           # 5% below market -> stays pending, never fills
print(f"\n{args.symbol} LTP {ltp} -> learning price {far}")


def show(title, call, **kw):
    print(f"\n--- {title} ---\n{call}(\n" + json.dumps(kw, indent=4) + "\n)")
    return kw


def order_id_of(resp):
    data = unwrap(resp)
    return data.get("orderId") or data.get("alertId") if isinstance(data, dict) else None


if args.type == "plain":
    kw = show("PLAIN LIMIT ORDER", "dhan.place_order",
              security_id=sec["id"], exchange_segment=dhan.NSE, transaction_type=dhan.BUY,
              quantity=1, order_type=dhan.LIMIT, product_type=dhan.CNC, price=far)
    if confirm_live(args):
        oid = order_id_of(dhan.place_order(**kw))
        print("  placed:", oid)
        time.sleep(1)
        print("  status:", unwrap(dhan.get_order_by_id(oid)))
        new = round(far * 0.99, 1)
        print("  modify ->", new, dhan.modify_order(oid, dhan.LIMIT, "ENTRY_LEG", 1, new, 0, 0, dhan.DAY)["status"])
        print("  cancel:", dhan.cancel_order(oid)["status"])

elif args.type == "super":
    kw = show("SUPER ORDER (entry + target + SL + trailing)", "dhan.place_super_order",
              security_id=sec["id"], exchange_segment=dhan.NSE, transaction_type=dhan.BUY,
              quantity=1, order_type=dhan.LIMIT, product_type=dhan.INTRA, price=far,
              targetPrice=round(far * 1.01, 1), stopLossPrice=round(far * 0.995, 1), trailingJump=1.0)
    if confirm_live(args):
        oid = order_id_of(dhan.place_super_order(**kw))
        print("  placed:", oid)
        time.sleep(1)
        print("  super orders:", unwrap(dhan.get_super_order_list()))
        print("  cancel:", dhan.cancel_super_order(oid, "ENTRY_LEG")["status"])

elif args.type == "forever":
    kw = show("FOREVER / GTT (SINGLE trigger)", "dhan.place_forever",
              security_id=sec["id"], exchange_segment=dhan.NSE, transaction_type=dhan.BUY,
              product_type=dhan.CNC, order_type=dhan.LIMIT, quantity=1,
              price=far, trigger_Price=round(far * 1.001, 1), order_flag="SINGLE")
    if confirm_live(args):
        oid = order_id_of(dhan.place_forever(**kw))
        print("  placed:", oid)
        time.sleep(1)
        print("  forever orders:", unwrap(dhan.get_forever()))
        print("  cancel:", dhan.cancel_forever(oid)["status"])

else:
    condition = {"comparisonType": "TECHNICAL_WITH_VALUE", "exchangeSegment": dhan.NSE,
                 "securityId": sec["id"], "indicatorName": "RSI_14", "timeFrame": "FIFTEEN_MIN",
                 "operator": "CROSSING_DOWN", "comparingValue": 20, "frequency": "ONCE"}
    orders    = [{"transactionType": dhan.BUY, "exchangeSegment": dhan.NSE, "productType": dhan.CNC,
                  "orderType": dhan.LIMIT, "securityId": sec["id"], "quantity": 1,
                  "validity": dhan.DAY, "price": str(far)}]
    show("CONDITIONAL ORDER (Dhan server watches RSI for you)", "dhan.place_conditional_order",
         condition=condition, orders=orders)
    if confirm_live(args):
        aid = order_id_of(dhan.place_conditional_order(condition, orders))
        print("  placed alert:", aid)
        time.sleep(1)
        print("  alerts:", unwrap(dhan.get_conditional_orders()))
        print("  cancel:", dhan.cancel_conditional_order(aid)["status"])

print("""
WHICH ORDER TYPE WINS WHEN
  plain        Full control; YOUR code must manage SL/target. Use for simple
               entries, exits, and when the algo itself decides the exit.
  super        Intraday entry + target + SL (+ trailing) in ONE call; SL lives
               on Dhan's server, so it still works if your script crashes.
               -> default for intraday algos.
  forever/GTT  Survives across days. Swing / positional entries and OCO exits
               (target + SL) without a script running all day.
  conditional  Dhan's server checks a SINGLE indicator condition (equity/index
               only). Zero infrastructure, but limited logic. Good for simple
               "buy when RSI < 30" alerts; use Python signals for anything multi-condition.
Rules: F&O MARKET orders are banned from 1 Apr 2026 -> always LIMIT.
       BUY limit slightly ABOVE LTP / SELL slightly BELOW LTP for an immediate fill.
""")
