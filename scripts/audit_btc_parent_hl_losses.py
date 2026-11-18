"""Read saved C losses and observed bars only; never instantiate a replay."""
from __future__ import annotations
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import aggregate
from trading_desk.btc_live import LIVE,CONTROLLER,verify_rules

NY=ZoneInfo('America/New_York')
OUT=ROOT/'reports/btc_parent_hl_loss_audit_2026_11_09'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
local=lambda t:datetime.fromtimestamp(t,NY).isoformat()


def bars(rows,frame):
    groups={}
    for b in rows:groups.setdefault(b['t']//frame*frame,[]).append(b)
    return [aggregate(obs,frame) for _,obs in sorted(groups.items())]


def pivots(series,frame,cutoff):
    """Same strict complete-neighbour convention, not wave classification."""
    result=[]
    for a,b,c in zip(series,series[1:],series[2:]):
        if c['t']+frame>cutoff:continue
        if b['t']!=a['t']+frame or c['t']!=b['t']+frame:continue
        if any(x['observed_minutes']!=frame//60 for x in (a,b,c)):continue
        lo=b['low']<min(a['low'],c['low']);hi=b['high']>max(a['high'],c['high'])
        if not lo and not hi:continue
        kind='outside' if lo and hi else 'L' if lo else 'H'
        result.append(dict(kind=kind,bar_time=b['t'],known_at=c['t']+frame,
            low=b['low'],high=b['high'],time=b['low_t'] if lo else b['high_t'],
            price=b['low'] if lo else b['high']))
    return result


def inspect(rows,context,entry,cutoff,record=None):
    start=context['parent']['bar_time']-7200
    observed=[b for b in rows if start<=b['t']<cutoff]
    fifteen=bars(observed,900);hours=bars(observed,3600)
    turns=pivots(fifteen,900,entry)
    prior_lows=[p for p in turns if p['kind']=='L' and p['time']<context['hl']['time']]
    prior_highs=[p for p in turns if p['kind']=='H' and p['time']<context['hl']['time']]
    hourly=pivots(hours,3600,entry)
    parent_candidates=[]
    for p in hourly:
        if p['kind']!='L':continue
        breaks=[b for b in observed if p['known_at']<=b['t']<entry and b['low']<=p['price']]
        parent_candidates.append(dict(p,broken_before_entry=bool(breaks),
            first_break=breaks[0]['t'] if breaks else None))
    # Extremes of entry/exit minutes cannot be assigned to the holding interval
    # without tick ordering. Breach references below include the exit minute,
    # but the excursion diagnostic excludes both boundary minutes.
    post=[b for b in observed if entry<b['t']<=ts(record['exit_time'])] if record else []
    diagnostics={}
    if record:
        for key,price in [('nearer_HL',context['hl']['price']),('parent_D',context['parent']['price']),('initial_stop',record['initial_stop'])]:
            first=next((b for b in post if b['low']<price),None)
            diagnostics[key]=dict(level=price,first_break=iso(first['t']) if first else None)
        interior=[b for b in post if b['t']<ts(record['exit_time'])]
        diagnostics['maximum_after_entry_minute']=dict(time=iso(max(interior,key=lambda b:b['high'])['t']),
            high=max(b['high'] for b in interior),gain=max(b['high'] for b in interior)-record['entry']) if interior else None
    return dict(context=context,entry_time=iso(entry),cutoff=iso(cutoff),
        parent_age_hours=(entry-context['parent']['time'])/3600,
        previous_confirmed_15m_low=prior_lows[-1] if prior_lows else None,
        previous_confirmed_15m_high=prior_highs[-1] if prior_highs else None,
        local_HL_vs_previous_low=(context['hl']['price']>prior_lows[-1]['price']) if prior_lows else None,
        confirmed_turns_known_at_entry=turns,hourly_turns_known_at_entry=hourly,
        parent_candidates_known_at_entry=parent_candidates,
        bars_15m=fifteen,bars_1h=hours,minutes=observed,
        record=record,post_entry_diagnostics=diagnostics,
        source_observed_minutes=len(observed),
        missing_minutes=(cutoff-start)//60-len(observed),
        retrospective_rows_not_entry_evidence=True)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    study_id=read(STORE/'parent_hl_studies/ACTIVE.json')['study_id']
    study=read(STORE/'parent_hl_studies'/study_id/'STUDY.json')
    frozen=STORE/'releases/0.2';manifest=read(frozen/'MANIFEST.json')
    protected={frozen/p:h for p,h in manifest['files_sha256'].items()}
    for pattern in ('trading_desk/btc_p1*','trading_desk/btc_parent_hl*'):
        for p in ROOT.glob(pattern):
            if p.is_file():protected[p]=sha(p)
    for family in ('parent_hl_studies','p1_studies'):
        pointer=STORE/family/'ACTIVE.json';protected[pointer]=sha(pointer)
        active=read(pointer)['study_id'];folder=STORE/family/active
        for p in folder.rglob('*'):
            if p.is_file():protected[p]=sha(p)
        for rid in read(folder/'STUDY.json')['run_ids'].values():
            for p in (STORE/'runs'/rid).rglob('*'):
                if p.is_file():protected[p]=sha(p)
    for p in (LIVE/'SESSION.json',LIVE/'CONTROL.json',STORE/'studies/ACTIVE.json',STORE/'releases/ACTIVE.json'):
        protected[p]=sha(p)
    verify_rules();before=CONTROLLER.status()
    with gzip.open(frozen/'data/MINUTES.jsonl.gz','rb') as f:raw=f.read()
    assert hashlib.sha256(raw).hexdigest()==study['source_minute_sha256']
    rows=[dict(zip(('t','open','high','low','close','volume','n','vw'),json.loads(line))) for line in raw.splitlines()]
    results={m:read(STORE/'runs'/rid/'result.json') for m,rid in study['run_ids'].items()}
    base=results['0.1'];worst=sorted((p for p in base['trades'] if p['entry_rule']=='C'),key=lambda p:p['net'])[:4]
    e1_worst=min((p for p in results['E1']['trades'] if p['entry_rule']=='C'),key=lambda p:p['net'])
    extra=next(p for p in base['trades'] if p['entry_time']==e1_worst['entry_time'] and p['entry_rule']=='C')
    if extra not in worst:worst.append(extra)
    audit=dict(study_id=study_id,selection='largest four 0.1 C losses plus largest E1 loss; E2 largest four coincide',
        source_minute_sha256=study['source_minute_sha256'],model_replayed=False,parameters_changed=False,cases=[])
    for p in worst:
        entry=ts(p['entry_time']);end=(ts(p['exit_time'])//900+1)*900
        item=inspect(rows,p['continuation'],entry,end,p)
        item['label']='baseline-C-'+str(p['id'])
        prior=next(b for b in item['bars_15m'] if b['t']==entry//900*900-900)
        minute=next(b for b in item['minutes'] if b['t']==entry)
        signal=next(x for x in base['signals'] if x['id']==p['signal_id'])
        assert prior['observed_minutes']==15 and minute['high']>prior['high']+.01
        assert p['entry']==max(prior['high']+.01,minute['open'])==signal['entry_reference']
        assert abs(p['initial_stop']-(p['continuation']['parent']['price']-.25*signal['atr']))<1e-8
        for key,price_key in [('parent','low'),('hl','low'),('rebound','high')]:
            point=p['continuation'][key]
            assert next(b for b in item['minutes'] if b['t']==point['time'])[price_key]==point['price']
            assert point['known_at']<=entry
        assert sum(x['fraction'] for x in p['legs'])==1 and len(p['legs'])==1
        item['saved_signal']=signal
        item['models']={}
        for model,result in results.items():
            other=next((x for x in result['trades'] if x['entry_rule']=='C' and x['entry_time']==p['entry_time']),None)
            item['models'][model]=None if other is None else {k:other[k] for k in ('id','entry_time','entry','initial_stop','exit_time','net','legs')}
        assert all(x['known_at']<=entry for x in item['confirmed_turns_known_at_entry'])
        audit['cases'].append(item)
    case=read(STORE/'parent_hl_studies'/study_id/'CASE_NOV09.json');cutoff=ts(case['cutoff'])
    source=LIVE/'sessions'/case['source_session']/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        actual=[json.loads(x) for x, in db.execute('SELECT body FROM minutes WHERE t<? ORDER BY t',(cutoff,))]
    benchmark=inspect(actual,case['signal']['setup_evidence'],ts(case['signal']['time_utc']),cutoff)
    benchmark.update(label='Nov09-0317-prefix',signal=case['signal'],existing_priority_position=case['existing_priority_position'])
    audit['benchmark']=benchmark
    save(OUT/'AUDIT.json',audit)
    # Every observed minute/candle is exported, including the partial exit
    # candle. Completeness and whether it was known at entry are explicit.
    for name,frame,key in [('BARS_15M.csv',900,'bars_15m'),('BARS_1H.csv',3600,'bars_1h'),('MINUTES.csv',60,'minutes')]:
        fields=['case','time_ny','end_ny','known_by_entry','observed_minutes','open','high','low','close','notes']
        with (OUT/name).open('w',newline='') as f:
            writer=csv.DictWriter(f,fields);writer.writeheader()
            for item in audit['cases']+[benchmark]:
                for b in item[key]:
                    t=b['t'];observed=b.get('observed_minutes',1)
                    writer.writerow(dict(case=item['label'],time_ny=local(t),end_ny=local(t+frame),
                        known_by_entry=t+frame<=ts(item['entry_time']),observed_minutes=observed,
                        **{k:b[k] for k in ('open','high','low','close')},
                        notes='partial observation' if observed<frame//60 else 'observed; later rows are hindsight context only'))
    verify_rules();assert all(sha(p)==h for p,h in protected.items())
    after=CONTROLLER.status()
    assert after['pid']==before['pid'] and after['session']['id']==before['session']['id']
    assert not after['orders_enabled']
    save(OUT/'PRESERVATION.json',dict(files={str(p.relative_to(ROOT)):h for p,h in protected.items()},
        worker_pid=after['pid'],session=after['session']['id'],health=after['health'],quote_fresh=after['quote_fresh'],
        monthly_replay=False,rule_mutation=False,orders_enabled=False))
    print(json.dumps(dict(cases=[dict(label=i['label'],entry=i['entry_time'],parent_age_hours=i['parent_age_hours'],
        previous_low=i['previous_confirmed_15m_low'],HL_is_higher_than_that_low=i['local_HL_vs_previous_low']) for i in audit['cases']+[benchmark]],
        protected_files=len(protected),live_health=after['health']),indent=2))
    return audit


if __name__=='__main__':run()
