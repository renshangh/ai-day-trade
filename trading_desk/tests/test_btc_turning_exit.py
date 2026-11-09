"""Approved new-high-failure policy, using only archived real observations."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_turning_exit as audit
from trading_desk.btc_data import ts,STORE
from trading_desk.btc_engine import aggregate,create_replay
from trading_desk.btc_turning_replay import turning_observation,POLICY


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_night_exit_and_total_pnl_match_reviewed_turning_point(reviewed):
    c=reviewed['cases'][1];p=c['trade']
    assert p['status']=='closed' and p['remaining']==0
    assert [l['fraction'] for l in p['legs']]==[.25,.75]
    assert p['legs'][0]['time_utc']=='2026-10-13T02:57:00Z'
    l=p['legs'][1]
    assert l['time_utc']=='2026-10-13T08:29:00Z' and l['price']==83835.33
    assert l['reason']=='turning_exit_remaining'
    assert l['gross']==pytest.approx(1828.563)
    assert l['cost']==pytest.approx(24.7848864)
    assert l['net']==pytest.approx(1803.7781136)
    assert c['realized_net']==pytest.approx(2186.7973952714283)
    assert reviewed['exit_net_change']==pytest.approx(213.394187625003)


def test_only_0429_qualifies_and_0144_is_rejected_for_not_making_new_high(reviewed):
    p=reviewed['cases'][1]['trade'];observations=p['turning_observations']
    qualified=[d for d in observations if d['qualified']]
    assert [d['time_utc'] for d in qualified]==['2026-10-13T08:29:00Z']
    early=next(d for d in observations if d['time_utc']=='2026-10-13T05:44:00Z')
    assert early['red_at_observation'] and early['non_inside'] and early['below_midpoint']
    assert not early['new_wave_high'] and 'no_current_new_wave_high' in early['blocked_by']
    final=qualified[0]
    assert final['observed_high']==84073.29445>final['prior_wave_high']==84068.5755
    assert final['previous_midpoint']==pytest.approx(83915.67925)
    assert final['prior_range_retracement']==pytest.approx(.7627574253783089)
    assert final['upper_wick_fraction']==0 # This is not a wick-only rule.


def test_does_not_wait_for_trade_level_half_giveback(reviewed):
    p=reviewed['cases'][1]['trade']
    guard=p['giveback_observations'][-1]
    assert guard['giveback_fraction']==pytest.approx(.08892381974623789)
    assert guard['giveback_fraction']<.5
    assert not guard['qualified']
    assert p['case_exit_evidence'][-1]['turning']['qualified']


def test_morning_entry_targets_and_profit_exit_are_unchanged(reviewed):
    previous=json.loads((audit.FOLDER.parent/'oct12_approved_profit_guard/REVIEW.json').read_text())
    assert reviewed['cases'][0]['trade']['legs']==previous['cases'][0]['trade']['legs']
    assert reviewed['cases'][0]['realized_net']==pytest.approx(218.89633641039558)


def test_last_minute_only_and_no_current_minute_or_future_close_reads(reviewed):
    _,m=audit.load();t=ts('2026-10-13T04:29:00-04:00');period=t//900*900
    now=next(b for b in m if b['t']==t);prefix=[b for b in m if period<=b['t']<t]
    prev=aggregate([b for b in m if period-900<=b['t']<period],900)
    class OpenOnly(dict):
        def __getitem__(self,key):
            if key in ('high','low','close'):raise AssertionError('Unfinished minute read')
            return super().__getitem__(key)
    p=copy.deepcopy(reviewed['cases'][1]['trade'])
    d=turning_observation(p,OpenOnly(now),prefix,prev)
    assert d['qualified'] and d['reference_price']==now['open']
    assert not d['current_minute_range_used']
    assert turning_observation(p,now,prefix[1:],prev) is None
    earlier=next(b for b in m if b['t']==t-60)
    assert turning_observation(p,earlier,prefix[:-1],prev) is None
    partial=aggregate([b for b in m if period-900<=b['t']<period-60],900)
    assert not turning_observation(p,now,prefix,partial)['qualified']


def test_version_dispatch_preserves_old_v4_and_v5_with_current_failed_rebound():
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    from trading_desk.btc_failed_rebound import POLICY as CURRENT
    assert create_replay(0,9999999999,db).policy==CURRENT
    assert create_replay(0,9999999999,db,exit_version='turning_consumed_v7').policy==POLICY
    assert create_replay(0,9999999999,db,exit_version='turning_v5').policy==POLICY
    from trading_desk.btc_guarded_replay import POLICY as V4
    assert create_replay(0,9999999999,db,exit_version='guarded_v4').policy==V4
    with pytest.raises(ValueError):create_replay(0,9999999999,db,exit_version='unknown')
    db.close()


def test_no_month_rerun_or_historical_file_mutation(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly rerun forbidden'))
    paths=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json']+list(audit.FOLDER.parent.glob('*/REVIEW.json'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=audit.review();assert not r['month_rerun'] and r['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
