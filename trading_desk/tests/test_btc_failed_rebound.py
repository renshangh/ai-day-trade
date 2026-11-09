"""Approved failed-rebound exit on real archived >$500 loss paths."""
import copy
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_large_losses as audit
from trading_desk.btc_data import STORE,read,ts
from trading_desk.btc_engine import create_replay,aggregate
from trading_desk.btc_failed_rebound import POLICY


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_five_original_entries_stops_and_baseline_exits_are_preserved(reviewed):
    assert [c['old_trade_id'] for c in reviewed['cases']]==[5,11,12,23,32]
    old=read(STORE/'runs'/audit.BASELINE/'result.json')
    for c in reviewed['cases']:
        original=next(p for p in old['trades'] if p['id']==c['old_trade_id'])
        assert c['before']['legs']==original['legs']
        for key in ('entry_time','entry','initial_stop','t1'):
            assert c['after'][key]==original[key]
        assert c['after']['remaining']==0


def test_loss_five_has_no_completed_turn_before_eight_minute_stop(reviewed):
    c=reviewed['cases'][0]
    assert c['after']['legs']==c['before']['legs']
    assert c['after']['net']==pytest.approx(-762.7505927499553)
    assert not c['after']['failed_rebound_history']


def test_confirmed_structure_exits_reduce_four_losses_without_500_cap(reviewed):
    expected={11:('2026-10-23T19:08:00Z',-327.6036062999973),
        12:('2026-10-24T09:19:00Z',-395.54357539998733),
        23:('2026-10-30T18:00:00Z',-482.78208549999545),
        32:('2026-11-05T22:47:00Z',-732.6663634999907)}
    for c in reviewed['cases'][1:]:
        p=c['after'];time,net=expected[c['old_trade_id']]
        assert p['legs'][-1]['reason']=='failed_rebound_exit_remaining'
        assert p['exit_time']==time and p['net']==pytest.approx(net)
        assert p['net']>c['before']['net']


def test_all_points_are_confirmed_before_reference_activation_and_actual_break(reviewed):
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for c in reviewed['cases'][1:]:
            p=c['after'];e=p['case_exit_evidence'][-1];a=e['failed_rebound']
            h,l,lh=(a[k] for k in ('high','low','lower_high'))
            assert h['time']<l['time']<lh['time']
            assert l['price']<lh['price']<h['price']
            assert max(h['known_at'],l['known_at'],lh['known_at'])<=a['effective_at']<=ts(e['time_utc'])
            for point,kind in [(h,'high'),(l,'low'),(lh,'high')]:
                rows=db.execute('SELECT t,h,l FROM minutes WHERE t>=? AND t<? ORDER BY t',
                    (point['bar_time']-900,point['bar_time']+1800)).fetchall()
                assert len(rows)==45
                index=1 if kind=='high' else 2;fn=max if kind=='high' else min
                vals=[fn(row[index] for row in rows[i:i+15]) for i in (0,15,30)]
                assert vals[1]==point['price']
                assert (vals[1]>max(vals[0],vals[2])) if kind=='high' else (vals[1]<min(vals[0],vals[2]))
            observed=db.execute('SELECT o,l FROM minutes WHERE t=?',(ts(e['time_utc']),)).fetchone()
            assert observed is not None and observed[1]<a['price']
            expected=observed[0] if observed[0]<a['price'] else a['price']
            assert e['price']==expected and e['fraction']==1


def test_gap_cannot_revoke_a_previously_confirmed_reference(reviewed):
    p=reviewed['cases'][2]['after'];e=p['case_exit_evidence'][-1]
    assert e['failed_rebound']['gap_exposed'] is True
    assert p['gap_exposed'] is True
    assert e['failed_rebound']['effective_at']<ts('2026-10-24T02:48:00-04:00')<ts(e['time_utc'])


def test_partial_final_candle_exposes_actual_observation_end(reviewed):
    last=reviewed['cases'][0]['rows'][-1]
    assert last['time']=='2026-10-15T13:45:00Z'
    assert last['observed_minutes']==9 and last['is_complete'] is False
    assert last['observed_end_exclusive']=='2026-10-15T13:54:00Z'
    assert last['end']=='2026-10-15T14:00:00Z' # Theoretical bucket end, not extra observations.


def test_observed_reclaim_invalidates_the_earlier_lh_before_new_confirmation(reviewed):
    c=reviewed['cases'][1]
    reclaim=next(e for row in c['rows'] for e in row['events']
        if e['type']=='failed_rebound_reclaimed')
    assert reclaim['time_utc']=='2026-10-23T16:34:00Z'
    final=c['after']['case_exit_evidence'][-1]['failed_rebound']
    assert final['lower_high']['known_at']>ts(reclaim['time_utc'])


def test_new_factory_and_historical_version_are_distinct():
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    current=create_replay(0,9999999999,db)
    previous=create_replay(0,9999999999,db,exit_version='turning_consumed_v7')
    assert current.policy==POLICY and current.consume_entry_history
    assert previous.policy!=POLICY and previous.consume_entry_history
    assert current.cfg.first_sale_fraction==previous.cfg.first_sale_fraction==.25
    assert current.cfg.one_way_friction_bps==previous.cfg.one_way_friction_bps==2
    db.close()
