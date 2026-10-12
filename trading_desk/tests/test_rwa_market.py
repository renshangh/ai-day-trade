"""Offline tests of market-screen semantics; test observations never enter runtime files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rwa_market as rwa


def observation(coin_id, cap=200_000_000, volume=20_000_000, **changes):
    return {'id':coin_id, 'symbol':coin_id, 'name':coin_id, 'market_cap':cap,
            'total_volume':volume, 'current_price':1, 'last_updated':'2026-10-12T14:00:00Z', **changes}


def test_screen_requires_both_metrics_and_source_timestamp():
    rows=[observation('chainlink'), observation('ondo-finance',volume=0),
          observation('stellar',cap=None), observation('quant-network',volume=float('nan')),
          observation('algorand',last_updated=None), observation('syrup',cap=99_000_000),
          observation('pax-gold',volume=9_000_000), observation('buidl')]
    result=rwa.build(rows)
    assert [c['id'] for c in result['coins']]==['chainlink']
    assert result['coins'][0]['market_cap']==200_000_000
    assert result['coins'][0]['volume_24h']==20_000_000


def test_rank_balances_cap_with_volume_and_preserves_values():
    result=rwa.build([observation('chainlink',cap=900_000_000,volume=10_000_000),
                      observation('stellar',cap=700_000_000,volume=50_000_000),
                      observation('ondo-finance',cap=100_000_000,volume=80_000_000)])
    assert [c['id'] for c in result['coins']]==['chainlink','stellar','ondo-finance']
    assert [(c['cap_rank'],c['volume_rank']) for c in result['coins']]==[(1,3),(2,2),(3,1)]
    assert result['coins'][2]['volume_24h']==80_000_000


def test_top_ten_duplicates_and_missing_price():
    result=rwa.build([observation(i,current_price=None) for i in rwa.ROLES]+[observation('chainlink')])
    assert len(result['coins'])==10
    assert result['eligible_count']==len(rwa.ROLES)
    assert all(c['price'] is None for c in result['coins'])


def test_cache_and_failed_refresh_remain_explicitly_dated(monkeypatch):
    monkeypatch.setattr(rwa,'_cached',None)
    monkeypatch.setattr(rwa,'_cached_at',0)
    success=rwa.get_market(fetch=lambda:[observation('chainlink')])
    def fail(): raise ValueError('Provider unavailable')
    assert rwa.get_market(fetch=fail) is success
    failed=rwa.get_market(force=True,fetch=fail)
    assert failed['stale'] is True
    assert failed['coins']==success['coins']
    assert failed['fetched_at']==success['fetched_at']


def test_empty_provider_response_is_not_reported_as_fresh(monkeypatch):
    monkeypatch.setattr(rwa,'_cached',None)
    result=rwa.get_market(force=True,fetch=lambda:[])
    assert result['stale'] is True
    assert result['warning']


def test_volume_can_outweigh_market_cap_order():
    result=rwa.build([observation('chainlink',cap=900_000_000,volume=10_000_000),
                      observation('stellar',cap=700_000_000,volume=80_000_000),
                      observation('ondo-finance',cap=100_000_000,volume=50_000_000)])
    assert result['coins'][0]['id']=='stellar'


def test_invalid_records_do_not_discard_valid_observations():
    result=rwa.build([None, 'bad record', observation('chainlink',symbol=None),
                      observation('stellar',last_updated='2026-10-12'), observation('ondo-finance')])
    assert [c['id'] for c in result['coins']]==['ondo-finance']


def test_provider_failure_is_briefly_cached(monkeypatch):
    monkeypatch.setattr(rwa,'_cached',None)
    monkeypatch.setattr(rwa,'_cached_at',0)
    calls=[]
    def fail():
        calls.append(1)
        raise ValueError('Unavailable')
    failed=rwa.get_market(fetch=fail)
    assert rwa.get_market(fetch=fail) is failed
    assert len(calls)==1
    monkeypatch.setattr(rwa,'_cached_at',rwa.time.monotonic()-31)
    assert rwa.get_market(fetch=fail)['stale']
    assert len(calls)==2


def test_http_market_refresh_and_sector_board_only(monkeypatch):
    import http.client
    import json
    import threading
    from http.server import ThreadingHTTPServer
    import server

    calls=[]
    def market(force=False):
        calls.append(force)
        return {'coins': [], 'stale': True, 'warning': 'Test provider unavailable'}
    monkeypatch.setattr(server.rwa_market,'get_market',market)
    httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=httpd.serve_forever,daemon=True)
    thread.start()
    def request(path):
        conn=http.client.HTTPConnection('127.0.0.1',httpd.server_address[1],timeout=3)
        try:
            conn.request('GET',path)
            response=conn.getresponse()
            assert response.status==200
            return response.read().decode()
        finally:
            conn.close()
    try:
        assert json.loads(request('/api/rwa-market'))['stale']
        assert json.loads(request('/api/rwa-market?force=1'))['stale']
        assert calls==[False,True]
        home=request('/')
        assert 'rwa-market-main' not in home and 'id="rwa"' not in home
        assert '/rwa_market.js' not in home and '/rwa_market.css' not in home
        assert 'href="#rwa"' not in home
        board=request('/board')
        assert 'rwa-market-board' in board
        assert '/rwa_market.js' in board and '/rwa_market.css' in board
        assert 'RwaMarket' in request('/rwa_market.js')
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=3)
