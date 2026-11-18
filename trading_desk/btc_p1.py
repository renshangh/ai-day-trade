"""Opt-in P1 A-entry research adapter; frozen engines and live worker stay intact."""
from __future__ import annotations

import copy

from trading_desk.btc_data import iso
from trading_desk.btc_entry_rules import four_wave_setup
from trading_desk.btc_shock_branches import ExpandedEntryDetector
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay

P1_RULE = dict(name='P1',post_d_complete_holds=2,rebound_high_atr=1.0,
    completed_close_atr=.5,atr='14 completed-bar true ranges known before D candle',
    timing='Completed post-D 15m observations only; no current-bar final values',
    scope='A only; preserve original origin, confirmed turns, HH/HL and shared risk checks')


class P1Detector(ExpandedEntryDetector):
    """Filter/merge A phases before the unchanged A/B validator sees a setup.

    Keep price/ATR observations across consumed-entry resets, just as the
    frozen engine keeps indicator history. Parent scopes and B episodes still
    reset through the original detector. An absent bar never becomes a hold.
    """
    def __init__(self):
        super().__init__(independent_b1_hold=False)
        self.p1_bars = {}
        self.p1_cache = {}
        self.p1_now = 0
        self.p1_reviews = []

    def observe(self,bar,previous,now):
        self.p1_bars[bar['t']] = copy.deepcopy(bar)
        self.p1_now = now
        super().observe(bar,previous,now)

    def low_check(self,point):
        key=(point['time'],point['price'])
        if key not in self.p1_cache:
            start=point['time']//900*900
            bar=self.p1_bars.get(start)
            atr=bar.get('atr_before') if bar else None
            valid=bool(bar and bar['observed_minutes']==15 and atr and atr>0)
            self.p1_cache[key]=dict(low=copy.deepcopy(point),atr=atr,
                cursor=start+900,holds=0,peak=point['price'],best_close=point['price'],
                status='waiting' if valid else 'missing_context',qualified_at=None,
                invalid_bar=None)
        c=self.p1_cache[key]
        while c['status']=='waiting' and c['cursor']+900<=self.p1_now:
            t=c['cursor'];bar=self.p1_bars.get(t)
            if not bar or bar['observed_minutes']!=15:
                c.update(status='missing_context',invalid_bar=t);break
            d=point['price']
            if bar['low']<d:
                c.update(status='extended_same_decline',invalid_bar=t);break
            c['holds']=c['holds']+1 if bar['low']>d else 0
            c['peak']=max(c['peak'],bar['high'])
            c['best_close']=max(c['best_close'],bar['close'])
            c['cursor']=t+900
            if (c['holds']>=2 and c['peak']>=d+c['atr']
                    and c['best_close']>=d+.5*c['atr']):
                c.update(status='qualified',qualified_at=t+900)
        return copy.deepcopy(c)

    def review_scope(self,scope):
        checks=[self.low_check(p) for p in scope['lows']]
        kept=[i for i,c in enumerate(checks) if c['status']=='qualified']
        reasons=[]
        if len(kept)<4:reasons.append('fewer than four P1-confirmed independent lows')
        if not checks or checks[-1]['status']!='qualified':
            reasons.append('current larger D has not passed P1')
        candidate=copy.deepcopy(scope)
        candidate['lows']=[dict(scope['lows'][i],known_at=max(
            scope['lows'][i]['known_at'],checks[i]['qualified_at'])) for i in kept]
        # A failed internal phase extends into the next lower D. The highest
        # intervening original LH is retained, rather than choosing a smaller
        # internal high merely to make the later HH check pass.
        candidate['intervening_highs']=[copy.deepcopy(max(
            scope['intervening_highs'][a:b],key=lambda p:p['price']))
            for a,b in zip(kept,kept[1:])]
        candidate['scope']=scope['scope']+'; P1 distance/close/two-hold phases'
        if not reasons:
            reasons.extend(four_wave_setup(candidate,self.p1_now)['reasons'])
        audit=dict(origin=copy.deepcopy(scope['origin']),original_low_count=len(checks),
            p1_low_count=len(kept),checks=checks,passed=not reasons,reasons=reasons,
            known_at=self.p1_now,hh=copy.deepcopy(scope['hh']),hl=copy.deepcopy(scope['hl']))
        candidate['p1']=copy.deepcopy(audit)
        return candidate,audit

    def setups(self):
        original=super().setups()
        # B objects, order and fields are returned unchanged. Only A scope
        # selection is constrained by P1, before the shared entry validator.
        b=[pair for pair in original if pair[0]!='A']
        ready=[s for s in self.a_scopes if s['lows'] and s.get('hh') and s.get('hl')
            and not s.get('d_broken') and not s.get('hl_broken')]
        reviewed=[self.review_scope(s) for s in ready]
        self.p1_reviews=[a for _,a in reviewed]
        accepted=[c for c,a in reviewed if a['passed']]
        chosen=min(accepted,key=lambda s:s['origin']['time']) if accepted else None
        return ([('A',chosen)] if chosen else [])+b


class P1Mixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.detector=P1Detector()
        self.p1_rejections=[]
        self.p1_rejection_keys=set()

    def scan(self,b,can_trade):
        self.detector.setups()
        prev=self.prev
        if (b['t']>=self.start and prev and prev['observed_minutes']==15
                and prev['t']+900==b['t']//900*900 and b['high']>prev['high']+.01):
            for audit in self.detector.p1_reviews:
                if audit['passed']:continue
                key=(audit['origin']['time'],audit['hl']['time'],prev['t'])
                if key in self.p1_rejection_keys:continue
                self.p1_rejection_keys.add(key)
                self.p1_rejections.append(dict(time_utc=iso(b['t']),trigger=prev['high']+.01,
                    classification='A price crossing blocked before shared risk validation',
                    p1=copy.deepcopy(audit)))
        super().scan(b,can_trade)

    def open_signal(self,b,s):
        super().open_signal(b,s)
        if self.position and 'A' in s['routes']:
            self.position['p1']=copy.deepcopy(s['setup_evidence'].get('p1'))

    def finish(self):
        r=super().finish()
        r['p1_rule']=copy.deepcopy(P1_RULE)
        r['p1_rejections']=self.p1_rejections
        return r


class P1BaselineReplay(P1Mixin,FailedReboundReplay):
    pass


class P1EarlyReplay(P1Mixin,EarlySequentialReplay):
    pass
