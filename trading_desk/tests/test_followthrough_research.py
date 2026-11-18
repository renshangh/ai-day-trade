"""Real saved minutes only: causal references, false exits and protected state."""
import hashlib
import json
from pathlib import Path
import sys
import threading
import urllib.request
import urllib.error
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_data import read,ts
from trading_desk.followthrough_view import VIEW,BOOKS,GROUPS
from trading_desk.followthrough_research import Market,value,PROTOCOL
from trading_desk.steeper_shock_research import PROTOCOL as SHOCK
from trading_desk.btc_live import verify_rules


def test_locked_protocol_controls_and_all_protected_files():
    folder,s=VIEW.current()
    assert s['status']=='complete' and s['exit_protocol']==PROTOCOL and s['shock_protocol']==SHOCK
    assert len(s['controls_reproduced'])==4 and all(s['controls_reproduced'].values())
    assert s['rule_hashes']==verify_rules()
    for p,h in {**read(folder/'PRESERVED_BEFORE.json'),**s['code_hashes']}.items():
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p


@pytest.mark.parametrize('asset',['BTC','SOL'])
def test_0445_failures_use_completed_minutes_and_no_current_minute_range(asset):
    folder,_=VIEW.current();c=read(folder/(asset+'_USD_0445.json'));p=c['original'];m=c['minutes']
    r=c['exits']['F1'];signal=r['signal'];now=ts(signal['exit_time'])
    assert now==ts('2026-11-10T10:05:00Z') and r['delta']>0
    assert all(x['t']+60<=now for x in signal['completed_minutes'])
    assert ts(signal['armed']['known_at'])<=signal['completed_minutes'][0]['t']
    assert signal['direction']['passed'] and signal['current_minute_range_used'] is False
    assert c['shock']['net_drop_atr']<3 and not c['shock']['qualifies']
    assert r['legs'][0]['fraction']==1
    # A real observation wrapper prevents accidental use of this minute's
    # not-yet-known range/close. No replacement market values are introduced.
    class OpeningOnly(dict):
        def __getitem__(self,k):
            assert k not in ('high','low','close'), 'future current-minute range was read'
            return super().__getitem__(k)
    prefix=[OpeningOnly(b) if b['t']==now else b for b in m if b['t']<=now]
    actual=Market(prefix).scan(p,'F1')
    assert actual['signal']==signal
    assert Market(m).scan(p,'F1',cutoff=now)['signal'] is None
    missing=Market([b for b in m if b['t']!=now]).scan(p,'F1')
    assert missing['signal'] is None or ts(missing['signal']['exit_time'])>now
    if asset=='BTC':assert not c['exits']['F2']['triggered'] # frozen exit is one minute earlier
    else:assert ts(c['exits']['F2']['exit_time'])==ts('2026-11-10T10:15:00Z')


def test_every_outcome_reconciles_preserves_earlier_legs_and_ties():
    folder,_=VIEW.current()
    for symbol,model in BOOKS:
        rows=read(folder/symbol.replace('/','_')/model/'EXITS.json')
        for p in rows:
            assert sum(l['fraction'] for l in p['legs'])==pytest.approx(1)
            assert sum(l['net'] for l in p['legs'])==pytest.approx(p['net'])
            assert p['delta']==pytest.approx(p['net']-p['original_net'])
            if p['triggered']:
                t=ts(p['exit_time']);assert t<ts(p['original_exit'])
                assert all(ts(l['time_utc'])!=t for l in p['original_legs'])
                earlier=[l for l in p['original_legs'] if ts(l['time_utc'])<t]
                assert p['legs'][:-1]==earlier
                leg=p['legs'][-1]
                assert leg['cost']==pytest.approx(leg['fraction']*(p['entry']+leg['price'])*.0002)
                assert p['signal']['direction']['passed']
            else:assert p['original_legs']==p['legs'] and p['delta']==0
        for policy in ('F1','F2'):
            totals={}
            for group in GROUPS:
                d=VIEW.snapshot(symbol,model,policy,group)
                summary=next(b['exit'] for b in d['summaries'] if (b['symbol'],b['model'])==(symbol,model))
                assert sum(r['delta'] for r in d['trades'])==pytest.approx(summary['delta'])
                assert summary['trades']==len(d['trades'])
                totals[group]=summary['delta']
                b=next(x for x in d['summaries'] if (x['symbol'],x['model'])==(symbol,model))
                assert sum(c['delta_normalized_10000'] for c in d['shock_changes'])==pytest.approx(b['shock_steeper']['normalized_10000_realized']-b['shock_original']['normalized_10000_realized'])
            assert totals['all']==pytest.approx(totals['no_flagged_gap']+totals['flagged_gap_or_context'])


def test_winner_harm_and_winning_control_are_not_hidden():
    d=VIEW.snapshot();s=next(x['exit'] for x in d['summaries'] if x['symbol']=='BTC/USD' and x['model']=='E1')
    assert s['winners_cut']==3 and s['winners_flipped_to_loss']==3
    p=next(x for x in d['trades'] if x['trade_id']==30)
    assert p['original_net']>0 and p['net']<0 and p['delta']<-1500
    sol=VIEW.snapshot('SOL/USD','E1');s=next(x['exit'] for x in sol['summaries'] if x['symbol']=='SOL/USD')
    assert s['loser_improved']==9 and s['loser_worsened']==1 and s['winners_cut']==0


def test_new_shock_entries_are_qualified_not_relabelled_by_default():
    folder,_=VIEW.current()
    for symbol,model in BOOKS:
        r=read(folder/symbol.replace('/','_')/model/'steeper/result.json')
        signals={p['trade_id']:p for p in r['signals'] if p['decision']=='entry'}
        for p in r['trades']:
            s=signals[p['id']];e=s['setup_evidence']
            assert s['initial_stop']==pytest.approx(s['references']['l1']['price']-.25*s['atr'])
            if p['entry_rule']=='A':assert p['p1']['passed'] and p['p1']['p1_low_count']>=4
            else:
                assert (e['previous_close']-e['impulse']['close'])/e['atr_before_impulse']>=3
                assert e['impulse']['t']+900<=ts(p['entry_time'])
                if p['entry_rule']=='B1':assert e['refined_first_hold']['t']+900==ts(p['entry_time'])//900*900


def test_export_validation_and_http_read_only():
    import server
    from http.server import ThreadingHTTPServer
    for bad in ('../.env','../../STUDY.json'):
        with pytest.raises(ValueError):VIEW.export('all','E1',bad)
    with pytest.raises(ValueError):VIEW.snapshot('SOL/USD','E2')
    with pytest.raises(ValueError):VIEW.snapshot(policy='submit')
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/followthrough') as r:d=json.load(r)
        assert d['available'] and not d['orders_enabled'] and not d['live_promoted'] and len(d['summaries'])==4
        with urllib.request.urlopen(base+'/api/followthrough/export?symbol=all&file=EXIT_TRADES.csv') as r:assert b'trade_id' in r.read()
        req=urllib.request.Request(base+'/api/followthrough',data=b'{}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
