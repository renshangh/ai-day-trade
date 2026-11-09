"""Approved new-high-failure exit, distinct from whole-trade profit giveback."""
from trading_desk.btc_data import iso
from trading_desk.btc_guarded_replay import GuardedABReplay
from trading_desk.btc_structure_exits import last_minute_state

POLICY='profit-guard-plus-last-minute-new-high-failure-v5'


def turning_observation(position,minute,prefix,previous):
    d=last_minute_state(minute,prefix,previous)
    if d is None:return None
    d.update(qualified=False,new_wave_high=d['observed_high']>position['active_wave_high'],
        prior_wave_high=position['active_wave_high'],current_minute_range_used=False)
    if not d['context']:
        d['blocked_by']=['missing_previous_complete_candle'];return d
    midpoint=(previous['high']+previous['low'])/2
    span=previous['high']-previous['low']
    d.update(previous_open=previous['open'],previous_close=previous['close'],
        previous_high=previous['high'],previous_low=previous['low'],previous_midpoint=midpoint,
        previous_bullish=previous['close']>previous['open'],
        prior_range_retracement=(previous['high']-minute['open'])/span if span>0 else None,
        red_at_observation=minute['open']<d['opening_15m'],
        below_midpoint=minute['open']<midpoint,
        non_inside=not (d['body_inside'] or d['full_range_inside']))
    blocked=[]
    for key,reason in (('new_wave_high','no_current_new_wave_high'),
            ('previous_bullish','previous_candle_not_bullish'),('below_midpoint','not_below_previous_range_midpoint'),
            ('red_at_observation','not_red_at_observation'),('direction_passed','above_previous_close'),
            ('non_inside','inside_previous_candle')):
        if not d[key]:blocked.append(reason)
    d.update(blocked_by=blocked,qualified=not blocked)
    return d


class TurningABReplay(GuardedABReplay):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.policy=POLICY

    def additional_exit_candidates(self,b):
        options=super().additional_exit_candidates(b)
        p=self.position;d=turning_observation(p,b,self.minutes,self.prev)
        if d is None:return options
        p.setdefault('turning_observations',[]).append(d)
        if d['qualified']:
            self.event('turning_signal',b['t'],trade_id=p['id'],price=b['open'],
                previous_midpoint=d['previous_midpoint'],prior_range_retracement=d['prior_range_retracement'],
                reason='current new wave high failed; red non-inside below previous bullish candle midpoint')
            options.append(dict(reason='turning_exit_remaining',price=b['open'],phase=0,priority=15,
                price_basis='last-minute observed open plus fourteen complete minutes; final close not used',
                policy=POLICY,turning=d))
        return options
