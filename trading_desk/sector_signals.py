"""Leading-indicator scorecard for a group of symbols, computed from bars alone.

Generic over any group from `universe.all_groups()` -- nothing here names a
sector. Every metric is a measured fact about the group's own price/volume
history: nothing is scored, banded, or combined into a verdict. Facts, not
signals dressed up as an edge this module does not have -- the same rule the
daily review's flags follow (see trading_desk/README.md).

"Leading" here means the metric's own value moves before, or as, sentiment
resolves into a directional print -- breadth divergence, volatility expansion,
participation acceleration, dispersion collapse -- as opposed to trailing
return, which is the resolution itself. It does not mean predictive: nothing
in this module claims to know which way a name breaks next; it names how much
agreement, energy, and room the group has *right now*.
"""

from __future__ import annotations

import statistics

import indicators

# Shared by new_highs_lows, participation, volatility_regime, and dispersion.
# One constant rather than four independent `=20` defaults, so a future change
# to widen or narrow the window is a single edit with an explicit relationship
# between the four, not four defaults that happen to agree today by accident.
DEFAULT_LOOKBACK_SESSIONS = 20


def _closes(bars: list[dict]) -> list[float]:
    return [float(b["c"]) for b in bars]


def _pct_return(closes: list[float], back: int) -> float | None:
    """Simple return from `back` sessions ago to the latest close."""
    if len(closes) <= back:
        return None
    return (closes[-1] / closes[-1 - back] - 1.0) * 100.0


def _last(series: list) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None


def relative_strength(
    bars_by_symbol: dict[str, list[dict]],
    benchmark_bars: list[dict] | None,
    windows: tuple[int, ...] = (5, 21, 63),
) -> dict:
    """Equal-weighted group return vs the benchmark, per window, plus a trend.

    The trend is the part that leads rather than reports: whether the most
    recent 5-session excess return is widening or narrowing versus the 5
    sessions before it -- outperformance accelerating or fading, not just
    present.
    """
    bench_closes = _closes(benchmark_bars) if benchmark_bars else None
    by_window: dict[str, dict] = {}
    for w in windows:
        rets = [r for r in (_pct_return(_closes(b), w) for b in bars_by_symbol.values())
                if r is not None]
        group_ret = statistics.fmean(rets) if rets else None
        bench_ret = _pct_return(bench_closes, w) if bench_closes else None
        excess = (group_ret - bench_ret) if (group_ret is not None and bench_ret is not None) else None
        by_window[str(w)] = {
            "group_return_pct": group_ret,
            "benchmark_return_pct": bench_ret,
            "excess_pct": excess,
            "n": len(rets),
        }

    excess_trend_pct = None
    if bench_closes is not None:
        def excess_over(back_start: int, back_end: int) -> float | None:
            # Return from `back_start` sessions ago to `back_end` sessions ago
            # (both counted back from latest), group minus benchmark.
            g = []
            for b in bars_by_symbol.values():
                c = _closes(b)
                if len(c) <= back_start:
                    continue
                g.append((c[-1 - back_end] / c[-1 - back_start] - 1.0) * 100.0)
            if not g or len(bench_closes) <= back_start:
                return None
            gr = statistics.fmean(g)
            br = (bench_closes[-1 - back_end] / bench_closes[-1 - back_start] - 1.0) * 100.0
            return gr - br

        recent = excess_over(5, 0)
        prior = excess_over(10, 5)
        if recent is not None and prior is not None:
            excess_trend_pct = recent - prior

    return {"windows": by_window, "excess_trend_pct": excess_trend_pct}


def breadth(bars_by_symbol: dict[str, list[dict]], indicators_by_symbol: dict[str, dict]) -> dict:
    """Share of constituents currently above their own 20/50/200-day SMA.

    Breadth narrowing while the group's own price is near highs is a classic
    divergence -- fewer names are actually participating in the move; breadth
    broadening while price lags is the opposite. The number is reported
    without that interpretation attached.

    `indicators_by_symbol` is each symbol's `indicators.compute_all(bars)`
    result, computed once by the caller and shared with `volatility_regime`
    and `at_level` -- computing the full indicator set (RSI, MACD, Bollinger,
    Stochastic, OBV, VWAP...) separately in all three, when only SMA/ATR are
    ever read, would triple the work on every group.
    """
    n = above20 = above50 = above200 = 0
    for symbol, bars in bars_by_symbol.items():
        closes = _closes(bars)
        if not closes:
            continue
        n += 1
        last = closes[-1]
        a = indicators_by_symbol[symbol]
        if (v := _last(a["sma20"])) is not None and last > v:
            above20 += 1
        if (v := _last(a["sma50"])) is not None and last > v:
            above50 += 1
        if (v := _last(a["sma200"])) is not None and last > v:
            above200 += 1
    return {
        "n": n,
        "above_sma20_pct": (above20 / n * 100.0) if n else None,
        "above_sma50_pct": (above50 / n * 100.0) if n else None,
        "above_sma200_pct": (above200 / n * 100.0) if n else None,
    }


def new_highs_lows(bars_by_symbol: dict[str, list[dict]], window: int = DEFAULT_LOOKBACK_SESSIONS) -> dict:
    """Count of constituents at a new `window`-session high or low today.

    Short-window (20 sessions, ~1 month) rather than 52-week on purpose: a
    52-week extreme is rare enough to be nearly always zero for a 4-13 name
    group, so it would report "nothing" most days. A 20-session window
    actually moves and is the horizon this desk's swing positions live in.
    """
    n = new_high = new_low = 0
    for bars in bars_by_symbol.values():
        if len(bars) < window:
            continue
        n += 1
        recent = bars[-window:]
        closes = [float(b["c"]) for b in recent]
        last_close = closes[-1]
        hi = max(closes)
        lo = min(closes)
        if last_close >= hi:
            new_high += 1
        if last_close <= lo:
            new_low += 1
    return {"n": n, "new_high_count": new_high, "new_low_count": new_low, "window_sessions": window}


def participation(bars_by_symbol: dict[str, list[dict]], lookback: int = DEFAULT_LOOKBACK_SESSIONS) -> dict:
    """Aggregate dollar volume, trailing 5-session average vs trailing `lookback`.

    A ratio above 1 means dollar volume across the group has picked up
    recently relative to its own past month; below 1 means it has cooled.
    Aggregate dollar volume, not share count, so one high-price low-share-count
    name cannot be swamped by a cheap, heavily-traded one in the sum.

    Only constituents with at least `lookback` sessions of history contribute,
    same guard `volatility_regime` and `dispersion` use. Without it, a group
    containing a recently-listed or recently-added name would have fewer
    contributors on distant days than on recent ones, and the aggregate ratio
    would move purely from that roster effect -- reporting a participation
    change with no volume change behind it.
    """
    usable = {s: b for s, b in bars_by_symbol.items() if len(b) > lookback}
    if not usable:
        return {"dollar_volume_5d_avg": None, "dollar_volume_20d_avg": None, "ratio": None}
    dvol_by_day: dict[int, float] = {}
    for bars in usable.values():
        for i, b in enumerate(reversed(bars[-lookback:])):  # i=0 is latest
            dvol_by_day[i] = dvol_by_day.get(i, 0.0) + float(b["c"]) * float(b["v"])
    last5 = statistics.fmean(dvol_by_day[i] for i in range(5))
    last20 = statistics.fmean(dvol_by_day[i] for i in range(lookback))
    return {
        "dollar_volume_5d_avg": last5,
        "dollar_volume_20d_avg": last20,
        "ratio": (last5 / last20) if last20 else None,
    }


def volatility_regime(
    bars_by_symbol: dict[str, list[dict]], indicators_by_symbol: dict[str, dict], lookback: int = DEFAULT_LOOKBACK_SESSIONS,
) -> dict:
    """Average ATR%, now versus `lookback` sessions ago.

    Volatility expanding across a group often precedes a directional
    resolution without saying which way; this reports the expansion, not a
    direction. `indicators_by_symbol` is shared with `breadth` and `at_level`
    -- see `breadth`'s docstring for why it is not recomputed here.
    """
    now_vals, past_vals = [], []
    for symbol, bars in bars_by_symbol.items():
        if len(bars) <= lookback:
            continue
        atr = indicators_by_symbol[symbol]["atr14"]
        closes = _closes(bars)
        now_atr, now_close = _last(atr), closes[-1]
        past_atr, past_close = atr[-1 - lookback], closes[-1 - lookback]
        # `is not None`, not truthiness: a name with a genuinely zero true
        # range over the period is a real (if rare) ATR value, not a missing one.
        if now_atr is not None and now_close:
            now_vals.append(now_atr / now_close * 100.0)
        if past_atr is not None and past_close:
            past_vals.append(past_atr / past_close * 100.0)
    now_avg = statistics.fmean(now_vals) if now_vals else None
    past_avg = statistics.fmean(past_vals) if past_vals else None
    expansion = (now_avg - past_avg) if (now_avg is not None and past_avg is not None) else None
    return {
        "avg_atr_pct_now": now_avg,
        "avg_atr_pct_20d_ago": past_avg,
        "expansion_pct_points": expansion,
    }


def dispersion(bars_by_symbol: dict[str, list[dict]], lookback: int = DEFAULT_LOOKBACK_SESSIONS) -> dict:
    """How much constituents moved together today versus their own recent norm.

    Cross-sectional standard deviation of one day's returns across the group:
    low relative to the group's own trailing average means the day was driven
    by one shared factor (a macro print, a sector-wide rate move) rather than
    company-specific news; high means the day was idiosyncratic -- some names
    moved on their own story while others did not. This is a measured fact
    about today, compared honestly against this group's own recent history,
    not against an arbitrary universal threshold.
    """
    closes_by_symbol = {s: _closes(b) for s, b in bars_by_symbol.items()}
    min_len = min((len(c) for c in closes_by_symbol.values()), default=0)
    if min_len < lookback + 1:
        return {"today_pct": None, "trailing_avg_pct": None, "ratio": None}

    def daily_returns_at(back: int) -> list[float]:
        # back=0 is today's session return; back=k looks k sessions earlier.
        out = []
        for c in closes_by_symbol.values():
            idx = len(c) - 1 - back
            if idx >= 1:
                out.append((c[idx] / c[idx - 1] - 1.0) * 100.0)
        return out

    today_rets = daily_returns_at(0)
    today_disp = statistics.pstdev(today_rets) if len(today_rets) > 1 else None

    trailing = []
    for back in range(1, lookback + 1):
        rets = daily_returns_at(back)
        if len(rets) > 1:
            trailing.append(statistics.pstdev(rets))
    trailing_avg = statistics.fmean(trailing) if trailing else None

    ratio = (today_disp / trailing_avg) if (today_disp is not None and trailing_avg) else None
    return {"today_pct": today_disp, "trailing_avg_pct": trailing_avg, "ratio": ratio}


def at_level(
    bars_by_symbol: dict[str, list[dict]], indicators_by_symbol: dict[str, dict], proximity_atr: float,
) -> dict:
    """Count of constituents currently within `proximity_atr` of a support or
    resistance level -- how many names in the group are at a decision point.

    `indicators_by_symbol` is shared with `breadth` and `volatility_regime` --
    see `breadth`'s docstring for why it is not recomputed here.
    """
    n = at_support = at_resistance = 0
    for symbol, bars in bars_by_symbol.items():
        closes = _closes(bars)
        if not closes:
            continue
        n += 1
        last = closes[-1]
        atr = _last(indicators_by_symbol[symbol]["atr14"])
        # `is None`, not truthiness: a genuinely zero ATR is a real value, and
        # dividing by it below would be the actual failure to guard against.
        if atr is None or atr == 0:
            continue
        levels = indicators.support_resistance(bars)
        for lvl in levels:
            dist_atr = abs(last - lvl["level"]) / atr
            if dist_atr <= proximity_atr:
                if lvl["kind"] == "support":
                    at_support += 1
                else:
                    at_resistance += 1
                break  # one flag per side is enough; do not double-count a name
    return {"n": n, "at_support_count": at_support, "at_resistance_count": at_resistance}


# The six-stage cycle a name's own price structure cycles through, in order.
# "Peak" and "Euphoria/Peak" are adjacent, not synonyms: Euphoria/Peak is the
# blow-off top still accelerating into an extreme; Peak is that same top once
# momentum has visibly rolled over. The loop closes Euphoria/Peak -> Peak.
CYCLE_STAGES = ("Peak", "Correction", "Bottoming", "Recovery", "Extended/Uptrend", "Euphoria/Peak")

# Thresholds behind the euphoria/peak split. Named so they can be tuned without
# hunting through the rule body; there is no universally agreed number here,
# only a reasonable, disclosed one.
EUPHORIA_RSI = 70.0
EUPHORIA_EXTENSION_PCT = 15.0          # % above SMA50
EUPHORIA_NEAR_HIGH_PCT = 5.0           # within this % of the 20-session high
PEAK_NEAR_HIGH_PCT = 10.0              # within this % of the 20-session high
SMA50_SLOPE_LOOKBACK = 10              # sessions back, for "is SMA50 rising"


def _name_cycle_stage(bars: list[dict], a: dict) -> str | None:
    """One name's stage, from its own price structure alone -- no benchmark.

    This is a classification, not a measurement: a rule-based read of where
    price sits relative to its own trend (Weinstein-style stage analysis: SMA50
    vs SMA200 position, whether SMA50 itself is rising, momentum extremity via
    RSI, and proximity to its recent high), not a forecast of what happens
    next. Every threshold is a named constant above, not a magic number here.

    Returns None when there isn't enough history to read all of SMA50, SMA200,
    RSI14, and a 20-session high -- an unclassified name, not a guessed one.
    """
    closes = _closes(bars)
    if len(closes) < 20 + SMA50_SLOPE_LOOKBACK:
        return None
    last = closes[-1]
    sma50_series, sma200_series, rsi_series = a["sma50"], a["sma200"], a["rsi14"]
    sma50, sma200, rsi = _last(sma50_series), _last(sma200_series), _last(rsi_series)
    if sma50 is None or sma200 is None or rsi is None:
        return None
    sma50_then = sma50_series[-1 - SMA50_SLOPE_LOOKBACK]
    if sma50_then is None:
        return None
    sma50_rising = sma50 > sma50_then

    high_20d = max(closes[-20:])
    pct_from_high = (last / high_20d - 1.0) * 100.0       # <= 0
    pct_above_sma50 = (last / sma50 - 1.0) * 100.0

    above_50, above_200 = last > sma50, last > sma200

    if above_50 and above_200:
        if (sma50_rising and (rsi >= EUPHORIA_RSI or pct_above_sma50 >= EUPHORIA_EXTENSION_PCT)
                and pct_from_high >= -EUPHORIA_NEAR_HIGH_PCT):
            return "Euphoria/Peak"
        if not sma50_rising and pct_from_high >= -PEAK_NEAR_HIGH_PCT:
            return "Peak"
        return "Extended/Uptrend"
    if above_50 and not above_200:
        return "Recovery"
    if not above_50 and above_200:
        return "Correction"
    return "Bottoming"                                     # below both


def cycle_stages(bars_by_symbol: dict[str, list[dict]], indicators_by_symbol: dict[str, dict]) -> dict:
    """Per-name cycle stage, a count per stage, and the group's own label.

    The group label is the stage the most names sit in. A tie is reported as a
    tie -- `"A / B"` -- rather than an arbitrary tie-break invented to force a
    single answer nobody actually observed.
    """
    by_symbol: dict[str, str | None] = {}
    for symbol, bars in bars_by_symbol.items():
        by_symbol[symbol] = _name_cycle_stage(bars, indicators_by_symbol[symbol])

    counts = {stage: 0 for stage in CYCLE_STAGES}
    unclassified = []
    for symbol, stage in by_symbol.items():
        if stage is None:
            unclassified.append(symbol)
        else:
            counts[stage] += 1

    classified = sum(counts.values())
    if classified == 0:
        group_label = None
    else:
        # `classified > 0` already guarantees `max(counts.values()) >= 1`, so
        # every stage this comprehension can match has a genuinely positive
        # count -- no separate `> 0` guard needed on top of it.
        top = max(counts.values())
        leaders = [s for s in CYCLE_STAGES if counts[s] == top]
        group_label = " / ".join(leaders)

    return {
        "by_symbol": by_symbol,
        "counts": counts,
        "unclassified": sorted(unclassified),
        "group_label": group_label,
        "n_classified": classified,
    }


def compute_sector_scorecard(
    bars_by_symbol: dict[str, list[dict]],
    benchmark_bars: list[dict] | None,
    *,
    level_proximity_atr: float = 0.5,
) -> dict:
    """Assemble every metric above for one group. Pure function: no I/O, no cache."""
    usable = {s: b for s, b in bars_by_symbol.items() if b}
    missing = sorted(set(bars_by_symbol) - set(usable))
    # Computed once per symbol here and shared with breadth/volatility_regime/
    # at_level, rather than each of those three recomputing the full indicator
    # set (RSI, MACD, Bollinger, Stochastic, OBV, VWAP...) from raw bars on its
    # own -- for a 32-name group that would be 96 full computations to read
    # four numbers per name.
    indicators_by_symbol = {s: indicators.compute_all(b) for s, b in usable.items()}
    return {
        "constituents_used": sorted(usable),
        "constituents_missing": missing,
        "relative_strength": relative_strength(usable, benchmark_bars),
        "breadth": breadth(usable, indicators_by_symbol),
        "new_highs_lows": new_highs_lows(usable),
        "participation": participation(usable),
        "volatility": volatility_regime(usable, indicators_by_symbol),
        "dispersion": dispersion(usable),
        "at_level": at_level(usable, indicators_by_symbol, level_proximity_atr),
        "cycle_stages": cycle_stages(usable, indicators_by_symbol),
    }
