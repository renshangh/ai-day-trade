"""Causal BTC signal research on observed Alpaca minutes; never routes orders.

This is an explicit mechanical draft of the learning manual, not equivalence
to its discretionary charts or actual ETF performance. Missing minutes remain
absent; exposed trades and incomplete aggregates are flagged, never filled.
"""
from __future__ import annotations
import argparse
import bisect
import collections
import csv
import hashlib
import json
import math
import sqlite3
import time
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.btc_structure_retest import Config,MajorResistance,reward_risk
from trading_desk.btc_data import STORE,connect,iso,quality,save

NY=ZoneInfo('America/New_York')


def partial_context(bars,count=14):
    window=list(bars)[-count:]
    return (len(window)!=count or any(b['observed_minutes']!=15 for b in window)
        or any(b['t']!=a['t']+900 for a,b in zip(window,window[1:])))


def aggregate(group,seconds):
    """Aggregate actual observations only; coverage is not invented."""
    return dict(t=group[0]['t']//seconds*seconds,open=group[0]['open'],high=max(b['high'] for b in group),
        low=min(b['low'] for b in group),close=group[-1]['close'],volume=sum(b['volume'] for b in group),
        observed_minutes=sum(b.get('observed_minutes',1) for b in group),
        low_t=min(group,key=lambda b:b['low']).get('low_t',min(group,key=lambda b:b['low'])['t']),
        high_t=max(group,key=lambda b:b['high']).get('high_t',max(group,key=lambda b:b['high'])['t']))


class Replay:
    def __init__(self,start,end,db,cfg=None):
        self.cfg=cfg or Config(version='Alpaca-BTC-ETF-cost-draft-3',first_sale_fraction=.25,resistance_mode='major1h')
        self.start=start;self.end=end;self.db=db;self.major=MajorResistance(self.cfg)
        self.recent=collections.deque(maxlen=1000);self.hours=collections.deque(maxlen=5)
        self.hour_pending=[];self.four_pending=[];self.four=collections.deque(maxlen=5);self.large_peaks=[]
        self.parent_highs=[];self.l1=None;self.leg_high=None;self.pullback=None
        self.trs=collections.deque(maxlen=14);self.atr=None;self.prev=None
        self.minutes=[];self.bucket=None;self.last_minute=None;self.position=None;self.trades=[]
        self.events=[];self.attempted=None;self.counter=collections.Counter();self.gaps=[]
        self.last_price=None;self.last_t=None;self.position_id=0

    def event(self,kind,t,**values):
        self.events.append(dict(type=kind,time_utc=iso(t),time_ny=datetime.fromtimestamp(t,NY).isoformat(),**values))

    def close_part(self,b,price,fraction,reason):
        p=self.position;q=self.cfg.one_way_friction_bps/10000
        gross=fraction*(price-p['entry']);cost=fraction*(price+p['entry'])*q
        leg=dict(reason=reason,time_utc=iso(b['t']),time_ny=datetime.fromtimestamp(b['t'],NY).isoformat(),
            time_basis='1-minute interval/model reference; exact second and actual fill unverified',
            price=price,fraction=fraction,gross=gross,cost=cost,net=gross-cost)
        p['legs'].append(leg);p['remaining']=round(p['remaining']-fraction,8)
        self.event(reason,b['t'],price=price,fraction=fraction,trade_id=p['id'])
        if p['remaining']==0:
            p['status']='closed';p['exit_time']=iso(b['t']);p['net']=sum(x['net'] for x in p['legs'])
            p['net_r']=p['net']/p['initial_risk'];self.trades.append(p);self.position=None

    def targets(self,entry,h1,t,atr):
        self.large_peaks=[p for p in self.large_peaks if p['t']>=t-7*86400]
        peaks=[p for p in self.large_peaks if p['high']>h1['high'] and p['known_at']<=t]
        if not peaks:
            return None,None
        peak=min(peaks,key=lambda p:p['high'])
        zones=self.major.zones(entry,t)
        z=next((z for z in zones if any(x['price']==peak['high'] for x in z['members'])),None)
        if not z:
            return None,None
        later=next((x for x in zones if x['lower']>z['upper']),None)
        return z['lower']-.1*atr,(later['lower']-.1*atr if later else None)

    def entry(self,b):
        if self.position or b['t']<self.start or self.prev is None or self.atr is None or self.l1 is None or self.leg_high is None:
            return
        prev=self.prev;period=b['t']//900*900
        if prev['t']+900!=period or self.attempted==period or prev['observed_minutes']!=15:
            return
        older=self.recent[-2] if len(self.recent)>=2 else None
        if (not older or self.leg_high['t']>=prev['t'] or self.pullback is None
                or prev['low']!=self.pullback or prev['low']>=older['low']
                or prev['low']<=self.l1['low']+.1*self.atr):
            return
        trigger=prev['high']+.01
        if b['high']<=trigger:
            return
        self.attempted=period;self.counter['candidates']+=1
        entry=max(trigger,b['open']);stop=self.l1['low']-.25*self.atr
        t1,t2=self.targets(entry,self.leg_high,b['t'],self.atr)
        ratio=reward_risk(entry,stop,t1,2) if t1 is not None else None
        why=('no known larger resistance' if t1 is None else
             'entry exceeds 0.10 ATR chase ceiling' if entry>trigger+.1*self.atr else
             'net first-target reward/risk below 2' if ratio is None or ratio<2 else None)
        refs=dict(l1=dict(time=iso(self.l1['low_t']),price=self.l1['low'],known_at=iso(self.l1['known_at'])),
            h1=dict(time=iso(self.leg_high['t']),price=self.leg_high['high']),
            l2=dict(time=iso(prev['t']),price=prev['low']),trigger=trigger,stop=stop,target=t1,net_reward_risk=ratio)
        if why:
            self.counter['rejected']+=1;self.event('entry_rejected',b['t'],reason=why,**refs);return
        self.position_id+=1
        # A wholly missing 15m bucket must not evade the partial-context flag
        # merely because every *remaining* aggregate contains fifteen minutes.
        context_partial=partial_context(self.recent)
        self.position=dict(id=self.position_id,status='open',entry=entry,entry_time=iso(b['t']),
            entry_interval_end=iso(b['t']+60),initial_stop=stop,stop=stop,t1=t1,t2=t2,remaining=1.0,
            initial_risk=entry-stop+(entry+stop)*.0002,legs=[],references=refs,
            protected_t=prev['t'],protected_low=prev['low'],pending_lows=[],
            peak=b['high'],peak_before_period=b['high'],entry_period=period,
            gap_exposed=False,context_partial=context_partial,quote_reference_entry=b['volume']==0)
        self.event('entry',b['t'],price=entry,trade_id=self.position_id,**refs)
        # Adverse-first for unknown ordering within an entry minute.
        if b['low']<=stop:
            self.position['entry_minute_ambiguity']=True
            self.close_part(b,stop,1.0,'stop_entry_minute_ambiguous')

    def minute(self,b):
        period=b['t']//900*900
        if self.bucket is not None and period!=self.bucket:
            self.complete()
            self.minutes=[]
            if self.position:
                self.position['peak_before_period']=self.position['peak']
        self.bucket=period
        if self.last_minute is not None and b['t']!=self.last_minute+60:
            missing=(b['t']-self.last_minute)//60-1
            self.counter['missing_minutes']+=missing;self.counter['gap_count']+=1
            if len(self.gaps)<200:
                self.gaps.append(dict(start=iso(self.last_minute+60),end=iso(b['t']),missing=missing))
            if self.position:
                self.position['gap_exposed']=True
                self.event('data_gap_exposure',b['t'],missing_minutes=missing,trade_id=self.position['id'])
        self.last_minute=b['t'];self.last_price=b['close'];self.last_t=b['t']
        p=self.position
        was_position=p is not None
        if p:
            # Opening observations precede this minute's final H/L. An open-time
            # wick exit cannot be replaced by a target/stop reached later here.
            if b['open']<=p['stop']:
                self.close_part(b,b['open'],p['remaining'],'stop')
            if self.position and b['t']%900==840 and len(self.minutes)==14:
                p=self.position
                if [x['t'] for x in self.minutes]==list(range(period,b['t'],60)):
                    h=max(b['open'],max(x['high'] for x in self.minutes));lo=min(b['open'],min(x['low'] for x in self.minutes))
                    opening=self.minutes[0]['open'];watch=math.floor(self.prev['close']/1000)*1000 if self.prev else 0
                    ratio=(h-max(opening,b['open']))/(h-lo) if h>lo else 0
                    if (watch>p['entry'] and self.prev['close']>=watch and h>p['peak_before_period']
                            and b['open']<watch and ratio>=.5):
                        self.event('wick_signal',b['t'],watch_level=watch,upper_wick_fraction=ratio,
                            observation='minute first price, preceding 14 completed minutes only',trade_id=p['id'])
                        self.close_part(b,b['open'],p['remaining'],'wick_exit_all')
            if self.position:
                p=self.position
                if b['low']<=p['stop']:
                    self.close_part(b,p['stop'],p['remaining'],'stop')
                elif p['remaining']==1 and b['high']>p['t1']:
                    self.close_part(b,p['t1'],.25,'target_25')
            if self.position:
                p=self.position
                if p['t2'] is not None and b['high']>p['t2']:
                    self.close_part(b,p['t2'],p['remaining'],'target_remaining')
        if self.position:
            self.position['peak']=max(self.position['peak'],b['high'])
        if self.position is None and not was_position:
            self.entry(b)
        self.minutes.append(b)

    def complete(self):
        if not self.minutes:
            return
        bar=aggregate(self.minutes,900);now=bar['t']+900
        bar['atr_before']=self.atr
        if self.prev:
            self.trs.append(max(bar['high']-bar['low'],abs(bar['high']-self.prev['close']),abs(bar['low']-self.prev['close'])))
        self.atr=sum(self.trs)/14 if len(self.trs)==14 else None
        self.recent.append(bar);self.major.observe(bar)
        if not self.hour_pending or bar['t']!=self.hour_pending[-1]['t']+900:
            self.hour_pending=[]
        if bar['t']%3600==0:
            self.hour_pending=[bar]
        elif self.hour_pending:
            self.hour_pending.append(bar)
        new_low=None
        if len(self.hour_pending)==4:
            hour=aggregate(self.hour_pending,3600);self.hours.append(hour);self.hour_pending=[]
            if len(self.hours)>=3:
                a,p,c=list(self.hours)[-3:]
                adjacent=p['t']==a['t']+3600 and c['t']==p['t']+3600
                if adjacent and p['high']>a['high'] and p['high']>c['high']:
                    self.parent_highs.append(dict(t=p['high_t'],high=p['high'],known_at=now))
                if adjacent and p['low']<a['low'] and p['low']<c['low']:
                    new_low=dict(**p,known_at=now)
                    self.l1=new_low
                    leg=[x for x in self.recent if x['t']>new_low['low_t']]
                    self.leg_high=max(leg,key=lambda x:x['high']) if leg else None
                    tail=[x for x in leg if self.leg_high and x['t']>self.leg_high['t']]
                    self.pullback=min((x['low'] for x in tail),default=None)
            if hour['t']%14400==0:
                self.four_pending=[hour]
            elif self.four_pending and hour['t']==self.four_pending[-1]['t']+3600:
                self.four_pending.append(hour)
            else:
                self.four_pending=[]
            if len(self.four_pending)==4:
                self.four.append(aggregate(self.four_pending,14400));self.four_pending=[]
                if len(self.four)==5:
                    w=list(self.four);p=w[2]
                    if all(y['t']==x['t']+14400 for x,y in zip(w,w[1:])) and all(p['high']>x['high'] for x in w[:2]+w[3:]):
                        self.large_peaks.append(dict(**p,known_at=now))
        if not new_low and self.l1:
            if self.leg_high is None or bar['high']>self.leg_high['high']:
                self.leg_high=bar;self.pullback=None
            elif bar['t']>self.leg_high['t']:
                self.pullback=min(self.pullback,bar['low']) if self.pullback is not None else bar['low']
        p=self.position
        if p:
            for candidate in p['pending_lows']:
                if bar['t']>candidate['t']:
                    if bar['low']<candidate['low']:
                        candidate['failed']=True
                    if candidate['breakout'] is None and bar['high']>candidate['peak']['high']:
                        candidate['breakout']=dict(t=bar['t'],atr=bar['atr_before'])
            if new_low and new_low['low_t']>p['protected_t'] and new_low['low']>p['protected_low']:
                peaks=[x for x in self.parent_highs if p['protected_t']<x['t']<new_low['low_t']]
                if peaks:
                    peak=max(peaks,key=lambda x:x['high'])
                    after=[x for x in self.recent if x['t']>new_low['low_t']]
                    hit=next((x for x in after if x['high']>peak['high']),None)
                    p['pending_lows'].append(dict(t=new_low['low_t'],low=new_low['low'],peak=peak,
                        failed=any(x['low']<new_low['low'] for x in after),
                        breakout=dict(t=hit['t'],atr=hit['atr_before']) if hit else None))
            for candidate in p['pending_lows']:
                hit=candidate['breakout']
                if candidate['failed'] or candidate['t']<=p['protected_t'] or candidate['low']<=p['protected_low'] or not hit or not hit['atr']:
                    continue
                proposed=candidate['low']-.25*hit['atr']
                if proposed>p['stop']:
                    p['stop']=proposed;p['protected_t']=candidate['t'];p['protected_low']=candidate['low']
                    self.event('stop_raised',now,price=proposed,trade_id=p['id'],
                        reference_low=candidate['low'],reference_low_time=iso(candidate['t']),
                        breakout_time=iso(hit['t']),effective_time=iso(now))
            p['pending_lows']=[x for x in p['pending_lows'] if not x['failed'] and x['t']>p['protected_t']]
        if bar['t']>=self.start:
            row=dict(**bar,end=iso(now),time=iso(bar['t']),time_ny=datetime.fromtimestamp(bar['t'],NY).isoformat(),
                l1_price=self.l1['low'] if self.l1 else None,l1_time=iso(self.l1['low_t']) if self.l1 else None,
                l1_known_at=iso(self.l1['known_at']) if self.l1 else None,
                l2_price=bar['low'] if self.pullback==bar['low'] and self.leg_high and self.leg_high['t']<bar['t'] else None,
                l2_time=iso(bar['t']) if self.pullback==bar['low'] else None,
                stop=self.position['stop'] if self.position else None,
                remaining=self.position['remaining'] if self.position else 0,
                position_id=self.position['id'] if self.position else None,events=self.events)
            day=datetime.fromtimestamp(bar['t'],NY).date().isoformat()
            self.db.execute('INSERT INTO ledger VALUES(?,?,?)',(bar['t'],day,json.dumps(row,ensure_ascii=False)))
        self.events=[];self.prev=bar

    def finish(self):
        self.complete()
        if self.position:
            p=self.position;p['status']='open';p['net']=None;p['net_r']=None
            p['unrealized_gross']=p['remaining']*(self.last_price-p['entry']);self.trades.append(p)
        for p in self.trades:
            p.pop('pending_lows',None)
        closed=[p for p in self.trades if p['status']=='closed']
        def metrics(rows):
            r=[p['net_r'] for p in rows];wins=sum(x>0 for x in r)
            peak=balance=drawdown=0
            for x in r:
                balance+=x;peak=max(peak,balance);drawdown=max(drawdown,peak-balance)
            return dict(closed=len(r),wins=wins,losses=sum(x<=0 for x in r),win_rate=wins/len(r) if r else None,
                net_r=sum(r),max_drawdown_r=drawdown)
        return dict(trades=self.trades,metrics=metrics(closed),
            gap_free_metrics=metrics([p for p in closed if not p['gap_exposed'] and not p['context_partial']]),
            gap_exposed_trades=sum(p['gap_exposed'] for p in self.trades),
            partial_context_trades=sum(p['context_partial'] for p in self.trades),
            counts=dict(self.counter),gaps=self.gaps,last_observed=iso(self.last_t) if self.last_t else None)


def export_csv(folder,result,db):
    """Downloadable research records; rejected signals never masquerade as fills."""
    def write(name,rows):
        if not rows:
            rows=[{'status':'No records in this run'}]
        with (folder/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    signals=[]
    for s in result.get('signals',[]):
        refs=s['references'];hl=refs.get('l2') or {}
        signals.append(dict(signal_id=s['id'],entry_rule=s['route'],time_ny=s['time_ny'],
            time_utc=s['time_utc'],interval_end=s['interval_end'],decision=s['decision'],
            trade_id=s['trade_id'],entry_reference=s['entry_reference'],
            initial_stop=s['initial_stop'],target1=s['t1'],target2=s['t2'],
            net_reward_risk=s['net_reward_risk'],risk_passed=s['risk_passed'],
            preferred_rr_met=s['preferred_rr_met'],rr_warning=s['rr_warning'],
            qualified_candidate=s['qualified_candidate'],structural_price_signal=s['structural_price_signal'],
            d_price=refs['l1']['price'],d_time=refs['l1']['time'],d_known_at=refs['l1']['known_at'],
            hl_price=hl.get('price'),hl_time=hl.get('time'),hl_known_at=hl.get('known_at'),
            previous_bar_time=s['previous_bar_time'],atr=s['atr'],
            reason='; '.join(s['signal_reasons']) or s['risk_reason'] or s['decision'],
            context_partial=s['context_partial'],quote_reference=s['quote_reference']))
    write('SIGNALS.csv',signals)
    trades=[];legs=[];protection=[]
    for p in result['trades']:
        first=next((l for l in p['legs'] if l['reason']=='target_25'),None)
        final=[l for l in p['legs'] if l['reason']!='target_25']
        trades.append(dict(trade_id=p['id'],signal_id=p.get('signal_id'),entry_rule=p.get('entry_rule','legacy'),
            entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],target1=p['t1'],target2=p['t2'],
            initial_stop_effective=p['entry_time'],
            first_25_time=first['time_utc'] if first else None,first_25_price=first['price'] if first else None,
            first_25_net=first['net'] if first else None,
            remainder_time=final[-1]['time_utc'] if final else None,remainder_price=final[-1]['price'] if final else None,
            remainder_fraction=sum(l['fraction'] for l in final),remainder_net=sum(l['net'] for l in final) if final else None,
            remainder_reason=final[-1]['reason'] if final else None,remaining=p['remaining'],
            realized_leg_net=sum(l['net'] for l in p['legs']),
            status=p['status'],exit_time=p.get('exit_time'),net=p.get('net'),net_r=p.get('net_r'),
            gap_exposed=p['gap_exposed'],context_partial=p['context_partial']))
        protection.append(dict(trade_id=p['id'],kind='initial_hard_stop',effective_time=p['entry_time'],
            price=p['initial_stop'],reference_low=p['references']['l1']['price'],
            reference_low_time=p['references']['l1']['time'],confirmation_time=p['references']['l1']['known_at']))
        for h in p.get('stop_history',[]):
            protection.append(dict(trade_id=p['id'],kind='hard_stop_raised',effective_time=h['effective_time'],
                price=h['price'],reference_low=h['reference_low'],reference_low_time=h['reference_low_time'],
                confirmation_time=h.get('breakout_time')))
        for h in p.get('structure_history',[]):
            protection.append(dict(trade_id=p['id'],kind='15m_structure_reference',effective_time=iso(h['effective_at']),
                price=h['price'],reference_low=h['price'],reference_low_time=iso(h['low_time']),
                confirmation_time=iso(h['breakout_known_at'])))
        for h in p.get('failed_rebound_history',[]):
            protection.append(dict(trade_id=p['id'],kind='failed_rebound_exit_reference_not_hard_stop',effective_time=iso(h['effective_at']),
                price=h['price'],reference_low=h['low']['price'],reference_low_time=iso(h['low']['time']),
                confirmation_time=iso(h['lower_high']['known_at'])))
        for leg in p['legs']:
            legs.append(dict(trade_id=p['id'],entry_rule=p.get('entry_rule','legacy'),**leg))
    protection.sort(key=lambda h:(h['trade_id'],h['effective_time']))
    write('TRADES.csv',trades);write('EXITS.csv',legs);write('PROTECTION.csv',protection)
    with (folder/'LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['time_ny','time','end','open','high','low','close','observed_minutes','l1_price','l1_time','l1_known_at','l2_price','l2_time','stop','remaining','position_id']
        w=csv.DictWriter(f,fieldnames=fields+['entry_setups','events']);w.writeheader()
        for (body,) in db.execute('SELECT body FROM ledger ORDER BY t'):
            row=json.loads(body)
            w.writerow({**{k:row.get(k) for k in fields},
                'entry_setups':json.dumps(row.get('entry_setups',{}),ensure_ascii=False),
                'events':json.dumps(row['events'],ensure_ascii=False)})


def create_replay(start,end,db,entry_mode='ab',*,expanded_b=False,exit_version='current',consume_entry_history=None,b1_independent_hold=None):
    """Select current policy without starting a run, downloading or trading."""
    if entry_mode=='ab':
        if exit_version=='guarded_v4':
            from trading_desk.btc_guarded_replay import GuardedABReplay as Engine
            version='Alpaca-BTC-AB-profit-guard-draft-5'
        elif exit_version in ('turning_consumed_v7','turning_v5'):
            from trading_desk.btc_turning_replay import TurningABReplay as Engine
            version='Alpaca-BTC-AB-profit-guard-consumed-turning-draft-7' if exit_version=='turning_consumed_v7' else 'Alpaca-BTC-AB-profit-guard-turning-draft-6'
        elif exit_version in ('current','failed_rebound'):
            from trading_desk.btc_failed_rebound import FailedReboundReplay as Engine
            version='Alpaca-BTC-AB-profit-guard-independent-B1-draft-9' if exit_version=='current' else 'Alpaca-BTC-AB-profit-guard-failed-rebound-draft-8'
        else:raise ValueError('Choose current, guarded_v4, turning_v5, turning_consumed_v7 or failed_rebound exit version')
        consumed=exit_version in ('current','failed_rebound','turning_consumed_v7') if consume_entry_history is None else consume_entry_history
        independent=exit_version=='current' if b1_independent_hold is None else b1_independent_hold
        return Engine(start,end,db,Config(version=version,
            first_sale_fraction=.25,resistance_mode='major1h'),expanded_b=expanded_b,consume_entry_history=consumed,
            b1_independent_hold=independent)
    if entry_mode=='legacy':return Replay(start,end,db)
    raise ValueError('Select ab or legacy entry mode')


def run(days=30,store=STORE,progress=None,entry_mode='ab',*,expanded_b=True,window_end=None,research_policy='release_0_1'):
    if days not in (30,90,365,'all'):
        raise ValueError('Select 30, 90, 365 or all')
    if entry_mode not in ('ab','legacy'):
        raise ValueError('Select ab or legacy entry mode')
    if research_policy not in ('release_0_1','independent_b1'):raise ValueError('Select release_0_1 or independent_b1 research policy')
    source=connect(store)
    first,last=source.execute('SELECT min(t),max(t) FROM minutes').fetchone()
    if first is None:
        raise ValueError('Download real Alpaca minutes first')
    end=(last+60)//900*900
    if window_end is not None:
        selected=int(window_end)
        if selected%900 or selected>end or selected<=first:raise ValueError('Use an observed, aligned historical window end')
        end=selected
    start=first+7*86400 if days=='all' else max(first+7*86400,end-days*86400)
    warm=max(first,start-7*86400)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+str(days)+('-ab' if entry_mode=='ab' else '')
    folder=store/'runs'/run_id;folder.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)');db.execute('CREATE INDEX ledger_day ON ledger(day,t)')
    # Keep the owner-selected release active; experimental factories must be
    # explicitly selected, never promoted because their run is newest.
    engine=create_replay(start,end,db,entry_mode,expanded_b=expanded_b,
        exit_version='failed_rebound' if research_policy=='release_0_1' else 'current')
    n=0;source_digest=hashlib.sha256()
    try:
        for t,o,h,l,c,v,trades,vw in source.execute('SELECT * FROM minutes WHERE t>=? AND t<? ORDER BY t',(warm,end)):
            source_digest.update((json.dumps([t,o,h,l,c,v,trades,vw],separators=(',',':'))+'\n').encode())
            engine.minute(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=trades));n+=1
            if n%10000==0:
                db.commit()
                if progress:progress(dict(status='running',processed=n,time=iso(t),run_id=run_id))
        result=engine.finish();db.commit()
        result.update(run_id=run_id,status='complete',start=iso(start),end=iso(end),warmup_start=iso(warm),
            source_minute_sha256=source_digest.hexdigest(),
            minute_count=n,days=days,source=quality(store),strategy_version=engine.cfg.version,research_policy=research_policy,
            code_sha256={str(path.relative_to(STORE.parents[1])):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (Path(__file__).resolve(),Path(__file__).with_name('btc_data.py'),
                    Path(__file__).resolve().parents[1]/'scripts/btc_structure_retest.py')},
            cost_model='BTC 24/7 signals; ETF zero commission + 2bps each way, not ETF actual returns',
            draft_parameters=dict(parent_period='1Hour, left/right 1 complete hour',
                entry='previous complete 15m pullback high, intrabar 1m crossing; L2 must have all 15 minute observations',
                initial_stop='previous confirmed 1h D minus 0.25 pre-entry 15m ATR',
                target='known 4h peak (2 right bars), covered by major hourly zone, before lower edge',
                min_net_reward_risk=2,upper_wick_fraction=.5,last_minute_seconds=60,
                watch_round_step_usd=1000,watch_rule='nearest lower $1000 level of prior complete 15m close; explicit research proxy for human-marked resistance',
                gaps='no invented minutes; observed-path fills only; gap-exposed trades separately flagged',
                context='aggregates use actual observed minutes and show coverage; partial windows are not filled',
                sizing='each trade normalized to 1 initial BTC; R totals are not compounded account returns'))
        test_count=source.execute('SELECT count(*) FROM minutes WHERE t>=? AND t<?',(start,end)).fetchone()[0]
        result['test_data_quality']=dict(observed_minutes=test_count,expected_minutes=(end-start)//60,
            missing_minutes=(end-start)//60-test_count,missing_policy='absent, never filled')
        if entry_mode=='ab':
            result['entry_mode']='ab';result['expanded_b']=expanded_b
            result['exit_policy']=engine.policy
            result['draft_parameters'].update(
                entry=('A four-wave reversal OR B1 first stabilization OR B2 rebound-HL retest; intrabar above previous complete 15m full high' if expanded_b else 'A four-wave reversal OR original B shock rebound; intrabar above previous complete 15m full high'),
                setup_lifecycle='after entry consume all prior A/B history; rebuild only from complete 15m candles starting after the entry candle; price/ATR/resistance history is retained',
                b1_confirmation=('a separate complete 15m candle starting after D known_at must hold that same D; only subsequent intrabar previous-high break may enter; lower D restarts confirmation, never retroactively holds old D' if engine.b1_independent_hold else 'release 0.1 aggressive first stabilization: completed D candle may be its own reference; no independent post-D hold required'),
                wave_confirmation='15m one complete left/right neighbour; mechanical wave-level approximation, no owner annotations',
                four_lower_lows=4,shock_down_atr=2,
                min_net_reward_risk=0,net_reward_rule='strictly positive net target reward; 2R advisory, no hindsight selection',
                preferred_net_reward_risk=2,
                shock_scope='new low since latest causally confirmed 15m swing high; downward excursion uses pre-drop ATR14',
                dedup='one per route/D/HL; exact same D/HL/trigger combines A+B, otherwise A priority, one position',
                rejected='all crossed signals retained, including below 2R, missing targets, chase and held-position skips',
                exit_contract='midpoint warning only; T1 sells 25%, fixed T2 disabled; confirmed structure, profit giveback, last-minute new-high failure and wick protect current remainder',
                turning_exit='last-minute observed current new wave high + previous complete bullish candle + price below its full-range midpoint + current red + not above previous close + neither body nor observed range inside previous candle',
                profit_guard='known maximum favourable excursion >= initial 1R AND giveback >= 50% AND current price <= current 15m open AND <= previous complete close AND neither body nor observed range inside previous bar',
                guard_sampling='actual 1m opening observations; completed post-entry minute highs only, entry-minute high excluded; do not wait for final 15m close',
                direction_filter='giveback and wick use current non-green/previous complete close; missing context withholds active exits, never hard protection',
                structure_exit='15m low below complete left/right neighbours, higher than retained reference, later complete new rally high, activate only when both confirmations known; strict break exits remainder',
                failed_rebound_exit='independent complete 15m H-L-LH then strict low break; activate after LH right neighbour completes; no new-high/1R gate; hard stop unchanged; gap/incomplete swing context reset',
                fixed_second_target_enabled=False,
                watch_round_step_usd=None,watch_rule='no integer gate for approved wick exits',
                exit_ties='known minute-open events first; hard stop > confirmed structure > failed rebound > giveback > new-high failure > wick > target at same observation; unresolved range ties risk-first, flagged ambiguous')
            for name in ('btc_ab_replay.py','btc_entry_detector.py','btc_entry_rules.py','btc_shock_branches.py','btc_approved_exits.py','btc_structure_exits.py','btc_guarded_replay.py','btc_turning_replay.py','btc_failed_rebound.py'):
                path=Path(__file__).with_name(name)
                result['code_sha256']['trading_desk/'+name]=hashlib.sha256(path.read_bytes()).hexdigest()
        export_csv(folder,result,db)
        save(folder/'result.json',result);save(store/'latest_run.json',dict(run_id=run_id))
        return result
    finally:
        db.close();source.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--days',default='30');parser.add_argument('--entry-mode',choices=('ab','legacy'),default='ab');parser.add_argument('--research-policy',choices=('release_0_1','independent_b1'),default='release_0_1');args=parser.parse_args()
    result=run('all' if args.days=='all' else int(args.days),progress=lambda p:print(json.dumps(p),flush=True),entry_mode=args.entry_mode,research_policy=args.research_policy)
    print(json.dumps({k:result[k] for k in ('run_id','metrics','gap_free_metrics','counts','minute_count')}))
