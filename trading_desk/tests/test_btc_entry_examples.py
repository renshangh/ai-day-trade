"""Two real-candle examples: intrabar trigger is not full trade eligibility."""
import hashlib
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_entry_examples as example


@pytest.fixture(scope='module')
def cases():
    root=ROOT/'reports/btc_structure_2026_11_08'
    files=[root/'major_resistance/MAJOR_RETEST.json',root/'BTC_30_DAY_RETEST.xlsx']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    report=example.audit(root)
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    return {c['name']:c for c in report['cases']}


def test_both_price_triggers_have_completed_previous_highs_but_no_close_confirmation(cases):
    for c in cases.values():
        p,b=c['previous_complete_bar'],c['entry_bar']
        assert p['t']+900==b['t']
        assert b['high']>p['high'] and b['close']<p['high']
        assert c['candidate_entry_reference']==pytest.approx(p['high']+.01)
        assert not c['passes_same_micro_anchor_and_rr']
        assert not c['passes_rr']


def test_intrabar_stop_uses_preceding_atr_not_future_bar_range(cases):
    a,b=cases['OCT11'],cases['NOV07']
    assert a['atr_known_before_entry']==pytest.approx(71.27428571428547)
    assert a['candidate_stop']==pytest.approx(82931.40142857144)
    assert b['atr_known_before_entry']==pytest.approx(65.04571428571633)
    assert b['candidate_stop']==pytest.approx(75529.07857142857)
    for c in cases.values():
        assert c['candidate_stop']==pytest.approx(c['candidate_low']-.25*c['atr_known_before_entry'])


def test_october_example_stops_before_target_in_conditional_trace(cases):
    a=cases['OCT11']
    events=a['conditional_exit_trace_not_backtest']
    assert len(events)==1 and events[0]['reason']=='stop'
    assert events[0]['interval_start_ny']=='2026-10-11T10:15:00-04:00'
    assert events[0]['fraction_initial']==1
    assert a['first_t1_trade_through_ny']=='2026-10-11T10:30:00-04:00'
    assert a['net_reward_risk']<0


def test_november_existing_exit_rules_finish_before_user_proposed_morning_exit(cases):
    b=cases['NOV07']
    events=b['conditional_exit_trace_not_backtest']
    exits=[x for x in events if x['fraction_initial']>0]
    assert [(x['reason'],x['fraction_initial']) for x in exits]==[('target1',.5),('stop',.5)]
    assert exits[0]['interval_start_ny']=='2026-11-07T22:00:00-05:00'
    assert exits[1]['interval_start_ny']=='2026-11-08T00:30:00-05:00'
    assert exits[1]['price_reference']==pytest.approx(75700.43392857144)
    assert b['classroom_75990_first_trade_through_ny']=='2026-11-08T08:00:00-05:00'
    assert b['candidate_entry_reference']>75624
    levels=[x['price_reference'] for x in events if x['reason']=='raise_protection']
    assert levels==sorted(levels)


def test_per_bar_tables_are_complete_contiguous_real_observations(cases):
    assert len(cases['OCT11']['bars'])==18
    assert len(cases['NOV07']['bars'])==53
    for c in cases.values():
        table=c['bars']
        assert all(example.ts(b['start_ny'])==example.ts(a['start_ny'])+900 for a,b in zip(table,table[1:]))
        assert all(example.ts(x['end_ny'])==example.ts(x['start_ny'])+900 for x in table)
