"""Actual frozen-stream experiment: causality, complete deltas and read-only UI."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.refined_entry_view import VIEW,BOOKS,GROUPS
from trading_desk.btc_data import read,ts
from trading_desk.btc_live import verify_rules
from trading_desk.refined_entries import PROTOCOL


def test_controls_source_and_locked_protocol_are_verified():
    folder,s=VIEW.current();assert s['status']=='complete' and s['protocol']==PROTOCOL
    assert len(s['controls_reproduced'])==4 and all(s['controls_reproduced'].values())
    assert s['rule_hashes']==verify_rules()
    for p,h in s['code_hashes'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    for p,h in read(folder/'PRESERVED_BEFORE.json').items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h


def test_full_sequences_keep_risk_exits_and_stage_known_at_entry():
    folder,s=VIEW.current()
    for symbol,model in BOOKS:
        old=read(folder/symbol.replace('/','_')/model/'original/result.json');new=read(folder/symbol.replace('/','_')/model/'refined/result.json')
        original={p['entry_time']:p for p in old['trades']}
        signals={p['trade_id']:p for p in new['signals'] if p['decision']=='entry'}
        for p in new['trades']:
            sig=signals[p['id']];setup=sig['setup_evidence'];now=ts(p['entry_time'])
            assert p['net']==pytest.approx(sum(l['net'] for l in p['legs']))
            assert sum(l['fraction'] for l in p['legs'])+p['remaining']==pytest.approx(1)
            assert sig['initial_stop']==pytest.approx(sig['references']['l1']['price']-.25*sig['atr'])
            if p['entry_rule']=='B1':
                hold=setup['refined_first_hold'];assert hold['t']>=setup['d']['known_at']
                assert hold['t']+900==now//900*900 and hold['observed_minutes']==15
                assert sig['b1_confirmation']['passed'] and not setup.get('refined_retired')
            elif p['entry_rule']=='B2':
                assert setup['rebound']['t']+900<=now and setup['hl']['known_at']<=now
                assert setup['hl']['time']>=setup['rebound']['t']+900
            else:assert p['p1']['passed'] and p['p1']['p1_low_count']>=4
            # Retained exact entries with the same recorded risk retain all exits;
            # labels can change without inventing a separate profit change.
            a=original.get(p['entry_time'])
            if a and all(a[k]==p[k] for k in ('entry','initial_stop','t1','t2')):assert a['legs']==p['legs']


def test_change_deltas_and_gap_partitions_reconcile_every_book():
    for symbol,model in BOOKS:
        groups={}
        for group in GROUPS:
            d=VIEW.snapshot(symbol,model,group);b=next(x for x in d['summaries'] if x['symbol']==symbol and x['model']==model)
            assert sum(c['delta_realized'] for c in d['changes'])==pytest.approx(b['delta_realized'])
            assert sum(c['delta_normalized_10000'] for c in d['changes'])==pytest.approx(b['delta_normalized_10000'])
            assert not d['orders_enabled'] and not d['live_promoted']
            groups[group]=b
        assert groups['all']['delta_realized']==pytest.approx(groups['no_flagged_gap']['delta_realized']+groups['flagged_gap_or_context']['delta_realized'])


def test_safe_exports_and_http_no_mutation(monkeypatch):
    import server
    for bad in ('../STUDY.json','../../.env'):
        with pytest.raises(ValueError):VIEW.export('all','E1','refined',bad)
    with pytest.raises(ValueError):VIEW.snapshot('SOL/USD','E2')
    from http.server import ThreadingHTTPServer
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/refined-entry') as r:d=json.load(r)
        assert d['available'] and len(d['summaries'])==4 and not d['orders_enabled']
        req=urllib.request.Request(base+'/api/refined-entry',data=b'{"operation":"start"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
