"""SOL 0.1 actual-source causality, preservation, accounting and read-only UI."""
import gzip,hashlib,json,math,sqlite3,sys,threading,urllib.request,urllib.error
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_data import read,ts
from trading_desk.btc_live import verify_rules
from trading_desk.sol01_view import VIEW
from trading_desk.sol_model01 import Contexts
from scripts.retest_refined_entries import signature


@pytest.fixture(scope='module')
def saved():
    f,s=VIEW.current();source=ROOT/s['source_study']
    with gzip.open(source/'data/SOL_USD_MINUTES.jsonl.gz','rt') as z:bars=[json.loads(l) for l in z]
    return f,s,source,bars


def test_original_paths_and_all_phase_cash_compounding(saved):
    f,s,source,bars=saved;old=read(source/'SOL_USD/E1/result.json');control=read(f/'full30/original_e1/result.json')
    assert s['control_reproduced'] and verify_rules()==s['rule_hashes']
    assert [signature(p) for p in old['trades']]==[signature(p) for p in control['trades']]
    assert len(s['books'])==16
    for b in s['books']:
        r=read(f/b['phase']/b['arm']/'result.json');a=r['account']
        closed=[p for p in r['trades'] if p['status']=='closed'];open_trades=[p for p in r['trades'] if p['remaining']]
        if not open_trades:assert a['final_equity']==pytest.approx(10000*math.prod(1+p['net']/(p['entry']*1.0002) for p in closed))
        else:
            assert len(open_trades)==1 and a['open_units']>0
            p=open_trades[0];assert a['last_price']==r['last_price']
            assert a['final_equity']==pytest.approx(a['cash']+a['open_units']*a['last_price']*.9998)
        assert not r['orders_enabled'] and not r['live_promoted']
    # UI extensions approved after this study do not change its frozen
    # rules; retain strict checks for every engine, worker and source file.
    for p,h in read(f/'PRESERVED_BEFORE.json').items():
        if p in {'trading_desk/btc_live.html','trading_desk/btc_live.js','trading_desk/btc_live.css'}:continue
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    release=ROOT/'trading_records/sol_structure/releases/0.1'
    for p,h in read(release/'MODEL.json')['files_sha256'].items():assert hashlib.sha256((release/p).read_bytes()).hexdigest()==h


def test_actual_sol_shocks_and_independent_holds_are_causal(saved):
    f,s,source,bars=saved;r=read(f/'full30/sol_01/result.json');market=Contexts(bars)
    signals=[q for q in r['signals'] if q['decision']=='entry']
    assert len(signals)==len(r['trades'])
    for sig in signals:
        if sig['route']=='A':continue
        setup=sig['setup_evidence'];shock=setup['sol_shock'];context=shock['context'];t=setup['impulse']['t']
        assert shock['qualifies'] and shock['net_drop_atr']>=2
        assert context['known_at']==t and context['last_source_bar']==t-900
        assert Contexts([b for b in bars if b['t']<t]).before(t)==market.before(t)==context
        assert setup['d']['known_at']<=ts(sig['time_utc'])
        if sig['route']=='B1':
            conf=sig['b1_confirmation'];assert conf['independent'] and conf['passed'] and conf['observed_minutes']==15
            assert ts(conf['time'])>=setup['d']['known_at']
            assert ts(conf['known_at'])<=ts(sig['time_utc'])
    tape=read(f/'TAPE.json');assert len(tape)==35
    # A real avoided failure and real delayed winner constrain both sides.
    assert next(t for t in tape if t['id']==19)['sol_net_shock_atr']<2
    changes=read(f/'CHANGES.json')
    assert any(c['original'] and c['original']['id']==19 and c['status']=='removed' for c in changes)
    assert any(c['status']=='added' and c['refined']['entry_time']=='2026-11-04T13:26:00Z' and c['refined']['net']>0 for c in changes)


def test_no_missing_minutes_become_atr_inputs(saved):
    f,s,source,bars=saved;market=Contexts(bars);missing=set(s['source_quality']['missing'])
    # Actual absent source observations invalidate their enclosing 15m context.
    checked=0
    for t in sorted(missing):
        period=t//900*900+900
        if ts(s['start'])<=period<ts(s['end']):
            assert market.before(period) is None;checked+=1
            if checked>=10:break
    assert checked==10


def test_isolated_read_only_pages_and_exports(saved):
    import server
    from http.server import ThreadingHTTPServer
    f,s,source,bars=saved
    with pytest.raises(ValueError):VIEW.snapshot('BTC/USD')
    with pytest.raises(ValueError):VIEW.export('full30','sol_01','../../.env')
    for phase in ('full30','first14','next7','final9'):
        for arm in ('original_e1','sol_net_shock','independent_hold','sol_01'):
            d=VIEW.snapshot(arm,phase);assert d['symbol']=='SOL/USD' and not d['live_promoted']
            if d['trades']:
                t=VIEW.snapshot(arm,phase,d['trades'][0]['id']);assert t['rows'] and t['selected_trade']
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        for route,title in (('/crypto-live','Crypto live stopped'),('/sol-live','SOL Live Paper · model 0.1'),('/btc-live','BTC Live Paper'),('/crypto-research','Crypto historical research')):
            html=urllib.request.urlopen(base+route).read().decode();assert title in html
            if route=='/crypto-live':assert '<script' not in html and 'id="start"' not in html
            if route=='/sol-live':assert '/btc_live.js' not in html and '/crypto_live.js' not in html
            if route=='/crypto-research':assert '/crypto_live.js' not in html and 'id="paper-alerts"' not in html
        for name in ('SUMMARY.csv','TAPE.csv','CHANGES.csv','TRADES.csv','PROTECTION.csv'):
            with urllib.request.urlopen(base+'/api/sol01/export?file='+name) as response:assert response.read()==VIEW.export('full30','sol_01',name).read_bytes()
        req=urllib.request.Request(base+'/api/sol01',data=b'{"operation":"start"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();thread.join(3)
