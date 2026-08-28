import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests


FRED_API_BASE_URL = "https://api.stlouisfed.org/fred"

logger = logging.getLogger(__name__)

# --- Cache freshness ---------------------------------------------------------
#
# A FRED request's cache key includes its ALFRED *vintage*
# (`realtime_start`/`realtime_end`, both the as-of date), which splits cached
# responses into two classes that must not share a caching policy:
#
#   * A **settled historical** vintage is immutable. What FRED reported as of
#     2024-01-15 is fixed forever, so caching it permanently is correct -- and
#     load-bearing, because backtests replay those same keys constantly. Putting
#     a TTL on these would re-fetch unchanged data on every run and hammer the
#     FRED API for nothing.
#   * The **current** vintage is not immutable. FRED publishes new observations
#     and restates existing ones through the day, so a copy cached this morning
#     can be stale by the afternoon while its cache key stays identical. That is
#     the live-trading case: a bot could act on a morning value for a whole
#     session.
#
# Only the second class gets a TTL. `max_age_seconds=None` means "cache forever"
# and is only correct for a settled vintage.
#
# This is the same defect class as the SEC client's permanent cache -- see
# docs/investigations/2026-08-28_SEC_SUBMISSIONS_CACHE_NEVER_EXPIRES.md -- though
# narrower here, because tomorrow's as-of date produces a different cache key
# and so re-fetches anyway. The staleness window is one day, not unbounded.
CURRENT_VINTAGE_CACHE_MAX_AGE_SECONDS = 60 * 60
# A vintage counts as settled once this many days have passed. Non-zero so the
# boundary is not decided by UTC-vs-local date skew or by same-day late
# revisions: today and yesterday stay refreshable, older vintages are permanent.
VINTAGE_SETTLES_AFTER_DAYS = 1


CURATED_FRED_SERIES: dict[str, dict[str, str]] = {
    "FEDFUNDS": {"category": "rates", "name": "Federal Funds Effective Rate"},
    "DGS2": {"category": "rates", "name": "2-Year Treasury Constant Maturity Rate"},
    "DGS10": {"category": "rates", "name": "10-Year Treasury Constant Maturity Rate"},
    "T10Y2Y": {"category": "rates", "name": "10-Year Treasury Minus 2-Year Treasury"},
    "CPIAUCSL": {"category": "inflation", "name": "Consumer Price Index for All Urban Consumers"},
    "PCEPI": {"category": "inflation", "name": "Personal Consumption Expenditures Price Index"},
    "UNRATE": {"category": "labor", "name": "Unemployment Rate"},
    "PAYEMS": {"category": "labor", "name": "All Employees, Total Nonfarm"},
    "GDP": {"category": "growth", "name": "Gross Domestic Product"},
    "GDPC1": {"category": "growth", "name": "Real Gross Domestic Product"},
    "M2SL": {"category": "liquidity", "name": "M2 Money Stock"},
    "WALCL": {"category": "liquidity", "name": "Federal Reserve Total Assets"},
    "BAMLH0A0HYM2": {"category": "credit", "name": "ICE BofA US High Yield Option-Adjusted Spread"},
    "VIXCLS": {"category": "risk", "name": "CBOE Volatility Index"},
}


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _as_of_datetime(value: Any) -> datetime:
    parsed = _parse_dt(value)
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)


def _date_text(value: Any | None) -> str | None:
    parsed = _parse_dt(value)
    if parsed is None:
        return None
    return parsed.date().isoformat()


def _safe_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text or text == ".":
        return None
    try:
        return float(text)
    except Exception:
        return None


class FREDMacroData:
    """FRED/ALFRED macro data client with local caching and strategy-date gating.

    Data access requires ``FRED_API_KEY`` and uses the official API with
    ``realtime_start``/``realtime_end`` so backtests can request the vintage
    observations known as of the simulated strategy datetime.
    """

    def __init__(
        self,
        strategy: Any | None = None,
        *,
        cache_dir: str | os.PathLike[str] | None = None,
        api_key: str | None = None,
        min_request_interval_seconds: float = 0.2,
    ) -> None:
        self.strategy = strategy
        self.cache_dir = Path(
            cache_dir
            or os.environ.get("LUMIBOT_FRED_CACHE_DIR")
            or Path.home() / ".lumibot" / "cache" / "fred"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        self.min_request_interval_seconds = max(float(min_request_interval_seconds), 0.0)
        self._last_request_at = 0.0

    def _strategy_as_of(self) -> datetime:
        if self.strategy is not None and hasattr(self.strategy, "get_datetime"):
            try:
                return _as_of_datetime(self.strategy.get_datetime())
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def _cache_path(self, *parts: str) -> Path:
        safe = [re.sub(r"[^A-Za-z0-9_.=-]+", "_", str(part)).strip("_") for part in parts]
        return self.cache_dir.joinpath(*safe)

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_request_interval_seconds:
            time.sleep(self.min_request_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _cache_age_seconds(self, cache_path: Path) -> float | None:
        """Age of a cached file in seconds, or None if it cannot be stat'd.

        May be **negative** when the file's mtime is in the future (clock skew, a
        restored backup, a mount whose clock runs ahead). Deliberately not
        clamped to zero: that would report such a file as brand new and pin it
        as fresh until the wall clock caught up. See `_cache_is_fresh`.
        """
        try:
            return time.time() - cache_path.stat().st_mtime
        except OSError:
            return None

    def _cache_is_fresh(self, cache_path: Path, max_age_seconds: float | None) -> bool:
        """Whether the cached copy may be served without re-fetching.

        `max_age_seconds=None` means the cached vintage is settled, so its age is
        irrelevant. Any other value expires the copy.
        """
        if not cache_path.exists():
            return False
        if max_age_seconds is None:
            return True
        age = self._cache_age_seconds(cache_path)
        if age is None:
            return False
        # A future mtime makes the age untrustworthy, so re-fetch rather than
        # trust a copy we cannot date.
        return 0.0 <= age < max_age_seconds

    def _vintage_cache_max_age(self, as_of_date: date) -> float | None:
        """TTL for a vintage: finite while it can still change, else permanent.

        Immutability is a property of *wall-clock* time having passed, not of
        strategy time -- a backtest asking for a 2024 vintage is reading settled
        history no matter what its own clock says -- so this compares against the
        real today rather than the strategy's as-of.
        """
        days_since = (datetime.now(timezone.utc).date() - as_of_date).days
        if days_since <= VINTAGE_SETTLES_AFTER_DAYS:
            return CURRENT_VINTAGE_CACHE_MAX_AGE_SECONDS
        return None

    def _describe_age(self, cache_path: Path) -> str:
        age = self._cache_age_seconds(cache_path)
        if age is None:
            return "unknown age"
        if age < 0:
            return f"mtime {abs(age) / 3600:.1f}h in the future"
        return f"{age / 3600:.1f}h old"

    def _get_json(
        self,
        url: str,
        params: dict[str, Any],
        cache_path: Path,
        *,
        max_age_seconds: float | None = None,
    ) -> dict[str, Any]:
        if self._cache_is_fresh(cache_path, max_age_seconds):
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                # An interrupted write leaves an unparseable file. Re-fetch
                # rather than hand a corrupt cache to the caller.
                logger.warning("Discarding unreadable FRED cache %s (%s); re-fetching.", cache_path, exc)
        try:
            self._rate_limit()
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - any fetch failure falls back to cache
            # An expired cache still beats no data at all: FRED being down or
            # rate-limiting must not break a run that used to work offline.
            # Warn loudly so the staleness is visible, unlike a silent
            # permanent cache.
            if cache_path.exists():
                try:
                    stale = json.loads(cache_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    raise exc
                logger.warning(
                    "FRED fetch failed for %s (%s); serving expired cached copy (%s).",
                    url, exc, self._describe_age(cache_path),
                )
                return stale
            raise
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return payload

    def list_series(self, category: str | None = None) -> dict[str, Any]:
        rows = []
        wanted_category = str(category).strip().lower() if category else None
        for series_id, metadata in CURATED_FRED_SERIES.items():
            if wanted_category and metadata["category"] != wanted_category:
                continue
            rows.append({"series_id": series_id, **metadata})
        return {
            "source": "fred",
            "series": rows,
            "categories": sorted({metadata["category"] for metadata in CURATED_FRED_SERIES.values()}),
            "notes": (
                "These are curated common macro series. Set FRED_API_KEY for official FRED/ALFRED "
                "API access and point-in-time vintage observations."
            ),
        }

    def get_series(
        self,
        series_id: str,
        *,
        start: Any | None = None,
        end: Any | None = None,
        as_of: Any | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        series = str(series_id or "").strip().upper()
        if not series:
            raise ValueError("series_id is required.")
        as_of_dt = _as_of_datetime(as_of) if as_of is not None else self._strategy_as_of()
        as_of_date = as_of_dt.date()
        start_text = _date_text(start)
        end_text = _date_text(end)
        if end_text is None or date.fromisoformat(end_text) > as_of_date:
            end_text = as_of_date.isoformat()

        if not self.api_key:
            raise ValueError(
                "FRED_API_KEY is required to fetch FRED macro data. "
                "Lumibot uses the official FRED/ALFRED API so backtests can request point-in-time vintage observations."
            )
        return self._get_series_from_api(series, start_text=start_text, end_text=end_text, as_of_date=as_of_date, limit=limit)

    def get_latest(self, series_id: str, *, as_of: Any | None = None) -> dict[str, Any]:
        payload = self.get_series(series_id, as_of=as_of)
        observations = payload.get("observations", [])
        latest = observations[-1] if observations else None
        return {**payload, "latest": latest, "observations": observations[-10:]}

    def get_snapshot(self, series_ids: list[str] | tuple[str, ...] | str, *, as_of: Any | None = None) -> dict[str, Any]:
        if isinstance(series_ids, str):
            requested = [part.strip() for part in series_ids.split(",") if part.strip()]
        else:
            requested = [str(part).strip() for part in series_ids if str(part).strip()]
        values = {}
        errors = {}
        for series_id in requested:
            try:
                values[series_id.upper()] = self.get_latest(series_id, as_of=as_of)["latest"]
            except Exception as exc:
                errors[series_id.upper()] = str(exc)
        as_of_dt = _as_of_datetime(as_of) if as_of is not None else self._strategy_as_of()
        return {"source": "fred", "as_of": as_of_dt.isoformat(), "values": values, "errors": errors}

    def _get_series_from_api(
        self,
        series_id: str,
        *,
        start_text: str | None,
        end_text: str,
        as_of_date: date,
        limit: int | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_end": end_text,
            "realtime_start": as_of_date.isoformat(),
            "realtime_end": as_of_date.isoformat(),
        }
        if start_text:
            params["observation_start"] = start_text
        cache_key = json.dumps({k: v for k, v in params.items() if k != "api_key"}, sort_keys=True)
        payload = self._get_json(
            f"{FRED_API_BASE_URL}/series/observations",
            params,
            self._cache_path("api", series_id, f"{hashlib.sha256(cache_key.encode()).hexdigest()}.json"),
            max_age_seconds=self._vintage_cache_max_age(as_of_date),
        )
        observations = self._normalize_api_observations(payload.get("observations", []), as_of_date)
        if limit is not None:
            observations = observations[-max(int(limit), 1):]
        return {
            "source": "fred_api",
            "series_id": series_id,
            "as_of": as_of_date.isoformat(),
            "point_in_time_safe": True,
            "uses_revised_data": False,
            "observations": observations,
        }

    def _normalize_api_observations(self, rows: list[dict[str, Any]], as_of_date: date) -> list[dict[str, Any]]:
        observations = []
        for row in rows:
            obs_date_text = row.get("date")
            obs_dt = _parse_dt(obs_date_text)
            if obs_dt is None or obs_dt.date() > as_of_date:
                continue
            observations.append(
                {
                    "date": obs_dt.date().isoformat(),
                    "value": _safe_float(row.get("value")),
                    "realtime_start": row.get("realtime_start"),
                    "realtime_end": row.get("realtime_end"),
                }
            )
        observations.sort(key=lambda row: row["date"])
        return observations
