"""Paper recommendation rules: deterministic, bounded, and no fake levels."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import paper_agent as agent  # noqa: E402


def stock(last=105.0, atr=10.0):
    return {
        "bars": [{"c": last}],
        "indicators": {"atr14": [atr]},
        "levels": [
            {"kind": "support", "level": 100.0},
            {"kind": "resistance", "level": 120.0},
        ],
    }


def test_recommendation_uses_support_resistance_and_atr():
    result = agent.recommend("FN", stock())
    assert result["available"] is True
    assert result["entry_range"] == {"low": 100.0, "high": 103.5}
    assert result["exit_range"] == {"low": 116.5, "high": 120.0}
    assert result["risk_reference"] == 95.0
    assert result["state"] == "wait"


def test_missing_level_is_reported_not_fabricated():
    data = stock()
    data["levels"] = [{"kind": "support", "level": 100.0}]
    result = agent.recommend("AXTI", data)
    assert result == {
        "symbol": "AXTI", "available": False,
        "reason": "support or resistance is unavailable",
    }


def test_unpermitted_symbol_is_rejected():
    result = agent.recommend("TSLA", stock())
    assert result["available"] is False
    assert result["reason"] == "symbol is not permitted"


def test_entry_and_exit_states_only_fire_inside_their_bands():
    assert agent.recommend("COHR", stock(last=102.0))["state"] == "entry_review"
    assert agent.recommend("LITE", stock(last=118.0))["state"] == "exit_review"


def test_empty_atr_series_is_unavailable_not_an_indexerror():
    """`atr14: []` used to raise IndexError instead of returning unavailable.

    `.get("atr14", [None])[-1]` applies its default only when the key is
    *absent*; an empty list is a real value, so `[-1]` raised. The route's broad
    `except Exception` then surfaced that to the dashboard as
    `reason: "list index out of range"` -- indistinguishable from a genuine data
    gap. `indicators.compute_all([])` returns exactly that empty list, so this
    was reachable for any permitted symbol whose bars failed to load.
    """
    for label, data in (
        ("no bars", {"bars": [], "indicators": {"atr14": []}, "levels": []}),
        ("bars present", {"bars": [{"c": 100.0}], "indicators": {"atr14": []}, "levels": []}),
        ("indicators missing", {"bars": [{"c": 100.0}], "levels": []}),
        ("atr all None", {"bars": [{"c": 100.0}], "indicators": {"atr14": [None, None]}, "levels": []}),
    ):
        result = agent.recommend("FN", data)
        assert result["available"] is False, label
        assert result["reason"] == "last price or ATR is unavailable", label


def test_unavailable_reasons_never_leak_internal_error_text():
    """Every unavailable path names a market-data reason a reader can act on.

    The bug above reached the UI as "list index out of range". A reason quoting
    a Python exception means an internal fault is being reported as missing data.
    """
    leaky = ("index out of range", "NoneType", "Traceback", "KeyError", "AttributeError")
    for data in (
        {"bars": [], "indicators": {"atr14": []}, "levels": []},
        {"bars": [{"c": 100.0}], "indicators": {"atr14": [2.0]}, "levels": []},
        {"bars": [{"c": 100.0}], "indicators": {"atr14": [2.0]},
         "levels": [{"kind": "support", "level": 95.0}]},
    ):
        reason = agent.recommend("FN", data).get("reason", "")
        assert not any(bad in reason for bad in leaky), f"leaked internal text: {reason!r}"
