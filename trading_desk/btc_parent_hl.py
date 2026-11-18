"""Separate C parent-HL research route on top of unchanged P1/A/B engines."""
from __future__ import annotations

import copy
from collections import deque
from datetime import datetime

from trading_desk.btc_data import iso
from trading_desk.btc_engine import aggregate,partial_context,NY
from trading_desk.btc_entry_rules import entry_signal
from trading_desk.btc_p1 import P1BaselineReplay,P1EarlyReplay

C_RULE=dict(name='C_PARENT_HL_CONTINUATION',parent_seconds=3600,turn_seconds=900,
    confirmed_turn='strict low/high with one complete adjacent candle each side; outside turns excluded',
    parent_selection='latest HL, then most recent intact confirmed 1h parent below it; no RR-based parent search',
    rebound='highest confirmed 15m high after parent D and before the fresh HL',
    fresh_episode='HL candle begins at/after the most recent entry consumption floor; first crossing only',
    warmup='context only; a crossing consumes its HL episode even before activation, without a trade',
    priority='existing P1 A/B entries first, then C; held and exit minutes cannot open a new trade',
    stop_basis='larger parent D; existing 0.25 entry-ATR buffer',
    hl_tolerance_atr=.1,trigger_increment=.01,orders_enabled=False)


class ParentHLDetector:
    def __init__(self):
        self.window=deque(maxlen=3)
        self.hour_pending=[]
        self.hours=deque(maxlen=3)
        self.parents=[];self.highs=[];self.lows=[]
        self.floor=None;self.now=0

    def gap(self):
        # An unknown path cannot certify that the parent/HL survived.
        self.window.clear();self.hour_pending=[];self.hours.clear()
        self.parents=[];self.highs=[];self.lows=[]

    def consume(self,floor):
        # Retain larger price context, but never recycle an old actionable HL.
        self.floor=floor

    @staticmethod
    def point(b,kind,known):
        return dict(time=b[kind+'_t'],bar_time=b['t'],price=b[kind],known_at=known,broken=False)

    def observe(self,bar,now):
        if bar['observed_minutes']!=15 or (self.window and bar['t']!=self.window[-1]['t']+900):
            self.gap()
            if bar['observed_minutes']!=15:return
        self.now=now;self.window.append(copy.deepcopy(bar))
        if len(self.window)==3:
            left,middle,right=self.window
            low=middle['low']<min(left['low'],right['low'])
            high=middle['high']>max(left['high'],right['high'])
            if low and not high:self.lows.append(self.point(middle,'low',now))
            if high and not low:self.highs.append(self.point(middle,'high',now))
        if bar['t']%3600==0:self.hour_pending=[copy.deepcopy(bar)]
        elif self.hour_pending and bar['t']==self.hour_pending[-1]['t']+900:
            self.hour_pending.append(copy.deepcopy(bar))
        else:self.hour_pending=[]
        if len(self.hour_pending)==4:
            self.hours.append(aggregate(self.hour_pending,3600));self.hour_pending=[]
            if len(self.hours)==3:
                left,middle,right=self.hours
                adjacent=middle['t']==left['t']+3600 and right['t']==middle['t']+3600
                low=middle['low']<min(left['low'],right['low'])
                high=middle['high']>max(left['high'],right['high'])
                if adjacent and low and not high:self.parents.append(self.point(middle,'low',now))

    def invalidate(self,minute):
        for p in self.parents:
            if minute['low']<=p['price']:p['broken']=True
        for p in self.lows:
            if minute['low']<p['price']:p['broken']=True

    def ready(self,atr):
        if not atr or not self.lows:return None
        # A broken recent HL cannot fall back to a stale older HL.
        hl=self.lows[-1]
        if hl['broken'] or (self.floor is not None and hl['bar_time']<self.floor):return None
        candidates=[]
        for parent in self.parents:
            if (parent['broken'] or parent['known_at']>self.now or parent['time']>=hl['time']
                    or hl['price']<=parent['price']+.1*atr):continue
            peaks=[h for h in self.highs if parent['time']<h['time']<hl['time']
                and h['known_at']<=self.now and h['price']>hl['price']]
            if not peaks:continue
            rebound=max(peaks,key=lambda h:h['price'])
            candidates.append(dict(parent=copy.deepcopy(parent),hl=copy.deepcopy(hl),
                rebound=copy.deepcopy(rebound),known_at=max(parent['known_at'],hl['known_at'],rebound['known_at'])))
        return max(candidates,key=lambda s:s['parent']['time']) if candidates else None


def continuation_signal(setup,previous,minute,atr,target):
    state=dict(rule=C_RULE['name'],setup_passed=True,reasons=[],
        setup_known_at=setup['known_at'],d=setup['parent']['price'],hl=setup['hl']['price'])
    signal=entry_signal(state,dict(previous_bar=previous,minute=minute,
        atr_before_entry=atr,atr_known_at=minute['t']//900*900,
        hl_unbroken_before_trigger=not setup['hl']['broken'],
        target=dict(price=target,known_at=minute['t']) if target is not None else None))
    if minute['low']<setup['hl']['price']:
        signal['structural_price_signal']=signal['qualified_candidate']=False
        signal['signal_reasons'].append('HL and trigger crossed in the same observed minute; order unknown')
    return signal


class ContinuationMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.parent_hl=ParentHLDetector();self.c_emitted=set();self.c_arms=[];self.c_arm_keys=set()

    def minute(self,b):
        if self.last_minute is not None and b['t']!=self.last_minute+60:self.parent_hl.gap()
        super().minute(b)
        self.parent_hl.invalidate(b)

    def complete(self):
        had=bool(self.minutes)
        super().complete()
        if not had:return
        bar=self.prev;self.parent_hl.observe(bar,bar['t']+900)
        setup=self.parent_hl.ready(self.atr)
        if setup and setup['known_at']>=self.start:
            key=(setup['parent']['time'],setup['hl']['time'])
            if key not in self.c_arm_keys:
                self.c_arm_keys.add(key);self.c_arms.append(dict(armed_at=iso(setup['known_at']),setup=setup))

    def scan(self,b,can_trade):
        setup=self.parent_hl.ready(self.atr)
        prev=self.prev
        eligible=bool(setup and prev and prev['observed_minutes']==15
            and prev['t']+900==b['t']//900*900 and setup['known_at']<=b['t']
            and setup['hl']['time'] not in self.c_emitted and b['high']>prev['high']+.01)
        # Snapshot C before an A/B entry consumes earlier setups. A/B retain
        # priority; a simultaneous C candidate remains visible as held/skipped.
        candidate=None
        if eligible:
            self.c_emitted.add(setup['hl']['time'])
            price=max(prev['high']+.01,b['open'])
            t1,t2=self.targets(price,dict(high=setup['rebound']['price']),b['t'],self.atr)
            candidate=continuation_signal(setup,prev,b,self.atr,t1)
            candidate.update(route='C',routes=['C'],time_utc=iso(b['t']),
                time_ny=datetime.fromtimestamp(b['t'],NY).isoformat(),quote_reference=b['volume']==0,
                interval_end=iso(b['t']+60),previous_bar_time=iso(prev['t']),t1=t1,t2=t2,atr=self.atr,
                setup_evidence=copy.deepcopy(setup),context_partial=partial_context(self.recent),
                references=dict(l1={k:iso(v) if k in ('time','known_at') else v for k,v in setup['parent'].items() if k in ('time','price','known_at')},
                    l2={k:iso(v) if k in ('time','known_at') else v for k,v in setup['hl'].items() if k in ('time','price','known_at')},
                    h1=dict(time=iso(setup['rebound']['time']),price=setup['rebound']['price']),
                    trigger=prev['high']+.01,stop=candidate['initial_stop'],target=t1,
                    net_reward_risk=candidate['net_reward_risk']))
        super().scan(b,can_trade)
        if candidate is None or b['t']<self.start:return
        s=candidate;s['id']=len(self.signals)+1;s['trade_id']=None
        s['decision']=('entry' if s['qualified_candidate'] and can_trade and self.position is None else
            'held_position' if s['qualified_candidate'] and self.position else
            'exit_minute_no_reentry' if s['qualified_candidate'] else
            'risk_rejected' if s['structural_price_signal'] else 'structure_rejected')
        self.signals.append(s);self.counter['candidates']+=1;self.counter['route_C']+=1
        if s['decision']=='entry':self.open_signal(b,s)
        else:
            if not s['qualified_candidate']:self.counter['rejected']+=1
            self.event('entry_skipped' if s['qualified_candidate'] else 'entry_rejected',b['t'],
                signal_id=s['id'],entry_rule='C',price=s['entry_reference'],
                reason='; '.join(s['signal_reasons']) or s['risk_reason'] or s['decision'])

    def open_signal(self,b,s):
        super().open_signal(b,s)
        self.parent_hl.consume(self.entry_history_start)
        if self.position and s['route']=='C':self.position['continuation']=copy.deepcopy(s['setup_evidence'])

    def finish(self):
        result=super().finish();result['continuation_rule']=copy.deepcopy(C_RULE)
        result['continuation_arms']=self.c_arms
        result['signal_counts']['C']=sum('C' in s['routes'] for s in result['signals'])
        return result


class ContinuationBaselineReplay(ContinuationMixin,P1BaselineReplay):
    pass


class ContinuationEarlyReplay(ContinuationMixin,P1EarlyReplay):
    pass
