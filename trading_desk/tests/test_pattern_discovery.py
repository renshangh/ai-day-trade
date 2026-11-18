"""Real archived observations and causal entry evidence, no synthetic price bars."""
import copy
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts
from trading_desk.pattern_library import HOME,features,match,create_library,FEATURES
from trading_desk.pattern_discovery import PatternReplay,Agent,validate_watchlist,configure,snapshot
from trading_desk.btc_p1 import P1BaselineReplay
from scripts.btc_structure_retest import Config


@pytest.fixture(scope='module')
def archived(tmp_path_factory):
    active=read(STORE/'p1_studies/ACTIVE.json')
    if not active:pytest.skip('Requires the authorized saved P1 reference study')
    lib=create_library(tmp_path_factory.mktemp('pattern-library')/'LIBRARY.json')
    r=read(ROOT/lib['source_result'])
    rows=[]
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rt') as f:
        for line in f:
            t,o,h,l,c,v,n,vw=json.loads(line);rows.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    return lib,r,rows


def test_ten_unique_baseline_winners_and_losing_controls(archived):
    lib,r,_=archived
    assert len(lib['examples'])==10 and len(lib['counterexamples'])==17
    clean=sorted([p for p in r['trades'] if p['net']>0],key=lambda p:(-p['net'],p['entry_time']))[:10]
    assert [e['source_trade_id'] for e in lib['examples']]==[p['id'] for p in clean]
    assert all(e['route']=='B1' for e in lib['examples'])
    assert lib['examples'][2]['quality_flag'] and not lib['examples'][2]['matching_enabled']
    assert sum(e['matching_enabled'] for e in lib['examples'])==9
    assert all(e['outcome']['net']<0 for e in lib['counterexamples'])


def test_matcher_never_reads_future_outcomes_and_rejects_losing_self_match(archived):
    lib,r,_=archived
    s=next(s for s in r['signals'] if s['trade_id']==2)
    v=features(s);assert set(v)==set(FEATURES)
    altered=copy.deepcopy(lib)
    for e in altered['examples']+altered['counterexamples']:e['outcome']={'net':999999999}
    assert match(v,lib)==match(v,altered)
    for e in lib['counterexamples']:assert not match(e['features'],lib)['accepted']
    future=copy.deepcopy(s);future['setup_evidence']['d']['known_at']=ts(s['time_utc'])+1
    with pytest.raises(ValueError,match='unconfirmed'):features(future)
    far={k:v[k]*100000 for k in v};assert not match(far,lib)['accepted']


def test_real_entry_freshness_gate_and_original_exit_inheritance(archived):
    lib,r,rows=archived
    for name in ('close_part','additional_exit_candidates'):
        assert getattr(PatternReplay,name) is getattr(P1BaselineReplay,name)
    target=lib['examples'][0];entry=ts(target['entry_time'])
    engines=[]
    try:
        for delay in (0,181):
            db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
            e=PatternReplay(ts(r['start']),ts(r['end']),db,Config(first_sale_fraction=.25,resistance_mode='major1h'),symbol='BTC/USD',library=lib)
            engines.append(e)
            for b in rows:
                if b['t']>entry:break
                e.received_at=b['t']+60+delay;e.minute(b)
        good,bad=engines
        assert good.position and good.position['entry_time']==target['entry_time']
        assert good.position['entry']==target['entry'] and good.position['initial_stop']==target['initial_stop']
        assert not any(d['accepted'] for d in bad.decisions)
        assert bad.position is None and any('fresh' in d['reason'] for d in bad.decisions)
    finally:
        for e in engines:e.db.close()


def test_worker_warmup_empty_response_and_recovery_keep_observed_rows_only(tmp_path,archived):
    lib,_,rows=archived;save(tmp_path/'LIBRARY.json',lib)
    actual=[b for b in rows if b['t']>=ts(lib['training_end'])-3600]
    class Source:
        def bars(self,symbol,start,end,folder):return [b for b in actual if start<=b['t']<end] if symbol=='BTC/USD' else []
    now=ts(lib['training_end'])+600
    a=Agent(tmp_path,source=Source(),clock=lambda:now)
    try:
        a.setup();a.config['watchlist']=['BTC/USD','SPY'];save(tmp_path/'CONFIG.json',a.config)
        a.cycle();s=read(tmp_path/'STATUS.json');btc,stock=s['symbols']
        assert btc['observed_minutes']==len(actual) and not btc['open_position']
        assert stock['observed_minutes']==0 and stock['last'] is None
        assert a.db.execute('SELECT count(*) FROM bars').fetchone()[0]==len(actual)
        a.cycle();assert a.db.execute('SELECT count(*) FROM bars').fetchone()[0]==len(actual)
        previous=read(tmp_path/'STATUS.json')['symbols']
        config=read(tmp_path/'CONFIG.json');config['enabled']=False;save(tmp_path/'CONFIG.json',config)
        a.cycle();assert read(tmp_path/'STATUS.json')['symbols']==previous
        config['enabled']=True;save(tmp_path/'CONFIG.json',config)
    finally:a.close()
    b=Agent(tmp_path,source=Source(),clock=lambda:now+60)
    try:
        b.cycle();assert not read(tmp_path/'STATUS.json')['symbols'][0]['closed_trades']
    finally:b.close()


def test_configuration_does_not_allow_broker_orders_or_remove_held_symbol(tmp_path,archived):
    lib,_,_=archived;save(tmp_path/'LIBRARY.json',lib)
    save(tmp_path/'CONFIG.json',{'watchlist':['BTC/USD','LITE'],'enabled':True})
    save(tmp_path/'STATUS.json',{'symbols':[{'symbol':'LITE','open_position':{'remaining':1}}]})
    with pytest.raises(ValueError,match='open paper'):configure(['SPY'],True,tmp_path)
    assert configure(['LITE','QQQ'],False,tmp_path)['watchlist']==['BTC/USD','LITE','QQQ']
    with pytest.raises(ValueError):validate_watchlist(['https://example.com'])
    with pytest.raises(ValueError):validate_watchlist(['SPY']*25)
    with pytest.raises(ValueError):configure(['LITE'],1,tmp_path)


def test_local_http_only_allows_scan_settings_and_get_has_no_fetch(tmp_path,archived,monkeypatch):
    import threading,urllib.request,urllib.error
    from http.server import ThreadingHTTPServer
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    from trading_desk import pattern_discovery as module
    lib,_,_=archived;save(tmp_path/'LIBRARY.json',lib)
    save(tmp_path/'CONFIG.json',{'watchlist':['BTC/USD','SPY'],'enabled':True})
    monkeypatch.setattr(module,'snapshot',lambda:snapshot(tmp_path))
    monkeypatch.setattr(module,'configure',lambda symbols,enabled:configure(symbols,enabled,tmp_path))
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/pattern-discovery') as r:assert len(json.load(r)['library']['examples'])==10
        for data,origin,expected in [({'order':'BUY'},None,400),({'watchlist':['SPY'],'enabled':True},'https://example.com',403)]:
            headers={'Content-Type':'application/json'}
            if origin:headers['Origin']=origin
            req=urllib.request.Request(base+'/api/pattern-discovery',data=json.dumps(data).encode(),headers=headers)
            with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
            assert e.value.code==expected
        req=urllib.request.Request(base+'/api/pattern-discovery',data=json.dumps({'watchlist':['SPY'],'enabled':False}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as r:assert json.load(r)['enabled'] is False
    finally:srv.shutdown();srv.server_close();t.join(3)
