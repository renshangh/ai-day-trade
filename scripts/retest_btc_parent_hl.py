"""Validate Nov 9 C setup first, then replay unchanged P1 controls plus C."""
from __future__ import annotations
import copy
from datetime import datetime,timezone,timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_live import LIVE,verify_rules
from trading_desk.btc_parent_hl import C_RULE,ContinuationBaselineReplay,ContinuationEarlyReplay
from trading_desk.btc_p1 import P1BaselineReplay,P1EarlyReplay
from scripts.btc_structure_retest import Config
from scripts.retest_btc_e1_e2_sequential import summarize
from scripts.retest_btc_p1_30d import changes
from trading_desk.btc_engine import export_csv,aggregate


def make_engine(model,start,end,db,continuation):
    cls=(ContinuationBaselineReplay if continuation else P1BaselineReplay) if model=='0.1' else (
        ContinuationEarlyReplay if continuation else P1EarlyReplay)
    kwargs=dict(expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
    if model!='0.1':kwargs['early_policy']=model
    return cls(start,end,db,Config(version='P1+C-'+model,first_sale_fraction=.25,resistance_mode='major1h'),**kwargs)


def case_first():
    session=read(LIVE/'SESSION.json')
    source=LIVE/'sessions'/session['id']/'observations.sqlite'
    cutoff=ts('2026-11-09T08:18:00Z')
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        rows=[json.loads(x) for x, in db.execute('SELECT body FROM minutes WHERE t<? ORDER BY t',(cutoff,))]
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=make_engine('0.1',ts('2026-11-09T08:15:00Z'),cutoff,db,True)
    trace=[]
    for b in rows:
        e.minute(b)
        if b['t']>=ts('2026-11-09T08:14:00Z'):
            setup=e.parent_hl.ready(e.atr)
            trace.append(dict(time=iso(b['t']),armed=bool(setup),setup=setup))
    candidates=[s for s in e.signals if s['route']=='C']
    signal=next((s for s in candidates if s['time_utc']=='2026-11-09T08:17:00Z'),None)
    assert signal is not None,'C detector did not identify the requested case; no parameters adjusted'
    assert signal['qualified_candidate'],signal
    assert signal['setup_evidence']['parent']['price']==73530.0885
    assert signal['setup_evidence']['hl']['price']==73629.551
    assert abs(signal['entry_reference']-73867.005)<1e-8
    assert not trace[0]['armed'] and trace[1]['armed']
    assert max(p['known_at'] for p in signal['setup_evidence'].values() if isinstance(p,dict))<=ts(signal['time_utc'])
    # Strict prefix and a second isolated run must reproduce the exact record;
    # no HH from 04:02 or any later rally is supplied to the case test.
    other_db=sqlite3.connect(':memory:');other_db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    other=make_engine('0.1',ts('2026-11-09T08:15:00Z'),cutoff,other_db,True)
    for b in rows:other.minute(b)
    assert next(s for s in other.signals if s['route']=='C' and s['time_utc']==signal['time_utc'])==signal
    context=[]
    for t in range(ts('2026-11-09T07:00:00Z'),cutoff,900):
        obs=[b for b in rows if t<=b['t']<t+900]
        if obs:context.append(aggregate(obs,900))
    result=dict(status='passed',signal=copy.deepcopy(signal),trace=trace,bars=context,
        source_session=session['id'],source_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
        activation='2026-11-09T08:15:00Z',cutoff=iso(cutoff),
        isolated_case=True,full_nov9_portfolio=False,known_no_earlier_than=signal['interval_end'],
        existing_priority_position={k:copy.deepcopy(e.position.get(k)) for k in ('entry_rule','entry_time','entry')} if e.position else None,
        note='Isolated flat-at-03:15 case. C is recorded even when an existing A/B candidate has entry priority. Not an assertion that the entire earlier Nov 9 portfolio would be flat. No later HH/HL data used; minute reference is observable only after 03:18 plus delivery.',
        nearer_hl_diagnostic=dict(level=74446.3365,first_break='2026-11-09T18:22:00Z',
            active_risk_change=False,note='Live trade #1 breaks its nearer entry HL in the 13:15 candle, but the recorded larger D/hard stop are not breached. Parent D remains the chosen stop basis.'))
    db.close();other_db.close();return result


def execute(model,original,rows,folder,ident,continuation):
    folder.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=make_engine(model,ts(original['start']),ts(original['end']),db,continuation)
    try:
        for i,b in enumerate(rows,1):
            e.minute(b)
            if i%10000==0:
                db.commit();print(json.dumps(dict(model=model,C=continuation,processed=i,time=iso(b['t']))),flush=True)
        r=e.finish();db.commit()
        if not continuation:
            assert len(r['trades'])==len(original['trades'])
            for a,b in zip(r['trades'],original['trades'],strict=True):
                for k in ('entry_time','entry','entry_rule','initial_stop','t1','t2','legs','status','remaining'):
                    assert a[k]==b[k],(model,b['id'],k)
            assert r['metrics']==original['metrics'];return r
        for k in ('start','end','warmup_start','days','source','source_minute_sha256','minute_count',
            'test_data_quality','cost_model','draft_parameters','entry_mode','expanded_b'):
            r[k]=copy.deepcopy(original[k])
        r.update(run_id=folder.name,status='complete',study_id=ident,strategy_version='P1+C-'+model,
            research_policy='P1+C-'+model,source_frozen_release='0.2',control_model=model)
        r['draft_parameters']['parent_HL_C']=copy.deepcopy(C_RULE)
        export_csv(folder,r,db);save(folder/'result.json',r);return r
    finally:db.close()


def run():
    verify_rules()
    release=STORE/'releases/0.2';manifest=read(release/'MANIFEST.json')
    preserved={release/n:h for n,h in manifest['files_sha256'].items()}
    p1_id=read(STORE/'p1_studies/ACTIVE.json')['study_id'];p1=read(STORE/'p1_studies'/p1_id/'STUDY.json')
    for p in (STORE/'p1_studies'/p1_id).rglob('*'):
        if p.is_file():preserved[p]=hashlib.sha256(p.read_bytes()).hexdigest()
    for rid in p1['run_ids'].values():
        for p in (STORE/'runs'/rid).rglob('*'):
            if p.is_file():preserved[p]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p in (LIVE/'SESSION.json',LIVE/'CONTROL.json',STORE/'studies/ACTIVE.json'):
        preserved[p]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p in list((ROOT/'trading_desk').glob('btc_p1*'))+[ROOT/'scripts/retest_btc_p1_30d.py',STORE/'p1_studies/ACTIVE.json']:
        if p.is_file():preserved[p]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p,h in preserved.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==h,str(p)
    case=case_first();print(json.dumps(dict(case='passed',time=case['signal']['time_utc'],decision=case['signal']['decision'],signal=case['signal']['qualified_candidate'])),flush=True)
    now=datetime.now(timezone.utc);ident=now.strftime('%Y%m%dT%H%M%SZ')+'-parent-HL'
    folder=STORE/'parent_hl_studies'/ident;folder.mkdir(parents=True,exist_ok=False)
    save(folder/'CASE_NOV09.json',case)
    rows=[];digest=hashlib.sha256()
    with gzip.open(release/'data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            digest.update(line);t,o,h,l,c,v,n,vw=json.loads(line)
            rows.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    assert digest.hexdigest()==p1['source_minute_sha256']
    s=dict(study_id=ident,status='running',start=p1['start'],end=p1['end'],warmup_start=p1['warmup_start'],
        source_minute_sha256=digest.hexdigest(),source_quality=p1['source_quality'],control_p1_study=p1_id,
        control_run_ids=p1['run_ids'],run_ids={},summaries={},changes={},controls_reproduced={},
        continuation_rule=copy.deepcopy(C_RULE),orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',s)
    for i,model in enumerate(('0.1','E1','E2')):
        original=read(STORE/'runs'/p1['run_ids'][model]/'result.json')
        execute(model,original,rows,folder/('control-'+model),ident,False);s['controls_reproduced'][model]=True
        n=now+timedelta(seconds=i)
        while (STORE/'runs'/(n.strftime('%Y%m%dT%H%M%SZ')+'-30-ab')).exists():n+=timedelta(seconds=3)
        rid=n.strftime('%Y%m%dT%H%M%SZ')+'-30-ab'
        new=execute(model,original,rows,STORE/'runs'/rid,ident,True)
        s['run_ids'][model]=rid
        s['summaries'][model]=dict(frozen=p1['summaries'][model]['frozen'],control=summarize(original),variant=summarize(new))
        s['changes'][model]=[dict(status=c['status'],control=c['original'],variant=c['p1'],delta=c['delta']) for c in changes(original,new)]
        save(folder/'STUDY.json',s)
    for p,h in preserved.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==h,str(p)
    verify_rules();s.update(status='complete',preserved_files=len(preserved),code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'trading_desk/btc_parent_hl.py',Path(__file__))})
    save(folder/'STUDY.json',s);save(STORE/'parent_hl_studies/ACTIVE.json',dict(study_id=ident))
    print(json.dumps(dict(study_id=ident,summaries=s['summaries']),indent=2));return s


if __name__=='__main__':run()
