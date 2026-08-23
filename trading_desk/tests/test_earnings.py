"""Tests for the earnings-timing projector.

Run: python3 trading_desk/tests/test_earnings.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import earnings as E  # noqa: E402


def ev(d: str, timing: str = "after_close") -> dict:
    return {"date": d, "timing": timing, "accepted_utc": ""}


def test_never_projects_a_past_date():
    """A stale projection is worse than none -- it reads as 'no print coming'.

    The invariant is "never in the past", not "always strictly future": today is
    a legitimate answer for a company reporting after tonight's close.
    """
    for today in (date(2026, 8, 17), date(2026, 1, 1), date(2030, 6, 6)):
        p = E.project_next([ev("2020-01-15")], today)
        if p is not None:
            assert p["projected_date"] >= today.isoformat()
            assert p["days_until"] >= 0


def test_empty_and_malformed_input_returns_none():
    assert E.project_next([], date(2026, 8, 17)) is None
    assert E.project_next([{"date": "not-a-date"}], date(2026, 8, 17)) is None
    assert E.earnings_move_stats([], []) is None
    assert E.earnings_move_stats([ev("2026-01-05")], []) is None


def test_weekend_projections_shift_to_a_weekday():
    assert E._shift_off_weekend(date(2026, 8, 15)).weekday() == 4   # Sat -> Fri
    assert E._shift_off_weekend(date(2026, 8, 16)).weekday() == 0   # Sun -> Mon
    assert E._shift_off_weekend(date(2026, 8, 18)).weekday() == 1   # Tue unchanged


def test_uncertainty_band_brackets_the_estimate():
    """Callers plan against the band; the earliest edge is the conservative one."""
    p = E.project_next([ev("2025-08-13"), ev("2024-08-14"), ev("2023-08-15")], date(2026, 8, 1))
    assert p is not None
    assert p["earliest_plausible"] < p["projected_date"] < p["latest_plausible"]
    assert p["days_until_earliest"] < p["days_until"]
    assert p["uncertainty_days"] == E.PROJECTION_P90_ERROR_DAYS
    assert p["estimated"] is True


def test_projection_lands_near_the_calendar_anniversary():
    """A steady annual slot should project within a few days of its anniversary.

    Guards the fix for the +364-day step, which drifted a week early per cycle.
    """
    hist = [ev("2023-08-15"), ev("2024-08-14"), ev("2025-08-13")]
    p = E.project_next(hist, date(2026, 7, 1))
    got = date.fromisoformat(p["projected_date"])
    assert abs((got - date(2026, 8, 13)).days) <= 5, got


def test_expected_timing_follows_the_company_habit():
    hist = [ev("2024-08-14", "before_open"), ev("2025-08-13", "before_open"),
            ev("2023-08-15", "before_open")]
    assert E.project_next(hist, date(2026, 7, 1))["expected_timing"] == "before_open"


def test_move_stats_use_the_right_reaction_session():
    """after_close reacts the NEXT session; before_open reacts the same session.

    Getting this backwards would measure the pre-earnings day as the reaction.
    """
    bars = [
        {"t": "2026-03-02", "c": 100.0}, {"t": "2026-03-03", "c": 100.0},
        {"t": "2026-03-04", "c": 110.0}, {"t": "2026-03-05", "c": 110.0},
    ]
    # Announced after the close on 03-03 -> the 03-04 session (+10%) is the move.
    after = E.earnings_move_stats([ev("2026-03-03", "after_close")], bars)
    assert after is not None and abs(after["mean_abs_move_pct"] - 10.0) < 1e-9

    # Announced before the open on 03-04 -> the 03-04 session itself (+10%).
    before = E.earnings_move_stats([ev("2026-03-04", "before_open")], bars)
    assert before is not None and abs(before["mean_abs_move_pct"] - 10.0) < 1e-9

    # Intraday releases are ambiguous and excluded rather than guessed at.
    assert E.earnings_move_stats([ev("2026-03-04", "intraday")], bars) is None


def test_move_stats_are_absolute_not_signed():
    """Direction is not predictable; magnitude is what matters for timing risk."""
    bars = [{"t": "2026-03-02", "c": 100.0}, {"t": "2026-03-03", "c": 100.0},
            {"t": "2026-03-04", "c": 90.0}]
    s = E.earnings_move_stats([ev("2026-03-03", "after_close")], bars)
    assert s["mean_abs_move_pct"] > 0


def test_median_uses_true_median_for_even_samples():
    """Regression: a hand-rolled moves_sorted[n//2] took the upper-middle element.

    Even n is the normal case (two years of quarters), and on
    [4.76, 5.0, 10.0, 20.0] the old code returned 10.0 against a true median of
    7.5 -- a 33% overstatement of the risk figure the calendar displays.
    """
    import statistics
    bars = [{"t": f"2026-01-{i+1:02d}", "c": c} for i, c in
            enumerate([100, 100, 110, 110, 100, 100, 105, 105, 100, 100, 120, 120])]
    evs = [ev(d) for d in ("2026-01-02", "2026-01-06", "2026-01-08", "2026-01-10")]
    s = E.earnings_move_stats(evs, bars)
    dates = [b["t"][:10] for b in bars]
    closes = [float(b["c"]) for b in bars]
    idx = {d: i for i, d in enumerate(dates)}
    moves = [abs(closes[idx[e["date"]] + 1] / closes[idx[e["date"]]] - 1) * 100 for e in evs]
    assert s["n"] == 4
    assert abs(s["median_abs_move_pct"] - statistics.median(moves)) < 1e-9
    assert abs(s["median_abs_move_pct"] - 7.5) < 1e-9


def test_past_dates_return_none_rather_than_an_invented_tomorrow():
    """Regression: the guard used to substitute today+1, asserting an imminent
    print on no evidence. Every other insufficient-history path returns None."""
    for today in (date(2026, 8, 18), date(2027, 1, 4)):
        p = E.project_next([ev("2019-03-05")], today)
        assert p is None or p["projected_date"] >= today.isoformat()


def test_a_print_landing_today_is_surfaced_not_skipped():
    """Regression: the guard required a strictly future date, so a company
    reporting after tonight's close was rolled forward a full year (366 days).
    Today is the most important day to show, not the one to skip."""
    hist = [ev("2025-08-18"), ev("2024-08-19"), ev("2023-08-17")]
    p = E.project_next(hist, date(2026, 8, 18))
    assert p is not None, "a print due today must not vanish"
    assert p["days_until"] == 0, p["days_until"]
    assert p["projected_date"] == "2026-08-18"


def test_slot_is_chosen_by_anniversary_not_by_364_day_stepping():
    """Stepping 364 days to pick the slot lands one day short of the anniversary
    and then skips a year; the anniversary must decide the slot."""
    hist = [ev("2025-08-18"), ev("2024-08-19")]
    # The day before the anniversary must project days ahead, not ~365.
    p = E.project_next(hist, date(2026, 8, 17))
    assert p["days_until"] < 30, p


def test_week_window_measures_from_the_pre_earnings_close():
    """1-week performance includes the initial gap, measured off the same base.

    base=100 -> reaction +10% -> 5 sessions on at 121 is +21% for the week.
    """
    closes = [100.0, 100.0, 110.0, 112.0, 115.0, 118.0, 121.0, 121.0]
    bars = [{"t": f"2026-03-{i+2:02d}", "c": c} for i, c in enumerate(closes)]
    s = E.earnings_move_stats([ev("2026-03-03", "after_close")], bars)
    assert s is not None
    assert abs(s["median_abs_move_pct"] - 10.0) < 1e-9          # 1-day
    assert abs(s["median_abs_move_1w_pct"] - 21.0) < 1e-9       # 1-week incl. gap
    assert s["n_week"] == 1


def test_week_window_is_skipped_rather_than_truncated():
    """A partial week must not be reported as a full one."""
    bars = [{"t": "2026-03-02", "c": 100.0}, {"t": "2026-03-03", "c": 100.0},
            {"t": "2026-03-04", "c": 110.0}]
    s = E.earnings_move_stats([ev("2026-03-03", "after_close")], bars)
    assert s is not None
    assert s["n"] == 1
    assert "median_abs_move_1w_pct" not in s, "no full week of history exists"


def test_signed_and_absolute_stats_disagree_when_moves_are_one_sided():
    """Signed median shows lean; absolute shows violence. Both are reported."""
    # Two prints, both down 10%.
    closes = [100.0, 100.0, 90.0, 90.0, 100.0, 100.0, 90.0, 90.0]
    bars = [{"t": f"2026-04-{i+1:02d}", "c": c} for i, c in enumerate(closes)]
    s = E.earnings_move_stats([ev("2026-04-02"), ev("2026-04-06")], bars)
    assert abs(s["median_abs_move_pct"] - 10.0) < 1e-9
    assert s["median_signed_move_pct"] < 0, "both prints fell; signed must be negative"
    assert s["down_count"] == 2 and s["up_count"] == 0


def _main() -> None:
    tests = sorted((n, f) for n, f in globals().items()
                   if n.startswith("test_") and callable(f))
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {name}: {e}")
    print(f"\n{'ALL PASSED' if not failures else 'FAILED'} ({failures} failure(s))")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    _main()
