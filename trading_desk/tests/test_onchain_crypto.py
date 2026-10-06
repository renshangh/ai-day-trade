"""Offline venue candles only; no fixture data enters live research storage."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import onchain_crypto
import server

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)

def candle(day, value='0.12', volume='123'):
    stamp = int(datetime(2026, 10, day, tzinfo=timezone.utc).timestamp())
    return [stamp, value, value, value, value, value, volume, 3]

def payload(rows):
    return {'error': [], 'result': {'CCUSD': rows, 'last': 123}}

def test_canton_keeps_vendor_values_excludes_current_day_and_preserves_gaps():
    urls=[]
    def fetch(url):
        urls.append(url)
        return payload([candle(3), candle(5), candle(6, '0.20')])
    bars=onchain_crypto.load('CCCAUSD',fetch,NOW)
    assert urls == ['https://api.kraken.com/0/public/OHLC?pair=CCUSD&interval=1440']
    assert [row['t'] for row in bars] == ['2026-10-03','2026-10-05']
    assert bars[-1]['c'] == 0.12 and bars[-1]['v'] == 123

@pytest.mark.parametrize('rows', [[], [candle(6)]])
def test_empty_or_only_forming_candle_returns_empty(rows):
    assert onchain_crypto.load('CCCAUSD',lambda _:payload(rows),NOW)==[]

@pytest.mark.parametrize('row', [candle(5,'nan'),candle(5,'-1'),candle(5,volume='-1'),candle(5)[:6]])
def test_invalid_candle_is_rejected_not_filled(row):
    with pytest.raises(ValueError):
        onchain_crypto.load('CCCAUSD',lambda _:payload([row,candle(6)]),NOW)

def test_duplicate_candles_and_venue_errors_are_rejected():
    for data in [payload([candle(5),candle(5),candle(6)]), {'error':['EQuery:Unknown asset pair']}]:
        with pytest.raises(ValueError):
            onchain_crypto.load('CCCAUSD',lambda _:data,NOW)

def test_server_canton_uses_crypto_feed_and_empty_state(monkeypatch):
    monkeypatch.setattr(server,'_get',lambda url,**kw:payload([candle(5),candle(6)]))
    result=server.get_crypto('cccausd')
    assert result['symbol']=='CCCAUSD' and result['feed']=='Kraken'
    assert result['asset_type']=='crypto'
    monkeypatch.setattr(server,'_get',lambda url,**kw:payload([]))
    assert server.get_crypto('CCCAUSD')['bars']==[]
    assert 'error' in server.get_crypto('CCCAUSD')

def test_public_venue_requests_do_not_include_broker_credentials(monkeypatch):
    requests=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return b'{}'
    def urlopen(req,**kwargs):
        requests.append(req)
        return Response()
    monkeypatch.setattr(server.urllib.request,'urlopen',urlopen)
    monkeypatch.setattr(server,'HEADERS',{'APCA-API-KEY-ID':'offline-test-key'})
    server._get('https://api.kraken.com/0/public/OHLC?pair=CCUSD')
    server._get('https://data.alpaca.markets/v2/stocks/bars')
    assert not requests[0].headers
    assert requests[1].headers['Apca-api-key-id']=='offline-test-key'
