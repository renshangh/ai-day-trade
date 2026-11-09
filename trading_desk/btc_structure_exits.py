"""Opt-in case study: midpoint warnings, first target, confirmed 15m structure.

This mixin does not change V1/V2/month defaults. Complete left/right neighbours
confirm a higher low; a later complete bar must exceed its prior rally peak
before that low can become an active structure reference. No future bars or
provisional candle lows may tighten it. Hard protection remains independent.
"""
import copy
import json

from trading_desk.btc_data import iso,ts
from trading_desk.btc_approved_exits import candidates,direction_context,direction_passed

POLICY='midpoint-warning-t1-then-confirmed-15m-structure-case-v3'


def giveback_diagnostic(entry,initial_stop,entry_time,minute,observations,reference_price):
    """Holding diagnostic only: no threshold, regime label, entry or sale.

    Exclude the entry minute's unresolved H/L order and the current minute's
    unfinished H/L/C. A later high in the same 15m candle is not known yet.
    """
    known=[b for b in observations if entry_time<b['t']<minute['t']]
    peak=max([entry,minute['open'],reference_price]+[b['high'] for b in known])
    mfe=peak-entry;drawdown=peak-reference_price;risk=entry-initial_stop
    return dict(time_utc=iso(minute['t']),reference_price=reference_price,
        highest_known_price=peak,max_favourable_excursion=mfe,profit_giveback=drawdown,
        giveback_fraction=drawdown/mfe if mfe>0 else None,
        giveback_in_initial_r=drawdown/risk if risk>0 else None,
        known_minutes_through=iso(known[-1]['t']) if known else None,
        current_minute_range_used=False,threshold=None,action='diagnostic_only',
        limitation='near-zero favourable excursion makes ratio unstable; not an entry-time prediction')


def last_minute_state(b,prefix,previous):
    period=b['t']//900*900
    if b['t']%900!=840 or [x['t'] for x in prefix]!=list(range(period,b['t'],60)):
        return None
    context=direction_context(b,prefix,previous)
    high=max(b['open'],max(x['high'] for x in prefix))
    low=min(b['open'],min(x['low'] for x in prefix))
    opening=prefix[0]['open'];body=sorted((opening,b['open']))
    prior_body=sorted((previous['open'],previous['close'])) if context else None
    return dict(time_utc=iso(b['t']),known_prefix_minutes=14,reference_price=b['open'],
        observed_high=high,observed_low=low,opening_15m=opening,
        upper_wick_fraction=(high-max(body))/(high-low) if high>low else 0,
        non_green=b['open']<=opening,
        direction_passed=direction_passed(b['open'],context),
        full_range_inside=(high<=previous['high'] and low>=previous['low']) if context else None,
        body_inside=(body[0]>=prior_body[0] and body[1]<=prior_body[1]) if context else None,
        context=context)


class StructureExitMixin:
    """Combine with the nominated-entry replay, explicitly, never by default."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.policy=POLICY

    def additional_exit_candidates(self,b):
        """Explicit policy extensions participate in normal event ordering."""
        return []

    def apply_exits(self,b):
        p=self.position
        # Retain the target as historical metadata, but never create a T2 leg.
        p['fixed_second_target_enabled']=False
        raw=candidates(p,b,self.minutes,self.prev,policy='v1')
        warnings=p.setdefault('midpoint_warnings',[])
        mid=next((c for c in raw if c['reason']=='midpoint_exit_all'),None)
        period=b['t']//900*900
        if mid and not any(w['period']==period for w in warnings):
            e=dict(time_utc=iso(b['t']),interval_end=iso(b['t']+60),period=period,
                reference_price=mid['price'],reference_t=mid['reference_t'],
                raw_midpoint=p['armed_midpoint']['price'],action='warning_only_no_sale')
            warnings.append(e)
            self.event('midpoint_warning',b['t'],price=mid['price'],trade_id=p['id'],
                reason='midpoint crossing is a warning, not an exit')

        options=[c for c in candidates(p,b,self.minutes,self.prev) if c['reason'] in ('stop','target_25','wick_exit_all')]
        last=last_minute_state(b,self.minutes,self.prev)
        if last:
            last.update(new_wave_high=last['observed_high']>p['active_wave_high'],
                above_entry=last['reference_price']>p['entry'])
            last['shape_qualified']=last['upper_wick_fraction']>=.5 and last['new_wave_high'] and last['above_entry']
            last['inside_exempt']=bool(last['full_range_inside'] or last['body_inside'])
            last['exit_qualified']=last['shape_qualified'] and last['direction_passed'] and not last['inside_exempt']
            p.setdefault('last_minute_observations',[]).append(last)
            if last['inside_exempt']:
                options=[c for c in options if c['reason']!='wick_exit_all']
            if last['shape_qualified'] and not last['exit_qualified']:
                self.event('wick_wait',b['t'],trade_id=p['id'],price=b['open'],
                    reason='last-minute wick lacks direction confirmation or remains inside prior candle',
                    non_green=last['non_green'],inside_exempt=last['inside_exempt'])

        anchor=p.get('structure_reference')
        if anchor and anchor['effective_at']<=b['t']:
            if b['open']<anchor['price']:
                options.append(dict(reason='structure_exit_remaining',price=b['open'],phase=0,priority=5,
                    price_basis='observed minute open below an already confirmed structure low',structure=copy.deepcopy(anchor)))
            elif b['low']<anchor['price']:
                options.append(dict(reason='structure_exit_remaining',price=anchor['price'],phase=1,priority=5,
                    price_basis='within-minute break reference; exact tick and fill unverified',structure=copy.deepcopy(anchor)))
        options.extend(self.additional_exit_candidates(b))
        options.sort(key=lambda c:(c['phase'],c['priority']))
        uncertain=[c for c in options if c['phase']==1]
        for c in options:
            if self.position is None:break
            p=self.position
            if c['reason']=='target_25' and p['remaining']!=1:continue
            e=copy.deepcopy(c)
            e.update(time_utc=iso(b['t']),interval_end=iso(b['t']+60),
                fraction=.25 if c['reason']=='target_25' else p['remaining'])
            if len(uncertain)>1 and any(x['reason'] in ('stop','structure_exit_remaining') for x in uncertain):
                p['same_minute_exit_ambiguity']=True
                e.update(same_minute_order_ambiguous=True,tie_rule='stop > confirmed structure > target')
            p.setdefault('case_exit_evidence',[]).append(e)
            if c['reason']=='giveback_exit_remaining':
                p.setdefault('giveback_exits',[]).append(copy.deepcopy(e))
            self.close_part(b,c['price'],e['fraction'],c['reason'])

    def complete(self):
        had=bool(self.minutes)
        super().complete()
        if not had or not self.position:return
        p=self.position;now=self.prev['t']+900
        entry_at=ts(p['entry_time'])
        recent=list(self.recent)
        if len(recent)>=3:
            a,low,right=recent[-3:]
            complete=all(x['observed_minutes']==15 for x in (a,low,right))
            adjacent=low['t']==a['t']+900 and right['t']==low['t']+900
            if complete and adjacent and low['t']>entry_at and low['low']<a['low'] and low['low']<right['low']:
                before=[x for x in recent if entry_at//900*900<=x['t']<low['t']]
                if before:
                    peak=max(before,key=lambda x:x['high'])
                    p.setdefault('structure_candidates',[]).append(dict(t=low['t'],price=low['low'],
                        low_time=low['low_t'],known_at=now,prior_peak=peak['high'],prior_peak_bar=peak['t']))
        active=p.get('structure_reference')
        floor=active['price'] if active else p['references']['l1']['price']
        for candidate in p.get('structure_candidates',[]):
            if candidate['price']<=floor:continue
            after=[x for x in recent if x['t']>candidate['t'] and x['t']<now]
            # Missing coverage cannot prove a low survived or a breakout.
            if (not after or any(x['observed_minutes']!=15 for x in after)
                    or [x['t'] for x in after]!=list(range(candidate['t']+900,now,900))):continue
            if any(x['low']<candidate['price'] for x in after):continue
            hit=next((x for x in after if x['high']>candidate['prior_peak']),None)
            if hit is None:continue
            anchor=dict(**copy.deepcopy(candidate),effective_at=now,breakout_bar=hit['t'],
                breakout_known_at=hit['t']+900,basis='confirmed 15m higher low + later new rally high')
            p['structure_reference']=anchor
            p.setdefault('structure_history',[]).append(copy.deepcopy(anchor));floor=anchor['price']
            self.event('structure_reference_raised',now,trade_id=p['id'],price=anchor['price'],
                reference_low_time=iso(anchor['low_time']),low_known_at=iso(anchor['known_at']),
                effective_time=iso(now),breakout_known_at=iso(anchor['breakout_known_at']))
        record=self.db.execute('SELECT body FROM ledger WHERE t=?',(self.prev['t'],)).fetchone()
        if record:
            row=json.loads(record[0]);row['events'].extend(self.events)
            row['case_structure_reference']=copy.deepcopy(p.get('structure_reference'))
            row['case_exit_policy']=POLICY
            if p.get('giveback_state'):
                row['giveback_state']=copy.deepcopy(p['giveback_state'])
                row['case_exit_policy']=self.policy
            self.db.execute('UPDATE ledger SET body=? WHERE t=?',(json.dumps(row,ensure_ascii=False),self.prev['t']))
        self.events=[]
