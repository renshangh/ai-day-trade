"""BTC-relative ATR% plus explicit coin weight; isolated research, never orders."""
from __future__ import annotations
from dataclasses import dataclass,asdict
import copy
import math
from trading_desk.btc_engine import aggregate
from trading_desk.btc_entry_detector import EntryDetector,point
from trading_desk.refined_entries import RefinedDetector,RefinedBaseline,RefinedEarly
from trading_desk.steeper_shock_research import measure as old_measure

PROTOCOL=dict(version='btc-relative-weighted-shock-1',
    formula='threshold_pct = base_btc_atr * BTC_pre_ATR_pct * max(1, asset_pre_ATR_pct / BTC_pre_ATR_pct) * asset_weight',
    normalization='ATR% = arithmetic mean of 14 prior true ranges / previous completed close * 100; exact same 15-minute frame',
    weight='BTC fixed at 1.0; SOL extra weight is explicit and adjustable, not estimated statistical beta',
    baseline='BTC base 2.0 ATR; compare ATR-only SOL weight 1.0 versus trial extra SOL weight 1.5',
    causality='Both ATR contexts use 15 consecutive complete prior bars; threshold known before shock candle starts. Missing context means no new B shock, never fill/carry.',
    definition='Net previous-close to current-close percentage decline; complete adjacent 15m bars, bearish direction and new scope low',
    unchanged='A/P1, B1 independent hold, B2 priority/lifecycle, original larger-D stops, exits, targets and risk/costs unchanged; F1/F2 not combined',
    fallback='Not a shock does not automatically qualify A: retain all P1 LL/LH, HH/HL and shared checks',
    scope='Comparison only; fixed trial settings before replay, same-month exploratory results, no claim of optimal weights')

@dataclass(frozen=True)
class Settings:
    base_btc_atr:float=2.0
    sol_weight:float=1.5
    def __post_init__(self):
        for name,lo,hi in [('base_btc_atr',2.,6.),('sol_weight',1.,3.)]:
            x=getattr(self,name)
            if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not lo<=x<=hi:
                raise ValueError(f'{name} must be a finite number from {lo} to {hi}')
    def asdict(self):return asdict(self)

class Contexts:
    """Only actual complete aggregates; absent buckets never become observations."""
    def __init__(self,minutes):
        groups={};times=[b['t'] for b in minutes]
        if len(times)!=len(set(times)) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Minutes must be unique and ordered')
        for b in minutes:groups.setdefault(b['t']//900*900,[]).append(b)
        self.bars={t:aggregate(g,900) for t,g in groups.items() if [b['t'] for b in g]==list(range(t,t+900,60))}
        self.cache={}
    def before(self,period):
        if period not in self.cache:
            bars=[self.bars.get(t) for t in range(period-15*900,period,900)]
            result=None
            if all(bars) and bars[-1]['close']>0:
                trs=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(bars,bars[1:])]
                atr=sum(trs)/14
                if atr>0:result=dict(atr=atr,previous_close=bars[-1]['close'],atr_pct=100*atr/bars[-1]['close'],known_at=period,
                    first_source_bar=bars[0]['t'],last_source_bar=bars[-1]['t'],complete_prior_bars=15)
            self.cache[period]=result
        return copy.deepcopy(self.cache[period])

def threshold(symbol,asset,btc,settings):
    if symbol not in ('BTC/USD','SOL/USD'):raise ValueError('Only BTC/USD and SOL/USD are in this comparison')
    if not asset or not btc or asset['known_at']!=btc['known_at']:return None
    ratio=asset['atr_pct']/btc['atr_pct'];weight=1. if symbol=='BTC/USD' else settings.sol_weight
    pct=settings.base_btc_atr*btc['atr_pct']*max(1.,ratio)*weight
    return dict(threshold_pct=pct,btc_atr_pct=btc['atr_pct'],asset_atr_pct=asset['atr_pct'],relative_volatility=ratio,
        volatility_scale=max(1.,ratio),asset_weight=weight,base_btc_atr=settings.base_btc_atr,
        effective_asset_atr=pct/asset['atr_pct'],known_at=asset['known_at'],asset_context=asset,btc_context=btc)

class Policy:
    def __init__(self,symbol,asset_contexts,btc_contexts,settings=Settings(),control=False):
        self.symbol=symbol;self.asset=asset_contexts;self.btc=btc_contexts;self.settings=settings;self.control=control
    def evaluate(self,bar,previous,prior_low):
        old=old_measure(bar,previous,prior_low,'net3')
        if self.control:return old
        k=threshold(self.symbol,self.asset.before(bar['t']),self.btc.before(bar['t']),self.settings)
        complete=old['complete'];drop=100*(previous['close']-bar['close'])/previous['close'] if complete and previous['close']>0 else None
        base=bool(k and complete and prior_low is not None and bar['close']<bar['open'] and bar['low']<prior_low)
        return {**old,'mode':'adaptive_weighted','threshold':k,'net_drop_pct':drop,
            'qualifies':bool(base and drop>=k['threshold_pct']),
            'context_unavailable':k is None}

class AdaptiveDetector(RefinedDetector):
    def __init__(self,policy):super().__init__();self.policy=policy;self.shock_reviews=[]

    def observe(self,bar,previous,now):
        # Advance A and its P1 price history exactly once, while bypassing the
        # old ExpandedEntryDetector's 2-ATR B-creation branch.
        self.p1_bars[bar['t']]=copy.deepcopy(bar);self.p1_now=now
        prior_low=self.lowest;generation=self.generation
        EntryDetector.observe(self,bar,previous,now)
        if self.generation!=generation:prior_low=None
        if bar['observed_minutes']!=15:return
        m=self.policy.evaluate(bar,previous,prior_low)
        if bar['close']<bar['open']:
            self.shock_reviews.append(dict(**m,new_scope_low=prior_low is not None and bar['low']<prior_low))
        c=self.shock_chain
        if c and c['d_broken'] and c['rebound'] is not None:c=None;self.shock_chain=None
        if m['qualifies']:
            c=dict(impulse=copy.deepcopy(bar),atr_before_impulse=bar['atr_before'],atr_before_impulse_known_at=bar['t'],
                previous_close=previous['close'],lowest_before_impulse=prior_low,d=point(bar,'low',now),extensions=[],
                rebound=None,hl=None,d_broken=False,hl_broken=False,stabilization_bar=copy.deepcopy(bar))
            self.shock_chain=c
            if not self.policy.control:c['adaptive_shock']=copy.deepcopy(m)
        elif c:
            if c['rebound'] is None and bar['low']<c['d']['price']:
                c['extensions'].append(point(bar,'low',now));c['d']=point(bar,'low',now)
                c['d_broken']=False;c['hl']=None;c['hl_broken']=False
            if not c['d_broken']:
                c['stabilization_bar']=copy.deepcopy(bar)
                if c['rebound'] is None:
                    if bar['close']>bar['open'] and bar['low']>c['d']['price']:c['rebound']=copy.deepcopy(bar)
                elif bar['t']>=c['rebound']['t']+900:
                    pullback=(previous and bar['low']<previous['low']) or bar['close']<bar['open']
                    if pullback and (c['hl'] is None or bar['low']<c['hl']['price']):c['hl']=point(bar,'low',now);c['hl_broken']=False
        if not c:return
        key=(c['d']['time'],c['d']['price'])
        if c.get('refined_d_key')!=key:c['refined_d_key']=key;c['refined_first_hold']=None
        if (not c.get('refined_retired') and not c['d_broken'] and c.get('refined_first_hold') is None
                and bar['t']>=c['d']['known_at'] and bar['low']>=c['d']['price'] and bar['close']>bar['low']):
            c['refined_first_hold']=copy.deepcopy(bar)

class AdaptiveMixin:
    def __init__(self,*args,adaptive_policy,**kwargs):
        super().__init__(*args,**kwargs);self.adaptive_policy=adaptive_policy;self.detector=AdaptiveDetector(adaptive_policy)
    def open_signal(self,b,s):
        super().open_signal(b,s)
        if self.position:self.position['adaptive_shock']=copy.deepcopy(s['setup_evidence'].get('adaptive_shock'))
    def finish(self):
        r=super().finish();r['adaptive_protocol']=PROTOCOL;r['adaptive_settings']=self.adaptive_policy.settings.asdict()
        r['shock_reviews']=copy.deepcopy(self.detector.shock_reviews);return r

class AdaptiveBaseline(AdaptiveMixin,RefinedBaseline):pass
class AdaptiveEarly(AdaptiveMixin,RefinedEarly):pass
