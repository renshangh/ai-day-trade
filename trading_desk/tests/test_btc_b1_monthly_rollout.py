"""Actual-minute rollout checks, with historical release 0.1 explicitly pinned."""
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_engine import create_replay
from trading_desk.btc_data import STORE,ts,read


def case(version,start,end):
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=create_replay(ts(start),ts(end),db,expanded_b=True,exit_version=version)
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as source:
        for t,o,h,l,c,v,n in source.execute('SELECT t,o,h,l,c,v,n FROM minutes WHERE t>=? AND t<? ORDER BY t',
                (ts('2026-10-03T00:00:00Z'),ts(end))):
            engine.minute(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    result=engine.finish();db.close();return result


def test_aggressive_old_entry_is_blocked_by_current_independent_confirmation():
    # The narrow window has a different position/setup-consumption history.
    # Replay from the frozen month boundary rather than inventing that state.
    args=('2026-10-10T00:00:00Z','2026-10-15T10:00:00-04:00')
    old=case('failed_rebound',*args);new=case('current',*args)
    assert old['trades'][4]['entry_time']=='2026-10-15T13:45:00Z'
    assert new['b1_independent_hold']
    assert not any(p['entry_time']=='2026-10-15T13:45:00Z' for p in new['trades'])
    for signal in new['signals']:
        if signal['route']=='B1' and signal['trade_id'] is not None:
            assert signal['b1_confirmation']['passed']
            assert signal['b1_confirmation']['independent']


def test_wait_rejection_does_not_consume_a_later_valid_confirmation():
    r=case('current','2026-10-12T09:30:00-04:00','2026-10-12T10:30:00-04:00')
    blocked=next(s for s in r['signals'] if s['route']=='B1' and s['time_utc']=='2026-10-12T13:33:00Z')
    assert blocked['decision']=='structure_rejected'
    first=r['trades'][0];signal=next(s for s in r['signals'] if s['trade_id']==first['id'])
    confirm=signal['b1_confirmation']
    assert signal['route']=='B1' and confirm['passed'] and confirm['independent']
    assert confirm['known_at']<=first['entry_time']
    assert confirm['time']>=signal['references']['l1']['known_at']
    assert confirm['low']>=signal['references']['l1']['price']


def test_frozen_release_source_and_workbook_remain_available():
    folder=STORE/'releases'/'0.1'
    if not folder.exists():pytest.skip('Requires the local frozen research release')
    import hashlib
    m=read(folder/'MANIFEST.json')
    assert m['version']=='0.1' and m['b1_independent_post_d_hold'] is False
    assert m['source_run']=='20261109T041525Z-30-ab'
    assert m['closed_net']==pytest.approx(3516.456280505433)
    assert all(hashlib.sha256((folder/p).read_bytes()).hexdigest()==h for p,h in m['files_sha256'].items())


def test_monthly_same_source_and_all_b1_invariants():
    from trading_desk.btc_lab import Lab
    old=read(STORE/'runs'/'20261109T041525Z-30-ab'/'result.json')
    folder=STORE/'runs'/'20261109T122648Z-30-ab'
    if not folder.exists():pytest.skip('Requires completed real-minute monthly rollout')
    r=read(folder/'result.json');a=read(folder/'B1_CONFIRMATION_REVIEW.json')
    assert r['source_minute_sha256']==old['source_minute_sha256']
    assert (r['start'],r['end'],r['cost_model'])==(old['start'],old['end'],old['cost_model'])
    assert len(a['rows'])==38 and len(a['accepted_b1'])==33 and a['waiting_cross_count']==26
    assert len(r['trades'])==36 and sum(p['net'] for p in r['trades'])==pytest.approx(2805.013738215147)
    for s in r['signals']:
        if s.get('b1_confirmation') and s['trade_id'] is not None:
            c=s['b1_confirmation'];d=s['references']['l1']
            assert c['passed'] and c['independent'] and c['observed_minutes']==15
            assert c['time']>=d['known_at'] and c['known_at']<=s['time_utc'] and c['low']>=d['price']
    detail=Lab().detail(r['run_id'])
    assert detail['b1_confirmation_review']['all_b1_confirmation_checks_pass']
    assert 'B1_CONFIRMATION_REVIEW.csv' in detail['exports']
    status=Lab().status()
    frozen=next(x for x in status['runs'] if x['run_id']==old['run_id'])
    assert frozen['release']['version']=='0.1'
    assert Lab().export(old['run_id'],'BTC_STRUCTURE_RELEASE_0.1.zip').is_file()
    with pytest.raises(ValueError):Lab().export(old['run_id'],'../MANIFEST.json')
