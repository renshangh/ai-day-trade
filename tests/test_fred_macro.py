import os
import time
from datetime import datetime, timezone

import pytest
import requests

import lumibot.macro.fred as fred_module
from lumibot.macro import FREDMacroData


class _Response:
    def __init__(self, *, payload=None, text=""):
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Strategy:
    def get_datetime(self):
        return datetime(2025, 1, 15, tzinfo=timezone.utc)


def test_fred_data_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    fred = FREDMacroData(_Strategy(), cache_dir=tmp_path, min_request_interval_seconds=0)

    try:
        fred.get_series("DGS10")
    except ValueError as exc:
        assert "FRED_API_KEY is required" in str(exc)
    else:
        raise AssertionError("FRED macro data should require FRED_API_KEY")

    catalog = fred.list_series(category="rates")
    assert any(row["series_id"] == "DGS10" for row in catalog["series"])


def test_fred_api_mode_uses_vintage_params_and_filters_future_observations(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return _Response(
            payload={
                "observations": [
                    {"date": "2024-12-01", "value": "4.1", "realtime_start": "2025-01-15", "realtime_end": "2025-01-15"},
                    {"date": "2025-01-15", "value": "4.3", "realtime_start": "2025-01-15", "realtime_end": "2025-01-15"},
                    {"date": "2025-01-16", "value": "4.4", "realtime_start": "2025-01-15", "realtime_end": "2025-01-15"},
                ]
            }
        )

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setattr("lumibot.macro.fred.requests.get", fake_get)
    fred = FREDMacroData(_Strategy(), cache_dir=tmp_path, min_request_interval_seconds=0)

    result = fred.get_series("DGS10", start="2024-01-01")
    assert result["source"] == "fred_api"
    assert result["point_in_time_safe"] is True
    assert result["uses_revised_data"] is False
    assert [row["date"] for row in result["observations"]] == ["2024-12-01", "2025-01-15"]

    params = calls[0][1]["params"]
    assert params["api_key"] == "test-key"
    assert params["realtime_start"] == "2025-01-15"
    assert params["realtime_end"] == "2025-01-15"
    assert params["observation_end"] == "2025-01-15"


def test_fred_snapshot_reports_per_series_errors(monkeypatch, tmp_path):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    fred = FREDMacroData(_Strategy(), cache_dir=tmp_path, min_request_interval_seconds=0)

    result = fred.get_snapshot(["NOT_A_CURATED_SERIES"])
    assert result["values"] == {}
    assert "NOT_A_CURATED_SERIES" in result["errors"]


# --- Cache expiry ------------------------------------------------------------
#
# `_get_json` cached every FRED response permanently. A request's cache key
# includes its ALFRED vintage, which makes that correct for settled history but
# wrong for the current vintage: FRED publishes and restates through the day, so
# a live bot could act on a morning value for a whole session. Same defect class
# as the SEC client -- see
# docs/investigations/2026-08-28_SEC_SUBMISSIONS_CACHE_NEVER_EXPIRES.md.


class _LiveStrategy:
    """Strategy clock on the current vintage, captured once.

    `now` is sampled in __init__ rather than per call on purpose: two
    `get_datetime()` calls straddling UTC midnight would yield different as-of
    dates, hence different cache keys, and the cache-hit assertions below would
    fail intermittently once a day.
    """

    def __init__(self):
        self.now = datetime.now(timezone.utc)

    def get_datetime(self):
        return self.now


def _observation(value, as_of_date):
    """One observation stamped with the caller's as-of date.

    Must use the strategy's date, not a freshly read `today`: the client filters
    to `observation_date <= as_of`, so a mismatched date silently yields zero
    observations.
    """
    stamp = as_of_date.isoformat()
    return {"observations": [{"date": stamp, "value": value,
                              "realtime_start": stamp, "realtime_end": stamp}]}


def _backdate(path, seconds):
    """Age a cached file so TTL logic sees it as stale."""
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def _only_cache_file(tmp_path):
    """The single cache file, asserting there is exactly one.

    `rglob` order is unspecified, so picking the first match would silently
    backdate an arbitrary file once a test fetches more than one series.
    """
    files = sorted(p for p in tmp_path.rglob("*.json") if p.is_file())
    assert len(files) == 1, f"expected exactly one cache file, found {files}"
    return files[0]


def _fred_with_versioned_series(monkeypatch, tmp_path, state, strategy):
    def fake_get(url, **kwargs):
        state["calls"] += 1
        return _Response(payload=_observation(state["value"], strategy.get_datetime().date()))

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setattr("lumibot.macro.fred.requests.get", fake_get)
    return FREDMacroData(strategy, cache_dir=tmp_path, min_request_interval_seconds=0)


def test_current_vintage_cache_is_served_within_ttl(monkeypatch, tmp_path):
    state = {"value": "4.1", "calls": 0}
    fred = _fred_with_versioned_series(monkeypatch, tmp_path, state, _LiveStrategy())

    fred.get_series("DGS10")
    fred.get_series("DGS10")

    assert state["calls"] == 1


def test_current_vintage_cache_expires_and_sees_revisions(monkeypatch, tmp_path):
    state = {"value": "4.1", "calls": 0}
    fred = _fred_with_versioned_series(monkeypatch, tmp_path, state, _LiveStrategy())

    first = fred.get_series("DGS10")
    assert first["observations"][-1]["value"] == 4.1

    # FRED restates the series later the same day; the cache key is unchanged.
    state["value"] = "4.5"
    # Backdated by a hardcoded 25h rather than by the TTL constant, so this test
    # fails *behaviorally* against the pre-fix implementation (wrong value
    # returned) instead of erroring on a missing attribute. The invariant this
    # relies on is asserted by test_current_vintage_ttl_is_intraday below.
    _backdate(_only_cache_file(tmp_path), 25 * 60 * 60)

    second = fred.get_series("DGS10")

    assert state["calls"] == 2
    # This is the assertion that would have caught the original bug.
    assert second["observations"][-1]["value"] == 4.5


def test_settled_historical_vintage_is_cached_permanently(monkeypatch, tmp_path):
    """A past ALFRED vintage is immutable, so age must never force a re-fetch.

    This is what keeps backtests from re-downloading unchanged history on every
    run, so it matters as much as the expiry above.
    """
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _Response(
            payload={
                "observations": [
                    {"date": "2024-12-01", "value": "4.1",
                     "realtime_start": "2025-01-15", "realtime_end": "2025-01-15"}
                ]
            }
        )

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setattr("lumibot.macro.fred.requests.get", fake_get)
    # _Strategy is pinned to 2025-01-15, comfortably in the settled past.
    fred = FREDMacroData(_Strategy(), cache_dir=tmp_path, min_request_interval_seconds=0)

    fred.get_series("DGS10", start="2024-01-01")
    _backdate(_only_cache_file(tmp_path), 365 * 24 * 60 * 60)
    fred.get_series("DGS10", start="2024-01-01")

    assert len(calls) == 1


def test_expired_current_vintage_falls_back_when_fred_unreachable(monkeypatch, tmp_path):
    state = {"value": "4.1", "calls": 0}
    fred = _fred_with_versioned_series(monkeypatch, tmp_path, state, _LiveStrategy())
    fred.get_series("DGS10")

    _backdate(_only_cache_file(tmp_path), fred_module.CURRENT_VINTAGE_CACHE_MAX_AGE_SECONDS + 60)

    def failing_get(url, **kwargs):
        raise requests.ConnectionError("FRED unreachable")

    monkeypatch.setattr("lumibot.macro.fred.requests.get", failing_get)

    # Stale beats nothing: an outage must not break a run that worked offline.
    result = fred.get_series("DGS10")
    assert result["observations"][-1]["value"] == 4.1


def test_missing_cache_still_raises_when_fred_unreachable(monkeypatch, tmp_path):
    def failing_get(url, **kwargs):
        raise requests.ConnectionError("FRED unreachable")

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setattr("lumibot.macro.fred.requests.get", failing_get)
    fred = FREDMacroData(_LiveStrategy(), cache_dir=tmp_path, min_request_interval_seconds=0)

    with pytest.raises(requests.ConnectionError):
        fred.get_series("DGS10")


def test_corrupt_json_cache_is_discarded_and_refetched(monkeypatch, tmp_path):
    state = {"value": "4.1", "calls": 0}
    fred = _fred_with_versioned_series(monkeypatch, tmp_path, state, _LiveStrategy())
    fred.get_series("DGS10")

    # Simulate an interrupted write leaving a truncated file.
    _only_cache_file(tmp_path).write_text('{"observations": [', encoding="utf-8")

    result = fred.get_series("DGS10")

    assert state["calls"] == 2
    assert result["observations"][-1]["value"] == 4.1


def test_current_vintage_ttl_is_intraday():
    """The current vintage must refresh within a trading day.

    FRED publishes and restates intraday, so a TTL at or beyond 24h would let a
    live bot hold a stale value for a full session. Also the invariant that lets
    test_current_vintage_cache_expires_and_sees_revisions hardcode its backdate.
    """
    assert 0 < fred_module.CURRENT_VINTAGE_CACHE_MAX_AGE_SECONDS < 24 * 60 * 60


def test_future_mtime_cache_is_treated_as_stale(monkeypatch, tmp_path):
    """A cache file dated in the future must not read as brand new.

    Clock skew, a restored backup, or a mount running ahead makes the computed
    age negative. Clamping that to zero would pin the copy as fresh until the
    wall clock caught up, silently reinstating the permanent-cache bug.
    """
    state = {"value": "4.1", "calls": 0}
    fred = _fred_with_versioned_series(monkeypatch, tmp_path, state, _LiveStrategy())
    fred.get_series("DGS10")

    state["value"] = "4.5"
    _backdate(_only_cache_file(tmp_path), -6 * 60 * 60)  # mtime 6h in the future

    result = fred.get_series("DGS10")

    assert state["calls"] == 2
    assert result["observations"][-1]["value"] == 4.5
