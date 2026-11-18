"""Isolated IBIT regular-session clock adapter on original BTC live rules."""
from __future__ import annotations
import copy
from collections import deque
from trading_desk.btc_data import iso
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay
from scripts.btc_structure_retest import Config

POLICY=dict(version='IBIT-RTH-clock-1',models=['0.1','E1','E2'],symbol='IBIT',
    window='Same saved October 10-November 9 2026 UTC month; seven calendar days of actual warmup',
    sessions='Exchange calendar regular session, normally 09:30-16:00 America/New_York weekdays; actual holidays, early closes and DST. No premarket, after-hours or invented closed-session bars.',
    exact_control='Original BTC live constructors on actual IBIT RTH bars, no clock changes; preserve diagnostics showing why 24/7 context cannot transfer literally.',
    adapted='Only scheduled-closure continuity/coverage and higher-timeframe resistance clock are adapted. Four actual complete RTH 15m bars form a trading-hour block; sixteen form a four-trading-hour block. Blocks can span scheduled closures, retain real first/last times and become known only after the last actual constituent ends.',
    target_rules='Original 2-neighbour-per-side hourly and 4h peak confirmation, hourly ATR14, prominence, zone width/merging, seven-calendar-day large-peak and original zone lookback/target buffer. No lower timeframe substituted or target fitted to outcomes.',
    entries='Original unfiltered A/B1/B2, consumed setup history, aggressive B1 and $0.01 increment. Original 15m structure resets across nonadjacent wall-clock bars; no opening entry from a stale previous-day bar. No P1/C/ML/ATR-weight gate.',
    overnight='Keep positions overnight; no forced daily close. Only observed RTH prices can trigger exits; opening gap through stop exits at actual opening reference, not the stale stop. No off-hours protection claimed.',
    risk='Original parent D, ATR buffer, chase, positive target space with advisory 2R, 25% target and original 0.1/E1/E2 exits unchanged. ATR still includes real close-to-next-open price gaps.',
    equity='Separate illustrative $10k available-cash reinvestment book per model/arm. Only actual observed minute-close liquidation marks. Fixed-$10k per-entry P/L is separate.',
    costs='Original 2bps per side ETF spread/slippage proxy; excludes actual spreads/impact, taxes, interest and venue execution constraints. ETF expenses already affect observed price; not separately double charged.',
    validation='Retrospective transfer, previously studied dates; no parameter search, strategy promotion or claim of broker fill parity.',
    protection='Original BTC worker/session and frozen 0.2 unchanged, SOL remains paused; no orders or new live worker.')


def observed_block(rows):
    return dict(t=rows[0]['t'],end=rows[-1]['t']+900,open=rows[0]['open'],close=rows[-1]['close'],
        high=max(p['high'] for p in rows),low=min(p['low'] for p in rows),
        high_t=max(rows,key=lambda p:p['high'])['high_t'],low_t=min(rows,key=lambda p:p['low'])['low_t'],
        observed_minutes=sum(p['observed_minutes'] for p in rows),source_15m_starts=[p['t'] for p in rows])


class Resistance:
    def __init__(self,cfg,calendar):
        self.cfg=cfg;self.calendar=calendar;self.pending=[];self.hours=[];self.fours=[];self.trs=[];self.peaks=[];self.large=[];self.last=None
    def observe(self,bar):
        if bar['observed_minutes']!=15 or (self.last is not None and not self.calendar.adjacent_bars(self.last,bar['t'])):
            self.pending=[];self.hours=[];self.fours=[];self.trs=[]
            if bar['observed_minutes']!=15:self.last=bar['t'];return
        self.last=bar['t'];self.pending.append(copy.deepcopy(bar));n=len(self.pending)
        if n%4==0:
            hour=observed_block(self.pending[-4:])
            if self.hours:
                prev=self.hours[-1]['close'];self.trs.append(max(hour['high']-hour['low'],abs(hour['high']-prev),abs(hour['low']-prev)))
            hour['atr']=sum(self.trs[-14:])/14 if len(self.trs)>=14 else None;self.hours.append(hour)
            k=self.cfg.major_pivot_hours
            if len(self.hours)>=2*k+1:
                w=self.hours[-(2*k+1):];peak=w[k]
                if peak['atr'] is not None and all(peak['high']>p['high'] for p in w[:k]+w[k+1:]):
                    prominence=min(peak['high']-min(p['low'] for p in w[:k]),peak['high']-min(p['low'] for p in w[k+1:]))
                    if prominence>=self.cfg.major_prominence_atr*peak['atr']:
                        half=self.cfg.major_zone_half_atr*peak['atr'];self.peaks.append(dict(t=peak['t'],known_at=hour['end'],price=peak['high'],lower=peak['high']-half,upper=peak['high']+half,atr_hour=peak['atr'],prominence=prominence,source_block=peak))
        if n==16:
            four=observed_block(self.pending);self.fours.append(four);self.pending=[]
            if len(self.fours)>=5:
                w=self.fours[-5:];peak=w[2]
                if all(peak['high']>p['high'] for p in w[:2]+w[3:]):self.large.append(dict(**peak,known_at=four['end']))
    def zones(self,entry,now):
        cutoff=now-self.cfg.resistance_lookback_bars*900
        self.peaks=[p for p in self.peaks if p['t']>=cutoff and p['known_at']<=now];groups=[]
        for p in sorted(self.peaks,key=lambda p:p['lower']):
            if groups and p['lower']<=groups[-1]['upper']:
                groups[-1]['upper']=max(groups[-1]['upper'],p['upper']);groups[-1]['members'].append(p)
            else:groups.append(dict(lower=p['lower'],upper=p['upper'],members=[p]))
        return [g for g in groups if g['upper']>=entry]


class SessionMixin:
    def __init__(self,*args,calendar,**kwargs):
        super().__init__(*args,**kwargs);self.calendar=calendar;self.rth_resistance=Resistance(self.cfg,calendar);self.closed_intervals=[];self.target_reviews=[]
    def minute(self,b):
        if b['t'] not in self.calendar.allowed:raise ValueError('Off-session observation cannot enter the RTH replay')
        last=self.last_minute
        if last is not None and b['t']>last+60 and len(self.calendar.missing_between(last,b['t']))<(b['t']-last)//60-1:
            missing=self.calendar.missing_between(last,b['t']);record=dict(last_observed=iso(last),next_observed=iso(b['t']),closed_minutes=(b['t']-last)//60-1-len(missing),missing_regular_minutes=len(missing))
            self.closed_intervals.append(record)
            if missing:
                self.counter['missing_minutes']+=len(missing);self.counter['gap_count']+=1;self.gaps.append(dict(start=iso(missing[0]),end=iso(b['t']),missing=len(missing)))
                if self.position:
                    self.position['gap_exposed']=True;self.reset_failed_rebound(b['t'],'missing regular-session observations, not a scheduled closure')
            # A continuity cursor is absent across a closed session. No fake
            # minute, price, mark, entry or protective execution is inserted.
            self.last_minute=None
        return super().minute(b)
    def complete(self):
        had=bool(self.minutes);super().complete()
        if had:self.rth_resistance.observe(self.prev)
    def open_signal(self,b,s):
        s['context_partial']=self.calendar.partial_context(self.recent)
        return super().open_signal(b,s)
    def targets(self,entry,h1,t,atr):
        resistance=self.rth_resistance;resistance.large=[p for p in resistance.large if p['t']>=t-7*86400]
        peaks=[p for p in resistance.large if p['high']>h1['high'] and p['known_at']<=t]
        if not peaks:return None,None
        peak=min(peaks,key=lambda p:p['high']);zones=resistance.zones(entry,t)
        zone=next((z for z in zones if any(p['price']==peak['high'] for p in z['members'])),None)
        if not zone:return None,None
        later=next((z for z in zones if z['lower']>zone['upper']),None)
        t1=zone['lower']-.1*atr;t2=later['lower']-.1*atr if later else None
        self.target_reviews.append(dict(time=iso(t),entry=entry,target=t1,large_peak=copy.deepcopy(peak),zone=copy.deepcopy(zone)))
        return t1,t2


class Baseline(SessionMixin,FailedReboundReplay):pass
class Early(SessionMixin,EarlySequentialReplay):pass


def make_engine(model,start,end,db,calendar,adapted):
    if model not in ('0.1','E1','E2'):raise ValueError('Choose an original BTC live model')
    if not adapted:
        from trading_desk.crypto_transfer import make_engine as original
        return original(model,start,end,db)
    cls=Baseline if model=='0.1' else Early;extra={} if model=='0.1' else dict(early_policy=model)
    return cls(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),expanded_b=True,
        consume_entry_history=True,b1_independent_hold=False,calendar=calendar,**extra)
