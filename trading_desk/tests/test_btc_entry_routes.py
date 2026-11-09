"""Independent route validators on the owner's real Nov 7/8 examples."""
import sys
from pathlib import Path
from copy import deepcopy
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_entry_rules import Rules,four_wave_setup,shock_setup,entry_signal
from trading_desk.btc_data import ts
from trading_desk.btc_engine import aggregate
import review_btc_nov06_07_swings as four
import audit_btc_nov08_1745_shock as shock


def four_case():
    f,minutes=four.load();case=four.review()['cases']['2145'];wave=case['new_four_swing_rule']['owner_full_decline_review']
    seq=case['new_four_swing_rule']['owner_ll_lh_sequence']['providers']['Alpaca'];lows=[];highs=[]
    for p in wave['evidence']:lows.append(dict(time=ts(p['alpaca_low_minute']),price=p['alpaca_phase_low'],known_at=ts(p['alpaca_known_by'])))
    for p in seq['rebounds'][:3]:highs.append(dict(time=ts(p['bar_start']),price=p['high'],known_at=ts(p['turn_known_by'])))
    hh=seq['rebounds'][3];hl=seq['subsequent_higher_low'];now=ts(case['signal_time'])
    setup=dict(origin=dict(time=ts(wave['count_origin']),price=wave['alpaca_origin_high'],known_at=ts('2026-11-07T04:30:00-05:00')),
        lows=lows,intervening_highs=highs,hh=dict(time=ts(hh['bar_start']),price=hh['high'],known_at=ts(hh['turn_known_by'])),
        hl=dict(time=ts(hl['bar_start']),price=hl['low'],known_at=ts(hl['turn_known_by'])),scope='Nov7 full decline from 04:00')
    context=dict(previous_bar=next(b for b in f['ledger'] if b['t']==ts('2026-11-07T21:30:00-05:00')),
        minute=next(b for b in minutes if b['t']==now),atr_before_entry=case['atr_before'],atr_known_at=ts(case['trigger_bar']['time']),
        hl_unbroken_before_trigger=case['l2_unbroken_before_trigger'],target=dict(price=case['target'],known_at=ts(case['target_zone_known_at'])))
    return setup,context,now


def shock_case():
    meta,minutes,bars,screen=shock.load();by={b['t']:b for b in bars};audit=shock.review();now=ts(audit['signal']['minute_start'])
    impulse=by[ts(audit['shock']['start'])];rebound=by[ts(audit['rebound']['start'])]
    setup=dict(impulse=impulse,rebound=rebound,hl=dict(time=ts(audit['higher_low']['start']),price=audit['higher_low']['low'],known_at=ts(audit['higher_low']['known_low_at'])),
        atr_before_impulse=audit['shock']['atr_before'],atr_before_impulse_known_at=impulse['t'],previous_close=by[impulse['t']-900]['close'],
        lowest_before_impulse=min(b['low'] for b in bars if b['t']<impulse['t']))
    context=dict(previous_bar=by[ts('2026-11-08T17:30:00-05:00')],minute=next(b for b in minutes if b['t']==now),
        atr_before_entry=audit['initial_stop']['atr_before_entry'],atr_known_at=ts(audit['signal']['bar_start']),
        hl_unbroken_before_trigger=audit['signal']['l2_held_before_trigger'],target=dict(price=screen['target1'],known_at=ts(screen['asof'])))
    return setup,context,now


def test_a_emits_2145_signal_with_positive_net_space_and_2r_warning():
    s,c,now=four_case();r=entry_signal(four_wave_setup(s,now),c)
    assert r['setup_passed'] and r['structural_price_signal']
    assert r['entry_reference']==pytest.approx(75655.545)
    assert r['net_reward_risk']==pytest.approx(1.8068331024993958)
    assert r['qualified_candidate'] and r['risk_passed']
    assert not r['preferred_rr_met'] and r['rr_warning']


def test_b_emits_1745_signal_without_waiting_for_four_lows():
    s,c,now=shock_case();setup=shock_setup(s,now);r=entry_signal(setup,c)
    assert setup['setup_passed'] and setup['four_lower_lows_required'] is False
    assert setup['downward_atr_multiple']==pytest.approx(21.78438514898283)
    assert r['structural_price_signal'] and r['entry_reference']==pytest.approx(74429.2125)
    assert r['initial_stop']==pytest.approx(73454.89409821428)
    assert r['net_reward_risk']==pytest.approx(1.6323215228730312)
    assert r['qualified_candidate'] and r['risk_passed']
    assert not r['preferred_rr_met']


def test_legacy_strict_2r_remains_available_for_historical_comparison():
    s,c,now=shock_case()
    strict=Rules(minimum_net_r=2.0)
    assert not entry_signal(shock_setup(s,now,strict),c,strict)['qualified_candidate']


def test_known_target_without_positive_net_space_still_rejects():
    s,c,now=shock_case()
    # A hypothetical target at an actual previously observed close; no candle
    # prices are invented or modified to manufacture a losing market path.
    c['target']=dict(price=c['previous_bar']['close'],known_at=c['previous_bar']['t']+900)
    result=entry_signal(shock_setup(s,now),c)
    assert result['structural_price_signal']
    assert result['net_reward_risk']<0 and not result['qualified_candidate']


def test_a_does_not_accept_three_waves_to_fit_a_desired_entry():
    s,c,now=four_case();s=deepcopy(s);s['lows']=s['lows'][:3];s['intervening_highs']=s['intervening_highs'][:2]
    assert not four_wave_setup(s,now)['setup_passed']


def test_future_confirmation_is_not_used_and_invalid_hl_stops_signal():
    s,c,now=four_case();s=deepcopy(s);s['hh']['known_at']=now+60
    assert not four_wave_setup(s,now)['setup_passed']
    s,c,now=shock_case();c['hl_unbroken_before_trigger']=False
    assert not entry_signal(shock_setup(s,now),c)['structural_price_signal']


def test_shock_needs_completed_impulse_and_rebound_not_just_a_red_candle():
    s,c,now=shock_case();assert not shock_setup(s,s['impulse']['t']+60)['setup_passed']
    assert not shock_setup(s,s['rebound']['t']+60)['setup_passed']
    meta,minutes,bars,_=shock.load()
    # A real, ordinary red candle from the same source is not the crash.
    s=deepcopy(s);s['impulse']=next(b for b in bars if b['t']==ts('2026-11-08T16:15:00-05:00'))
    s['previous_close']=next(b['close'] for b in bars if b['t']==ts('2026-11-08T16:00:00-05:00'))
    s['atr_before_impulse']=88.11910714285997
    s['atr_before_impulse_known_at']=s['impulse']['t']
    s['lowest_before_impulse']=min(b['low'] for b in bars if b['t']<s['impulse']['t'])
    assert not shock_setup(s,now)['setup_passed']


def test_shock_does_not_use_post_drop_atr_for_pre_drop_classification():
    s,c,now=shock_case();s['atr_before_impulse_known_at']=s['impulse']['t']+900
    assert not shock_setup(s,now)['setup_passed']


def test_a_later_validated_setup_cannot_be_backdated_to_a_price_signal():
    s,c,now=shock_case()
    # Only the annotation's confirmation timestamp changes; market bars stay real.
    s['hl']['known_at']=now+60
    validated=shock_setup(s,now+60)
    assert validated['setup_passed']
    result=entry_signal(validated,c)
    assert result['price_crossed'] and not result['structural_price_signal']
