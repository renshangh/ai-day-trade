"""Cash-sizing invariants. Synthetic ACCOUNT fixtures, never market bars."""
from datetime import datetime, timedelta, timezone
import json
import threading

import pytest
from scripts import schwab_cash as c

NOW = datetime(2026, 11, 10, 15, tzinfo=timezone.utc)


def account(kind="CASH", **fields):
    return {"accountNumber": "11112840", "type": kind,
            "currentBalances": {"cashBalance": 100, **fields}}


def buy(status="WORKING", **fields):
    return {"status": status, "orderType": "LIMIT", "price": 10,
            "remainingQuantity": 3,
            "orderLegCollection": [{"instruction": "BUY", "quantity": 8}], **fields}


def test_available_funds_never_become_cash_and_missing_orders_block():
    row = c.account_cash(account("MARGIN", availableFunds=999999, buyingPower=999999), [])
    assert row["cash_ceiling_cents"] == 10000
    assert row["verified_cash_cents"] is None
    assert c.account_cash(account(cashAvailableForTrading=100), None)["cash_ceiling_cents"] is None
    assert c.account_cash(account(cashAvailableForTrading=100), [{}])["error"]


def test_partial_fill_reserve_not_original_quantity_or_double_subtraction():
    row = c.account_cash(account(cashAvailableForTrading=70), [buy()])
    assert row["buy_commitments_cents"] == 3000
    assert row["verified_cash_cents"] == 7000  # NOT40, and not original8*10.
    assert c.account_cash(account(cashAvailableForTrading=100), [buy()])["verified_cash_cents"] == 7000


def test_unbounded_buy_and_missing_quantities_fail_closed_children_reserved():
    assert c.order_commitments([buy(orderType="MARKET")])[0] is None
    assert c.order_commitments([buy(orderLegCollection=[{"instruction":"UNKNOWN"}])])[0] is None
    assert c.order_commitments([buy(remainingQuantity=None)])[0] is None
    assert c.order_commitments([buy("FILLED", childOrderStrategies=[buy("AWAITING_PARENT_ORDER")])])[0] == 3000
    assert c.order_commitments([buy("CANCELED")])[0] == 0
    assert c.order_commitments([buy()] * 3000)[0] is None


def payload():
    return {"as_of": NOW.isoformat(), "accounts": [
        c.account_cash(account(cashAvailableForTrading=100), []),
        {**c.account_cash(account("MARGIN"), []), "account": "3652"}]}


def test_whole_share_rounding_percentages_and_confirmation_capped_by_live_cash():
    for percent, expected in [(25,1),(50,2),(75,4),(100,5)]:
        result = c.size(payload(), ["2840"], "18", percent, now=NOW)
        assert result["rows"][0]["quantity"] == expected
    result = c.size(payload(), ["3652"], "18", 50, {"3652":"90.00"}, now=NOW)
    assert result["rows"][0]["quantity"] == 2
    assert c.size(payload(), ["3652"], "18", 50, now=NOW)["rows"][0]["quantity"] is None
    with pytest.raises(ValueError):
        c.size(payload(), ["3652"], "18", 50, {"3652":"100.01"}, now=NOW)
    assert not result["execution_ready"]


@pytest.mark.parametrize("price", ["0", "-1", "NaN", "Infinity", "0.001"])
def test_bad_price_rejected(price):
    with pytest.raises(ValueError): c.size(payload(), ["2840"], price, 50, now=NOW)


def test_stale_future_missing_selection_and_unknown_account_rejected():
    for current in [NOW + timedelta(seconds=31), NOW - timedelta(seconds=1)]:
        with pytest.raises(ValueError): c.size(payload(), ["2840"], "18", 50, now=current)
    for selected in [[], ["2840","2840"], ["9999"]]:
        with pytest.raises(ValueError): c.size(payload(), selected, "18", 50, now=NOW)
    with pytest.raises(ValueError): c.size(payload(), ["2840"], "18", 10, now=NOW)


def test_one_book_read_and_parallel_order_requests_only_gets(monkeypatch, tmp_path):
    barrier = threading.Barrier(2, timeout=3)
    calls = []
    mapping = [{"accountNumber":"11112840","hashValue":"test-hash-a"},
               {"accountNumber":"11113652","hashValue":"test-hash-b"}]
    def fake(path, params=None):
        calls.append(path)
        if path.endswith("accountNumbers"): return mapping
        if path == "/trader/v1/accounts":
            return [{"securitiesAccount":account(cashAvailableForTrading=100)},
                    {"securitiesAccount":{**account("MARGIN"),"accountNumber":"11113652"}}]
        assert path.endswith("/orders")
        barrier.wait()  # Sequential requests would time out.
        return []
    monkeypatch.setattr(c.api,"load_env",lambda _:None)
    monkeypatch.setattr(c.api,"access_token",lambda:None)
    monkeypatch.setattr(c.api,"api",fake)
    monkeypatch.setattr(c,"SNAPSHOT_PATH",tmp_path/"snapshot.json")
    result = c.fetch_snapshot()
    assert calls.count("/trader/v1/accounts") == 1
    serialized = json.dumps(result)
    assert "11112840" not in serialized and "test-hash" not in serialized
    assert len(result["accounts"]) == 2
    assert result["read_only"] and not result["execution_ready"]


def test_refresh_failure_never_returns_cached_success(monkeypatch):
    monkeypatch.setattr(c,"_cached",{"as_of":datetime.now(timezone.utc).isoformat()})
    monkeypatch.setattr(c,"fetch_snapshot",lambda:(_ for _ in ()).throw(ValueError("failed")))
    with pytest.raises(ValueError): c.snapshot(force=True)
    assert c._cached is None


def holding(symbol="AXTI", long="100", short="0"):
    return {"instrument":{"symbol":symbol,"assetType":"EQUITY"},
            "longQuantity":long, "shortQuantity":short}


def sell(**fields):
    return {"status":"WORKING", "orderType":"LIMIT", "remainingQuantity":30,
            "orderLegCollection":[{"instruction":"SELL", "quantity":40,
                "instrument":{"assetType":"EQUITY", "symbol":"AXTI"}}], **fields}


def test_sells_use_long_holdings_less_remaining_orders_and_children_not_cash():
    row = c.account_cash({**account("MARGIN"), "positions":[holding()]},
                         [sell(childOrderStrategies=[sell(remainingQuantity=10)])])
    assert row["verified_cash_cents"] is None
    assert row["holdings"]["AXTI"]["sell_reserved_quantity"] == "40"
    assert row["holdings"]["AXTI"]["available_to_sell_quantity"] == "60"
    data = {"as_of":NOW.isoformat(), "accounts":[row]}
    result = c.size(data,["2840"],"43",100,now=NOW,side="sell",symbol="AXTI")
    assert result["rows"][0]["quantity"] == 60
    assert result["rows"][0]["estimated_proceeds_cents"] == 258000
    assert not result["execution_ready"]
    assert c.account_holdings({"positions":[holding()]},[sell(status="CANCELED")])["holdings"]["AXTI"]["available_to_sell_quantity"] == "100"


def test_fractional_sells_floor_and_short_missing_or_ambiguous_positions_block():
    row = c.account_cash({**account(),"positions":[holding(long="125.5")]},[])
    data={"as_of":NOW.isoformat(), "accounts":[row]}
    assert c.size(data,["2840"],"43",50,now=NOW,side="sell",symbol="AXTI")["rows"][0]["quantity"] == 62
    for positions, orders in [(None,[]),([holding()],None),([holding()],[sell(remainingQuantity=None)]),
                               ([holding()],[sell(status="UNKNOWN")]),([holding(),holding()],[])]:
        row=c.account_cash({**account(),"positions":positions},orders)
        assert row["holdings_error"]
    row=c.account_cash({**account(),"positions":[holding(short=1)]},[])
    assert row["holdings"]["AXTI"]["available_to_sell_quantity"] is None
    row=c.account_cash({**account(),"positions":[holding()]},[sell(remainingQuantity=101)])
    assert row["holdings"]["AXTI"]["available_to_sell_quantity"] == "0"
    for symbol in [None,"", "bad symbol"]:
        with pytest.raises(ValueError):
            c.size(data,["2840"],"43",50,now=NOW,side="sell",symbol=symbol)


def test_cash_page_and_snapshot_route_are_read_only_and_mask_failures(monkeypatch):
    import sys
    from pathlib import Path
    import urllib.request
    from http.server import ThreadingHTTPServer
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import server
    force = []
    def fake_snapshot(**kwargs):
        force.append(kwargs["force"])
        return {"ok":True,"accounts":[],"execution_ready":False}
    monkeypatch.setattr(server.schwab_cash,"snapshot",fake_snapshot)
    http = ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
    thread = threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base = f"http://127.0.0.1:{http.server_port}"
    try:
        with urllib.request.urlopen(base+"/cash-ticket") as response:
            assert b"No orders are sent" in response.read()
        with urllib.request.urlopen(base+"/api/schwab/cash-snapshot?force=1") as response:
            assert not json.load(response)["execution_ready"]
            assert response.headers["Cache-Control"] == "no-store"
        assert force == [True]
        # This endpoint must never accept an order-shaped POST.
        request = urllib.request.Request(base+"/api/schwab/cash-snapshot", data=b'{}',
                                         headers={"Content-Type":"application/json"})
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 404
    finally:
        http.shutdown();http.server_close();thread.join()
