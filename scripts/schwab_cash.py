#!/usr/bin/env python3
"""Read-only multi-account cash snapshots and whole-share sizing. Never orders."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time

try:
    from . import schwab_api as api
except ImportError:
    import schwab_api as api

SNAPSHOT_PATH = api.REPO_ROOT / "trading_records" / "schwab_cash_snapshot.json"
MAX_AGE_SECONDS = 30
TERMINAL = {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "REPLACED"}
ACTIVE = {"AWAITING_PARENT_ORDER", "AWAITING_CONDITION", "AWAITING_MANUAL_REVIEW",
          "ACCEPTED", "AWAITING_UR_OUT", "PENDING_ACTIVATION", "QUEUED", "WORKING",
          "PENDING_CANCEL", "PENDING_REPLACE", "NEW", "AWAITING_RELEASE_TIME",
          "PENDING_ACKNOWLEDGEMENT", "AWAITING_STOP_CONDITION"}
_lock = threading.Lock()
_cached = None


def money(value):
    """Never make absent, nonfinite or negative cash into an available amount."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() else None


def cents(value):
    amount = money(value)
    return None if amount is None else int((amount * 100).to_integral_value(rounding=ROUND_DOWN))


def order_commitments(orders):
    """Conservatively reserve remaining buys, including contingent children.

    Unknown statuses, missing legs or unbounded buy prices prevent sizing. This
    is cash commitment review, not tax clearance or a broker preview.
    """
    if not isinstance(orders, list) or len(orders) >= 3000:
        return None, "Order coverage unavailable or possibly truncated."
    total = Decimal(0)
    def visit(order):
        nonlocal total
        status = order.get("status")
        if status not in TERMINAL:
            if status not in ACTIVE:
                raise ValueError("Unknown order status; verify open orders.")
            legs = order.get("orderLegCollection")
            if not isinstance(legs, list) or not legs:
                raise ValueError("Missing order legs; verify open orders.")
            if any(leg.get("instruction") not in {"BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT", "BUY_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_OPEN", "SELL_TO_CLOSE"} for leg in legs):
                raise ValueError("Unknown order instruction; verify open orders.")
            buys = [leg for leg in legs if str(leg.get("instruction", "")).startswith("BUY")]
            if buys:
                if len(legs) != 1 or order.get("orderType") not in {"LIMIT", "STOP_LIMIT"}:
                    raise ValueError("Unbounded or complex buy commitment needs review.")
                quantity = money(order.get("remainingQuantity"))
                price = money(order.get("price"))
                if quantity is None or price is None or quantity < 0 or price <= 0:
                    raise ValueError("Missing remaining buy quantity or price.")
                total += quantity * price
        for child in order.get("childOrderStrategies", []):
            visit(child)
    try:
        for order in orders:
            visit(order)
    except (ValueError, AttributeError, TypeError) as exc:
        return None, str(exc)
    # Round reserve UP to cents, never under-reserve a fractional-cent obligation.
    from decimal import ROUND_UP
    return int((total * 100).to_integral_value(rounding=ROUND_UP)), None


def account_cash(securities, orders):
    number = str(securities.get("accountNumber", ""))
    if not re.fullmatch(r"\d{4,}", number):
        raise ValueError("Invalid account response")
    balance = securities.get("currentBalances") or {}
    raw_cash = cents(balance.get("cashBalance"))
    reserve, error = order_commitments(orders)
    cap = max(0, raw_cash - reserve) if raw_cash is not None and reserve is not None else None
    # MARGIN availableFunds/buyingPower can be borrowed money. Never use them.
    available = cents(balance.get("cashAvailableForTrading"))
    verified = (min(cap, max(0, available)) if cap is not None and available is not None
                and securities.get("type") == "CASH" else None)
    return {"account": number[-4:], "account_type": securities.get("type"),
            "cash_balance_cents": raw_cash, "buy_commitments_cents": reserve,
            "cash_ceiling_cents": cap, "verified_cash_cents": verified,
            "cash_source": "cashAvailableForTrading capped by cash less buy commitments" if verified is not None
                           else "Cash balance only; verify net cash available without borrowing.",
            "error": error, **account_holdings(securities, orders),
            "wash_sale": "Not cleared; separate review required before execution."}


def account_holdings(securities, orders):
    """Verified long equity inventory less ALL potentially active sell legs.

    Reserve contingent/OCO legs conservatively, even when mutually exclusive.
    An incomplete order or position book must never imply sellable inventory.
    Cash availability does not govern closing an existing long position.
    """
    positions, reserves = {}, {}
    try:
        raw = securities.get("positions")
        if not isinstance(raw, list):
            raise ValueError("Holdings coverage unavailable; refresh or verify in Schwab.")
        for position in raw:
            instrument = position.get("instrument") or {}
            if not instrument.get("assetType"):
                raise ValueError("Missing holding asset type.")
            if instrument["assetType"] != "EQUITY":
                continue
            symbol = instrument.get("symbol")
            long = money(position.get("longQuantity"))
            short = money(position.get("shortQuantity"))
            if not symbol or symbol in positions or long is None or short is None or min(long, short) < 0:
                raise ValueError("Incomplete or ambiguous equity holdings.")
            positions[symbol] = {"long_quantity": format(long, "f"),
                                 "short_quantity": format(short, "f")}
        if not isinstance(orders, list) or len(orders) >= 3000:
            raise ValueError("Sell order coverage unavailable or possibly truncated.")
        def visit(order):
            status = order.get("status")
            if status not in TERMINAL:
                if status not in ACTIVE:
                    raise ValueError("Unknown order status; verify open sell orders.")
                legs = order.get("orderLegCollection")
                if not isinstance(legs, list) or not legs:
                    raise ValueError("Missing order legs; verify open sell orders.")
                for leg in legs:
                    instruction = leg.get("instruction")
                    if instruction not in {"BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT", "BUY_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_OPEN", "SELL_TO_CLOSE"}:
                        raise ValueError("Unknown order instruction; verify sell commitments.")
                    if instruction not in {"SELL", "SELL_SHORT"}:
                        continue
                    instrument = leg.get("instrument") or {}
                    quantity = money(order.get("remainingQuantity"))
                    if (len(legs) != 1 or instrument.get("assetType") != "EQUITY"
                            or not instrument.get("symbol") or quantity is None or quantity < 0):
                        raise ValueError("Incomplete or complex equity sell commitment.")
                    symbol = instrument["symbol"]
                    reserves[symbol] = reserves.get(symbol, Decimal(0)) + quantity
            for child in order.get("childOrderStrategies", []):
                visit(child)
        for order in orders:
            visit(order)
        for symbol, holding in positions.items():
            long, short = money(holding["long_quantity"]), money(holding["short_quantity"])
            reserve = reserves.get(symbol, Decimal(0))
            holding["sell_reserved_quantity"] = format(reserve, "f")
            holding["available_to_sell_quantity"] = format(max(Decimal(0), long - reserve), "f") if short == 0 else None
        return {"holdings": positions, "holdings_error": None}
    except (ValueError, AttributeError, TypeError):
        return {"holdings": {}, "holdings_error": "Holdings or open sell commitments unavailable; refresh or verify in Schwab."}


def fetch_snapshot():
    started = time.perf_counter()
    api.load_env(api.REPO_ROOT / ".env")
    # Refresh OAuth ONCE before parallel GETs; never race multiple refreshes.
    api.access_token()
    mapping = api.api("/trader/v1/accounts/accountNumbers")
    if not isinstance(mapping, list) or not mapping:
        raise ValueError("Linked accounts unavailable")
    now = datetime.now(timezone.utc)
    # Schwab GTC orders last at most180 calendar days. Use midnight at the
    # boundary, not now-minus180, to include the entire oldest eligible day.
    boundary = (now - timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)
    params = {"fromEnteredTime": boundary.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
              "toEnteredTime": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"), "maxResults": 3000}
    def orders(entry):
        try:
            return api.api(f"/trader/v1/accounts/{entry['hashValue']}/orders", params)
        except Exception:
            return None  # A failed account cannot silently look free of commitments.
    with ThreadPoolExecutor(max_workers=6) as pool:
        book = pool.submit(api.api, "/trader/v1/accounts", {"fields": "positions"})
        requests = {str(a["accountNumber"]): pool.submit(orders, a) for a in mapping}
        raw = book.result()
        observed = datetime.now(timezone.utc)
        if not isinstance(raw, list):
            raise ValueError("Account balances unavailable")
        found = {}
        for entry in raw:
            securities = entry.get("securitiesAccount") or {}
            number = str(securities.get("accountNumber", ""))
            if number in requests:
                found[number] = account_cash(securities, requests[number].result())
        if set(found) != set(requests):
            raise ValueError("Incomplete linked-account balance coverage")
    if len({row["account"] for row in found.values()}) != len(found):
        raise ValueError("Account suffixes are not unique")
    payload = {"ok": True, "as_of": observed.isoformat(), "max_age_seconds": MAX_AGE_SECONDS,
               "elapsed_seconds": round(time.perf_counter() - started, 3),
               "accounts": sorted(found.values(), key=lambda row: row["account"]),
               "read_only": True, "execution_ready": False}
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=SNAPSHOT_PATH.parent,
                                     prefix=".schwab_cash_", suffix=".tmp", delete=False) as handle:
        temp = Path(handle.name)
        handle.write(json.dumps(payload, indent=2) + "\n")
    temp.replace(SNAPSHOT_PATH)
    return payload


def snapshot(force=False):
    global _cached
    with _lock:
        if not force and _cached is not None:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(_cached["as_of"])).total_seconds()
            if 0 <= age <= MAX_AGE_SECONDS:
                return _cached
        _cached = None  # Failure must not serve the last snapshot as current.
        _cached = fetch_snapshot()
        return _cached


def size(payload, accounts, price, percentage, confirmed=None, now=None, *, side="buy", symbol=None):
    """Fast, deterministic sizing of one fresh snapshot; no network or orders."""
    price_value = money(price)
    if price_value is None or price_value <= 0 or price_value != price_value.quantize(Decimal("0.01")):
        raise ValueError("Use a positive limit price with at most two decimals.")
    if percentage not in (25, 50, 75, 100):
        raise ValueError("Percentage must be 25, 50, 75 or 100.")
    if side not in {"buy", "sell"}:
        raise ValueError("Side must be buy or sell.")
    ticker = str(symbol or "").strip().upper()
    if side == "sell" and not re.fullmatch(r"[A-Z][A-Z0-9./-]{0,11}", ticker):
        raise ValueError("A stock/ETF symbol is required for sell sizing.")
    current = now or datetime.now(timezone.utc)
    age = (current - datetime.fromisoformat(payload["as_of"])).total_seconds()
    if not 0 <= age <= MAX_AGE_SECONDS:
        raise ValueError("Cash snapshot expired; refresh before sizing.")
    if not accounts or len(accounts) != len(set(accounts)):
        raise ValueError("Select explicit unique account suffixes.")
    book = {a["account"]: a for a in payload["accounts"]}
    rows = []
    for account in accounts:
        if account not in book:
            raise ValueError("Selected account is not linked.")
        row = book[account]
        if side == "sell":
            holding = row.get("holdings", {}).get(ticker)
            error = row.get("holdings_error", "Holdings coverage unavailable.")
            if error or holding is None or money(holding.get("available_to_sell_quantity")) is None:
                rows.append({"account": account, "quantity": None,
                             "reason": error or "No verified sellable long position for this symbol."})
                continue
            available = money(holding["available_to_sell_quantity"])
            if available < 0:
                raise ValueError("Invalid available holdings.")
            quantity = int(available * percentage / 100)
            rows.append({"account": account, **holding, "quantity": quantity,
                         "estimated_proceeds_cents": quantity * cents(price)})
            continue
        cash = row["verified_cash_cents"]
        source = row["cash_source"]
        if account in (confirmed or {}):
            cash = cents(confirmed[account])
            cap = row["cash_ceiling_cents"]
            if cash is None or cash < 0 or cap is None or cash > cap or row["error"]:
                raise ValueError("Confirmed net cash is invalid or exceeds the current cash ceiling.")
            source = "Owner-confirmed net cash for this snapshot, after commitments and costs"
        if cash is None or row["error"]:
            rows.append({"account": account, "quantity": None, "reason": row["error"] or source})
            continue
        budget = cash * percentage // 100
        quantity = budget // cents(price)
        cost = quantity * cents(price)
        rows.append({"account": account, "cash_cents": cash, "cash_source": source,
                     "budget_cents": budget, "quantity": quantity, "cost_cents": cost,
                     "remaining_cash_cents": cash - cost})
    return {"ok": True, "as_of": payload["as_of"], "percentage": percentage, "side": side,
            "symbol": ticker or None,
            "limit_price": str(price_value), "rows": rows, "execution_ready": False,
            "notice": "Sizing only. Wash-sale clearance and broker validation are separate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("snapshot", "size"))
    parser.add_argument("--accounts", nargs="+")
    parser.add_argument("--price")
    parser.add_argument("--percentage", type=int, choices=(25,50,75,100))
    parser.add_argument("--side", choices=("buy", "sell"), default="buy")
    parser.add_argument("--symbol")
    parser.add_argument("--confirmed-cash", action="append", default=[], metavar="LAST4=NET_CASH")
    args = parser.parse_args()
    try:
        if args.command == "snapshot":
            result = snapshot(force=True)
        else:
            confirmed = dict(item.split("=", 1) for item in args.confirmed_cash)
            payload = json.loads(SNAPSHOT_PATH.read_text())
            result = size(payload, args.accounts, args.price, args.percentage, confirmed,
                          side=args.side, symbol=args.symbol)
        print(json.dumps(result, indent=2))
    except (Exception, SystemExit):
        # Broker error bodies can contain full identifiers. Never echo them here.
        print(json.dumps({"ok": False, "error": "Cash sizing unavailable; refresh or verify the supplied inputs and OAuth.", "execution_ready": False}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
