"""Nominated real-data cases: parent hierarchy and causal first exit, no tuning."""
import hashlib
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import review_btc_nov06_07_swings as audit


@pytest.fixture(scope='module')
def result():
    preserved=[ROOT/'trading_desk/btc_engine.py',ROOT/'reports/btc_structure_2026_11_08/major_resistance/MAJOR_RETEST.json',
        ROOT/'reports/btc_structure_2026_11_08/BTC_30_DAY_RETEST.xlsx']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    r=audit.review()
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return r


def test_23_full_range_midpoint_first_cross_is_not_bar_open(result):
    events=result['cases']['23']['exit_review']['events']
    e=next(e for e in events if e.get('reference_bar')=='2026-11-06T07:15:00-05:00')
    assert e['reference_high']==76259.375 and e['reference_low']==75999.311
    assert e['threshold']==pytest.approx(76129.343)
    assert e['time']=='2026-11-06T07:32:00-05:00'
    assert e['reference_known_at']=='2026-11-06T07:30:00-05:00'
    assert e['pnl']['net']==pytest.approx(538.6175539)
    assert e['conditional_after_earlier_exit']


def test_23_earlier_wick_is_not_hidden_to_keep_preferred_0730_exit(result):
    e=result['cases']['23']['exit_review']['first_candidate']
    assert e['time']=='2026-11-06T04:29:00-05:00'
    assert e['type']=='last_minute_new_wave_high_upper_wick'
    assert e['known_prefix_minutes']==14 and e['integer_watch_gate'] is False
    assert e['price']==76010.851 and e['price']>76000
    assert e['upper_wick_fraction']==pytest.approx(.8821424096661507)
    assert e['pnl']['net']==pytest.approx(420.1492523)
    assert not e['exact_second_verified']
    fixture,minutes=audit.load()
    assert next(b for b in minutes if b['t']==audit.ts(e['time']))['close']!=e['price']


def test_23_already_broken_d_cannot_use_future_confirmation_at_entry(result):
    c=result['cases']['23'];h=c['hierarchy'];d=h['new_large_d_candidate']
    assert h['original_d_already_undercut_before_entry']
    assert d['price']==75200.475
    assert audit.ts(d['hour_pivot_confirmed_at'])>audit.ts(c['entry_time'])
    assert audit.ts(h['first_undercut'])<audit.ts(c['entry_time'])


def test_24_parent_correction_keeps_deep_low_not_internal_low(result):
    h=result['cases']['24']['hierarchy']
    assert h['parent_peak']['price']==76091.144
    assert h['whole_pullback_low']['price']==75681.0945
    assert h['whole_pullback_low']['time']=='2026-11-06T22:43:00-05:00'
    assert h['whole_pullback_low']['hour_pivot_confirmed_at']=='2026-11-07T00:00:00-05:00'
    assert h['first_parent_peak_break']=='2026-11-07T03:56:00-05:00'
    assert h['internal_low_not_parent']==75862.817
    assert h['cycle_stop_candidate']==pytest.approx(75664.233125)
    assert h['candidate_effective_at']=='2026-11-07T04:00:00-05:00'


def test_24_midpoint_precedes_wick_and_does_not_double_exit(result):
    r=result['cases']['24']['exit_review'];first=r['first_candidate']
    assert first['time']=='2026-11-07T04:02:00-05:00'
    assert first['price']==pytest.approx(76069.4185)
    wick=next(e for e in r['events'] if e['type']=='last_minute_new_wave_high_upper_wick')
    assert wick['time']=='2026-11-07T04:14:00-05:00'
    assert wick['conditional_after_earlier_exit']
    assert wick['pnl']['net']==pytest.approx(224.022534)


def test_25_tiny_internal_high_does_not_create_parent_new_high(result):
    c=result['cases']['25'];h=c['hierarchy']
    assert h['highest_after_entry']==75708.631<h['parent_peak']['price']==75794.65
    assert h['parent_promotions']==[]
    r=c['exit_review'];assert len(r['events'])==1
    assert r['first_candidate']['time']=='2026-11-07T16:31:00-05:00'
    assert r['first_candidate']['pnl']['net']==pytest.approx(-229.92005716427911)


def test_2130_parent_fix_does_not_invent_breakout_or_override_2r(result):
    c=result['cases']['2130']
    assert c['parent_d']['price']==75462.2
    assert c['internal_d_rejected']['price']==75607.5
    assert c['higher_low_pass'] and not c['own_feed_breakout'] and not c['entry']
    assert c['shortfall_to_previous_high']==pytest.approx(.295)
    assert c['hypothetical_net_reward_risk']==pytest.approx(1.8045949290272556)
    assert c['hypothetical_net_reward_risk']<2
    assert c['later_crossing_minute']=='2026-11-07T21:58:00-05:00'
    assert audit.ts(c['target_known_at'])<=audit.ts(c['candidate_15m']['time'])


def test_2145_records_breakout_without_requiring_fresh_l2_or_overriding_cost_gate(result):
    c=result['cases']['2145']
    assert c['price_signal'] and c['l2_unbroken_before_trigger']
    assert c['signal_time']=='2026-11-07T21:58:00-05:00'
    assert c['trigger']==pytest.approx(75655.545)
    assert c['retained_l2']['price']==75545.7915
    assert not c['legacy_previous_bar_is_pullback_minimum']
    assert c['gross_reward_risk']>2
    assert c['net_reward_risk']==pytest.approx(1.8068331024993958)
    assert not c['qualified_under_unchanged_2r']
    assert audit.ts(c['target_zone_known_at'])<=audit.ts(c['signal_time'])


def test_four_swings_does_not_relabel_four_lower_candles_as_four_confirmed_lows(result):
    c=result['cases']['2145'];rule=c['new_four_swing_rule']
    assert rule['required_independent_lower_swings']==4
    local=rule['local_peak_diagnostic_candidates']
    assert [p['bar_start'] for p in local]==['2026-11-07T20:15:00-05:00','2026-11-07T21:15:00-05:00']
    assert [p['low'] for p in local]==[75658.3,75545.7915]
    assert len(rule['parent_peak_diagnostic_candidates'])==2
    assert all(audit.ts(p['diagnostic_known_at'])<=audit.ts(c['signal_time']) for p in local)
    # The short-scope diagnostics are retained as evidence of the old mistake;
    # they must not discard owner-marked earlier waves in the full decline.
    assert rule['qualifying_four_swings_demonstrated'] and not rule['entry']


def test_owner_four_lows_keep_full_decline_scope_and_separate_provider_prices(result):
    rule=result['cases']['2145']['new_four_swing_rule'];wave=rule['owner_full_decline_review']
    assert wave['count_origin']=='2026-11-07T04:00:00-05:00'
    assert wave['confirmed_count']==4 and wave['child_rebounds_do_not_reset_count']
    assert [e['owner_15m_start'][11:16] for e in wave['evidence']]==['06:15','07:30','10:45','16:30']
    assert [e['coinbase_low'] for e in wave['evidence']]==[75818.42,75711.39,75507.9,75452.88]
    assert wave['known_by']=='2026-11-07T17:00:00-05:00'
    assert wave['alpaca_known_by']=='2026-11-07T17:00:00-05:00'
    second=wave['evidence'][1]
    assert second['alpaca_low_minute']=='2026-11-07T07:46:00-05:00'
    assert second['alpaca_phase_low']==75726.326
    assert result['cases']['2130']['four_swing_gate_passed']
    assert not result['cases']['2145']['qualified_under_unchanged_2r']


def test_intervening_lower_highs_and_fourth_higher_high_are_not_mislabeled(result):
    seq=result['cases']['2145']['new_four_swing_rule']['owner_ll_lh_sequence']
    assert seq['timeframe']=='15Min'
    for provider in ('Coinbase','Alpaca'):
        p=seq['providers'][provider]
        assert [b['label'] for b in p['rebounds']]==['LH','LH','LH','HH']
        assert p['structure_strengthens']
        assert p['strength_signal_15m_interval']=='2026-11-07T18:45:00-05:00'
        assert p['subsequent_higher_low']['higher']
        assert p['subsequent_higher_low']['turn_known_by']=='2026-11-07T21:45:00-05:00'
    assert [b['high'] for b in seq['providers']['Coinbase']['rebounds']]==[75946.76,75892.6,75789.4,75811.88]
    assert [b['high'] for b in seq['providers']['Alpaca']['rebounds']]==[75951.7,75897.91,75794.65,75815.937]
