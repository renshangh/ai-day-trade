"""How do stocks trade in the sessions just before and after a split takes effect?

Three questions, answered from Alpaca's corporate-actions feed and raw daily bars:

1. How many split events (forward and reverse) happen per year?
2. Over the 1, 2, 3 and 5 sessions ending on the last pre-split close, what is
   the price change?
3. Over the 1, 2, 3, 5 and 10 sessions starting on the first post-split close,
   what is the price change?

Definitions
-----------
ex_date   The first session the stock trades on the new share count.
T-1       The last session *before* ex_date. Every "pre-split" window ends here.
ret_N     close[T-1] / close[T-1 - N] - 1, in percent. Cumulative over N sessions.
ex_ret    close[ex_date] * new_rate / old_rate / close[T-1] - 1. The ex-date
          session return with the split ratio backed out. Included for context
          only; it is not part of the pre-split windows.
post_N    close[ex_date + N] / close[ex_date] - 1, in percent. No ratio backing-
          out needed: everything from ex_date onward already trades on the new
          share count, so this is a plain return.

post_N is a raw continuation number, not baselined against this population's
normal drift the way `drift_study.py` baselines earnings drift. These names
were already falling before the split (see the ret_Nd columns on the same
row), so "down after the split" and "this population is generally down" are
not distinguished here -- read post_N as "still falling", not as "caused by
the split".

Security type matters here. The corporate-actions feed covers every US security,
so a raw count mixes three very different populations:
  stock  exchange-listed common stock / ADR / REIT (the population most people
         mean by "stock split")
  etf    exchange-traded funds and notes, tagged from the Alpaca asset name or
         an ARCA/BATS listing (leveraged ETFs split and reverse-split often)
  otc    over-the-counter names; Alpaca has no price bars for these, so they
         are counted but never measured
A symbol missing from Alpaca's asset list is resolved after the bar fetch: if it
has bars it was exchange-listed at the time and has since been delisted (mostly
reverse-split names that later failed), so it is kept as a stock to avoid
survivorship bias; with no bars it is filed as otc. The tag is a heuristic over
the asset name and listing venue, not a fund flag.

Bars are requested with adjustment=raw so every pre-split close sits on the same
share basis. Returns are computed only from bars that exist; a symbol with no
bars, a stale last-pre-split bar, or a bar series where the vendor applied the
split inside the pre-split window is skipped and counted, never filled in
(repo Rule #1).

Usage:  python3 trading_desk/research/split_study.py
Writes: split_events.csv (one row per event) and split_study.json (summary).
"""

from __future__ import annotations

import csv
import json
import math
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import server  # noqa: E402  - reuse env loading, headers, backoff, feed pick

WINDOWS = [1, 2, 3, 5]
POST_WINDOWS = [1, 2, 3, 5, 10]
LOOKBACK_YEARS = 2
CSV_OUT = HERE / "split_events.csv"
JSON_OUT = HERE / "split_study.json"
# A pre-split bar older than this many calendar days before ex_date means the
# stock was halted or the vendor has a gap; the window would not mean anything.
MAX_STALE_DAYS = 5
# A split must move price by at least this much (log terms) before we bother
# checking whether the vendor applied it to the wrong session.
MIN_DETECTABLE_LOG_JUMP = 0.30
JUMP_TOLERANCE = 0.15
# Alpaca rejects a whole batch when one entry is not a ticker; a few events
# carry a CUSIP in the symbol field, so those are skipped up front.
TICKER_RE = re.compile(r"^[A-Z]+(\.[A-Z]+)?$")
ETF_NAME_RE = re.compile(
    r"\bETFs?\b|\bETN\b|\bFund\b|Trust,? Series|iShares|ProShares|Direxion|"
    r"GraniteShares|WisdomTree|VanEck|Leveraged|Daily Target|YieldMax|"
    r"\b[23]X\b|\bBull\b|\bBear\b",
    re.IGNORECASE,
)
ETF_VENUES = {"ARCA", "BATS"}


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def month_starts(first: date, last: date) -> list[date]:
    out, cur = [], first.replace(day=1)
    while cur <= last:
        out.append(cur)
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def fetch_splits(window_start: date, window_end: date) -> list[dict]:
    """Every forward/reverse split whose ex_date falls inside the window.

    The endpoint's own start/end filter is not strictly on ex_date (a 2016
    ex_date came back for a 2025 query), so we over-fetch a couple of months
    either side and filter on ex_date ourselves, de-duplicating on id.
    """
    seen: dict[str, dict] = {}
    for ms in month_starts(window_start - timedelta(days=62), window_end + timedelta(days=31)):
        me = (ms.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        page_token = None
        while True:
            params = {
                "types": "forward_split,reverse_split",
                "start": ms.isoformat(),
                "end": me.isoformat(),
                "limit": 1000,
            }
            if page_token:
                params["page_token"] = page_token
            data = server._get(f"{server.ALPACA_DATA}/v1/corporate-actions?{urllib.parse.urlencode(params)}")
            ca = data.get("corporate_actions") or {}
            for kind, key in (("forward", "forward_splits"), ("reverse", "reverse_splits")):
                for ev in ca.get(key) or []:
                    ev = dict(ev)
                    ev["kind"] = kind
                    seen[ev["id"]] = ev
            page_token = data.get("next_page_token")
            if not page_token:
                break
        print(f"  splits through {me}: {len(seen)} unique so far", file=sys.stderr)

    events = []
    for ev in seen.values():
        ex = date.fromisoformat(ev["ex_date"])
        if not (window_start <= ex <= window_end):
            continue
        old, new = ev.get("old_rate"), ev.get("new_rate")
        if not old or not new or old == new:
            continue  # malformed ratio; nothing sensible to measure
        events.append(ev)
    events.sort(key=lambda e: (e["ex_date"], e["symbol"]))
    return events


def fetch_assets() -> dict[str, dict]:
    """Alpaca's full US-equity asset list, keyed by symbol (active wins)."""
    paper = str(server.ENV.get("ALPACA_IS_PAPER", "true")).lower() not in ("false", "0", "no")
    host = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    assets = server._get(f"{host}/v2/assets?asset_class=us_equity")
    out: dict[str, dict] = {}
    for a in assets:
        cur = out.get(a["symbol"])
        if cur is None or (cur["status"] != "active" and a["status"] == "active"):
            out[a["symbol"]] = {"exchange": a["exchange"], "name": a["name"], "status": a["status"]}
    return out


def classify(asset: dict | None) -> str:
    if asset is None:
        return "unknown"
    if asset["exchange"] == "OTC":
        return "otc"
    if asset["exchange"] in ETF_VENUES or ETF_NAME_RE.search(asset["name"] or ""):
        return "etf"
    return "stock"


def fetch_raw_bars(symbols: list[str], start: date, end: datetime) -> dict[str, list[dict]]:
    """Unadjusted daily bars for many symbols, following pagination."""
    out: dict[str, list[dict]] = {}
    end = server._window_end(end)
    for i in range(0, len(symbols), 100):
        chunk = symbols[i : i + 100]
        page_token = None
        while True:
            params = {
                "symbols": ",".join(chunk),
                "timeframe": "1Day",
                "start": start.isoformat() + "T00:00:00Z",
                "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "adjustment": "raw",
                "sort": "asc",
                "limit": 10000,
                "feed": server.FEED,
            }
            if page_token:
                params["page_token"] = page_token
            data = server._get(f"{server.ALPACA_DATA}/v2/stocks/bars?{urllib.parse.urlencode(params)}")
            for sym, bars in (data.get("bars") or {}).items():
                out.setdefault(sym, []).extend(bars)
            page_token = data.get("next_page_token")
            if not page_token:
                break
    return out


def fetch_bars_for_events(events: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Bars keyed by ex-month then symbol, so each event's window is covered."""
    by_month: dict[str, set[str]] = defaultdict(set)
    for ev in events:
        if TICKER_RE.match(ev["symbol"]) and ev["security_type"] != "otc":
            by_month[ev["ex_date"][:7]].add(ev["symbol"])
    now = datetime.now(timezone.utc)
    out: dict[str, dict[str, list[dict]]] = {}
    for month, syms in sorted(by_month.items()):
        ms = date.fromisoformat(month + "-01")
        me = (ms.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        start = ms - timedelta(days=35)
        # +22 calendar days covers 10 trading sessions after an ex_date on the
        # last day of the month, with room for a holiday or two.
        end = min(datetime.combine(me + timedelta(days=22), datetime.min.time(), tzinfo=timezone.utc), now)
        out[month] = fetch_raw_bars(sorted(syms), start, end)
        got = sum(1 for s in syms if out[month].get(s))
        print(f"  bars {month}: {got}/{len(syms)} symbols returned data", file=sys.stderr)
    return out


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------
def measure(ev: dict, bars: list[dict]) -> tuple[dict | None, str | None]:
    """Return (row, None) on success or (None, skip_reason)."""
    if not TICKER_RE.match(ev["symbol"]):
        return None, "invalid_symbol"
    if ev["security_type"] == "otc":
        return None, "otc_no_price_data"
    if not bars:
        return None, "no_bars"
    ex = date.fromisoformat(ev["ex_date"])
    dates = [date.fromisoformat(b["t"][:10]) for b in bars]
    closes = [float(b["c"]) for b in bars]
    pre = [i for i, d in enumerate(dates) if d < ex]
    if not pre:
        return None, "no_pre_bars"
    t1 = pre[-1]
    if (ex - dates[t1]).days > MAX_STALE_DAYS:
        return None, "stale_pre_bar"
    if t1 < max(WINDOWS):
        return None, "short_history"

    old, new = float(ev["old_rate"]), float(ev["new_rate"])
    split_log = math.log(old / new)  # what the raw ex-date jump should look like
    if abs(split_log) > MIN_DETECTABLE_LOG_JUMP:
        # If any session inside the widest pre-split window moved by the split
        # ratio itself, the vendor applied the split early and the window is
        # contaminated. Skip rather than measure a bookkeeping jump.
        for i in range(t1 - max(WINDOWS) + 1, t1 + 1):
            if abs(math.log(closes[i] / closes[i - 1]) - split_log) < JUMP_TOLERANCE:
                return None, "split_applied_early_in_bars"

    row = {
        "kind": ev["kind"],
        "security_type": ev["security_type"],
        "symbol": ev["symbol"],
        "new_symbol": ev.get("new_symbol") or "",
        "name": ev.get("name") or "",
        "exchange": ev.get("exchange") or "",
        "asset_record": ev.get("asset_record", ""),
        "ex_date": ev["ex_date"],
        "old_rate": ev["old_rate"],
        "new_rate": ev["new_rate"],
        "ratio": f"{ev['new_rate']}:{ev['old_rate']}",
        "pre_close_date": dates[t1].isoformat(),
        "pre_close": closes[t1],
    }
    for n in WINDOWS:
        row[f"ret_{n}d_pct"] = round((closes[t1] / closes[t1 - n] - 1) * 100, 3)

    ex_idx = next((i for i, d in enumerate(dates) if d == ex), None)
    if ex_idx is not None:
        adj_ex_close = closes[ex_idx] * new / old
        row["ex_ret_pct"] = round((adj_ex_close / closes[t1] - 1) * 100, 3)
        actual_log = math.log(closes[ex_idx] / closes[t1])
        row["ex_jump_matches_ratio"] = (
            abs(split_log) <= MIN_DETECTABLE_LOG_JUMP or abs(actual_log - split_log) < 0.5
        )
    else:
        row["ex_ret_pct"] = ""
        row["ex_jump_matches_ratio"] = ""

    # Post-split returns need no ratio adjustment: every close from ex_date
    # onward already trades on the new share count. Only trustworthy when the
    # ex-date jump itself landed where expected (row["ex_jump_matches_ratio"]),
    # otherwise the vendor's split bookkeeping could still be unwinding here.
    trustworthy = ex_idx is not None and row["ex_jump_matches_ratio"] is True
    for n in POST_WINDOWS:
        key = f"post_{n}d_pct"
        if trustworthy and ex_idx + n < len(dates):
            row[key] = round((closes[ex_idx + n] / closes[ex_idx] - 1) * 100, 3)
        else:
            row[key] = ""
    return row, None


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------
def describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    s = sorted(values)
    mid = len(s) // 2
    median = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    return {
        "n": len(s),
        "mean_pct": round(sum(s) / len(s), 2),
        "median_pct": round(median, 2),
        "pct_positive": round(100 * sum(1 for v in s if v > 0) / len(s), 1),
        "p10_pct": round(s[int(0.10 * (len(s) - 1))], 2),
        "p90_pct": round(s[int(0.90 * (len(s) - 1))], 2),
    }


def count_table(events: list[dict], key_fn) -> dict:
    table: dict[str, Counter] = defaultdict(Counter)
    for ev in events:
        table[key_fn(ev)][f"{ev['kind']}_{ev['security_type']}"] += 1
    return {k: dict(sorted(v.items())) for k, v in sorted(table.items())}


def summarize(events: list[dict], rows: list[dict], skipped: Counter,
              window_start: date, window_end: date) -> dict:
    y1_end = window_start.replace(year=window_start.year + 1) - timedelta(days=1)
    label1 = f"{window_start} to {y1_end}"
    label2 = f"{y1_end + timedelta(days=1)} to {window_end}"

    def trailing(ev: dict) -> str:
        return label1 if date.fromisoformat(ev["ex_date"]) <= y1_end else label2

    def fwd_ratio(r: dict) -> float:
        return r["new_rate"] / r["old_rate"]

    def rev_ratio(r: dict) -> float:
        return r["old_rate"] / r["new_rate"]

    stock = [r for r in rows if r["security_type"] == "stock"]
    etf = [r for r in rows if r["security_type"] == "etf"]
    groups = {
        "forward_stock_all": [r for r in stock if r["kind"] == "forward"],
        "forward_stock_2_for_1_or_larger": [r for r in stock if r["kind"] == "forward" and fwd_ratio(r) >= 2],
        "forward_stock_under_2_for_1_stock_dividend_like": [r for r in stock if r["kind"] == "forward" and fwd_ratio(r) < 2],
        "forward_etf": [r for r in etf if r["kind"] == "forward"],
        "reverse_stock_all": [r for r in stock if r["kind"] == "reverse"],
        "reverse_stock_1_for_10_or_larger": [r for r in stock if r["kind"] == "reverse" and rev_ratio(r) >= 10],
        "reverse_stock_under_1_for_10": [r for r in stock if r["kind"] == "reverse" and rev_ratio(r) < 10],
        "reverse_etf": [r for r in etf if r["kind"] == "reverse"],
    }
    returns = {}
    for name, grp in groups.items():
        returns[name] = {f"ret_{n}d": describe([r[f"ret_{n}d_pct"] for r in grp]) for n in WINDOWS}
        # Only rows whose ex-date jump matches the ratio: elsewhere the vendor
        # applied the split on another session and ex_ret is bookkeeping noise.
        returns[name]["ex_day"] = describe([r["ex_ret_pct"] for r in grp if r["ex_jump_matches_ratio"] is True])
        returns[name]["ex_day"]["dropped_misdated"] = sum(1 for r in grp if r["ex_jump_matches_ratio"] is False)
        for n in POST_WINDOWS:
            returns[name][f"post_{n}d"] = describe([r[f"post_{n}d_pct"] for r in grp if r[f"post_{n}d_pct"] != ""])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"start": window_start.isoformat(), "end": window_end.isoformat()},
        "source": {
            "splits": "Alpaca /v1/corporate-actions (forward_split, reverse_split)",
            "bars": f"Alpaca /v2/stocks/bars adjustment=raw feed={server.FEED}",
            "security_type": "Alpaca /v2/assets exchange + name heuristic (see module docstring)",
        },
        "definitions": {
            "ret_Nd": "close[T-1]/close[T-1-N]-1 where T-1 is the last session before ex_date",
            "ex_day": "close[ex_date]*new_rate/old_rate/close[T-1]-1 (split ratio backed out); "
                      "only events whose raw ex-date jump matches the ratio",
            "post_Nd": "close[ex_date+N]/close[ex_date]-1; only events whose raw ex-date jump "
                       "matches the ratio (no baseline against this population's normal drift)",
        },
        "events_total": len(events),
        "events_measured": len(rows),
        "skipped": dict(sorted(skipped.items())),
        "counts_by_calendar_year": count_table(events, lambda e: e["ex_date"][:4]),
        "counts_by_trailing_12_months": count_table(events, trailing),
        "returns": returns,
    }


def print_summary(summary: dict) -> None:
    cols = ["forward_stock", "forward_etf", "forward_otc", "reverse_stock", "reverse_etf", "reverse_otc"]
    for title, key in (("calendar year (ex_date)", "counts_by_calendar_year"),
                       ("trailing 12 months", "counts_by_trailing_12_months")):
        print(f"\nSplit events by {title}:")
        print(f"  {'period':26s}" + "".join(f"{c:>15s}" for c in cols) + f"{'total':>8s}")
        for period, c in summary[key].items():
            print(f"  {period:26s}" + "".join(f"{c.get(col, 0):15d}" for col in cols) + f"{sum(c.values()):8d}")
    print(f"\nMeasured {summary['events_measured']} of {summary['events_total']} events; skipped {summary['skipped']}")
    for name, stats in summary["returns"].items():
        print(f"\n{name}")
        print(f"  {'window':8s} {'n':>5s} {'mean%':>7s} {'median%':>8s} {'%pos':>6s} {'p10%':>7s} {'p90%':>7s}")
        for w, d in stats.items():
            if d["n"] == 0:
                print(f"  {w:8s} {0:5d}")
                continue
            print(f"  {w:8s} {d['n']:5d} {d['mean_pct']:7.2f} {d['median_pct']:8.2f} "
                  f"{d['pct_positive']:6.1f} {d['p10_pct']:7.2f} {d['p90_pct']:7.2f}")


# --------------------------------------------------------------------------
def main() -> None:
    if not server.HEADERS["APCA-API-KEY-ID"]:
        sys.exit("ALPACA_API_KEY / ALPACA_API_SECRET not found in .env")
    server.resolve_feed()
    window_end = date.today()
    window_start = window_end.replace(year=window_end.year - LOOKBACK_YEARS)

    print(f"fetching splits with ex_date in [{window_start}, {window_end}]", file=sys.stderr)
    events = fetch_splits(window_start, window_end)
    print(f"{len(events)} split events", file=sys.stderr)

    assets = fetch_assets()
    for ev in events:
        a = assets.get(ev["symbol"])
        ev["security_type"] = classify(a)
        ev["name"] = a["name"] if a else ""
        ev["exchange"] = a["exchange"] if a else ""
        ev["asset_record"] = "present" if a else "missing"
    print("security types:", dict(Counter(e["security_type"] for e in events)), file=sys.stderr)

    bars_by_month = fetch_bars_for_events(events)
    for ev in events:
        if ev["security_type"] == "unknown":
            has_bars = bool(bars_by_month.get(ev["ex_date"][:7], {}).get(ev["symbol"]))
            ev["security_type"] = "stock" if has_bars else "otc"
            ev["asset_record"] = "missing (delisted since)" if has_bars else "missing (uncovered by Alpaca)"
    print("security types after bar check:", dict(Counter(e["security_type"] for e in events)), file=sys.stderr)

    rows, skipped = [], Counter()
    for ev in events:
        bars = bars_by_month.get(ev["ex_date"][:7], {}).get(ev["symbol"]) or []
        row, why = measure(ev, bars)
        if row is None:
            skipped[f"{why}:{ev['security_type']}"] += 1
        else:
            rows.append(row)

    fields = ["kind", "security_type", "symbol", "new_symbol", "name", "exchange", "asset_record", "ex_date",
              "old_rate", "new_rate", "ratio", "pre_close_date", "pre_close"] + \
             [f"ret_{n}d_pct" for n in WINDOWS] + ["ex_ret_pct", "ex_jump_matches_ratio"] + \
             [f"post_{n}d_pct" for n in POST_WINDOWS]
    with CSV_OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    summary = summarize(events, rows, skipped, window_start, window_end)
    JSON_OUT.write_text(json.dumps(summary, indent=2))
    print_summary(summary)
    print(f"\nwrote {CSV_OUT}\nwrote {JSON_OUT}")


if __name__ == "__main__":
    main()
