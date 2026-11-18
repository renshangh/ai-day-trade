"""Actual native SOL/ETH observations, frozen controls, and read-only delivery."""
import copy
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts,STORE
from trading_desk.crypto_transfer import STUDIES,make_engine,sha
from trading_desk.crypto_transfer_view import CryptoView
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay


@pytest.fixture(scope='module')
def saved():
    view=CryptoView();folder,s=view.current()
    if not s or s['status']!='complete':pytest.skip('Requires authorized saved SOL/ETH transfer study')
    return view,folder,s


def test_exact_frozen_constructors_and_reproduced_btc_controls(saved):
    view,folder,s=saved;assert all(s['btc_controls_reproduced'].values())
    assert s['start']=='2026-10-10T00:00:00Z' and s['end']=='2026-11-09T00:00:00Z'
    ids=read(STORE/'releases/0.2/REGISTRY.json')['0.2']['run_ids']
    for model in ('0.1','E1','E2'):
        db=sqlite3.connect(':memory:')
        try:
            e=make_engine(model,ts(s['start']),ts(s['end']),db)
            assert type(e) is (FailedReboundReplay if model=='0.1' else EarlySequentialReplay)
            assert e.consume_entry_history and not e.b1_independent_hold
            assert e.cfg.one_way_friction_bps==2 and e.cfg.first_sale_fraction==.25
        finally:db.close()
        baseline=read(STORE/'releases/0.2/results'/ids[model]/'result.json')
        new=view.result(folder,'BTC/USD',model)
        assert new['metrics']==baseline['metrics']
        for a,b in zip(baseline['trades'],new['trades'],strict=True):
            for key in ('entry','entry_time','initial_stop','t1','t2','net','net_r','status','remaining'):
                assert a[key]==b[key]


def test_source_pages_and_gaps_reconcile_without_default_bars(saved):
    view,folder,s=saved
    for asset in s['assets']:
        q=s['source_quality'][asset];p=folder/'data'/(asset.replace('/','_')+'_MINUTES.jsonl.gz')
        assert sha(p)==q['archive_sha256']
        with gzip.open(p,'rt') as f:bars=[json.loads(x) for x in f]
        assert len(bars)==q['observed'] and all(b['t']>a['t'] for a,b in zip(bars,bars[1:]))
        assert len(bars)+len(q['missing'])==q['expected']
        assert set(q['missing']).isdisjoint(b['t'] for b in bars)
        data=view.snapshot(asset)
        row=next(x for x in data['summaries'] if x['symbol']==asset)
        assert row['coverage']['test_expected']==43200
        assert row['coverage']['test_observed']+row['coverage']['test_missing']==43200
    for page in read(folder/'data/SOURCES.json')['pages']:
        payload=gzip.decompress((folder/'data'/page['file']).read_bytes())
        assert __import__('hashlib').sha256(payload).hexdigest()==page['raw_sha256']


def test_all_leg_fractions_costs_marks_and_gap_groups_reconcile(saved):
    view,folder,s=saved
    for asset in s['assets']:
        for model in s['models']:
            r=view.result(folder,asset,model);summary=r['summary']
            for field in ('realized_net','unrealized_net','normalized_10000_realized','normalized_10000_unrealized','trades'):
                assert summary['all'][field]==pytest.approx(summary['no_flagged_gap'][field]+summary['flagged_gap_or_context'][field])
            for p in r['trades']:
                assert sum(l['fraction'] for l in p['legs'])+p['remaining']==pytest.approx(1)
                assert p['realized_leg_net']==pytest.approx(sum(l['net'] for l in p['legs']))
                assert p['normalized_10000_realized_net']==pytest.approx(p['realized_leg_net']/p['entry']*10000)
                if p['remaining']:
                    assert p['status']=='open' and p['net'] is None and not p.get('exit_time')
                    expected=p['remaining']*(p['mark_price']-p['entry'])-p['remaining']*(p['mark_price']+p['entry'])*.0002
                    assert p['unrealized_net_reference']==pytest.approx(expected)
                else:assert p['net']==pytest.approx(sum(l['net'] for l in p['legs']))
                for l in p['legs']:
                    assert p['entry_time']<=l['time_utc']<s['end']
                    assert l['cost']==pytest.approx(l['fraction']*(l['price']+p['entry'])*.0002)
            assert not r['orders_enabled']


def test_real_prefix_reproduces_sol_entry_and_eth_remains_open(saved):
    view,folder,s=saved;r=view.result(folder,'SOL/USD','0.1');p=r['trades'][0]
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=make_engine('0.1',ts(s['start']),ts(s['end']),db)
    try:
        with gzip.open(folder/'data/SOL_USD_MINUTES.jsonl.gz','rt') as f:
            for line in f:
                b=json.loads(line)
                if b['t']>ts(p['entry_time']):break
                e.minute(b)
        current=e.position or e.trades[-1]
        for key in ('entry_time','entry','initial_stop','t1','references'):assert current[key]==p[key]
    finally:db.close()
    for model in s['models']:
        eth=view.result(folder,'ETH/USD',model)
        assert eth['summary']['all']['open']==1 and eth['trades'][-1]['remaining']>0


def test_safe_exports_and_read_only_http(saved,monkeypatch):
    view,_,s=saved
    for symbol,model,name in [('all','all','TRADES.csv'),('SOL/USD','E1','SIGNALS.csv'),('ETH/USD','E2','PROTECTION.csv')]:
        assert view.export(symbol,model,name).is_file()
    with pytest.raises(ValueError):view.snapshot('../.env')
    with pytest.raises(ValueError):view.snapshot('SOL/USD','bad')
    with pytest.raises(ValueError):view.export('all','all','../../.env')
    import threading,urllib.request,urllib.error
    from http.server import ThreadingHTTPServer
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    from trading_desk import crypto_transfer_view
    monkeypatch.setattr(crypto_transfer_view,'CRYPTO_VIEW',view)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/crypto-transfer?symbol=ETH/USD&model=E1') as resp:
            d=json.load(resp);assert d['model']=='E1' and not d['orders_enabled']
        req=urllib.request.Request(base+'/api/crypto-transfer',data=b'{"operation":"submit"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as err:urllib.request.urlopen(req)
        assert err.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
