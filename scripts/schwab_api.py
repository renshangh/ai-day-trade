#!/usr/bin/env python3
"""Minimal Charles Schwab Trader API client -- stdlib only, read-only.

A hands-on way to try https://developer.schwab.com with your own registered app,
without installing schwab-py or touching the lumibot Schwab broker (which is
wired to Lumiwealth's hosted OAuth callback, not to a personal app key).

Setup (see docs/SCHWAB_API.md for the full walkthrough):
    1. Register an app at developer.schwab.com, callback https://127.0.0.1:8182
    2. Wait for status "Ready For Use" (a few days), then copy the key + secret
    3. Put SCHWAB_APP_KEY / SCHWAB_APP_SECRET in .env
    4. python3 scripts/schwab_api.py login

Usage:
    python3 scripts/schwab_api.py login                  # one-time OAuth, writes token
    python3 scripts/schwab_api.py check                  # token status + accounts + a quote
    python3 scripts/schwab_api.py positions
    python3 scripts/schwab_api.py transactions --days 30
    python3 scripts/schwab_api.py quote NVDA AXTI COHR
    python3 scripts/schwab_api.py raw /trader/v1/userPreference

This script only reads. It never places, replaces, or cancels an order.

RULE #1 (AGENTS.md): every number printed here comes straight off the wire. A
field Schwab does not return is shown as "--", never defaulted or carried over.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
API_BASE = "https://api.schwabapi.com"

DEFAULT_CALLBACK = "https://127.0.0.1:8182"
DEFAULT_TOKEN_PATH = ".secrets/schwab_token.json"

# Schwab expires the refresh token 7 days after the *original* authorization.
# Refreshing the access token does not restart that clock, so `login` has to be
# re-run weekly. We warn early, at 6.5 days, the same cutoff schwab-py uses.
REFRESH_TOKEN_LIFETIME = timedelta(days=7)
REFRESH_TOKEN_WARN_AFTER = timedelta(hours=156)
ACCESS_TOKEN_SKEW_SECONDS = 60

REPO_ROOT = Path(__file__).resolve().parent.parent


class SchwabError(Exception):
    """An HTTP error from Schwab, carrying the response body (which explains a lot)."""

    def __init__(self, status: int, body: str, url: str):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status} from {url}\n{body}")


# --------------------------------------------------------------------------- env


def load_env(path: Path) -> None:
    """Read a .env file into os.environ without depending on python-dotenv.

    Existing environment variables win, so `SCHWAB_APP_KEY=... python3 ...` works.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(
            f"{name} is not set. Add it to {REPO_ROOT / '.env'} or export it.\n"
            "See docs/SCHWAB_API.md for where to find your app key and secret."
        )
    return value


def token_path() -> Path:
    configured = os.environ.get("SCHWAB_TOKEN_PATH", "").strip() or DEFAULT_TOKEN_PATH
    path = Path(configured)
    return path if path.is_absolute() else REPO_ROOT / path


def callback_url() -> str:
    return os.environ.get("SCHWAB_CALLBACK_URL", "").strip() or DEFAULT_CALLBACK


# ------------------------------------------------------------------------- http


def http(method: str, url: str, *, headers: dict, data: bytes | None = None) -> str:
    request = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        raise SchwabError(err.code, err.read().decode("utf-8", "replace"), url) from None


def basic_auth_header() -> str:
    pair = f"{require_env('SCHWAB_APP_KEY')}:{require_env('SCHWAB_APP_SECRET')}"
    return "Basic " + base64.b64encode(pair.encode("utf-8")).decode("ascii")


# ------------------------------------------------------------------------ token


def read_token() -> dict:
    path = token_path()
    if not path.is_file():
        sys.exit(f"No token at {path}. Run: python3 scripts/schwab_api.py login")
    return json.loads(path.read_text(encoding="utf-8"))


def write_token(payload: dict, *, authorized_at: float) -> Path:
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "authorized_at": authorized_at,  # start of the 7-day refresh-token clock
        "refreshed_at": time.time(),
        "token": payload,
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    path.chmod(0o600)
    return path


def exchange(form: dict) -> dict:
    body = urllib.parse.urlencode(form).encode("utf-8")
    headers = {
        "Authorization": basic_auth_header(),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    return json.loads(http("POST", TOKEN_URL, headers=headers, data=body))


def access_token() -> str:
    """Return a usable access token, refreshing it in place when it has aged out."""
    record = read_token()
    token = record["token"]
    expires_in = token.get("expires_in", 1800)
    age = time.time() - record["refreshed_at"]

    if age < expires_in - ACCESS_TOKEN_SKEW_SECONDS:
        return token["access_token"]

    refresh_token = token.get("refresh_token")
    if not refresh_token:
        sys.exit("Token file has no refresh_token. Run: python3 scripts/schwab_api.py login")

    try:
        refreshed = exchange({"grant_type": "refresh_token", "refresh_token": refresh_token})
    except SchwabError as err:
        if err.status in (400, 401):
            sys.exit(
                f"Refresh was rejected ({err.status}) -- the 7-day refresh token has most "
                "likely expired.\nRun: python3 scripts/schwab_api.py login\n\n"
                f"Schwab said: {err.body}"
            )
        raise

    refreshed.setdefault("refresh_token", refresh_token)
    write_token(refreshed, authorized_at=record["authorized_at"])
    return refreshed["access_token"]


def api(path: str, params: dict | None = None) -> object:
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {access_token()}", "Accept": "application/json"}
    return json.loads(http("GET", url, headers=headers))


# ------------------------------------------------------------------ formatting


def fmt(value, spec: str = "") -> str:
    """Render a value, or '--' when Schwab did not send it. Never substitutes a default.

    A missing value is padded to the same width as the number it replaces, so a
    sparse column still lines up.
    """
    if value is None or value == "":
        align, width = re.match(r"([<>^]?)(\d*)", spec).groups()
        return format("--", f"{align or '>'}{width}") if width else "--"
    if spec:
        try:
            return format(value, spec)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def security_leg(transaction: dict) -> dict:
    """Pick the traded security out of a transaction's legs, ignoring fee/commission legs."""
    for item in transaction.get("transferItems", []):
        instrument = item.get("instrument") or {}
        if instrument.get("symbol") and not item.get("feeType"):
            return item
    return {}


# --------------------------------------------------------------------- commands


def cmd_login(args: argparse.Namespace) -> None:
    app_key = require_env("SCHWAB_APP_KEY")
    require_env("SCHWAB_APP_SECRET")
    callback = callback_url()

    query = urllib.parse.urlencode(
        {"response_type": "code", "client_id": app_key, "redirect_uri": callback}
    )
    url = f"{AUTH_URL}?{query}"

    print("Schwab authorization\n")
    print("1. Log in and approve your accounts at this URL:\n")
    print(f"   {url}\n")
    print(f"2. Schwab then redirects to {callback}, which nothing is listening on.")
    print("   Your browser will show a connection or certificate error. That is expected.")
    print("   The part that matters is the URL in the address bar.\n")
    print("3. Copy that whole URL (it contains ?code=...) and paste it below.\n")

    if not args.no_browser:
        try:
            webbrowser.open(url)
            print("   (opened in your browser)\n")
        except Exception:
            pass

    pasted = input("Redirected URL: ").strip()
    if not pasted:
        sys.exit("Nothing pasted; aborting.")

    code = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query).get("code", [None])[0]
    if not code:
        sys.exit("That URL has no ?code= parameter. Paste the full redirected URL.")

    payload = exchange(
        {"grant_type": "authorization_code", "code": code, "redirect_uri": callback}
    )
    path = write_token(payload, authorized_at=time.time())

    print(f"\nToken written to {path} (mode 600, git-ignored).")
    print(f"Valid until {datetime.now() + REFRESH_TOKEN_LIFETIME:%Y-%m-%d %H:%M}; re-run `login` then.")
    print("\nNext: python3 scripts/schwab_api.py check")


def cmd_check(args: argparse.Namespace) -> None:
    record = read_token()
    authorized_at = datetime.fromtimestamp(record["authorized_at"])
    age = datetime.now() - authorized_at
    remaining = REFRESH_TOKEN_LIFETIME - age

    print("Token")
    print(f"  authorized     {authorized_at:%Y-%m-%d %H:%M} ({age.days}d {age.seconds // 3600}h ago)")
    if remaining.total_seconds() <= 0:
        print("  refresh token  EXPIRED -- run `login` again")
    else:
        hours = int(remaining.total_seconds() // 3600)
        flag = "  <- re-run `login` soon" if age > REFRESH_TOKEN_WARN_AFTER else ""
        print(f"  refresh token  {hours}h left{flag}")

    numbers = api("/trader/v1/accounts/accountNumbers")
    print(f"\nAccounts ({len(numbers)})")
    for entry in numbers:
        masked = "***" + entry["accountNumber"][-4:]
        print(f"  {masked}  hash {entry['hashValue'][:12]}...")

    accounts = api("/trader/v1/accounts")
    for account in accounts:
        securities = account.get("securitiesAccount", {})
        balances = securities.get("currentBalances", {})
        masked = "***" + str(securities.get("accountNumber", "????"))[-4:]
        print(f"\n  {masked} ({fmt(securities.get('type'))})")
        for label, key in (
            ("liquidation value", "liquidationValue"),
            ("cash balance", "cashBalance"),
            ("buying power", "buyingPower"),
        ):
            if balances.get(key) is not None:
                print(f"    {label:<18} {balances[key]:>14,.2f}")

    quotes = api("/marketdata/v1/quotes", {"symbols": "SPY", "fields": "quote"})
    quote = quotes.get("SPY", {}).get("quote", {})
    print(f"\nMarket data  SPY last {fmt(quote.get('lastPrice'), ',.2f')}")
    print("\nBoth API products are responding.")


def cmd_positions(args: argparse.Namespace) -> None:
    accounts = api("/trader/v1/accounts", {"fields": "positions"})
    for account in accounts:
        securities = account.get("securitiesAccount", {})
        masked = "***" + str(securities.get("accountNumber", "????"))[-4:]
        positions = securities.get("positions", [])
        print(f"\n{masked} -- {len(positions)} position(s)")
        if not positions:
            continue
        print(f"  {'SYMBOL':<8} {'QTY':>9} {'AVG COST':>11} {'MKT VALUE':>13} {'OPEN P/L':>12}")
        for position in sorted(positions, key=lambda p: p["instrument"].get("symbol", "")):
            quantity = (position.get("longQuantity") or 0) - (position.get("shortQuantity") or 0)
            print(
                f"  {position['instrument'].get('symbol', '--'):<8}"
                f" {quantity:>9,.0f}"
                f" {fmt(position.get('averagePrice'), '>11,.2f')}"
                f" {fmt(position.get('marketValue'), '>13,.2f')}"
                f" {fmt(position.get('longOpenProfitLoss'), '>12,.2f')}"
            )


def cmd_transactions(args: argparse.Namespace) -> None:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    stamp = "%Y-%m-%dT%H:%M:%S.000Z"

    for entry in api("/trader/v1/accounts/accountNumbers"):
        masked = "***" + entry["accountNumber"][-4:]
        transactions = api(
            f"/trader/v1/accounts/{entry['hashValue']}/transactions",
            {"startDate": start.strftime(stamp), "endDate": end.strftime(stamp), "types": args.types},
        )
        print(f"\n{masked} -- {len(transactions)} {args.types} in the last {args.days} days")
        if not transactions:
            continue
        print(f"  {'WHEN':<17} {'SYMBOL':<8} {'QTY':>9} {'PRICE':>10} {'NET':>13}")
        for transaction in sorted(transactions, key=lambda t: t.get("time", "")):
            leg = security_leg(transaction)
            instrument = leg.get("instrument") or {}
            print(
                f"  {transaction.get('time', '--')[:16]:<17}"
                f" {instrument.get('symbol', '--'):<8}"
                f" {fmt(leg.get('amount'), '>9,.0f')}"
                f" {fmt(leg.get('price'), '>10,.4f')}"
                f" {fmt(transaction.get('netAmount'), '>13,.2f')}"
            )


def cmd_quote(args: argparse.Namespace) -> None:
    symbols = [s.upper() for s in args.symbols]
    quotes = api("/marketdata/v1/quotes", {"symbols": ",".join(symbols), "fields": "quote"})

    print(f"  {'SYMBOL':<8} {'LAST':>10} {'CHANGE %':>10} {'BID':>10} {'ASK':>10} {'VOLUME':>13}")
    for symbol in symbols:
        entry = quotes.get(symbol)
        if entry is None or "quote" not in entry:
            print(f"  {symbol:<8} {'no data returned':>10}")
            continue
        quote = entry["quote"]
        print(
            f"  {symbol:<8}"
            f" {fmt(quote.get('lastPrice'), '>10,.2f')}"
            f" {fmt(quote.get('netPercentChange'), '>10,.2f')}"
            f" {fmt(quote.get('bidPrice'), '>10,.2f')}"
            f" {fmt(quote.get('askPrice'), '>10,.2f')}"
            f" {fmt(quote.get('totalVolume'), '>13,.0f')}"
        )


def cmd_raw(args: argparse.Namespace) -> None:
    params = dict(pair.split("=", 1) for pair in args.param)
    print(json.dumps(api(args.path, params), indent=2))


def main() -> None:
    load_env(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="run the one-time OAuth flow")
    login.add_argument("--no-browser", action="store_true", help="print the URL, do not open it")
    login.set_defaults(func=cmd_login)

    sub.add_parser("check", help="token status, accounts, balances, one quote").set_defaults(func=cmd_check)
    sub.add_parser("positions", help="open positions per account").set_defaults(func=cmd_positions)

    transactions = sub.add_parser("transactions", help="recent transactions per account")
    transactions.add_argument("--days", type=int, default=30)
    transactions.add_argument("--types", default="TRADE", help="TRADE, DIVIDEND_OR_INTEREST, ...")
    transactions.set_defaults(func=cmd_transactions)

    quote = sub.add_parser("quote", help="real-time quotes")
    quote.add_argument("symbols", nargs="+")
    quote.set_defaults(func=cmd_quote)

    raw = sub.add_parser("raw", help="GET any endpoint path and dump the JSON")
    raw.add_argument("path", help="e.g. /trader/v1/userPreference")
    raw.add_argument("--param", action="append", default=[], metavar="K=V")
    raw.set_defaults(func=cmd_raw)

    args = parser.parse_args()
    try:
        args.func(args)
    except SchwabError as err:
        sys.exit(f"\nSchwab returned HTTP {err.status} for {err.url}\n{err.body}")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
