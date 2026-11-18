"""Reporting-only cash accounting on original reference trades and actual bars."""
from __future__ import annotations
import csv,gzip,json,math
from datetime import datetime,timezone
from trading_desk.btc_data import iso,ts,save

PROTOCOL=dict(version='unfiltered-90d-1',strategy='Exact frozen 0.2 BTC 0.1/E1/E2 and SOL E1 constructors; no ML, P1, C, adaptive shock, indicator or new exit filters',
    period='90 days ending at the same original November 9 00:00 UTC boundary, seven days of real warmup',
    data='Earlier BTC from read-only original Alpaca cache; earlier SOL via approved GET-only Alpaca source; original 37-day suffix retained byte-for-byte. No filled/synthetic/interpolated bars.',
    original_sizing='Unchanged one initial coin per reference trade; also fixed $10,000 per-entry normalized P/L, not an account return',
    cash_scenario='Separate illustrative $10,000 all-cash account per book; fractional units bought with all available cash including entry cost, partial exits scale unchanged fractions, reinvest only after previous position exits; no borrowing or added cash',
    equity='Cash plus remaining units at each actual observed minute close less hypothetical liquidation cost; open marks are not forced sales. No marks are created in missing minutes.',
    drawdown='Maximum observed minute-close liquidation-equity peak-to-trough percent, includes open-position marks. Gaps/intraminute order can hide worse drawdowns. Original closed-trade R drawdown reported separately.',
    costs='Same frozen 2bps per side ETF friction proxy, excluding actual spot crypto fees, funding, interest and taxes',
    buyhold='Same $10,000 illustrative cash, first actual test-minute opening buy and last actual minute-close liquidation mark, same friction',
    comparison='Original standalone 30-day controls reproduce, and are separately accounted from flat. Continuous 90-day trailing trades may differ from a reset 30-day run.',
    validation='Rules were developed using the overlapping recent month; the 90-day historical extension is not a prospective/out-of-sample profitability proof',
    protection='No broker or broker-paper orders, no account funding, no change to frozen release, prior selectors or either live worker')


def funded_account(trades,bars,start,end,folder=None,capital=10000.,fee=.0002):
    actual=[b for b in bars if start<=b['t']<end]
    if not actual:raise ValueError('No actual test minutes; no account return invented')
    times=[b['t'] for b in actual]
    if len(times)!=len(set(times)) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Actual bars must be ordered and unique')
    observed=set(times);events={};account_trades={}
    for p in trades:
        entry=ts(p['entry_time'])
        if entry not in observed:raise ValueError('Entry minute unavailable; no retrospective fill')
        events.setdefault(entry,[]).append(('entry',p,None))
        for leg in p['legs']:
            t=ts(leg['time_utc'])
            if t not in observed:raise ValueError('Exit minute unavailable; no retrospective fill')
            events.setdefault(t,[]).append(('exit',p,leg))
    cash=capital;units=0.;position=None;peak=capital;peak_at=iso(start);ddmax=0.;worst=None;days={};last=None;held=0;points=[]
    first=actual[0];hold_units=capital/(first['open']*(1+fee));hold_peak=capital;hold_dd=0.;max_observation_gap=0
    for b in actual:
        t=b['t'];gap=(t-last)//60-1 if last is not None else 0;max_observation_gap=max(max_observation_gap,gap)
        for kind,p,leg in events.get(t,[]):
            if kind=='entry':
                if position is not None or units>1e-8:raise ValueError('Overlapping positions require a different cash model')
                before=cash;q=before/(p['entry']*(1+fee));units=q;cash=0.;position=p['id']
                account_trades[p['id']]=dict(trade_id=p['id'],cash_before_entry=before,initial_units=q,entry_cost=q*p['entry']*fee,
                    realized_net=0.,cash_returned=0.,legs=[])
            else:
                if position!=p['id']:raise ValueError('Exit has no corresponding open cash position')
                a=account_trades[p['id']];q=a['initial_units']*leg['fraction'];proceeds=q*leg['price']*(1-fee)
                cash+=proceeds;units-=q;net=a['initial_units']*leg['net'];a['cash_returned']+=proceeds;a['realized_net']+=net
                a['legs'].append(dict(time_utc=leg['time_utc'],fraction=leg['fraction'],units=q,price=leg['price'],net=net,reason=leg['reason']))
                if abs(units)<max(1e-10,a['initial_units']*1e-9):units=0.;position=None
                if units<0:raise ValueError('Negative cash-scenario position')
        if units>0:held+=1
        equity=cash+units*b['close']*(1-fee);when=iso(t+60)
        if not math.isfinite(equity) or equity<0:raise ValueError('Invalid illustrative equity')
        if equity>peak:peak=equity;peak_at=when
        dd=100*(peak-equity)/peak
        if dd>ddmax:
            ddmax=dd;worst=dict(percent=dd,amount=peak-equity,peak_equity=peak,trough_equity=equity,peak_at=peak_at,trough_at=when,recovered_at=None)
        elif worst and worst['recovered_at'] is None and when>worst['trough_at'] and equity>=worst['peak_equity']:worst['recovered_at']=when
        hold_eq=hold_units*b['close']*(1-fee);hold_peak=max(hold_peak,hold_eq);hold_dd=max(hold_dd,100*(hold_peak-hold_eq)/hold_peak)
        point=dict(time_utc=when,minute_start=iso(t),equity=equity,cash=cash,units=units,position_id=position,mark_price=b['close'],drawdown_pct=dd,buyhold_equity=hold_eq,missing_minutes_before=gap)
        points.append(point);day=datetime.fromtimestamp(t,timezone.utc).date().isoformat();days[day]=point
        last=t
    final=points[-1]
    for p in trades:
        a=account_trades[p['id']];assert math.isclose(a['realized_net'],a['initial_units']*p['realized_leg_net'],rel_tol=1e-10,abs_tol=1e-8)
        a['return_on_entry_cash_pct']=100*a['realized_net']/a['cash_before_entry'] if a['cash_before_entry'] else None
        a['open_units']=a['initial_units']*p['remaining'];a['status']=p['status']
    if folder:
        folder.mkdir(parents=True,exist_ok=True)
        with gzip.open(folder/'EQUITY.jsonl.gz','wt') as z:
            for p in points:z.write(json.dumps(p)+'\n')
        with (folder/'EQUITY.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(points[0]));writer.writeheader();writer.writerows(points)
        save(folder/'ACCOUNT_TRADES.json',account_trades);save(folder/'DAILY_EQUITY.json',[dict(date_utc=d,**p) for d,p in days.items()])
    return dict(initial_cash=capital,final_equity=final['equity'],cash=final['cash'],open_units=final['units'],net=final['equity']-capital,
        return_pct=100*(final['equity']/capital-1),max_observed_drawdown_pct=ddmax,drawdown_episode=worst,
        last_mark=final['time_utc'],last_price=final['mark_price'],observed_test_minutes=len(actual),expected_test_minutes=(end-start)//60,
        missing_test_minutes=(end-start)//60-len(actual),max_observation_gap_minutes=max_observation_gap,
        last_mark_age_seconds=end-(actual[-1]['t']+60),observed_held_minutes=held,
        buyhold_return_pct=100*(final['buyhold_equity']/capital-1),buyhold_max_observed_drawdown_pct=hold_dd,
        buyhold_entry_time=iso(first['t']),buyhold_entry_price=first['open'],account_trades=account_trades)


def loss_analysis(trades):
    closed=[p for p in trades if p['status']=='closed'];losses=[p for p in closed if p['net']<0];wins=[p for p in closed if p['net']>0]
    streak=max_streak=0
    for p in sorted(closed,key=lambda p:p['exit_time']):
        streak=streak+1 if p['net']<0 else 0;max_streak=max(max_streak,streak)
    reasons={};routes={}
    for p in closed:
        for key,table in [(p['legs'][-1]['reason'],reasons),(p['entry_rule'],routes)]:
            x=table.setdefault(key,dict(trades=0,losses=0,wins=0,normalized_net=0.));x['trades']+=1;x['losses']+=p['net']<0;x['wins']+=p['net']>0;x['normalized_net']+=p['normalized_10000_realized_net']
    return dict(closed=len(closed),losses=len(losses),wins=len(wins),breakeven=sum(p['net']==0 for p in closed),
        win_rate=len(wins)/len(closed) if closed else None,max_consecutive_losses=max_streak,
        normalized_gross_profit=sum(p['normalized_10000_realized_net'] for p in wins),normalized_gross_loss=sum(p['normalized_10000_realized_net'] for p in losses),
        profit_factor=(sum(p['normalized_10000_realized_net'] for p in wins)/-sum(p['normalized_10000_realized_net'] for p in losses)) if losses else None,
        worst_normalized_loss=min((p['normalized_10000_realized_net'] for p in losses),default=None),
        losing_trade_ids=[p['id'] for p in sorted(losses,key=lambda p:p['normalized_10000_realized_net'])],exit_reasons=reasons,entry_routes=routes)
