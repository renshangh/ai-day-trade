"""Side-by-side P1 low confirmation on six saved C examples; no replay."""
from __future__ import annotations
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import aggregate
from trading_desk.btc_p1 import P1Detector,P1_RULE
from trading_desk.btc_live import LIVE,CONTROLLER,verify_rules
from scripts.audit_btc_parent_hl_losses import local

PRIOR=ROOT/'reports/btc_parent_hl_loss_audit_2026_11_09'
OUT=ROOT/'reports/btc_c_p1_confirmation_2026_11_09'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def completed_bars(rows):
    groups={}
    for b in rows:groups.setdefault(b['t']//900*900,[]).append(b)
    return {t:aggregate(obs,900) for t,obs in sorted(groups.items())}


def atr_before(bars,t):
    # Fourteen observed true ranges need fifteen previous complete candles.
    previous=[bars.get(t-i*900) for i in range(15,0,-1)]
    if any(b is None or b['observed_minutes']!=15 for b in previous):return None
    return sum(max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close']))
        for a,b in zip(previous,previous[1:]))/14


def check(point,entry,end,bars):
    start=point['time']//900*900
    subset={t:copy.deepcopy(b) for t,b in bars.items() if start<=t<end}
    for t,b in subset.items():b['atr_before']=atr_before(bars,t)
    detector=P1Detector();detector.p1_bars=subset;detector.p1_now=entry
    at_entry=detector.low_check(point)
    trace=[]
    for t in range(start+900,entry//900*900,900):
        b=subset.get(t);atr=at_entry['atr']
        trace.append(dict(start_utc=iso(t),start_ny=local(t),complete_at=iso(t+900),
            observed_minutes=b['observed_minutes'] if b else 0,
            high=b['high'] if b else None,low=b['low'] if b else None,close=b['close'] if b else None,
            holds=bool(b and b['observed_minutes']==15 and b['low']>point['price']),
            reaches_one_atr=bool(b and atr and b['high']>=point['price']+atr),
            close_reaches_half_atr=bool(b and atr and b['close']>=point['price']+.5*atr)))
    later=[]
    # Later completions are timing diagnostics only, never hypothetical fills.
    for known in range(entry//900*900+900,end+1,900):
        detector.p1_now=known;state=detector.low_check(point)
        later.append(dict(known_at=iso(known),check=state))
        if state['status']!='waiting':break
    first=at_entry['qualified_at']
    if first is None:
        first=next((x['check']['qualified_at'] for x in later if x['check']['status']=='qualified'),None)
    return dict(point=point,atr_before_low=at_entry['atr'],
        high_required=point['price']+at_entry['atr'] if at_entry['atr'] else None,
        close_required=point['price']+.5*at_entry['atr'] if at_entry['atr'] else None,
        at_original_entry=at_entry,first_qualified_at=iso(first) if first else None,
        trace_known_at_entry=trace,later_confirmation_only=later)


def run():
    audit=read(PRIOR/'AUDIT.json');proof=read(PRIOR/'PRESERVATION.json')
    protected={ROOT/p:h for p,h in proof['files'].items()}
    for p in PRIOR.iterdir():
        if p.is_file():protected[p]=sha(p)
    assert all(sha(p)==h for p,h in protected.items());verify_rules()
    before=CONTROLLER.status()
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:raw=f.read()
    assert hashlib.sha256(raw).hexdigest()==audit['source_minute_sha256']
    rows=[dict(zip(('t','open','high','low','close','volume','n','vw'),json.loads(line))) for line in raw.splitlines()]
    frozen_bars=completed_bars(rows)
    benchmark=audit['benchmark'];entry=ts(benchmark['entry_time']);end=entry//900*900+5*900
    session=read(STORE/'parent_hl_studies'/audit['study_id']/'CASE_NOV09.json')['source_session']
    source=LIVE/'sessions'/session/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        actual=[json.loads(body) for body, in db.execute('SELECT body FROM minutes WHERE t>=? AND t<? ORDER BY t',
            (benchmark['context']['parent']['bar_time']-15*900,end))]
    actual_bars=completed_bars(actual)
    assert abs(atr_before(actual_bars,entry//900*900)-benchmark['signal']['atr'])<1e-8
    study=read(STORE/'parent_hl_studies'/audit['study_id']/'STUDY.json')
    ledger=STORE/'runs'/study['run_ids']['0.1']/'ledger.sqlite'
    result=dict(study_id=audit['study_id'],rules=copy.deepcopy(P1_RULE),scope='P1 low_check on parent D and entry HL separately; not the four-LL A setup',
        monthly_replay=False,rules_changed=False,orders_enabled=False,cases=[],
        source_minute_sha256=audit['source_minute_sha256'],
        live_observation_slice_sha256=hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest())
    with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True) as db:
        for item in audit['cases']+[benchmark]:
            is_benchmark=item is benchmark;bars=actual_bars if is_benchmark else frozen_bars
            entry=ts(item['entry_time']);end=entry//900*900+5*900
            row=dict(label=item['label'],entry_time=item['entry_time'],entry_ny=local(entry),
                net=None if is_benchmark else item['record']['net'],checks={})
            for key in ('parent','hl'):
                point=item['context'][key];start=point['time']//900*900
                if not is_benchmark:
                    record=db.execute('SELECT body FROM ledger WHERE t=?',(start,)).fetchone()
                    assert record is not None
                    assert abs(atr_before(bars,start)-json.loads(record[0])['atr_before'])<1e-8
                row['checks'][key]=check(point,entry,end,bars)
                prefix={t:b for t,b in bars.items() if t+900<=entry}
                original=check(point,entry,entry//900*900,prefix)
                assert original['at_original_entry']==row['checks'][key]['at_original_entry']
            row['parent_gate_passes']=row['checks']['parent']['at_original_entry']['status']=='qualified'
            row['HL_gate_passes']=row['checks']['hl']['at_original_entry']['status']=='qualified'
            result['cases'].append(row)
    assert all(row['parent_gate_passes'] for row in result['cases'])
    assert [row['label'] for row in result['cases'] if row['HL_gate_passes']]==['baseline-C-13']
    result['prefix_only_checks_equal']=True
    OUT.mkdir(parents=True,exist_ok=True);save(OUT/'COMPARISON.json',result)
    with (OUT/'SUMMARY.csv').open('w',newline='') as f:
        fields=['case','original_entry_ny','original_net','parent_P1_pass','HL_P1_pass','HL_price','ATR_before_HL',
            'completed_holds_at_entry','required_high','observed_high_at_entry','required_close','observed_close_at_entry','first_HL_P1_confirmation_ny']
        writer=csv.DictWriter(f,fields);writer.writeheader()
        for row in result['cases']:
            c=row['checks']['hl'];state=c['at_original_entry'];known=c['first_qualified_at']
            writer.writerow(dict(case=row['label'],original_entry_ny=row['entry_ny'],original_net=row['net'],
                parent_P1_pass=row['parent_gate_passes'],HL_P1_pass=row['HL_gate_passes'],HL_price=c['point']['price'],
                ATR_before_HL=c['atr_before_low'],completed_holds_at_entry=state['holds'],required_high=c['high_required'],
                observed_high_at_entry=state['peak'],required_close=c['close_required'],observed_close_at_entry=state['best_close'],
                first_HL_P1_confirmation_ny=local(ts(known)) if known else None))
    assert all(sha(p)==h for p,h in protected.items());verify_rules();after=CONTROLLER.status()
    assert before['pid']==after['pid'] and before['session']['id']==after['session']['id'] and not after['orders_enabled']
    save(OUT/'PRESERVATION.json',dict(files={str(p.relative_to(ROOT)):h for p,h in protected.items()},
        live_pid=after['pid'],live_session=after['session']['id'],health=after['health'],quote_fresh=after['quote_fresh'],
        rules_changed=False,monthly_replay=False,orders_enabled=False))
    for row in result['cases']:
        c=row['checks']['hl'];state=c['at_original_entry']
        print(json.dumps(dict(case=row['label'],entry=row['entry_ny'],parent=row['parent_gate_passes'],HL=row['HL_gate_passes'],
            status=state['status'],holds=state['holds'],atr=c['atr_before_low'],peak=state['peak'],close=state['best_close'],
            first_qualified_at=c['first_qualified_at']),ensure_ascii=False))
    return result


if __name__=='__main__':run()
