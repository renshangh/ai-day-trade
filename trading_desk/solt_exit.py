"""Account-specific SOLT recovery-exit planning from real market observations.

The planner is advisory only. It does not fetch data or create orders. Missing
position, price, ATR, support, or aligned SOL data stays unavailable rather than
being estimated or carried forward.
"""

from __future__ import annotations

import math

RECOVERY_ATR_HIGH = 0.25
EXTENSION_ATR_LOW = 0.50
EXTENSION_ATR_HIGH = 1.00
BETA_LOOKBACK = 20


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _bar_map(data: dict) -> dict[str, dict]:
    return {
        str(bar.get("t")): bar for bar in (data.get("bars") or [])
        if bar.get("t") and _finite(bar.get("c")) is not None
    }


def _beta(solt_by_day: dict[str, dict], sol_by_day: dict[str, dict], dates: list[str]) -> tuple[float | None, int]:
    pairs = []
    window = dates[-(BETA_LOOKBACK + 1):]
    for previous, current in zip(window, window[1:]):
        solt_prev = _finite(solt_by_day[previous].get("c"))
        solt_now = _finite(solt_by_day[current].get("c"))
        sol_prev = _finite(sol_by_day[previous].get("c"))
        sol_now = _finite(sol_by_day[current].get("c"))
        if None in (solt_prev, solt_now, sol_prev, sol_now) or min(solt_prev, solt_now, sol_prev, sol_now) <= 0:
            continue
        x = sol_now / sol_prev - 1
        y = solt_now / solt_prev - 1
        if abs(x) > 1e-9:
            pairs.append((x, y))
    denominator = sum(x * x for x, _ in pairs)
    beta = sum(x * y for x, y in pairs) / denominator if denominator > 0 and len(pairs) >= 8 else None
    # Withhold a non-positive or extreme fit instead of forcing the fund's
    # stated 2x objective into the observed relationship.
    if beta is None or not 0.5 <= beta <= 4.0:
        return None, len(pairs)
    return beta, len(pairs)


def build(position: dict, solt: dict, sol: dict) -> dict:
    """Build a staged recovery plan for one account's SOLT position."""
    quantity = _finite(position.get("quantity"))
    average = _finite(position.get("average_price"))
    if quantity is None or quantity <= 0 or average is None or average <= 0:
        return {"available": False, "reason": "SOLT quantity or average cost is unavailable"}

    solt_by_day, sol_by_day = _bar_map(solt), _bar_map(sol)
    dates = sorted(set(solt_by_day) & set(sol_by_day))
    if not dates:
        return {"available": False, "reason": "aligned SOLT and SOL sessions are unavailable"}
    reference_date = dates[-1]
    solt_close = _finite(solt_by_day[reference_date].get("c"))
    sol_close = _finite(sol_by_day[reference_date].get("c"))
    solt_bars = solt.get("bars") or []
    bar_index = next((i for i, bar in enumerate(solt_bars) if str(bar.get("t")) == reference_date), None)
    atr_series = (solt.get("indicators") or {}).get("atr14") or []
    atr = _finite(atr_series[bar_index]) if bar_index is not None and bar_index < len(atr_series) else None
    if solt_close is None or sol_close is None or atr is None or atr <= 0:
        return {"available": False, "reason": "aligned close or SOLT ATR is unavailable"}

    supports = sorted(
        value for level in (solt.get("levels") or [])
        if level.get("kind") == "support"
        and (value := _finite(level.get("level"))) is not None
        and value < solt_close
    )
    support = supports[-1] if supports else None

    whole_shares = math.floor(quantity)
    first = math.floor(whole_shares * 0.25)
    second = math.floor(whole_shares * 0.25)
    runner = whole_shares - first - second
    beta, observations = _beta(solt_by_day, sol_by_day, dates)
    sol_equivalent = None
    if beta is not None:
        required_solt_return = average / solt_close - 1
        projected = sol_close * (1 + required_solt_return / beta)
        if math.isfinite(projected) and projected > 0:
            sol_equivalent = projected

    recovery_low = average
    recovery_high = average + RECOVERY_ATR_HIGH * atr
    extension_low = average + EXTENSION_ATR_LOW * atr
    extension_high = average + EXTENSION_ATR_HIGH * atr
    if support is not None and solt_close < support:
        state = "support_break_review"
    elif solt_close < recovery_low:
        state = "recovery_wait"
    elif solt_close <= recovery_high:
        state = "first_trim_review"
    else:
        state = "extension_review"

    return {
        "available": True,
        "mode": "advisory",
        "symbol": "SOLT",
        "state": state,
        "quantity": quantity,
        "whole_shares": whole_shares,
        "average_cost": round(average, 6),
        "reference_date": reference_date,
        "solt_reference_close": round(solt_close, 4),
        "sol_reference_close": round(sol_close, 4),
        "atr14": round(atr, 4),
        "support": round(support, 2) if support is not None else None,
        "stages": [
            {"name": "Recovery trim", "shares": first,
             "low": round(recovery_low, 2), "high": round(recovery_high, 2),
             "gate": "30-minute SOLT close above average cost and above session VWAP"},
            {"name": "Extension trim", "shares": second,
             "low": round(extension_low, 2), "high": round(extension_high, 2),
             "gate": "first trim confirmed and SOLT holds above the recovery zone"},
            {"name": "Runner", "shares": runner, "low": None, "high": None,
             "gate": "trail below the latest confirmed 30-minute higher low or session VWAP"},
        ],
        "sol_equivalent": {
            "price": round(sol_equivalent, 2) if sol_equivalent is not None else None,
            "observed_beta": round(beta, 3) if beta is not None else None,
            "observations": observations,
            "scope": "single-session equivalent; not a multi-day forecast",
        },
        "notes": [
            "Average cost is a recovery reference, not guaranteed break-even after fees or taxes.",
            "SOLT resets leverage daily, so SOL price alone cannot determine a future SOLT price across multiple sessions.",
            "Support is a review trigger, not an entered stop or authorization to sell at a loss.",
        ],
    }
