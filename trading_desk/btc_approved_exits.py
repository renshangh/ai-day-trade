"""Approved causal exits, separate from the frozen legacy Replay implementation.

Known opening observations precede a minute's unresolved H/L. Within-minute
ordering cannot be invented: stop > midpoint > target is the risk-first tie
rule, flagged as ambiguous. Both active exits sell the CURRENT remainder.
"""
import copy
import json

from trading_desk.btc_data import iso,ts
from trading_desk.btc_engine import Replay

POLICY_V1='midpoint-and-unrestricted-wick-v1'
POLICY='midpoint-and-wick-direction-filter-v2'


def initialize(position):
    if 'active_wave_high' not in position:
        position['active_wave_high']=(position.get('references',{}).get('h1',{}).get('price')
            or position['peak_before_period'])
        position['armed_midpoint']=None


def direction_context(minute,prefix,previous_bar):
    """Only already-known 15m opening and preceding completed close qualify."""
    period=minute['t']//900*900
    if not previous_bar or previous_bar.get('t',-1)+900!=period or previous_bar.get('observed_minutes')!=15:
        return None
    if prefix and prefix[0]['t']==period:
        opening=prefix[0]['open']
    elif not prefix and minute['t']==period:
        opening=minute['open']
    else:
        return None # Never substitute the first later observation for a missing open.
    return dict(direction_bar_open=opening,previous_bar_close=previous_bar['close'],
        previous_bar_start=previous_bar['t'],previous_bar_known_at=period)


def direction_passed(price,context):
    # Equal-to-open is neutral/doji, not green; equality to prior close is allowed.
    return bool(context and price<=context['direction_bar_open'] and price<=context['previous_bar_close'])


def candidates(position,minute,prefix,previous_bar=None,*,policy='v2'):
    """Return causal observations, not orders or guaranteed executable prices."""
    initialize(position)
    if policy not in ('v1','v2'):raise ValueError('Unknown active exit policy')
    p=position;b=minute;period=b['t']//900*900;out=[]
    context=direction_context(b,prefix,previous_bar) if policy=='v2' else None
    def add(reason,price,phase,priority,**evidence):
        out.append(dict(reason=reason,price=price,phase=phase,priority=priority,**evidence))
    if b['open']<=p['stop']:
        add('stop',b['open'],0,0,price_basis='observed minute open already through stop')
    elif b['low']<=p['stop']:
        add('stop',p['stop'],1,0,price_basis='within-minute threshold reference')
    mid=p['armed_midpoint']
    if mid and period==mid['reference_t']+900 and mid['known_at']<=b['t']:
        reference={k:v for k,v in mid.items() if k!='price'}
        if policy=='v2' and context:
            threshold=min(mid['price'],context['direction_bar_open'],context['previous_bar_close'])
            evidence=dict(**reference,**context,raw_midpoint=mid['price'],
                direction_filter_applied=True,direction_gate_price=threshold)
            if b['open']<mid['price'] and direction_passed(b['open'],context):
                add('midpoint_exit_all',b['open'],0,10,**evidence,
                    direction_reference_price=b['open'],price_basis='observed open meets midpoint and both direction conditions')
            elif b['low']<mid['price'] and direction_passed(b['low'],context):
                add('midpoint_exit_all',threshold,1,10,**evidence,
                    direction_reference_price=threshold,price_basis='within-minute crossing of all three known bounds; no old midpoint backfill')
        elif policy=='v1' and b['open']<mid['price']:
            add('midpoint_exit_all',b['open'],0,10,**reference,
                price_basis='observed minute open below known midpoint')
        elif policy=='v1' and b['low']<mid['price']:
            add('midpoint_exit_all',mid['price'],1,10,**reference,
                price_basis='within-minute midpoint-crossing reference')
    if b['t']%900==840 and [x['t'] for x in prefix]==list(range(period,b['t'],60)):
        high=max(b['open'],max(x['high'] for x in prefix))
        low=min(b['open'],min(x['low'] for x in prefix))
        ratio=(high-max(prefix[0]['open'],b['open']))/(high-low) if high>low else 0
        if (high>p['active_wave_high'] and ratio>=.5 and b['open']>p['entry']
                and (policy=='v1' or direction_passed(b['open'],context))):
            evidence=dict(**context,direction_filter_applied=True,direction_reference_price=b['open']) if context else {}
            add('wick_exit_all',b['open'],0,20,observed_high=high,observed_low=low,
                opening_15m=prefix[0]['open'],upper_wick_fraction=ratio,
                wave_high_before=p['active_wave_high'],known_prefix_minutes=14,
                integer_watch_gate=False,price_basis='minute open and prior 14 completed minutes only',**evidence)
    if p['remaining']==1 and p['t1'] is not None and b['high']>p['t1']:
        add('target_25',p['t1'],0 if b['open']>p['t1'] else 1,30,
            price_basis='unchanged conservative limit-target reference')
    if p['t2'] is not None and b['high']>p['t2']:
        add('target_remaining',p['t2'],0 if b['open']>p['t2'] else 1,40,
            price_basis='unchanged conservative limit-target reference')
    return sorted(out,key=lambda c:(c['phase'],c['priority']))


class ApprovedExitReplay(Replay):
    def __init__(self,*args,exit_policy='approved',**kwargs):
        if exit_policy not in ('approved','approved_v1','legacy'):
            raise ValueError('Choose approved, approved_v1 or legacy exit policy')
        super().__init__(*args,**kwargs);self.exit_policy=exit_policy
        self.policy='legacy' if exit_policy=='legacy' else POLICY_V1 if exit_policy=='approved_v1' else POLICY

    def complete(self):
        if self.exit_policy=='legacy':
            return super().complete()
        had_minutes=bool(self.minutes)
        # Protective low confirmation, ATR buffers, targets and costs remain
        # in the unmodified parent implementation for historical comparison.
        super().complete()
        if not had_minutes:return
        bar=self.prev;p=self.position
        if p:
            initialize(p)
            complete=[b['t'] for b in self.minutes]==list(range(bar['t'],bar['t']+900,60))
            entry_at=ts(p['entry_time']) if p.get('entry_time') else p['entry_period']
            p['armed_midpoint']=None
            if complete and bar['t']>=entry_at:
                if bar['high']>p['active_wave_high']:
                    p['armed_midpoint']=dict(reference_t=bar['t'],known_at=bar['t']+900,
                        reference_high=bar['high'],reference_low=bar['low'],price=(bar['high']+bar['low'])/2)
                    self.event('midpoint_armed',bar['t']+900,price=p['armed_midpoint']['price'],
                        reference_bar=iso(bar['t']),reference_high=bar['high'],reference_low=bar['low'],
                        effective_time=iso(bar['t']+900),expires=iso(bar['t']+1800),trade_id=p['id'])
                p['active_wave_high']=max(p['active_wave_high'],bar['high'])
        if bar['t']>=self.start:
            record=self.db.execute('SELECT body FROM ledger WHERE t=?',(bar['t'],)).fetchone()
            if record:
                row=json.loads(record[0]);row['events'].extend(self.events)
                row['active_exit_state']=dict(policy=self.policy,
                    wave_high=p['active_wave_high'] if p else None,
                    midpoint=copy.deepcopy(p['armed_midpoint']) if p else None)
                self.db.execute('UPDATE ledger SET body=? WHERE t=?',(json.dumps(row,ensure_ascii=False),bar['t']))
        self.events=[]

    def apply_exits(self,b):
        p=self.position
        mode='v1' if self.exit_policy=='approved_v1' else 'v2'
        options=candidates(p,b,self.minutes,self.prev,policy=mode)
        if mode=='v2':
            context=direction_context(b,self.minutes,self.prev)
            for old in candidates(p,b,self.minutes,self.prev,policy='v1'):
                if old['reason'] not in ('midpoint_exit_all','wick_exit_all') or direction_passed(old['price'],context):continue
                period=b['t']//900*900
                rejected=p.setdefault('direction_filter_rejections',[])
                if any(e['period']==period and e['reason']==old['reason'] for e in rejected):continue
                evidence=dict(period=period,reason=old['reason'],time_utc=iso(b['t']),
                    old_reference_price=old['price'],direction_context=context,
                    blocked_green=old['price']>context['direction_bar_open'] if context else None,
                    blocked_above_previous_close=old['price']>context['previous_bar_close'] if context else None,
                    missing_direction_reference=context is None)
                rejected.append(evidence)
                self.event('exit_filter_rejected',b['t'],trade_id=p['id'],
                    reason='active-exit direction conditions not met; wait without retroactive midpoint fill',
                    blocked_exit_reason=old['reason'],
                    **{k:v for k,v in evidence.items() if k not in ('reason','time_utc')})
        unresolved=[c for c in options if c['phase']==1]
        uncertain=len(unresolved)>1 and any(c['reason'] in ('stop','midpoint_exit_all') for c in unresolved)
        for c in options:
            if self.position is None:break
            p=self.position;reason=c['reason']
            if reason=='target_25' and p['remaining']!=1:continue
            evidence={k:v for k,v in c.items() if k not in ('reason','phase','priority','price')}
            if c['phase']==1 and uncertain:
                p['same_minute_exit_ambiguity']=True
                evidence.update(same_minute_order_ambiguous=True,
                    candidates=[x['reason'] for x in unresolved],tie_rule='stop > midpoint > target')
                audit=dict(time_utc=iso(b['t']),chosen=reason,**copy.deepcopy(evidence))
                p.setdefault('exit_order_audit',[]).append(audit)
                self.event('exit_order_ambiguity',b['t'],trade_id=p['id'],
                    chosen=reason,candidates=evidence['candidates'],tie_rule=evidence['tie_rule'])
            if reason in ('midpoint_exit_all','wick_exit_all'):
                evidence.update(policy=self.policy,time_utc=iso(b['t']),interval_end=iso(b['t']+60),
                    reference_price=c['price'],fraction=p['remaining'])
                p.setdefault('active_exit_events',[]).append(copy.deepcopy(evidence))
                self.event('midpoint_signal' if reason=='midpoint_exit_all' else 'wick_signal',
                    b['t'],price=c['price'],trade_id=p['id'],**{k:v for k,v in evidence.items() if k!='time_utc'})
            self.close_part(b,c['price'],.25 if reason=='target_25' else p['remaining'],reason)

    def minute(self,b):
        if self.exit_policy=='legacy':
            return super().minute(b)
        # Match the frozen replay's observation/gap/entry lifecycle. Only the
        # decision ordering below differs; no current-bar final close is used.
        period=b['t']//900*900
        if self.bucket is not None and period!=self.bucket:
            self.complete();self.minutes=[]
            if self.position:self.position['peak_before_period']=self.position['peak']
        self.bucket=period
        if self.last_minute is not None and b['t']!=self.last_minute+60:
            missing=(b['t']-self.last_minute)//60-1
            self.counter['missing_minutes']+=missing;self.counter['gap_count']+=1
            if len(self.gaps)<200:self.gaps.append(dict(start=iso(self.last_minute+60),end=iso(b['t']),missing=missing))
            if self.position:
                self.position['gap_exposed']=True
                self.event('data_gap_exposure',b['t'],missing_minutes=missing,trade_id=self.position['id'])
        self.last_minute=b['t'];self.last_price=b['close'];self.last_t=b['t']
        was_position=self.position is not None
        if self.position:self.apply_exits(b)
        if self.position:self.position['peak']=max(self.position['peak'],b['high'])
        if self.position is None and not was_position:self.entry(b)
        self.minutes.append(b)
