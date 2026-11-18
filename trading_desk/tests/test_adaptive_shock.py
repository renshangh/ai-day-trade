"""Actual archived observations: causal cross-asset scaling and calibration."""
import copy,gzip,json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.adaptive_shock import Contexts,Settings,Policy,threshold
from trading_desk.crypto_transfer import STUDIES
from trading_desk.btc_data import read
from scripts.study_adaptive_shock import choose

@pytest.fixture(scope='module')
def actual():
    folder=STUDIES/read(STUDIES/'ACTIVE.json')['study_id'];out={}
    for s in ('BTC/USD','SOL/USD'):
        with gzip.open(folder/'data'/(s.replace('/','_')+'_MINUTES.jsonl.gz'),'rt') as f:out[s]=[json.loads(x) for x in f]
    return out


def test_thresholds_have_known_prior_context_and_explicit_separate_weight(actual):
    contexts={s:Contexts(x) for s,x in actual.items()};times=sorted(contexts['BTC/USD'].bars)
    t=next(t for t in times if contexts['BTC/USD'].before(t) and contexts['SOL/USD'].before(t))
    btc=contexts['BTC/USD'].before(t);sol=contexts['SOL/USD'].before(t)
    a=threshold('BTC/USD',btc,btc,Settings());b=threshold('SOL/USD',sol,btc,Settings(2.,1.));c=threshold('SOL/USD',sol,btc,Settings(2.,1.5))
    assert a['asset_weight']==1 and a['threshold_pct']==pytest.approx(2*btc['atr_pct'])
    assert b['threshold_pct']>=a['threshold_pct'] and c['threshold_pct']==pytest.approx(1.5*b['threshold_pct'])
    assert c['effective_asset_atr']>=3
    assert btc['last_source_bar']+900==t and btc['known_at']==t
    # Removing all later actual observations cannot change the pre-shock threshold.
    prefix=Contexts([x for x in actual['BTC/USD'] if x['t']<t])
    assert prefix.before(t)==btc
    missing=Contexts([x for x in actual['BTC/USD'] if x['t']<t and x['t']!=t-60])
    assert missing.before(t) is None
    assert threshold('SOL/USD',sol,None,Settings()) is None


@pytest.mark.parametrize('kwargs',[dict(base_btc_atr=1.),dict(sol_weight=.9),dict(sol_weight=float('nan')),dict(base_btc_atr=True),dict(sol_weight=4.)])
def test_bounds_cannot_change_broker_or_frozen_risk(kwargs):
    with pytest.raises(ValueError):Settings(**kwargs)


def test_a_nonshock_never_becomes_an_automatic_a_entry(actual):
    c={s:Contexts(x) for s,x in actual.items()};policy=Policy('SOL/USD',c['SOL/USD'],c['BTC/USD'])
    t=next(t for t in sorted(c['SOL/USD'].bars) if c['SOL/USD'].before(t) and c['BTC/USD'].before(t) and t-900 in c['SOL/USD'].bars)
    b=copy.deepcopy(c['SOL/USD'].bars[t]);b['atr_before']=c['SOL/USD'].before(t)['atr']
    m=policy.evaluate(b,c['SOL/USD'].bars[t-900],None)
    assert not m['qualifies'] and 'A' not in m


def test_empty_calibration_falls_back_without_claiming_learning():
    p=choose([]);assert p['settings']==Settings(2.,1.).asdict() and not p['learned']


def test_replayed_controls_hashes_and_trade_evidence():
    import hashlib
    from trading_desk.adaptive_shock_view import VIEW,BOOKS
    from trading_desk.btc_data import ts
    from trading_desk.btc_live import verify_rules
    folder,s=VIEW.current();assert s['status']=='complete' and all(s['controls_reproduced'].values()) and len(s['controls_reproduced'])==4
    assert s['rule_hashes']==verify_rules()
    for p,h in {**s['code_hashes'],**read(folder/'PRESERVED_BEFORE.json')}.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    for symbol,model in BOOKS:
        for sequence in ('atr_only','weighted','test_selected'):
            r=read(folder/symbol.replace('/','_')/model/sequence/'result.json')
            for p in r['trades']:
                assert sum(l['fraction'] for l in p['legs'])+p['remaining']==pytest.approx(1)
                assert sum(l['net'] for l in p['legs'])==pytest.approx(p['realized_leg_net'])
                if p['entry_rule']=='A':assert p['p1']['passed']
                else:
                    m=p['adaptive_shock'];t=m['threshold']
                    assert m['qualifies'] and m['net_drop_pct']>=t['threshold_pct']
                    assert t['known_at']<=m['bar_time'] and m['known_at']<=ts(p['entry_time'])
                    assert t['asset_context']['last_source_bar']+900==m['bar_time']
                    assert t['btc_context']['last_source_bar']+900==m['bar_time']
                    assert t['asset_weight']==(1. if symbol=='BTC/USD' else r['adaptive_settings']['sol_weight'])
                    assert p['initial_stop']==pytest.approx(p['references']['l1']['price']-.25*r['signals'][p['signal_id']-1]['atr'])


def test_calibration_is_reproducible_without_any_test_score():
    from trading_desk.adaptive_shock_view import VIEW,BOOKS
    folder,s=VIEW.current()
    for symbol,model in BOOKS:
        book=folder/symbol.replace('/','_')/model
        candidates=read(book/'CALIBRATION.json');expected=read(book/'SELECTION_BEFORE_TEST.json')
        assert choose(candidates)==expected
        for c in candidates:assert set(c)=={'symbol','model','settings','train','validation'}
        # Real test outcomes attached as irrelevant metadata cannot affect selection.
        actual_test=read(book/'test_weighted/result.json')['summary']
        augmented=[dict(c,test=actual_test) for c in candidates]
        assert choose(augmented)==expected
        for n in ('uniform3','atr_only','weighted','selected'):
            r=read(book/('test_'+n)/'result.json')
            assert all(p['entry_time']>=s['test_start'] for p in r['trades'])
            assert r['start']==s['test_start']
    sol=next(b for b in s['books'] if b['symbol']=='SOL/USD')
    assert sol['selection']['settings']['sol_weight']==1.
    assert sol['test']['weighted']['all']['normalized_10000_realized']>sol['test']['selected']['all']['normalized_10000_realized']


def test_gap_partitions_changes_exports_and_read_only_http():
    from trading_desk.adaptive_shock_view import VIEW,BOOKS,GROUPS
    from http.server import ThreadingHTTPServer
    import threading,urllib.request,urllib.error
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    for symbol,model in BOOKS:
        for phase in ('full','test'):
            totals={}
            for group in GROUPS:
                d=VIEW.snapshot(symbol,model,phase,group);b=next(b for b in d['summaries'] if (b['symbol'],b['model'])==(symbol,model))
                diff=b['sequences'][d['comparison']]['normalized_10000_realized']-b['sequences']['atr_only']['normalized_10000_realized']
                assert sum(c['delta_normalized_10000'] for c in d['changes'])==pytest.approx(diff)
                totals[group]=diff
            assert totals['all']==pytest.approx(totals['no_flagged_gap']+totals['flagged_gap_or_context'])
    with pytest.raises(ValueError):VIEW.export('all','E1','weighted','../.env')
    with pytest.raises(ValueError):VIEW.snapshot('SOL/USD','E2')
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start();base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/adaptive-shock') as r:d=json.load(r)
        assert d['available'] and not d['orders_enabled'] and len(d['summaries'])==4
        req=urllib.request.Request(base+'/api/adaptive-shock',data=b'{"operation":"trade"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
