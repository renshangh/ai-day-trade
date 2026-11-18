"""Real-observation lifecycle regression; no generated market fixtures."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_parent_memory import RetainedParentDetector,ParentMemoryBaseline,ParentMemoryEarly
from trading_desk.btc_parent_five import ParentFiveDetector,ParentFiveBaseline,ParentFiveEarly,five_signal
from trading_desk.btc_data import ts


@pytest.fixture
def actual():
    return json.loads((Path(__file__).parent/'fixtures/ph5_memory_case_20261115.json').read_text())


def feed_to(detector,actual,end):
    for b in actual['fifteen']:
        if b['t']+900>ts(end):break
        detector.observe(b)


def test_consumed_buy_point_does_not_erase_intact_parent_or_recycle_old_HL(actual):
    d=RetainedParentDetector();feed_to(d,actual,'2026-11-15T04:45:00Z')
    original=copy.deepcopy(d.ready(actual['signal_0320']['atr']))
    assert original and original['parent']['price']==61991.3285
    d.consume_entry(ts('2026-11-15T05:00:00Z'))
    assert d.parent==original['parent'] and d.highs and d.window
    assert d.ready(actual['signal_0320']['atr']) is None
    assert d.action_floor==ts('2026-11-15T05:00:00Z')


def test_new_HL_can_form_under_old_parent_after_entry_floor(actual):
    d=RetainedParentDetector();feed_to(d,actual,'2026-11-15T04:45:00Z')
    d.consume_entry(ts('2026-11-15T06:45:00Z'))
    for b in actual['fifteen']:
        if ts('2026-11-15T04:45:00Z')<=b['t']<ts('2026-11-15T08:15:00Z'):d.observe(b)
    s=d.ready(actual['signal_0320']['atr'])
    assert s and s['parent']['price']==61991.3285 and s['hl']['price']==63735.105
    assert s['hl']['bar_time']>=d.action_floor
    assert s['parent']['bar_time']<d.action_floor
    v=five_signal(s,actual['signal_0320']['hold_bar'],actual['minute_0320'],actual['signal_0320']['atr'],actual['signal_0320']['t1'])
    assert v['qualified_candidate'] and v['entry_reference']==pytest.approx(63948.515)


def test_missing_candle_still_clears_parent_and_preserves_consumption_floor(actual):
    d=RetainedParentDetector();feed_to(d,actual,'2026-11-15T04:45:00Z');floor=ts('2026-11-15T05:00:00Z')
    d.consume_entry(floor)
    # Omit the 23:45 candle. The unknown path cannot preserve the old parent.
    d.observe(next(b for b in actual['fifteen'] if b['t']==floor))
    assert d.parent is None and d.action_floor==floor
    assert d.ready(actual['signal_0320']['atr']) is None


def test_original_detector_still_erases_parent_on_entry_reset(actual):
    d=ParentFiveDetector();feed_to(d,actual,'2026-11-15T04:45:00Z')
    assert d.parent['price']==61991.3285
    d.reset(ts('2026-11-15T05:00:00Z'))
    assert d.parent is None and not d.highs


def test_risk_and_exit_methods_are_inherited_without_reimplementation():
    for new,old in ((ParentMemoryBaseline,ParentFiveBaseline),(ParentMemoryEarly,ParentFiveEarly)):
        for name in ('targets','apply_exits','additional_exit_candidates','close_part'):
            assert getattr(new,name) is getattr(old,name),name
