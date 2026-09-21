"""Deterministic, paper-only trade proposals for the human-in-the-loop desk.

The module does not fetch data, submit orders, or simulate fills. It converts
real chart measurements supplied by the server into inspectable price bands.
Missing measurements produce an unavailable result, never an estimated level.
"""

from __future__ import annotations

import math

PERMITTED_SYMBOLS = ("FN", "AXTI", "COHR", "LITE")
ENTRY_ATR_WIDTH = 0.35
EXIT_ATR_WIDTH = 0.35
STOP_ATR_BUFFER = 0.50


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def recommend(symbol: str, stock: dict) -> dict:
    """Return a paper proposal derived only from supplied market measurements."""
    symbol = str(symbol).upper()
    if symbol not in PERMITTED_SYMBOLS:
        return {"symbol": symbol, "available": False, "reason": "symbol is not permitted"}

    bars = stock.get("bars") or []
    last = _finite(bars[-1].get("c")) if bars else None
    atr = _finite((stock.get("indicators") or {}).get("atr14", [None])[-1])
    levels = stock.get("levels") or []
    supports = sorted(
        value for level in levels
        if level.get("kind") == "support" and (value := _finite(level.get("level"))) is not None
        and last is not None and value < last
    )
    resistances = sorted(
        value for level in levels
        if level.get("kind") == "resistance" and (value := _finite(level.get("level"))) is not None
        and last is not None and value > last
    )
    if last is None or atr is None or atr <= 0:
        return {"symbol": symbol, "available": False, "reason": "last price or ATR is unavailable"}
    if not supports or not resistances:
        return {"symbol": symbol, "available": False, "reason": "support or resistance is unavailable"}

    support, resistance = supports[-1], resistances[0]
    entry_low = support
    entry_high = support + ENTRY_ATR_WIDTH * atr
    exit_high = resistance
    exit_low = resistance - EXIT_ATR_WIDTH * atr
    stop = max(0.01, support - STOP_ATR_BUFFER * atr)

    if last <= stop:
        state = "risk_review"
    elif entry_low <= last <= entry_high:
        state = "entry_review"
    elif exit_low <= last <= exit_high:
        state = "exit_review"
    else:
        state = "wait"

    return {
        "symbol": symbol,
        "available": True,
        "mode": "paper",
        "state": state,
        "last": round(last, 4),
        "atr14": round(atr, 4),
        "entry_range": {"low": round(entry_low, 2), "high": round(entry_high, 2)},
        "exit_range": {"low": round(exit_low, 2), "high": round(exit_high, 2)},
        "risk_reference": round(stop, 2),
        "basis": {
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "entry_width_atr": ENTRY_ATR_WIDTH,
            "exit_width_atr": EXIT_ATR_WIDTH,
            "stop_buffer_atr": STOP_ATR_BUFFER,
        },
    }
