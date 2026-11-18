"""Native VWAP and moving-average ML ablation; no live changes or orders."""
from __future__ import annotations
import copy,gzip,hashlib,json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,iso,ts
from trading_desk.crypto_transfer import STUDIES as SOURCES,protected_state,sha,enrich,summarize,csv_table
from trading_desk.entry_quality_view import VIEW as PREVIOUS
from trading_desk.refined_entry_view import BOOKS
from trading_desk.adaptive_shock import Contexts
from trading_desk.entry_quality import metrics
from trading_desk.entry_indicator_ml import PROTOCOL,ARMS,Indicators,names,fit,predict,IndicatorBaseline,IndicatorEarly
from trading_desk.btc_engine import export_csv
from trading_desk.btc_live import verify_rules
from trading_desk.sol_live import snapshot
from scripts.btc_structure_retest import Config
from scripts.study_entry_quality import record,replay as control_replay
from scripts.retest_refined_entries import signature,compare
STUDIES=STORE/'entry_indicator_studies'


def load_native(source,inputs):
    native={k:{} for k in inputs};files={};expected={k:{b['t']:b for b in v} for k,v in inputs.items()};audits={}
    def include(symbol,t,o,h,l,c,v,n,vw):
        b=expected[symbol].get(t)
        if b is None:return
        if any(b[k]!=x for k,x in zip(('open','high','low','close','volume','n'),(o,h,l,c,v,n))):raise ValueError('Native VWAP archive disagrees with original OHLCV; no mixed observations')
        if t in native[symbol] and native[symbol][t]!=vw:raise ValueError('Conflicting native VWAP records')
        native[symbol][t]=vw
    p=STORE/'releases/0.2/data/MINUTES.jsonl.gz';files[str(p.relative_to(ROOT))]=sha(p)
    with gzip.open(p,'rt') as z:
        for line in z:
            t,o,h,l,c,v,n,vw=json.loads(line);include('BTC/USD',t,o,h,l,c,v,n,vw)
    p=source/'data/SOURCES.json';manifest=read(p);files[str(p.relative_to(ROOT))]=sha(p)
    for page in manifest['pages']:
        path=(source/'data'/page['file']).resolve()
        if not path.is_relative_to((source/'data/raw').resolve()):raise ValueError('Invalid raw page path')
        files[str(path.relative_to(ROOT))]=sha(path);raw=gzip.decompress(path.read_bytes())
        if hashlib.sha256(raw).hexdigest()!=page['raw_sha256']:raise ValueError('Raw provider response hash mismatch')
        for b in json.loads(raw).get('bars',{}).get('SOL/USD',[]):include('SOL/USD',ts(b['t']),b['o'],b['h'],b['l'],b['c'],b['v'],b['n'],b.get('vw'))
    for symbol,bars in inputs.items():
        positive=[b for b in bars if b['volume']>0]
        audits[symbol]=dict(observed_minutes=len(bars),native_rows_matched=len(native[symbol]),positive_volume_minutes=len(positive),
            positive_missing_native=sum(native[symbol].get(b['t']) is None or native[symbol].get(b['t'],0)<=0 for b in positive),
            zero_volume_minutes=sum(b['volume']==0 for b in bars),source='Original raw provider minute VWAP matched against unchanged original OHLCV')
    return native,audits,files


def dataset_for(symbol,result,indicators,arm,start,train_end,test_start,end):
    signals={x['id']:x for x in result['signals']};rows=[]
    for p in result['trades']:
        s=signals[p['signal_id']];r=record(symbol,p,s,indicators.market,start,train_end,test_start,end)
        feature,reason=indicators.feature(symbol,s,arm);r.update(feature=feature,feature_unavailable_reason=reason,arm=arm)
        r['training_eligible']=r['training_eligible'] and feature is not None;rows.append(r)
    return rows


def score(rows,model):
    out=copy.deepcopy(rows)
    for r in out:
        p=predict(model,r['feature']);r.update(probability=p,accepted=p is None or p>=.5,abstained=p is None,baseline_probability=model.get('baseline',{}).get(r['symbol']))
    return out


def replay(symbol,variant,bars,quality,indicators,start,end,folder,arm,model,expected=None):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    cls=IndicatorBaseline if variant=='0.1' else IndicatorEarly
    cfg=Config(version='Alpaca-BTC-AB-profit-guard-failed-rebound-draft-8',first_sale_fraction=.25,resistance_mode='major1h') if variant=='0.1' else Config(first_sale_fraction=.25,resistance_mode='major1h')
    args={} if variant=='0.1' else dict(early_policy=variant)
    e=cls(start,end,db,cfg,expanded_b=True,consume_entry_history=True,b1_independent_hold=False,
        indicator_model=model,indicator_symbol=symbol,indicators=indicators,feature_arm=arm,**args)
    try:
        for b in bars:
            if start-7*86400<=b['t']<end:e.minute(b)
        r=e.finish();db.commit()
        if expected:
            assert len(r['trades'])==len(expected['trades'])
            for p,q in zip(r['trades'],expected['trades'],strict=True):
                want=signature(q);want['legs']=[{k:v for k,v in l.items() if k!='normalized_10000_net'} for l in q['legs']]
                assert signature(p)==want and p['entry_time']==q['entry_time'] and p['entry_rule']==q['entry_rule']
            assert r['metrics']==expected['metrics']
        r.update(symbol=symbol,model=variant,arm=arm,start=iso(start),end=iso(end),status='complete',last_price=e.last_price,
            policy=PROTOCOL,source_quality=quality,orders_enabled=False,live_promoted=False)
        enrich(r,symbol,variant,quality);r['summary']=summarize(r);export_csv(folder,r,db);save(folder/'result.json',r);return r
    finally:db.close()


def run():
    source=SOURCES/read(SOURCES/'ACTIVE.json')['study_id'];src=read(source/'STUDY.json');previous,prior=PREVIOUS.current()
    start=ts(src['start']);end=ts(src['end']);train_end=start+14*86400;test_start=start+21*86400
    files,_=protected_state();state=snapshot();workers={k:dict(pid=state[k]['pid'],session=state[k]['session']['id']) for k in ('btc','sol')}
    for parent in ('entry_quality_studies','adaptive_shock_studies','followthrough_shock_studies','refined_entry_studies'):
        home=STORE/parent;p=home/'ACTIVE.json';files[str(p.relative_to(ROOT))]=sha(p)
        for p in (home/read(p)['study_id']).rglob('*'):
            if p.is_file():files[str(p.relative_to(ROOT))]=sha(p)
    for p in ('trading_desk/btc_live.py','trading_desk/sol_live.py','scripts/run_btc_live.py','scripts/run_sol_live.py','trading_desk/entry_quality.py','scripts/study_entry_quality.py'):
        files[p]=sha(ROOT/p)
    for p in (SOURCES/'ACTIVE.json',source/'STUDY.json'):files[str(p.relative_to(ROOT))]=sha(p)
    code={p:sha(ROOT/p) for p in ('trading_desk/entry_indicator_ml.py','scripts/study_entry_indicators.py')}
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-entry-indicators';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',protocol=PROTOCOL,start=iso(start),end=iso(end),train_end=iso(train_end),test_start=iso(test_start),
        source_study=str(source.relative_to(ROOT)),previous_study=str(previous.relative_to(ROOT)),code_hashes=code,rule_hashes=verify_rules(),workers=workers,
        books=[],model_summaries={},prediction_metrics={},controls_reproduced={},original_ml_reproduced={},source_quality=src['source_quality'],orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files);save(folder/'SOURCE_BUNDLE.json',{p:(ROOT/p).read_text() for p in code})
    inputs={};original={}
    for symbol in ('BTC/USD','SOL/USD'):
        p=source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz');assert sha(p)==src['source_quality'][symbol]['archive_sha256'];files[str(p.relative_to(ROOT))]=sha(p)
        with gzip.open(p,'rt') as z:inputs[symbol]=[json.loads(l) for l in z]
    native,audit,native_files=load_native(source,inputs);files.update(native_files);save(folder/'VWAP_SOURCE_AUDIT.json',audit);study['vwap_sources']=audit
    indicators={symbol:Indicators(Contexts(bars),bars,native[symbol]) for symbol,bars in inputs.items()}
    for symbol,variant in BOOKS:
        p=source/symbol.replace('/','_')/variant/'result.json';files[str(p.relative_to(ROOT))]=sha(p);original[symbol,variant]=read(p)
    models={};datasets={}
    for arm in ARMS:
        rows=[]
        for symbol in ('BTC/USD','SOL/USD'):rows.extend(dataset_for(symbol,original[symbol,'E1'],indicators[symbol],arm,start,train_end,test_start,end))
        m=fit(rows,train_end,names(arm));models[arm]=m;datasets[arm]=rows
    # Verify the original 11-feature model exactly before scoring later labels.
    assert models['original_ml']==read(previous/'MODEL_BEFORE_VALIDATION_TEST.json')
    for a,b in [('matched_ma','plus_ma'),('matched_all','plus_ma_vwap')]:assert models[a].get('training_keys')==models[b].get('training_keys')
    save(folder/'MODELS_BEFORE_VALIDATION_TEST.json',models)
    for arm in ARMS:
        rows=score(datasets[arm],models[arm]);datasets[arm]=rows;save(folder/('DATASET_'+arm+'.json'),rows)
        study['model_summaries'][arm]={k:v for k,v in models[arm].items() if k not in ('mean','std','weights','training_keys','patterns')}
        study['prediction_metrics'][arm]={phase:metrics([r for r in rows if r['phase']==phase and r['phase_label_resolved']]) for phase in ('train','validation','test')}
    summary_rows=[];fixed_rows=[];decisions_rows=[]
    for symbol,variant in BOOKS:
        bookfolder=folder/symbol.replace('/','_')/variant;bookfolder.mkdir(parents=True);quality=src['source_quality'][symbol]
        control_replay(symbol,variant,inputs[symbol],quality,indicators[symbol].market,start,end,bookfolder/'full_control',expected=original[symbol,variant])
        control=control_replay(symbol,variant,inputs[symbol],quality,indicators[symbol].market,test_start,end,bookfolder/'test_control',expected=read(previous/symbol.replace('/','_')/variant/'test_control/result.json'))
        study['controls_reproduced'][symbol+' '+variant]=True;arms={}
        for arm in ARMS:
            fixed=score(dataset_for(symbol,original[symbol,variant],indicators[symbol],arm,start,train_end,test_start,end),models[arm]);save(bookfolder/('FIXED_'+arm+'.json'),fixed)
            folder_arm=bookfolder/arm
            result=replay(symbol,variant,inputs[symbol],quality,indicators[symbol],test_start,end,folder_arm,arm,models[arm],
                expected=read(previous/symbol.replace('/','_')/variant/'test_filtered/result.json') if arm=='original_ml' else None)
            if arm=='original_ml':study['original_ml_reproduced'][symbol+' '+variant]=True
            save(folder_arm/'CHANGES.json',compare(control,result));ds=result['indicator_decisions']
            arms[arm]=dict(summary=result['summary'],fixed={phase:metrics([r for r in fixed if r['phase']==phase and r['phase_label_resolved']]) for phase in ('train','validation','test')},
                decisions=dict(scored=sum(d['probability'] is not None for d in ds),abstained=sum(d['abstained'] for d in ds),rejected=sum(not d['accepted'] for d in ds)))
            for group in ('all','no_flagged_gap','flagged_gap_or_context'):summary_rows.append(dict(symbol=symbol,model=variant,arm=arm,group=group,**result['summary'][group]))
            fixed_rows.extend(dict(model=variant,**{k:r[k] for k in ('arm','symbol','trade_id','entry_time','entry','exit_time','net','normalized_net','phase','phase_label_resolved','probability','accepted','abstained')}) for r in fixed)
            decisions_rows.extend(dict(symbol=symbol,model=variant,**{k:d[k] for k in ('arm','signal_id','time_utc','route','reference','probability','accepted','abstained','reason')}) for d in ds)
        study['books'].append(dict(symbol=symbol,model=variant,control=control['summary'],arms=arms));save(folder/'STUDY.json',study);print(json.dumps(study['books'][-1]),flush=True)
    csv_table(folder/'SUMMARY.csv',summary_rows);csv_table(folder/'FIXED_ENTRIES.csv',fixed_rows);csv_table(folder/'DECISIONS.csv',decisions_rows)
    save(folder/'PRESERVED_BEFORE.json',files)
    for p,h in {**files,**code}.items():assert sha(ROOT/p)==h,p
    assert verify_rules()==study['rule_hashes'];after=snapshot()
    for k,v in workers.items():assert dict(pid=after[k]['pid'],session=after[k]['session']['id'])==v
    study.update(status='complete',preserved_files=len(files));save(folder/'STUDY.json',study);save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)

if __name__=='__main__':run()
