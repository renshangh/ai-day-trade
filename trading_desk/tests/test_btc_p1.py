"""P1 research gating on real frozen bars; original B/exit paths remain inherited."""
import copy
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,ts
from trading_desk.btc_p1 import P1Detector,P1BaselineReplay,P1EarlyReplay
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_shock_branches import ExpandedEntryDetector


@pytest.fixture(scope='module')
def frozen():
    folder=STORE/'releases/0.2/results/20261109T041525Z-30-ab'
    result=json.loads((folder/'result.json').read_text())
    with sqlite3.connect((folder/'ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        bars={t:json.loads(body) for t,body in db.execute('SELECT t,body FROM ledger ORDER BY t')}
    return result,bars


@pytest.mark.parametrize(('ident','expected'),[(23,3),(26,2)])
def test_same_p1_rule_filters_original_loser_and_winner(frozen,ident,expected):
    result,bars=frozen;p=next(p for p in result['trades'] if p['id']==ident)
    scope=next(s['setup_evidence'] for s in result['signals'] if s.get('trade_id')==ident)
    detector=P1Detector();detector.p1_bars=bars;detector.p1_now=ts(p['entry_time'])//900*900
    before=copy.deepcopy(scope);_,audit=detector.review_scope(scope)
    assert scope==before
    assert audit['p1_low_count']==expected and not audit['passed']
    assert all(c['qualified_at'] is None or c['qualified_at']<=ts(p['entry_time']) for c in audit['checks'])


def test_two_bar_confirmation_is_causal_and_old_phase_is_not_revoked(frozen):
    result,bars=frozen;s=next(s for s in result['signals'] if s.get('trade_id')==23)
    low=s['setup_evidence']['lows'][1];detector=P1Detector();detector.p1_bars=bars
    detector.p1_now=ts('2026-10-30T10:45:00Z')
    assert detector.low_check(low)['status']=='waiting'
    detector.p1_now=ts('2026-10-30T11:00:00Z')
    check=detector.low_check(low)
    assert check['status']=='qualified' and check['qualified_at']==detector.p1_now
    detector.p1_now=ts('2026-10-30T13:00:00Z')
    assert detector.low_check(low)==check


def test_failed_D_cannot_be_resurrected_by_later_rebound(frozen):
    result,bars=frozen;s=next(s for s in result['signals'] if s.get('trade_id')==23)
    low=s['setup_evidence']['lows'][0];detector=P1Detector();detector.p1_bars=bars
    detector.p1_now=ts('2026-10-30T09:00:00Z')
    c=detector.low_check(low)
    assert c['status']=='extended_same_decline'
    detector.p1_now=ts('2026-10-30T16:00:00Z')
    assert detector.low_check(low)==c


def test_missing_actual_confirmation_bar_is_never_filled(frozen):
    result,bars=frozen;s=next(s for s in result['signals'] if s.get('trade_id')==23)
    low=s['setup_evidence']['lows'][1];detector=P1Detector();detector.p1_bars=dict(bars)
    missing=low['time']//900*900+900;del detector.p1_bars[missing]
    detector.p1_now=ts('2026-10-30T11:00:00Z')
    assert detector.low_check(low)['status']=='missing_context'
    assert missing not in detector.p1_bars


def test_B_setup_objects_are_passed_through_without_changes(frozen):
    result,bars=frozen
    chain=copy.deepcopy(next(s['setup_evidence'] for s in result['signals'] if s['route']=='B1'))
    original=ExpandedEntryDetector();p1=P1Detector()
    original.shock_chain=chain;p1.shock_chain=chain
    assert p1.setups()==original.setups()
    assert p1.setups()[0][1] is chain


def test_no_exit_or_risk_method_is_overridden():
    for new,old in [(P1BaselineReplay,FailedReboundReplay),(P1EarlyReplay,EarlySequentialReplay)]:
        for method in ('additional_exit_candidates','close_part','targets','minute','complete'):
            assert getattr(new,method) is getattr(old,method)
