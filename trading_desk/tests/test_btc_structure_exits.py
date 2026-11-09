"""One-case V3 study on real stored Alpaca bars, with no synthetic OHLC."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_structure_exit as audit
from audit_btc_oct12_b_branches import load,FOLDER,local
from trading_desk.btc_data import STORE,ts
from trading_desk.btc_engine import aggregate
from trading_desk.btc_structure_exits import last_minute_state,giveback_diagnostic


@pytest.fixture(scope='module')
def reviewed():return audit.review()


@pytest.fixture(scope='module')
def minutes():return load()[1]


def engine():
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    return audit.Case(db)


def context(minutes,stamp):
    t=ts(stamp);period=t//900*900
    return (next(b for b in minutes if b['t']==t),[b for b in minutes if period<=b['t']<t],
        aggregate([b for b in minutes if period-900<=b['t']<period],900))


def test_first_target_only_and_no_forced_cutoff_exit(reviewed):
    p=reviewed['trade'];old=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][1]['trade']
    assert all(p[k]==old[k] for k in ('entry','entry_time','initial_stop','t1','t2'))
    assert p['status']=='open' and p['remaining']==.75 and p['net'] is None
    assert len(p['legs'])==1 and p['legs'][0]==old['legs'][0]
    assert p['legs'][0]['time_ny']=='2026-10-12T22:57:00-04:00'
    assert reviewed['realized_net']==pytest.approx(383.0192816714264)
    assert p['fixed_second_target_enabled'] is False
    assert not p.get('stop_history')
    assert reviewed['observed_case_minutes']==285
    assert reviewed['rows'][-1]['end']==reviewed['cutoff']


def test_warning_is_not_exit_and_inside_candles_are_retained(reviewed):
    p=reviewed['trade']
    assert [local(e['time_utc'])[11:16] for e in p['midpoint_warnings']]==['22:30','23:00','23:45','01:30']
    assert all(w['action']=='warning_only_no_sale' for w in p['midpoint_warnings'])
    assert not any(l['reason']=='midpoint_exit_all' for l in p['legs'])
    by={local(b['t']):b for b in reviewed['rows']}
    assert by['2026-10-12T23:00:00-04:00']['completed_full_inside']
    assert by['2026-10-13T00:00:00-04:00']['completed_body_inside']
    assert by['2026-10-13T00:45:00-04:00']['completed_full_inside']
    assert not any(e['type'] in ('structure_exit_remaining','wick_exit_all') for b in by.values() for e in b['events'])


def test_structure_confirmation_and_new_high_both_required(reviewed):
    history=reviewed['trade']['structure_history']
    assert [h['price'] for h in history]==[82578.695,82677.245,83153.77,83285.235]
    assert [local(h['effective_at'])[11:16] for h in history]==['23:00','23:45','01:15','01:30']
    candidate=history[2]
    assert local(candidate['known_at'])=='2026-10-13T00:45:00-04:00'
    assert local(candidate['breakout_known_at'])=='2026-10-13T01:15:00-04:00'
    for h in history:
        assert h['effective_at']>=max(h['known_at'],h['breakout_known_at'])
        assert h['breakout_bar']>h['t']
    assert reviewed['trade']['structure_reference']['price']==83285.235


def test_previous_candle_low_is_not_confirmed_swing_low(reviewed):
    final=reviewed['rows'][-1]
    assert final['low']<83508.87 # Single candle low broken at 01:40.
    assert final['low']>final['case_structure_reference']['price']
    assert all(h['price']!=83508.87 for h in reviewed['trade']['structure_history'])


def test_cutoff_valuation_stays_unrealized(reviewed):
    v=reviewed['valuation']
    assert v['price']==83488.2935 and not v['is_exit']
    assert v['source_minute']=='2026-10-13T05:44:00Z'
    assert v['unrealized_gross']==pytest.approx(1568.285625)
    assert v['unrealized_after_entry_cost']==pytest.approx(1556.0760381)
    assert v['hypothetical_roundtrip_net']==pytest.approx(1543.552794075)
    assert v['hypothetical_total_net']==pytest.approx(1926.572075746427)
    assert reviewed['trade'].get('exit_time') is None


def test_giveback_diagnostic_separates_paths_without_new_exit_rule(reviewed,minutes):
    morning,night=reviewed['giveback_comparison']
    assert morning['highest_known_price']==82950
    assert morning['giveback_fraction']==pytest.approx(.4755047470652929)
    assert night['highest_known_price']==82757.985
    assert night['giveback_fraction']==pytest.approx(.0756768932175856)
    for d in (morning,night):
        assert d['action']=='diagnostic_only' and d['threshold'] is None
        assert d['current_minute_range_used'] is False
    # The later high in the unfinished 10:00 candle was NOT known at 10:05.
    future=[b for b in minutes if ts('2026-10-12T10:05:00-04:00')<=b['t']<ts('2026-10-12T10:15:00-04:00')]
    assert max(b['high'] for b in future)==83040.768>morning['highest_known_price']


def test_giveback_never_reads_future_observations(minutes):
    old=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][0]['trade']
    now,_,_=context(minutes,'2026-10-12T10:05:00-04:00')
    args=(old['entry'],old['initial_stop'],ts(old['entry_time']),now)
    full=giveback_diagnostic(*args,minutes,82769.94775)
    prefix=giveback_diagnostic(*args,[b for b in minutes if b['t']<now['t']],82769.94775)
    assert full==prefix


def test_last_minute_does_not_use_final_colour_or_final_minute_range(minutes):
    now,prefix,prev=context(minutes,'2026-10-13T01:29:00-04:00')
    s=last_minute_state(now,prefix,prev)
    assert not s['non_green'] and not s['direction_passed']
    assert s['reference_price']==83659.85
    assert s['observed_high']==max(now['open'],max(b['high'] for b in prefix))
    assert s['upper_wick_fraction']==pytest.approx(.5087365372726073)
    assert last_minute_state(now,prefix[1:],prev) is None
    now,prefix,prev=context(minutes,'2026-10-12T23:14:00-04:00')
    assert last_minute_state(now,prefix,prev)['full_range_inside']


def test_later_observations_do_not_backdate_structure_references(minutes):
    e=engine();cut=ts('2026-10-13T00:45:00-04:00')
    before=[b for b in minutes if b['t']<cut]
    after=[b for b in minutes if cut<=b['t']<audit.CUTOFF]
    for b in before:e.minute(b)
    # The completed 00:30 candle is processed on the first actual 00:45 minute.
    e.minute(after[0]);history=copy.deepcopy(e.position['structure_history'])
    assert history[-1]['price']==82677.245
    for b in after[1:]:e.minute(b)
    assert history==e.position['structure_history'][:len(history)]
    assert e.position['structure_reference']['price']==83285.235
    e.db.close()


def test_protective_stop_cannot_be_vetoed_by_inside_exemption(minutes,reviewed):
    now,prefix,prev=context(minutes,'2026-10-12T23:14:00-04:00')
    e=engine();p=copy.deepcopy(reviewed['trade']);p.update(status='open',net=None,remaining=.75)
    # Hypothetical protective control at a real observed price, no edited OHLC.
    p['stop']=now['open'];e.position=p;e.minutes=prefix;e.prev=prev;e.bucket=now['t']//900*900
    e.apply_exits(now)
    assert e.position is None
    assert e.trades[0]['legs'][-1]['reason']=='stop'
    assert e.trades[0]['legs'][-1]['fraction']==.75
    e.db.close()


def test_confirmed_structure_control_closes_only_remaining_quantity(minutes,reviewed):
    now,prefix,prev=context(minutes,'2026-10-13T01:40:00-04:00')
    e=engine();p=copy.deepcopy(reviewed['trade'])
    # Hypothetical active structural control at the actual previous-bar low.
    # This checks execution only; the actual audit correctly rejects this low
    # as unconfirmed. Market bars remain completely unchanged.
    p['structure_reference']=dict(price=prev['low'],effective_at=prev['t']+900)
    assert now['open']>prev['low']>now['low']
    e.position=p;e.minutes=prefix;e.prev=prev
    e.apply_exits(now)
    assert e.position is None and e.trades[0]['remaining']==0
    assert [l['fraction'] for l in e.trades[0]['legs']]==[.25,.75]
    assert e.trades[0]['legs'][-1]['reason']=='structure_exit_remaining'
    assert e.trades[0]['legs'][-1]['price']==prev['low']
    e.db.close()


def test_existing_results_and_month_registry_never_change(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('No monthly run authorized'))
    paths=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json',
        FOLDER.parent/'oct12_direction_filtered_exits/REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=audit.review()
    assert not r['month_rerun'] and r['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
