"""Two research entry validators. No broker client, routing or wave guessing.

Wave labels/known-at times are supplied by a reviewed structure detector (or
annotated case). These validators do not claim to solve automatic wave ranking.
A setup, a price signal and a cost-qualified candidate are separate outcomes.
"""
from __future__ import annotations
from dataclasses import dataclass
from scripts.btc_structure_retest import reward_risk


@dataclass(frozen=True)
class Rules:
    required_lower_lows: int = 4
    shock_down_atr: float = 2.0 # Explicit research draft, not optimized on this case.
    higher_low_atr: float = .10
    stop_buffer_atr: float = .25
    chase_atr: float = .10
    trigger_increment: float = .01
    friction_bps: float = 2.0
    minimum_net_r: float = 0.0
    preferred_net_r: float = 2.0


def _known(points,now):
    return all(p['known_at']<=now and p['time']<=p['known_at'] for p in points)


def four_wave_setup(setup,now,rules=Rules()):
    """A: >=4 independent LL phases, intervening LH, then HH and HL."""
    lows=setup['lows'];highs=setup['intervening_highs'];hh=setup['hh'];hl=setup['hl'];why=[]
    if len(lows)<rules.required_lower_lows or len(highs)!=len(lows)-1:
        why.append('need four independent lower lows with intervening rebound highs')
    if not _known(lows+highs+[hh,hl,setup['origin']],now):
        why.append('structure evidence not known at signal time')
    if lows:
        if not setup['origin']['time']<lows[0]['time']:
            why.append('decline origin must precede the first low')
        if not all(b['price']<a['price'] for a,b in zip(lows,lows[1:])):
            why.append('lows do not form successive same-scope LL phases')
        for i,h in enumerate(highs):
            if i+1>=len(lows) or not lows[i]['time']<h['time']<lows[i+1]['time']:
                why.append('a separate rebound must occur between lows');break
        previous=setup['origin']['price']
        for h in highs:
            if h['price']>=previous:why.append('intervening rebound is not a lower high')
            previous=h['price']
        if not highs or not (hh['time']>lows[-1]['time'] and hh['price']>highs[-1]['price']):
            why.append('no HH above the previous rebound high after the final LL')
        if not (hl['time']>hh['time'] and hl['price']>lows[-1]['price']):
            why.append('no subsequent higher low above the larger D')
    return dict(rule='A_FOUR_WAVE_REVERSAL',setup_passed=not why,reasons=why,
        setup_known_at=max(p['known_at'] for p in lows+highs+[hh,hl,setup['origin']]),
        count_scope=setup.get('scope','preselected whole decline'),
        d=lows[-1]['price'] if lows else None,hl=hl['price'])


def shock_setup(setup,now,rules=Rules()):
    """B: completed bearish impulse, completed rebound, higher pullback low."""
    b=setup['impulse'];r=setup['rebound'];hl=setup['hl'];why=[]
    if not (b['t']+900<=now and r['t']+900<=now and hl['time']<=hl['known_at']<=now):
        why.append('impulse/rebound/pullback reference is not yet known')
    if setup['atr_before_impulse_known_at']>b['t']:
        why.append('impulse ATR includes information not known before the decline')
    if b['observed_minutes']!=15 or r['observed_minutes']!=15:
        why.append('missing real impulse or rebound minutes')
    atr=setup['atr_before_impulse']
    down=max(b['open'],setup['previous_close'])-b['low']
    if not (atr>0 and b['close']<b['open'] and down>=rules.shock_down_atr*atr):
        why.append('not a completed rapid bearish decline under the declared ATR draft')
    if b['low']>=setup['lowest_before_impulse']:
        why.append('impulse did not make a new setup low')
    if not (r['t']>=b['t']+900 and r['close']>r['open'] and r['low']>b['low']):
        why.append('no completed bullish rebound holding the impulse D')
    if not (hl['time']>=r['t']+900 and hl['price']>b['low']):
        why.append('no pullback higher low after the rebound')
    return dict(rule='B_SHOCK_REBOUND',setup_passed=not why,reasons=why,d=b['low'],hl=hl['price'],
        setup_known_at=max(b['t']+900,r['t']+900,hl['known_at']),
        downward_atr_multiple=down/atr if atr>0 else None,
        four_lower_lows_required=False,larger_rebound_high_break_required_before_local_signal=False)


def entry_signal(setup_result,context,rules=Rules()):
    """Shared intrabar trigger and unchanged cost/risk screen, never an order."""
    prev=context['previous_bar'];minute=context['minute'];atr=context['atr_before_entry'];why=list(setup_result['reasons'])
    period=minute['t']//900*900
    # A validated structure cannot be attached retrospectively to an earlier minute.
    if setup_result['setup_known_at']>minute['t']:
        why.append('structure was not yet known at this trigger minute')
    if prev['t']+900!=period or prev['observed_minutes']!=15:
        why.append('previous completed 15m reference is unavailable')
    if context['atr_known_at']>period or atr<=0:
        why.append('ATR was not known before the trigger bar')
    requires_hl=setup_result.get('requires_hl',True)
    if not context['hl_unbroken_before_trigger']:
        why.append('pullback low invalidated before trigger' if requires_hl else 'larger D invalidated before trigger')
    if setup_result['d'] is None or (requires_hl and (setup_result['hl'] is None or setup_result['hl']<=setup_result['d']+rules.higher_low_atr*atr)):
        why.append('higher-low tolerance failed')
    trigger=prev['high']+rules.trigger_increment
    crossed=minute['high']>trigger
    price=max(trigger,minute['open']) if crossed else None
    chase=bool(price is not None and price<=trigger+rules.chase_atr*atr)
    if not crossed:why.append('previous-bar full high has not been crossed')
    if crossed and not chase:why.append('entry exceeds the existing chase ceiling')
    stop=setup_result['d']-rules.stop_buffer_atr*atr if setup_result['d'] is not None else None
    target=context.get('target')
    target_known=bool(target and target['known_at']<=minute['t'])
    ratio=reward_risk(price,stop,target['price'],rules.friction_bps) if price is not None and stop is not None and target_known else None
    # 2R is advisory under the owner's latest instruction. Positive net
    # target space uses only information known at entry, never future winners.
    risk_pass=bool(ratio is not None and ratio>0 and ratio>=rules.minimum_net_r)
    preferred=bool(ratio is not None and ratio>=rules.preferred_net_r)
    signal=setup_result['setup_passed'] and not why
    return dict(rule=setup_result['rule'],setup_passed=setup_result['setup_passed'],
        price_crossed=crossed,structural_price_signal=signal,signal_interval_start=minute['t'],signal_interval_end=minute['t']+60,
        trigger=trigger,entry_reference=price,initial_stop=stop,target_known=target_known,
        net_reward_risk=ratio,risk_passed=risk_pass,qualified_candidate=bool(signal and risk_pass),
        preferred_rr_met=preferred,rr_warning='below 2R; advisory only' if ratio is not None and not preferred else None,
        signal_reasons=why,risk_reason=None if risk_pass else 'target unavailable or net target reward not positive or configured minimum not met',
        execution='research signal only; exact seconds and actual fills unverified; no order API')
