"""Cash-ticket owner scope. Synthetic account/trade fixtures, no live requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import schwab_trade as trade
import server

ENTRIES = [{"accountNumber": "11113652", "hashValue": "private-taxable"},
           {"accountNumber": "11112840", "hashValue": "private-roth"}]


@pytest.fixture
def broker(monkeypatch):
    monkeypatch.setattr(trade, "account_numbers", lambda: ENTRIES)
    # Any attempted broker preview or order is a test failure.
    monkeypatch.setattr(trade, "broker_post", lambda *a, **k: pytest.fail("must be read-only"))
    monkeypatch.setattr(trade, "_account_positions", lambda account: {"positions": [
        {"symbol": "TEST", "average_price": "20.00"}]})


def scan_events(monkeypatch, events):
    calls = []
    def read(symbol, *, accounts, strict):
        calls.append((symbol, accounts, strict))
        suffixes = {"***" + a["accountNumber"][-4:] for a in accounts}
        return [event for event in events if event["account"] in suffixes]
    monkeypatch.setattr(trade, "recent_symbol_trades", read)
    return calls


def test_buy_checks_only_3652_sales_not_retirement_sales(broker, monkeypatch):
    calls = scan_events(monkeypatch, [{"side": "SELL", "account": "***2840"}])
    result = trade.cash_ticket_wash_check("BUY", "TEST", "18.00")
    assert result["possible"] is False
    assert calls == [("TEST", [ENTRIES[0]], True)]
    assert result["protected_account"] == "3652"
    assert result["read_only"] and not result["execution_ready"]
    assert not result["tax_determination"]
    scan_events(monkeypatch, [{"side": "SELL", "account": "***3652"}])
    result = trade.cash_ticket_wash_check("BUY", "TEST", "18.00")
    assert result["possible"] is True
    assert "Realized tax-lot loss is unavailable" in result["message"]


def test_3652_sell_checks_replacement_buys_in_all_linked_accounts(broker, monkeypatch):
    calls = scan_events(monkeypatch, [{"side": "BUY", "account": "***2840"}])
    result = trade.cash_ticket_wash_check("SELL", "TEST", "18.00")
    assert calls == [("TEST", ENTRIES, True)]
    assert result["possible"] is True
    assert result["matched_trades"] == [{"side": "BUY", "account": "***2840"}]
    assert "***3652" in result["message"]
    # A prospective taxable loss still needs forward-window protection.
    scan_events(monkeypatch, [])
    assert trade.cash_ticket_wash_check("SELL", "TEST", "18.00")["possible"] is True


def test_missing_taxable_coverage_or_basis_cannot_approve(broker, monkeypatch):
    scan_events(monkeypatch, [])
    monkeypatch.setattr(trade, "_account_positions", lambda _: {"positions": []})
    assert trade.cash_ticket_wash_check("SELL", "TEST", "18.00")["possible"] is None
    monkeypatch.setattr(trade, "account_numbers", lambda: [ENTRIES[1]])
    with pytest.raises(trade.TradeError, match="coverage"):
        trade.cash_ticket_wash_check("BUY", "TEST", "18.00")


def test_profit_estimate_still_labels_selected_lot_review(broker, monkeypatch):
    scan_events(monkeypatch, [])
    result = trade.cash_ticket_wash_check("SELL", "TEST", "25.00")
    assert result["possible"] is False
    assert "Selected tax-lot basis still needs review" in result["message"]


@pytest.mark.parametrize("basis", [None, 0, -1, "NaN", "Infinity", "invalid"])
def test_invalid_basis_is_unknown_not_a_zero_cost_profit(broker, monkeypatch, basis):
    scan_events(monkeypatch, [])
    monkeypatch.setattr(trade, "_account_positions", lambda _: {"positions": [
        {"symbol": "TEST", "average_price": basis}]})
    assert trade.cash_ticket_wash_check("SELL", "TEST", "25.00")["possible"] is None


def test_scoped_history_reads_only_requested_accounts_and_rejects_missing_evidence(broker, monkeypatch):
    now = datetime(2026, 11, 13, 17, tzinfo=timezone.utc)
    rows = [{"time": "2026-11-10T17:00:00Z", "netAmount": 180,
             "transferItems": [{"instrument": {"symbol": "TEST", "assetType": "EQUITY"},
                                "amount": 10, "price": 18}]}]
    calls = []
    def api(path, params):
        calls.append(path)
        return rows
    monkeypatch.setattr(trade.schwab_api, "api", api)
    result = trade.recent_symbol_trades("TEST", now=now, accounts=[ENTRIES[0]], strict=True)
    assert calls == ["/trader/v1/accounts/private-taxable/transactions"]
    assert result[0]["account"] == "***3652"
    assert "private-taxable" not in json.dumps(result) and "11113652" not in json.dumps(result)
    rows[0]["time"] = None
    with pytest.raises(trade.TradeError, match="Incomplete"):
        trade.recent_symbol_trades("TEST", now=now, accounts=[ENTRIES[0]], strict=True)


def test_route_skips_other_sells_and_masks_helper_failures(monkeypatch):
    calls = []
    def helper(*args):
        calls.append(args)
        return {"ok": False, "message": "private-taxable 11113652"}
    monkeypatch.setattr(server, "run_schwab_helper", helper)
    code, result = server.schwab_cash_wash_get("SELL", "TEST", "18.00", "2840,1638")
    assert code == 200 and result["skipped"]
    assert not calls
    for side, accounts in [("BUY", "2840"), ("SELL", "3652,2840")]:
        code, result = server.schwab_cash_wash_get(side, "TEST", "18.00", accounts)
        assert code == 503 and not result["ok"]
        assert "11113652" not in json.dumps(result)
        assert calls[-1] == ("cash-ticket-wash-check", "--side", side,
                             "--symbol", "TEST", "--limit-price", "18.00")
    count = len(calls)
    assert server.schwab_cash_wash_get("SELL", "TEST", "18.00", "")[0] == 400
    assert server.schwab_cash_wash_get("BUY", "bad symbol", "18.00", "2840")[0] == 400
    assert len(calls) == count


def test_http_check_is_no_store_and_cannot_accept_order_post(monkeypatch):
    from http.server import ThreadingHTTPServer
    import threading
    import urllib.request
    import urllib.error
    calls = []
    def helper(*args):
        calls.append(args)
        return {"ok": True, "possible": False, "read_only": True, "execution_ready": False}
    monkeypatch.setattr(server, "run_schwab_helper", helper)
    http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{http.server_port}/api/schwab/cash-wash-check?side=BUY&symbol=TEST&price=18.00&accounts=2840"
    try:
        with urllib.request.urlopen(url) as response:
            assert response.headers["Cache-Control"] == "no-store"
            assert not json.load(response)["execution_ready"]
        assert len(calls) == 1
        request = urllib.request.Request(url, data=b'{}', headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 404
        assert len(calls) == 1
    finally:
        http.shutdown()
        http.server_close()
        worker.join()
