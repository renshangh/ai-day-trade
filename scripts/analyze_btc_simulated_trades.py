"""Diagnose frozen BTC model trades, without rerunning or changing the strategy.

Pre-entry descriptors use completed bars only. Post-stop observations are marked
as retrospective, fixed-horizon evidence, never alternative trade outcomes.
"""
import json
from datetime import datetime
from pathlib import Path

from btc_structure_retest import STEP, iso, local, write_csv
from retest_btc_major_resistance import load_source


def stamp(value):
    return int(datetime.fromisoformat(value.replace('Z','+00:00')).timestamp())


def aggregate(bars, seconds):
    groups={}
    for b in bars:
        groups.setdefault(b['t']//seconds*seconds,[]).append(b)
    output=[]
    for t,group in sorted(groups.items()):
        if [b['t'] for b in group] != list(range(t,t+seconds,STEP)):
            continue
        output.append(dict(t=t,end=t+seconds,open=group[0]['open'],close=group[-1]['close'],
                           high=max(b['high'] for b in group),low=min(b['low'] for b in group)))
    return output


def context(aggregated, entry_time):
    known=[b for b in aggregated if b['end']<=entry_time]
    if len(known)<21:
        return dict(available=False)
    sma=sum(b['close'] for b in known[-20:])/20
    old_sma=sum(b['close'] for b in known[-21:-1])/20
    trs=[max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close'])) for a,b in zip(known,known[1:])]
    highs=[];lows=[]
    for i in range(2,len(known)-2):
        p=known[i];others=known[i-2:i]+known[i+1:i+3]
        if all(p['high']>x['high'] for x in others):
            highs.append(dict(time=iso(p['t']),price=p['high']))
        if all(p['low']<x['low'] for x in others):
            lows.append(dict(time=iso(p['t']),price=p['low']))
    hstate=('HH' if highs[-1]['price']>highs[-2]['price'] else 'LH' if highs[-1]['price']<highs[-2]['price'] else 'equal') if len(highs)>1 else None
    lstate=('HL' if lows[-1]['price']>lows[-2]['price'] else 'LL' if lows[-1]['price']<lows[-2]['price'] else 'equal') if len(lows)>1 else None
    return dict(available=True,last_end_utc=iso(known[-1]['end']),last_close=known[-1]['close'],
                sma20=sma,sma20_change= sma-old_sma,close_vs_sma_pct=(known[-1]['close']/sma-1)*100,
                atr14=sum(trs[-14:])/14,hour_highs=highs[-2:],hour_lows=lows[-2:],
                swing_highs=hstate,swing_lows=lstate)


def fixed_followup(bars, exit_start, entry, target, l1, hours):
    begin=exit_start+STEP;end=begin+hours*3600
    after=[b for b in bars if begin<=b['t']<end]
    complete=len(after)==hours*4 and all(b['t']==begin+i*STEP for i,b in enumerate(after))
    if not complete:
        return dict(hours=hours,complete=False,observed_bars=len(after),expected_bars=hours*4)
    recovery=next((b['t']+STEP for b in after if b['close']>=entry),None)
    target_touch=next((b['t'] for b in after if b['high']>target),None)
    return dict(hours=hours,complete=True,high=max(b['high'] for b in after),low=min(b['low'] for b in after),
                closing_price=after[-1]['close'],close_change_from_entry_pct=(after[-1]['close']/entry-1)*100,
                first_close_above_entry_utc=iso(recovery) if recovery else None,
                minutes_from_stop_bar_end_to_recovery=(recovery-begin)//60 if recovery else None,
                first_target_trade_through_interval_utc=iso(target_touch) if target_touch else None,
                broke_l1=min(b['low'] for b in after)<l1)


def diagnose(root):
    baseline,bars,start,end=load_source(root)
    frozen=json.loads((root/'major_resistance/MAJOR_RETEST.json').read_text())['runs'][1]
    candles={b['t']:b for b in bars}
    candidates={c['confirmed_utc']:c for c in frozen['candidates']}
    hourly=aggregate(bars,3600);fourhour=aggregate(bars,14400)
    rows=[]
    for t in frozen['trades']:
        c=candidates[t['signal_time_utc']]
        at=stamp(t['entry_time_utc']);stop_at=stamp(t['exit_time_utc'])
        holding=[b for b in bars if at<=b['t']<stop_at]
        exit_bar=candles[stop_at]
        prior_high=max([t['entry']]+[b['high'] for b in holding])
        stop_distance=t['entry']-t['initial_stop']
        h1bars=[b for b in bars if stamp(c['l1_time_utc'])<b['t']<stamp(c['l2_time_utc'])]
        h1=max(b['high'] for b in h1bars)
        prior={hours:candles.get(at-hours*3600) for hours in (6,24)}
        known_pre=[b for b in bars if b['t']+STEP<=at]
        past_day=[b for b in known_pre if b['t']>=at-86400]
        day_low=min(b['low'] for b in past_day);day_high=max(b['high'] for b in past_day)
        returns={f'prior_{hours}h_return_pct':(known_pre[-1]['close']/bar['open']-1)*100 if bar else None for hours,bar in prior.items()}
        row=dict(id=t['id'],entry_time_ny=t['entry_time_ny'],entry=t['entry'],stop=t['initial_stop'],
                 t1=t['t1'],t1_distance_atr=(t['t1']-t['entry'])/c['atr'],net_r=t['net_r'],
                 exit_interval_start_ny=t['exit_time_ny'],exit_interval_end_ny=local(stop_at+STEP),
                 hold_min_minutes=(stop_at-at)//60,hold_max_minutes=(stop_at-at+STEP)//60,
                 signal_atr15=c['atr'],stop_distance=stop_distance,stop_distance_pct=stop_distance/t['entry']*100,
                 stop_distance_atr15=stop_distance/c['atr'],stop_buffer_atr15=(c['l2']-t['initial_stop'])/c['atr'],
                 l1=c['l1'],l2=c['l2'],higher_low_gap_atr=(c['l2']-c['l1'])/c['atr'],local_h1=h1,
                 signal_close_above_local_h1=c['close_reference']>h1,
                 close_beyond_trigger_atr=(c['close_reference']-c['trigger'])/c['atr'],
                 pre_entry_24h_low=day_low,pre_entry_24h_high=day_high,
                 entry_location_in_prior_24h_range=(t['entry']-day_low)/(day_high-day_low) if day_high>day_low else None,
                 pre_exit_max_high=prior_high,exit_bar_high=exit_bar['high'],
                 favorable_stop_distance_lower=(prior_high-t['entry'])/stop_distance,
                 favorable_stop_distance_upper=(max(prior_high,exit_bar['high'])-t['entry'])/stop_distance,
                 initial_stop_touched=exit_bar['low']<=t['initial_stop'],
                 stop_bar_open=exit_bar['open'],stop_bar_high=exit_bar['high'],stop_bar_low=exit_bar['low'],stop_bar_close=exit_bar['close'],
                 stop_bar_close_below_initial_stop=exit_bar['close']<t['initial_stop'],
                 stop_bar_close_below_l2=exit_bar['close']<c['l2'],
                 stop_bar_close_above_entry=exit_bar['close']>=t['entry'],
                 stop_bar_also_traded_through_t1=exit_bar['high']>t['t1'],
                 hourly=context(hourly,at),fourhour=context(fourhour,at),**returns)
        for key in ('hourly','fourhour'):
            cx=row[key]
            cx['entry_vs_known_sma_pct']=(t['entry']/cx['sma20']-1)*100
            cx['entry_below_latest_confirmed_low']=t['entry']<cx['hour_lows'][-1]['price'] if cx['hour_lows'] else None
        row['stop_distance_atr1h']=stop_distance/row['hourly']['atr14']
        row['post_exit']=[fixed_followup(bars,stop_at,t['entry'],t['t1'],c['l1'],hours) for hours in (1,4,24)]
        rows.append(row)
    return dict(source_snapshot='major_resistance/MAJOR_RETEST.json',baseline_config=frozen['config'],
                scope='Diagnostic only; no parameter changes, alternative stops, new signals or simulated replacement trades.',
                stop_timing='Interval known, exact tick unknown; favorable excursion bounds exclude/include stop-bar high.',
                rows=rows)


def main():
    root=Path('reports/btc_structure_2026_11_08')
    result=diagnose(root)
    (root/'major_resistance/TRADE_DIAGNOSTICS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    simple=[]
    for row in result['rows']:
        flat={k:v for k,v in row.items() if not isinstance(v,(dict,list))}
        for name in ('hourly','fourhour'):
            flat.update({name+'_'+k:v for k,v in row[name].items() if not isinstance(v,(dict,list))})
        for follow in row['post_exit']:
            flat.update({f"after_{follow['hours']}h_"+k:v for k,v in follow.items()})
        simple.append(flat)
    write_csv(root/'major_resistance/TRADE_DIAGNOSTICS.csv',simple,keys=list(dict.fromkeys(k for r in simple for k in r)))
    for r in result['rows']:
        print(json.dumps({k:r[k] for k in ('id','entry_time_ny','stop_distance_atr15','stop_distance_atr1h',
                                         'favorable_stop_distance_lower','favorable_stop_distance_upper',
                                         'entry_location_in_prior_24h_range','stop_bar_close_below_l2','net_r')},ensure_ascii=False))


if __name__=='__main__':
    main()
