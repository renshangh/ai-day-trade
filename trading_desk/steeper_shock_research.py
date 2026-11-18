"""Isolated shock definition on the prior refined entry draft, no live promotion."""
import copy
from trading_desk.refined_entries import RefinedDetector,RefinedBaseline,RefinedEarly
from trading_desk.btc_entry_detector import EntryDetector,point

PROTOCOL=dict(version='steeper-net-shock-draft-1',threshold=3.0,
    metric='(previous complete 15m close - current complete 15m close) / ATR known before current candle',
    duration_seconds=900,requirements='Complete adjacent 15m observations, bearish candle and new scope low, net close decline >=3 pre-candle ATR',
    baseline='Prior refined A/P1 + first-hold B1 + B2-first draft uses >=2 ATR previous-close/open-to-low excursion',
    nonshock='A candidate only; still needs four independent P1 LL/LH phases, HH/HL and shared checks. Otherwise watch/unclassified, never auto-buy A.',
    unchanged='Prior refined A rules, B1/B2 lifecycle/priority, original risk/targets/exits/costs fixed. Exit overlays not combined.',
    angle='ATR per fixed 15 minutes, not chart-screen degrees or a fitted slope threshold')


def measure(bar,previous,prior_low,mode='net3'):
    if mode not in ('net3','legacy'):raise ValueError('Choose net3 or legacy control')
    atr=bar.get('atr_before');complete=bool(previous and bar['observed_minutes']==15 and previous['observed_minutes']==15 and previous['t']+900==bar['t'])
    net=(previous['close']-bar['close'])/atr if complete and atr and atr>0 else None
    excursion=(max(bar['open'],previous['close'])-bar['low'])/atr if complete and atr and atr>0 else None
    # The control must reproduce the prior adapter even at partial prior
    # context; only the new draft adds adjacent-complete context explicitly.
    context=complete if mode=='net3' else bool(previous and bar['observed_minutes']==15)
    if context and mode=='legacy' and atr and atr>0:
        excursion=(max(bar['open'],previous['close'])-bar['low'])/atr
    base=bool(context and atr and prior_low is not None and bar['close']<bar['open'] and bar['low']<prior_low)
    return dict(net_drop_atr=net,excursion_atr=excursion,atr=atr,complete=complete,
        qualifies=bool(base and (net>=3 if mode=='net3' else excursion>=2)),mode=mode,
        known_at=bar['t']+900,bar_time=bar['t'])


class SteeperDetector(RefinedDetector):
    def __init__(self,mode='net3'):super().__init__();self.mode=mode;self.shock_reviews=[]

    def observe(self,bar,previous,now):
        # Advance A and its P1 price history exactly once, while bypassing the
        # old ExpandedEntryDetector's 2-ATR B-creation branch.
        self.p1_bars[bar['t']]=copy.deepcopy(bar);self.p1_now=now
        prior_low=self.lowest;generation=self.generation
        EntryDetector.observe(self,bar,previous,now)
        if self.generation!=generation:prior_low=None
        if bar['observed_minutes']!=15:return
        m=measure(bar,previous,prior_low,self.mode)
        if m['excursion_atr'] is not None and m['excursion_atr']>=2 and bar['close']<bar['open']:
            self.shock_reviews.append(dict(**m,new_scope_low=prior_low is not None and bar['low']<prior_low))
        c=self.shock_chain
        if c and c['d_broken'] and c['rebound'] is not None:c=None;self.shock_chain=None
        if m['qualifies']:
            c=dict(impulse=copy.deepcopy(bar),atr_before_impulse=bar['atr_before'],atr_before_impulse_known_at=bar['t'],
                previous_close=previous['close'],lowest_before_impulse=prior_low,d=point(bar,'low',now),extensions=[],
                rebound=None,hl=None,d_broken=False,hl_broken=False,stabilization_bar=copy.deepcopy(bar))
            self.shock_chain=c
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


class ShockMixin:
    def __init__(self,*args,shock_mode='net3',**kwargs):
        super().__init__(*args,**kwargs);self.detector=SteeperDetector(shock_mode)
    def finish(self):
        r=super().finish();r['steeper_shock_protocol']=PROTOCOL;r['shock_reviews']=copy.deepcopy(self.detector.shock_reviews);return r

class ShockBaseline(ShockMixin,RefinedBaseline):pass
class ShockEarly(ShockMixin,RefinedEarly):pass
