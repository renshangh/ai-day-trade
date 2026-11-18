"""HTTP contracts; no market requests or broker orders in this test."""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server as srv


@pytest.fixture
def endpoint(monkeypatch):
    calls = []
    class Discovery:
        def get(self):
            return {'status': 'idle', 'rows': []}
        def chart(self, symbol, asset, scan_id=None):
            source = json.loads((Path(__file__).resolve().parents[2] / 'reports/range_trading/NEAR_DOT_REFRESH.json').read_text())
            from datetime import datetime
            asof = datetime.fromisoformat(source['retrieved_at'].replace('Z', '+00:00')).timestamp()
            observed = srv.range_discovery.normalize(source['products']['NEAR-USD']['candles'], 14400, asof)[-84:]
            calls.append(('chart', symbol, asset, scan_id))
            return dict(symbol=symbol, asset_type=asset, bars=[dict(t=srv.range_discovery.iso(b['start']),
                        o=b['open'],h=b['high'],l=b['low'],c=b['close'],v=b['volume']) for b in observed])
        def start(self, market, threshold, stock_mode='45_day'):
            if stock_mode not in ('45_day', 'two_year'):
                raise ValueError('invalid stock mode')
            if not isinstance(threshold, int) or isinstance(threshold, bool) or not 1 <= threshold <= 100:
                raise ValueError('invalid threshold')
            calls.append((market, threshold, stock_mode))
            return {'status': 'running', 'rows': []}
    monkeypatch.setattr(srv.range_discovery, 'DISCOVERY', Discovery())
    http = srv.ThreadingHTTPServer(('127.0.0.1', 0), srv.Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    base = 'http://127.0.0.1:' + str(http.server_address[1])
    yield base, calls
    http.shutdown()
    http.server_close()
    worker.join(2)


def request(base, body=None, **headers):
    req = urllib.request.Request(base + '/api/range-discovery',
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json', **headers})
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)


def test_opening_reads_status_and_explicit_post_starts_once(endpoint):
    base, calls = endpoint
    assert request(base)[0] == 200
    assert calls == []
    assert request(base, {'market': 'crypto', 'threshold': 15})[0] == 202
    assert calls == [('crypto', 15, '45_day')]


def test_cross_origin_cannot_trigger_provider_scan(endpoint):
    base, calls = endpoint
    assert request(base, {}, Origin='https://unrelated.example')[0] == 403
    assert calls == []


def test_invalid_body_and_threshold_rejected(endpoint):
    base, calls = endpoint
    assert request(base, [])[0] == 400
    assert request(base, {'threshold': 0})[0] == 400
    assert calls == []


def test_two_year_mode_is_explicit_and_bounded(endpoint):
    base, calls = endpoint
    assert request(base, {'market': 'stocks', 'stock_mode': 'two_year'})[0] == 202
    assert calls == [('stocks', 15, 'two_year')]
    assert request(base, {'stock_mode': 'arbitrary'})[0] == 400


def test_chart_endpoint_is_asset_aware_and_rejects_invalid_symbols(endpoint):
    base, calls = endpoint
    with urllib.request.urlopen(base + '/api/range-discovery/chart?symbol=NEAR&asset=crypto&scan=dated') as response:
        result = json.load(response)
    assert result['asset_type'] == 'crypto'
    assert len(result['bars']) == 84 and len(result['indicators']['rsi14']) == 84
    assert calls == [('chart', 'NEAR', 'crypto', 'dated')]
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(base + '/api/range-discovery/chart?symbol=NEAR&asset=invalid')
    assert error.value.code == 400
