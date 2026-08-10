"""Regression tests for the reversal-candidates screen.

Deliberately self-contained: `trading_desk` is a stdlib-only sub-project, and the
repo-root `tests/` suite has a conftest that pulls in dotenv/APScheduler/lumibot
fixtures none of this needs. Run with either:

    python3 trading_desk/tests/test_reversal.py
    python3 -m pytest trading_desk/tests/test_reversal.py

No network access -- every case is synthetic bars, so the qualification rules are
pinned independently of whatever the market did today.

What's worth protecting here is the window arithmetic and the threshold scaling:
`reversal_metrics` splits a run of bars into "prior period" and "trigger day",
and an off-by-one in that split silently changes which names qualify without
throwing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server as srv  # noqa: E402


def mk(closes: list[float], volumes: list[float] | None = None) -> list[dict]:
    """Synthetic daily bars. Only close and volume matter to reversal_metrics."""
    volumes = volumes or [1000.0] * len(closes)
    return [
        {"t": f"2026-01-{i + 1:02d}", "o": c, "h": c, "l": c, "c": c, "v": v}
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]


def test_qualifying_reversal_reports_prior_bounce_and_volume():
    # 3 prior sessions sliding 110 -> 94, then a bounce to 97 on heavy volume.
    bars = mk([120, 110, 100, 97, 94, 97], volumes=[1000, 1000, 1000, 900, 800, 2000])
    rm = srv.reversal_metrics(bars, 4)
    assert rm is not None

    # Trigger day is the last bar only.
    assert rm["trigger_return_pct"] == (97 / 94 - 1) * 100
    # Prior period excludes the trigger day entirely. Cross-checked against
    # pct_return directly so this isn't re-deriving the same arithmetic twice.
    assert rm["prior_return_pct"] == srv.pct_return(bars[:-1], 3)
    assert rm["prior_return_pct"] < 0
    # Volume ratio compares the trigger day against the prior period's mean,
    # i.e. mean(900, 800, 1000) -- not the whole history.
    assert rm["volume_ratio"] == 2000 / ((1000 + 900 + 800) / 3)
    assert rm["last_close"] == 97
    assert rm["date"] == "2026-01-06"


def test_prior_period_flat_or_up_does_not_qualify():
    assert srv.reversal_metrics(mk([100, 101, 102, 103, 105]), 4) is None


def test_still_falling_on_trigger_day_does_not_qualify():
    # Prior period fell hard, but the most recent session kept falling.
    assert srv.reversal_metrics(mk([120, 110, 100, 94, 90]), 4) is None


def test_flat_trigger_day_does_not_qualify():
    # An unchanged close is not a reversal -- the rule is strictly positive.
    assert srv.reversal_metrics(mk([120, 110, 100, 94, 94]), 4) is None


def test_decline_shallower_than_scaled_threshold_does_not_qualify():
    # A 4-session window needs REVERSAL_MIN_DECLINE_PER_DAY * 3 = -2.25%.
    # This one drifts down only -1.1%, so it must not qualify: the whole point
    # of scaling the threshold is to reject sideways windows.
    bars = mk([100, 99.5, 99.0, 98.9, 99.5])
    assert srv.pct_return(bars[:-1], 3) > srv.REVERSAL_MIN_DECLINE_PER_DAY * 3
    assert srv.reversal_metrics(bars, 4) is None


def test_threshold_scales_with_window_length():
    """The same cumulative decline qualifies over a short prior period but not
    a long one -- that scaling is the whole reason the threshold is per-day."""
    # -1.1% concentrated in a single prior session: clears the -0.75% bar.
    short = srv.reversal_metrics(mk([100.0, 98.9, 99.5]), 2)
    assert short is not None
    assert short["prior_return_pct"] == (98.9 / 100.0 - 1) * 100

    # The same -1.1%, but spread across four prior sessions, is a sideways
    # drift rather than a slide, and must fail the -3.0% bar.
    spread = mk([100.0, 99.7, 99.4, 99.1, 98.9, 99.5])
    assert srv.pct_return(spread[:-1], 4) == (98.9 / 100.0 - 1) * 100
    assert srv.reversal_metrics(spread, 5) is None


def test_minimum_window_uses_single_prior_session():
    bars = mk([100, 96, 99], volumes=[1000, 1200, 2500])
    rm = srv.reversal_metrics(bars, 2)
    assert rm is not None
    assert rm["prior_return_pct"] == (96 / 100 - 1) * 100
    assert rm["trigger_return_pct"] == (99 / 96 - 1) * 100
    assert rm["volume_ratio"] == 2500 / 1200


def test_insufficient_history_returns_none():
    # lb + 1 bars are required; one short must not raise or half-compute.
    assert srv.reversal_metrics(mk([100, 95, 98]), 4) is None
    assert srv.reversal_metrics([], 2) is None


def test_zero_prior_volume_yields_null_ratio_not_a_division_error():
    # A halted prior session has no meaningful ratio. RULE #1: report the
    # absence rather than substituting a number.
    bars = mk([100, 94, 97], volumes=[500, 0, 1000])
    rm = srv.reversal_metrics(bars, 2)
    assert rm is not None
    assert rm["volume_ratio"] is None


def test_reversal_lookbacks_exclude_the_single_session_window():
    # A 1-session window has no prior period, so the screen cannot exist there.
    assert 1 not in srv.REVERSAL_LOOKBACKS
    assert set(srv.REVERSAL_LOOKBACKS).issubset(set(srv.LOOKBACKS))


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
