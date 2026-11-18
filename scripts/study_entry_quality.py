"""Entry-pattern learning on original BTC/SOL, independent saved comparison."""
from __future__ import annotations
import copy,gzip,json,sqlite3,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,iso,ts
from trading_desk.crypto_transfer import STUDIES as SOURCES,make_engine,protected_state,sha,enrich,summarize,csv_table
from trading_desk.refined_entry_view import BOOKS
from trading_desk.adaptive_shock import Contexts
from trading_desk.entry_quality import PROTOCOL,FEATURES,features,fit,predict,metrics,FilterBaseline,FilterEarly
from trading_desk.btc_engine import export_csv
from trading_desk.btc_live import verify_rules
from trading_desk.sol_live import snapshot
from scripts.btc_structure_retest import Config
from scripts.retest_refined_entries import signature,compare
STUDIES=STORE/'entry_quality_studies'


def record(symbol,p,s,market,start,train_end,test_start,end):
    feature,reason=features(symbol,s,market);entry=ts(p['entry_time']);exit=ts(p['exit_time']) if p.get('exit_time') else end
    phase='train' if entry<train_end else 'validation' if entry<test_start else 'test';boundary=train_end if phase=='train' else test_start if phase=='validation' else end
    # Exit labels cannot be known before their observed minute completes.
    label_time=exit+60
    flagged=bool(p['gap_exposed'] or p['context_partial']);resolved=p['status']=='closed' and label_time<boundary
    return dict(key=symbol+'|'+p['entry_time'],symbol=symbol,trade_id=p['id'],route=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],
        stop=p['initial_stop'],target=p['t1'],exit_time=p.get('exit_time'),legs=p['legs'],net=p.get('net'),normalized_net=p['normalized_10000_realized_net'],
        label=(int(p['net']>0) if p['status']=='closed' and p.get('net') is not None else None),
        label_known_at=iso(label_time) if p.get('exit_time') else None,phase=phase,phase_label_resolved=resolved,
        training_eligible=phase=='train' and resolved and not flagged and feature is not None,
        quality_group='flagged_gap_or_context' if flagged else 'no_flagged_gap',feature=feature,feature_unavailable_reason=reason)


def score_rows(rows,model):
    out=copy.deepcopy(rows)
    for r in out:
        r['probability']=predict(model,r['feature']);r['accepted']=r['probability'] is None or r['probability']>=.5
        r['baseline_probability']=model.get('baseline',{}).get(r['symbol']);r['abstained']=r['probability'] is None
    return out


def replay(symbol,model,bars,quality,market,start,end,folder=None,quality_model=None,expected=None):
    if folder:folder.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(':memory:' if folder is None else folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    if quality_model is None:engine=make_engine(model,start,end,db)
    else:
        cls=FilterBaseline if model=='0.1' else FilterEarly
        cfg=Config(version='Alpaca-BTC-AB-profit-guard-failed-rebound-draft-8',first_sale_fraction=.25,resistance_mode='major1h') if model=='0.1' else Config(first_sale_fraction=.25,resistance_mode='major1h')
        args={} if model=='0.1' else dict(early_policy=model)
        engine=cls(start,end,db,cfg,expanded_b=True,consume_entry_history=True,b1_independent_hold=False,
            quality_model=quality_model,quality_symbol=symbol,quality_market=market,**args)
    try:
        for b in bars:
            if start-7*86400<=b['t']<end:engine.minute(b)
        result=engine.finish();db.commit()
        if expected:
            assert len(result['trades'])==len(expected['trades'])
            for p,q in zip(result['trades'],expected['trades'],strict=True):
                want=signature(q);want['legs']=[{k:v for k,v in l.items() if k!='normalized_10000_net'} for l in q['legs']]
                assert signature(p)==want and p['entry_time']==q['entry_time'] and p['entry_rule']==q['entry_rule'],(symbol,model,p['id'])
            assert result['metrics']==expected['metrics']
        result.update(symbol=symbol,model=model,start=iso(start),end=iso(end),status='complete',last_price=engine.last_price,
            policy=dict(entry_quality=PROTOCOL if quality_model else 'unfiltered original frozen entries',risk_exits='Original unchanged'),
            source_quality=quality,orders_enabled=False,live_promoted=False)
        enrich(result,symbol,model,quality);result['summary']=summarize(result)
        if folder:export_csv(folder,result,db);save(folder/'result.json',result)
        return result
    finally:db.close()


def run():
    source=SOURCES/read(SOURCES/'ACTIVE.json')['study_id'];src=read(source/'STUDY.json');start=ts(src['start']);end=ts(src['end']);train_end=start+14*86400;test_start=start+21*86400
    files,_=protected_state();before=snapshot();workers={k:dict(pid=before[k]['pid'],session=before[k]['session']['id']) for k in ('btc','sol')}
    for parent in ('adaptive_shock_studies','followthrough_shock_studies','refined_entry_studies'):
        home=STORE/parent;selector=home/'ACTIVE.json';files[str(selector.relative_to(ROOT))]=sha(selector)
        for p in (home/read(selector)['study_id']).rglob('*'):
            if p.is_file():files[str(p.relative_to(ROOT))]=sha(p)
    for name in ('trading_desk/btc_live.py','trading_desk/sol_live.py','scripts/run_btc_live.py','scripts/run_sol_live.py','trading_desk/adaptive_shock.py','scripts/study_adaptive_shock.py','trading_desk/refined_entries.py','trading_desk/steeper_shock_research.py'):
        files[name]=sha(ROOT/name)
    for p in (SOURCES/'ACTIVE.json',source/'STUDY.json'):
        files[str(p.relative_to(ROOT))]=sha(p)
    code={p:sha(ROOT/p) for p in ('trading_desk/entry_quality.py','scripts/study_entry_quality.py')}
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-entry-quality';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',protocol=PROTOCOL,source_study=str(source.relative_to(ROOT)),start=iso(start),end=iso(end),train_end=iso(train_end),test_start=iso(test_start),
        code_hashes=code,rule_hashes=verify_rules(),workers=workers,books=[],controls_reproduced={},abstention_controls_reproduced={},source_quality=src['source_quality'],orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files)
    save(folder/'SOURCE_BUNDLE.json',{p:(ROOT/p).read_text() for p in code})
    inputs={};markets={};original={}
    for symbol in ('BTC/USD','SOL/USD'):
        p=source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz');assert sha(p)==src['source_quality'][symbol]['archive_sha256'];files[str(p.relative_to(ROOT))]=sha(p)
        with gzip.open(p,'rt') as f:inputs[symbol]=[json.loads(x) for x in f]
        markets[symbol]=Contexts(inputs[symbol])
    for symbol,model in BOOKS:
        p=source/symbol.replace('/','_')/model/'result.json';original[symbol,model]=read(p);files[str(p.relative_to(ROOT))]=sha(p)
    dataset=[]
    for symbol in ('BTC/USD','SOL/USD'):
        r=original[symbol,'E1'];signals={x['id']:x for x in r['signals']}
        dataset.extend(record(symbol,p,signals[p['signal_id']],markets[symbol],start,train_end,test_start,end) for p in r['trades'])
    assert len({r['key'] for r in dataset})==len(dataset)
    # Training and preprocessing see eligible resolved first-period labels only.
    model=fit(dataset,train_end);save(folder/'MODEL_BEFORE_VALIDATION_TEST.json',model)
    dataset=score_rows(dataset,model);save(folder/'DATASET.json',dataset)
    patterns=[]
    for symbol in ('BTC/USD','SOL/USD'):
        rows=[r for r in dataset if r['symbol']==symbol and r['training_eligible']]
        for name in FEATURES:
            wins=[r['feature']['values'][name] for r in rows if r['label']==1];losses=[r['feature']['values'][name] for r in rows if r['label']==0]
            patterns.append(dict(symbol=symbol,feature=name,train_winners=len(wins),train_losers=len(losses),
                winning_mean=float(np.mean(wins)) if wins else None,losing_mean=float(np.mean(losses)) if losses else None))
    save(folder/'PATTERNS.json',dict(pooled=model.get('patterns',[]),by_asset=patterns))
    study['model_summary']={k:v for k,v in model.items() if k not in ('mean','std','weights','training_keys','patterns')}
    study['prediction_metrics']={}
    for phase in ('train','validation','test'):
        study['prediction_metrics'][phase]={}
        for symbol in ('all','BTC/USD','SOL/USD'):
            rows=[r for r in dataset if r['phase']==phase and (symbol=='all' or r['symbol']==symbol) and r['phase_label_resolved']]
            study['prediction_metrics'][phase][symbol]=metrics(rows)
    summary_csv=[];decision_csv=[];fixed_csv=[]
    for symbol,variant in BOOKS:
        bfolder=folder/symbol.replace('/','_')/variant;quality=src['source_quality'][symbol];bfolder.mkdir(parents=True)
        replay(symbol,variant,inputs[symbol],quality,markets[symbol],start,end,bfolder/'full_control',expected=original[symbol,variant]);study['controls_reproduced'][symbol+' '+variant]=True
        r=original[symbol,variant];signals={x['id']:x for x in r['signals']}
        fixed=score_rows([record(symbol,p,signals[p['signal_id']],markets[symbol],start,train_end,test_start,end) for p in r['trades']],model);save(bfolder/'FIXED_ENTRIES.json',fixed)
        phase_metrics={}
        for phase in ('train','validation','test'):
            rows=[x for x in fixed if x['phase']==phase and x['phase_label_resolved']];phase_metrics[phase]=metrics(rows)
            fixed_csv.extend({k:x[k] for k in ('key','symbol','trade_id','route','entry_time','entry','exit_time','net','normalized_net','label','phase','quality_group','probability','accepted','abstained')} for x in rows)
        control=replay(symbol,variant,inputs[symbol],quality,markets[symbol],test_start,end,bfolder/'test_control')
        replay(symbol,variant,inputs[symbol],quality,markets[symbol],test_start,end,quality_model={'available':False},expected=control);study['abstention_controls_reproduced'][symbol+' '+variant]=True
        filtered=replay(symbol,variant,inputs[symbol],quality,markets[symbol],test_start,end,bfolder/'test_filtered',quality_model=model)
        changes=compare(control,filtered);save(bfolder/'SEQUENTIAL_CHANGES.json',changes)
        decisions=filtered['entry_quality_decisions'];csv_table(bfolder/'DECISIONS.csv',[{k:d[k] for k in ('signal_id','time_utc','route','reference','probability','accepted','abstained','reason')} for d in decisions])
        decision_csv.extend(dict(symbol=symbol,model=variant,**{k:d[k] for k in ('signal_id','time_utc','route','reference','probability','accepted','abstained','reason')}) for d in decisions)
        book=dict(symbol=symbol,model=variant,fixed=phase_metrics,control=control['summary'],filtered=filtered['summary'],
            decisions=dict(scored=sum(d['probability'] is not None for d in decisions),rejected=sum(not d['accepted'] for d in decisions),abstained=sum(d['abstained'] for d in decisions)),
            sequence_change_counts={n:sum(c['status']==n for c in changes) for n in ('unchanged','relabelled_only','changed','removed','added')})
        for name,result in [('control',control),('filtered',filtered)]:
            for group in ('all','no_flagged_gap','flagged_gap_or_context'):summary_csv.append(dict(symbol=symbol,model=variant,sequence=name,group=group,**result['summary'][group]))
        study['books'].append(book);save(folder/'STUDY.json',study);print(json.dumps(book),flush=True)
    csv_table(folder/'SUMMARY.csv',summary_csv);csv_table(folder/'FIXED_ENTRIES.csv',fixed_csv);csv_table(folder/'DECISIONS.csv',decision_csv)
    save(folder/'PRESERVED_BEFORE.json',files)
    for p,h in {**files,**code}.items():assert sha(ROOT/p)==h,p
    assert verify_rules()==study['rule_hashes'];after=snapshot()
    for k,v in workers.items():assert dict(pid=after[k]['pid'],session=after[k]['session']['id'])==v
    study.update(status='complete',preserved_files=len(files));save(folder/'STUDY.json',study);save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)

if __name__=='__main__':run()
