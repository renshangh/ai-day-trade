"""Verify 03:20 first, then the identical month with retained parent context."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_live import LIVE
from trading_desk.btc_engine import export_csv
from trading_desk.btc_parent_memory import MEMORY_RULE,ParentMemoryBaseline,ParentMemoryEarly
from trading_desk.btc_parent_five_view import PARENT_FIVE_VIEW
from scripts.btc_structure_retest import Config
from scripts.retest_btc_parent_five import (
    engine as original_engine,database,preservation,verify_preserved,CASE_START,CASE_END,MODELS,
)
from scripts.retest_btc_e1_e2_sequential import summarize,sequence_changes

BASE=STORE/'parent_memory_studies'


def make_engine(model,start,end,db,sequence):
    if sequence=='original':return original_engine(model,start,end,db,'control')
    mode=sequence.split('_')[1]
    if sequence.startswith('cleared_'):return original_engine(model,start,end,db,mode)
    if sequence not in ('retained_combined','retained_standalone'):raise ValueError('Choose a comparison sequence')
    cls=ParentMemoryBaseline if model=='0.1' else ParentMemoryEarly
    kw=dict(expanded_b=True,consume_entry_history=True,b1_independent_hold=False,ph5_mode=mode)
    if model!='0.1':kw['early_policy']=model
    return cls(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),**kw)


def capture_case(engine,rows,receipts):
    snapshots=[]
    for b in rows:
        engine.minute(b)
        if b['t'] in (ts('2026-11-15T03:19:00-05:00'),ts('2026-11-15T03:20:00-05:00')):
            snapshots.append(dict(time=iso(b['t']),parent=copy.deepcopy(engine.ph5.parent),
                action_floor=getattr(engine.ph5,'action_floor',engine.ph5.floor),
                ready=copy.deepcopy(engine.ph5.ready(engine.atr)),
                consumed_tokens=sorted(engine.ph5_emitted),
                position_entry=engine.position['entry_time'] if engine.position else None))
    trades=copy.deepcopy(engine.trades+([engine.position] if engine.position else []))
    trades=[p for p in trades if ts(p['entry_time'])>=CASE_START]
    for p in trades:
        p['entry_received_at']=iso(receipts[ts(p['entry_time'])])
        for leg in p['legs']:leg['received_at']=iso(receipts[ts(leg['time_utc'])])
        if p['status']=='open':
            p['net']=None;p['mark_time']=iso(rows[-1]['t']);p['mark_price']=rows[-1]['close']
            p['realized_leg_net']=sum(l['net'] for l in p['legs'])
            p['unrealized_net']=p['remaining']*((p['mark_price']-p['entry'])-(p['mark_price']+p['entry'])*.0002)
            p['marked_net']=p['realized_leg_net']+p['unrealized_net']
    signals=[copy.deepcopy(s) for s in engine.signals if ts(s['time_utc'])>=CASE_START]
    for s in signals:s['received_at']=iso(receipts[ts(s['time_utc'])])
    ledger=[json.loads(body) for body, in engine.db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t',(CASE_START,))]
    return dict(trades=trades,signals=signals,trace=copy.deepcopy(engine.ph5_trace),bars=ledger,snapshots=snapshots,
        note='Historical observed prefix; no finish() or forced close. Entry availability is distinct from receipt. Not broker fills.')


def same_result(actual,expected,label):
    assert len(actual['trades'])==len(expected['trades']),label
    for a,b in zip(actual['trades'],expected['trades'],strict=True):
        for k in ('entry_time','entry','entry_rule','initial_stop','t1','t2','legs','status','remaining'):
            assert a[k]==b[k],(label,b['id'],k)
    assert actual['metrics']==expected['metrics'],label


def case_first(folder,old_folder):
    original=read(old_folder/'CASE.json');session=read(LIVE/'SESSION.json')
    source=LIVE/'sessions'/original['source_session']/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(CASE_END,)).fetchall()
    assert hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest()==original['source_sha256']
    rows=[json.loads(body) for body,_ in records]
    receipts={b['t']:r for b,(_,r) in zip(rows,records)}
    result=dict(start=iso(CASE_START),cutoff=iso(CASE_END),source_session=original['source_session'],
        source_sha256=original['source_sha256'],models={},orders_enabled=False,case_outside_month=True)
    target='2026-11-15T08:20:00Z'
    for model in MODELS:
        cleared=copy.deepcopy(original['models'][model])
        db=database();e=make_engine(model,session['start'],CASE_END,db,'retained_combined')
        e.ph5_active_from=CASE_START;e.ph5_trace_enabled=True
        retained=capture_case(e,rows,receipts)
        signal_0320=next((s for s in retained['signals'] if s['route']=='PH5' and s['time_utc']==target),None)
        assert signal_0320 and signal_0320['qualified_candidate'],(model,'03:20 structure not qualified; no tuning allowed')
        assert signal_0320['decision'] in ('entry','held_position')
        assert signal_0320['entry_reference']==63948.515
        assert signal_0320['references']['l1']['price']==61991.3285
        assert signal_0320['references']['l2']['price']==63735.105
        old=next(p for p in cleared['trades'] if p['entry_rule']=='PH5')
        first=next(p for p in retained['trades'] if p['entry_time']==old['entry_time'])
        for k in ('entry','initial_stop','t1','t2','net'):assert first[k]==old[k],(model,k)
        assert [{k:v for k,v in l.items() if k!='received_at'} for l in first['legs']]==[
            {k:v for k,v in l.items() if k!='received_at'} for l in old['legs']]
        # Independent strict prefix through the triggering minute must reproduce
        # the exact candidate before supplying any later upswing or exit data.
        pdb=database();prefix=make_engine(model,session['start'],CASE_END,pdb,'retained_combined')
        prefix.ph5_active_from=CASE_START
        for b in rows:
            if b['t']>ts(target):break
            prefix.minute(b)
        short=next(s for s in prefix.signals if s['route']=='PH5' and s['time_utc']==target)
        for k in ('entry_reference','initial_stop','t1','t2','decision','setup_evidence','hold_bar'):
            assert short[k]==signal_0320[k],(model,k)
        assert prefix.position
        if signal_0320['decision']=='held_position':
            assert prefix.position['entry_time']<target
        else:assert prefix.position['entry_time']==target
        result['models'][model]=dict(cleared=cleared,retained=retained,
            reentry=copy.deepcopy(signal_0320),prefix_verified=True,first_exit_unchanged=True,
            position_at_0320={k:copy.deepcopy(prefix.position[k]) for k in
                ('id','entry_time','entry_rule','entry','initial_stop','t1','remaining')})
        db.close();pdb.close()
        print(json.dumps(dict(stage='case_passed',model=model,reentry=target,
            price=signal_0320['entry_reference'],stop=signal_0320['initial_stop'],
            decision=signal_0320['decision'],held_entry=prefix.position['entry_time'])),flush=True)
    save(folder/'CASE.json',result)
    return result


def execute(model,sequence,expected,rows,folder):
    folder.mkdir(parents=True,exist_ok=False)
    db=database(folder/'ledger.sqlite')
    e=make_engine(model,ts(expected['start']),ts(expected['end']),db,sequence)
    try:
        for i,b in enumerate(rows,1):
            e.minute(b)
            if i%20000==0:
                db.commit();print(json.dumps(dict(stage='month',model=model,sequence=sequence,processed=i)),flush=True)
        r=e.finish();db.commit()
        if not sequence.startswith('retained_'):same_result(r,expected,model+'/'+sequence)
        for k in ('start','end','warmup_start','days','source','source_minute_sha256','minute_count',
                  'test_data_quality','cost_model','draft_parameters','entry_mode','expanded_b'):
            r[k]=copy.deepcopy(expected[k])
        r.update(status='complete',control_model=model,sequence=sequence,orders_enabled=False,live_promoted=False,
            source_frozen_release='0.2',parent_memory_comparison=sequence.startswith('retained_'))
        export_csv(folder,r,db);save(folder/'result.json',r)
        return r
    finally:db.close()


def run(case_only=False):
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('20 minute research limit')))
    signal.alarm(1200)
    before=preservation()
    old_folder,old_study=PARENT_FIVE_VIEW.current()
    extra=[p for p in old_folder.rglob('*') if p.is_file()]
    extra += [old_folder.parent/'ACTIVE.json',ROOT/'trading_desk/btc_parent_five.py',
        ROOT/'scripts/retest_btc_parent_five.py',ROOT/'scripts/audit_btc_ph5_exit_reentry.py']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in extra}
    ident=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-PH5-memory'
    folder=BASE/ident;folder.mkdir(parents=True,exist_ok=False)
    save(folder/'PRESERVED.json',dict(original=before,PH5_files=hashes))
    save(folder/'LOCKED_RULE.json',MEMORY_RULE)
    case_first(folder,old_folder)
    if case_only:
        for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
        save(folder/'PRESERVATION_CHECK.json',verify_preserved(before));print(folder);return
    release=STORE/'releases/0.2';registry=read(release/'REGISTRY.json')['0.2']
    rows=[];digest=hashlib.sha256()
    with gzip.open(release/'data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            digest.update(line);t,o,h,l,c,v,n,_=json.loads(line)
            rows.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    assert digest.hexdigest()==old_study['source_minute_sha256']
    s=dict(study_id=ident,status='running',start=old_study['start'],end=old_study['end'],
        warmup_start=old_study['warmup_start'],source_minute_sha256=digest.hexdigest(),
        source_quality=old_study['source_quality'],rule=MEMORY_RULE,
        original_PH5_study=old_study['study_id'],summaries={},changes={},controls_reproduced={},
        orders_enabled=False,live_promoted=False,case_outside_month=True,
        measure=old_study['measure'])
    save(folder/'STUDY.json',s)
    for model in MODELS:
        frozen=read(release/'results'/registry['run_ids'][model]/'result.json')
        old={mode:read(old_folder/model/mode/'result.json') for mode in ('combined','standalone')}
        expected={'original':frozen,'cleared_combined':old['combined'],'cleared_standalone':old['standalone']}
        results={}
        for sequence,original in expected.items():
            results[sequence]=execute(model,sequence,original,rows,folder/model/sequence)
        s['controls_reproduced'][model]=dict(original=True,cleared_combined=True,cleared_standalone=True)
        for mode in ('combined','standalone'):
            sequence='retained_'+mode
            results[sequence]=execute(model,sequence,old[mode],rows,folder/model/sequence)
        s['summaries'][model]={name:summarize(r) for name,r in results.items()}
        s['changes'][model]={}
        for mode in ('combined','standalone'):
            name='retained_'+mode;r=results[name]
            s['changes'][model][name]=dict(vs_cleared=sequence_changes(old[mode],r),vs_original=sequence_changes(frozen,r))
            s['summaries'][model][name]['ph5_only']=summarize(dict(trades=[p for p in r['trades'] if p['entry_rule']=='PH5']))
        save(folder/'STUDY.json',s)
    for p,h in hashes.items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h,p
    s.update(status='complete',preservation=verify_preserved(before),PH5_preserved_files=len(hashes),
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__),ROOT/'trading_desk/btc_parent_memory.py')})
    save(folder/'STUDY.json',s);save(BASE/'ACTIVE.json',dict(study_id=ident))
    print(json.dumps(dict(study_id=ident,summaries=s['summaries'],preservation=s['preservation']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case-only',action='store_true');run(p.parse_args().case_only)
