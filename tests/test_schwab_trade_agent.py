"""Regression tests for the chat-only Schwab order safety boundary.

All Schwab responses are deterministic API fixtures. These tests never connect
to a broker and never submit a live order.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import schwab_trade  # noqa: E402


@pytest.fixture
def isolated_previews(tmp_path, monkeypatch):
    preview_dir = tmp_path / "schwab_order_previews"
    monkeypatch.setattr(schwab_trade, "PREVIEW_DIR", preview_dir)
    monkeypatch.setattr(
        schwab_trade,
        "account_numbers",
        lambda: [{"accountNumber": "12345678", "hashValue": "account-hash"}],
    )
    return preview_dir


def make_order(side="BUY"):
    return schwab_trade.normalize_order(
        side=side,
        symbol="AXTI",
        quantity="10",
        order_type="limit",
        duration="day",
        limit_price="30.50",
    )


def accepted_preview(*_args, **_kwargs):
    return 200, {"orderValidationResult": {"accepts": [{"message": "accepted"}]}}, {}


def test_preview_is_private_and_does_not_place(isolated_previews, monkeypatch):
    calls = []

    def fake_post(path, payload, *, submitting):
        calls.append((path, payload, submitting))
        return accepted_preview()

    monkeypatch.setattr(schwab_trade, "broker_post", fake_post)

    result = schwab_trade.preview_order(make_order(), "5678")

    assert result["ok"] is True
    assert result["message"] == "Preview only. No live order has been submitted."
    assert calls[0][0].endswith("/previewOrder")
    assert calls[0][2] is False
    assert result["confirmation_phrase"] == "PLACE BUY 10 AXTI LIMIT 30.50 DAY IN ACCOUNT 5678"
    record = isolated_previews / f"{result['preview_token']}.json"
    assert record.is_file()
    assert stat.S_IMODE(record.stat().st_mode) == 0o600


def test_exact_confirmation_is_required_and_preview_stays_active_on_mismatch(
    isolated_previews, monkeypatch
):
    monkeypatch.setattr(schwab_trade, "broker_post", accepted_preview)
    result = schwab_trade.preview_order(make_order(), "5678")

    with pytest.raises(schwab_trade.TradeError, match="did not exactly match"):
        schwab_trade.place_order(result["preview_token"], "yes")

    assert (isolated_previews / f"{result['preview_token']}.json").is_file()


def test_confirmed_preview_is_submitted_once(isolated_previews, monkeypatch):
    calls = []

    def fake_post(path, payload, *, submitting):
        calls.append((path, submitting))
        if submitting:
            return (
                201,
                {},
                {"Location": "https://api.schwabapi.com/trader/v1/accounts/x/orders/42"},
            )
        return accepted_preview()

    monkeypatch.setattr(schwab_trade, "broker_post", fake_post)
    result = schwab_trade.preview_order(make_order(), "5678")
    placed = schwab_trade.place_order(result["preview_token"], result["confirmation_phrase"])

    assert placed["submitted"] is True
    assert placed["order_id"] == "42"
    assert calls == [
        ("/trader/v1/accounts/account-hash/previewOrder", False),
        ("/trader/v1/accounts/account-hash/orders", True),
    ]
    with pytest.raises(schwab_trade.TradeError, match="missing or has already been consumed"):
        schwab_trade.place_order(result["preview_token"], result["confirmation_phrase"])


def test_sell_is_blocked_if_position_shrinks_after_preview(isolated_previews, monkeypatch):
    quantities = iter((schwab_trade.Decimal("10"), schwab_trade.Decimal("4")))
    monkeypatch.setattr(schwab_trade, "long_quantity", lambda *_args: next(quantities))
    calls = []

    def fake_post(path, payload, *, submitting):
        calls.append((path, submitting))
        return accepted_preview()

    monkeypatch.setattr(schwab_trade, "broker_post", fake_post)
    result = schwab_trade.preview_order(make_order("SELL"), "5678")

    with pytest.raises(schwab_trade.TradeError, match="blocked after recheck"):
        schwab_trade.place_order(result["preview_token"], result["confirmation_phrase"])

    assert calls == [("/trader/v1/accounts/account-hash/previewOrder", False)]


def test_tampered_saved_payload_is_never_submitted(isolated_previews, monkeypatch):
    calls = []

    def fake_post(path, payload, *, submitting):
        calls.append((path, submitting))
        return accepted_preview()

    monkeypatch.setattr(schwab_trade, "broker_post", fake_post)
    result = schwab_trade.preview_order(make_order(), "5678")
    record_path = isolated_previews / f"{result['preview_token']}.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["payload"]["orderLegCollection"][0]["quantity"] = 999
    schwab_trade.write_private_json(record_path, record)

    with pytest.raises(schwab_trade.TradeError, match="no longer matches its preview"):
        schwab_trade.place_order(result["preview_token"], result["confirmation_phrase"])

    assert calls == [("/trader/v1/accounts/account-hash/previewOrder", False)]


def test_schwab_preview_rejects_never_create_placeable_record(isolated_previews, monkeypatch):
    monkeypatch.setattr(
        schwab_trade,
        "broker_post",
        lambda *_args, **_kwargs: (
            200,
            {"orderValidationResult": {"rejects": [{"message": "insufficient funds"}]}},
            {},
        ),
    )

    result = schwab_trade.preview_order(make_order(), "5678")

    assert result["ok"] is False
    assert "preview_token" not in result
    assert not list(isolated_previews.glob("*.json"))


def test_market_gtc_and_rounded_limit_prices_are_rejected():
    with pytest.raises(schwab_trade.TradeError, match="market orders must use DAY"):
        schwab_trade.normalize_order(
            side="BUY",
            symbol="AXTI",
            quantity="1",
            order_type="MARKET",
            duration="GTC",
            limit_price=None,
        )

    with pytest.raises(schwab_trade.TradeError, match="at most 2 decimal places"):
        schwab_trade.normalize_order(
            side="BUY",
            symbol="AXTI",
            quantity="1",
            order_type="LIMIT",
            duration="DAY",
            limit_price="30.505",
        )


def test_live_positions_are_masked_and_missing_values_stay_missing(monkeypatch):
    # Position serialization is deterministic and must not depend on a
    # developer's local Schwab credentials or OAuth token.
    monkeypatch.setattr(schwab_trade, "status", lambda: {"ok": True})
    monkeypatch.setattr(
        schwab_trade,
        "resolve_account",
        lambda _last4: {"accountNumber": "12345678", "hashValue": "secret-hash"},
    )
    monkeypatch.setattr(
        schwab_trade,
        "account_details",
        lambda _hash: {
            "type": "CASH",
            "currentBalances": {"liquidationValue": 1000.0},
            "positions": [
                {
                    "instrument": {"symbol": "AXTI", "assetType": "EQUITY"},
                    "longQuantity": 10,
                    "shortQuantity": 0,
                    "averagePrice": 30.5,
                    # Schwab omitted marketValue and P/L; the bridge must not
                    # invent them from quantity or any cached journal value.
                }
            ],
        },
    )

    result = schwab_trade.positions("5678")

    assert result["account"] == "***5678"
    assert "secret-hash" not in json.dumps(result)
    assert result["positions"][0]["quantity"] == 10.0
    assert result["positions"][0]["market_value"] is None
    assert result["positions"][0]["open_profit_loss"] is None
