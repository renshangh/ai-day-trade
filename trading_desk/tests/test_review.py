"""Tests for the daily position review.

Run: python3 trading_desk/tests/test_review.py

Everything here is offline: `_review_one` is fed a stubbed `get_stock`, so no
test touches Alpaca. The point is the arithmetic and the flag rules, which are
what a reader of the review will actually trust.
"""

from __future__ import annotations

import csv
import sys
import tempfile
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


def _one_lot_journal() -> Path:
    """A throwaway journal with a single open POWL lot."""
    header = ["trade_id", "status", "setup", "group", "symbol", "side", "qty",
              "entry_date", "entry_price", "stop", "thesis"]
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerow({"trade_id": "1", "status": "open", "symbol": "POWL", "side": "long",
                    "qty": "45", "entry_date": "2026-08-03", "entry_price": "216.32",
                    "stop": "", "setup": "", "group": "", "thesis": ""})
        return Path(fh.name)


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
    rows = [
        # symbol, status, qty, entry_price, stop
        ("POWL", "open", "45", "216.32", ""),
        ("SNDL", "open", "50", "15.12", ""),      # excluded holding, no stop
        ("AXTI", "open", "100", "67.50", "60"),   # reviewed, has a stop
    ]
    header = ["trade_id", "status", "setup", "group", "symbol", "side", "qty",
              "entry_date", "entry_price", "stop", "thesis"]
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
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


def test_force_reaches_get_stock_so_refresh_actually_refreshes():
    """A forced review must re-fetch bars, not rebuild over the stock cache.

    Regression: `force` stopped at `get_position_review` and never reached
    `get_stock`, so Refresh stamped a fresh "built at" time on prices up to
    STOCK_TTL old -- the page overstated its own freshness.
    """
    seen: list[bool] = []

    def fake_get_stock(sym, force=False):
        seen.append(force)
        return stub_stock([90.0, 95.0], [{"level": 90.0}])

    original_journal, original_stock = srv.JOURNAL_PATH, srv.get_stock
    path = _one_lot_journal()
    srv.JOURNAL_PATH, srv.get_stock = path, fake_get_stock
    try:
        srv.build_position_review(force=True)
        assert seen == [True], f"force did not reach get_stock: {seen}"
        seen.clear()
        srv.build_position_review()
        assert seen == [False], f"default should not force a re-fetch: {seen}"
    finally:
        srv.JOURNAL_PATH, srv.get_stock = original_journal, original_stock
        path.unlink(missing_ok=True)


def test_review_ttl_never_outpaces_bar_freshness():
    """Rebuilding faster than bars can change would misrepresent the timestamp."""
    assert srv.REVIEW_TTL >= srv.STOCK_TTL, (
        "a review rebuilt more often than STOCK_TTL stamps a fresh build time on "
        "stale prices")


def test_totals_treat_zero_as_a_value_not_as_missing():
    """`if (mv and cost)` blanked a legitimate zero; presence is the right test."""
    def fail_stock(sym, force=False):
        raise RuntimeError("feed down")

    original_journal, original_stock = srv.JOURNAL_PATH, srv.get_stock
    path = _one_lot_journal()
    srv.JOURNAL_PATH, srv.get_stock = path, fail_stock
    try:
        out = srv.build_position_review()
    finally:
        srv.JOURNAL_PATH, srv.get_stock = original_journal, original_stock
        path.unlink(missing_ok=True)
    # Every position errored, so market value is 0 but cost is still known --
    # the totals must be computable rather than showing "$0" beside a dash.
    assert out["totals"]["cost"] > 0
    assert out["totals"]["pnl"] is not None
    assert out["totals"]["pnl_pct"] is not None


def test_partial_moving_average_flag_is_pluralised():
    e = review_one(stub_stock([90.0, 95.0], []), HELD)
    e["vs_sma200_pct"] = 4.0          # above the 200 only, so two remain below
    texts = [f["text"] for f in srv._review_flags(e, None)]
    assert any(t == "Below the 20, 50-day averages" for t in texts), texts
    e["vs_sma50_pct"] = 4.0           # now only one below
    texts = [f["text"] for f in srv._review_flags(e, None)]
    assert any(t == "Below the 20-day average" for t in texts), texts


def test_open_positions_can_aggregate_rows_without_touching_the_file():
    """The review needs the aggregate and the lots from ONE read.

    Regression: `build_position_review` called `open_positions()` (which opened
    the CSV) and `journal_open_rows()` (which opened it again). If the file
    changed between them the two disagreed, surfacing as flag text like
    "No stop recorded on 3 of 2 open lot(s)". `open_positions` now accepts
    already-read rows, proven here by pointing JOURNAL_PATH at a path that does
    not exist -- if it still touched the filesystem, the result would be empty.
    """
    rows = [
        {"status": "open", "symbol": "FN", "qty": "11", "entry_price": "426.50",
         "entry_date": "2026-08-25", "stop": ""},
        {"status": "open", "symbol": "FN", "qty": "11", "entry_price": "437.00",
         "entry_date": "2026-08-27", "stop": ""},
    ]
    original = srv.JOURNAL_PATH
    srv.JOURNAL_PATH = Path("/nonexistent/never-opened.csv")
    try:
        held = srv.open_positions(rows)
    finally:
        srv.JOURNAL_PATH = original

    assert set(held) == {"FN"}
    assert held["FN"]["lots"] == 2
    assert held["FN"]["qty"] == 22.0
    assert abs(held["FN"]["cost"] - (11 * 426.50 + 11 * 437.00)) < 1e-9
    assert held["FN"]["entry_date"] == "2026-08-25"   # earliest across the lots


def test_managed_stop_is_reported_separately_from_the_entry_stop():
    """`stop_current` must not silence the entry-stop flag.

    trading_records/README.md keys "trades with no stop" on the stop set **at
    entry**, because that is what r_multiple divides by. A stop decided today is
    a real risk decision but a different fact, so both are reported.
    """
    lots = [{"symbol": "FN", "status": "open", "qty": "11", "entry_price": "488.00",
             "stop": "", "stop_current": "376.77", "stop_current_set": "2026-09-04",
             "thesis": "t", "setup": "s"}]
    held = {"qty": 11.0, "cost": 5368.0, "lots": 1, "avg_entry": 488.0, "entry_date": "2026-08-18"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([400.0, 405.72], [{"level": 404.32}])
    try:
        e = srv._review_one("FN", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    assert e["stop_current"] == 376.77
    assert e["stop_current_set"] == "2026-09-04"
    # The entry-stop gap is still counted -- filling stop_current does not fix it.
    assert e["lots_without_stop"] == 1
    # Risk to the managed stop, from today's price.
    assert abs(e["risk_to_stop"] - (405.72 - 376.77) * 11) < 1e-6
    assert e["through_stop"] is False


def test_price_through_the_managed_stop_is_flagged_not_reported_as_room():
    """Past the stop there is no risk *to* it; a positive number would mislead."""
    lots = [{"symbol": "POWL", "status": "open", "qty": "45", "entry_price": "216.32",
             "stop": "", "stop_current": "200.00", "stop_current_set": "2026-09-04",
             "thesis": "t", "setup": "s"}]
    held = {"qty": 45.0, "cost": 9734.4, "lots": 1, "avg_entry": 216.32, "entry_date": "2026-08-03"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([195.0, 180.14], [{"level": 122.13}])
    try:
        e = srv._review_one("POWL", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    assert e["through_stop"] is True
    assert e["risk_to_stop"] < 0, "through the stop, the figure must be negative"
    flags = {f["key"] for f in srv._review_flags(e, None)}
    assert "through_stop" in flags
    assert "near_stop" not in flags, "through and near are mutually exclusive"


def test_disagreeing_lot_stops_take_the_tightest_and_say_so():
    """Averaging into a level nobody set would be inventing a decision."""
    lots = [
        {"symbol": "COHR", "status": "open", "qty": "50", "entry_price": "302.00",
         "stop": "", "stop_current": "256.41", "stop_current_set": "2026-09-04",
         "thesis": "t", "setup": "s"},
        {"symbol": "COHR", "status": "open", "qty": "48", "entry_price": "265.25",
         "stop": "", "stop_current": "250.00", "stop_current_set": "2026-09-04",
         "thesis": "t", "setup": "s"},
    ]
    held = {"qty": 98.0, "cost": 27832.0, "lots": 2, "avg_entry": 284.0, "entry_date": "2026-08-27"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([270.0, 279.50], [{"level": 254.97}])
    try:
        e = srv._review_one("COHR", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    assert e["stop_current"] == 256.41, "tightest of the two"
    assert e["stop_current_disagrees"] is True
    assert "stop_disagrees" in {f["key"] for f in srv._review_flags(e, None)}


def test_positions_without_a_managed_stop_report_none_not_zero():
    """A missing stop is an absence, and 0.0 would be a price."""
    lots = [{"symbol": "IBIT", "status": "open", "qty": "300", "entry_price": "59.53",
             "stop": "", "stop_current": "", "thesis": "", "setup": ""}]
    held = {"qty": 300.0, "cost": 17859.0, "lots": 1, "avg_entry": 59.53, "entry_date": "2025-01-23"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([44.0, 44.88], [{"level": 40.0}])
    try:
        e = srv._review_one("IBIT", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    assert "stop_current" not in e
    assert "risk_to_stop" not in e
    assert "through_stop" not in e


def test_unparseable_stop_current_does_not_take_down_the_review():
    """A hand-edited cell must not blank every position.

    This parsing runs past the get_stock guard, so an uncaught ValueError escapes
    _review_one's documented "raises nothing" contract and /api/review returns
    502 for one bad character in one cell.
    """
    lots = [{"symbol": "FN", "status": "open", "qty": "11", "entry_price": "488.00",
             "side": "long", "stop": "", "stop_current": "n/a", "thesis": "t", "setup": "s"},
            {"symbol": "FN", "status": "open", "qty": "11", "entry_price": "426.50",
             "side": "long", "stop": "", "stop_current": "376.77", "thesis": "t", "setup": "s"}]
    held = {"qty": 22.0, "cost": 10059.5, "lots": 2, "avg_entry": 457.25, "entry_date": "2026-08-18"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([400.0, 405.72], [{"level": 404.32}])
    try:
        e = srv._review_one("FN", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    # The good lot still drives the number; the bad one is reported, not fatal.
    assert e["stop_current"] == 376.77
    assert e["stop_current_unparsed"] == ["n/a"]
    assert e["lots_with_stop_current"] == 2  # both cells are filled, one is junk


def test_short_position_takes_the_lowest_stop_and_inverts_through():
    """Tightest depends on direction, and so does "through".

    For a short the stop sits above, so the lowest is tightest and price *rising*
    past it is the breach. Keying off max() and `last < stop` silently picks the
    loosest stop and never fires the flag.
    """
    lots = [{"symbol": "XYZ", "status": "open", "qty": "100", "entry_price": "50.00",
             "side": "short", "stop": "", "stop_current": "55.00",
             "stop_current_set": "2026-09-04", "thesis": "t", "setup": "s"},
            {"symbol": "XYZ", "status": "open", "qty": "100", "entry_price": "50.00",
             "side": "short", "stop": "", "stop_current": "58.00",
             "stop_current_set": "2026-09-04", "thesis": "t", "setup": "s"}]
    held = {"qty": 200.0, "cost": 10000.0, "lots": 2, "avg_entry": 50.0, "entry_date": "2026-09-01"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([52.0, 53.00], [{"level": 48.0}])
    try:
        e = srv._review_one("XYZ", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    assert e["stop_current"] == 55.00, "lowest is tightest for a short"
    assert e["risk_to_stop"] == (55.00 - 53.00) * 200, "risk measured upward"
    assert e["through_stop"] is False

    # Now price rises through the short's stop.
    srv.get_stock = lambda sym, force=False: stub_stock([54.0, 56.00], [{"level": 48.0}])
    try:
        e2 = srv._review_one("XYZ", held, lots, {}, force=False)
    finally:
        srv.get_stock = original
    assert e2["through_stop"] is True
    assert e2["risk_to_stop"] < 0
    assert "through_stop" in {f["key"] for f in srv._review_flags(e2, None)}


def test_stop_set_date_is_withheld_when_lots_disagree():
    """Reporting one date as though it covered the position asserts a false provenance."""
    base = {"symbol": "COHR", "status": "open", "qty": "50", "entry_price": "302.00",
            "side": "long", "stop": "", "stop_current": "256.41", "thesis": "t", "setup": "s"}
    lots = [dict(base, stop_current_set="2026-09-04"), dict(base, stop_current_set="2026-09-08")]
    held = {"qty": 100.0, "cost": 30000.0, "lots": 2, "avg_entry": 300.0, "entry_date": "2026-08-27"}

    original = srv.get_stock
    srv.get_stock = lambda sym, force=False: stub_stock([270.0, 279.50], [{"level": 254.97}])
    try:
        e = srv._review_one("COHR", held, lots, {}, force=False)
    finally:
        srv.get_stock = original

    assert e["stop_current"] == 256.41, "prices agree, so no disagreement on the level"
    assert e["stop_current_disagrees"] is False
    assert e["stop_current_set"] is None, "dates differ -- report none rather than one of them"


def test_level_proximity_matches_the_client_constant():
    """app.js highlights amber off this number; the near_stop flag fires off it.

    They drifted once -- the table used 1.0 while the server used 0.5, so a
    position at 0.8 ATR rendered amber with no matching flag.
    """
    import re
    src = (Path(__file__).resolve().parent.parent / "app.js").read_text()
    m = re.search(r"const LEVEL_PROXIMITY_ATR = ([0-9.]+);", src)
    assert m, "app.js must declare LEVEL_PROXIMITY_ATR"
    assert float(m.group(1)) == srv.LEVEL_PROXIMITY_ATR
    assert "atr <= LEVEL_PROXIMITY_ATR" in src, "the cell must use the constant, not a literal"


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
