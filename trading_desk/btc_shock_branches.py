"""Opt-in B1/B2 research extension; no implicit monthly rollout or broker calls."""
import copy
from trading_desk.btc_entry_detector import EntryDetector,point
from trading_desk.btc_entry_rules import Rules


def expanded_shock_setup(setup,now,branch,rules=Rules()):
    impulse=setup['impulse'];d=setup['d'];why=[]
    down=max(impulse['open'],setup['previous_close'])-impulse['low']
    if not (setup['atr_before_impulse']>0 and impulse['close']<impulse['open']
            and down>=rules.shock_down_atr*setup['atr_before_impulse']
            and impulse['low']<setup['lowest_before_impulse']):
        why.append('no causally established 2-ATR bearish new-low impulse')
    if setup['atr_before_impulse_known_at']>impulse['t']:
        why.append('pre-impulse ATR is not known before the impulse')
    if not (impulse['t']+900<=now and d['time']<=d['known_at']<=now):
        why.append('impulse or extended D is not yet known')
    if impulse['observed_minutes']!=15 or setup['d_broken']:
        why.append('incomplete impulse or extended D already broken')
    hl=setup.get('hl');known=[impulse['t']+900,d['known_at']]
    if branch=='B1':
        stop_bar=setup['stabilization_bar']
        if not (stop_bar['t']+900<=now and stop_bar['observed_minutes']==15
                and stop_bar['close']>stop_bar['low'] and stop_bar['low']>=d['price']):
            why.append('no completed off-low stabilization reference holding current D')
        known.append(stop_bar['t']+900)
        # No HL is claimed here. The ensuing intrabar high break confirms the
        # first reversal; a lower wick alone is never a buy signal.
        hl=None
    elif branch=='B2':
        rebound=setup.get('rebound')
        if not rebound or not hl:
            why.append('completed rebound and later HL are required')
        else:
            if not (rebound['t']+900<=now and rebound['close']>rebound['open']
                    and rebound['low']>d['price'] and rebound['observed_minutes']==15
                    and hl['time']>=rebound['t']+900 and hl['time']<=hl['known_at']<=now
                    and hl['price']>d['price'] and not setup['hl_broken']):
                why.append('rebound/HL is incomplete, not higher, or broken')
            known.extend([rebound['t']+900,hl['known_at']])
    else:
        raise ValueError('Choose B1 first reversal or B2 HL retest')
    return dict(rule='B1_FIRST_STABILIZATION' if branch=='B1' else 'B2_HIGHER_LOW_RETEST',
        setup_passed=not why,reasons=why,setup_known_at=max(known),
        d=d['price'],hl=hl['price'] if hl else None,requires_hl=branch=='B2',
        downward_atr_multiple=down/setup['atr_before_impulse'] if setup['atr_before_impulse']>0 else None,
        four_lower_lows_required=False)


def independent_b1_setup(setup,now,confirmation_bar,*,d_intact=None,rules=Rules()):
    """Approved independent post-D hold; historical aliases remain permissive.

    Current research uses this validator; release 0.1 keeps its snapshot. The
    next entry may be considered only after a separate complete 15m bar, whose
    start is at/after the D candle's completed known_at, has held that same D.
    It never rolls D downward to make a failed confirmation pass.
    """
    candidate=copy.deepcopy(setup)
    if confirmation_bar is not None:candidate['stabilization_bar']=confirmation_bar
    if d_intact is not None:candidate['d_broken']=not d_intact
    intact=not candidate['d_broken']
    original=expanded_shock_setup(candidate,now,'B1',rules)
    why=list(original['reasons']);d=setup['d'];known=[original['setup_known_at']]
    if not intact:why.append('the original D was breached while waiting; this setup is invalid')
    if confirmation_bar is None:
        why.append('no independent completed post-D confirmation candle')
    else:
        b=confirmation_bar
        if b['observed_minutes']!=15 or b['t']+900>now:
            why.append('confirmation candle is incomplete or not yet known')
        if b['t']<d['known_at']:
            why.append('D candle itself cannot serve as its own post-D confirmation')
        if b['low']<d['price']:
            why.append('confirmation candle did not hold the original D')
        known.append(b['t']+900)
    passed=not why
    return dict(**{k:v for k,v in original.items() if k not in ('rule','setup_passed','reasons','setup_known_at')},
        rule='B1_INDEPENDENT_POST_D_HOLD',setup_passed=passed,reasons=why,
        setup_known_at=max(known),independent_confirmation_required=True,
        confirmation_bar_time=confirmation_bar['t'] if confirmation_bar else None,
        confirmation_known_at=confirmation_bar['t']+900 if confirmation_bar else None,
        entry_not_before=d['known_at']+900,
        trigger_reference=confirmation_bar['high']+rules.trigger_increment if passed else None)


class ExpandedEntryDetector(EntryDetector):
    """Retain the impulse through extensions until a full rebound holds D.

    No time-expiry threshold is introduced. After that rebound, a broken D
    invalidates the episode; before it, only completed lower-low bars may
    extend D. Already-open positions never receive a downward stop change.
    """
    def __init__(self,*,independent_b1_hold=False):
        super().__init__();self.shock_chain=None
        self.independent_b1_hold=independent_b1_hold

    def reset(self,reason):
        super().reset(reason);self.shock_chain=None

    def invalidate(self,minute):
        super().invalidate(minute)
        chain=self.shock_chain
        if chain:
            broken=minute['low']<chain['d']['price'] if self.independent_b1_hold else minute['low']<=chain['d']['price']
            if broken:chain['d_broken']=True
            if chain['hl'] and minute['low']<chain['hl']['price']:chain['hl_broken']=True

    def observe(self,bar,previous,now):
        prior_low=self.lowest
        generation=self.generation
        super().observe(bar,previous,now)
        if self.generation!=generation:prior_low=None
        if bar['observed_minutes']!=15:return
        chain=self.shock_chain;atr=bar.get('atr_before')
        is_impulse=bool(previous and atr and prior_low is not None and
            bar['close']<bar['open'] and bar['low']<prior_low and
            max(bar['open'],previous['close'])-bar['low']>=2*atr)
        if chain and chain['d_broken'] and chain['rebound'] is not None:
            chain=None;self.shock_chain=None
        if chain is None and is_impulse:
            chain=dict(impulse=copy.deepcopy(bar),atr_before_impulse=atr,
                atr_before_impulse_known_at=bar['t'],previous_close=previous['close'],
                lowest_before_impulse=prior_low,d=point(bar,'low',now),
                extensions=[],rebound=None,hl=None,d_broken=False,hl_broken=False,
                stabilization_bar=copy.deepcopy(bar))
            self.shock_chain=chain
        elif chain:
            if chain['rebound'] is None and bar['low']<chain['d']['price']:
                chain['extensions'].append(point(bar,'low',now))
                chain['d']=point(bar,'low',now)
                chain['d_broken']=False;chain['hl']=None;chain['hl_broken']=False
            if not chain['d_broken']:
                chain['stabilization_bar']=copy.deepcopy(bar)
                if chain['rebound'] is None:
                    if bar['close']>bar['open'] and bar['low']>chain['d']['price']:
                        chain['rebound']=copy.deepcopy(bar)
                elif bar['t']>=chain['rebound']['t']+900:
                    pullback=(previous and bar['low']<previous['low']) or bar['close']<bar['open']
                    if pullback and (chain['hl'] is None or bar['low']<chain['hl']['price']):
                        chain['hl']=point(bar,'low',now);chain['hl_broken']=False

    def setups(self):
        out=[x for x in super().setups() if x[0]=='A']
        chain=self.shock_chain
        if chain and not chain['d_broken']:
            out.append(('B1',chain))
            if chain['rebound'] and chain['hl'] and not chain['hl_broken']:
                out.append(('B2',chain))
        return out

    def snapshot(self):
        out={k:v for k,v in super().snapshot().items() if k=='A'}
        if self.shock_chain:
            c=self.shock_chain
            out['B1']=dict(d=c['d'],hl=None,lower_low_count=None,
                hh=None,rebound=c['rebound'],invalid=c['d_broken'],
                independent_confirmation_required=self.independent_b1_hold,
                confirmation_not_before=c['d']['known_at']+900 if self.independent_b1_hold else None)
            out['B2']=dict(d=c['d'],hl=c['hl'],lower_low_count=None,
                hh=None,rebound=c['rebound'],invalid=c['d_broken'] or c['hl_broken'])
        return out
