"""A real minute-open observation must not borrow its final close or later bars."""
import hashlib
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_nov08_last_minute as audit


@pytest.fixture(scope='module')
def result():
    root=ROOT/'reports/btc_structure_2026_11_08'
    preserved=[root/'major_resistance/MAJOR_RETEST.json',root/'BTC_30_DAY_RETEST.xlsx',
        root/'entry_examples/NOV07_USER_STRUCTURE.json',root/'entry_examples/OCT11_USER_STRUCTURE.json',
        root/'entry_examples/NOV07_PARENT_SWING_REVIEW.json']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    result=audit.review(root)
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return result


def test_real_minutes_reproduce_archived_parent_candle_and_missing_data_fails(result):
    assert len(result['minutes'])==15
    assert result['source_rollup_matches_archived_15m']
    assert result['rollup']==dict(open=76015.62,high=76094.99,low=75944.77,close=75956.19,volume=17.2015192)
    folder=ROOT/'reports/btc_structure_2026_11_08/entry_examples/minute_rejection_2026_11_08'
    _,rows=audit.load_minutes(folder)
    start=audit.stamp(result['signal_start_ny'])
    with pytest.raises(ValueError,match='Missing real minute'):
        audit.target_minutes([r for r in rows if r['t']!=start+60],start)


def test_last_minute_gate_and_no_current_minute_final_values(result):
    start=audit.stamp(result['signal_start_ny'])
    rows=[dict(t=audit.stamp(b['start_ny']),**{k:b[k] for k in ('open','high','low','close','volume')}) for b in result['minutes']]
    before_window=start+13*60
    p=next(b for b in rows if b['t']==before_window)
    early=audit.snapshot_at_minute_open([b for b in rows if b['t']<before_window],p['open'],before_window,
        start,76015.62,76017.37,76015.63)
    assert early['shape_condition'] and not early['in_last_minute'] and not early['trigger']
    observed=result['observed_trigger']
    assert observed['trigger']
    assert observed['observation_minute_start_ny']=='2026-11-08T08:29:00-05:00'
    assert observed['last_closed_minute_end_ny']=='2026-11-08T08:29:00-05:00'
    assert observed['current_price_reference']==75955.04!=result['rollup']['close']
    assert not observed['used_current_minute_final_high_low_close']
    assert observed['upper_wick_fraction']==pytest.approx(79.37/150.22)
    with pytest.raises(ValueError,match='already-completed'):
        audit.snapshot_at_minute_open(rows,75955.04,start+14*60,start,76015.62,76017.37,76015.63)


def test_full_exit_reference_pnl_and_previous_d_are_not_old_staged_result(result):
    assert result['initial_d_price']==75452.88
    assert result['initial_stop_reference']==pytest.approx(75436.61857142858)
    assert result['initial_net_reward_risk']<2
    assert result['exit_fraction']==1.0
    pnl=result['model_pnl_per_initial_btc']
    assert pnl['quantity_btc']==1.0 and pnl['exit_reference']==75955.04
    assert pnl['gross_pnl']==pytest.approx(305.04)
    assert pnl['assumed_roundtrip_friction']==pytest.approx(30.321008)
    assert pnl['net_pnl']==pytest.approx(274.718992)
    assert result['active_structural_stop_at_observation']==pytest.approx(75674.10142857143)
