"""Failed-trade evidence must not turn later OHLC into earlier knowledge."""
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.audit_btc_e3_failure_controls import measure
from trading_desk.btc_data import ts


@pytest.fixture
def actual():
    f=Path(__file__).parent/'fixtures/e3_failure_controls_actual.json'
    return {p['trade']['id']:p for p in json.loads(f.read_text())['cases']}


def result(p):
    return measure(p['trade'],p['rows'],ts(p['cutoff']))


@pytest.mark.parametrize('ident',[22,111,75,2])
def test_first_failure_checkpoint_is_identical_without_future_data(actual,ident):
    p=actual[ident];full=result(p);point=full['checkpoints']['first_5m_failure']
    at=point['snapshot']['at'];prefix=[b for b in p['rows'] if b['t']+60<=at]
    short=measure(p['trade'],prefix,ts(p['cutoff']))
    assert short['checkpoints']['first_5m_failure']==point
    assert point['snapshot']['local_HL_broken']
    assert not point['snapshot']['parent_D_broken']
    assert full['original_net']==p['trade']['net']


@pytest.mark.parametrize('ident',[75,2])
def test_parent_wick_break_is_not_a_sustained_close_and_exit_bar_is_separate(actual,ident):
    p=actual[ident];r=result(p);d=r['parent_D']['price']
    assert r['parent_first_wick_before_exit']['low']<=d
    assert r['parent_first_wick_before_exit']['close']>=d
    assert r['parent_first_1m_close_before_exit'] is None
    assert r['parent_first_5m_close_before_exit'] is None
    assert r['parent_first_15m_close_before_exit'] is None
    assert r['original_exit_minute']['close']<d
    assert r['original_exit_minute']['t']==ts(p['trade']['exit_time'])


def test_complete_15m_failure_can_be_in_original_stop_minute(actual):
    r=result(actual[75]);p=r['checkpoints']['first_15m_failure']
    assert p['same_original_exit_minute']
    assert r['first_15m_below_HL']['end']==ts('2026-10-29T23:45:00Z')
    assert r['original_exit_minute']['t']==r['first_15m_below_HL']['end']
    assert r['original_legs'][0]['price']==pytest.approx(78070.80194642858)
    assert r['original_exit_minute']['low']!=r['original_legs'][0]['price']


def test_five_minute_reclaim_does_not_imply_fifteen_minute_reclaim(actual):
    r=result(actual[22])
    assert r['reclaims_after_15m_failure']['300']['end']==ts('2026-10-16T15:35:00Z')
    assert r['reclaims_after_15m_failure']['900'] is None
    assert r['parent_first_wick_before_exit'] is None


def test_late_confirmation_keeps_original_actual_open_reference(actual):
    r=result(actual[111]);h=r['original_failed_rebound_history'][0]
    assert h['effective_at']==ts('2026-11-05T14:15:00Z')
    assert r['original_legs'][0]['price']==79320.817
    assert r['original_legs'][0]['price']<h['price']
    assert r['reclaims_after_15m_failure']['300'] is None
    assert r['parent_first_wick_before_exit'] is None
