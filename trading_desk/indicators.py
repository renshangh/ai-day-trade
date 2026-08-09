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
