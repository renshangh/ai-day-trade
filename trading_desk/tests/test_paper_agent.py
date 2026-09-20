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
