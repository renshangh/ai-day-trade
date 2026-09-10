"""Server-side tests for build_sector_scorecard / get_sector_scorecard.

Stubs fetch_daily_bars so these run with no network. Run:
python3 trading_desk/tests/test_sector_route.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import server as srv  # noqa: E402
import universe  # noqa: E402


def _bars(price: float, n: int = 70) -> list[dict]:
    return [{"t": f"2026-01-{i%28+1:02d}", "o": price, "h": price, "l": price,
              "c": price, "v": 1_000_000.0} for i in range(n)]


def _with_fake_fetch(by_symbol: dict[str, list[dict]]):
    """Context manager swapping fetch_daily_bars for a fixed lookup table."""
    original = srv.fetch_daily_bars

    def fake(symbols, start, end):
        return {s: by_symbol.get(s, []) for s in symbols}

    class _Ctx:
        def __enter__(self):
            srv.fetch_daily_bars = fake
            return fake
        def __exit__(self, *a):
            srv.fetch_daily_bars = original
    return _Ctx()


def test_unknown_group_reports_the_error_and_the_real_list():
    out = srv.build_sector_scorecard("Not A Real Group")
    assert "error" in out
    assert "AI Optical / Interconnect" in out["available_groups"]


def test_known_group_resolves_its_own_etf_as_benchmark():
    """Semiconductors carries etf=SMH in universe.py; that must win over the
    module default without the caller naming it."""
    groups = universe.all_groups()
    syms = groups["Semiconductors"]["constituents"]
    by_symbol = {s: _bars(100.0) for s in syms}
    by_symbol["SMH"] = _bars(100.0)
    with _with_fake_fetch(by_symbol):
        out = srv.build_sector_scorecard("Semiconductors")
    assert out["benchmark"] == "SMH"
    assert out["constituents_missing"] == []


def test_theme_group_without_an_etf_falls_back_to_the_module_default():
    groups = universe.all_groups()
    syms = groups["AI Power / Datacenter Buildout"]["constituents"]
    assert groups["AI Power / Datacenter Buildout"]["etf"] is None
    by_symbol = {s: _bars(100.0) for s in syms}
    by_symbol[srv.DEFAULT_SECTOR_BENCHMARK] = _bars(100.0)
    with _with_fake_fetch(by_symbol):
        out = srv.build_sector_scorecard("AI Power / Datacenter Buildout")
    assert out["benchmark"] == srv.DEFAULT_SECTOR_BENCHMARK


def test_explicit_benchmark_overrides_both_etf_and_default():
    groups = universe.all_groups()
    syms = groups["Semiconductors"]["constituents"]
    by_symbol = {s: _bars(100.0) for s in syms}
    by_symbol["QQQ"] = _bars(100.0)
    with _with_fake_fetch(by_symbol):
        out = srv.build_sector_scorecard("Semiconductors", benchmark="QQQ")
    assert out["benchmark"] == "QQQ"


def test_a_constituent_with_no_bars_is_reported_missing_not_silently_dropped():
    groups = universe.all_groups()
    syms = groups["AI Optical / Interconnect"]["constituents"]
    by_symbol = {s: _bars(100.0) for s in syms}
    dropped = syms[0]
    by_symbol[dropped] = []              # simulates "no bars returned"
    by_symbol["SPY"] = _bars(100.0)
    with _with_fake_fetch(by_symbol):
        out = srv.build_sector_scorecard("AI Optical / Interconnect")
    assert dropped in out["constituents_missing"]
    assert dropped not in out["constituents_used"]
    assert out["breadth"]["n"] == len(syms) - 1


def test_a_fetch_failure_is_reported_as_an_error_not_raised():
    def boom(symbols, start, end):
        raise RuntimeError("feed unavailable")
    original = srv.fetch_daily_bars
    srv.fetch_daily_bars = boom
    try:
        out = srv.build_sector_scorecard("AI Optical / Interconnect")
    finally:
        srv.fetch_daily_bars = original
    assert "error" in out
    assert "AI Optical / Interconnect" in out["available_groups"]


def test_get_sector_scorecard_caches_within_the_ttl():
    """Two calls within STOCK_TTL for the same (group, benchmark) must not
    re-fetch -- this is what keeps flipping the dropdown cheap."""
    groups = universe.all_groups()
    syms = groups["AI Power / Datacenter Buildout"]["constituents"]
    calls = {"n": 0}

    def counting_fetch(symbols, start, end):
        calls["n"] += 1
        return {s: _bars(100.0) for s in symbols}

    srv._cache["sector"] = {}   # isolate from any prior test/run
    original = srv.fetch_daily_bars
    srv.fetch_daily_bars = counting_fetch
    try:
        first = srv.get_sector_scorecard("AI Power / Datacenter Buildout")
        second = srv.get_sector_scorecard("AI Power / Datacenter Buildout")
    finally:
        srv.fetch_daily_bars = original
        srv._cache["sector"] = {}   # leave the shared module cache clean for later tests
    assert calls["n"] == 1, "second call within the TTL must reuse the cache"
    assert first == second


def test_get_sector_scorecard_force_bypasses_the_cache():
    calls = {"n": 0}

    def counting_fetch(symbols, start, end):
        calls["n"] += 1
        return {s: _bars(100.0) for s in symbols}

    srv._cache["sector"] = {}
    original = srv.fetch_daily_bars
    srv.fetch_daily_bars = counting_fetch
    try:
        srv.get_sector_scorecard("Semiconductors")
        srv.get_sector_scorecard("Semiconductors", force=True)
    finally:
        srv.fetch_daily_bars = original
        srv._cache["sector"] = {}
    assert calls["n"] == 2


def test_different_benchmarks_for_the_same_group_do_not_share_a_cache_entry():
    """Keying only on group name would serve QQQ's cached data back for a SPY
    request made moments later -- the cache key must include the benchmark."""
    def fake(symbols, start, end):
        return {s: _bars(100.0) for s in symbols}

    srv._cache["sector"] = {}
    original = srv.fetch_daily_bars
    srv.fetch_daily_bars = fake
    try:
        a = srv.get_sector_scorecard("Semiconductors", benchmark="SPY")
        b = srv.get_sector_scorecard("Semiconductors", benchmark="QQQ")
    finally:
        srv.fetch_daily_bars = original
        srv._cache["sector"] = {}
    assert a["benchmark"] == "SPY"
    assert b["benchmark"] == "QQQ"


def test_an_errored_build_is_not_cached():
    """A transient feed failure must not get pinned in the cache for the TTL --
    the fix is usually to retry, not to wait out STOCK_TTL."""
    def boom(symbols, start, end):
        raise RuntimeError("down")

    srv._cache["sector"] = {}
    original = srv.fetch_daily_bars
    srv.fetch_daily_bars = boom
    try:
        out = srv.get_sector_scorecard("AI Optical / Interconnect")
        assert "error" in out
        assert srv._cache["sector"] == {}
    finally:
        srv.fetch_daily_bars = original
        srv._cache["sector"] = {}


def _main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{'FAILED' if failures else 'ALL PASSED'} ({failures} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
