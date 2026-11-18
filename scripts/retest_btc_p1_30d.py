"""Same frozen 0.2 stream: P1 A entries only, full 0.1/E1/E2 sequences."""
from __future__ import annotations

import copy
import csv
from datetime import datetime,timezone,timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import create_replay,export_csv
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_live import verify_rules
from trading_desk.btc_p1 import P1BaselineReplay,P1EarlyReplay,P1_RULE
from scripts.btc_structure_retest import Config
from scripts.retest_btc_e1_e2_sequential import summarize


def changes(old,new):
    key=lambda p:(p['entry_time'],p['entry_rule'])
    before={key(p):p for p in old['trades']};after={key(p):p for p in new['trades']}
    def compact(p):
        return {k:copy.deepcopy(p.get(k)) for k in ('id','entry_time','entry_rule','entry',
            'initial_stop','t1','exit_time','legs','net','gap_exposed','context_partial')}
    rows=[]
    for k in sorted(before.keys()|after.keys()):
        a=before.get(k);b=after.get(k)
        same=bool(a and b and all(a.get(f)==b.get(f) for f in
            ('entry','initial_stop','t1','t2','legs','status','remaining')))
        rows.append(dict(status='unchanged' if same else 'changed' if a and b else
            'removed' if a else 'added',original=compact(a) if a else None,
            p1=compact(b) if b else None,
            delta=(b['net'] if b and b['net'] is not None else 0)-
                  (a['net'] if a and a['net'] is not None else 0)))
    return rows


def execute(model,original,minutes,folder,study_id,*,p1):
    folder.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(folder/'ledger.sqlite')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    cfg=Config(version='P1-A-only-'+model,first_sale_fraction=.25,resistance_mode='major1h')
    kwargs=dict(expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
    if model=='0.1':
        e=P1BaselineReplay(ts(original['start']),ts(original['end']),db,cfg,**kwargs) if p1 else create_replay(
            ts(original['start']),ts(original['end']),db,expanded_b=True,exit_version='failed_rebound')
    else:
        cls=P1EarlyReplay if p1 else EarlySequentialReplay
        e=cls(ts(original['start']),ts(original['end']),db,cfg,early_policy=model,**kwargs)
    try:
        for i,b in enumerate(minutes,1):
            e.minute(b)
            if i%10000==0:
                db.commit();print(json.dumps(dict(model=model,p1=p1,processed=i,time=iso(b['t']))),flush=True)
        result=e.finish();db.commit()
        if not p1:
            assert len(result['trades'])==len(original['trades'])
            for a,b in zip(result['trades'],original['trades'],strict=True):
                for k in ('entry_time','entry','entry_rule','initial_stop','t1','t2','legs','status','remaining'):
                    assert a[k]==b[k],(model,b['id'],k)
            assert result['metrics']==original['metrics']
            return result
        for key in ('start','end','warmup_start','days','source','source_minute_sha256','minute_count',
                    'test_data_quality','cost_model','draft_parameters','entry_mode','expanded_b'):
            result[key]=copy.deepcopy(original[key])
        result.update(run_id=folder.name,status='complete',study_id=study_id,
            strategy_version='P1-A-only-'+model,research_policy='P1-A-only-'+model,
            source_frozen_release='0.2',frozen_model=model,p1_rule=copy.deepcopy(P1_RULE))
        result['draft_parameters']['P1_A_only']=copy.deepcopy(P1_RULE)
        export_csv(folder,result,db);save(folder/'result.json',result)
        return result
    finally:db.close()


def run():
    release=STORE/'releases/0.2'
    manifest=read(release/'MANIFEST.json');before={}
    for name,want in manifest['files_sha256'].items():
        p=release/name;before[p]=hashlib.sha256(p.read_bytes()).hexdigest()
        assert before[p]==want,name
    verify_rules()
    ids=read(release/'REGISTRY.json')['0.2']['run_ids']
    originals={m:read(release/'results'/rid/'result.json') for m,rid in ids.items()}
    source=hashlib.sha256();minutes=[]
    with gzip.open(release/'data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            source.update(line);t,o,h,l,c,v,n,vw=json.loads(line)
            minutes.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    digest=source.hexdigest()
    assert all(digest==r['source_minute_sha256'] for r in originals.values())
    assert all(b['t']>a['t'] for a,b in zip(minutes,minutes[1:]))
    now=datetime.now(timezone.utc);ident=now.strftime('%Y%m%dT%H%M%SZ')+'-P1-A-sequential'
    folder=STORE/'p1_studies'/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',start=originals['0.1']['start'],end=originals['0.1']['end'],
        warmup_start=originals['0.1']['warmup_start'],source_minute_sha256=digest,
        source_quality=copy.deepcopy(originals['0.1']['test_data_quality']),
        baseline_run_ids=ids,run_ids={},summaries={},changes={},p1_rule=copy.deepcopy(P1_RULE),
        orders_enabled=False,live_promoted=False,baseline_reproduced={})
    save(folder/'STUDY.json',study)
    for index,model in enumerate(('0.1','E1','E2')):
        execute(model,originals[model],minutes,folder/('control-'+model),ident,p1=False)
        study['baseline_reproduced'][model]=True
        n=now+timedelta(seconds=index)
        while (STORE/'runs'/(n.strftime('%Y%m%dT%H%M%SZ')+'-30-ab')).exists():n+=timedelta(seconds=3)
        rid=n.strftime('%Y%m%dT%H%M%SZ')+'-30-ab'
        new=execute(model,originals[model],minutes,STORE/'runs'/rid,ident,p1=True)
        study['run_ids'][model]=rid
        study['summaries'][model]=dict(frozen=summarize(originals[model]),p1=summarize(new))
        study['changes'][model]=changes(originals[model],new)
        save(folder/'STUDY.json',study)
    for p,d in before.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==d,str(p)
    verify_rules();study['status']='complete';study['frozen_files_verified']=len(before)
    study['code_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT/'trading_desk/btc_p1.py',Path(__file__))}
    save(folder/'STUDY.json',study)
    # Independent research selection; never replaces frozen/current review,
    # original study pointers or the live session/control files.
    save(STORE/'p1_studies/ACTIVE.json',dict(study_id=ident))
    print(json.dumps(dict(study_id=ident,summaries=study['summaries']),indent=2))
    return study


if __name__=='__main__':run()
