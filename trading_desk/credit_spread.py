"""Daily U.S. high-yield option-adjusted spread for the Trading Desk."""

import csv
import threading
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from http.client import HTTPException
from urllib.request import urlopen
from zoneinfo import ZoneInfo

SERIES = "BAMLH0A0HYM2"
CSV_URL = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={SERIES}"
CACHE_SECONDS = 900
MAX_CSV_BYTES = 128_000
ET = ZoneInfo("America/New_York")
_lock = threading.Lock()
_cache = None


def summarize(csv_text: str, today: date) -> dict:
    rows = csv.DictReader(csv_text.splitlines())
    if rows.fieldnames != ["observation_date", SERIES]:
        raise ValueError("Unexpected FRED credit spread columns")

    observations = {}
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Incomplete or extra FRED credit spread columns")
        raw = row[SERIES]
        if raw in ("", "."):
            continue
        observed = date.fromisoformat(row["observation_date"])
        try:
            value = Decimal(raw)
        except InvalidOperation as exc:
            raise ValueError("Invalid FRED credit spread value") from exc
        if not value.is_finite() or observed in observations:
            raise ValueError("Invalid or duplicate FRED credit spread observation")
        if observed <= today:
            observations[observed] = value
    if not observations:
        raise ValueError("FRED returned no credit spread observations")

    latest = max(observations)
    spread = observations[latest]
    # Include the last published close before the seven-day mark for holidays.
    cutoff = latest - timedelta(days=7)
    baseline = max(
        (day for day in observations if cutoff - timedelta(days=3) <= day <= cutoff),
        default=None,
    )
    change = (spread - observations[baseline]) * 100 if baseline else None
    if spread > 6:
        alert = "above_six"
    elif change is not None and spread >= Decimal("4.50") and change >= 50:
        alert = "rapid_widening"
    else:
        alert = "none" if change is not None else "unavailable"
    return {
        "date": latest.isoformat(),
        "spread_pct": float(spread),
        "weekly_base_date": baseline.isoformat() if baseline else None,
        "weekly_change_bp": float(change) if change is not None else None,
        "alert": alert,
        "stale": (today - latest).days > 4,
    }


def get(*, force: bool = False) -> dict:
    global _cache
    with _lock:
        today = datetime.now(ET).date()
        if _cache and not force and _cache[0] == today and time.monotonic() - _cache[1] < CACHE_SECONDS:
            return _cache[2]
        _cache = None
        try:
            with urlopen(CSV_URL, timeout=8) as response:
                content = response.read(MAX_CSV_BYTES + 1)
        except HTTPException as exc:
            raise OSError("Could not read FRED credit spread response") from exc
        if len(content) > MAX_CSV_BYTES:
            raise ValueError("FRED credit spread response is too large")
        today = datetime.now(ET).date()
        result = summarize(content.decode("utf-8-sig"), today)
        _cache = (today, time.monotonic(), result)
        return result
