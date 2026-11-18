"""C research causality and isolation using the actual Nov 9 observation prefix."""
import copy
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.retest_btc_parent_hl import case_first
from trading_desk.btc_parent_hl import ParentHLDetector,ContinuationBaselineReplay,ContinuationEarlyReplay
from trading_desk.btc_p1 import P1BaselineReplay,P1EarlyReplay
from trading_desk.btc_data import ts


@pytest.fixture(scope='module')
def case():
    return case_first()


def test_Nov9_case_arms_at_0315_and_crosses_in_0317_minute(case):
    s=case['signal'];assert s['time_utc']=='2026-11-09T08:17:00Z'
    assert s['qualified_candidate'] and s['entry_reference']==pytest.approx(73867.005)
    assert not case['trace'][0]['armed'] and case['trace'][1]['armed']
    assert s['setup_evidence']['hl']['known_at']==ts('2026-11-09T08:15:00Z')
    assert case['known_no_earlier_than']=='2026-11-09T08:18:00Z'


def test_parent_is_confirmed_hourly_D_and_stop_uses_that_D(case):
    s=case['signal'];parent=s['setup_evidence']['parent']
    assert parent['price']==73530.0885
    assert parent['known_at']==ts('2026-11-08T23:00:00Z')
    assert s['initial_stop']==pytest.approx(parent['price']-.25*s['atr'])
    assert s['initial_stop']<s['references']['l2']['price']


def test_later_rally_information_is_not_present_in_case_inputs(case):
    assert case['cutoff']=='2026-11-09T08:18:00Z'
    s=case['signal']
    assert all(p['known_at']<=ts(s['time_utc']) for p in s['setup_evidence'].values() if isinstance(p,dict))
    assert all(b['t']<ts(case['cutoff']) for b in case['bars'])


def test_consumed_entry_keeps_parent_context_but_requires_fresh_HL(case):
    setup=case['signal']['setup_evidence'];d=ParentHLDetector()
    d.parents=[copy.deepcopy(setup['parent'])];d.highs=[copy.deepcopy(setup['rebound'])]
    d.lows=[copy.deepcopy(setup['hl'])];d.now=ts('2026-11-09T08:15:00Z')
    assert d.ready(case['signal']['atr'])
    d.consume(ts('2026-11-09T08:30:00Z'))
    assert d.ready(case['signal']['atr']) is None
    assert d.parents[0]['price']==73530.0885


def test_unknown_gap_does_not_certify_parent_survival(case):
    setup=case['signal']['setup_evidence'];d=ParentHLDetector()
    d.parents=[copy.deepcopy(setup['parent'])];d.highs=[copy.deepcopy(setup['rebound'])]
    d.lows=[copy.deepcopy(setup['hl'])];d.now=ts('2026-11-09T08:15:00Z')
    d.gap();assert not d.parents and d.ready(case['signal']['atr']) is None


def test_existing_route_keeps_priority_in_isolated_case(case):
    assert case['signal']['decision']=='held_position'
    assert case['existing_priority_position']['entry_rule'].startswith('B')
    assert case['existing_priority_position']['entry_time']==case['signal']['time_utc']


def test_inherited_exit_and_risk_methods_are_unchanged():
    for new,old in [(ContinuationBaselineReplay,P1BaselineReplay),(ContinuationEarlyReplay,P1EarlyReplay)]:
        for name in ('additional_exit_candidates','close_part','targets'):
            assert getattr(new,name) is getattr(old,name)
