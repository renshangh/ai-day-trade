#!/usr/bin/env python3
"""Guarded Schwab stock/ETF order helper for the chat-invoked Codex skill.

This command is intentionally narrow: whole-share BUY/SELL orders, MARKET or
LIMIT, normal session only. A live order requires a recent server-side preview,
an exact confirmation phrase, and a separate invocation. Preview records are
single-use and stored under .secrets with owner-only permissions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import schwab_api  # noqa: E402

REPO_ROOT = SCRIPT_DIR.parent
PREVIEW_DIR = REPO_ROOT / ".secrets" / "schwab_order_previews"
PREVIEW_LIFETIME_SECONDS = 10 * 60
SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,40}$")


class TradeError(Exception):
    """A safe-to-display error that confirms no order was submitted."""


class SubmissionUncertain(Exception):
    """The order request may have reached Schwab and must not be retried."""


@dataclass(frozen=True)
class OrderRequest:
    side: str
    symbol: str
    quantity: int
    order_type: str
    duration: str
    limit_price: str | None


def emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_positive_int(raw: object, field: str = "quantity") -> int:
    if isinstance(raw, bool):
        raise TradeError(f"{field} must be a positive whole number")
    try:
        value = int(str(raw))
    except (TypeError, ValueError):
        raise TradeError(f"{field} must be a positive whole number") from None
    if str(raw).strip() != str(value) or value <= 0:
        raise TradeError(f"{field} must be a positive whole number")
    return value


def normalize_price(raw: object) -> str:
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, AttributeError):
        raise TradeError("limit price must be a positive decimal") from None
    if not value.is_finite() or value <= 0:
        raise TradeError("limit price must be a positive decimal")
    places = 4 if value < 1 else 2
    quantum = Decimal(1).scaleb(-places)
    if value != value.quantize(quantum):
        raise TradeError(
            f"limit price supports at most {places} decimal places at this price; "
            "enter the intended price explicitly"
        )
    return f"{value:.{places}f}"


def normalize_order(
    *,
    side: object,
    symbol: object,
    quantity: object,
    order_type: object,
    duration: object,
    limit_price: object | None,
) -> OrderRequest:
    normalized_side = str(side).strip().upper()
    if normalized_side not in {"BUY", "SELL"}:
        raise TradeError("side must be BUY or SELL; short sales are not supported")

    normalized_symbol = str(symbol).strip().upper()
    if not SYMBOL_RE.fullmatch(normalized_symbol):
        raise TradeError("symbol must be a simple stock or ETF ticker")

    normalized_type = str(order_type).strip().upper()
    if normalized_type not in {"MARKET", "LIMIT"}:
        raise TradeError("order type must be MARKET or LIMIT")

    normalized_duration = str(duration).strip().upper().replace("GOOD_TILL_CANCEL", "GTC")
    if normalized_duration not in {"DAY", "GTC"}:
        raise TradeError("duration must be DAY or GTC")
    if normalized_type == "MARKET" and normalized_duration != "DAY":
        raise TradeError("market orders must use DAY duration")

    price = normalize_price(limit_price) if normalized_type == "LIMIT" else None
    if normalized_type == "MARKET" and limit_price not in (None, ""):
        raise TradeError("market orders cannot include a limit price")

    return OrderRequest(
        side=normalized_side,
        symbol=normalized_symbol,
        quantity=parse_positive_int(quantity),
        order_type=normalized_type,
        duration=normalized_duration,
        limit_price=price,
    )


def account_numbers() -> list[dict]:
    try:
        response = schwab_api.api("/trader/v1/accounts/accountNumbers")
    except schwab_api.SchwabError as err:
        raise TradeError(
            f"Schwab account-list request failed (HTTP {err.status}): "
            f"{safe_api_message(err.body)}"
        ) from None
    if not isinstance(response, list):
        raise TradeError("Schwab did not return an account list")
    entries = []
    for entry in response:
        if not isinstance(entry, dict):
            continue
        number = str(entry.get("accountNumber", ""))
        account_hash = str(entry.get("hashValue", ""))
        if number and account_hash:
            entries.append({"accountNumber": number, "hashValue": account_hash})
    if not entries:
        raise TradeError("Schwab returned no linked brokerage accounts")
    return entries


def resolve_account(last4: str | None) -> dict:
    entries = account_numbers()
    if last4:
        suffix = str(last4).strip()
        if not re.fullmatch(r"\d{4}", suffix):
            raise TradeError("account must be identified by its last four digits")
        matches = [entry for entry in entries if entry["accountNumber"].endswith(suffix)]
        if len(matches) != 1:
            raise TradeError(f"expected one linked account ending {suffix}, found {len(matches)}")
        return matches[0]
    if len(entries) != 1:
        labels = ", ".join(f"***{entry['accountNumber'][-4:]}" for entry in entries)
        raise TradeError(f"choose an account by last four digits: {labels}")
    return entries[0]


def account_details(account_hash: str) -> dict:
    try:
        response = schwab_api.api(
            f"/trader/v1/accounts/{account_hash}", {"fields": "positions"}
        )
    except schwab_api.SchwabError as err:
        raise TradeError(
            f"Schwab position request failed (HTTP {err.status}): "
            f"{safe_api_message(err.body)}"
        ) from None
    if not isinstance(response, dict):
        raise TradeError("Schwab did not return account details")
    securities = response.get("securitiesAccount")
    if not isinstance(securities, dict):
        raise TradeError("Schwab account details did not include a securities account")
    return securities


def long_quantity(account_hash: str, symbol: str) -> Decimal:
    securities = account_details(account_hash)
    positions = securities.get("positions")
    if positions is None:
        raise TradeError("Schwab omitted positions, so a sell cannot be verified")
    if not isinstance(positions, list):
        raise TradeError("Schwab returned positions in an unexpected format")
    for position in positions:
        if not isinstance(position, dict):
            continue
        instrument = position.get("instrument") or {}
        if str(instrument.get("symbol", "")).upper() != symbol:
            continue
        raw = position.get("longQuantity")
        if raw is None:
            raise TradeError(f"Schwab omitted the long quantity for {symbol}")
        try:
            return Decimal(str(raw))
        except InvalidOperation:
            raise TradeError(f"Schwab returned an invalid long quantity for {symbol}") from None
    return Decimal("0")


def order_payload(order: OrderRequest) -> dict:
    payload = {
        "session": "NORMAL",
        "duration": "GOOD_TILL_CANCEL" if order.duration == "GTC" else "DAY",
        "orderType": order.order_type,
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {
                "instruction": order.side,
                "quantity": order.quantity,
                "instrument": {"symbol": order.symbol, "assetType": "EQUITY"},
            }
        ],
    }
    if order.limit_price is not None:
        payload["price"] = order.limit_price
    return payload


def safe_api_message(body: str) -> str:
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return "Schwab returned an error without a readable JSON message"
    if isinstance(payload, dict):
        for key in ("message", "error_description", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:500]
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return str(errors[0])[:500]
    return "Schwab rejected the request"


def broker_post(path: str, payload: dict, *, submitting: bool) -> tuple[int, dict, dict]:
    url = schwab_api.API_BASE + path
    headers = {
        "Authorization": f"Bearer {schwab_api.access_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    request = urllib.request.Request(
        url, method="POST", data=json.dumps(payload).encode("utf-8"), headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
            parsed = json.loads(text) if text.strip() else {}
            return response.status, parsed, dict(response.headers.items())
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")
        raise TradeError(
            f"Schwab rejected the request (HTTP {err.code}): {safe_api_message(body)}"
        ) from None
    except (urllib.error.URLError, TimeoutError, socket.timeout) as err:
        if submitting:
            raise SubmissionUncertain(
                "The connection failed while submitting the order. It may have reached Schwab. "
                "Do not retry; check Schwab open orders and order history first."
            ) from err
        raise TradeError("The Schwab preview request could not be completed") from err


def validation_messages(preview: dict) -> dict:
    result = preview.get("orderValidationResult")
    if not isinstance(result, dict):
        return {"rejects": [], "warns": [], "alerts": [], "reviews": [], "accepts": []}
    output = {}
    for key in ("rejects", "warns", "alerts", "reviews", "accepts"):
        value = result.get(key, [])
        output[key] = value if isinstance(value, list) else []
    return output


def confirmation_phrase(order: OrderRequest, account_last4: str) -> str:
    price = f" {order.limit_price}" if order.limit_price is not None else ""
    return (
        f"PLACE {order.side} {order.quantity} {order.symbol} {order.order_type}{price} "
        f"{order.duration} IN ACCOUNT {account_last4}"
    )


def ensure_preview_dir() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    PREVIEW_DIR.chmod(0o700)


def preview_path(token: str, suffix: str = ".json") -> Path:
    if not TOKEN_RE.fullmatch(token):
        raise TradeError("invalid preview token")
    return PREVIEW_DIR / f"{token}{suffix}"


def write_private_json(path: Path, record: dict) -> None:
    ensure_preview_dir()
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)
    path.chmod(0o600)


def read_preview(token: str) -> tuple[Path, dict]:
    path = preview_path(token)
    if not path.is_file():
        raise TradeError("that preview is missing or has already been consumed")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise TradeError("the preview record is unreadable; create a new preview") from None
    if not isinstance(record, dict):
        raise TradeError("the preview record is invalid; create a new preview")
    return path, record


def public_summary(order: OrderRequest, account_last4: str) -> dict:
    return {
        "account": f"***{account_last4}",
        "side": order.side,
        "symbol": order.symbol,
        "quantity": order.quantity,
        "order_type": order.order_type,
        "limit_price": order.limit_price,
        "duration": order.duration,
        "session": "NORMAL",
    }


def preview_order(order: OrderRequest, account_last4: str | None) -> dict:
    account = resolve_account(account_last4)
    suffix = account["accountNumber"][-4:]
    if order.side == "SELL":
        available = long_quantity(account["hashValue"], order.symbol)
        if available < order.quantity:
            raise TradeError(
                f"sell blocked: Schwab reports {available} long shares of {order.symbol}, "
                f"less than the requested {order.quantity}"
            )

    payload = order_payload(order)
    status, response, _headers = broker_post(
        f"/trader/v1/accounts/{account['hashValue']}/previewOrder",
        payload,
        submitting=False,
    )
    if status < 200 or status >= 300 or not isinstance(response, dict):
        raise TradeError("Schwab did not return a valid order preview")
    validation = validation_messages(response)
    if validation["rejects"]:
        return {
            "ok": False,
            "previewed": True,
            "summary": public_summary(order, suffix),
            "validation": validation,
            "message": "Schwab rejected the preview; no live order can be placed.",
        }

    now = time.time()
    token = secrets.token_urlsafe(18)
    phrase = confirmation_phrase(order, suffix)
    record = {
        "version": 1,
        "state": "active",
        "created_at": now,
        "expires_at": now + PREVIEW_LIFETIME_SECONDS,
        "account_hash": account["hashValue"],
        "account_last4": suffix,
        "order": order.__dict__,
        "payload": payload,
        "confirmation_phrase": phrase,
        "validation": validation,
    }
    write_private_json(preview_path(token), record)
    return {
        "ok": True,
        "previewed": True,
        "summary": public_summary(order, suffix),
        "validation": validation,
        "preview_token": token,
        "confirmation_phrase": phrase,
        "expires_at_epoch": record["expires_at"],
        "message": "Preview only. No live order has been submitted.",
    }


def mark_consumed(path: Path, token: str, record: dict, state: str, message: str) -> None:
    record["state"] = state
    record["finished_at"] = time.time()
    record["result_message"] = message
    write_private_json(preview_path(token, ".consumed.json"), record)
    path.unlink(missing_ok=True)


def place_order(token: str, supplied_confirmation: str) -> dict:
    path, record = read_preview(token)
    expected = str(record.get("confirmation_phrase", ""))
    if not expected or not secrets.compare_digest(supplied_confirmation, expected):
        raise TradeError(
            "confirmation did not exactly match the preview phrase; no order was submitted"
        )
    if time.time() > float(record.get("expires_at", 0)):
        mark_consumed(path, token, record, "expired", "Preview expired before submission.")
        raise TradeError("preview expired; no order was submitted, so create a new preview")

    consumed = preview_path(token, ".submitting.json")
    try:
        os.replace(path, consumed)
    except FileNotFoundError:
        raise TradeError("that preview has already been consumed") from None

    order_data = record.get("order") or {}
    try:
        order = normalize_order(**order_data)
        linked_accounts = {
            entry["hashValue"]: entry["accountNumber"][-4:] for entry in account_numbers()
        }
        account_hash = str(record.get("account_hash", ""))
        account_last4 = str(record.get("account_last4", ""))
        if account_hash not in linked_accounts:
            raise TradeError("the previewed Schwab account is no longer linked")
        if linked_accounts[account_hash] != account_last4:
            raise TradeError("the preview account identity no longer matches")
        if record.get("payload") != order_payload(order):
            raise TradeError("the saved order no longer matches its preview; create a new preview")
        if order.side == "SELL":
            available = long_quantity(account_hash, order.symbol)
            if available < order.quantity:
                raise TradeError(
                    f"sell blocked after recheck: Schwab reports {available} long shares of "
                    f"{order.symbol}, less than the requested {order.quantity}"
                )
        status, _body, headers = broker_post(
            f"/trader/v1/accounts/{account_hash}/orders",
            record["payload"],
            submitting=True,
        )
        if status < 200 or status >= 300:
            raise TradeError(f"Schwab returned unexpected HTTP {status}")
    except SubmissionUncertain as exc:
        mark_consumed(consumed, token, record, "uncertain", str(exc))
        raise
    except TradeError as exc:
        mark_consumed(consumed, token, record, "blocked", str(exc))
        raise
    except Exception as exc:
        message = (
            "An unexpected error occurred during submission. The outcome is uncertain. "
            "Do not retry; check Schwab open orders and order history first."
        )
        mark_consumed(consumed, token, record, "uncertain", message)
        raise SubmissionUncertain(message) from exc

    location = next(
        (value for key, value in headers.items() if key.lower() == "location"), ""
    )
    order_id = location.rstrip("/").split("/")[-1] if location else None
    message = "Schwab accepted the live order."
    record["order_id"] = order_id
    mark_consumed(consumed, token, record, "accepted", message)
    return {
        "ok": True,
        "submitted": True,
        "summary": public_summary(order, account_last4),
        "order_id": order_id,
        "message": message,
    }


def active_previews() -> list[dict]:
    if not PREVIEW_DIR.is_dir():
        return []
    now = time.time()
    output = []
    for path in PREVIEW_DIR.glob("*.json"):
        if path.name.endswith(".consumed.json") or path.name.endswith(".submitting.json"):
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("state") != "active" or float(record.get("expires_at", 0)) <= now:
                continue
            order = normalize_order(**record["order"])
            output.append(
                {
                    "preview_token": path.stem,
                    "summary": public_summary(order, str(record["account_last4"])),
                    "confirmation_phrase": record["confirmation_phrase"],
                    "expires_at_epoch": record["expires_at"],
                }
            )
        except (KeyError, OSError, TypeError, ValueError, TradeError):
            continue
    return sorted(output, key=lambda item: item["expires_at_epoch"])


def discard_preview(token: str) -> dict:
    path, record = read_preview(token)
    mark_consumed(path, token, record, "discarded", "Preview discarded without submission.")
    return {"ok": True, "discarded": True, "message": "Preview discarded; no order was submitted."}


def status() -> dict:
    key_set = bool(os.environ.get("SCHWAB_APP_KEY", "").strip())
    secret_set = bool(os.environ.get("SCHWAB_APP_SECRET", "").strip())
    token_exists = schwab_api.token_path().is_file()
    result = {
        "ok": False,
        "configured": key_set and secret_set,
        "token_exists": token_exists,
        "accounts": [],
        "active_previews": active_previews(),
    }
    if not key_set or not secret_set:
        result["message"] = (
            "Add SCHWAB_APP_KEY and SCHWAB_APP_SECRET to .env after the app is Ready For Use."
        )
        return result
    if not token_exists:
        result["message"] = (
            "Run python3 scripts/schwab_api.py login after the app is Ready For Use."
        )
        return result
    entries = account_numbers()
    result["ok"] = True
    result["accounts"] = [{"label": f"***{entry['accountNumber'][-4:]}"} for entry in entries]
    result["message"] = "Schwab authentication and linked accounts are available."
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="check configuration, token, accounts, and active previews")

    preview = sub.add_parser("preview", help="preview, but do not place, a guarded order")
    preview.add_argument("--account-last4")
    preview.add_argument("--side", required=True, choices=("buy", "sell", "BUY", "SELL"))
    preview.add_argument("--symbol", required=True)
    preview.add_argument("--quantity", required=True)
    preview.add_argument(
        "--order-type", required=True, choices=("market", "limit", "MARKET", "LIMIT")
    )
    preview.add_argument("--limit-price")
    preview.add_argument("--duration", default="day", choices=("day", "gtc", "DAY", "GTC"))

    place = sub.add_parser("place", help="consume one preview and submit its exact order")
    place.add_argument("--preview-token", required=True)
    place.add_argument("--confirmation", required=True)

    discard = sub.add_parser("discard", help="discard one preview without placing it")
    discard.add_argument("--preview-token", required=True)
    sub.add_parser("previews", help="list active, unexpired previews")
    return parser


def main() -> None:
    schwab_api.load_env(REPO_ROOT / ".env")
    args = build_parser().parse_args()
    try:
        if args.command == "status":
            emit(status())
        elif args.command == "previews":
            emit({"ok": True, "active_previews": active_previews()})
        elif args.command == "discard":
            emit(discard_preview(args.preview_token))
        elif args.command == "preview":
            order = normalize_order(
                side=args.side,
                symbol=args.symbol,
                quantity=args.quantity,
                order_type=args.order_type,
                duration=args.duration,
                limit_price=args.limit_price,
            )
            emit(preview_order(order, args.account_last4))
        elif args.command == "place":
            emit(place_order(args.preview_token, args.confirmation))
    except SubmissionUncertain as exc:
        emit({"ok": False, "submitted": "uncertain", "error": str(exc)})
        raise SystemExit(2) from None
    except TradeError as exc:
        emit({"ok": False, "submitted": False, "error": str(exc)})
        raise SystemExit(1) from None
    except schwab_api.SchwabError as exc:
        emit(
            {
                "ok": False,
                "submitted": False,
                "error": (
                    f"Schwab authentication request failed (HTTP {exc.status}): "
                    f"{safe_api_message(exc.body)}"
                ),
            }
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
