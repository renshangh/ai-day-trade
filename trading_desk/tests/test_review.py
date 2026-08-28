"""Tests for the daily position review.

Run: python3 trading_desk/tests/test_review.py

Everything here is offline: `_review_one` is fed a stubbed `get_stock`, so no
test touches Alpaca. The point is the arithmetic and the flag rules, which are
what a reader of the review will actually trust.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server as srv  # noqa: E402


# ----------------------------------------------------------------- fixtures
def bars(closes: list[float]) -> list[dict]:
    """Daily bars with a plausible intraday range around each close."""
    return [
        {"t": f"2026-0{1 + i // 28}-{1 + i % 28:02d}", "o": c, "h": c * 1.01,
         "l": c * 0.99, "c": c, "v": 1_000_000.0}
        for i, c in enumerate(closes)
    ]


def stub_stock(closes: list[float], levels: list[dict], *, stale: bool = False) -> dict:
    b = bars(closes)
    return {"symbol": "TEST", "bars": b, "levels": levels, "stale": stale,
            "indicators": {
                "atr14": [None] * (len(b) - 1) + [10.0],
                "rsi14": [None] * (len(b) - 1) + [45.0],
                "sma20": [None] * (len(b) - 1) + [110.0],
                "sma50": [None] * (len(b) - 1) + [120.0],
                "sma200": [None] * (len(b) - 1) + [130.0],
            }}


def review_one(stock: dict, held: dict, lots: list[dict] | None = None) -> dict:
    """Call `_review_one` with `get_stock` stubbed out."""
    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stock
    try:
        return srv._review_one("TEST", held, lots or [], {})
    finally:
        srv.get_stock = original


HELD = {"qty": 10.0, "cost": 1000.0, "avg_entry": 100.0, "lots": 1, "entry_date": "2026-01-01"}


# -------------------------------------------------------------------- tests
def test_pnl_and_market_value_use_the_latest_close():
    e = review_one(stub_stock([90.0, 95.0], []), HELD)
    assert e["last"] == 95.0
    assert e["market_value"] == 950.0
    # (95 - 100) * 10
    assert abs(e["pnl"] - (-50.0)) < 1e-9
    assert abs(e["pnl_pct"] - (-5.0)) < 1e-9
    # 95 / 90 - 1
    assert abs(e["day_pct"] - 5.5555555) < 1e-4


def test_nearest_levels_are_the_closest_on_each_side_not_the_most_tested():
    """Ranking by touch count would surface a far-away wall over the live level."""
    levels = [
        {"level": 80.0, "touches": 9, "tests": 99, "last_touch": "2025-01-01"},
        {"level": 94.0, "touches": 2, "tests": 3, "last_touch": "2026-07-01"},
        {"level": 96.0, "touches": 2, "tests": 4, "last_touch": "2026-07-02"},
        {"level": 130.0, "touches": 8, "tests": 88, "last_touch": "2025-02-01"},
    ]
    e = review_one(stub_stock([90.0, 95.0], levels), HELD)
    assert e["nearest_support"]["level"] == 94.0
    assert e["nearest_resistance"]["level"] == 96.0


def test_level_distance_is_reported_in_atr_as_well_as_percent():
    """Percent alone is not comparable across names whose ATRs differ 3x."""
    e = review_one(stub_stock([90.0, 95.0], [{"level": 90.0, "touches": 2, "tests": 5}]), HELD)
    sup = e["nearest_support"]
    assert abs(sup["distance_pct"] - (-5.2631578)) < 1e-4
    # |95 - 90| / atr 10.0
    assert abs(sup["distance_atr"] - 0.5) < 1e-9


def test_risk_to_support_is_measured_from_price_not_from_entry():
    """An underwater position has already spent the difference; risk is what is left."""
    e = review_one(stub_stock([90.0, 95.0], [{"level": 90.0, "touches": 2, "tests": 5}]), HELD)
    assert abs(e["risk_to_support"] - 50.0) < 1e-9   # (95 - 90) * 10, NOT from 100
    assert e["avg_entry"] == 100.0                   # entry still reported alongside


def test_no_support_below_price_reports_absence_rather_than_a_guess():
    e = review_one(stub_stock([90.0, 95.0], [{"level": 200.0, "touches": 2, "tests": 5}]), HELD)
    assert e["nearest_support"] is None
    assert "risk_to_support" not in e
    keys = {f["key"] for f in srv._review_flags(e, None)}
    assert "no_support" in keys


def test_journal_gaps_are_counted_per_lot():
    lots = [
        {"symbol": "TEST", "stop": "", "thesis": "", "setup": "momentum"},
        {"symbol": "TEST", "stop": "88", "thesis": "real reason", "setup": ""},
        {"symbol": "TEST", "stop": "   ", "thesis": "x", "setup": "reversal"},
    ]
    e = review_one(stub_stock([90.0, 95.0], []), {**HELD, "lots": 3}, lots)
    assert e["lots_without_stop"] == 2      # "" and whitespace-only both count
    assert e["lots_without_thesis"] == 1
    assert e["lots_without_setup"] == 1


def test_journal_gaps_survive_a_market_data_failure():
    """Record hygiene is knowable even when the fetch dies, so it is filled first."""
    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: (_ for _ in ()).throw(RuntimeError("feed down"))
    try:
        e = srv._review_one("TEST", HELD, [{"symbol": "TEST", "stop": ""}], {})
    finally:
        srv.get_stock = original
    assert e["error"] == "feed down"
    assert e["lots_without_stop"] == 1
    # A dead symbol yields exactly one flag and never a level/risk claim.
    flags = srv._review_flags(e, None)
    assert [f["key"] for f in flags] == ["no_data"]


def test_at_support_flag_fires_only_inside_the_proximity_band():
    near = review_one(stub_stock([90.0, 95.0], [{"level": 90.0, "touches": 2, "tests": 5}]), HELD)
    far = review_one(stub_stock([90.0, 95.0], [{"level": 60.0, "touches": 2, "tests": 5}]), HELD)
    assert "at_support" in {f["key"] for f in srv._review_flags(near, None)}      # 0.5 ATR
    assert "at_support" not in {f["key"] for f in srv._review_flags(far, None)}   # 3.5 ATR


def test_below_all_averages_is_one_flag_not_three():
    e = review_one(stub_stock([90.0, 95.0], []), HELD)   # 95 < sma20 110 < 50 < 200
    keys = [f["key"] for f in srv._review_flags(e, None)]
    assert "below_all_ma" in keys
    assert "below_ma" not in keys


def test_earnings_flag_respects_the_swing_window():
    e = review_one(stub_stock([90.0, 95.0], []), HELD)
    inside = srv._review_flags(e, {"days_until": srv.SWING_WINDOW_DAYS, "projected_date": "2026-09-10"})
    outside = srv._review_flags(e, {"days_until": srv.SWING_WINDOW_DAYS + 1, "projected_date": "2026-09-11"})
    assert "earnings_soon" in {f["key"] for f in inside}
    assert "earnings_soon" not in {f["key"] for f in outside}


def test_flags_never_tell_the_reader_what_to_do():
    """The review reports measurements. Imperatives would imply an edge it lacks."""
    e = review_one(stub_stock([90.0, 95.0], [{"level": 90.0, "touches": 2, "tests": 5}]), HELD)
    banned = ("buy", "sell", "should", "recommend", "exit now", "take profit", "cut ")
    for f in srv._review_flags(e, {"days_until": 3, "projected_date": "2026-09-01"}):
        low = f["text"].lower()
        for word in banned:
            assert word not in low, f"flag {f['key']!r} reads as advice: {f['text']!r}"


def test_excluded_symbols_are_reported_but_carry_no_risk_math():
    # The exclusion list is the documented contract, and every entry must carry
    # a reason -- an unexplained exclusion is indistinguishable from a bug.
    for sym in ("IBIT", "SNDL"):
        assert sym in srv.REVIEW_EXCLUDE, f"{sym} should be excluded"
        assert (srv.REVIEW_EXCLUDE[sym] or "").strip(), f"{sym} excluded without a reason"
    e = review_one(stub_stock([90.0, 95.0], [{"level": 90.0}]), HELD)
    assert e["excluded"] is False
    original = srv.REVIEW_EXCLUDE
    srv.REVIEW_EXCLUDE = {"TEST": "because"}
    try:
        e2 = review_one(stub_stock([90.0, 95.0], [{"level": 90.0}]), HELD)
    finally:
        srv.REVIEW_EXCLUDE = original
    assert e2["excluded"] is True
    assert e2["exclusion_reason"] == "because"


def test_missing_journal_is_reported_as_absence_not_an_empty_review():
    """An empty table would read as "no positions", which is a different claim."""
    original = srv.JOURNAL_PATH
    srv.JOURNAL_PATH = Path("/nonexistent/does-not-exist.csv")
    try:
        out = srv.build_position_review()
    finally:
        srv.JOURNAL_PATH = original
    assert out["positions"] == []
    assert "error" in out and "does-not-exist.csv" in out["error"]


def test_stale_quote_is_surfaced():
    e = review_one(stub_stock([90.0, 95.0], [], stale=True), HELD)
    assert "stale_quote" in {f["key"] for f in srv._review_flags(e, None)}


def test_swing_window_matches_the_client_constant():
    """app.js cannot import this, so the two are asserted to agree."""
    js = (Path(__file__).resolve().parent.parent / "app.js").read_text()
    assert f"const SWING_WINDOW_DAYS = {srv.SWING_WINDOW_DAYS};" in js


def test_generated_at_is_utc_and_parseable():
    original = srv.JOURNAL_PATH
    srv.JOURNAL_PATH = Path("/nonexistent/does-not-exist.csv")
    try:
        out = srv.build_position_review()
    finally:
        srv.JOURNAL_PATH = original
    stamp = datetime.fromisoformat(out["generated_at"])
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timezone.utc.utcoffset(None)


def test_lot_counts_are_reported_at_both_scopes():
    """The table shows reviewed rows only, so a journal-wide tile beside it would
    read as a contradiction -- but the journal-wide count is the one the README's
    "trades with no stop should trend to zero" rule is about. Both are returned.
    """
    import csv as _csv
    import tempfile
    rows = [
        # symbol, status, qty, entry_price, stop
        ("POWL", "open", "45", "216.32", ""),
        ("SNDL", "open", "50", "15.12", ""),      # excluded holding, no stop
        ("AXTI", "open", "100", "67.50", "60"),   # reviewed, has a stop
    ]
    header = ["trade_id", "status", "setup", "group", "symbol", "side", "qty",
              "entry_date", "entry_price", "stop", "thesis"]
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for i, (sym, status, qty, px, stop) in enumerate(rows, 1):
            w.writerow({"trade_id": str(i), "status": status, "symbol": sym, "side": "long",
                        "qty": qty, "entry_date": "2026-01-01", "entry_price": px,
                        "stop": stop, "setup": "", "group": "", "thesis": ""})
        path = Path(fh.name)

    original_journal, original_stock = srv.JOURNAL_PATH, srv.get_stock
    srv.JOURNAL_PATH = path
    srv.get_stock = lambda sym, force=False: stub_stock([90.0, 95.0], [{"level": 90.0}])
    try:
        out = srv.build_position_review()
    finally:
        srv.JOURNAL_PATH, srv.get_stock = original_journal, original_stock
        path.unlink(missing_ok=True)

    reviewed = {e["symbol"] for e in out["positions"]}
    assert "SNDL" not in reviewed, "SNDL is excluded and must not be reviewed"
    assert {e["symbol"] for e in out["excluded"]} == {"SNDL"}
    # Journal-wide: 3 lots, 2 without a stop (POWL, SNDL).
    assert out["open_lots"] == 3
    assert out["lots_without_stop"] == 2
    # Reviewed-only: 2 lots, 1 without a stop (POWL). SNDL's gap is not counted here.
    assert out["reviewed_open_lots"] == 2
    assert out["reviewed_lots_without_stop"] == 1


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
        except Exception as e:  # noqa: BLE001 - surface any error as a failure
            failures += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{'FAILED' if failures else 'ALL PASSED'} ({failures} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
