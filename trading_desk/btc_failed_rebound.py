"""Approved independent 15m lower-high / pullback-low-break exit.

This does not move the hard stop or require a new high/initial-1R profit.
Every swing uses the existing complete left/middle/right 15m convention.
"""
import copy
import json

from trading_desk.btc_data import iso,ts
from trading_desk.btc_turning_replay import TurningABReplay

POLICY='profit-guard-turning-plus-confirmed-failed-rebound-v6'


class FailedReboundReplay(TurningABReplay):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.policy=POLICY

    def reset_failed_rebound(self,t,reason):
        if self.position:
            previous=self.position.get('failed_rebound_state') or {}
            anchor=copy.deepcopy(previous.get('reference'))
            # Missing observations cannot revoke a previously confirmed exit
            # reference. Clear unconfirmed construction only; execute solely
            # on later observed prices and explicitly flag the unknown gap path.
            if anchor:anchor['gap_exposed']=True
            self.position['failed_rebound_state']=dict(high=None,low=None,reference=anchor)
            self.event('failed_rebound_context_reset',t,trade_id=self.position['id'],reason=reason,
                retained_confirmed_reference=anchor['price'] if anchor else None)

    def minute(self,b):
        if self.position and self.last_minute is not None and b['t']!=self.last_minute+60:
            self.reset_failed_rebound(b['t'],'missing observed minutes; rebuild pattern, hard stop retained')
        super().minute(b)

    def complete(self):
        had=bool(self.minutes)
        super().complete()
        if not had or not self.position:return
        p=self.position;recent=list(self.recent);now=self.prev['t']+900
        if len(recent)<3:return
        left,middle,right=recent[-3:]
        adjacent=middle['t']==left['t']+900 and right['t']==middle['t']+900
        if not adjacent or any(b['observed_minutes']!=15 for b in (left,middle,right)):
            self.reset_failed_rebound(now,'incomplete or absent 15m neighbour; no inferred swing')
        else:
            state=p.setdefault('failed_rebound_state',dict(high=None,low=None,reference=None))
            high_turn=middle['high']>max(left['high'],right['high'])
            low_turn=middle['low']<min(left['low'],right['low'])
            entry=ts(p['entry_time'])
            if high_turn and low_turn:
                self.event('failed_rebound_outside_bar',now,trade_id=p['id'],
                    reason='high/low swing order within outside candle is unknown; neither inferred')
            elif high_turn and middle['high_t']>entry:
                h=dict(time=middle['high_t'],bar_time=middle['t'],price=middle['high'],known_at=now)
                high=state['high'];low=state['low']
                if h['price']>p['entry'] and (high is None or h['price']>=high['price']):
                    state.update(high=h,low=None)
                    anchor=state.get('reference')
                    if anchor is None or h['price']>anchor['lower_high']['price']:
                        state['reference']=None
                elif high and low and high['time']<low['time']<h['time'] and low['price']<h['price']<high['price']:
                    anchor=dict(high=copy.deepcopy(high),low=copy.deepcopy(low),lower_high=h,
                        price=low['price'],effective_at=now,
                        basis='complete 15m H-L-LH; independent break-low exit, no new-high or 1R gate')
                    state['reference']=anchor
                    p.setdefault('failed_rebound_history',[]).append(copy.deepcopy(anchor))
                    self.event('failed_rebound_reference',now,trade_id=p['id'],price=anchor['price'],
                        high=anchor['high'],low=anchor['low'],lower_high=anchor['lower_high'],effective_time=iso(now))
            elif low_turn and middle['low_t']>entry and state['high']:
                if state['high']['time']<middle['low_t']:
                    low=dict(time=middle['low_t'],bar_time=middle['t'],price=middle['low'],known_at=now)
                    # Retain the low of this pullback, rather than tightening to
                    # a later internal higher low without a fresh high phase.
                    if low['price']<state['high']['price'] and (state['low'] is None or low['price']<state['low']['price']):
                        state['low']=low
        record=self.db.execute('SELECT body FROM ledger WHERE t=?',(self.prev['t'],)).fetchone()
        if record:
            row=json.loads(record[0]);row['events'].extend(self.events)
            row['failed_rebound_state']=copy.deepcopy(p.get('failed_rebound_state'))
            self.db.execute('UPDATE ledger SET body=? WHERE t=?',(json.dumps(row,ensure_ascii=False),self.prev['t']))
        self.events=[]

    def additional_exit_candidates(self,b):
        options=super().additional_exit_candidates(b)
        p=self.position;state=p.get('failed_rebound_state');a=state.get('reference') if state else None
        if not a or a['effective_at']>b['t']:return options
        floor=a['price'];ceiling=a['lower_high']['price']
        if b['open']<floor:
            price=b['open'];phase=0
        elif b['open']>ceiling:
            state['reference']=None
            self.event('failed_rebound_reclaimed',b['t'],trade_id=p['id'],price=b['open'],
                reason='observed opening reclaimed LH before any range-based break; wait for a new confirmed LH')
            return options
        elif b['low']<floor:
            price=floor;phase=1
        else:
            if b['high']>ceiling:
                state['reference']=None
                self.event('failed_rebound_reclaimed',b['t'],trade_id=p['id'],price=ceiling,
                    reason='LH reclaimed without breaking reference low; pattern invalidated')
            return options
        ambiguity=phase==1 and (b['high']>ceiling or
            (p['remaining']==1 and p['t1'] is not None and b['open']<p['t1']<=b['high']))
        candidate=dict(reason='failed_rebound_exit_remaining',price=price,phase=phase,priority=6,
            price_basis='observed opening gap' if phase==0 else 'strict break of previously confirmed pullback low',
            failed_rebound=copy.deepcopy(a),policy=POLICY)
        if ambiguity:
            p['same_minute_exit_ambiguity']=True
            candidate.update(same_minute_order_ambiguous=True,
                tie_rule='unresolved break-low/reclaim/target order; risk exit first, not verified tick execution')
        options.append(candidate)
        return options
