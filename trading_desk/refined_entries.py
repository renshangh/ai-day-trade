"""Separate A/P1, first-hold B1 and B2-first historical comparison only."""
from __future__ import annotations
import copy
from trading_desk.btc_p1 import P1Detector,P1Mixin,P1_RULE
from trading_desk.btc_entry_detector import point
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_data import iso

PROTOCOL=dict(version='refined-AB-draft-1',A=P1_RULE,
    B1='First independent completed post-D off-low candle holding D; breakout only in its immediately following 15m candle. No later rolling stabilization reference.',
    B1_window_interpretation='Operational interpretation of first stabilization, fixed before results: first confirmation candle must be the previous complete candle at entry; after that phase closes, wait for B2.',
    B2='Inherited completed shock rebound then later qualifying HL; check B2 before B1; never fall back to B1 after its first-hold window.',
    shock='Inherited causally known 2-ATR bearish new-low impulse; a new qualifying impulse starts a fresh B episode without resetting A.',
    lifecycle='D may extend before any independent hold; after the first hold, a D breach retires this B episode and cannot roll D downward to rescue that attempt. A new qualifying shock can start a new episode.',
    priority=['A','B2','B1'],unchanged='Parent-D stop/buffer, HL tolerance, targets, full exit variants, risk/costs, consumed history and missing-data rules unchanged. 2R remains advisory.',
    no_expiry_fitting='No chosen hour-count expiry or outcome-tuned thresholds.',
    execution='Historical comparison only; no worker promotion or broker orders')


class RefinedDetector(P1Detector):
    def observe(self,bar,previous,now):
        prior_low=self.lowest;generation=self.generation
        super().observe(bar,previous,now)
        if self.generation!=generation:prior_low=None
        if bar['observed_minutes']!=15:return
        atr=bar.get('atr_before')
        fresh=bool(previous and atr and prior_low is not None and bar['close']<bar['open']
            and bar['low']<prior_low and max(bar['open'],previous['close'])-bar['low']>=2*atr)
        chain=self.shock_chain
        if fresh and (chain is None or chain['impulse']['t']!=bar['t']):
            # Unlike the permissive frozen detector, a fresh qualifying shock
            # owns a new B episode rather than inheriting a stale warmup D.
            chain=dict(impulse=copy.deepcopy(bar),atr_before_impulse=atr,atr_before_impulse_known_at=bar['t'],
                previous_close=previous['close'],lowest_before_impulse=prior_low,d=point(bar,'low',now),
                extensions=[],rebound=None,hl=None,d_broken=False,hl_broken=False,stabilization_bar=copy.deepcopy(bar))
            self.shock_chain=chain
        if not chain:return
        d_key=(chain['d']['time'],chain['d']['price'])
        if chain.get('refined_d_key')!=d_key:
            chain['refined_d_key']=d_key
            chain['refined_first_hold']=None
        if (not chain.get('refined_retired') and not chain['d_broken']
                and chain.get('refined_first_hold') is None and bar['t']>=chain['d']['known_at']
                and bar['low']>=chain['d']['price'] and bar['close']>bar['low']):
            chain['refined_first_hold']=copy.deepcopy(bar)

    def invalidate(self,minute):
        super().invalidate(minute)
        chain=self.shock_chain
        if chain and chain.get('refined_first_hold') and chain['d_broken']:
            chain['refined_retired']=True

    def b_state(self):
        c=self.shock_chain
        if not c:return dict(phase='no_B_episode')
        first=c.get('refined_first_hold')
        active=bool(first and first['t']+900==self.p1_now and not c['d_broken'] and not c.get('refined_retired'))
        return dict(phase='retired' if c.get('refined_retired') or c['d_broken'] else
            'B2_HL_available' if c['rebound'] and c['hl'] and not c['hl_broken'] else
            'B1_first_hold_breakout_window' if active else 'waiting_for_independent_hold' if first is None else 'B1_window_closed_wait_for_B2',
            impulse=iso(c['impulse']['t']),d=copy.deepcopy(c['d']),first_hold=iso(first['t']) if first else None,
            first_hold_known_at=iso(first['t']+900) if first else None,b1_window_active=active,
            rebound=iso(c['rebound']['t']) if c['rebound'] else None,hl=copy.deepcopy(c['hl']))

    def setups(self):
        original=super().setups();a=[x for x in original if x[0]=='A'];c=self.shock_chain
        if not c or c['d_broken'] or c.get('refined_retired'):return a
        b2=[x for x in original if x[0]=='B2']
        first=c.get('refined_first_hold')
        if not first or first['t']+900!=self.p1_now:return a+b2
        # A qualified B2 is always evaluated before a possible B1. In normal
        # sequence a genuine later HL already means the first-hold window ended.
        candidate=copy.deepcopy(c);candidate['stabilization_bar']=copy.deepcopy(first)
        return a+b2+[('B1',candidate)]

    def snapshot(self):
        result=super().snapshot();result['refined_B_phase']=self.b_state();return result


class RefinedMixin(P1Mixin):
    def __init__(self,*args,original_entry_times=(),**kwargs):
        super().__init__(*args,**kwargs)
        self.detector=RefinedDetector();self.original_entry_times=set(original_entry_times)
        self.original_entry_reviews=[];self.reviewed_minutes=set()

    def scan(self,b,can_trade):
        if b['t'] in self.original_entry_times and b['t'] not in self.reviewed_minutes:
            routes=[r for r,_ in self.detector.setups()]
            self.original_entry_reviews.append(dict(time_utc=iso(b['t']),holding_trade=self.position['id'] if self.position else None,
                can_trade=can_trade,routes_available=routes,B_phase=self.detector.b_state(),
                A_reviews=[dict(original_low_count=a['original_low_count'],p1_low_count=a['p1_low_count'],passed=a['passed'],reasons=a['reasons']) for a in self.detector.p1_reviews]))
            self.reviewed_minutes.add(b['t'])
        super().scan(b,can_trade)

    def open_signal(self,b,s):
        phase=self.detector.b_state()
        super().open_signal(b,s)
        if self.position:self.position['entry_refinement']=dict(recorded_route=s['route'],phase_at_entry=phase)

    def finish(self):
        r=super().finish();r['refined_entry_protocol']=copy.deepcopy(PROTOCOL)
        r['original_entry_reviews']=copy.deepcopy(self.original_entry_reviews);return r


class RefinedBaseline(RefinedMixin,FailedReboundReplay):pass
class RefinedEarly(RefinedMixin,EarlySequentialReplay):pass
