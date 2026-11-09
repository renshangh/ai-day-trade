"""Causality and read-only contracts, using preserved real Coinbase minutes."""
import json
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'trading_desk'))
from trading_desk import btc_data, btc_engine, btc_lab
import server as srv


@pytest.fixture
def minutes():
    path = ROOT / 'reports/btc_structure_2026_11_08/entry_examples/minute_rejection_2026_11_08/COINBASE_BTCUSD_1M_RAW.json'
    return sorted([dict(t=t, low=l, high=h, open=o, close=c, volume=v) for t,l,h,o,c,v in json.loads(path.read_text())], key=lambda b:b['t'])


def position():
    # Hypothetical strategy state, never fabricated market bars.
    return dict(id=1, entry=75650, initial_risk=244, stop=75674.10142857143, t1=76118.18496,
        t2=None, remaining=1., legs=[], peak=76094.99, peak_before_period=76017.37,
        protected_t=1794140000, protected_low=75690, pending_lows=[], entry_period=1794083400,
        gap_exposed=False, context_partial=False)


def engine():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    return btc_engine.Replay(0,9999999999,db)


def test_last_minute_exit_uses_open_observation_before_later_low(minutes):
    e=engine();e.position=position()
    selected=[b for b in minutes if 1794143700<=b['t']<1794144600]
    e.minutes=selected[:14];e.bucket=selected[0]['t'];e.prev={'close':76015.63}
    e.last_minute=selected[13]['t']
    # A stop at a genuine adjacent minute's observed low is later crossed
    # inside 08:29, but the wick is already actionable at its opening observation.
    e.position['stop']=minutes[-1]['low']
    assert selected[-1]['low']<e.position['stop']<selected[-1]['open']
    e.minute(selected[-1])
    assert e.position is None
    assert len(e.trades[0]['legs'])==1
    leg=e.trades[0]['legs'][0]
    assert leg['reason']=='wick_exit_all' and leg['fraction']==1
    assert leg['price']==75955.04
    assert leg['net']==pytest.approx(274.718992)


def test_stop_closes_all_remaining_without_reentering_same_minute(minutes):
    for remaining in (1.,.75):
        e=engine();e.position=position();e.position['remaining']=remaining
        e.position['stop']=76000 # strategy state, not substituted market data
        attempts=[];e.entry=lambda b:attempts.append(b)
        e.minute(minutes[-1])
        assert e.position is None and not attempts
        leg=e.trades[0]['legs'][0]
        assert leg['reason']=='stop' and leg['fraction']==remaining
        assert leg['price']==minutes[-1]['open']


def test_removed_observation_stays_absent_and_flags_open_position(minutes):
    e=engine();e.position=position()
    e.minute(minutes[0]);e.minute(minutes[2])
    assert len(e.minutes)==2 and e.counter['missing_minutes']==1
    assert e.position['gap_exposed']
    bar=btc_engine.aggregate([minutes[0],minutes[2]],900)
    assert bar['observed_minutes']==2
    assert bar['volume']==minutes[0]['volume']+minutes[2]['volume']
    complete=btc_engine.aggregate([b for b in minutes if 1794143700<=b['t']<1794144600],900)
    assert not btc_engine.partial_context([complete],count=1)
    assert btc_engine.partial_context([bar],count=1)
    assert btc_engine.partial_context([complete]) # fewer than fourteen actual buckets


def test_normalization_rejects_missing_values_and_preserves_real_quotes(minutes):
    b=minutes[0]
    row=dict(t=btc_data.iso(b['t']),o=b['open'],h=b['high'],l=b['low'],c=b['close'],v=b['volume'])
    assert len(btc_data.normalize([row],b['t'],b['t']+60))==1
    with pytest.raises(ValueError,match='Duplicate'):
        btc_data.normalize([row,row],b['t'],b['t']+60)
    del row['c']
    with pytest.raises(KeyError):
        btc_data.normalize([row],b['t'],b['t']+60)


def test_lab_rejects_paths_and_unknown_operations(tmp_path):
    lab=btc_lab.Lab(tmp_path)
    for run_id in ('../secret','.env','20261108T194421Z-all/../../.env'):
        with pytest.raises(ValueError):lab.result(run_id)
    with pytest.raises(ValueError):lab.start('place_order')
    with pytest.raises(ValueError):lab.start('backtest',True)
    assert lab.status()['orders_enabled'] is False
    assert not list(tmp_path.glob('**/*'))


@pytest.fixture
def endpoint(monkeypatch):
    calls=[]
    class Lab:
        def status(self):return dict(read_only=True,orders_enabled=False)
        def approved_cases(self):
            calls.append(('cases',));return dict(available=True,cases=[],read_only=True,orders_enabled=False)
        def structure_case(self):
            calls.append(('structure-case',));return dict(available=True,review={},read_only=True,orders_enabled=False)
        def detail(self,run_id,day,trade_id):
            calls.append(('detail',run_id,day,trade_id));return dict(rows=[])
        def start(self,operation,days):
            if operation!='backtest':raise ValueError('Invalid operation')
            calls.append((operation,days));return dict(status='running')
    monkeypatch.setattr(srv.btc_lab,'LAB',Lab())
    http=srv.ThreadingHTTPServer(('127.0.0.1',0),srv.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(http.server_address[1]),calls
    http.shutdown();http.server_close();thread.join(2)


def request(base,body=None,origin=None):
    headers={'Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    req=urllib.request.Request(base+'/api/btc-lab',data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=3) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as exc:return exc.code,json.load(exc)


def test_get_never_starts_work_and_cross_origin_cannot_start_job(endpoint):
    base,calls=endpoint
    assert request(base)==(200,dict(read_only=True,orders_enabled=False))
    assert calls==[]
    assert request(base,{'operation':'backtest'},'https://other.example')[0]==403
    assert request(base,[])[0]==400
    assert request(base,{'operation':'place_order'})[0]==400
    assert calls==[]
    assert request(base,{'operation':'backtest','days':30})[0]==202
    assert calls==[('backtest',30)]


def test_case_endpoint_reads_only_saved_results(endpoint):
    base,calls=endpoint
    with urllib.request.urlopen(base+'/api/btc-lab/cases',timeout=3) as response:
        data=json.load(response)
    assert data['read_only'] and data['orders_enabled'] is False
    assert calls==[('cases',)]


def test_missing_case_file_stays_unavailable_without_starting_jobs(tmp_path,monkeypatch):
    monkeypatch.setattr(btc_lab,'APPROVED_CASES',tmp_path/'absent.json')
    lab=btc_lab.Lab(tmp_path/'empty-store')
    assert lab.approved_cases()==dict(available=False,cases=[],read_only=True,orders_enabled=False)
    assert not (tmp_path/'empty-store').exists()


def test_structure_case_endpoint_only_reads_saved_case(endpoint):
    base,calls=endpoint
    with urllib.request.urlopen(base+'/api/btc-lab/structure-case',timeout=3) as response:
        data=json.load(response)
    assert data['read_only'] and not data['orders_enabled']
    assert calls==[('structure-case',)]


def test_structure_case_missing_file_never_creates_store(tmp_path,monkeypatch):
    monkeypatch.setattr(btc_lab,'STRUCTURE_CASE',tmp_path/'absent.json')
    lab=btc_lab.Lab(tmp_path/'empty')
    assert lab.structure_case()==dict(available=False,read_only=True,orders_enabled=False)
    assert not (tmp_path/'empty').exists()
