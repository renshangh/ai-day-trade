"""Profit-taking is staged; a stop exits every share still held, without overselling."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import clarify_btc_nov07_structure as case


@pytest.fixture(scope='module')
def result():
    root=ROOT/'reports/btc_structure_2026_11_08'
    preserved=[root/'major_resistance/MAJOR_RETEST.json',root/'BTC_30_DAY_RETEST.xlsx',
               root/'entry_examples/AUDIT.json',root/'entry_examples/NOV07_BARS.csv',
               root/'entry_examples/OCT11_USER_STRUCTURE.json',
               ROOT/'docs/investigations/2026-11-08_BTC_OCT11_STRUCTURE_CLARIFICATION.md']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    result=case.clarify(root)
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return result


def test_anchor_hierarchy_and_information_available_at_entry(result):
    anchors=result['anchors']
    assert anchors['L1']['low']==75452.88
    assert anchors['L2']['low']==75545.34>anchors['L1']['low']
    assert anchors['H1']['high']==75811.88
    assert all(case.stamp(b['end_ny'])<=case.stamp(result['entry_interval_start_ny']) for b in anchors.values())
    assert result['entry_reference']==75650
    assert result['initial_stop_reference']==pytest.approx(75529.07857142857)
    assert result['l2_right_neighbor_first_complete_ny']=='2026-11-07T21:45:00-05:00'


def test_same_known_larger_wave_target_cannot_be_replaced_by_reached_classroom_target(result):
    assert result['larger_resistance_peak']['price']==76152.43
    assert case.stamp(result['larger_resistance_peak']['known_at_utc'])<case.stamp(result['entry_interval_start_ny'])
    assert result['target1_reference']==pytest.approx(76118.18496428571)
    assert result['highest_price_since_entry']==76094.99<result['target1_reference']
    assert result['first_target_interval_start_ny'] is None
    assert result['minimum_price_since_entry']>result['initial_stop_reference']
    assert not result['initial_stop_touched']
    exits=[e for e in result['conditional_exit_trace'] if e['fraction_initial']>0]
    assert [(e['reason'],e['fraction_initial']) for e in exits]==[('stop',1.0)]
    assert exits[0]['interval_start_ny']=='2026-11-08T01:00:00-05:00'
    assert result['remaining_fraction_initial']==0
    assert result['source_end_exclusive_ny']=='2026-11-08T11:00:00-05:00'


def test_all_candles_and_new_highs_are_visible_without_false_post_target_stops(result):
    assert len(result['bars'])==74
    assert result['bars'][0]['start_ny']=='2026-11-07T16:30:00-05:00'
    assert result['bars'][-1]['end_ny']==result['source_end_exclusive_ny']
    highs=[b['start_ny'] for b in result['bars'] if b.get('price_new_wave_high')]
    assert highs==[
        '2026-11-07T22:00:00-05:00','2026-11-07T23:15:00-05:00',
        '2026-11-08T02:45:00-05:00','2026-11-08T06:15:00-05:00',
        '2026-11-08T08:00:00-05:00','2026-11-08T08:15:00-05:00']
    post=[b for b in result['bars'] if b['active_stop'] is not None]
    assert len(post)==15
    raises=[e for e in result['conditional_exit_trace'] if e['reason']=='raise_after_new_high']
    assert len(raises)==1
    assert raises[0]['breakout_interval_start_ny']=='2026-11-07T23:15:00-05:00'
    assert raises[0]['reference_low_start_ny']=='2026-11-07T22:30:00-05:00'
    assert raises[0]['reference_low']==75704.58
    assert raises[0]['price_reference']==pytest.approx(75686.95428571428)
    by_time={b['start_ny'][5:16]:b for b in post}
    assert by_time['11-07T22:00']['proposed_stop']<result['initial_stop_reference']
    assert by_time['11-07T23:15']['active_stop']==result['initial_stop_reference']
    assert by_time['11-07T23:30']['active_stop']==raises[0]['price_reference']
    assert by_time['11-08T00:45']['low']>raises[0]['price_reference']
    assert by_time['11-08T01:00']['low']<raises[0]['price_reference']
    assert all(b['active_stop'] is None for b in result['bars'] if b['start_ny']>='2026-11-08T01:15:00-05:00')


def test_single_protective_exit_profit_is_not_split_or_marked_at_later_prices(result):
    legs=result['realized_legs_per_initial_btc']
    assert len(legs)==1 and legs[0]['quantity_btc']==1.0
    assert legs[0]['gross_pnl']==pytest.approx(36.95428571428)
    assert legs[0]['assumed_roundtrip_friction']==pytest.approx(30.26739085714)
    assert legs[0]['net_pnl']==pytest.approx(6.68689485714)
    assert result['unrealized_gross_total_per_initial_btc']==0
    assert result['highest_price_while_active']==75868.27
    assert result['highest_price_since_entry']>result['highest_price_while_active']
    projected=result['hypothetical_first_target_leg_per_initial_btc']
    assert projected['gross_pnl']==pytest.approx(117.04624107142765)
    assert projected['net_pnl']==pytest.approx(109.45783182321336)
    assert projected['quantity_btc']==.25


def test_a_stop_after_an_actual_partial_profit_exits_only_remaining_75_percent(result):
    # Exercise the real, archived old target solely for position accounting.
    # The report keeps the owner's 76,118 target; no synthetic bars or tuning.
    root=ROOT/'reports/btc_structure_2026_11_08'
    _,bars,_,end=case.load_source(root)
    frozen=json.loads((root/'major_resistance/MAJOR_RETEST.json').read_text())['runs'][1]
    atr={case.stamp(r['start_utc'])+case.STEP:r['atr'] for r in frozen['ledger']}
    old=next(c for c in json.loads((root/'entry_examples/AUDIT.json').read_text())['cases'] if c['name']=='NOV07')
    cfg=case.Config(**frozen['config'])
    trace=case.trace_case(bars,atr,case.stamp(result['entry_interval_start_ny']),result['anchors']['H1'],
        result['initial_stop_reference'],old['t1'],old['t2'],old['resistance_zones'][0]['lower'],cfg,end)
    exits=[e for e in trace['events'] if e['fraction_initial']>0]
    assert [(e['reason'],e['fraction_initial']) for e in exits]==[('target1',.25),('stop',.75)]
    assert sum(e['fraction_initial'] for e in exits)==1.0
    assert trace['remaining']==0 and trace['first_target_hit']


def test_stop_update_does_not_depend_on_future_exit_bar(result):
    root=ROOT/'reports/btc_structure_2026_11_08'
    _,bars,_,_=case.load_source(root)
    frozen=json.loads((root/'major_resistance/MAJOR_RETEST.json').read_text())['runs'][1]
    atr={case.stamp(r['start_utc'])+case.STEP:r['atr'] for r in frozen['ledger']}
    end=case.stamp('2026-11-07T23:30:00-05:00')
    prefix=case.trace_case([b for b in bars if b['t']<end],atr,case.stamp(result['entry_interval_start_ny']),
        result['anchors']['H1'],result['initial_stop_reference'],result['target1_reference'],
        result['next_target_reference'],result['primary_supply_zone']['lower'],case.Config(**frozen['config']),end)
    assert prefix['remaining']==1.0
    assert prefix['events']==[e for e in result['conditional_exit_trace'] if e['reason']=='raise_after_new_high']
