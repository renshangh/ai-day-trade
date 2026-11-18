"""Fixed-entry, outcome-independent failed-reclaim diagnostics; never orders."""
from __future__ import annotations
import bisect
import copy
from trading_desk.btc_data import iso,ts
from trading_desk.btc_engine import aggregate

PROTOCOL=dict(version='failed-followthrough-draft-1',level='Original local trigger (previous complete 15m high + $0.01), fixed at entry',
    arm='At least one complete observed post-entry 15m candle closes above the trigger before the failure candle starts',
    F1='Two adjacent completed 1m closes below trigger after arming; next actual minute open stays below; current 15m non-green/not above previous complete close and neither full-range nor body inside previous complete bar',
    F2='A later complete 15m candle closes below trigger, red/not above previous close, neither full-range nor body inside; next exact actual minute open remains below',
    timing='Only prior completed observations plus execution-minute open; no current minute high/low/close or future 15m close',
    execution='Exact next observed 1m opening at confirmation boundary as a historical reference only; if absent, no fill/carry-forward. Actual receipt, spread and executable price unverified.',
    precedence='Original exit wins equal-minute ties; overlay can replace only a strictly later exit, keeping earlier 25% legs',
    scope='Original frozen entries fixed, no replacement buys; exits and steeper-shock entry experiment kept separate',
    costs='Same 2bps/side ETF proxy, excluding actual spot crypto fees',
    guards='No 1R profit requirement; no integer-price-level restriction; missing context resets arming; original hard stops retained')


def direction(bar,previous):
    full=bar['high']<=previous['high'] and bar['low']>=previous['low']
    body=min(bar['open'],bar['close'])>=min(previous['open'],previous['close']) and max(bar['open'],bar['close'])<=max(previous['open'],previous['close'])
    return dict(non_green=bar['close']<=bar['open'],not_above_previous_close=bar['close']<=previous['close'],
        full_inside=full,body_inside=body,passed=bar['close']<=bar['open'] and bar['close']<=previous['close'] and not(full or body))


class Market:
    def __init__(self,minutes):
        self.minutes=minutes;self.times=[b['t'] for b in minutes];self.by_t={b['t']:b for b in minutes};groups={}
        assert len(self.times)==len(self.by_t) and all(b>a for a,b in zip(self.times,self.times[1:]))
        for b in minutes:groups.setdefault(b['t']//900*900,[]).append(b)
        self.bars={t:aggregate(g,900) for t,g in groups.items() if [b['t'] for b in g]==list(range(t,t+900,60))}

    def scan(self,p,policy,cutoff=None):
        if policy not in ('F1','F2'):raise ValueError('Choose F1 or F2')
        entry=ts(p['entry_time']);floor=entry//900*900;end=ts(p.get('exit_time') or iso(self.times[-1]+60))
        if cutoff is not None:end=min(end,cutoff)
        level=p['references']['trigger'];armed=None;notes=[];ties={ts(l['time_utc']) for l in p['legs']}
        for now in range(entry+60,end,60):
            # Only a newly completed full 15m bar can arm or confirm F2.
            bar=self.bars.get(now-900) if now%900==0 else None
            previous=self.bars.get(now-1800) if bar else None
            old_arm=copy.deepcopy(armed)
            if bar and bar['t']>=floor and bar['close']>level and armed is None:
                armed=dict(known_at=iso(now),bar_time=iso(bar['t']),close=bar['close'])
            candidate=None
            if policy=='F2' and bar and previous and old_arm and ts(old_arm['known_at'])<=bar['t'] and bar['close']<level:
                gates=direction(bar,previous)
                if gates['passed']:candidate=dict(armed=old_arm,failed_bar=bar,previous_bar=previous,direction=gates,confirmed_at=iso(now))
            b=self.by_t.get(now)
            if b is None:
                if candidate:notes.append(dict(type='next_observation_missing',confirmed_at=iso(now)))
                armed=None;continue
            if policy=='F1' and armed:
                two=[self.by_t.get(now-120),self.by_t.get(now-60)];period=now//900*900
                prev=self.bars.get(period-900);opening=self.by_t.get(period)
                if prev and opening and all(m and m['t']>=max(entry,ts(armed['known_at'])) and m['close']<level for m in two):
                    prefix=[self.by_t.get(t) for t in range(period,now,60)]
                    if all(prefix):
                        current=dict(open=opening['open'],close=b['open'],high=max([b['open']]+[m['high'] for m in prefix]),
                            low=min([b['open']]+[m['low'] for m in prefix]))
                        gates=direction(current,prev)
                        if gates['passed']:candidate=dict(armed=copy.deepcopy(armed),completed_minutes=copy.deepcopy(two),
                            previous_bar=prev,known_current_prefix=current,direction=gates,confirmed_at=iso(now))
            if candidate:
                if b['open']>=level:notes.append(dict(type='next_open_reclaimed',time=iso(now)));continue
                if now in ties:notes.append(dict(type='original_leg_wins_tie',time=iso(now)));continue
                candidate.update(policy=policy,level=level,exit_time=iso(now),exit_reference=b['open'],
                    execution='next exact observed minute open; not a verified live fill',current_minute_range_used=False)
                return dict(signal=candidate,notes=notes)
        return dict(signal=None,notes=notes)


def value(p,scan,policy):
    old=sum(l['net'] for l in p['legs']);signal=scan['signal']
    if signal is None:return dict(triggered=False,original_net=old,net=old,delta=0,normalized_10000_delta=0,
        exit_time=p.get('exit_time'),legs=copy.deepcopy(p['legs']),signal=None,notes=scan['notes'])
    now=ts(signal['exit_time']);legs=[copy.deepcopy(l) for l in p['legs'] if ts(l['time_utc'])<now]
    remaining=1-sum(l['fraction'] for l in legs);price=signal['exit_reference']
    gross=remaining*(price-p['entry']);cost=remaining*(price+p['entry'])*.0002
    legs.append(dict(reason='research_'+policy+'_failed_reclaim',time_utc=iso(now),price=price,fraction=remaining,gross=gross,cost=cost,net=gross-cost,
        time_basis='Historical next-minute open reference; actual receipt/fill unavailable'))
    new=sum(l['net'] for l in legs)
    return dict(triggered=True,original_net=old,net=new,delta=new-old,normalized_10000_delta=(new-old)/p['entry']*10000,
        exit_time=iso(now),legs=legs,signal=signal,notes=scan['notes'],
        original_outcome='winner' if old>0 else 'nonpositive',winner_cut=old>0 and new<old,winner_flipped_to_loss=old>0 and new<=0,
        loser_improved=old<=0 and new>old,loser_worsened=old<=0 and new<old,
        minutes_earlier=(ts(p['exit_time'])-now)/60 if p.get('exit_time') else None)


def summarize(trades,results):
    old=sum(sum(l['net'] for l in p['legs']) for p in trades);new=sum(r['net'] for r in results)
    return dict(trades=len(trades),earlier=sum(r['triggered'] for r in results),original_realized=old,overlay_realized=new,delta=new-old,
        normalized_10000_original=sum(sum(l['net'] for l in p['legs'])/p['entry']*10000 for p in trades),
        normalized_10000_overlay=sum(r['net']/p['entry']*10000 for p,r in zip(trades,results)),
        loser_improved=sum(r.get('loser_improved',False) for r in results),loser_worsened=sum(r.get('loser_worsened',False) for r in results),
        winners_cut=sum(r.get('winner_cut',False) for r in results),winners_flipped_to_loss=sum(r.get('winner_flipped_to_loss',False) for r in results),
        original_winners=sum(sum(l['net'] for l in p['legs'])>0 for p in trades),
        original_nonpositive=sum(sum(l['net'] for l in p['legs'])<=0 for p in trades))
