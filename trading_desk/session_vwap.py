"""Today's regular-session VWAP, using only completed consolidated minute bars."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import math
import threading
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
DELAY_MINUTES = 17
TTL = 120
EXCLUDED = {"SNDL"}
_lock = threading.Lock()
_cached = None


def summarize(bars, start, cutoff):
    """Weight vendor VWAPs by volume; never approximate from OHLC or fill gaps."""
    selected = []
    seen = set()
    for bar in bars:
        stamp = datetime.fromisoformat(bar["t"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Missing bar timezone")
        if not start <= stamp < cutoff:
            continue
        if stamp in seen:
            raise ValueError("Duplicate minute bars")
        seen.add(stamp)
        volume, vwap, close = (float(bar[k]) for k in ("v", "vw", "c"))
        if not all(math.isfinite(x) for x in (volume, vwap, close)):
            raise ValueError("Invalid bar values")
        if volume <= 0 or vwap <= 0 or close <= 0:
            raise ValueError("Nonpositive bar values")
        selected.append((stamp, volume, vwap, close))
    if not selected:
        return {"error": "No regular-session trades available for this window."}
    selected.sort()
    volume = sum(b[1] for b in selected)
    vwap = sum(b[1] * b[2] for b in selected) / volume
    last = selected[-1][3]
    return {"vwap": vwap, "last": last, "difference_pct": (last / vwap - 1) * 100,
            "volume": volume, "last_bar_at": selected[-1][0].isoformat(),
            "bar_count": len(selected)}


def build(symbols, request, now=None):
    now = (now or datetime.now(EASTERN)).astimezone(EASTERN)
    session = now.date().isoformat()
    symbols = sorted(set(symbols) - EXCLUDED)
    result = {"session_date": session, "built_at": now.isoformat(), "feed": "sip",
              "delay_minutes": DELAY_MINUTES, "rows": [], "excluded": sorted(EXCLUDED)}
    if not symbols:
        return dict(result, message="No open holdings to display.")
    # Broker calendar supplies holidays and early closes; fixed 16:00 windows
    # would incorrectly include after-hours trades on half days.
    try:
        calendar = request("https://paper-api.alpaca.markets/v2/calendar?" +
                           urlencode({"start": session, "end": session}))
        if not isinstance(calendar, list):
            raise ValueError("Invalid calendar response")
        if not calendar:
            return dict(result, message="Market closed today; no session VWAP.")
        if len(calendar) != 1 or calendar[0]["date"] != session:
            raise ValueError("Calendar date mismatch")
        start = datetime.fromisoformat(session + "T" + calendar[0]["open"]).replace(tzinfo=EASTERN)
        close = datetime.fromisoformat(session + "T" + calendar[0]["close"]).replace(tzinfo=EASTERN)
        if close <= start:
            raise ValueError("Invalid calendar hours")
    except Exception:
        return dict(result, error="Session calendar unavailable; VWAP cannot be verified.")
    cutoff = min(close, (now - timedelta(minutes=DELAY_MINUTES)).replace(second=0, microsecond=0))
    result.update(session_open=start.isoformat(), session_close=close.isoformat())
    if cutoff <= start:
        return dict(result, message="Waiting for today's first completed, delayed session bars.")
    result["cutoff_at"] = cutoff.isoformat()

    def fetch_symbol(symbol):
        params = {"symbols": symbol, "timeframe": "1Min", "start": start.isoformat(),
                  "end": (cutoff - timedelta(microseconds=1)).isoformat(),
                  "feed": "sip", "adjustment": "raw", "sort": "asc", "limit": 10000}
        bars, tokens = [], set()
        try:
            for _ in range(6):
                payload = request("https://data.alpaca.markets/v2/stocks/bars?" + urlencode(params))
                if not isinstance(payload.get("bars"), dict):
                    raise ValueError("Invalid bars response")
                bars.extend(payload["bars"].get(symbol, []))
                token = payload.get("next_page_token")
                if not token:
                    return dict(summarize(bars, start, cutoff), symbol=symbol)
                if token in tokens:
                    raise ValueError("Repeated page token")
                tokens.add(token)
                params["page_token"] = token
            raise ValueError("Incomplete pagination")
        except Exception:
            # A partial fetch must never look like a complete session VWAP.
            return {"symbol": symbol, "error": "Consolidated session data unavailable or incomplete."}

    with ThreadPoolExecutor(max_workers=3) as pool:
        result["rows"] = list(pool.map(fetch_symbol, symbols))
    return result


def get(symbols, request, force=False, now=None):
    """Small memory-only cache keyed by session and current journal membership."""
    global _cached
    now = (now or datetime.now(EASTERN)).astimezone(EASTERN)
    key = (now.date(), tuple(sorted(set(symbols) - EXCLUDED)))
    with _lock:
        if not force and _cached and _cached[0] == key and time.monotonic() - _cached[1] < TTL:
            return _cached[2]
        result = build(symbols, request, now)
        _cached = (key, time.monotonic(), result)
        return result
