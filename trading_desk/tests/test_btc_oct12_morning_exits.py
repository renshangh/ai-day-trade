"""Real-minute audit of original stops versus already-approved active exits."""
import hashlib
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_morning_exits as audit
from trading_desk.btc_data import ts,STORE


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_no_confirmed_new_low_and_no_automatic_target_breakeven(reviewed):
    a=reviewed['stop_audit']
    assert not a['automatic_breakeven_on_target']
    assert a['new_confirmed_hour_lows_before_exit']==[]
    assert a['new_confirmed_15m_lows_before_exit']==[]
    assert not a['stop_history'] and a['initial_stop']==pytest.approx(82323.948375)
    assert a['highest_after_b2_hl']==82962.03<a['higher_wave_peak']==83040.768
    assert a['b2_candidate_stop']<a['initial_stop']
    assert a['b2_stop_does_not_replace_held_b1']


def test_midpoint_known_before_cross_and_before_first_target(reviewed):
    e=reviewed['first_approved_exit']
    assert e['reference_bar']=='2026-10-12T09:45:00-04:00'
    assert e['reference_known_at']=='2026-10-12T10:00:00-04:00'
    assert e['time']=='2026-10-12T10:05:00-04:00'
    assert e['threshold']==pytest.approx(82769.94775)
    assert e['threshold']==(e['reference_high']+e['reference_low'])/2
    m=reviewed['critical_minutes']['10:05']
    assert m['open']>e['threshold']>m['low']
    assert ts(e['time'])<ts(reviewed['original_case']['trade']['legs'][0]['time_utc'])
    path=reviewed['paths']['approved_earliest']
    assert not path['first_25_target_occurs']
    assert len(path['legs'])==1 and path['legs'][0]['fraction']==1
    assert path['net']==pytest.approx(165.53449145)


def test_pre_entry_rebound_anchor_does_not_change_earliest_exit(reviewed):
    p=reviewed['prior_rebound']
    assert p['price']==82886.91 and p['known_at']=='2026-10-12T09:00:00-04:00'
    assert ts(p['known_at'])<ts(reviewed['original_case']['trade']['entry_time'])
    assert [(e['type'],e['time']) for e in reviewed['stored_local_anchor_events']]==[
        (e['type'],e['time']) for e in reviewed['approved_exit_events']]


def test_current_bar_new_high_does_not_silently_cancel_previous_midpoint(reviewed):
    b=next(b for b in reviewed['chronological_bars'] if b['start_ny'][11:16]=='10:00')
    assert b['first_high_break']=='2026-10-12T10:00:00-04:00'
    assert b['previous_wave_high']==82946.42
    assert reviewed['first_approved_exit']['time']=='2026-10-12T10:05:00-04:00'


def test_last_minute_wick_uses_prior_14_minutes_and_current_open_only(reviewed):
    _,minutes=audit.load()
    period=ts('2026-10-12T10:00:00-04:00');now=period+840
    prefix=[b for b in minutes if period<=b['t']<now]
    assert [b['t'] for b in prefix]==list(range(period,now,60))
    current=reviewed['critical_minutes']['10:14']
    h=max(current['open'],max(b['high'] for b in prefix))
    lo=min(current['open'],min(b['low'] for b in prefix))
    ratio=(h-max(prefix[0]['open'],current['open']))/(h-lo)
    assert ratio==pytest.approx(.5417529151444962)
    gate=reviewed['original_wick_gate']
    assert gate['new_high'] and gate['shape_passed']
    assert gate['watch']==82000
    assert not gate['watch_above_entry'] and not gate['observation_below_watch']
    path=reviewed['paths']['conditional_after_target_wick']
    assert path['conditional_after_earlier_full_exit']
    assert [l['fraction'] for l in path['legs']]==[.25,.75]
    assert path['net']==pytest.approx(286.36334031039223)


def test_later_gap_below_midpoint_uses_observed_open_not_better_threshold(reviewed):
    e=reviewed['approved_exit_events'][-1]
    assert e['time']=='2026-10-12T10:15:00-04:00'
    assert e['threshold']==82886.659
    assert e['price']==reviewed['critical_minutes']['10:15']['open']==82844.255
    assert e['conditional_after_earlier_exit']
    assert reviewed['paths']['conditional_later_midpoint']['net']==pytest.approx(286.04465406039225)


def test_full_15m_table_and_original_loss_preserved(reviewed):
    assert [b['start_ny'][11:16] for b in reviewed['chronological_bars']]==[
        '09:30','09:45','10:00','10:15','10:30','10:45']
    assert all(b['observed_minutes']==15 for b in reviewed['chronological_bars'])
    assert not reviewed['chronological_bars'][-1]['completed_before_original_exit']
    assert reviewed['paths']['original']['net']==pytest.approx(-104.10726869585321)
    assert reviewed['paths']['original']['legs'][0]['net']==pytest.approx(106.17449406039225)
    assert reviewed['paths']['original']['legs'][1]['net']==pytest.approx(-210.28176275624546)


def test_no_month_run_or_archive_mutation(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('monthly run prohibited'))
    watched=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json',audit.FOLDER/'B_BRANCH_REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    r=audit.review()
    assert r['month_rerun'] is False and r['orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
