"""Approved profit protection on observed minute openings, never broker orders.

Initial R is immutable. Peaks use completed post-entry minutes; the entry
minute's unresolved high is excluded. Current minute H/L/C is unavailable to
the guard, which participates in the shared stop/structure/target ordering.
"""
import copy

from trading_desk.btc_ab_replay import ABReplay
from trading_desk.btc_approved_exits import direction_context
from trading_desk.btc_data import iso,ts
from trading_desk.btc_structure_exits import StructureExitMixin

POLICY='profit-giveback-1r-half-direction-non-inside-v4'


def guard_observation(position,minute,prefix,previous,known_peak):
    entry=position['entry'];risk=entry-position['initial_stop'];price=minute['open']
    peak=max(entry,known_peak,price);mfe=peak-entry
    d=dict(time_utc=iso(minute['t']),interval_end=iso(minute['t']+60),reference_price=price,
        highest_known_price=peak,initial_risk=risk,max_favourable_excursion=mfe,
        giveback_fraction=(peak-price)/mfe if mfe>0 else None,
        mfe_r=mfe/risk if risk>0 else None,armed=risk>0 and mfe>=risk,
        reference_context_complete=False,non_green=None,not_above_previous_close=None,
        full_range_inside=None,body_inside=None,qualified=False,
        current_minute_range_used=False,sampling='observed 1m open, not final 15m close')
    period=minute['t']//900*900
    context=direction_context(minute,prefix,previous)
    if not context or [b['t'] for b in prefix]!=list(range(period,minute['t'],60)):
        d['blocked_by']=['missing_complete_direction_or_prefix_context'];return d
    high=max([price]+[b['high'] for b in prefix]);low=min([price]+[b['low'] for b in prefix])
    body=sorted((context['direction_bar_open'],price));prior_body=sorted((previous['open'],previous['close']))
    d.update(reference_context_complete=True,**context,observed_high=high,observed_low=low,
        non_green=price<=context['direction_bar_open'],not_above_previous_close=price<=context['previous_bar_close'],
        full_range_inside=high<=previous['high'] and low>=previous['low'],
        body_inside=body[0]>=prior_body[0] and body[1]<=prior_body[1])
    blocked=[]
    if not d['armed']:blocked.append('maximum_favourable_excursion_below_initial_1r')
    if d['giveback_fraction'] is None or d['giveback_fraction']<.5:blocked.append('giveback_below_half_or_unavailable')
    if not d['non_green']:blocked.append('currently_green')
    if not d['not_above_previous_close']:blocked.append('above_previous_complete_close')
    if d['full_range_inside'] or d['body_inside']:blocked.append('inside_previous_candle')
    d.update(blocked_by=blocked,qualified=not blocked)
    return d


class GuardedABReplay(StructureExitMixin,ABReplay):
    """Current A/B exit policy; frozen ABReplay remains for prior audits."""
    def __init__(self,*args,**kwargs):
        if kwargs.get('exit_policy','approved')!='approved':
            raise ValueError('Use frozen ABReplay for legacy or V1/V2 comparison')
        super().__init__(*args,**kwargs)
        self.policy=POLICY

    def minute(self,b):
        super().minute(b)
        p=self.position
        if p and b['t']>ts(p['entry_time']):
            state=p.setdefault('giveback_state',dict(highest_completed_peak=p['entry']))
            # This high becomes known after this minute; never before its
            # opening guard decision. It is retained only for the next call.
            state['highest_completed_peak']=max(state['highest_completed_peak'],b['high'])
            state['last_completed_minute']=b['t']

    def additional_exit_candidates(self,b):
        p=self.position
        state=p.setdefault('giveback_state',dict(highest_completed_peak=p['entry']))
        d=guard_observation(p,b,self.minutes,self.prev,state['highest_completed_peak'])
        p.setdefault('giveback_observations',[]).append(copy.deepcopy(d))
        state['last_observation']=copy.deepcopy(d)
        if d['armed'] and not state.get('armed_at'):
            state['armed_at']=b['t']
            self.event('giveback_armed',b['t'],trade_id=p['id'],price=b['open'],
                initial_risk=d['initial_risk'],highest_known_price=d['highest_known_price'])
        if not d['qualified']:return []
        return [dict(reason='giveback_exit_remaining',price=b['open'],phase=0,priority=10,
            price_basis='actual observed minute opening; current minute range and final candle excluded',
            policy=POLICY,guard=copy.deepcopy(d))]
