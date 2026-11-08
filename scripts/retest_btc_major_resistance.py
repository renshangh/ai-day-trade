"""Replay the archived month with predeclared major-hourly resistance only.

Never refetch/replace the baseline source, tune a parameter grid, or route orders.
"""
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

from btc_structure_retest import Config, MajorResistance, STEP, iso, replay, reward_risk, write_csv


def load_source(root):
    baseline=json.loads((root/'RETEST.json').read_text())
    archived={}
    for r in baseline['provenance']['requests']:
        payload=(root/'raw'/r['file']).read_bytes()
        if hashlib.sha256(payload).hexdigest()!=r['sha256']:
            raise ValueError('Archived source hash changed')
        for t,low,high,opening,close,volume in json.loads(payload):
            archived[t]=dict(t=t,open=opening,high=high,low=low,close=close,volume=volume)
    with (root/'BTCUSD_15M.csv').open() as f:
        bars=[dict(t=int(x['t']),**{k:float(x[k]) for k in ('open','high','low','close','volume')})
              for x in csv.DictReader(f)]
    if any(b['t']!=a['t']+STEP for a,b in zip(bars,bars[1:])):
        raise ValueError('Archived snapshot has missing/duplicate observations')
    if any(archived.get(b['t'])!=b for b in bars):
        raise ValueError('Normalized CSV disagrees with exact archived API responses')
    start=int(datetime.fromisoformat(baseline['start_utc'].replace('Z','+00:00')).timestamp())
    end=int(datetime.fromisoformat(baseline['end_utc'].replace('Z','+00:00')).timestamp())
    return baseline,bars,start,end


def compare_candidates(bars, original, cfg):
    """Same 114 original signal instants, independently of position occupancy."""
    by_time={c['signal_t']:c for c in original}
    major=MajorResistance(cfg)
    output=[]
    for b in bars:
        major.observe(b)
        if b['t'] not in by_time:
            continue
        c=by_time[b['t']]
        zones=major.zones(c['close_reference'],b['t']+STEP)
        target=zones[0]['lower']-cfg.target_buffer_atr*c['atr'] if zones else None
        rr=reward_risk(c['close_reference'],c['stop'],target,cfg.one_way_friction_bps) if target else None
        output.append(dict(**c, major_resistance=zones[0]['lower'] if zones else None,
                           major_t1=target,major_t2=zones[1]['lower']-cfg.target_buffer_atr*c['atr'] if len(zones)>1 else None,
                           major_reward_risk=rr, major_pass=bool(rr is not None and rr>=cfg.min_reward_risk),
                           major_reason=('pass price screen; occupancy/fill checked separately' if rr is not None and rr>=cfg.min_reward_risk else
                                         'reject: no known major resistance' if not zones else 'reject: net reward/risk below 2'),
                           major_zones=zones[:2]))
    return output


def main():
    root=Path('reports/btc_structure_2026_11_08')
    baseline,bars,start,end=load_source(root)
    output=root/'major_resistance'
    output.mkdir(exist_ok=True)
    runs=[]
    for bps in (0.0,2.0,5.0):
        cfg=Config(version='V1.2-major-hourly-2026-11-08',resistance_mode='major1h',one_way_friction_bps=bps)
        result=replay(bars,start,end,cfg)
        comparisons=compare_candidates(bars,baseline['runs'][1]['candidates'],cfg)
        result['comparison']=comparisons
        result['summary']['same_signal_count']=len(comparisons)
        result['summary']['same_signal_passes']=sum(c['major_pass'] for c in comparisons)
        result['summary']['execution_candidates']=len(result['candidates'])
        result['summary']['model_entries']=sum(c['decision'].startswith('entered:') for c in result['candidates'])
        result['summary']['profit_factor']=(sum(t['net_r'] for t in result['trades'] if t['net_r']>0)/
                                          -sum(t['net_r'] for t in result['trades'] if t['net_r']<0)
                                          if any(t['net_r']<0 for t in result['trades']) else None)
        runs.append(result)
    report=dict(source_snapshot='../RETEST.json',source_sha256=hashlib.sha256((root/'RETEST.json').read_bytes()).hexdigest(),
                start_utc=iso(start),end_utc=iso(end),test_bars=end//STEP-start//STEP,runs=runs,
                scope='In-sample specification revision. Not out-of-sample validation or real ETF fills.')
    (output/'MAJOR_RETEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    for name in ('candidates','trades','fills','ledger','comparison'):
        write_csv(output/(name.upper()+'.csv'),runs[1][name])
    print(json.dumps([dict(bps=r['config']['one_way_friction_bps'],**r['summary']) for r in runs]))


if __name__=='__main__':
    main()
