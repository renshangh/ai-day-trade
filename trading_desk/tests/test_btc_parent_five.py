"""Causal PH5 checks on archived real observations; no synthetic market bars."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_parent_five import ParentFiveDetector, five_signal
from trading_desk.btc_data import ts


@pytest.fixture
def actual():
    return json.loads((Path(__file__).parent/'fixtures/ph5_bounce_20261114.json').read_text())


def test_parent_is_not_replaced_by_higher_internal_pullback(actual):
    d=ParentFiveDetector()
    states=[]
    for bar in actual['fifteen']:
        d.observe(bar)
        states.append((bar['t']+900,copy.deepcopy(d.parent),d.ready(actual['signal']['atr'])))
    base=61991.3285
    after=[p for t,p,_ in states if t>=ts('2026-11-15T02:15:00Z')]
    assert after and all(p['price']==base for p in after)
    assert not next(s for t,_,s in states if t==ts('2026-11-15T04:15:00Z'))
    setup=next(s for t,_,s in states if t==ts('2026-11-15T04:30:00Z'))
    assert setup['hl']['price']==64620.6
    assert setup['known_at']==ts('2026-11-15T04:30:00Z')


def test_exact_bounce_trigger_risk_and_price_from_real_minute(actual):
    old=actual['signal']
    s=five_signal(old['setup_evidence'],old['hold_bar'],actual['minute'],old['atr'],old['t1'])
    assert s['qualified_candidate']
    assert s['entry_reference']==pytest.approx(64826.61)
    assert s['initial_stop']==pytest.approx(61846.56581280788)
    assert s['initial_stop']==pytest.approx(old['setup_evidence']['parent']['price']-.25*old['atr'])
    assert s['net_reward_risk']==pytest.approx(old['net_reward_risk'])
    assert not s['preferred_rr_met'] and s['net_reward_risk']>0  # 2R advisory


def test_future_confirmation_or_nonadjacent_hold_cannot_be_used(actual):
    s=actual['signal'];setup=copy.deepcopy(s['setup_evidence'])
    setup['known_at']=actual['minute']['t']+60  # Fault injection: not a price/bar.
    assert not five_signal(setup,s['hold_bar'],actual['minute'],s['atr'],s['t1'])['qualified_candidate']
    other=actual['fifteen'][-1]
    assert not five_signal(s['setup_evidence'],other,actual['minute'],s['atr'],s['t1'])['qualified_candidate']


def test_gap_and_consumed_entry_clear_old_parent(actual):
    d=ParentFiveDetector()
    for bar in actual['fifteen']:
        d.observe(bar)
    assert d.ready(actual['signal']['atr'])
    floor=ts(actual['signal']['time_utc'])//900*900+900
    d.reset(floor)
    for bar in actual['fifteen']:
        d.observe(bar)
    assert not d.ready(actual['signal']['atr'])
    assert not d.parent
    d.reset()
    for bar in actual['fifteen'][:-2]:d.observe(bar)
    d.observe(actual['fifteen'][-1])  # Missing middle interval stays absent.
    assert not d.ready(actual['signal']['atr'])


def test_parent_needs_independent_completed_holds(actual):
    d=ParentFiveDetector()
    for bar in actual['fifteen']:
        if bar['t']+900>ts('2026-11-15T02:15:00Z'):break
        d.observe(bar)
    assert d.parent['price']==61991.3285
    assert d.parent['independence_at'] is None
    assert d.parent['holds']==1
    d.observe(next(b for b in actual['fifteen'] if b['t']==ts('2026-11-15T02:15:00Z')))
    assert d.parent['independence_at']==ts('2026-11-15T02:30:00Z')
