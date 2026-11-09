"""One same-source conditional entry, causal protection and first exit."""
import hashlib
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_nov07_2145_timeline as audit


@pytest.fixture(scope='module')
def result():
    preserved=[ROOT/'trading_desk/btc_engine.py',ROOT/'trading_records/btc_structure/latest_run.json',
        ROOT/'reports/btc_structure_2026_11_08/BTC_30_DAY_RETEST.xlsx',
        ROOT/'reports/btc_structure_2026_11_08/major_resistance/MAJOR_RETEST.json',
        ROOT/'reports/btc_structure_2026_11_08/entry_examples/hierarchy_review/FOUR_CASE_HIERARCHY_REVIEW.json']
    # The local run pointer need not exist on another checkout.
    preserved=[p for p in preserved if p.exists()]
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    r=audit.review()
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return r


def test_entry_reference_and_cost_gate_stay_separate(result):
    r=result
    assert r['entry_time']=='2026-11-07T21:58:00-05:00'
    assert r['entry_reference']==pytest.approx(75655.545)
    assert r['initial_d']['price']==75462.2
    assert r['atr_before']==pytest.approx(69.2945)
    assert r['initial_stop']==pytest.approx(75444.876375)
    assert r['entry_qualification']['four_independent_lows']
    assert not r['entry_qualification']['net_2r_passed']


def test_internal_or_unfinished_low_does_not_raise_stop(result):
    r=result
    assert r['whole_initial_pullback_low']['price']==75545.7915
    assert r['whole_initial_pullback_low']['time']=='2026-11-07T21:16:00-05:00'
    assert r['stop_raises']==[] and r['stop_raises_before_exit']==0
    assert r['confirmed_new_lows_before_exit_15m']==[]
    assert r['confirmed_new_lows_before_exit_hourly']==[]
    assert r['next_low_candidate']['low']==75734.171
    assert r['next_low_candidate']['known_at']=='2026-11-07T23:00:00-05:00'
    assert r['next_low_known_after_exit']


def test_first_midpoint_is_not_breached(result):
    check=result['midpoint_check']
    assert check['threshold']==pytest.approx(75754.455)
    assert check['following_bar_low']==75756.175>check['threshold']
    assert not check['triggered']


def test_last_minute_wick_uses_open_and_exits_before_later_protection(result):
    r=result;e=r['exit']
    assert e['time']=='2026-11-07T22:59:00-05:00'
    assert e['price']==75779.12
    assert e['known_prefix_minutes']==14 and not e['integer_watch_gate']
    assert e['observed_high']==75821.555 and e['observed_low']==75761.41
    assert e['upper_wick_fraction']==pytest.approx(.7055449330784781)
    assert r['new_high_increment']==pytest.approx(.866)
    assert r['exit_minute_final_hlc_excluded_from_wick']
    assert r['exit_minute_actual_final_close_not_used']==75810.965!=e['price']
    assert r['fraction_exited']==1 and not r['target_touched_before_exit']
    assert not r['initial_stop_touched_before_exit']


def test_pnl_and_unambiguous_decimal_table(result):
    p=result['pnl']
    assert p['gross']==pytest.approx(123.575)
    assert p['cost']==pytest.approx(30.286933)
    assert p['net']==pytest.approx(93.288067)
    text=audit.table(result)
    assert '$75,655.545' in text
    assert '+$123.58' in text and '+$93.29' in text
    assert text.count('不上移')==2
