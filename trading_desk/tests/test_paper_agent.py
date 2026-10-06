"""Paper recommendation rules: deterministic, bounded, and no fake levels."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import paper_agent as agent  # noqa: E402
import server  # noqa: E402


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


def test_missing_support_is_reported_not_fabricated():
    data = stock()
    data["levels"] = [{"kind": "resistance", "level": 120.0}]
    result = agent.recommend("AXTI", data)
    assert result == {
        "symbol": "AXTI", "available": False,
        "reason": "support is unavailable",
    }


def test_price_discovery_exit_is_explicit_atr_projection():
    """No resistance may produce a labelled projection, never a fake level."""
    data = stock()
    data["bars"] = [{"c": 105.0, "h": 108.0}]
    data["levels"] = [{"kind": "support", "level": 100.0}]
    result = agent.recommend("HYPEUSD", data)
    assert result["available"] is True
    assert result["exit_basis"] == "atr_projection_above_observed_high"
    assert result["exit_range"] == {"low": 113.0, "high": 118.0}
    assert result["basis"]["resistance"] is None
    assert result["basis"]["observed_high"] == 108.0


def test_unpermitted_symbol_is_rejected():
    result = agent.recommend("TSLA", stock())
    assert result["available"] is False
    assert result["reason"] == "symbol is not permitted"


def test_entry_and_exit_states_only_fire_inside_their_bands():
    assert agent.recommend("COHR", stock(last=102.0))["state"] == "entry_review"
    assert agent.recommend("LITE", stock(last=118.0))["state"] == "exit_review"


def test_crcl_and_hypeusd_are_permitted_for_human_review():
    """The expanded sleeve deliberately covers one stock and one crypto pair."""
    assert agent.recommend("CRCL", stock())["available"] is True
    assert agent.recommend("HYPEUSD", stock())["available"] is True


def test_hypeusd_uses_alpaca_crypto_bars(monkeypatch):
    """HYPEUSD must not drift onto the Schwab stock or CoinGecko data paths."""
    def fake_get(url, retries=4):
        assert "/v1beta3/crypto/us/bars?" in url
        assert "HYPE%2FUSD" in url
        return {"bars": {"HYPE/USD": [
            {"t": "2026-09-20T00:00:00Z", "o": 40, "h": 42, "l": 39, "c": 41, "v": 1000},
            {"t": "2026-09-21T00:00:00Z", "o": 41, "h": 44, "l": 40, "c": 43, "v": 1200},
        ]}}

    monkeypatch.setattr(server, "_get", fake_get)
    result = server.get_crypto("HYPEUSD")
    assert result["feed"] == "Alpaca Crypto"
    assert result["feed_note"] == "daily HYPE/USD OHLC and volume"
    assert [bar["c"] for bar in result["bars"]] == [41.0, 43.0]


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
