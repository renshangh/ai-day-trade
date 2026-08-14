"""Regression tests for indicators whose definition is easy to conflate.

Self-contained for the same reason as `test_reversal.py`: `trading_desk` is a
stdlib-only sub-project and the repo-root `tests/` conftest pulls in fixtures
none of this needs. Run with either:

    python3 trading_desk/tests/test_indicators.py
    python3 -m pytest trading_desk/tests/test_indicators.py

No network -- every case is synthetic bars with a hand-computable answer.

The thing worth protecting here is that **TDR is not ATR**. They differ only in
whether overnight gaps count, so a "simplification" that routes one through the
other would produce plausible-looking numbers that are quietly wrong, and the
dashboard shows the difference between them as a gap-share figure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import indicators as ind  # noqa: E402


def bars_from(highs: list[float], lows: list[float], closes: list[float] | None = None):
    closes = closes if closes is not None else [(h + l) / 2 for h, l in zip(highs, lows)]
    return [
        {"t": f"2026-01-{i + 1:02d}", "o": closes[i], "h": highs[i], "l": lows[i],
         "c": closes[i], "v": 1000.0}
        for i in range(len(highs))
    ]


def test_tdr_warmup_is_none_not_zero():
    """An undefined average must read as undefined, never as 0.00."""
    t = ind.true_daily_range([104.0] * 20, [100.0] * 20, 14)
    assert t[:13] == [None] * 13
    assert t[13] is not None


def test_tdr_constant_range():
    t = ind.true_daily_range([104.0] * 20, [100.0] * 20, 14)
    assert abs(t[13] - 4.0) < 1e-9
    assert abs(t[19] - 4.0) < 1e-9


def test_tdr_known_mean():
    # Ranges 1..14 -> mean 7.5.
    highs = [100.0 + i for i in range(1, 15)]
    t = ind.true_daily_range(highs, [100.0] * 14, 14)
    assert abs(t[13] - 7.5) < 1e-9


def test_tdr_rolling_window_matches_recomputed_mean():
    """Guards the running-sum optimisation against drift/stale-window bugs."""
    highs, lows = [], []
    v = 100.0
    for i in range(60):
        # Deterministic but varying ranges.
        lows.append(v + (i % 7))
        highs.append(v + (i % 7) + 1.0 + (i % 5))
    t = ind.true_daily_range(highs, lows, 14)
    for i in range(13, 60):
        want = sum(highs[j] - lows[j] for j in range(i - 13, i + 1)) / 14
        assert abs(t[i] - want) < 1e-9, f"index {i}"


def test_tdr_too_short_input():
    assert ind.true_daily_range([1.0] * 5, [0.0] * 5, 14) == [None] * 5
    assert ind.true_daily_range([], [], 14) == []


def test_tdr_ignores_gaps_while_atr_counts_them():
    """The whole reason both exist. Tight intraday ranges, large overnight gaps.

    TDR must report only the intraday range; ATR must be far larger because true
    range includes the gap from the prior close.
    """
    highs, lows, closes = [], [], []
    price = 100.0
    for _ in range(30):
        lows.append(price)
        highs.append(price + 1.0)
        closes.append(price + 0.5)
        price += 10.0  # gap up every session
    tdr = ind.true_daily_range(highs, lows, 14)[-1]
    atr = ind.atr(highs, lows, closes, 14)[-1]
    assert abs(tdr - 1.0) < 1e-9, "TDR must be the pure intraday range"
    assert atr > tdr * 5, f"ATR ({atr}) should dwarf TDR ({tdr}) on a gapping series"


def test_atr_and_tdr_agree_when_there_are_no_gaps():
    """With every session opening at the prior close, true range == high-low."""
    highs, lows, closes = [], [], []
    for _ in range(30):
        lows.append(100.0)
        highs.append(102.0)
        closes.append(101.0)
    tdr = ind.true_daily_range(highs, lows, 14)[-1]
    atr = ind.atr(highs, lows, closes, 14)[-1]
    assert abs(atr - tdr) < 1e-9, f"no gaps: ATR {atr} should equal TDR {tdr}"


def test_compute_all_exposes_tdr14_aligned():
    highs = [102.0 + (i % 3) for i in range(30)]
    lows = [100.0] * 30
    allv = ind.compute_all(bars_from(highs, lows))
    assert "tdr14" in allv
    assert len(allv["tdr14"]) == 30
    # Every series must stay index-aligned with the bars.
    assert all(len(v) == 30 for v in allv.values())


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
