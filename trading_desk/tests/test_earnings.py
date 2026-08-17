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
    """A stale projection is worse than none -- it reads as 'no print coming'."""
    for today in (date(2026, 8, 17), date(2026, 1, 1), date(2030, 6, 6)):
        p = E.project_next([ev("2020-01-15")], today)
        if p is not None:
            assert p["projected_date"] > today.isoformat()
            assert p["days_until"] > 0


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
