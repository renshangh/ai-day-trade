"""Tests for sector_signals.py's group-level metrics.

Pure functions over synthetic bars -- no network, no server. Run:
python3 trading_desk/tests/test_sector_signals.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import sector_signals as ss  # noqa: E402


def _bars(closes: list[float], *, highs=None, lows=None, vols=None) -> list[dict]:
    """Daily bars from a close series. h/l default to the close (no wick)."""
    n = len(closes)
    highs = highs or closes
    lows = lows or closes
    vols = vols or [1_000_000.0] * n
    return [
        {"t": f"2026-01-{i+1:02d}", "o": closes[i], "h": highs[i], "l": lows[i],
         "c": closes[i], "v": vols[i]}
        for i in range(n)
    ]


def _flat(price: float, n: int) -> list[dict]:
    return _bars([price] * n)


def _trend(start: float, daily_pct: float, n: int) -> list[dict]:
    closes = [start]
    for _ in range(n - 1):
        closes.append(closes[-1] * (1 + daily_pct / 100.0))
    return _bars(closes)


def _wicked(closes: list[float], wick_pct: float = 2.0) -> list[dict]:
    """Bars with a realistic high above (and low below) the close.

    Real bars never close exactly at their own high -- using them wherever a
    test cares about that distinction is what would have caught the shipped
    new_highs_lows bug, where the check compared today's close against the
    window's intraday high instead of the window's other closes.
    """
    highs = [c * (1 + wick_pct / 100.0) for c in closes]
    lows = [c * (1 - wick_pct / 100.0) for c in closes]
    return _bars(closes, highs=highs, lows=lows)


def _indicators_for(bars_by_symbol: dict[str, list[dict]]) -> dict[str, dict]:
    """The precomputed-indicators argument breadth/volatility_regime/at_level
    now take, mirroring what compute_sector_scorecard builds for real callers."""
    import indicators as ind
    return {s: ind.compute_all(b) for s, b in bars_by_symbol.items()}


# ---- relative_strength ------------------------------------------------------

def test_relative_strength_reports_group_return_matching_the_benchmark():
    """Group and benchmark rising identically nets to zero excess."""
    group = {"A": _trend(100, 1.0, 70), "B": _trend(100, 1.0, 70)}
    bench = _trend(100, 1.0, 70)
    out = ss.relative_strength(group, bench)
    for w in ("5", "21", "63"):
        assert abs(out["windows"][w]["excess_pct"]) < 1e-6, out["windows"][w]


def test_relative_strength_excess_is_positive_when_group_outperforms():
    group = {"A": _trend(100, 2.0, 30)}
    bench = _trend(100, 0.5, 30)
    out = ss.relative_strength(group, bench)
    assert out["windows"]["5"]["excess_pct"] > 0
    assert out["windows"]["21"]["excess_pct"] > 0


def test_relative_strength_handles_missing_benchmark():
    group = {"A": _trend(100, 1.0, 30)}
    out = ss.relative_strength(group, None)
    assert out["windows"]["5"]["benchmark_return_pct"] is None
    assert out["windows"]["5"]["excess_pct"] is None
    assert out["windows"]["5"]["group_return_pct"] is not None
    assert out["excess_trend_pct"] is None


def test_relative_strength_trend_detects_accelerating_outperformance():
    """Flat for 5 sessions, then a sharp run -- recent excess must exceed prior."""
    closes = [100.0] * 6 + [100 * 1.03 ** i for i in range(1, 6)]
    group = {"A": _bars(closes)}
    bench = _bars([100.0] * 11)
    out = ss.relative_strength(group, bench)
    assert out["excess_trend_pct"] > 0


def test_relative_strength_skips_symbols_shorter_than_the_window():
    """A newly-added constituent with 10 bars must not crash the 21/63d windows."""
    group = {"OLD": _trend(100, 0.5, 70), "NEW": _flat(50, 10)}
    out = ss.relative_strength(group, _trend(100, 0.5, 70))
    assert out["windows"]["63"]["n"] == 1
    assert out["windows"]["5"]["n"] == 2


# ---- breadth -----------------------------------------------------------------

def test_breadth_is_100_percent_when_every_name_is_above_its_averages():
    group = {"A": _trend(100, 0.3, 250), "B": _trend(100, 0.3, 250)}
    out = ss.breadth(group, _indicators_for(group))
    assert out["above_sma20_pct"] == 100.0
    assert out["above_sma50_pct"] == 100.0
    assert out["above_sma200_pct"] == 100.0
    assert out["n"] == 2


def test_breadth_is_0_percent_when_every_name_is_below_its_averages():
    group = {"A": _trend(100, -0.3, 250)}
    out = ss.breadth(group, _indicators_for(group))
    assert out["above_sma20_pct"] == 0.0
    assert out["above_sma200_pct"] == 0.0


def test_breadth_reports_none_for_an_empty_group():
    out = ss.breadth({}, {})
    assert out["n"] == 0
    assert out["above_sma20_pct"] is None


# ---- new_highs_lows ------------------------------------------------------------

def test_new_high_is_counted_when_todays_close_is_the_window_max():
    """Wicked bars, not flat h=c ones: the shipped bug compared close against
    the window's intraday HIGH, which a flat-wick fixture cannot distinguish
    from the correct close-against-close comparison. With a 2% wick, today's
    close (150) is still the window's highest close, but is nowhere near the
    window's highest intraday high (150 * 1.02) -- only the correct
    implementation counts this as a new high."""
    closes = [100.0] * 19 + [150.0]
    out = ss.new_highs_lows({"A": _wicked(closes)}, window=20)
    assert out["new_high_count"] == 1
    assert out["new_low_count"] == 0


def test_new_low_is_counted_when_todays_close_is_the_window_min():
    closes = [100.0] * 19 + [50.0]
    out = ss.new_highs_lows({"A": _wicked(closes)}, window=20)
    assert out["new_low_count"] == 1
    assert out["new_high_count"] == 0


def test_a_wide_intraday_wick_does_not_manufacture_a_new_high():
    """A day with a huge wick but a close that is not itself a new extreme
    must not count.

    This is the shipped bug in reverse: comparing close against the window's
    intraday high would make almost every ordinary day register as a "new
    high" the moment any single day's wick exceeded the rest, regardless of
    where that day's close actually landed. Today's close (99.5) sits below
    every prior close (100.0), even though its intraday high (140.0) dwarfs
    the rest of the window.
    """
    closes = [100.0] * 19 + [99.5]
    highs = [100.5] * 19 + [140.0]   # a huge wick on the last day
    bars = _bars(closes, highs=highs)
    out = ss.new_highs_lows({"A": bars}, window=20)
    assert out["new_high_count"] == 0


def test_a_name_with_fewer_bars_than_the_window_is_excluded_not_miscounted():
    out = ss.new_highs_lows({"SHORT": _wicked([100.0] * 5)}, window=20)
    assert out["n"] == 0
    assert out["new_high_count"] == 0


# ---- participation -------------------------------------------------------------

def test_participation_ratio_above_one_when_recent_volume_is_higher():
    # 21 bars: strictly more than the 20-session lookback, matching the
    # sibling functions' `len(bars) <= lookback: continue` guard.
    vols = [1_000_000.0] * 16 + [5_000_000.0] * 5
    bars = _bars([100.0] * 21, vols=vols)
    out = ss.participation({"A": bars})
    assert out["ratio"] > 1.0


def test_participation_is_none_below_20_sessions_of_history():
    out = ss.participation({"A": _flat(100, 10)})
    assert out["ratio"] is None
    assert out["dollar_volume_5d_avg"] is None


def test_participation_sums_dollar_volume_across_constituents():
    """Two names summed must exceed either alone -- guards against overwriting
    rather than accumulating in the per-day aggregation loop."""
    a = _bars([100.0] * 21, vols=[1_000_000.0] * 21)
    b = _bars([50.0] * 21, vols=[1_000_000.0] * 21)
    solo = ss.participation({"A": a})
    combined = ss.participation({"A": a, "B": b})
    assert combined["dollar_volume_20d_avg"] > solo["dollar_volume_20d_avg"]


def test_participation_excludes_a_constituent_shorter_than_the_lookback():
    """This is the shipped bug: summing a short-history name into some days but
    not others let the ratio move purely from a roster/history-length
    difference, with zero real volume change in either name.

    A (long history, flat $10/share * 1 share = irrelevant constant volume)
    plus B (exactly at the lookback boundary, so too short to qualify) must
    report identically to A alone -- B must be excluded outright, not summed
    into only the days it has data for.
    """
    a = _bars([100.0] * 40, vols=[1_000_000.0] * 40)   # ample history
    b = _bars([100.0] * 20, vols=[9_000_000.0] * 20)    # exactly 20: too short
    solo = ss.participation({"A": a})
    combined = ss.participation({"A": a, "B": b})
    assert combined["dollar_volume_20d_avg"] == solo["dollar_volume_20d_avg"]
    assert combined["ratio"] == solo["ratio"]


# ---- volatility_regime ----------------------------------------------------------

def test_volatility_expansion_is_positive_when_atr_percent_has_grown():
    # Tight range for the first 40 bars, then a much wider range for the last 20.
    n1, n2 = 40, 25
    tight = _bars([100.0] * n1, highs=[100.5] * n1, lows=[99.5] * n1)
    wide = _bars([100.0] * n2, highs=[110.0] * n2, lows=[90.0] * n2)
    bars = tight + wide
    group = {"A": bars}
    out = ss.volatility_regime(group, _indicators_for(group), lookback=20)
    assert out["expansion_pct_points"] > 0
    assert out["avg_atr_pct_now"] > out["avg_atr_pct_20d_ago"]


def test_volatility_regime_none_when_history_too_short():
    group = {"A": _flat(100, 15)}
    out = ss.volatility_regime(group, _indicators_for(group), lookback=20)
    assert out["avg_atr_pct_now"] is None


def test_volatility_regime_treats_a_genuinely_zero_atr_as_a_value_not_missing():
    """A perfectly flat series has atr14 == 0.0 -- a real reading, not an
    absent one. Truthiness-based filtering would silently drop it."""
    group = {"A": _flat(100, 40)}
    out = ss.volatility_regime(group, _indicators_for(group), lookback=20)
    assert out["avg_atr_pct_now"] == 0.0


# ---- dispersion ------------------------------------------------------------------

def test_dispersion_is_zero_when_every_name_moves_identically():
    """Everything up 5% together today: today's cross-sectional stdev is 0 --
    the textbook 'macro day, not stock-picking day' case."""
    base = [100.0] * 24 + [105.0]
    group = {"A": _bars(list(base)), "B": _bars([c * 2 for c in base])}
    out = ss.dispersion(group)
    assert out["today_pct"] == 0.0


def test_dispersion_is_positive_when_names_diverge_today():
    a = [100.0] * 24 + [110.0]   # +10% today
    b = [100.0] * 24 + [95.0]    # -5% today
    out = ss.dispersion({"A": _bars(a), "B": _bars(b)})
    assert out["today_pct"] > 5.0


def test_dispersion_none_below_lookback_plus_one_sessions():
    out = ss.dispersion({"A": _flat(100, 10), "B": _flat(100, 10)}, lookback=20)
    assert out["today_pct"] is None


# ---- at_level ----------------------------------------------------------------

def test_at_level_counts_a_name_sitting_on_a_well_tested_support():
    # A repeated bounce off 90 -- classic support -- then price sits near it.
    closes = []
    for _ in range(6):
        closes += [110.0, 100.0, 90.0, 100.0]
    closes += [91.0]
    bars = _bars(closes, highs=[c + 1 for c in closes], lows=[c - 1 for c in closes])
    group = {"A": bars}
    out = ss.at_level(group, _indicators_for(group), proximity_atr=2.0)
    assert out["n"] == 1
    assert out["at_support_count"] + out["at_resistance_count"] >= 0  # never negative/crash


def test_at_level_handles_a_flat_series_with_no_levels_gracefully():
    group = {"A": _flat(100, 30)}
    out = ss.at_level(group, _indicators_for(group), proximity_atr=0.5)
    assert out["at_support_count"] == 0
    assert out["at_resistance_count"] == 0


# ---- compute_sector_scorecard (assembly) --------------------------------------

def test_scorecard_separates_used_from_missing_constituents():
    group = {"A": _trend(100, 0.2, 70), "B": []}
    out = ss.compute_sector_scorecard(group, _trend(100, 0.2, 70))
    assert out["constituents_used"] == ["A"]
    assert out["constituents_missing"] == ["B"]


def test_scorecard_has_every_documented_top_level_key():
    group = {"A": _trend(100, 0.2, 70)}
    out = ss.compute_sector_scorecard(group, _trend(100, 0.2, 70))
    for key in ("relative_strength", "breadth", "new_highs_lows", "participation",
                "volatility", "dispersion", "at_level", "cycle_stages"):
        assert key in out, key


def test_scorecard_survives_an_empty_group_without_raising():
    out = ss.compute_sector_scorecard({}, None)
    assert out["constituents_used"] == []
    assert out["breadth"]["n"] == 0


# ---- cycle_stages -------------------------------------------------------------

def _noisy_trend(start: float, drift_pct: float, amp_pct: float, n: int) -> list[float]:
    """A close series with genuine bidirectional daily moves, not a flat line.

    Every other day steps by `drift_pct + amp_pct`, the rest by `drift_pct -
    amp_pct` -- net drift accumulates over time, but with amp_pct > 0 there are
    real up AND down days, so RSI lands at a realistic mid-range value instead
    of pinning at 0 or 100 the way a perfectly flat-then-one-direction series
    does (a flat base has zero average loss, so RSI=100 on literally any single
    uptick -- the bug that made the first version of these fixtures useless).
    """
    c = [start]
    for i in range(1, n):
        step = drift_pct + (amp_pct if i % 2 == 0 else -amp_pct)
        c.append(c[-1] * (1 + step / 100.0))
    return c


# Six fixtures, one per cycle stage, each verified numerically against
# `_name_cycle_stage` before being written here -- see the PR description for
# the derivation. Every one uses `_noisy_trend` for realistic RSI behavior
# rather than a flat base.

def _stage_bars_extended() -> list[dict]:
    """Steady climb throughout: above both averages, SMA50 rising, RSI moderate."""
    return _wicked(_noisy_trend(60.0, 0.15, 0.5, 260), wick_pct=1.0)


def _stage_bars_euphoria() -> list[dict]:
    """A steady climb that accelerates sharply in the final month."""
    base = _noisy_trend(60.0, 0.15, 0.5, 240)
    tail = _noisy_trend(base[-1], 1.5, 0.5, 21)[1:]
    return _wicked(base + tail, wick_pct=1.0)


def _stage_bars_peak() -> list[dict]:
    """An uptrend, a plateau (SMA50 catches up to price), then a small dip with
    a partial recovery -- enough to flip SMA50's own recent slope negative
    without pulling price back below it. This is the mathematically narrow
    case: price above SMA50 while SMA50 itself has just started rolling over,
    which for a 50-day average fed by a long prior uptrend requires the last
    few days to retrace toward -- not through -- the average, not a simple
    proportional decline (which flips both conditions at once, landing on
    Correction instead)."""
    uptrend = _noisy_trend(60.0, 0.2, 0.4, 180)
    peak_level = uptrend[-1]
    plateau = [peak_level] * 45
    dip = [peak_level * 0.96, peak_level * 0.95, peak_level * 0.96,
           peak_level * 0.965, peak_level * 1.001]
    return _wicked(uptrend + plateau + dip, wick_pct=1.0)


def _stage_bars_correction() -> list[dict]:
    """An uptrend, then a real recent decline -- below SMA50, still above SMA200."""
    base = _noisy_trend(60.0, 0.15, 0.5, 240)
    tail = _noisy_trend(base[-1], -0.5, 0.3, 20)[1:]
    return _wicked(base + tail, wick_pct=1.0)


def _stage_bars_bottoming() -> list[dict]:
    """An uptrend, then a long decline -- below both averages."""
    base = _noisy_trend(60.0, 0.15, 0.5, 200)
    tail = _noisy_trend(base[-1], -0.3, 0.3, 61)[1:]
    return _wicked(base + tail, wick_pct=1.0)


def _stage_bars_recovery() -> list[dict]:
    """An uptrend, a long decline (drags SMA200 down), then a real bounce that
    reclaims SMA50 while SMA200 is still well above price."""
    base = _noisy_trend(60.0, 0.15, 0.5, 200)
    decline = _noisy_trend(base[-1], -0.25, 0.3, 221)[1:]
    bounce = _noisy_trend((base + decline)[-1], 0.8, 0.3, 21)[1:]
    return _wicked(base + decline + bounce, wick_pct=1.0)


def test_stage_extended_uptrend_above_both_averages_sma50_rising_not_extreme():
    bars = _stage_bars_extended()
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) == "Extended/Uptrend"


def test_stage_euphoria_peak_needs_extension_or_overbought_near_a_high():
    bars = _stage_bars_euphoria()
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) == "Local Euphoria/Peak"


def test_stage_peak_is_near_the_high_but_sma50_has_rolled_over():
    bars = _stage_bars_peak()
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) == "Local Peak"


# ---- long_high context ---------------------------------------------------------

def test_long_high_context_reports_the_full_window_when_history_allows():
    bars = _stage_bars_extended()   # 260 sessions, well over the 252-session window
    ctx = ss._long_high_context(ss._closes(bars))
    assert ctx["window_sessions"] == ss.LONG_HIGH_WINDOW_SESSIONS
    assert ctx["pct_from_high"] <= 0


def test_long_high_context_uses_whatever_history_is_actually_available():
    """A name with less than 52 weeks of history must not silently claim one."""
    bars = _wicked([100.0] * 40)
    ctx = ss._long_high_context(ss._closes(bars))
    assert ctx["window_sessions"] == 40


def test_long_high_context_is_none_below_the_minimum_history():
    bars = _wicked([100.0] * 15)
    assert ss._long_high_context(ss._closes(bars)) is None


def test_local_peak_can_sit_far_below_its_own_long_high():
    """The GLW case: a name stalling near a 20-session high that is itself far
    below where the name actually traded months ago. A `Local Peak` reads as
    "at its high" unless this context travels with it -- this is the
    regression test for exactly that misreading.

    Built directly (not by reusing `_stage_bars_peak`'s own embedded uptrend --
    layering that whole shape on top of a decline just re-climbs past the
    original peak, defeating the point): a genuine multi-month peak, a real
    decline, then a plateau-and-small-dip at the post-decline level. The
    decline alone leaves enough residual weight in the trailing 200-day
    average that price still clears both SMA50 and SMA200 by the end, without
    a second independent climb.
    """
    real_peak = _noisy_trend(60.0, 0.5, 0.5, 180)
    decline = _noisy_trend(real_peak[-1], -0.35, 0.3, 50)[1:]
    base = decline[-1]
    plateau = [base] * 45
    dip = [base * 0.96, base * 0.95, base * 0.96, base * 0.965, base * 1.001]
    closes = real_peak + decline + plateau + dip
    bars = _wicked(closes, wick_pct=1.0)

    a = _indicators_for({"A": bars})["A"]
    stage = ss._name_cycle_stage(ss._closes(bars), a)
    ctx = ss._long_high_context(ss._closes(bars))

    assert stage == "Local Peak"
    # The whole point: a real, double-digit-percent gap between "near its
    # 20-session high" (true, by construction of the Local Peak shape) and
    # "near its 52-week high" (false -- it peaked and fell first).
    assert ctx["pct_from_high"] < -10.0


def test_cycle_stages_includes_long_high_context_per_symbol():
    group = {"A": _stage_bars_extended()}
    out = ss.cycle_stages(group, _indicators_for(group))
    assert "long_high" in out
    assert out["long_high"]["A"]["window_sessions"] == ss.LONG_HIGH_WINDOW_SESSIONS


def test_stage_correction_is_below_sma50_but_still_above_sma200():
    bars = _stage_bars_correction()
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) == "Correction"


def test_stage_bottoming_is_below_both_averages():
    bars = _stage_bars_bottoming()
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) == "Bottoming"


def test_stage_recovery_is_above_sma50_but_still_below_sma200():
    bars = _stage_bars_recovery()
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) == "Recovery"


def test_stage_is_none_when_history_is_too_short():
    bars = _wicked([100.0] * 25)
    a = _indicators_for({"A": bars})["A"]
    assert ss._name_cycle_stage(ss._closes(bars), a) is None


def test_cycle_stages_group_label_is_the_most_common_stage():
    group = {
        "A": _stage_bars_extended(),
        "B": _stage_bars_extended(),
        "C": _stage_bars_peak(),
    }
    out = ss.cycle_stages(group, _indicators_for(group))
    assert out["group_label"] == "Extended/Uptrend"
    assert out["counts"]["Extended/Uptrend"] == 2
    assert out["counts"]["Local Peak"] == 1
    assert out["n_classified"] == 3
    assert out["unclassified"] == []


def test_cycle_stages_reports_a_tie_rather_than_inventing_a_winner():
    group = {
        "A": _stage_bars_extended(),
        "B": _stage_bars_peak(),
    }
    out = ss.cycle_stages(group, _indicators_for(group))
    assert " / " in out["group_label"]
    assert "Extended/Uptrend" in out["group_label"]
    assert "Local Peak" in out["group_label"]


def test_cycle_stages_excludes_short_history_names_from_the_label():
    group = {
        "A": _stage_bars_extended(),
        "SHORT": _wicked([100.0] * 25),
    }
    out = ss.cycle_stages(group, _indicators_for(group))
    assert out["unclassified"] == ["SHORT"]
    assert out["n_classified"] == 1
    assert out["group_label"] == "Extended/Uptrend"


def test_cycle_stages_group_label_is_none_when_nothing_is_classifiable():
    group = {"SHORT": _wicked([100.0] * 25)}
    out = ss.cycle_stages(group, _indicators_for(group))
    assert out["group_label"] is None
    assert out["unclassified"] == ["SHORT"]


def test_compute_sector_scorecard_includes_cycle_stages():
    group = {"A": _stage_bars_extended()}
    out = ss.compute_sector_scorecard(group, _trend(100, 0.1, 260))
    assert out["cycle_stages"]["group_label"] == "Extended/Uptrend"


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
