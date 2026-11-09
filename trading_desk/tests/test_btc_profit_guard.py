"""Approved current policy on archived bars; no synthetic market observations."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_profit_guard as audit
from trading_desk.btc_data import STORE,ts
from trading_desk.btc_engine import aggregate,create_replay
from trading_desk.btc_guarded_replay import GuardedABReplay,guard_observation,POLICY


@pytest.fixture(scope='module')
def reviewed():return audit.review()


@pytest.fixture(scope='module')
def minutes():return audit.load()[1]


def context(minutes,stamp):
    t=ts(stamp);period=t//900*900
    return (next(b for b in minutes if b['t']==t),[b for b in minutes if period<=b['t']<t],
        aggregate([b for b in minutes if period-900<=b['t']<period],900))


def db():
    c=sqlite3.connect(':memory:');c.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)');return c


def test_default_factory_uses_approved_guard_without_starting_any_run():
    connection=db();e=create_replay(0,9999999999,connection)
    from trading_desk.btc_turning_replay import TurningABReplay
    from trading_desk.btc_failed_rebound import POLICY as CURRENT_POLICY
    assert isinstance(e,TurningABReplay) and e.policy==CURRENT_POLICY
    assert e.cfg.first_sale_fraction==.25
    assert e.cfg.one_way_friction_bps==2
    assert 'profit-guard' in e.cfg.version
    connection.close()


def test_approved_two_case_results_match_previous_selected_hypothesis(reviewed):
    morning,night=reviewed['cases']
    assert reviewed['rule_approved'] and not reviewed['month_rerun'] and reviewed['broker_orders']==0
    for c in (morning,night):assert c['matches_prior_hypothesis'] and c['parameters_unchanged']
    p=morning['trade']
    assert p['status']=='closed' and p['remaining']==0
    assert [l['reason'] for l in p['legs']]==['target_25','giveback_exit_remaining']
    assert [l['fraction'] for l in p['legs']]==[.25,.75]
    assert [l['time_utc'] for l in p['legs']]==['2026-10-12T14:11:00Z','2026-10-12T14:19:00Z']
    assert p['legs'][1]['price']==82754.706
    assert morning['realized_net']==pytest.approx(218.89633641039558)
    p=night['trade']
    assert p['status']=='open' and p['remaining']==.75 and p['net'] is None
    assert len(p['legs'])==1 and p['legs'][0]['reason']=='target_25'
    assert night['realized_net']==pytest.approx(383.0192816714264)
    assert night['valuation']['is_exit'] is False
    assert night['valuation']['unrealized_gross']==pytest.approx(1568.285625)
    assert p['fixed_second_target_enabled'] is False


def test_inside_holds_even_when_half_giveback_and_direction_pass(reviewed):
    p=reviewed['cases'][0]['trade'];by={d['time_utc']:d for d in p['giveback_observations']}
    for t in ('2026-10-12T14:06:00Z','2026-10-12T14:17:00Z','2026-10-12T14:18:00Z'):
        d=by[t]
        assert d['armed'] and d['giveback_fraction']>=.5
        assert d['non_green'] and d['not_above_previous_close']
        assert 'inside_previous_candle' in d['blocked_by'] and not d['qualified']
    d=by['2026-10-12T14:19:00Z']
    assert d['qualified'] and not d['full_range_inside'] and not d['body_inside']
    assert d['giveback_fraction']==pytest.approx(.6093906774912897)


def test_initial_r_and_peaks_are_not_rebased_after_partial_sale(reviewed,minutes):
    for c in reviewed['cases']:
        p=c['trade'];risk=p['entry']-p['initial_stop']
        assert all(d['initial_risk']==risk for d in p['giveback_observations'])
        highs=[d['highest_known_price'] for d in p['giveback_observations']]
        assert highs==sorted(highs)
    p=copy.deepcopy(reviewed['cases'][0]['trade']);now,prefix,prev=context(minutes,'2026-10-12T10:19:00-04:00')
    p['stop']=now['open'] # Hypothetical stop raise; original initial risk stays fixed.
    d=guard_observation(p,now,prefix,prev,83040.768)
    assert d['initial_risk']==pytest.approx(247.396625)


def test_current_minute_high_low_close_are_inaccessible_to_guard(reviewed,minutes):
    class OpeningOnly(dict):
        def __getitem__(self,key):
            if key in ('high','low','close'):raise AssertionError('Unfinished minute accessed')
            return super().__getitem__(key)
    p=reviewed['cases'][0]['trade'];now,prefix,prev=context(minutes,'2026-10-12T10:05:00-04:00')
    d=guard_observation(p,OpeningOnly(now),prefix,prev,82950)
    assert d['highest_known_price']==82950
    assert not d['qualified'] # Only 33.5% given back at this opening, not a later low.
    assert not d['current_minute_range_used']


def test_unarmed_and_green_references_cannot_trigger(reviewed):
    first=reviewed['cases'][0]['trade']['giveback_observations']
    assert any(not d['armed'] and 'maximum_favourable_excursion_below_initial_1r' in d['blocked_by'] for d in first)
    assert all(not d['qualified'] for d in first if not d['armed'])
    night=reviewed['cases'][1]['trade']['giveback_observations']
    assert any(d['armed'] and not d['non_green'] for d in night)
    assert not any(d['qualified'] for d in night)


def test_gap_in_prefix_or_incomplete_previous_candle_withholds_guard(reviewed,minutes):
    p=reviewed['cases'][0]['trade'];now,prefix,prev=context(minutes,'2026-10-12T10:19:00-04:00')
    assert guard_observation(p,now,prefix,prev,83040.768)['qualified']
    for actual_prefix,actual_prev in ((prefix[1:],prev),(prefix[:-1],prev),(prefix,None)):
        d=guard_observation(p,now,actual_prefix,actual_prev,83040.768)
        assert not d['qualified'] and not d['reference_context_complete']
    partial=aggregate([b for b in minutes if prev['t']<=b['t']<prev['t']+840],900)
    assert not guard_observation(p,now,prefix,partial,83040.768)['qualified']


@pytest.mark.parametrize('protective_kind',['stop','structure'])
def test_hard_and_structure_opening_events_precede_profit_guard(reviewed,minutes,protective_kind):
    now,prefix,prev=context(minutes,'2026-10-12T10:19:00-04:00');connection=db()
    e=create_replay(0,9999999999,connection)
    p=copy.deepcopy(reviewed['cases'][0]['trade']);p.update(status='open',remaining=.75,net=None,legs=p['legs'][:1])
    p['giveback_state']['highest_completed_peak']=83040.768
    if protective_kind=='stop':p['stop']=now['open']
    else:p['structure_reference']=dict(price=prev['high'],effective_at=prev['t']+900)
    e.position=p;e.minutes=prefix;e.prev=prev;e.apply_exits(now)
    assert e.position is None
    reason='stop' if protective_kind=='stop' else 'structure_exit_remaining'
    assert e.trades[0]['legs'][-1]['reason']==reason
    assert e.trades[0]['legs'][-1]['fraction']==.75
    connection.close()


def test_no_same_minute_reentry_or_duplicate_sales_after_guard(reviewed,minutes):
    connection=db();cut=ts('2026-10-12T11:00:00-04:00')
    e=audit.engine_for_case(ts('2026-10-12T09:30:00-04:00'),cut,connection)
    for b in minutes:
        if b['t']>=cut:break
        e.minute(b)
    r=e.finish();assert len(r['trades'])==1
    assert sum(l['fraction'] for l in r['trades'][0]['legs'])==1
    assert e.position_id==1 and e.position is None
    connection.close()


def test_month_and_all_previous_review_artifacts_preserved(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('No monthly run authorized'))
    paths=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json']+list(audit.FOLDER.parent.glob('*/REVIEW.json'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    audit.review()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
