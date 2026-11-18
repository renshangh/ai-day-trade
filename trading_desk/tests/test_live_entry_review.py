"""Recorded live entry review uses saved observations, not tuned trade outcomes."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.btc_live import verify_rules

FOLDER=ROOT/'reports/live_entry_review_20261110T111101Z'


def test_original_routes_and_exits_reproduced_with_original_observations():
    r=read(FOLDER/'REVIEW.json');assert not r['live_changed'] and not r['monthly_replay'] and not r['orders_enabled']
    assert r['rules']==verify_rules()
    for asset in r['results']:
        h=hashlib.sha256()
        with sqlite3.connect((ROOT/asset['actual_source']).as_uri()+'?mode=ro',uri=True) as db:
            records=db.execute('SELECT body FROM minutes WHERE t<? ORDER BY t',(ts(asset['prefix_through']),)).fetchall()
            for body, in records:h.update((body+'\n').encode())
            for p in asset['trades']:
                saved=[json.loads(body) for body, in db.execute("SELECT body FROM signals WHERE model='E1' AND ref=?",(ts(p['entry_time']),))]
                s=next(s for s in saved if s.get('trade_id')==p['trade_id'])
                assert s['route']==p['recorded_route'] and s['setup_evidence']==p['setup_evidence']
                assert p['net']==pytest.approx(sum(l['fraction']*((l['price']-p['entry'])-.0002*(l['price']+p['entry'])) for l in p['legs']))
                assert all(ts(l['time_utc'])>=ts(p['entry_time']) for l in p['legs'])
        assert len(records)==asset['minute_count'] and h.hexdigest()==asset['minute_sha256']


def test_a_independence_and_b_priority_are_separate_from_profit():
    r=read(FOLDER/'REVIEW.json');btc=r['results'][0]['trades'];sol=r['results'][1]['trades']
    assert [p['recorded_route'] for p in btc]==['A','A','B1']
    for p in btc[:2]:
        a=next(c for c in p['review']['candidates'] if c['route']=='A')
        assert a['p1']['p1_low_count']==3 and not a['p1']['passed'] and p['net']>0
        assert a['p1']['checks'][2]['status']=='extended_same_decline'
        assert all(c['qualified_at'] is None or c['qualified_at']<=ts(p['entry_time']) for c in a['p1']['checks'])
    latest=btc[-1]
    assert {c['route'] for c in latest['review']['candidates'] if c['would_qualify_before_route_priority']}=={'B1','B2'}
    assert latest['net']<0 and all(l['reason']!='stop' for l in latest['legs'])
    assert [p['recorded_route'] for p in sol]==['B1','B1']
    b2=next(c for c in sol[0]['review']['candidates'] if c['route']=='B2')
    assert not b2['would_qualify_before_route_priority'] and 'higher-low tolerance failed' in b2['check']['signal_reasons']
    assert [c['route'] for c in sol[1]['review']['candidates']]==['B1']


def test_recent_history_uses_complete_source_not_capped_dashboard_events():
    from trading_desk.sol_live import snapshot
    from trading_desk.crypto_live_history import recent
    state=snapshot();baseline=recent(state)
    assert baseline['trades'] and not baseline['orders_enabled']
    for key in ('btc','sol'):state[key]['events']=[];state[key]['signals']=[]
    assert recent(state)==baseline
    for row in baseline['trades']:
        s=row['entry_signal']
        assert row['realized_net']==pytest.approx(sum(l['fraction']*((l['price']-s['entry_reference'])-.0002*(l['price']+s['entry_reference'])) for l in row['legs']))
    state['sol']['session']={'id':'99999999T999999Z'}
    assert recent(state)['unavailable']==['SOL/USD']


def test_new_sol_b1_uses_d_candle_not_independent_confirmation():
    from trading_desk.btc_shock_branches import independent_b1_setup,expanded_shock_setup
    data=read(FOLDER/'NEW_SOL_ENTRY.json');s=data['signal'];setup=s['setup_evidence'];now=ts(s['time_utc'])
    independent=independent_b1_setup(setup,now,setup['stabilization_bar'],d_intact=not setup['d_broken'])
    assert s['route']=='B1' and expanded_shock_setup(setup,now,'B1')['setup_passed']
    assert independent==data['independent_b1_check'] and not independent['setup_passed']
    assert setup['stabilization_bar']['t']<setup['d']['known_at']
    assert independent['entry_not_before']==ts('2026-11-10T11:30:00Z')
    assert not expanded_shock_setup(setup,now,'B2')['setup_passed']
