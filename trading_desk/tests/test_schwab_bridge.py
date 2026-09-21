"""Trading Desk coverage for the preview-only Schwab bridge."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import server as srv  # noqa: E402


def test_preview_post_passes_only_supported_order_fields(monkeypatch):
    calls = []

    def fake_helper(*args):
        calls.append(args)
        return {"ok": True, "message": "Preview only"}

    monkeypatch.setattr(srv, "run_schwab_helper", fake_helper)
    code, result = srv.schwab_preview_post(
        {
            "account_last4": "5678",
            "side": "BUY",
            "symbol": "AXTI",
            "quantity": "10",
            "order_type": "LIMIT",
            "limit_price": "30.50",
            "duration": "DAY",
            "ignored": "must not cross the boundary",
        }
    )

    assert code == 200
    assert result["ok"] is True
    assert calls == [
        (
            "preview", "--side", "BUY", "--symbol", "AXTI", "--quantity", "10",
            "--order-type", "LIMIT", "--duration", "DAY", "--account-last4", "5678",
            "--limit-price", "30.50",
        )
    ]


def test_preview_post_requires_complete_material_details(monkeypatch):
    monkeypatch.setattr(
        srv,
        "run_schwab_helper",
        lambda *_args: (_ for _ in ()).throw(AssertionError("helper must not run")),
    )

    code, result = srv.schwab_preview_post({"side": "BUY"})

    assert code == 400
    assert result["ok"] is False
    assert "symbol" in result["error"]


def test_status_reports_preview_mode_not_autonomous_submission(monkeypatch):
    monkeypatch.setattr(srv, "run_schwab_helper", lambda *_args: {"ok": True})

    result = srv.schwab_status()

    assert result["execution_mode"] == "guarded_preview"
    assert result["broker_ready"] is True
    assert result["dashboard_submission_enabled"] is False
