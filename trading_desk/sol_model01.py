"""SOL-only 0.1 research candidate; never imported by the BTC live worker."""
from __future__ import annotations
import copy
from dataclasses import dataclass
from trading_desk.btc_entry_detector import EntryDetector,point
from trading_desk.btc_shock_branches import ExpandedEntryDetector
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.adaptive_shock import Contexts
from scripts.btc_structure_retest import Config

ARMS=('original_e1','sol_net_shock','independent_hold','sol_01')
PROTOCOL=dict(version='SOL-0.1-candidate',symbol='SOL/USD',candidate='sol_01',status='Research candidate; not promoted',
    shock='Complete bearish 15m new-scope-low candle, net previous-close to close decline >= 2.0 times SOL pre-shock ATR14. ATR requires 15 consecutive fully observed prior 15m bars and is known before shock starts.',
    B1='An independent complete 15m candle starting at or after D confirmation must hold that D; only a later intraminute break above the prior completed high can enter. The D candle cannot confirm itself.',
    B2='Original completed rebound, later higher-low retest and breakout; original A/B1/B2 route priority and consumed history retained.',
    A='Original mechanical A entry; no BTC observation, cross-asset filter, P1 or C gate.',
    unchanged='Original larger-D stop and ATR buffer, target construction, positive target space with 2R advisory only, E1 exits, 25% first sale/remaining 75%, spread/slippage proxy and all other risk settings unchanged.',
    ablation='Original SOL E1; SOL net shock only; independent B1 hold only; fixed combined SOL 0.1 candidate. Publish all arms without selecting one after results.',
    validation='Same saved October 10-November 9 2026 UTC month; full sequence plus separately flat-start first14/next7/final9-day diagnostics. Previously studied tape, not unseen validation; no grid search or post-result tuning.',
    execution='No live installation, activation, broker or broker-paper orders; original BTC process/session and frozen 0.2 untouched.')


@dataclass(frozen=True)
class Settings:
    net_drop_atr:float=2.0
    independent_b1_hold:bool=True


class SolDetector(ExpandedEntryDetector):
    def __init__(self,market,settings=Settings()):
        super().__init__(independent_b1_hold=settings.independent_b1_hold)
        self.market=market;self.settings=settings;self.shock_reviews=[]

    def observe(self,bar,previous,now):
        prior_low=self.lowest;generation=self.generation
        # Advance the unchanged A detector once, bypassing the old wick-shock branch.
        EntryDetector.observe(self,bar,previous,now)
        if generation!=self.generation:prior_low=None
        if bar['observed_minutes']!=15:return
        context=self.market.before(bar['t'])
        adjacent=bool(previous and previous['observed_minutes']==15 and previous['t']+900==bar['t'])
        drop=(previous['close']-bar['close'])/context['atr'] if adjacent and context else None
        qualifies=bool(context and adjacent and prior_low is not None and bar['close']<bar['open']
            and bar['low']<prior_low and drop>=self.settings.net_drop_atr)
        review=dict(time=bar['t'],known_at=now,context=context,net_drop_atr=drop,qualifies=qualifies,
            threshold_atr=self.settings.net_drop_atr,missing_context=context is None,prior_low=prior_low)
        if bar['close']<bar['open']:self.shock_reviews.append(copy.deepcopy(review))
        chain=self.shock_chain
        if chain and chain['d_broken'] and chain['rebound'] is not None:
            chain=None;self.shock_chain=None
        if chain is None and qualifies:
            chain=dict(impulse=copy.deepcopy(bar),atr_before_impulse=context['atr'],atr_before_impulse_known_at=bar['t'],
                previous_close=previous['close'],lowest_before_impulse=prior_low,d=point(bar,'low',now),
                extensions=[],rebound=None,hl=None,d_broken=False,hl_broken=False,
                stabilization_bar=copy.deepcopy(bar),sol_shock=review)
            self.shock_chain=chain
        elif chain:
            if chain['rebound'] is None and bar['low']<chain['d']['price']:
                chain['extensions'].append(point(bar,'low',now));chain['d']=point(bar,'low',now)
                chain['d_broken']=False;chain['hl']=None;chain['hl_broken']=False
            if not chain['d_broken']:
                chain['stabilization_bar']=copy.deepcopy(bar)
                if chain['rebound'] is None:
                    if bar['close']>bar['open'] and bar['low']>chain['d']['price']:chain['rebound']=copy.deepcopy(bar)
                elif bar['t']>=chain['rebound']['t']+900:
                    pullback=(previous and bar['low']<previous['low']) or bar['close']<bar['open']
                    if pullback and (chain['hl'] is None or bar['low']<chain['hl']['price']):chain['hl']=point(bar,'low',now);chain['hl_broken']=False


def make_engine(arm,start,end,db,market):
    if arm not in ARMS:raise ValueError('Choose a declared SOL-only research arm')
    hold=arm in ('independent_hold','sol_01')
    engine=EarlySequentialReplay(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),
        early_policy='E1',expanded_b=True,consume_entry_history=True,b1_independent_hold=hold)
    if arm in ('sol_net_shock','sol_01'):engine.detector=SolDetector(market,Settings(independent_b1_hold=hold))
    return engine
