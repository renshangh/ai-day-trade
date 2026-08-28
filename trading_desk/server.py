"""Trading desk dashboard server.

Stdlib only -- no pip installs. Serves a static dashboard plus a small JSON API
backed by real Alpaca market data.

RULE #1 (AGENTS.md): no fabricated market data. If a symbol's bars are missing or
too short we drop it from the board and report it under `omitted`; we never
substitute, interpolate, or carry forward a price. On a fetch failure we fall back
to the last known-good cache and mark the payload `stale` rather than serving an
empty or partial board as if it were fresh.

Usage:
    python3 trading_desk/server.py [--port 8799]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
# Running `python3 trading_desk/server.py` puts only trading_desk/ on sys.path,
# so the repo root has to be added for the optional `lumibot` SEC import.
sys.path.append(str(REPO_ROOT))

import fundamentals  # noqa: E402
import earnings  # noqa: E402
import indicators  # noqa: E402
import universe  # noqa: E402

ALPACA_DATA = "https://data.alpaca.markets"
CACHE_PATH = HERE / "cache.json"

# Feed selection.
#
# IEX is real-time but is a single venue: measured against SIP it carries only
# ~2.5-4% of consolidated volume, so every volume and dollar-volume figure taken
# from it is understated by roughly 25-40x. Closing prices agree to within 0.2%,
# so rankings are unaffected either way -- but liquidity is not something to be
# wrong about by an order of magnitude when it is being read as tradability.
#
# This subscription can query SIP as long as the window ends at least 15 minutes
# ago ("subscription does not permit querying recent SIP data" otherwise). The
# board runs on daily bars, where a 15-minute-old cutoff is worth nothing during
# a session and nothing at all outside one, so SIP is the better trade. We probe
# once at startup and fall back to IEX if SIP is not permitted.
SIP_DELAY_MINUTES = 16
FEED = "iex"
FEED_NOTE = "not yet resolved"

BOARD_TTL = 300  # seconds
STOCK_TTL = 300
LOOKBACKS = [1, 2, 3, 4, 5]
# Reversal candidates need a "prior period" before the trigger day, so a
# 1-session window has nothing to reverse from.
REVERSAL_LOOKBACKS = [2, 3, 4, 5]
TOP_N = 5
# Shared so the client and the API cannot drift to different "defaults".
DEFAULT_HORIZON_DAYS = 30
# A reversal candidate must have been genuinely down before today, not just
# flat. Scaled per prior session rather than fixed, so a 4-day prior period
# needs more cumulative decline than a 1-day one to qualify -- a flat fixed
# threshold would let a window with 3 do-nothing days and a random red hair
# qualify on the same footing as a real 4-day slide.
REVERSAL_MIN_DECLINE_PER_DAY = -0.75
# Per-symbol payloads are ~200 KB each. Cap the in-memory cache so browsing every
# group cannot grow it without bound.
STOCK_CACHE_MAX = 60
# Filings change quarterly and headlines hourly; 15 minutes is plenty.
DETAIL_TTL = 900
DETAIL_CACHE_MAX = 60
# Tied to STOCK_TTL on purpose. The review reuses the per-symbol stock cache, so
# rebuilding more often than the bars can change would stamp a fresh "built at"
# time on prices up to STOCK_TTL old -- the page would overstate its own
# freshness. Equal means a rebuild and a bar refresh come due together.
REVIEW_TTL = STOCK_TTL
# Holdings deliberately left out of the review's risk math and flags, at the
# desk owner's instruction. They are still reported, in a separate section:
# silently dropping a real position would make the review actively misleading
# about concentration -- and IBIT alone is over half the book.
#
# A mapping rather than a set so the reason travels with the symbol and shows up
# on the page. "Excluded" covers two quite different cases and a bare set would
# flatten them: one is a large position the owner does not want commentary on,
# the other is a residual too small to act on.
REVIEW_EXCLUDE: dict[str, str] = {
    "IBIT": "Bitcoin position, held by choice — not part of the swing book",
    "SNDL": "Residual position, too small to act on",
}
# The desk owner's stated swing horizon. A print landing inside this window
# while a position is open is the case the earnings flag exists to catch.
# `SWING_WINDOW_DAYS` in app.js must match; the client cannot import this.
SWING_WINDOW_DAYS = 21
# A position sitting this close to a level is "at" it for review purposes.
# Expressed in ATR rather than percent because a 14%-ATR name and a 6%-ATR name
# are not equally close at the same percentage distance.
LEVEL_PROXIMITY_ATR = 0.5

_lock = threading.Lock()
_board_build_lock = threading.Lock()
_earnings_build_lock = threading.Lock()
_review_build_lock = threading.Lock()
_cache: dict = {"board": None, "board_ts": 0.0, "stocks": {}, "details": {}, "earnings": {},
                "review": None, "review_ts": 0.0}


# --------------------------------------------------------------------------
# Environment / credentials
# --------------------------------------------------------------------------
def load_env() -> dict[str, str]:
    """Read .env from the repo root without printing any values."""
    env: dict[str, str] = {}
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("ALPACA_API_KEY", "ALPACA_API_SECRET"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


ENV = load_env()
HEADERS = {
    "APCA-API-KEY-ID": ENV.get("ALPACA_API_KEY", ""),
    "APCA-API-SECRET-KEY": ENV.get("ALPACA_API_SECRET", ""),
}


# --------------------------------------------------------------------------
# Alpaca client
# --------------------------------------------------------------------------
def _get(url: str, retries: int = 4) -> dict:
    """GET with exponential backoff on 429/5xx."""
    delay = 1.0
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
        except Exception as e:  # noqa: BLE001 - network layer, retry then surface
            last_err = e
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError(f"request failed: {last_err}")


def resolve_feed() -> None:
    """Pick the best feed this subscription can actually read, once at startup."""
    global FEED, FEED_NOTE
    end = datetime.now(timezone.utc) - timedelta(minutes=SIP_DELAY_MINUTES)
    params = {
        "symbols": "SPY",
        "timeframe": "1Day",
        "start": (end - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "limit": 1,
        "feed": "sip",
    }
    try:
        _get(f"{ALPACA_DATA}/v2/stocks/bars?{urllib.parse.urlencode(params)}", retries=1)
        FEED = "sip"
        FEED_NOTE = f"consolidated tape, delayed {SIP_DELAY_MINUTES}m"
    except Exception:  # noqa: BLE001 - any refusal means fall back
        FEED = "iex"
        FEED_NOTE = "IEX only (single venue, ~3% of consolidated volume)"
    print(f"[info] feed={FEED} ({FEED_NOTE})")


def _window_end(end: datetime) -> datetime:
    """Clamp the request window so SIP stays outside its no-recent-data guard."""
    if FEED != "sip":
        return end
    return min(end, datetime.now(timezone.utc) - timedelta(minutes=SIP_DELAY_MINUTES))


def fetch_daily_bars(symbols: list[str], start: datetime, end: datetime) -> dict[str, list[dict]]:
    """Fetch adjusted daily bars for many symbols, following pagination."""
    out: dict[str, list[dict]] = {}
    end = _window_end(end)
    chunk_size = 100
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i : i + chunk_size]
        page_token = None
        while True:
            params = {
                "symbols": ",".join(chunk),
                "timeframe": "1Day",
                "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "adjustment": "all",
                "sort": "asc",
                "limit": 10000,
                "feed": FEED,
            }
            if page_token:
                params["page_token"] = page_token
            data = _get(f"{ALPACA_DATA}/v2/stocks/bars?{urllib.parse.urlencode(params)}")
            for sym, bars in (data.get("bars") or {}).items():
                out.setdefault(sym, []).extend(bars)
            page_token = data.get("next_page_token")
            if not page_token:
                break
    return out


# --------------------------------------------------------------------------
# Board computation
# --------------------------------------------------------------------------
def pct_return(bars: list[dict], n_days: int) -> float | None:
    """Return over the last `n_days` trading sessions, or None if too short.

    Uses actual returned bars as the trading-day calendar, so holidays and
    halts shift the window rather than producing a fabricated value.
    """
    if len(bars) < n_days + 1:
        return None
    prior = float(bars[-(n_days + 1)]["c"])
    latest = float(bars[-1]["c"])
    if prior <= 0:
        return None
    return (latest / prior - 1.0) * 100.0


def reversal_metrics(bars: list[dict], lb: int) -> dict | None:
    """Trigger-day bounce, prior-period decline, and volume confirmation for one symbol.

    `lb` is the total sessions considered: the most recent one (the trigger
    day) plus `lb - 1` sessions before it (the prior/decline period). Returns
    None if there isn't enough history or the symbol doesn't actually qualify
    as a reversal (prior period down past the threshold, trigger day positive).
    """
    if len(bars) < lb + 1:
        return None
    trigger_return = pct_return(bars, 1)
    prior_return = pct_return(bars[:-1], lb - 1)
    if trigger_return is None or prior_return is None:
        return None
    if prior_return > REVERSAL_MIN_DECLINE_PER_DAY * (lb - 1) or trigger_return <= 0:
        return None

    prior_volumes = [float(b["v"]) for b in bars[-lb:-1]]
    prior_avg_volume = sum(prior_volumes) / len(prior_volumes) if prior_volumes else 0.0
    volume_ratio = (float(bars[-1]["v"]) / prior_avg_volume) if prior_avg_volume > 0 else None

    return {
        "trigger_return_pct": trigger_return,
        "prior_return_pct": prior_return,
        "volume_ratio": volume_ratio,
        "last_close": float(bars[-1]["c"]),
        "volume": float(bars[-1]["v"]),
        "date": bars[-1]["t"][:10],
    }


def build_board() -> dict:
    """Rank every group per lookback and pick the top movers inside the leader."""
    end = datetime.now(timezone.utc)
    # 30 calendar days comfortably covers 5 trading days plus holidays.
    start = end - timedelta(days=30)

    symbols = universe.all_symbols()
    bars_by_symbol = fetch_daily_bars(symbols, start, end)

    groups = universe.all_groups()
    omitted: dict[str, list[str]] = {}
    board: dict[str, dict] = {}

    # Today's single-day return per benchmark, for the reversal view's "vs SPY"
    # context. This doesn't depend on lb, so it's computed once and reused
    # across every reversal block below rather than recomputed per lookback.
    benchmarks_1d = [
        {"symbol": b, "return_pct": pct_return(bars_by_symbol.get(b) or [], 1)}
        for b in universe.BENCHMARKS
    ]

    for lb in LOOKBACKS:
        rankings = []
        reversal_rankings = []
        for gname, cfg in groups.items():
            members = []
            reversal_qualifiers = []
            missing = []
            for sym in cfg["constituents"]:
                bars = bars_by_symbol.get(sym) or []
                r = pct_return(bars, lb)
                if r is None:
                    missing.append(sym)
                    continue
                members.append(
                    {
                        "symbol": sym,
                        "return_pct": r,
                        "last_close": float(bars[-1]["c"]),
                        "volume": float(bars[-1]["v"]),
                        "date": bars[-1]["t"][:10],
                    }
                )
                if lb in REVERSAL_LOOKBACKS:
                    rm = reversal_metrics(bars, lb)
                    if rm is not None:
                        reversal_qualifiers.append({"symbol": sym, **rm})
            if missing:
                omitted.setdefault(gname, []).extend(sorted(set(missing)))

            if members:
                returns = [m["return_pct"] for m in members]
                etf_sym = cfg.get("etf")
                etf_return = pct_return(bars_by_symbol.get(etf_sym) or [], lb) if etf_sym else None

                members.sort(key=lambda m: m["return_pct"], reverse=True)
                rankings.append(
                    {
                        "group": gname,
                        "kind": cfg["kind"],
                        "etf": etf_sym,
                        "etf_return_pct": etf_return,
                        "mean_return_pct": sum(returns) / len(returns),
                        "median_return_pct": statistics.median(returns),
                        "breadth_pct": sum(1 for r in returns if r > 0) / len(returns) * 100.0,
                        "member_count": len(members),
                        "top": members[:TOP_N],
                    }
                )

            # A group only appears in the reversal view if at least one
            # constituent actually qualified -- an empty-handed group has
            # nothing honest to show here, unlike the momentum view where
            # every priced group gets a (possibly negative) mean return.
            if reversal_qualifiers:
                triggers = [q["trigger_return_pct"] for q in reversal_qualifiers]
                priors = [q["prior_return_pct"] for q in reversal_qualifiers]
                vol_ratios = [q["volume_ratio"] for q in reversal_qualifiers if q["volume_ratio"] is not None]
                reversal_qualifiers.sort(key=lambda q: q["trigger_return_pct"], reverse=True)
                reversal_rankings.append(
                    {
                        "group": gname,
                        "kind": cfg["kind"],
                        "avg_trigger_return_pct": sum(triggers) / len(triggers),
                        "avg_prior_return_pct": sum(priors) / len(priors),
                        "avg_volume_ratio": (sum(vol_ratios) / len(vol_ratios)) if vol_ratios else None,
                        "qualifying_count": len(reversal_qualifiers),
                        "evaluated_count": len(members),
                        "breadth_pct": len(reversal_qualifiers) / len(members) * 100.0 if members else 0.0,
                        "top": reversal_qualifiers[:TOP_N],
                    }
                )

        rankings.sort(key=lambda g: g["mean_return_pct"], reverse=True)
        # Most names reversing, then biggest average bounce among those that did.
        reversal_rankings.sort(key=lambda g: (g["breadth_pct"], g["avg_trigger_return_pct"]), reverse=True)
        benchmarks = [
            {
                "symbol": b,
                "return_pct": pct_return(bars_by_symbol.get(b) or [], lb),
            }
            for b in universe.BENCHMARKS
        ]
        board[str(lb)] = {
            "lookback_days": lb,
            "rankings": rankings,
            "hottest": rankings[0] if rankings else None,
            "benchmarks": benchmarks,
            "reversal": (
                {
                    "rankings": reversal_rankings,
                    "leader": reversal_rankings[0] if reversal_rankings else None,
                    "benchmarks_1d": benchmarks_1d,
                }
                if lb in REVERSAL_LOOKBACKS
                else None
            ),
        }

    latest_dates = [b[-1]["t"][:10] for b in bars_by_symbol.values() if b]
    # `omitted` accumulates once per lookback pass, so dedupe before reporting --
    # otherwise a single missing symbol is counted five times.
    omitted = {g: sorted(set(syms)) for g, syms in omitted.items()}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_session": max(latest_dates) if latest_dates else None,
        "feed": FEED,
        "feed_note": FEED_NOTE,
        "lookbacks": board,
        "omitted": omitted,
        "universe_size": len(symbols),
        "stale": False,
    }


def get_board(force: bool = False) -> dict:
    """Cached board with last-good fallback on failure."""
    with _lock:
        cached = _cache.get("board")
        age = time.time() - _cache.get("board_ts", 0.0)
        if cached and not force and age < BOARD_TTL:
            return cached

    # Serialize builds. Without this, N concurrent requests on a cold cache each
    # kick off a full 271-symbol fetch; the loser(s) re-check the cache after the
    # winner finishes and reuse its result.
    with _board_build_lock:
        with _lock:
            cached = _cache.get("board")
            age = time.time() - _cache.get("board_ts", 0.0)
            if cached and not force and age < BOARD_TTL:
                return cached
        try:
            board = build_board()
            with _lock:
                _cache["board"] = board
                _cache["board_ts"] = time.time()
                save_cache()
            return board
        except Exception as e:  # noqa: BLE001 - degrade to last-good rather than blank
            with _lock:
                cached = _cache.get("board")
            if cached:
                stale = dict(cached)
                stale["stale"] = True
                stale["stale_reason"] = str(e)
                return stale
            raise


def get_stock(symbol: str, force: bool = False) -> dict:
    """Two years of daily bars plus the full indicator set for one symbol."""
    symbol = symbol.upper().strip()
    with _lock:
        entry = _cache["stocks"].get(symbol)
        if entry and not force and time.time() - entry["ts"] < STOCK_TTL:
            return entry["data"]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=760)  # ~2y, enough warmup for SMA200
    try:
        bars = (fetch_daily_bars([symbol], start, end)).get(symbol) or []
    except Exception as e:  # noqa: BLE001
        with _lock:
            entry = _cache["stocks"].get(symbol)
        if entry:
            stale = dict(entry["data"])
            stale["stale"] = True
            stale["stale_reason"] = str(e)
            return stale
        raise

    if not bars:
        # Real absence, surfaced as absence.
        return {"symbol": symbol, "bars": [], "indicators": {}, "error": "no bars returned"}

    data = {
        "symbol": symbol,
        "feed": FEED,
        "feed_note": FEED_NOTE,
        "bars": [
            {
                "t": b["t"][:10],
                "o": float(b["o"]),
                "h": float(b["h"]),
                "l": float(b["l"]),
                "c": float(b["c"]),
                "v": float(b["v"]),
            }
            for b in bars
        ],
        "indicators": indicators.compute_all(bars),
        # Levels are horizontal, not per-bar, so they travel beside the series
        # rather than inside them. Computed over the full history: a level set
        # nine months ago still matters if price is near it now.
        "levels": indicators.support_resistance(bars),
        "stale": False,
    }
    with _lock:
        stocks = _cache["stocks"]
        stocks[symbol] = {"ts": time.time(), "data": data}
        # Evict least-recently-fetched beyond the cap.
        if len(stocks) > STOCK_CACHE_MAX:
            for old in sorted(stocks, key=lambda s: stocks[s]["ts"])[: len(stocks) - STOCK_CACHE_MAX]:
                del stocks[old]
    # Deliberately no save_cache() here -- see save_cache's docstring.
    return data


def get_detail(symbol: str, force: bool = False) -> dict:
    """Company detail: SEC fundamentals, price-derived stats, news, and links.

    Each block degrades independently -- a SEC outage must not take the news
    list down with it, and vice versa.
    """
    symbol = symbol.upper().strip()
    with _lock:
        entry = _cache["details"].get(symbol)
        if entry and not force and time.time() - entry["ts"] < DETAIL_TTL:
            return entry["data"]

    # Price context comes from the bars we already fetch for the chart.
    last_price = None
    stats: dict = {}
    try:
        stock = get_stock(symbol)
        bars = stock.get("bars") or []
        ind = stock.get("indicators") or {}
        if bars:
            last_price = bars[-1]["c"]
            year = bars[-252:] if len(bars) >= 252 else bars
            highs = [b["h"] for b in year]
            lows = [b["l"] for b in year]
            hi, lo = max(highs), min(lows)
            atr = (ind.get("atr14") or [None])[-1]
            tdr = (ind.get("tdr14") or [None])[-1]
            vol20 = (ind.get("vol_sma20") or [None])[-1]
            stats = {
                "last_price": last_price,
                "session": bars[-1]["t"],
                "week52_high": hi,
                "week52_low": lo,
                # Where price sits inside the 52w range, 0 = at low, 100 = at high.
                "range_position_pct": ((last_price - lo) / (hi - lo) * 100) if hi > lo else None,
                "atr14": atr,
                "atr_pct": (atr / last_price * 100) if (atr and last_price) else None,
                "tdr14": tdr,
                "tdr_pct": (tdr / last_price * 100) if (tdr and last_price) else None,
                # ATR counts overnight gaps, TDR does not, so the shortfall is the
                # share of average range that arrives as a gap rather than as
                # intraday movement. None rather than 0 when either is missing.
                "gap_share_pct": (
                    (atr - tdr) / atr * 100 if (atr and tdr and atr > 0) else None
                ),
                "avg_volume_20d": vol20,
                "dollar_volume_20d": (vol20 * last_price) if (vol20 and last_price) else None,
                "bars_used_for_52w": len(year),
            }
    except Exception as e:  # noqa: BLE001
        stats = {"error": str(e)}

    try:
        fund = fundamentals.get_fundamentals(symbol, last_price)
    except Exception as e:  # noqa: BLE001
        fund = {"available": False, "reason": f"fundamentals error: {e}"}

    try:
        news = fundamentals.get_news(
            symbol, HEADERS["APCA-API-KEY-ID"], HEADERS["APCA-API-SECRET-KEY"]
        )
        news_error = None
    except Exception as e:  # noqa: BLE001
        news, news_error = [], str(e)

    data = {
        "symbol": symbol,
        "stats": stats,
        "fundamentals": fund,
        "news": news,
        "news_error": news_error,
        "links": fundamentals.research_links(symbol, fund.get("cik")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        details = _cache["details"]
        details[symbol] = {"ts": time.time(), "data": data}
        if len(details) > DETAIL_CACHE_MAX:
            for old in sorted(details, key=lambda s: details[s]["ts"])[: len(details) - DETAIL_CACHE_MAX]:
                del details[old]
    return data


# --------------------------------------------------------------------------
# Earnings calendar (timing awareness)
# --------------------------------------------------------------------------
EARNINGS_TTL = 3600  # dates move rarely; an hour is plenty
# The handler accepts any horizon in 1..400, so without a cap an external caller
# could mint 400 payloads. Same reasoning as STOCK_CACHE_MAX / DETAIL_CACHE_MAX.
EARNINGS_CACHE_MAX = 8
JOURNAL_PATH = REPO_ROOT / "trading_records" / "trades-schwab.csv"


def open_positions(rows: list[dict] | None = None) -> dict[str, dict]:
    """Symbols currently held, aggregated from the local trade journal.

    Pass `rows` (from `journal_open_rows()`) to aggregate an already-read
    snapshot instead of opening the file again. The review needs both the
    aggregate and the individual lots, and reading the CSV twice let the two
    disagree if the file changed in between -- which surfaced as flag text like
    "No stop recorded on 3 of 2 open lot(s)".

    The journal is gitignored and optional -- this is a convenience so a print
    landing inside a live holding period is impossible to miss, which is the
    single most useful thing this feature can do. A missing or malformed file is
    not an error; the calendar just loses the "you hold this" flag.
    """
    held: dict[str, dict] = {}
    if rows is None:
        if not JOURNAL_PATH.exists():
            return {}
        rows = journal_open_rows()
    try:
        for row in rows:
            if (row.get("status") or "").strip().lower() != "open":
                continue
            sym = (row.get("symbol") or "").strip().upper()
            if not sym:
                continue
            # Aggregate, never overwrite. A symbol legitimately has several
            # open lots (two FN buys on the same day at different prices);
            # keying by symbol and assigning would report the last lot only
            # and halve the stated exposure on the one alert that exists to
            # stop an earnings event going unnoticed.
            try:
                qty = float(row.get("qty") or 0)
                price = float(row.get("entry_price") or 0)
            except ValueError:
                continue
            if qty <= 0:
                continue
            acc = held.setdefault(sym, {"qty": 0.0, "cost": 0.0, "lots": 0,
                                        "entry_date": row.get("entry_date", "")})
            acc["qty"] += qty
            acc["cost"] += qty * price
            acc["lots"] += 1
            d = row.get("entry_date", "")
            if d and (not acc["entry_date"] or d < acc["entry_date"]):
                acc["entry_date"] = d   # earliest entry across the lots
    except Exception as e:  # noqa: BLE001 - journal is best-effort context
        print(f"[warn] could not read journal: {e}", file=sys.stderr)
    for acc in held.values():
        acc["avg_entry"] = (acc["cost"] / acc["qty"]) if acc["qty"] else None
    return held


def journal_open_rows() -> list[dict]:
    """Raw open rows from the trade journal, one per lot.

    `open_positions()` aggregates lots by symbol, which is right for the
    earnings flag but loses the per-lot fields the review reports on -- a
    missing `stop` is a property of the lot, not of the symbol. Kept separate
    rather than folded into `open_positions` so that function's contract, and
    the earnings view that depends on it, do not change.
    """
    if not JOURNAL_PATH.exists():
        return []
    rows: list[dict] = []
    try:
        with JOURNAL_PATH.open() as f:
            for row in csv.DictReader(f):
                if (row.get("status") or "").strip().lower() == "open":
                    rows.append(row)
    except Exception as e:  # noqa: BLE001 - journal is best-effort context
        print(f"[warn] could not read journal rows: {e}", file=sys.stderr)
    return rows


def _symbol_groups() -> dict[str, list[str]]:
    """symbol -> group names, so the review can report theme concentration."""
    out: dict[str, list[str]] = {}
    for name, cfg in universe.all_groups().items():
        for sym in cfg.get("constituents", []):
            out.setdefault(sym.upper(), []).append(name)
    return out


def _last_of(series: list) -> float | None:
    """Most recent non-None value of an indicator series."""
    for v in reversed(series or []):
        if v is not None:
            return float(v)
    return None


def _review_one(symbol: str, held: dict, lots: list[dict], groups: dict[str, list[str]],
                *, force: bool = False) -> dict:
    """Everything the review reports for one holding.

    Raises nothing: a symbol whose bars fail to load comes back with `error`
    set, so one bad name cannot blank the whole review.
    """
    entry: dict = {
        "symbol": symbol,
        "qty": held.get("qty"),
        "avg_entry": held.get("avg_entry"),
        "cost": held.get("cost"),
        "lots": held.get("lots"),
        "entry_date": held.get("entry_date") or None,
        "groups": groups.get(symbol, []),
        "excluded": symbol in REVIEW_EXCLUDE,
        "exclusion_reason": REVIEW_EXCLUDE.get(symbol),
        # Journal hygiene is a fact about the record, available even when the
        # market data fetch fails, so it is filled in before anything else.
        "lots_without_stop": sum(1 for r in lots if not (r.get("stop") or "").strip()),
        "lots_without_thesis": sum(1 for r in lots if not (r.get("thesis") or "").strip()),
        "lots_without_setup": sum(1 for r in lots if not (r.get("setup") or "").strip()),
    }
    try:
        stock = get_stock(symbol, force=force)
    except Exception as e:  # noqa: BLE001 - one dead symbol must not kill the review
        entry["error"] = str(e)
        return entry
    bars = stock.get("bars") or []
    if len(bars) < 2:
        entry["error"] = stock.get("error") or "not enough bars"
        return entry

    ind = stock.get("indicators") or {}
    last = float(bars[-1]["c"])
    prev = float(bars[-2]["c"])
    atr = _last_of(ind.get("atr14"))
    entry.update({
        "session": bars[-1]["t"],
        "last": last,
        "prev_close": prev,
        "day_pct": (last / prev - 1.0) * 100.0 if prev else None,
        "rsi14": _last_of(ind.get("rsi14")),
        "atr14": atr,
        "atr_pct": (atr / last * 100.0) if (atr and last) else None,
        "stale": bool(stock.get("stale")),
    })
    if entry["avg_entry"]:
        entry["pnl"] = (last - entry["avg_entry"]) * entry["qty"]
        entry["pnl_pct"] = (last / entry["avg_entry"] - 1.0) * 100.0
    entry["market_value"] = last * entry["qty"] if entry["qty"] else None

    for key in ("sma20", "sma50", "sma200"):
        ma = _last_of(ind.get(key))
        entry[key] = ma
        entry[f"vs_{key}_pct"] = ((last / ma - 1.0) * 100.0) if ma else None

    # Levels: nearest on each side, with distance in ATR as well as percent.
    # Percent alone is misleading across names whose ATRs differ by 3x.
    levels = stock.get("levels") or []
    below = [l for l in levels if l.get("level") is not None and l["level"] < last]
    above = [l for l in levels if l.get("level") is not None and l["level"] > last]
    def shape(l: dict | None) -> dict | None:
        if not l:
            return None
        px = float(l["level"])
        return {
            "level": px,
            "distance_pct": (px / last - 1.0) * 100.0,
            "distance_atr": (abs(last - px) / atr) if atr else None,
            "touches": l.get("touches"),
            "tests": l.get("tests"),
            "last_touch": l.get("last_touch"),
        }
    sup = shape(max(below, key=lambda l: l["level"]) if below else None)
    res = shape(min(above, key=lambda l: l["level"]) if above else None)
    entry["nearest_support"] = sup
    entry["nearest_resistance"] = res
    # Downside to the nearest support, measured from today's price. This is
    # remaining risk to that level, NOT the risk taken at entry -- an
    # underwater position has already spent the difference.
    if sup and entry["qty"]:
        entry["risk_to_support"] = (last - sup["level"]) * entry["qty"]
    return entry


def _review_flags(e: dict, earn: dict | None) -> list[dict]:
    """Observations worth a second look, as facts rather than instructions.

    Each flag states something measurable about the position. None of them says
    what to do -- that judgement is the desk owner's, and a dashboard that
    dressed these up as signals would be pretending to an edge none of them has.
    """
    flags: list[dict] = []
    if e.get("error"):
        return [{"key": "no_data", "level": "warn", "text": f"No market data: {e['error']}"}]

    if e.get("lots_without_stop"):
        n, total = e["lots_without_stop"], e.get("lots") or 0
        flags.append({"key": "no_stop", "level": "warn",
                      "text": f"No stop recorded on {n} of {total} open lot(s)"})
    if e.get("lots_without_thesis"):
        flags.append({"key": "no_thesis", "level": "info",
                      "text": f"No thesis recorded on {e['lots_without_thesis']} lot(s)"})

    sup, res = e.get("nearest_support"), e.get("nearest_resistance")
    if sup and sup.get("distance_atr") is not None and sup["distance_atr"] <= LEVEL_PROXIMITY_ATR:
        flags.append({"key": "at_support", "level": "warn",
                      "text": f"Sitting on support {sup['level']:.2f} "
                              f"({sup['distance_atr']:.1f} ATR below, "
                              f"{sup.get('tests') or 0} tests)"})
    if res and res.get("distance_atr") is not None and res["distance_atr"] <= LEVEL_PROXIMITY_ATR:
        flags.append({"key": "at_resistance", "level": "info",
                      "text": f"Under resistance {res['level']:.2f} "
                              f"({res['distance_atr']:.1f} ATR above, "
                              f"{res.get('tests') or 0} tests)"})
    if not sup:
        flags.append({"key": "no_support", "level": "warn",
                      "text": "No support level below price in the tested history"})

    below = [k for k in ("sma20", "sma50", "sma200")
             if e.get(f"vs_{k}_pct") is not None and e[f"vs_{k}_pct"] < 0]
    if len(below) == 3:
        flags.append({"key": "below_all_ma", "level": "warn",
                      "text": "Below the 20, 50 and 200-day averages"})
    elif below:
        flags.append({"key": "below_ma", "level": "info",
                      "text": "Below the " + ", ".join(k.replace("sma", "") for k in below)
                              + "-day average" + ("s" if len(below) > 1 else "")})

    rsi = e.get("rsi14")
    if rsi is not None and rsi < 30:
        flags.append({"key": "oversold", "level": "info", "text": f"RSI {rsi:.0f} (below 30)"})
    elif rsi is not None and rsi > 70:
        flags.append({"key": "overbought", "level": "info", "text": f"RSI {rsi:.0f} (above 70)"})

    if earn and earn.get("days_until") is not None:
        d = earn["days_until"]
        if d <= SWING_WINDOW_DAYS:
            flags.append({"key": "earnings_soon", "level": "warn",
                          "text": f"Earnings in ~{d}d ({earn.get('projected_date')}, estimated) "
                                  f"while holding"})
    if e.get("stale"):
        flags.append({"key": "stale_quote", "level": "info",
                      "text": "Quote served from cache after a failed fetch"})
    return flags


def build_position_review(force: bool = False) -> dict:
    """Per-holding state, levels, risk-to-support and journal gaps.

    Deliberately reuses `get_stock`, so a review right after browsing the board
    is nearly free and the numbers cannot disagree with the chart.
    """
    rows = journal_open_rows()
    held = open_positions(rows)
    if not held:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "positions": [], "excluded": [],
            "error": f"No open positions in {JOURNAL_PATH.name}. "
                     "Record entries there and the review fills in.",
        }

    lots_by_symbol: dict[str, list[dict]] = {}
    for r in rows:
        lots_by_symbol.setdefault((r.get("symbol") or "").strip().upper(), []).append(r)

    groups = _symbol_groups()
    events = earnings.load_event_file()
    today = datetime.now(timezone.utc).date()

    reviewed, excluded = [], []
    for symbol in sorted(held):
        e = _review_one(symbol, held[symbol], lots_by_symbol.get(symbol, []), groups,
                        force=force)
        earn = None
        if symbol in events:
            try:
                earn = earnings.project_next(events[symbol], today)
            except Exception:  # noqa: BLE001 - a projection is context, never fatal
                earn = None
        e["earnings"] = earn
        if e["excluded"]:
            # No flags and no risk math: excluded by instruction, still reported.
            e.pop("risk_to_support", None)
            e["flags"] = []
            excluded.append(e)
        else:
            e["flags"] = _review_flags(e, earn)
            reviewed.append(e)

    # Closest to its support first: that is the position where the level the
    # journal would key a stop off is nearest, so it is the one worth reading
    # first. Names with no support at all sort to the top -- nothing to lean on
    # is more notable than sitting near something.
    def sort_key(e: dict):
        s = e.get("nearest_support")
        if e.get("error"):
            return (0, 0.0)
        if not s or s.get("distance_atr") is None:
            return (1, 0.0)
        return (2, s["distance_atr"])
    reviewed.sort(key=sort_key)

    def totals(items: list[dict]) -> dict:
        mv = sum(i["market_value"] for i in items if i.get("market_value"))
        cost = sum(i["cost"] for i in items if i.get("cost"))
        return {
            "market_value": mv, "cost": cost,
            # Presence, not truthiness: a legitimate 0.0 must not read as missing.
            "pnl": (mv - cost) if cost else None,
            "pnl_pct": ((mv / cost - 1.0) * 100.0) if cost else None,
        }

    t_rev = totals(reviewed)
    excluded_mv = sum(i["market_value"] for i in excluded if i.get("market_value"))
    book_mv = (t_rev["market_value"] or 0.0) + excluded_mv
    for e in reviewed + excluded:
        e["book_weight_pct"] = (e["market_value"] / book_mv * 100.0) if (book_mv and e.get("market_value")) else None

    # Theme concentration across the reviewed names only -- the excluded holding
    # is in no board group, and folding it in would invent a theme for it.
    by_group: dict[str, float] = {}
    for e in reviewed:
        if not e.get("market_value"):
            continue
        for g in e["groups"] or ["(ungrouped)"]:
            by_group[g] = by_group.get(g, 0.0) + e["market_value"]

    risk = sum(e["risk_to_support"] for e in reviewed if e.get("risk_to_support"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feed": FEED,
        "feed_note": FEED_NOTE,
        "journal": JOURNAL_PATH.name,
        "positions": reviewed,
        "excluded": excluded,
        "excluded_note": "Left out of the risk math and flags by instruction. "
                         "Reported here so the weights above still add up.",
        "totals": t_rev,
        "book_market_value": book_mv,
        "risk_to_support": risk,
        "risk_to_support_pct_of_book": (risk / book_mv * 100.0) if book_mv else None,
        "group_exposure": [
            {"group": g, "market_value": v,
             "pct_of_book": (v / book_mv * 100.0) if book_mv else None}
            for g, v in sorted(by_group.items(), key=lambda kv: -kv[1])
        ],
        # Reported at two scopes on purpose. The table shows reviewed positions
        # only, so a tile counting every lot in the journal beside it reads as a
        # contradiction; but the journal-wide figure is the one the README's
        # "trades with no stop should trend to zero" rule is actually about.
        "reviewed_lots_without_stop": sum(e.get("lots_without_stop") or 0 for e in reviewed),
        "reviewed_open_lots": sum(e.get("lots") or 0 for e in reviewed),
        "lots_without_stop": sum(e.get("lots_without_stop") or 0 for e in reviewed + excluded),
        "open_lots": sum(e.get("lots") or 0 for e in reviewed + excluded),
    }


def get_position_review(force: bool = False) -> dict:
    """Cached wrapper. Same build-lock pattern as the board and the calendar."""
    with _lock:
        cached = _cache.get("review")
        if cached and not force and time.time() - _cache.get("review_ts", 0.0) < REVIEW_TTL:
            return cached
    with _review_build_lock:
        with _lock:
            cached = _cache.get("review")
            if cached and not force and time.time() - _cache.get("review_ts", 0.0) < REVIEW_TTL:
                return cached
        data = build_position_review(force=force)
        # A review with no positions is a legitimate answer, but an errored one
        # is not worth caching -- the fix is usually to edit the journal.
        if not data.get("error"):
            with _lock:
                _cache["review"] = data
                _cache["review_ts"] = time.time()
    return data


def build_earnings_calendar(horizon_days: int) -> dict:
    """Upcoming projected prints across the universe, nearest first."""
    events_by_symbol = earnings.load_event_file()
    if not events_by_symbol:
        return {
            "error": "no earnings history on disk -- run research/earnings_dates.py",
            "rows": [], "held_without_dates": [],
        }

    today = datetime.now(timezone.utc).date()
    held = open_positions()
    groups = universe.all_groups()
    group_of: dict[str, str] = {}
    for gname, cfg in groups.items():
        for sym in cfg["constituents"]:
            group_of.setdefault(sym, gname)

    # Group momentum rank, so a print can be read against how hot its group is.
    rank_of: dict[str, int] = {}
    try:
        board = get_board()
        ranked = board["lookbacks"]["5"]["rankings"]
        rank_of = {g["group"]: i + 1 for i, g in enumerate(ranked)}
    except Exception:  # noqa: BLE001 - ranking is context, not a requirement
        pass

    # Two passes. The first only projects dates (no network), so we learn which
    # symbols actually make the cut; the second fetches their bars in one batched
    # request. Calling get_stock per symbol instead meant ~37 separate two-year
    # bar downloads, which made the first load slow enough that the table was
    # still empty seconds after switching to the view.
    shortlist: list[tuple[str, list[dict], dict]] = []
    for sym, events in events_by_symbol.items():
        proj = earnings.project_next(events, today)
        if not proj:
            continue
        # Conservative edge: a print whose *earliest* plausible date is inside
        # the horizon counts even if the point estimate sits just outside.
        #
        # A held position is never filtered out, however distant its print.
        # Dropping it and then listing it as "no date known" is actively
        # misleading -- "POWL reports in 92 days" and "we cannot date POWL" are
        # opposite claims, and only one is true.
        if proj["days_until_earliest"] > horizon_days and sym not in held:
            continue
        shortlist.append((sym, events, proj))

    bars_by_symbol: dict[str, list[dict]] = {}
    if shortlist:
        try:
            end = datetime.now(timezone.utc)
            bars_by_symbol = fetch_daily_bars(
                [s for s, _, _ in shortlist], end - timedelta(days=760), end
            )
        except Exception as e:  # noqa: BLE001 - move stats are optional colour
            print(f"[warn] earnings move stats unavailable: {e}", file=sys.stderr)

    rows = []
    for sym, events, proj in shortlist:
        move = earnings.earnings_move_stats(events, bars_by_symbol.get(sym) or [])

        grp = group_of.get(sym, "(unclassified)")
        rows.append({
            "symbol": sym,
            "group": grp,
            "group_rank_5d": rank_of.get(grp),
            "held": sym in held,
            "reports_today": proj["days_until"] == 0,
            "position": held.get(sym),
            # 1-day reaction: magnitude, lean, and the up/down split.
            "typical_move_pct": (move or {}).get("median_abs_move_pct"),
            "max_move_pct": (move or {}).get("max_abs_move_pct"),
            "signed_move_pct": (move or {}).get("median_signed_move_pct"),
            "up_count": (move or {}).get("up_count"),
            "down_count": (move or {}).get("down_count"),
            "move_sample": (move or {}).get("n"),
            # 1-week follow-through, measured from the same pre-earnings close so
            # it includes the gap rather than starting after it.
            "typical_move_1w_pct": (move or {}).get("median_abs_move_1w_pct"),
            "max_move_1w_pct": (move or {}).get("max_abs_move_1w_pct"),
            "signed_move_1w_pct": (move or {}).get("median_signed_move_1w_pct"),
            "move_sample_1w": (move or {}).get("n_week"),
            **proj,
        })

    rows.sort(key=lambda r: r["projected_date"])

    # A held name with no projectable date is itself worth surfacing -- silence
    # would read as "no earnings coming", which is not what it means.
    dated = {r["symbol"] for r in rows}
    held_without_dates = sorted(set(held) - dated)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": today.isoformat(),
        "horizon_days": horizon_days,
        "rows": rows,
        "held_symbols": sorted(held),
        "held_without_dates": held_without_dates,
        "universe_with_history": len(events_by_symbol),
        "median_error_days": earnings.PROJECTION_MEDIAN_ERROR_DAYS,
        "uncertainty_days": earnings.PROJECTION_P90_ERROR_DAYS,
    }


def get_earnings_calendar(horizon_days: int = DEFAULT_HORIZON_DAYS,
                         force: bool = False) -> dict:
    key = f"cal:{horizon_days}"

    def cached() -> dict | None:
        entry = _cache["earnings"].get(key)
        if entry and not force and time.time() - entry["ts"] < EARNINGS_TTL:
            return entry["data"]
        return None

    with _lock:
        hit = cached()
    if hit is not None:
        return hit

    # One builder at a time: a cold build calls get_board() plus a batched
    # multi-year bar fetch (~10s measured), so two concurrent misses would do the
    # whole thing twice and hit Alpaca twice. Same guard the board uses.
    with _earnings_build_lock:
        with _lock:
            hit = cached()          # another thread may have finished while we waited
        if hit is not None:
            return hit
        data = build_earnings_calendar(horizon_days)
        # Never cache a failure. The error tells the user to run the collector;
        # caching it for an hour would keep showing that message after they had.
        if not data.get("error"):
            with _lock:
                store = _cache["earnings"]
                store[key] = {"ts": time.time(), "data": data}
                if len(store) > EARNINGS_CACHE_MAX:
                    for old in sorted(store, key=lambda k: store[k]["ts"])[
                            : len(store) - EARNINGS_CACHE_MAX]:
                        store.pop(old, None)
    return data


# --------------------------------------------------------------------------
# Cache persistence (last-good survives restarts; a failed fetch never wipes it)
# --------------------------------------------------------------------------
def save_cache() -> None:
    """Persist the board only.

    Per-symbol payloads are deliberately NOT written. They are large (~200 KB
    each, tens of MB in aggregate) and this function runs under the global lock,
    so persisting them meant every stock cache-miss re-serialized the entire
    cache -- hundreds of milliseconds of blocking work per request, and the
    dashboard fires five concurrent stock fetches when it paints a Top 5 strip.
    Stock data stays in memory (still last-good within a session) and is cheap to
    refetch after a restart; the board is the payload whose staleness the UI
    actually surfaces, and it is small.
    """
    try:
        payload = {
            "board": _cache.get("board"),
            "board_ts": _cache.get("board_ts", 0.0),
        }
        tmp = CACHE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(CACHE_PATH)  # atomic; a crash mid-write can't corrupt the cache
    except Exception as e:  # noqa: BLE001 - cache is best-effort
        print(f"[warn] could not save cache: {e}", file=sys.stderr)


def load_cache() -> None:
    if not CACHE_PATH.exists():
        return
    try:
        payload = json.loads(CACHE_PATH.read_text())
        _cache["board"] = payload.get("board")
        _cache["board_ts"] = payload.get("board_ts", 0.0)
        # Older cache files also carried per-symbol payloads; ignore them.
        _cache["stocks"] = {}
        print("[info] loaded cached board" if _cache["board"] else "[info] cache had no board")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] could not load cache: {e}", file=sys.stderr)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[http] {self.address_string()} {fmt % args}")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: dict, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)

        if path in STATIC:
            fname, ctype = STATIC[path]
            fpath = HERE / fname
            if not fpath.exists():
                self._send(404, b"not found", "text/plain")
                return
            self._send(200, fpath.read_bytes(), ctype)
            return

        if path == "/api/board":
            try:
                self._json(get_board(force=qs.get("force", ["0"])[0] == "1"))
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 502)
            return

        if path in ("/api/stock", "/api/detail"):
            sym = (qs.get("symbol") or [""])[0].upper().strip()
            if not sym or not sym.replace(".", "").isalnum():
                self._json({"error": "invalid symbol"}, 400)
                return
            fetch = get_stock if path == "/api/stock" else get_detail
            try:
                self._json(fetch(sym, force=qs.get("force", ["0"])[0] == "1"))
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 502)
            return

        if path == "/api/earnings":
            try:
                horizon = int((qs.get("horizon") or [str(DEFAULT_HORIZON_DAYS)])[0])
            except ValueError:
                horizon = DEFAULT_HORIZON_DAYS
            try:
                self._json(get_earnings_calendar(
                    horizon_days=max(1, min(horizon, 400)),
                    force=qs.get("force", ["0"])[0] == "1",
                ))
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 502)
            return

        if path == "/api/review":
            try:
                self._json(get_position_review(force=qs.get("force", ["0"])[0] == "1"))
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 502)
            return

        if path == "/api/health":
            self._json(
                {
                    "ok": True,
                    "feed": FEED,
                    "feed_note": FEED_NOTE,
                    "has_credentials": bool(HEADERS["APCA-API-KEY-ID"]),
                    "cached_board": _cache.get("board") is not None,
                    "cached_symbols": len(_cache.get("stocks", {})),
                }
            )
            return

        self._send(404, b"not found", "text/plain")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading desk dashboard server")
    # PORT (set by the preview launcher) wins over the default; an explicit
    # --port still overrides both. The dashboard fetches its API on relative
    # URLs, so it works on whatever port it lands on.
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8799)))
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not HEADERS["APCA-API-KEY-ID"] or not HEADERS["APCA-API-SECRET-KEY"]:
        print("ERROR: ALPACA_API_KEY / ALPACA_API_SECRET not found in .env", file=sys.stderr)
        raise SystemExit(1)

    resolve_feed()
    load_cache()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[info] trading desk on http://{args.host}:{args.port}")
    print(f"[info] universe: {len(universe.all_symbols())} symbols")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
