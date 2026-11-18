"""Actual IBIT RTH observations, calendar continuity, targets and live isolation."""
import copy,gzip,hashlib,json,math,sqlite3,sys,threading,urllib.request,urllib.error
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_data import read,ts
from trading_desk.btc_live import verify_rules
from trading_desk.ibit_sessions import Calendar
from trading_desk.ibit_model import make_engine
from trading_desk.ibit_view import VIEW


@pytest.fixture(scope='module')
def saved():
    f,s=VIEW.current();source=ROOT/s['input_path']
    with gzip.open(source/'IBIT_MINUTES.jsonl.gz','rt') as z:bars=[json.loads(l) for l in z]
    calendar=Calendar(read(source/'CALENDAR.json'),ts(s['warmup_start']),ts(s['end']))
    return f,s,bars,calendar


def test_real_session_coverage_dst_and_closed_intervals(saved):
    f,s,bars,c=saved;assert len(bars)==9750 and len(c.allowed)==9750
    assert {b['t'] for b in bars}==c.allowed and s['test_observed']==s['test_expected']==7800
    ny=ZoneInfo('America/New_York')
    for b in bars:
        d=datetime.fromtimestamp(b['t'],ny);assert d.weekday()<5 and (d.hour,d.minute)>=(9,30) and d.hour<16
    a=ts('2026-10-30T19:59:00Z');b=ts('2026-11-02T14:30:00Z')
    assert a in c.allowed and b in c.allowed and c.missing_between(a,b)==[]
    assert c.adjacent_bars(a//900*900,b//900*900)
    assert ts('2026-10-30T13:30:00Z') in c.allowed and ts('2026-11-02T13:30:00Z') not in c.allowed
    # Calendar metadata, not market bars: documented Thanksgiving early-close
    # fixture proves the adapter uses supplied close times rather than 16:00.
    early=Calendar([dict(date='2026-11-27',open='09:30',close='13:00')],ts('2026-11-27T00:00:00Z'),ts('2026-11-28T00:00:00Z'))
    assert len(early.minutes)==210 and ts('2026-11-27T18:00:00Z') not in early.allowed


def test_original_control_and_observed_equity_reconcile(saved):
    f,s,bars,c=saved;assert verify_rules()==s['rule_hashes']
    # Frozen engine/source checks remain strict. The owner subsequently
    # authorized new BTC view panels and IBIT badges; those assets are not
    # part of the frozen strategy and cannot use this old study's UI hash.
    for p,h in {**read(f/'PRESERVED_BEFORE.json'),**s['code_hashes']}.items():
        if p in {'trading_desk/btc_live.html','trading_desk/btc_live.js','trading_desk/btc_live.css'}:continue
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    for arm in ('exact_control','session_adapted'):
        for model in ('0.1','E1','E2'):
            r=read(f/arm/model/'result.json');a=r['account']
            assert a['expected_test_minutes']==7800 and a['missing_test_minutes']==0
            assert a['final_equity']==pytest.approx(10000*math.prod(1+p['net']/(p['entry']*1.0002) for p in r['trades']))
            with gzip.open(f/arm/model/'EQUITY.jsonl.gz','rt') as z:points=[json.loads(l) for l in z]
            peak=10000.;dd=0.
            for p in points:
                assert ts(p['minute_start']) in c.allowed and p['missing_minutes_before']==0
                assert p['equity']==pytest.approx(p['cash']+p['units']*p['mark_price']*.9998)
                peak=max(peak,p['equity']);dd=max(dd,100*(peak-p['equity'])/peak)
            assert len(points)==7800 and dd==pytest.approx(a['max_observed_drawdown_pct'])
            if arm=='exact_control':assert not r['trades'] and r['signal_counts']['target_missing']==11
            else:assert len(r['trades'])==4 and r['counts'].get('missing_minutes',0)==0


def test_native_times_targets_and_overnight_execution_are_known(saved):
    f,s,bars,c=saved;source={b['t']:b for b in bars};r=read(f/'session_adapted/E1/result.json')
    for review in r['target_reviews']:
        now=ts(review['time']);peak=review['large_peak'];assert peak['known_at']<=now and peak['observed_minutes']==240
        assert len(peak['source_15m_starts'])==16 and all(t in c.period_index for t in peak['source_15m_starts'])
        assert peak['end']==peak['source_15m_starts'][-1]+900
        for member in review['zone']['members']:
            assert member['known_at']<=now and member['source_block']['observed_minutes']==60
    for p in r['trades']:
        assert ts(p['entry_time']) in source and p['references']['l1']['known_at']<=p['entry_time']
        for l in p['legs']:assert ts(l['time_utc']) in source
    first=r['trades'][0];assert first['entry_time'][:10]!=first['exit_time'][:10]
    opening=source[ts(first['exit_time'])];evidence=first['case_exit_evidence'][-1]
    assert first['exit_time']=='2026-10-16T13:30:00Z'
    assert evidence['phase']==1 and opening['low']<=first['legs'][-1]['price']<opening['open']
    assert first['legs'][-1]['price']==evidence['failed_rebound']['price']
    # Real source opening gap, hypothetical protection state: prove the shared
    # stop selector uses the opening reference instead of an unreachable stop.
    from trading_desk.btc_approved_exits import candidates
    pair=next((a,b) for a,b in zip(bars,bars[1:]) if b['t']-a['t']>3600 and b['open']<a['close'])
    old,new=pair;p=copy.deepcopy(first);p.update(stop=old['close'],remaining=1.,t1=None,armed_midpoint=None)
    opts=candidates(p,new,[],None,policy='v2');stop=next(o for o in opts if o['reason']=='stop')
    assert stop['price']==new['open'] and stop['price']<p['stop']


def test_rth_adapter_recovery_is_deterministic_and_rejects_off_session(saved):
    f,s,bars,c=saved;db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=make_engine('E1',ts(s['start']),ts(s['end']),db,c,True)
    for b in bars:engine.minute(b)
    r=engine.finish();saved_result=read(f/'session_adapted/E1/result.json')
    assert [(p['entry_time'],p['entry'],p['exit_time'],p['net']) for p in r['trades']]==[(p['entry_time'],p['entry'],p['exit_time'],p['net']) for p in saved_result['trades']]
    # Use a genuine archived extended-hours minute, never a made-up price/time.
    rejected=None
    for raw in (ROOT/s['input_path']/'raw').glob('*.gz'):
        with gzip.open(raw,'rt') as z:page=json.load(z)
        candidates_raw=(page.get('bars') or {}).get('IBIT',[]) if isinstance(page,dict) else []
        if len(candidates_raw)<1000:continue
        q=next((q for q in candidates_raw if ts(s['warmup_start'])<=ts(q['t'])<ts(s['end']) and ts(q['t']) not in c.allowed),None)
        if q:
            rejected=dict(t=ts(q['t']),open=q['o'],high=q['h'],low=q['l'],close=q['c'],volume=q['v'],n=q.get('n'));break
    assert rejected is not None
    with pytest.raises(ValueError):engine.minute(rejected)
    db.close()


def test_read_only_api_details_and_exports(saved):
    import server
    from http.server import ThreadingHTTPServer
    with pytest.raises(ValueError):VIEW.snapshot('SOL')
    with pytest.raises(ValueError):VIEW.export('session_adapted','E1','../../.env')
    d=VIEW.snapshot(trade_id=1);assert d['rows'] and not d['orders_enabled'] and not d['live_promoted']
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start();base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        assert b'BTC live models on IBIT' in urllib.request.urlopen(base+'/ibit-lab').read()
        for name in ('SUMMARY.csv','TRADES.csv','EXITS.csv','PROTECTION.csv'):
            with urllib.request.urlopen(base+'/api/ibit-lab/export?file='+name) as r:assert r.read()==VIEW.export('session_adapted','E1',name).read_bytes()
        req=urllib.request.Request(base+'/api/ibit-lab',data=b'{"operation":"start"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();thread.join(3)
