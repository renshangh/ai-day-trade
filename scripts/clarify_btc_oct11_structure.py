"""Relabel only October 11 after the owner specifies D-based protection.

This is a single-case structural clarification, not a monthly strategy revision.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from analyze_btc_simulated_trades import aggregate
from btc_structure_retest import Config, MajorResistance, STEP, iso, local, reward_risk, write_csv
from retest_btc_major_resistance import load_source


def stamp(value):
    return int(datetime.fromisoformat(value).timestamp())


def trace_remaining(bars, before_atr, first_target, initial_stop, next_target, resistance, cfg, end_at):
    """Audit one nominated path, never enter the frozen monthly replay.

    A new high means exceeding the previous wave peak, not the prior candle.
    Use the lowest *completed* bar after that peak and before the new-high bar;
    a breakout-bar low has unknown intrabar ordering and cannot be its anchor.
    Keep the existing 0.25 ATR buffer, using ATR known at the bar start. Stop
    changes take effect next bar, avoiding unobservable within-bar sequencing.
    """
    peak=first_target['high']
    peak_at=first_target['t']
    stop=initial_stop
    pullback=[]
    rows=[]
    events=[]
    pending_weak_exit=False
    for b in bars:
        if not first_target['t']<b['t']<end_at:
            continue
        row=dict(start_ny=local(b['t']),end_ny=local(b['t']+STEP),
                 open=b['open'],high=b['high'],low=b['low'],close=b['close'],
                 active_stop=stop,previous_wave_high=peak,previous_wave_high_start_ny=local(peak_at),
                 new_high=False,reference_low=None,reference_low_start_ny=None,
                 atr_known_at_start=before_atr.get(b['t']),new_stop=None,effective_from_ny=None,
                 action='hold; no new wave high')
        rows.append(row)
        reason=None
        if pending_weak_exit:
            reason='wick_failure_next_open'; price=b['open']
        elif b['low']<=stop:
            reason='stop'; price=min(b['open'],stop)
        elif next_target is not None and b['high']>next_target:
            reason='target2'; price=next_target
        if reason:
            row['action']='exit remaining 75%: '+reason
            events.append(dict(interval_start_ny=local(b['t']),interval_end_ny=local(b['t']+STEP),
                               reason=reason,price_reference=price,fraction_initial=.75,
                               time_basis='15m interval only; conditional reference, not verified fill'))
            return dict(rows=rows,events=events,terminal=True)
        if b['high']>peak:
            row['new_high']=True
            row['action']='new wave high; no completed intervening pullback, keep stop'
            if pullback:
                anchor=min(pullback,key=lambda x:x['low'])
                assert anchor['t']+STEP<=b['t']
                atr=before_atr.get(b['t'])
                row['reference_low']=anchor['low']
                row['reference_low_start_ny']=local(anchor['t'])
                if atr is None:
                    raise ValueError('Missing actual pre-breakout ATR; do not fill defaults')
                proposed=anchor['low']-cfg.stop_buffer_atr*atr
                row['action']='new wave high; candidate does not raise protection, keep stop'
                if stop<proposed<peak:
                    row.update(new_stop=proposed,effective_from_ny=local(b['t']+STEP),
                               action='new wave high; raise stop next bar')
                    events.append(dict(known_at_ny=local(b['t']+STEP),
                                       breakout_interval_start_ny=local(b['t']),
                                       effective_from_ny=local(b['t']+STEP),reason='raise_after_new_high',
                                       price_reference=proposed,fraction_initial=0,
                                       reference_low=anchor['low'],reference_low_start_ny=local(anchor['t']),
                                       atr_known_at_breakout_start=atr))
                    stop=proposed
            peak=b['high']; peak_at=b['t']; pullback=[]
        else:
            pullback.append(b)
        span=b['high']-b['low']; wick=b['high']-max(b['open'],b['close'])
        if span>0 and b['high']>=resistance and wick/span>=cfg.upper_wick_fraction and b['close']<resistance:
            pending_weak_exit=True
            row['action']+='; resistance wick failure, exit next actual open'
    return dict(rows=rows,events=events,terminal=False)


def clarify(root):
    _,bars,_,_=load_source(root)
    frozen_path=root/'major_resistance/MAJOR_RETEST.json'
    frozen=json.loads(frozen_path.read_text())['runs'][1]
    cfg=Config(**frozen['config'])
    by_time={b['t']:b for b in bars}
    ledger={stamp(x['start_utc']):x for x in frozen['ledger']}
    atr_before={t+STEP:x['atr'] for t,x in ledger.items()}
    at=stamp('2026-10-11T10:00:00-04:00')
    anchors={
        'macro_L1':by_time[stamp('2026-10-11T00:00:00-04:00')],
        'macro_H1':by_time[stamp('2026-10-11T03:00:00-04:00')],
        'macro_L2_D':by_time[stamp('2026-10-11T06:45:00-04:00')],
        'local_H2':by_time[stamp('2026-10-11T08:00:00-04:00')],
        'local_pullback_at_entry':by_time[at-STEP],
    }
    for a in anchors.values():
        assert a['t']+STEP<=at
    assert anchors['macro_L2_D']['low']>anchors['macro_L1']['low']
    entry=round(by_time[at-STEP]['high']+.01,2)
    stop=82865.0  # Explicit owner clarification, not an ATR-fit to later prices.
    atr=atr_before[at]
    major=MajorResistance(cfg)
    for b in bars:
        if b['t']+STEP<=at:
            major.observe(b)
    zones=major.zones(entry,at)
    h4=[h for h in aggregate(bars,14400) if h['end']<=at]
    # A larger wave target: nearest already-confirmed 4h swing high above the
    # current formation's upper boundary. This ranks scale rather than PnL.
    peaks=[]
    for i in range(2,len(h4)-2):
        p=h4[i]
        if p['t']<at-7*86400:
            continue
        if p['high']>anchors['local_H2']['high'] and all(p['high']>h['high'] for h in h4[i-2:i]+h4[i+1:i+3]):
            peaks.append(dict(time_utc=iso(p['t']),price=p['high'],known_at_utc=iso(h4[i+2]['end'])))
    peak=min(peaks,key=lambda x:x['price'])
    zone=next(z for z in zones if any(p['price']==peak['price'] for p in z['members']))
    target=zone['lower']-cfg.target_buffer_atr*atr
    next_zone=next((z for z in zones if z['lower']>zone['upper']),None)
    next_target=next_zone['lower']-cfg.target_buffer_atr*atr if next_zone else None
    price_path=[b for b in bars if at<=b['t']]
    first_target=next(b for b in price_path if b['high']>target)
    before_target=[b for b in price_path if b['t']<first_target['t']]
    remaining=trace_remaining(bars,atr_before,first_target,stop,next_target,zone['lower'],cfg,
                              stamp('2026-10-12T00:00:00-04:00'))
    q=cfg.one_way_friction_bps/10000
    risk=entry-stop+q*(entry+stop)
    min_target_2r=(entry*(1+q)+cfg.min_reward_risk*risk)/(1-q)
    result=dict(scope='October 11 only; owner-selected D stop and larger-wave target clarification; no monthly rerun.',
                original_replay_sha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
                entry_interval_start_ny=local(at),entry_interval_end_ny=local(at+STEP),
                anchors={k:dict(**b,start_ny=local(b['t']),end_ny=local(b['t']+STEP)) for k,b in anchors.items()},
                entry_reference=entry,user_confirmed_stop=stop,d_to_stop_buffer=anchors['macro_L2_D']['low']-stop,
                atr_known_at_entry=atr,larger_resistance_peak=peak,primary_supply_zone=zone,
                intermediate_obstacles=[z for z in zones if z['lower']<zone['lower']],
                target1_reference=target,next_target_reference=next_target,
                gross_reward_risk=(target-entry)/(entry-stop),net_reward_risk=reward_risk(entry,stop,target,cfg.one_way_friction_bps),
                minimum_target_for_unchanged_2r=min_target_2r,
                passes_unchanged_t1_rr=reward_risk(entry,stop,target,cfg.one_way_friction_bps)>=cfg.min_reward_risk,
                first_target_interval_start_ny=local(first_target['t']),
                min_price_before_target_bar=min(b['low'] for b in before_target),
                exit_policy=dict(first_exit_fraction_initial=.25,remaining_fraction_initial=.75,
                    initial_stop=stop,first_exit_moves_stop=False,
                    stop_recalculation_requires_new_high=True,stop_may_only_increase=True,
                    new_high_reference='strict intrabar break of previous wave peak; baseline first-target bar high',
                    pullback_reference='lowest completed bar after prior peak bar and before breakout bar',
                    stop_buffer_atr=cfg.stop_buffer_atr,atr_timing='completed bars known at breakout bar start',
                    stop_effective='next 15m bar; OHLC does not prove intrabar order',
                    remaining_exit_status='conditional_single_case_exit' if remaining['terminal'] else 'open_at_review_end',
                    interpretation='explicit single-case audit convention, not optimized or monthly-validated'),
                conditional_exit_trace=[dict(interval_start_ny=local(first_target['t']),
                    interval_end_ny=local(first_target['t']+STEP),reason='target1',
                    price_reference=target,fraction_initial=.25,stop_after_first_exit=stop,
                    time_basis='15m interval only; not a verified fill')]+remaining['events'],
                after_first_target_bars=remaining['rows'],
                old_config=frozen['config'])
    # Optional acceleration descriptor: only assess after the target bar closes.
    prior=by_time[first_target['t']-STEP]
    tr=max(first_target['high']-first_target['low'],abs(first_target['high']-prior['close']),abs(first_target['low']-prior['close']))
    result['target_bar_after_close']=dict(known_at_ny=local(first_target['t']+STEP),
        open=first_target['open'],high=first_target['high'],low=first_target['low'],close=first_target['close'],
        true_range=tr,prior_completed_atr=atr_before[first_target['t']],tr_to_prior_atr=tr/atr_before[first_target['t']],
        close_location=(first_target['close']-first_target['low'])/(first_target['high']-first_target['low']))
    end=stamp('2026-10-11T15:15:00-04:00')
    labels={a['t']:name for name,a in anchors.items()}
    rows=[]
    for b in bars:
        if stamp('2026-10-11T00:00:00-04:00')<=b['t']<end:
            rows.append(dict(start_ny=local(b['t']),end_ny=local(b['t']+STEP),open=b['open'],high=b['high'],
                             low=b['low'],close=b['close'],label=labels.get(b['t'],''),
                             user_stop=stop if b['t']>=at else None))
    result['bars']=rows
    return result


def main():
    root=Path('reports/btc_structure_2026_11_08')
    result=clarify(root)
    out=root/'entry_examples'
    out.mkdir(exist_ok=True)
    (out/'OCT11_USER_STRUCTURE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    write_csv(out/'OCT11_USER_STRUCTURE_BARS.csv',result['bars'])
    print(json.dumps({k:v for k,v in result.items() if k not in ('bars','after_first_target_bars','anchors','old_config','intermediate_obstacles','primary_supply_zone')},ensure_ascii=False))


if __name__=='__main__':
    main()
