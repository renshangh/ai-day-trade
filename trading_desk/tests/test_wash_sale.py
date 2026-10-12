"""Deterministic tests for the advisory wash-sale classifier."""

from __future__ import annotations

import sys
from datetime import timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import schwab_trade  # noqa: E402


def order(side: str, price: str = "90.00") -> schwab_trade.OrderRequest:
    return schwab_trade.normalize_order(
        side=side,
        symbol="LITE",
        quantity=10,
        order_type="LIMIT",
        limit_price=price,
        duration="DAY",
    )


def test_buy_warns_after_recent_same_symbol_sale():
    result = schwab_trade.evaluate_wash_sale(
        order("BUY"),
        [{"account": "***3652", "side": "SELL", "symbol": "LITE", "quantity": 5,
          "price": 95, "trade_date": "2026-10-01"}],
        None,
    )

    assert result["possible"] is True
    assert result["level"] == "warning"
    assert result["matched_trades"][0]["account"] == "***3652"


def test_loss_sell_warns_after_cross_account_replacement_buy():
    result = schwab_trade.evaluate_wash_sale(
        order("SELL", "90.00"),
        [{"account": "***6434", "side": "BUY", "symbol": "LITE", "quantity": 4,
          "price": 92, "trade_date": "2026-10-05"}],
        {"average_price": 100, "quantity": 10, "market_value": 900},
    )

    assert result["estimated_loss"] is True
    assert result["possible"] is True
    assert "replacement buys" in result["message"]


def test_loss_sell_warns_about_future_thirty_day_window_without_prior_buy():
    result = schwab_trade.evaluate_wash_sale(
        order("SELL", "90.00"), [],
        {"average_price": 100, "quantity": 10, "market_value": 900},
    )

    assert result["estimated_loss"] is True
    assert result["possible"] is True
    assert "30 calendar days after" in result["message"]


def test_sell_above_average_cost_is_not_certified_tax_safe():
    result = schwab_trade.evaluate_wash_sale(
        order("SELL", "110.00"), [],
        {"average_price": 100, "quantity": 10, "market_value": 1100},
    )

    assert result["possible"] is False
    assert result["tax_determination"] is False
    assert "not tax clearance" in result["message"]


def test_trade_time_without_offset_is_treated_as_utc():
    parsed = schwab_trade._trade_time("2026-10-01T12:00:00")

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
