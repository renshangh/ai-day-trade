"""Real Nov 8 shock setup; no future confirmation or forced 2R trade."""
import sys
import hashlib
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_nov08_1745_shock as audit


@pytest.fixture(scope='module')
def result():
    preserved=[ROOT/'trading_desk/btc_engine.py',ROOT/'reports/btc_structure_2026_11_08/major_resistance/MAJOR_RETEST.json',ROOT/'reports/btc_structure_2026_11_08/BTC_30_DAY_RETEST.xlsx']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    r=audit.review()
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return r


def test_real_minutes_are_complete_half_open_windows(result):
    meta,minutes,bars,screen=audit.load()
    assert len(minutes)==630 and len(bars)==42
    assert minutes[-1]['t']<audit.ts(meta['params']['end'])
    assert all(b['observed_minutes']==15 for b in bars)
    assert result['timeframe']=='15Min' and not result['monthly_replay_run']


def test_capitulation_is_1645_using_atr_known_before_the_drop(result):
    s=result['shock']
    assert s['start']=='2026-11-08T16:45:00-05:00'
    assert s['low']==73530.0885 and s['low_minute']=='2026-11-08T16:55:00-05:00'
    assert s['atr_before']==pytest.approx(90.61428571428716)
    assert s['atr_multiple']==pytest.approx(21.78438514898283)
    assert result['higher_low']['low']==74090.65>s['low']


def test_breakout_is_1758_not_bar_open_and_later_close_is_not_used(result):
    s=result['signal']
    assert s['bar_start']=='2026-11-08T17:45:00-05:00'
    assert s['minute_start']=='2026-11-08T17:58:00-05:00'
    assert s['trigger']==pytest.approx(74429.2125)
    assert s['l2_held_before_trigger'] and s['intrabar_signal']
    assert s['final_15m_close']==74386.017<s['trigger']
    assert result['larger_structure']['reclaimed_before_signal'] is False
    assert result['larger_structure']['later_reclaim_minute']=='2026-11-08T18:00:00-05:00'


def test_four_lows_is_not_relabeled_or_risk_gate_relaxed(result):
    assert result['internal_higher_low']['low']>result['internal_higher_low']['prior_low']
    assert len(result['day_decline_reference'])==3
    assert result['proposed_routes']['draft_shock_atr_multiple']==2
    assert not result['proposed_routes']['threshold_search_performed']
    assert result['signal_passed_under_proposed_route']
    assert result['initial_stop']['price']==pytest.approx(73454.89409821428)
    assert result['target_screen']['net_reward_risk']==pytest.approx(1.6323215228730312)
    assert not result['qualified_order'] and not result['orders_submitted']
