"""Fixed adaptive-weight comparisons plus chronological calibration; no orders."""
from __future__ import annotations
import argparse,copy,gzip,json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.adaptive_shock import Settings,Contexts,Policy,PROTOCOL,AdaptiveBaseline,AdaptiveEarly
from trading_desk.crypto_transfer import STUDIES as SOURCES,protected_state,sha,enrich,summarize,csv_table
from trading_desk.followthrough_view import VIEW as PRIOR
from trading_desk.refined_entry_view import BOOKS
from trading_desk.btc_live import verify_rules,LIVE
from trading_desk.sol_live import snapshot,HOME
from trading_desk.btc_engine import export_csv
from scripts.btc_structure_retest import Config
from scripts.retest_refined_entries import signature,compare

STUDIES=STORE/'adaptive_shock_studies'
ML_PROTOCOL=dict(method='Low-complexity chronological hyperparameter calibration, not a neural network or proven forecast model',
 train_days=14,validation_days=7,test_days=9,base_grid=[2.,2.5,3.],sol_weight_grid=[1.,1.25,1.5],
 label='Only trades completed by each phase boundary; exclude unresolved labels explicitly, no future exit leakage',
 eligibility='At least 3 completed training trades and 2 validation trades; both phase net R positive',
 objective='Validation net R minus validation closed-trade peak-to-trough drawdown R; tie prefers fewer parameter departures from ATR-only base 2, weight 1',
 selection='Use development data ending day 21 only. No test scores supplied to selector. No eligible candidate falls back to ATR-only base 2, weight 1, explicitly not a learned choice.',
 test='Reset all comparison books flat at day 21 with seven days of real warmup; no inherited development position or forced closing fill',
 limitations='Previously inspected 30-day history; retrospective chronological holdout, not genuinely unseen data. Very small sample; forward paper validation required. No profit optimization claim or live promotion.')

def cohort(result,start,end):
    entries=[p for p in result['trades'] if start<=ts(p['entry_time'])<end]
    rows=[p for p in entries if p['status']=='closed' and ts(p['exit_time'])<end]
    equity=peak=dd=0.
    for p in sorted(rows,key=lambda p:p['exit_time']):
        equity+=p['net_r'];peak=max(peak,equity);dd=max(dd,peak-equity)
    return dict(entries=len(entries),completed=len(rows),unresolved=len(entries)-len(rows),
        net=sum(p['realized_leg_net'] for p in rows),normalized_10000=sum(p['normalized_10000_realized_net'] for p in rows),
        net_r=equity,closed_drawdown_r=dd,score=equity-dd,wins=sum(p['net']>0 for p in rows))

def choose(candidates):
    eligible=[c for c in candidates if c['train']['completed']>=3 and c['validation']['completed']>=2 and c['train']['net_r']>0 and c['validation']['net_r']>0]
    if not eligible:return dict(settings=Settings(2.,1.).asdict(),learned=False,reason='Insufficient positive train/validation evidence; predeclared ATR-only fallback, not learned')
    best=max(eligible,key=lambda c:(c['validation']['score'],-abs(c['settings']['base_btc_atr']-2.)-abs(c['settings']['sol_weight']-1.)))
    return dict(settings=copy.deepcopy(best['settings']),learned=True,reason='Highest eligible validation net-R-minus-drawdown score; test not consulted',
        train=best['train'],validation=best['validation'],eligible_candidates=len(eligible))

def replay(symbol,model,bars,quality,contexts,start,end,settings,folder=None,control=False,expected=None):
    db=sqlite3.connect(':memory:' if folder is None else folder/'ledger.sqlite')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    cls=AdaptiveBaseline if model=='0.1' else AdaptiveEarly;kwargs={} if model=='0.1' else dict(early_policy=model)
    engine=cls(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),expanded_b=True,
        consume_entry_history=True,b1_independent_hold=True,adaptive_policy=Policy(symbol,contexts[symbol],contexts['BTC/USD'],settings,control),**kwargs)
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
        result.update(symbol=symbol,model=model,status='complete',start=iso(start),end=iso(end),last_price=engine.last_price,
            policy=dict(entries=PROTOCOL,settings=settings.asdict(),control_uniform_net3=control),source_quality=quality,orders_enabled=False,live_promoted=False)
        enrich(result,symbol,model,quality);result['summary']=summarize(result)
        if folder:export_csv(folder,result,db);save(folder/'result.json',result)
        return result
    finally:db.close()

def case_review(symbol,contexts_settings):
    audit=read(ROOT/'reports/live_entry_review_20261110T111101Z/REVIEW.json');a=next(x for x in audit['results'] if x['asset']==symbol.split('/')[0]);p=next(x for x in a['trades'] if x['trade_id']==(3 if symbol=='BTC/USD' else 2));imp=p['setup_evidence']['impulse'];t=imp['t']
    minutes={}
    for asset in ('BTC/USD','SOL/USD'):
        record=next(x for x in audit['results'] if x['asset']==asset.split('/')[0])
        with sqlite3.connect((ROOT/record['actual_source']).as_uri()+'?mode=ro',uri=True) as db:
            minutes[asset]=[json.loads(x) for x, in db.execute('SELECT body FROM minutes WHERE t>=? AND t<? ORDER BY t',(t-16*900,t+900))]
    contexts={k:Contexts(v) for k,v in minutes.items()};asset=contexts[symbol];bar=copy.deepcopy(imp)
    bar['atr_before']=imp['atr_before'];previous=asset.bars.get(t-900)
    return dict(symbol=symbol,entry_time=p['entry_time'],entry=p['entry'],impulse_time=iso(t),
        measurements={name:Policy(symbol,asset,contexts['BTC/USD'],cfg).evaluate(bar,previous,p['setup_evidence']['lowest_before_impulse']) for name,cfg in contexts_settings.items()},
        source_minutes=minutes,entry_detection=p['detected_at'],not_a_fill=True)

def run(settings=Settings()):
    source=SOURCES/read(SOURCES/'ACTIVE.json')['study_id'];base=read(source/'STUDY.json');prior_folder,prior=PRIOR.current()
    start=ts(base['start']);end=ts(base['end']);train_end=start+14*86400;test_start=start+21*86400
    assert end-test_start==9*86400
    files,_=protected_state();state=snapshot();workers={k:dict(pid=state[k]['pid'],session=state[k]['session']['id']) for k in ('btc','sol')}
    for path in prior_folder.rglob('*'):
        if path.is_file():files[str(path.relative_to(ROOT))]=sha(path)
    for p in ('trading_desk/btc_live.py','trading_desk/sol_live.py','scripts/run_btc_live.py','scripts/run_sol_live.py','trading_desk/refined_entries.py','trading_desk/steeper_shock_research.py','scripts/study_followthrough_shock.py','trading_desk/followthrough_research.py'):
        files[p]=sha(ROOT/p)
    for p in (SOURCES/'ACTIVE.json',source/'STUDY.json',prior_folder.parent/'ACTIVE.json'):
        files[str(p.relative_to(ROOT))]=sha(p)
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-adaptive-shock';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    code={p:sha(ROOT/p) for p in ('trading_desk/adaptive_shock.py','scripts/study_adaptive_shock.py')}
    study=dict(study_id=ident,status='running',protocol=PROTOCOL,ml_protocol=ML_PROTOCOL,settings=settings.asdict(),start=iso(start),end=iso(end),
        train_end=iso(train_end),test_start=iso(test_start),source_study=str(source.relative_to(ROOT)),prior_study=str(prior_folder.relative_to(ROOT)),
        books=[],workers=workers,code_hashes=code,rule_hashes=verify_rules(),orders_enabled=False,live_promoted=False,controls_reproduced={},source_quality=base['source_quality'])
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files)
    inputs={}
    for symbol in ('BTC/USD','SOL/USD'):
        p=source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz');assert sha(p)==base['source_quality'][symbol]['archive_sha256'];files[str(p.relative_to(ROOT))]=sha(p)
        with gzip.open(p,'rt') as f:inputs[symbol]=[json.loads(l) for l in f]
    contexts={k:Contexts(v) for k,v in inputs.items()};variants={'atr_only':Settings(settings.base_btc_atr,1.),'weighted':settings}
    study['cases']=[case_review(symbol,variants) for symbol in ('BTC/USD','SOL/USD')]
    for c in study['cases']:save(folder/(c['symbol'].replace('/','_')+'_CASE.json'),c)
    summary_rows=[];calibration=[];changes_rows=[]
    for symbol,model in BOOKS:
        bfolder=folder/symbol.replace('/','_')/model;bfolder.mkdir(parents=True);quality=base['source_quality'][symbol]
        expected_path=prior_folder/symbol.replace('/','_')/model/'steeper/result.json';expected=read(expected_path)
        results={}
        for name,cfg,control in [('uniform3',settings,True)]+[(n,c,False) for n,c in variants.items()]:
            out=bfolder/name;out.mkdir();r=replay(symbol,model,inputs[symbol],quality,contexts,start,end,cfg,out,control,expected if control else None);results[name]=r
        study['controls_reproduced'][symbol+' '+model]=True
        changes=compare(results['atr_only'],results['weighted']);save(bfolder/'WEIGHT_CHANGES.json',changes)
        changes_rows.extend(dict(symbol=symbol,model=model,time=c['time'],status=c['status'],delta_normalized_10000=c['delta_normalized_10000']) for c in changes)
        candidates=[]
        for k in ML_PROTOCOL['base_grid']:
            for w in ([1.] if symbol=='BTC/USD' else ML_PROTOCOL['sol_weight_grid']):
                cfg=Settings(k,w);r=replay(symbol,model,inputs[symbol],quality,contexts,start,test_start,cfg)
                c=dict(symbol=symbol,model=model,settings=cfg.asdict(),train=cohort(r,start,train_end),validation=cohort(r,train_end,test_start))
                candidates.append(c);calibration.append(c)
        selected=choose(candidates);save(bfolder/'SELECTION_BEFORE_TEST.json',selected)
        test_results={}
        for name,cfg,control in [('uniform3',settings,True),('atr_only',variants['atr_only'],False),('weighted',settings,False),('selected',Settings(**selected['settings']),False)]:
            out=bfolder/('test_'+name);out.mkdir();test_results[name]=replay(symbol,model,inputs[symbol],quality,contexts,test_start,end,cfg,out,control)
        save(bfolder/'CALIBRATION.json',candidates)
        book=dict(symbol=symbol,model=model,full={n:r['summary'] for n,r in results.items()},test={n:r['summary'] for n,r in test_results.items()},selection=selected,
            weight_change_counts={n:sum(c['status']==n for c in changes) for n in ('unchanged','relabelled_only','changed','removed','added')})
        for phase,rs in [('full',results),('test',test_results)]:
            for name,r in rs.items():
                for group in ('all','no_flagged_gap','flagged_gap_or_context'):summary_rows.append(dict(symbol=symbol,model=model,phase=phase,sequence=name,group=group,**r['summary'][group]))
        study['books'].append(book);save(folder/'STUDY.json',study);print(json.dumps(book),flush=True)
    csv_table(folder/'SUMMARY.csv',summary_rows);csv_table(folder/'WEIGHT_CHANGES.csv',changes_rows)
    save(folder/'CALIBRATION.json',calibration);save(folder/'PRESERVED_BEFORE.json',files)
    for p,h in {**files,**code}.items():assert sha(ROOT/p)==h,p
    assert verify_rules()==study['rule_hashes'];after=snapshot()
    for k,w in workers.items():assert dict(pid=after[k]['pid'],session=after[k]['session']['id'])==w
    study.update(status='complete',preserved_files=len(files));save(folder/'STUDY.json',study);save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--btc-base-atr',type=float,default=2.);p.add_argument('--sol-weight',type=float,default=1.5);a=p.parse_args();run(Settings(a.btc_base_atr,a.sol_weight))
