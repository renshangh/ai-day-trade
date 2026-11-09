"""V2 exits on immutable archived Alpaca observations, not synthetic bars."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_direction_filtered_exits as audit
from audit_btc_oct12_b_branches import load,FOLDER
from trading_desk.btc_data import ts,STORE
from trading_desk.btc_engine import aggregate
from trading_desk.btc_approved_exits import candidates,direction_context,direction_passed,ApprovedExitReplay,POLICY


@pytest.fixture(scope='module')
def minutes():return load()[1]


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def context(minutes,stamp):
    t=ts(stamp);period=t//900*900
    current=next(b for b in minutes if b['t']==t)
    prefix=[b for b in minutes if period<=b['t']<t]
    previous=aggregate([b for b in minutes if period-900<=b['t']<period],900)
    return current,prefix,previous


def position(case=0):
    p=copy.deepcopy(json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][case]['trade'])
    p.update(status='open',remaining=1.,legs=[],stop=p['initial_stop'],pending_lows=[],
        armed_midpoint=None,active_wave_high=p['references']['h1']['price'])
    return p


def active(options):return [c for c in options if c['reason'] in ('midpoint_exit_all','wick_exit_all')]


def test_two_fixed_cases_pass_filters_without_changing_other_parameters(reviewed):
    morning,night=reviewed['cases']
    assert reviewed['policy']==POLICY
    assert morning['trade']['exit_time']=='2026-10-12T14:05:00Z'
    assert morning['trade']['net']==pytest.approx(165.53449145)
    assert night['trade']['exit_time']=='2026-10-13T02:31:00Z'
    assert night['trade']['legs'][0]['price']==82655.0085
    assert night['trade']['net']==pytest.approx(1224.9520491)
    for c in (morning,night):
        assert c['entry_and_parameters_unchanged'] and c['holding_minutes_contiguous']
        p=c['trade'];assert not p.get('stop_history')
        assert len(p['legs'])==1 and p['legs'][0]['fraction']==1
        for e in p['active_exit_events']:
            assert e['direction_reference_price']<=min(e['direction_bar_open'],e['previous_bar_close'])
    rejected=night['filter_rejections']
    assert [r['time_utc'] for r in rejected]==['2026-10-13T02:29:00Z','2026-10-13T02:30:00Z']
    assert all(r['blocked_above_previous_close'] and not r['blocked_green'] for r in rejected)


@pytest.mark.parametrize('stamp,allowed,green,above',[
    ('2026-10-04T11:29:00-04:00',True,False,False),
    ('2026-10-05T02:29:00-04:00',False,False,True),
    ('2026-10-05T06:14:00-04:00',False,True,True),
    ('2026-10-07T16:29:00-04:00',False,True,False),
])
def test_wick_both_direction_conditions_independently(minutes,stamp,allowed,green,above):
    now,prefix,prev=context(minutes,stamp);p=position()
    # Hypothetical held strategy controls from actual prior bar; OHLC unmodified.
    p.update(entry=prev['low'],stop=prev['low']-1,t1=None,t2=None,active_wave_high=prev['high'])
    d=direction_context(now,prefix,prev)
    assert (now['open']>d['direction_bar_open'])==green
    assert (now['open']>d['previous_bar_close'])==above
    assert any(c['reason']=='wick_exit_all' for c in candidates(p,now,prefix,prev,policy='v1'))
    wick=[c for c in candidates(p,now,prefix,prev) if c['reason']=='wick_exit_all']
    assert bool(wick)==allowed
    if wick:
        e=wick[0]
        assert e['price']==now['open'] and e['phase']==0
        h=max(now['open'],max(b['high'] for b in prefix))
        l=min(now['open'],min(b['low'] for b in prefix))
        assert e['upper_wick_fraction']==pytest.approx((h-max(prefix[0]['open'],now['open']))/(h-l))


def test_midpoint_waits_for_actual_direction_crossing_not_old_higher_midpoint(minutes):
    now,prefix,prev=context(minutes,'2026-10-12T22:30:00-04:00');p=position(1)
    p['armed_midpoint']=dict(reference_t=prev['t'],known_at=prev['t']+900,
        reference_high=prev['high'],reference_low=prev['low'],price=(prev['high']+prev['low'])/2)
    old=active(candidates(p,now,prefix,prev,policy='v1'))[0]
    assert old['price']==82658.58 and old['phase']==0
    assert now['low']>prev['close']
    assert not active(candidates(p,now,prefix,prev))
    nxt,prefix,prev=context(minutes,'2026-10-12T22:31:00-04:00')
    c=active(candidates(p,nxt,prefix,prev))[0]
    assert c['phase']==1 and c['price']==prev['close']==82655.0085
    assert c['price']<old['price']<p['armed_midpoint']['price']
    # Actual completed candle ends GREEN, but its future close cannot veto an
    # eligible earlier non-green intrabar observation.
    final=aggregate([b for b in minutes if now['t']<=b['t']<now['t']+900],900)
    assert final['close']>final['open']


def test_missing_true_open_or_previous_complete_bar_withholds_active_exits(minutes):
    now,prefix,prev=context(minutes,'2026-10-12T10:14:00-04:00');p=position()
    assert active(candidates(p,now,prefix,prev))
    assert not active(candidates(p,now,prefix,None))
    assert not active(candidates(p,now,prefix[1:],prev))
    earlier=aggregate([b for b in minutes if prev['t']-900<=b['t']<prev['t']],900)
    assert not active(candidates(p,now,prefix,earlier))
    incomplete=aggregate([b for b in minutes if prev['t']<=b['t']<prev['t']+840],900)
    assert not active(candidates(p,now,prefix,incomplete))
    # Filters apply to active shape exits, never the protective stop.
    p['stop']=now['low']
    assert any(c['reason']=='stop' for c in candidates(p,now,[],None))


def test_equality_is_non_green_and_not_above_previous_close(minutes):
    now,prefix,prev=context(minutes,'2026-10-12T22:30:00-04:00')
    d=direction_context(now,prefix,prev)
    assert not direction_passed(now['open'],d) # doji, but above previous close
    assert direction_passed(d['previous_bar_close'],d) # equality permitted
    assert not direction_passed(d['direction_bar_open'],None)


def test_closes_only_remainder_and_does_not_reenter(minutes):
    now,prefix,prev=context(minutes,'2026-10-12T10:05:00-04:00');p=position()
    old=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][0]['trade']
    p.update(remaining=.75,legs=[copy.deepcopy(old['legs'][0])],active_wave_high=prev['high'],
        armed_midpoint=dict(reference_t=prev['t'],known_at=prev['t']+900,
            reference_high=prev['high'],reference_low=prev['low'],price=(prev['high']+prev['low'])/2))
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=ApprovedExitReplay(0,9999999999,db);e.position=p;e.prev=prev;e.minutes=prefix;e.bucket=now['t']//900*900
    attempts=[];e.entry=lambda b:attempts.append(b)
    e.minute(now)
    assert e.position is None and not attempts
    assert [l['fraction'] for l in e.trades[0]['legs']]==[.25,.75]
    db.close()


def test_preserves_old_artifacts_and_never_runs_month(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly rerun forbidden'))
    watched=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json',audit.PRIOR]
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    r=audit.review()
    assert not r['month_rerun'] and r['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert sorted(p.name for p in (STORE/'runs').iterdir())==folders
