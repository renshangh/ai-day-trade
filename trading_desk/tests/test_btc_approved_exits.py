"""Approved exits on real archived minutes, including causal ordering edges."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_approved_exits as audit
from audit_btc_oct12_b_branches import load,FOLDER
from trading_desk.btc_data import STORE,ts
from trading_desk.btc_engine import aggregate,Replay
from trading_desk.btc_approved_exits import ApprovedExitReplay,candidates


@pytest.fixture(scope='module')
def reviewed():return audit.review()


@pytest.fixture(scope='module')
def source():return load()[1]


def state():
    # Hypothetical carried strategy state from the frozen morning trade;
    # market OHLC is never edited or synthesized for edge cases.
    p=copy.deepcopy(json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][0]['trade'])
    p.update(status='open',remaining=1.,legs=[],peak=82946.42,peak_before_period=82946.42,
        pending_lows=[],
        stop=p['initial_stop'],active_wave_high=82946.42,
        armed_midpoint=dict(reference_t=ts('2026-10-12T09:45:00-04:00'),
            known_at=ts('2026-10-12T10:00:00-04:00'),reference_high=82946.42,
            reference_low=82593.4755,price=82769.94775))
    return p


def engine():
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    return ApprovedExitReplay(0,9999999999,db,exit_policy="approved_v1")


def minute_at(source,clock):return next(b for b in source if b['t']==ts('2026-10-12T'+clock+':00-04:00'))


def test_two_entries_and_protection_targets_unchanged_earliest_program_exits(reviewed):
    morning,night=reviewed['cases']
    for c in (morning,night):
        p,old=c['trade'],c['original_trade']
        assert all(p[k]==old[k] for k in ('entry_time','entry','initial_stop','t1','t2'))
        assert len(p['legs'])==1 and p['legs'][0]['fraction']==1
        assert not p.get('stop_history')
    p=morning['trade'];leg=p['legs'][0]
    assert leg['reason']=='midpoint_exit_all' and leg['time_ny']=='2026-10-12T10:05:00-04:00'
    assert leg['price']==pytest.approx(82769.94775)
    assert p['net']==pytest.approx(165.53449145)
    p=night['trade'];leg=p['legs'][0]
    assert leg['reason']=='wick_exit_all' and leg['time_ny']=='2026-10-12T22:29:00-04:00'
    assert leg['price']==82637.3 and p['net']==pytest.approx(1207.2470908)
    e=p['active_exit_events'][0]
    assert e['upper_wick_fraction']==pytest.approx(.7479583348768211)
    assert not e['integer_watch_gate']


def test_midpoint_reference_known_only_at_close_and_not_canceled_by_current_high(reviewed):
    rows=reviewed['cases'][0]['rows'];armed=next(e for b in rows for e in b['events'] if e['type']=='midpoint_armed')
    assert armed['reference_bar']=='2026-10-12T13:45:00Z'
    assert armed['effective_time']=='2026-10-12T14:00:00Z'
    assert armed['expires']=='2026-10-12T14:15:00Z'
    assert armed['price']==pytest.approx(82769.94775)
    assert reviewed['cases'][0]['trade']['legs'][0]['time_utc']=='2026-10-12T14:05:00Z'


def test_midpoint_only_applies_to_next_bar(source):
    p=state();now=minute_at(source,'10:15')
    assert not any(c['reason']=='midpoint_exit_all' for c in candidates(p,now,[],policy="v1"))


def test_open_gap_below_midpoint_uses_observed_open(source):
    p=state();p['armed_midpoint']=dict(reference_t=ts('2026-10-12T10:00:00-04:00'),
        known_at=ts('2026-10-12T10:15:00-04:00'),reference_high=83040.768,
        reference_low=82732.55,price=82886.659)
    result=candidates(p,minute_at(source,'10:15'),[],policy="v1")
    c=next(c for c in result if c['reason']=='midpoint_exit_all')
    assert c['phase']==0 and c['price']==82844.255<82886.659


def test_last_minute_open_wick_precedes_later_stop_and_exits_remaining_only(source):
    e=engine();p=state();p['armed_midpoint']=None
    original=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][0]['trade']
    p.update(remaining=.75,legs=[copy.deepcopy(original['legs'][0])],stop=82839.7135)
    e.position=p
    period=ts('2026-10-12T10:00:00-04:00');now=minute_at(source,'10:14')
    e.minutes=[b for b in source if period<=b['t']<now['t']];e.bucket=period;e.last_minute=now['t']-60
    e.minute(now)
    assert e.position is None
    assert [l['fraction'] for l in e.trades[0]['legs']]==[.25,.75]
    assert e.trades[0]['legs'][-1]['reason']=='wick_exit_all'
    assert e.trades[0]['legs'][-1]['price']==now['open']
    assert e.trades[0]['net']==pytest.approx(286.36334031039223)


def test_incomplete_prefix_cannot_generate_a_wick(source):
    p=state();p['armed_midpoint']=None;now=minute_at(source,'10:14')
    prefix=[b for b in source if now['t']-840<=b['t']<now['t']]
    assert len(prefix)==14
    assert any(c['reason']=='wick_exit_all' for c in candidates(p,now,prefix,policy="v1"))
    assert not any(c['reason']=='wick_exit_all' for c in candidates(p,now,prefix[:5]+prefix[6:],policy="v1"))


def test_known_open_target_precedes_later_range_midpoint(source):
    e=engine();p=state();now=minute_at(source,'10:05')
    # A hypothetical target at the actual already-observed 10:04 close.
    p['t1']=minute_at(source,'10:04')['close'];p['t2']=None
    e.position=p;e.bucket=now['t']//900*900;e.minute(now)
    legs=e.trades[0]['legs']
    assert [l['reason'] for l in legs]==['target_25','midpoint_exit_all']
    assert [l['fraction'] for l in legs]==[.25,.75]


def test_unknown_range_order_is_flagged_and_stop_prioritized(source):
    e=engine();p=state();now=minute_at(source,'10:05')
    p['stop']=now['low'] # hypothetical protective state, real OHLC untouched
    p['t1']=None;p['t2']=None;e.position=p;e.bucket=now['t']//900*900
    e.minute(now);p=e.trades[0]
    assert p['legs'][0]['reason']=='stop'
    assert p['same_minute_exit_ambiguity']
    assert p['exit_order_audit'][0]['chosen']=='stop'
    assert set(p['exit_order_audit'][0]['candidates'])=={'stop','midpoint_exit_all'}


def test_whole_exit_never_reenters_same_minute(source):
    e=engine();e.position=state();now=minute_at(source,'10:05');e.bucket=now['t']//900*900
    attempted=[];e.entry=lambda b:attempted.append(b)
    e.minute(now)
    assert not attempted and len(e.trades[0]['legs'])==1 and e.position is None


def test_only_complete_post_entry_bar_arms_midpoint(source):
    e=engine();p=state();p['armed_midpoint']=None;e.position=p
    period=ts('2026-10-12T09:45:00-04:00')
    rows=[b for b in source if period<=b['t']<period+900]
    e.minutes=rows[:5]+rows[6:];e.bucket=period
    # No prior bar is needed for this isolated coverage check; no prices are filled.
    e.complete()
    assert e.position['armed_midpoint'] is None and len(e.minutes)==14


def test_legacy_mode_keeps_earlier_artifacts_and_does_not_run_a_month(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('monthly rerun forbidden'))
    watched=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    result=audit.review()
    assert not result['month_rerun'] and result['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert sorted(p.name for p in (STORE/'runs').iterdir())==folders
    assert ApprovedExitReplay.close_part is Replay.close_part
    assert ApprovedExitReplay.targets is Replay.targets
