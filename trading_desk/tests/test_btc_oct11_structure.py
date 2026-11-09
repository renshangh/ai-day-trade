"""The owner's D-based example is audited without rewriting frozen results."""
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import clarify_btc_oct11_structure as case


@pytest.fixture(scope='module')
def result():
    root=ROOT/'reports/btc_structure_2026_11_08'
    preserved=[root/'major_resistance/MAJOR_RETEST.json',root/'BTC_30_DAY_RETEST.xlsx',root/'entry_examples/AUDIT.json',root/'entry_examples/NOV07_BARS.csv']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    out=case.clarify(root)
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return out


def test_major_and_local_lows_are_not_conflated(result):
    a=result['anchors']
    assert a['macro_L1']['low']==82714.25
    assert a['macro_L2_D']['low']==82869.45
    assert a['local_pullback_at_entry']['low']==82949.22
    assert result['user_confirmed_stop']==82865
    assert result['min_price_before_target_bar']==82929.08>result['user_confirmed_stop']
    at=datetime.fromisoformat(result['entry_interval_start_ny'])
    assert all(datetime.fromisoformat(x['end_ny'])<=at for x in a.values())


def test_primary_target_uses_preexisting_larger_resistance_not_later_peak(result):
    peak=result['larger_resistance_peak']
    assert peak['price']==83452.99
    assert datetime.fromisoformat(peak['known_at_utc'].replace('Z','+00:00'))<datetime.fromisoformat(result['entry_interval_start_ny'])
    assert result['target1_reference']<result['primary_supply_zone']['lower']
    assert result['gross_reward_risk']>2
    assert result['net_reward_risk']<2 and not result['passes_unchanged_t1_rr']


def test_exits_and_acceleration_use_correct_availability_times(result):
    exits=[x for x in result['conditional_exit_trace'] if x['fraction_initial']>0]
    assert [(x['reason'],x['fraction_initial']) for x in exits]==[('target1',.25),('stop',.75)]
    assert exits[0]['interval_start_ny']=='2026-10-11T11:45:00-04:00'
    assert exits[0]['stop_after_first_exit']==82865
    policy=result['exit_policy']
    assert policy['remaining_fraction_initial']==.75
    assert not policy['first_exit_moves_stop']
    assert policy['stop_recalculation_requires_new_high']
    assert policy['stop_may_only_increase']
    assert policy['remaining_exit_status']=='conditional_single_case_exit'
    assert exits[-1]['interval_start_ny']=='2026-10-11T14:45:00-04:00'
    assert exits[-1]['price_reference']==pytest.approx(83613.65232142857)
    assert result['target_bar_after_close']['known_at_ny']=='2026-10-11T12:00:00-04:00'
    assert len(result['bars'])==61


def test_only_wave_breakouts_raise_stop_using_completed_intervening_lows(result):
    raises=[e for e in result['conditional_exit_trace'] if e['reason']=='raise_after_new_high']
    assert [e['breakout_interval_start_ny'] for e in raises]==[
        '2026-10-11T12:30:00-04:00','2026-10-11T13:30:00-04:00']
    assert [e['reference_low'] for e in raises]==[83630,83658.11]
    assert [e['price_reference'] for e in raises]==pytest.approx([83594.76464285715,83613.65232142857])
    for e in raises:
        breakout=case.stamp(e['breakout_interval_start_ny'])
        assert case.stamp(e['reference_low_start_ny'])+case.STEP<=breakout
        assert case.stamp(e['effective_from_ny'])==breakout+case.STEP
        assert e['price_reference']==pytest.approx(e['reference_low']-.25*e['atr_known_at_breakout_start'])
    rows={r['start_ny'][11:16]:r for r in result['after_first_target_bars']}
    assert rows['12:15']['active_stop']==82865
    assert rows['12:30']['active_stop']==82865
    assert rows['12:45']['active_stop']==raises[0]['price_reference']
    assert rows['13:30']['active_stop']==raises[0]['price_reference']
    assert rows['13:45']['active_stop']==raises[1]['price_reference']
    # A locally higher low is insufficient: no new wave high after 13:30.
    assert not rows['14:15']['new_high'] and rows['14:15']['new_stop'] is None
    assert rows['14:30']['active_stop']==raises[1]['price_reference']
    assert len(rows)==12


def test_later_candles_cannot_change_earlier_stop_updates(result):
    bars=[dict(t=case.stamp(b['start_ny']),**{k:b[k] for k in ('open','high','low','close')}) for b in result['bars']]
    first=next(b for b in bars if b['t']==case.stamp(result['first_target_interval_start_ny']))
    atr={case.stamp(r['start_ny']):r['atr_known_at_start'] for r in result['after_first_target_bars']}
    cfg=case.Config(**result['old_config'])
    boundary=case.stamp('2026-10-11T13:45:00-04:00')
    prefix=case.trace_remaining([b for b in bars if b['t']<boundary],atr,first,82865,
        result['next_target_reference'],result['primary_supply_zone']['lower'],cfg,boundary)
    assert not prefix['terminal']
    assert prefix['events']==[e for e in result['conditional_exit_trace'] if e['reason']=='raise_after_new_high']
    assert prefix['rows']==[r for r in result['after_first_target_bars'] if case.stamp(r['start_ny'])<boundary]
