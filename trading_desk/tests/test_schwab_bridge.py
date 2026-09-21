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


# ---- DNS-rebinding guard ---------------------------------------------------

class _Headers(dict):
    """Minimal stand-in for the handler's `self.headers.get`."""


def _host_check(host_value):
    """Run Handler._host_is_local against one Host header value."""
    handler = srv.Handler.__new__(srv.Handler)      # no socket, no __init__
    handler.headers = _Headers({"Host": host_value} if host_value is not None else {})
    return srv.Handler._host_is_local(handler)


def test_loopback_hosts_are_accepted():
    """The names a browser actually dials when the user opens the desk."""
    for host in ("127.0.0.1:8799", "localhost:8799", "127.0.0.1", "localhost",
                 "[::1]:8799", None):
        assert _host_check(host) is True, host


def test_rebinding_hosts_are_rejected():
    """A page that points its own hostname at 127.0.0.1 must not read this server.

    Binding to 127.0.0.1 keeps other machines out but does nothing here -- the
    request genuinely arrives on loopback. The Host header is the only thing
    that still carries the name the browser dialled, which is why it is checked.
    `127.0.0.1.nip.io` is the standard rebinding trick: it resolves to 127.0.0.1
    while remaining a foreign origin, so a prefix or substring test on the host
    would wave it through.
    """
    for host in ("evil.example:8799", "attacker.com", "127.0.0.1.nip.io:8799",
                 "localhost.evil.com", "0.0.0.0:8799", "192.168.1.10:8799"):
        assert _host_check(host) is False, host


def test_both_verbs_enforce_the_host_guard():
    """A guard on GET alone would leave the preview POST reachable."""
    import inspect
    for verb in ("do_GET", "do_POST"):
        source = inspect.getsource(getattr(srv.Handler, verb))
        assert "_host_is_local" in source, f"{verb} does not check the Host header"
