"""Technical indicators, pure stdlib.

Every function returns a list the same length as its input, with `None` in the
warmup region where the indicator is not yet defined. Warmup is never
back-filled, zero-filled, or carried forward -- an undefined indicator value is
reported as undefined (AGENTS.md RULE #1 applies to derived series too, since a
fabricated SMA200 on day 3 is just as misleading as a fabricated bar).
"""

from __future__ import annotations

Series = list[float | None]


def sma(values: list[float], period: int) -> Series:
    """Simple moving average."""
    out: Series = [None] * len(values)
    if period <= 0:
        return out
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= period:
            running -= values[i - period]
        if i >= period - 1:
            out[i] = running / period
    return out


def ema(values: list[float], period: int) -> Series:
    """Exponential moving average, seeded with the first `period` SMA."""
    out: Series = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    k = 2.0 / (period + 1.0)
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    prev = seed
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rolling_std(values: list[float], period: int) -> Series:
    """Population standard deviation over a rolling window."""
    out: Series = [None] * len(values)
    if period <= 1:
        return out
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        mean = sum(window) / period
        var = sum((x - mean) ** 2 for x in window) / period
        out[i] = var ** 0.5
    return out


def bollinger(values: list[float], period: int = 20, mult: float = 2.0) -> dict[str, Series]:
    """Bollinger Bands: middle SMA plus/minus `mult` standard deviations."""
    mid = sma(values, period)
    sd = rolling_std(values, period)
    upper: Series = [None] * len(values)
    lower: Series = [None] * len(values)
    for i in range(len(values)):
        m, s = mid[i], sd[i]
        if m is not None and s is not None:
            upper[i] = m + mult * s
            lower[i] = m - mult * s
    return {"middle": mid, "upper": upper, "lower": lower}


def rsi(values: list[float], period: int = 14) -> Series:
    """Wilder's RSI."""
    out: Series = [None] * len(values)
    if len(values) <= period:
        return out
    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    # gains[j] corresponds to values[j+1]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    for j in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[j]) / period
        avg_loss = (avg_loss * (period - 1) + losses[j]) / period
        idx = j + 1
        out[idx] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
    return out


def macd(
    values: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, Series]:
    """MACD line, signal line, and histogram."""
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    line: Series = [None] * len(values)
    for i in range(len(values)):
        if fast_ema[i] is not None and slow_ema[i] is not None:
            line[i] = fast_ema[i] - slow_ema[i]

    # Signal is an EMA of the MACD line, which itself only starts at `slow - 1`.
    defined = [(i, v) for i, v in enumerate(line) if v is not None]
    sig: Series = [None] * len(values)
    hist: Series = [None] * len(values)
    if len(defined) >= signal:
        sub_vals = [v for _, v in defined]
        sub_sig = ema(sub_vals, signal)
        for (orig_idx, _), s in zip(defined, sub_sig):
            sig[orig_idx] = s
    for i in range(len(values)):
        if line[i] is not None and sig[i] is not None:
            hist[i] = line[i] - sig[i]
    return {"macd": line, "signal": sig, "hist": hist}


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Series:
    """Average True Range (Wilder smoothing)."""
    n = len(closes)
    out: Series = [None] * n
    if n <= period:
        return out
    trs: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    prev = sum(trs[:period]) / period
    out[period] = prev
    for j in range(period, len(trs)):
        prev = (prev * (period - 1) + trs[j]) / period
        out[j + 1] = prev
    return out


def stochastic(
    highs: list[float], lows: list[float], closes: list[float], k_period: int = 14, d_period: int = 3
) -> dict[str, Series]:
    """Stochastic oscillator %K and %D."""
    n = len(closes)
    k: Series = [None] * n
    for i in range(k_period - 1, n):
        hh = max(highs[i - k_period + 1 : i + 1])
        ll = min(lows[i - k_period + 1 : i + 1])
        rng = hh - ll
        # A flat window has no defined position within its range.
        k[i] = None if rng == 0 else (closes[i] - ll) / rng * 100.0

    d: Series = [None] * n
    for i in range(n):
        window = k[max(0, i - d_period + 1) : i + 1]
        if len(window) == d_period and all(x is not None for x in window):
            d[i] = sum(window) / d_period  # type: ignore[arg-type]
    return {"k": k, "d": d}


def obv(closes: list[float], volumes: list[float]) -> Series:
    """On-Balance Volume."""
    n = len(closes)
    if n == 0:
        return []
    out: Series = [None] * n
    running = 0.0
    out[0] = 0.0
    for i in range(1, n):
        if closes[i] > closes[i - 1]:
            running += volumes[i]
        elif closes[i] < closes[i - 1]:
            running -= volumes[i]
        out[i] = running
    return out


def rolling_vwap(
    highs: list[float], lows: list[float], closes: list[float], volumes: list[float], period: int = 20
) -> Series:
    """Rolling volume-weighted average price over `period` bars.

    Daily bars have no intraday session anchor, so this is the rolling-window
    variant rather than a session VWAP.
    """
    n = len(closes)
    out: Series = [None] * n
    typical = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]
    for i in range(period - 1, n):
        vol = sum(volumes[i - period + 1 : i + 1])
        if vol <= 0:
            continue  # no volume means no defined VWAP; leave it None
        pv = sum(typical[j] * volumes[j] for j in range(i - period + 1, i + 1))
        out[i] = pv / vol
    return out


def swing_points(
    highs: list[float], lows: list[float], k: int = 5
) -> tuple[list[int], list[int]]:
    """Indices of swing highs and swing lows.

    A swing high is a bar whose high is the highest across the +/-k bars around
    it and strictly above its immediate neighbours. The strict-neighbour test
    stops a flat plateau from emitting a pivot on every bar of the plateau.
    """
    n = len(highs)
    ph: list[int] = []
    pl: list[int] = []
    if n < 2 * k + 1:
        return ph, pl
    for i in range(k, n - k):
        window_hi = highs[i - k : i + k + 1]
        if highs[i] >= max(window_hi) and highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            ph.append(i)
        window_lo = lows[i - k : i + k + 1]
        if lows[i] <= min(window_lo) and lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            pl.append(i)
    return ph, pl


def support_resistance(
    bars: list[dict],
    k: int = 5,
    tolerance_pct: float | None = None,
    min_touches: int = 2,
    max_per_side: int = 4,
    max_distance_pct: float | None = None,
) -> list[dict]:
    """Horizontal support/resistance levels derived from swing pivots.

    Pivot highs and lows are clustered by price; a cluster that price turned at
    more than once becomes a level. Every level is a real price the market
    actually reversed at -- nothing is drawn at a round number or a projection.

    Selection is anchored to the latest close and balanced across both sides.
    Ranking purely by touch count is useless in practice: a stock that ran from
    $2 to $88 has its most-touched clusters down at $2, and a name in a
    persistent uptrend returns nothing but support. So levels further than
    `max_distance_pct` from the last close are dropped, and up to `max_per_side`
    are kept above and below it.

    `touches` counts the clustered pivots. `tests` additionally counts bars whose
    range came within tolerance of the level, which is the better measure of how
    contested a level is.

    Each level carries the dates it was first and last tested, so a stale level
    can be told from a live one.
    """
    if len(bars) < 2 * k + 2:
        return []

    highs = [float(b["h"]) for b in bars]
    lows = [float(b["l"]) for b in bars]
    closes = [float(b["c"]) for b in bars]
    # Callers pass either raw Alpaca bars (full ISO timestamps) or normalized
    # ones; levels only ever report a session, so keep just the date part.
    dates = [str(b["t"])[:10] for b in bars]

    # A level is a zone, and the zone's width has to scale with how much the
    # instrument moves. A fixed 1.5% band is roughly right for NVDA (ATR ~3%) and
    # far too tight for AXTI (ATR ~12%), where it finds no levels at all because
    # every genuine retest lands outside the band. Both the cluster width and the
    # "near enough to trade against" horizon are therefore derived from ATR.
    ref = closes[-1]
    atr_series = atr(highs, lows, closes, 14)
    recent_atr = next((v for v in reversed(atr_series) if v is not None), None)
    atr_pct = (recent_atr / ref * 100.0) if (recent_atr and ref > 0) else 2.0
    if tolerance_pct is None:
        tolerance_pct = min(max(0.6 * atr_pct, 1.0), 8.0)
    if max_distance_pct is None:
        max_distance_pct = min(max(8.0 * atr_pct, 15.0), 60.0)

    ph, pl = swing_points(highs, lows, k)
    pivots = [(highs[i], dates[i]) for i in ph] + [(lows[i], dates[i]) for i in pl]
    if not pivots:
        return []
    pivots.sort(key=lambda p: p[0])

    # Greedy clustering: extend a cluster while the next pivot sits within
    # tolerance of the cluster's running mean.
    clusters: list[list[tuple[float, str]]] = [[pivots[0]]]
    for price, date in pivots[1:]:
        current = clusters[-1]
        mean = sum(p for p, _ in current) / len(current)
        if abs(price - mean) <= mean * tolerance_pct / 100.0:
            current.append((price, date))
        else:
            clusters.append([(price, date)])

    levels: list[dict] = []
    for cl in clusters:
        if len(cl) < min_touches:
            continue
        level = sum(p for p, _ in cl) / len(cl)
        band = level * tolerance_pct / 100.0
        # A "test" is any bar whose range reached into the level's band.
        tests = sum(1 for i in range(len(bars)) if lows[i] - band <= level <= highs[i] + band)
        level_dates = sorted(d for _, d in cl)
        levels.append({
            "level": level,
            "touches": len(cl),
            "tests": tests,
            "first_touch": level_dates[0],
            "last_touch": level_dates[-1],
        })

    last_close = ref
    if last_close <= 0:
        return []

    def keep(side: list[dict]) -> list[dict]:
        # Nearest first. Proximity, not touch count, decides what a trader can
        # act on -- ranking by touches buried NVDA's level 4% away under ones
        # 13-24% away that happened to have been hit more often. Touch and test
        # counts ride along on each level so strength is still visible.
        side.sort(key=lambda x: abs(x["level"] - last_close))
        return side[:max_per_side]

    near = [
        lv for lv in levels
        if abs(lv["level"] / last_close - 1.0) * 100.0 <= max_distance_pct
    ]
    resistance = keep([lv for lv in near if lv["level"] > last_close])
    support = keep([lv for lv in near if lv["level"] <= last_close])

    for lv in resistance:
        lv["kind"] = "resistance"
    for lv in support:
        lv["kind"] = "support"

    out = resistance + support
    for lv in out:
        lv["distance_pct"] = (lv["level"] / last_close - 1.0) * 100.0
    out.sort(key=lambda x: x["level"], reverse=True)
    return out


def compute_all(bars: list[dict]) -> dict:
    """Compute the full indicator set for a list of Alpaca daily bars."""
    closes = [float(b["c"]) for b in bars]
    highs = [float(b["h"]) for b in bars]
    lows = [float(b["l"]) for b in bars]
    volumes = [float(b["v"]) for b in bars]

    bb = bollinger(closes, 20, 2.0)
    macd_vals = macd(closes)
    stoch = stochastic(highs, lows, closes)

    return {
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "sma200": sma(closes, 200),
        "ema12": ema(closes, 12),
        "ema26": ema(closes, 26),
        "bb_upper": bb["upper"],
        "bb_middle": bb["middle"],
        "bb_lower": bb["lower"],
        "rsi14": rsi(closes, 14),
        "macd": macd_vals["macd"],
        "macd_signal": macd_vals["signal"],
        "macd_hist": macd_vals["hist"],
        "atr14": atr(highs, lows, closes, 14),
        "stoch_k": stoch["k"],
        "stoch_d": stoch["d"],
        "obv": obv(closes, volumes),
        "vwap20": rolling_vwap(highs, lows, closes, volumes, 20),
        "vol_sma20": sma(volumes, 20),
    }
