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
import indicators  # noqa: E402
import universe  # noqa: E402

ALPACA_DATA = "https://data.alpaca.markets"
FEED = "iex"  # this key is not SIP-entitled; IEX is what it can actually read
CACHE_PATH = HERE / "cache.json"

BOARD_TTL = 300  # seconds
STOCK_TTL = 300
LOOKBACKS = [1, 2, 3, 4, 5]
TOP_N = 5
# Per-symbol payloads are ~200 KB each. Cap the in-memory cache so browsing every
# group cannot grow it without bound.
STOCK_CACHE_MAX = 60
# Filings change quarterly and headlines hourly; 15 minutes is plenty.
DETAIL_TTL = 900
DETAIL_CACHE_MAX = 60

_lock = threading.Lock()
_board_build_lock = threading.Lock()
_cache: dict = {"board": None, "board_ts": 0.0, "stocks": {}, "details": {}}


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


def fetch_daily_bars(symbols: list[str], start: datetime, end: datetime) -> dict[str, list[dict]]:
    """Fetch adjusted daily bars for many symbols, following pagination."""
    out: dict[str, list[dict]] = {}
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

    for lb in LOOKBACKS:
        rankings = []
        for gname, cfg in groups.items():
            members = []
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
            if missing:
                omitted.setdefault(gname, []).extend(sorted(set(missing)))
            if not members:
                continue

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

        rankings.sort(key=lambda g: g["mean_return_pct"], reverse=True)
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
        }

    latest_dates = [b[-1]["t"][:10] for b in bars_by_symbol.values() if b]
    # `omitted` accumulates once per lookback pass, so dedupe before reporting --
    # otherwise a single missing symbol is counted five times.
    omitted = {g: sorted(set(syms)) for g, syms in omitted.items()}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_session": max(latest_dates) if latest_dates else None,
        "feed": FEED,
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

        if path == "/api/health":
            self._json(
                {
                    "ok": True,
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

    load_cache()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"[info] trading desk on http://{args.host}:{args.port}")
    print(f"[info] universe: {len(universe.all_symbols())} symbols, feed={FEED}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[info] shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
