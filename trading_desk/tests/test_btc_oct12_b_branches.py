"""Expanded B1/B2 on preserved October 12 minutes, never invented OHLC."""
import copy
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_b_branches as audit
from trading_desk import btc_engine
from trading_desk.btc_data import STORE,ts
from trading_desk.btc_entry_detector import EntryDetector
from trading_desk.btc_shock_branches import ExpandedEntryDetector,expanded_shock_setup


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_morning_first_reversal_has_no_fabricated_hl_and_no_future_d(reviewed):
    c=reviewed['cases'][0];s=c['signal'];w=s['setup_evidence']
    assert s['route']=='B1' and s['qualified_candidate']
    assert s['time_ny']=='2026-10-12T09:33:00-04:00'
    assert s['entry_reference']==pytest.approx(82571.345)
    assert s['references']['l2'] is None and s['rule']=='B1_FIRST_STABILIZATION'
    assert w['d']['price']==82370.1 and w['d']['known_at']==ts('2026-10-12T09:30:00-04:00')
    assert s['initial_stop']==pytest.approx(82323.948375)
    assert s['net_reward_risk']==pytest.approx(1.5147461102007356)
    assert s['rr_warning'] and not s['preferred_rr_met']
    assert all(x['known_at']<=ts(s['time_utc']) for x in w['extensions'])
    # This completed red candle need not have a >=50% lower wick.
    b=w['stabilization_bar'];assert b['close']<b['open']
    assert 0<(b['close']-b['low'])/(b['high']-b['low'])<.5


def test_morning_partial_profit_then_remaining_loss_is_not_hidden(reviewed):
    p=reviewed['cases'][0]['trade'];first,last=p['legs']
    assert first['time_ny']=='2026-10-12T10:11:00-04:00' and first['fraction']==.25
    assert first['price']==pytest.approx(83029.16307785714)
    assert first['net']==pytest.approx(106.17449406039225)
    assert last['time_ny']=='2026-10-12T10:49:00-04:00' and last['fraction']==.75
    assert last['reason']=='stop' and last['price']==p['initial_stop']
    assert last['net']==pytest.approx(-210.28176275624546)
    assert p['net']==pytest.approx(-104.10726869585321)
    assert not p.get('stop_history')


def test_evening_green_extension_belongs_to_same_impulse_before_rebound(reviewed):
    c=reviewed['cases'][1];s=c['signal'];w=s['setup_evidence']
    assert s['route']=='B1' and s['time_ny']=='2026-10-12T21:00:00-04:00'
    assert w['impulse']['t']==ts('2026-10-12T20:00:00-04:00')
    assert w['d']['price']==80942.813 and w['d']['known_at']==ts(s['time_utc'])
    assert w['stabilization_bar']['close']>w['stabilization_bar']['open']
    assert s['entry_reference']==pytest.approx(81397.246)
    assert s['initial_stop']==pytest.approx(80860.50044793599)
    p=c['trade'];assert p['legs'][0]['time_ny']=='2026-10-12T22:57:00-04:00'
    assert p['legs'][1]['time_ny']=='2026-10-12T23:35:00-04:00'
    assert [l['fraction'] for l in p['legs']]==[.25,.75]
    assert p['net']==pytest.approx(1833.696281189417)
    assert not p.get('stop_history')


def test_b2_is_a_separate_later_hl_signal_not_an_automatic_add(reviewed):
    for c,at in zip(reviewed['cases'],['2026-10-12T10:31:00-04:00','2026-10-12T22:53:00-04:00']):
        s=next(s for s in c['later_structure_signals'] if s['route']=='B2')
        assert s['time_ny']==at and s['structural_price_signal']
        assert s['decision']=='held_position' and s['trade_id'] is None
        assert s['references']['l2'] is not None
        assert s['setup_evidence']['d']['price']==c['signal']['setup_evidence']['d']['price']


def test_future_d_or_incomplete_stabilization_never_confirms_b1(reviewed):
    s=reviewed['cases'][0]['signal'];w=copy.deepcopy(s['setup_evidence']);now=ts(s['time_utc'])
    w['d']['known_at']=now+60
    assert not expanded_shock_setup(w,now,'B1')['setup_passed']
    w=copy.deepcopy(s['setup_evidence']);w['stabilization_bar']['observed_minutes']=14
    assert not expanded_shock_setup(w,now,'B1')['setup_passed']
    w=copy.deepcopy(s['setup_evidence']);w['atr_before_impulse']=0
    assert not expanded_shock_setup(w,now,'B1')['setup_passed']


def test_pre_entry_extensions_never_widen_an_existing_stop(reviewed):
    c=reviewed['cases'][0]
    assert c['trade']['initial_stop']==c['trade']['stop']
    assert c['trade']['legs'][-1]['price']==c['signal']['initial_stop']


def test_two_case_review_never_invokes_monthly_or_rewrites_archives(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('monthly run forbidden')
    monkeypatch.setattr(btc_engine,'run',forbidden)
    paths=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    r=audit.review()
    assert not r['month_rerun'] and r['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==v for p,v in before.items())
    # Preview expansion is explicitly opt-in, so existing monthly behavior stays frozen.
    db=sqlite3.connect(':memory:')
    e=audit.ABReplay(0,1,db)
    assert type(e.detector) is EntryDetector
    assert isinstance(audit.NominatedCase(0,db).detector,ExpandedEntryDetector)
    db.close()
