"""Actual archived trades and closes: cash accounting, no added capital or bars."""
import gzip,json,math,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.crypto_transfer import STUDIES
from trading_desk.unfiltered_90d import funded_account,loss_analysis

@pytest.fixture(scope='module')
def old():
    source=STUDIES/read(STUDIES/'ACTIVE.json')['study_id'];s=read(source/'STUDY.json');out={}
    for symbol in ('BTC/USD','SOL/USD'):
        with gzip.open(source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz'),'rt') as z:bars=[json.loads(x) for x in z]
        out[symbol]=(read(source/symbol.replace('/','_')/'E1/result.json'),bars)
    return s,out


def test_cash_return_matches_exact_fractional_trade_compounding(old):
    s,books=old
    for symbol,(r,bars) in books.items():
        a=funded_account(r['trades'],bars,ts(s['start']),ts(s['end']))
        expected=10000.
        for p in r['trades']:expected*=1+p['net']/(p['entry']*1.0002)
        assert a['final_equity']==pytest.approx(expected)
        assert a['cash']==pytest.approx(a['final_equity']) and a['open_units']==0
        assert a['return_pct']==pytest.approx(100*(expected/10000-1))
        assert len(a['account_trades'])==len(r['trades'])
        assert a['observed_test_minutes']+a['missing_test_minutes']==43200
        assert 0<=a['max_observed_drawdown_pct']<100
        for p in r['trades']:
            t=a['account_trades'][p['id']]
            assert t['initial_units']*p['entry']*1.0002==pytest.approx(t['cash_before_entry'])
            assert t['realized_net']==pytest.approx(t['initial_units']*p['net'])


def test_no_missing_entry_or_exit_observation_is_filled(old):
    s,books=old;r,bars=books['BTC/USD'];first=ts(r['trades'][0]['entry_time'])
    with pytest.raises(ValueError,match='Entry minute unavailable'):funded_account(r['trades'],[b for b in bars if b['t']!=first],ts(s['start']),ts(s['end']))
    with pytest.raises(ValueError,match='No actual test'):funded_account(r['trades'],[],ts(s['start']),ts(s['end']))
    losses=loss_analysis(r['trades']);assert losses['losses']==sum(p['net']<0 for p in r['trades'])
    assert set(losses['losing_trade_ids'])=={p['id'] for p in r['trades'] if p['net']<0}


def test_real_open_prefix_is_marked_not_forcibly_sold(old):
    import copy
    s,books=old;r,bars=books['BTC/USD'];p=copy.deepcopy(r['trades'][0]);start=ts(s['start']);cutoff=ts(p['entry_time'])+5*60
    p['legs']=[l for l in p['legs'] if ts(l['time_utc'])<cutoff];p['remaining']=1-sum(l['fraction'] for l in p['legs']);p['status']='open';p['net']=None;p.pop('exit_time',None);p['realized_leg_net']=sum(l['net'] for l in p['legs'])
    assert p['remaining']>0
    a=funded_account([p],[b for b in bars if b['t']<cutoff],start,cutoff)
    assert a['open_units']>0 and a['account_trades'][p['id']]['status']=='open'
    q=a['account_trades'][p['id']]['initial_units']
    expected=q*(p['realized_leg_net']+p['remaining']*(a['last_price']-p['entry']-(a['last_price']+p['entry'])*.0002))
    assert a['net']==pytest.approx(expected)
    assert len(a['account_trades'][p['id']]['legs'])==len(p['legs'])


def test_saved_90_sources_controls_and_account_drawdowns():
    import hashlib
    from trading_desk.unfiltered_90_view import VIEW,BOOKS
    from trading_desk.btc_live import verify_rules
    folder,s=VIEW.current();assert s['status']=='complete' and ts(s['end'])-ts(s['start'])==90*86400
    assert len(s['controls_reproduced'])==4 and all(s['controls_reproduced'].values()) and s['rule_hashes']==verify_rules()
    for p,h in {**read(folder/'PRESERVED_BEFORE.json'),**s['code_hashes']}.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    for symbol,q in s['source_quality'].items():
        path=folder/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==q['archive_sha256']
        with gzip.open(path,'rt') as z:bars=[json.loads(l) for l in z]
        assert len(bars)+len(q['missing'])==q['expected']
        assert q['test_observed']+q['test_missing']==129600 and not q['completely_missing_test_days']
        assert set(q['missing']).isdisjoint(b['t'] for b in bars)
    for symbol,model in BOOKS:
        for period in ('original30','unfiltered90'):
            book=folder/symbol.replace('/','_')/model/period;r=read(book/'result.json');a=r['cash_scenario']
            with gzip.open(book/'EQUITY.jsonl.gz','rt') as z:points=[json.loads(l) for l in z]
            peak=10000.;dd=0.
            for p in points:
                assert p['equity']==pytest.approx(p['cash']+p['units']*p['mark_price']*.9998)
                assert p['cash']>=-1e-8 and p['units']>=0
                peak=max(peak,p['equity']);dd=max(dd,100*(peak-p['equity'])/peak)
            assert len(points)==a['observed_test_minutes'] and points[-1]['equity']==a['final_equity']
            assert dd==pytest.approx(a['max_observed_drawdown_pct'])
            assert sum(l['losses'] for l in r['loss_analysis']['entry_routes'].values())==r['loss_analysis']['losses']
            assert len(VIEW.snapshot(symbol,model,period,'all','losses')['trades'])==r['loss_analysis']['losses']
            clean=VIEW.snapshot(symbol,model,period,'no_flagged_gap','losses')['trades'];flagged=VIEW.snapshot(symbol,model,period,'flagged_gap_or_context','losses')['trades']
            assert len(clean)+len(flagged)==r['loss_analysis']['losses']
            assert a['final_equity']==pytest.approx(10000*math.prod(1+p['net']/(p['entry']*1.0002) for p in r['trades']))


def test_http_read_only_exports_and_full_book_metrics_not_filtered():
    from trading_desk.unfiltered_90_view import VIEW
    import threading,urllib.request,urllib.error
    from http.server import ThreadingHTTPServer
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    with pytest.raises(ValueError):VIEW.export('all','E1','unfiltered90','../.env')
    with pytest.raises(ValueError):VIEW.snapshot('SOL/USD','E2')
    a=VIEW.snapshot('SOL/USD','E1','unfiltered90','all','all');b=VIEW.snapshot('SOL/USD','E1','unfiltered90','flagged_gap_or_context','losses')
    assert a['account']==b['account'] and a['summaries']==b['summaries']
    assert VIEW.snapshot('SOL/USD','E1','unfiltered90','all','open')['trades']==[]
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start();url='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(url+'/api/unfiltered-90') as r:d=json.load(r)
        assert d['available'] and not d['orders_enabled'] and not d['live_promoted'] and len(d['summaries'])==4
        req=urllib.request.Request(url+'/api/unfiltered-90',data=b'{"operation":"trade"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
