"""Separate fixed-entry exit research and steeper-shock entry-only replay."""
from __future__ import annotations
import copy
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,iso,ts
from trading_desk.crypto_transfer import STUDIES as INPUTS,protected_state,sha,csv_table,enrich,summarize as seq_summary
from trading_desk.refined_entry_view import VIEW as PREVIOUS,BOOKS,GROUPS
from trading_desk.followthrough_research import Market,PROTOCOL as EXIT_PROTOCOL,value,summarize
from trading_desk.steeper_shock_research import PROTOCOL as SHOCK_PROTOCOL,ShockBaseline,ShockEarly,measure
from trading_desk.btc_engine import aggregate,export_csv
from trading_desk.btc_live import verify_rules,LIVE
from trading_desk.sol_live import snapshot,HOME
from scripts.btc_structure_retest import Config
from scripts.retest_refined_entries import signature,compare

STUDIES=STORE/'followthrough_shock_studies'


def group_of(p):return 'flagged_gap_or_context' if p['gap_exposed'] or p['context_partial'] else 'no_flagged_gap'


def case_review(asset,trade_id,root,folder):
    state=snapshot()['btc' if asset=='BTC/USD' else 'sol'];path=root/'sessions'/state['session']['id']/'observations.sqlite'
    audit=read(ROOT/'reports/live_entry_review_20261110T111101Z/REVIEW.json')
    book=next(r for r in audit['results'] if r['asset']==asset.split('/')[0]);p=next(t for t in book['trades'] if t['trade_id']==trade_id)
    original=dict(entry_time=p['entry_time'],entry=p['entry'],exit_time=p['exit_time'],legs=p['legs'],references=p['references'],
        initial_stop=p['stop'],t1=p['target_25'],entry_rule=p['recorded_route'])
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        minutes=[json.loads(b) for b, in db.execute('SELECT body FROM minutes WHERE t>=? AND t<? ORDER BY t',
            (ts(p['entry_time'])//900*900-1800,ts(p['exit_time'])+60))]
        setup=p['setup_evidence'];impulse=setup['impulse']
        previous=[json.loads(b) for b, in db.execute('SELECT body FROM minutes WHERE t>=? AND t<? ORDER BY t',(impulse['t']-900,impulse['t']))]
    prev=aggregate(previous,900);shock=measure(impulse,prev,setup['lowest_before_impulse'])
    market=Market(minutes)
    out=dict(asset=asset,trade_id=trade_id,original=original,minutes=minutes,
        shock=shock,nonshock_classification='A candidate; no qualifying A exposed in the original entry-time audit, so not an automatic A buy',
        exits={policy:value(original,market.scan(original,policy),policy) for policy in ('F1','F2')})
    save(folder/(asset.replace('/','_')+'_0445.json'),out);return out


def shock_run(symbol,model,bars,quality,start,end,folder,baseline,mode):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    cls=ShockBaseline if model=='0.1' else ShockEarly;args={} if model=='0.1' else dict(early_policy=model)
    engine=cls(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),expanded_b=True,
        consume_entry_history=True,b1_independent_hold=True,original_entry_times=[ts(p['entry_time']) for p in baseline['trades']],shock_mode=mode,**args)
    try:
        for b in bars:engine.minute(b)
        r=engine.finish();db.commit()
        if mode=='legacy':
            assert len(r['trades'])==len(baseline['trades'])
            for a,b in zip(r['trades'],baseline['trades'],strict=True):
                expected=signature(b);expected['legs']=[{k:v for k,v in l.items() if k!='normalized_10000_net'} for l in b['legs']]
                assert signature(a)==expected and a['entry_time']==b['entry_time'] and a['entry_rule']==b['entry_rule'],(symbol,model,a['id'])
            assert r['metrics']==baseline['metrics']
        r.update(symbol=symbol,model=model,start=iso(start),end=iso(end),last_price=engine.last_price,status='complete',
            policy=copy.deepcopy(baseline['policy']),source_quality=quality,orders_enabled=False,live_promoted=False)
        enrich(r,symbol,model,quality);r['summary']=seq_summary(r);export_csv(folder,r,db);save(folder/'result.json',r);return r
    finally:db.close()


def run():
    source=INPUTS/read(INPUTS/'ACTIVE.json')['study_id'];old_folder,prior=PREVIOUS.current();inputs_study=read(source/'STUDY.json')
    files,_=protected_state();state=snapshot();workers={k:dict(pid=state[k]['pid'],session=state[k]['session']['id']) for k in ('btc','sol')}
    for name in ('trading_desk/btc_live.py','trading_desk/sol_live.py','scripts/run_btc_live.py','scripts/run_sol_live.py','trading_desk/refined_entries.py','scripts/retest_refined_entries.py'):
        files[name]=sha(ROOT/name)
    for p in [INPUTS/'ACTIVE.json',old_folder.parent/'ACTIVE.json',old_folder/'STUDY.json',source/'STUDY.json']:
        files[str(p.relative_to(ROOT))]=sha(p)
    code={n:sha(ROOT/n) for n in ('trading_desk/followthrough_research.py','trading_desk/steeper_shock_research.py','scripts/study_followthrough_shock.py')}
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-followthrough-shock';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',start=inputs_study['start'],end=inputs_study['end'],source_study=str(source.relative_to(ROOT)),prior_refined_study=str(old_folder.relative_to(ROOT)),
        exit_protocol=EXIT_PROTOCOL,shock_protocol=SHOCK_PROTOCOL,code_hashes=code,rule_hashes=verify_rules(),workers=workers,books=[],
        controls_reproduced={},live_promoted=False,orders_enabled=False,source_quality=inputs_study['source_quality'])
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files)
    study['cases']=[case_review('BTC/USD',3,LIVE,folder),case_review('SOL/USD',2,HOME,folder)]
    # The protocol/code are already pinned. Do not adjust after these cases.
    for c in study['cases']:print(json.dumps(dict(asset=c['asset'],shock=c['shock'],exits={k:{x:v.get(x) for x in ('triggered','exit_time','net','delta')} for k,v in c['exits'].items()})),flush=True)
    inputs={}
    for symbol in ('BTC/USD','SOL/USD'):
        p=source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz');q=inputs_study['source_quality'][symbol]
        assert sha(p)==q['archive_sha256'];files[str(p.relative_to(ROOT))]=sha(p)
        with gzip.open(p,'rt') as f:inputs[symbol]=[json.loads(l) for l in f]
    overlay_rows=[];summary_rows=[];shock_changes=[]
    for symbol,model in BOOKS:
        baseline_path=source/symbol.replace('/','_')/model/'result.json';original=read(baseline_path)
        previous_path=old_folder/symbol.replace('/','_')/model/'refined/result.json';previous=read(previous_path)
        files[str(baseline_path.relative_to(ROOT))]=sha(baseline_path);files[str(previous_path.relative_to(ROOT))]=sha(previous_path)
        market=Market(inputs[symbol]);bookfolder=folder/symbol.replace('/','_')/model;bookfolder.mkdir(parents=True)
        rows=[];summaries={}
        for policy in ('F1','F2'):
            outcomes=[value(p,market.scan(p,policy),policy) for p in original['trades']]
            summaries[policy]={}
            for group in GROUPS:
                pairs=[(p,r) for p,r in zip(original['trades'],outcomes) if group=='all' or group_of(p)==group]
                summary=summarize([p for p,r in pairs],[r for p,r in pairs]);summaries[policy][group]=summary
                summary_rows.append(dict(symbol=symbol,model=model,policy=policy,group=group,**summary))
            for p,r in zip(original['trades'],outcomes):
                row=dict(symbol=symbol,model=model,policy=policy,trade_id=p['id'],entry_time=p['entry_time'],entry=p['entry'],route=p['entry_rule'],
                    initial_stop=p['initial_stop'],target_25=p['t1'],references=p['references'],original_exit=p.get('exit_time'),original_legs=p['legs'],group=group_of(p),**r)
                rows.append(row)
                overlay_rows.append({k:row.get(k) for k in ('symbol','model','policy','trade_id','entry_time','entry','route','original_exit','exit_time','original_net','net','delta','normalized_10000_delta','triggered','winner_cut','winner_flipped_to_loss','loser_improved','loser_worsened','minutes_earlier','group')})
        save(bookfolder/'EXITS.json',rows)
        old=shock_run(symbol,model,inputs[symbol],inputs_study['source_quality'][symbol],ts(study['start']),ts(study['end']),bookfolder/'shock_control',previous,'legacy')
        study['controls_reproduced'][symbol+' '+model]=True
        new=shock_run(symbol,model,inputs[symbol],inputs_study['source_quality'][symbol],ts(study['start']),ts(study['end']),bookfolder/'steeper',previous,'net3')
        changes=compare(old,new);save(bookfolder/'SHOCK_CHANGES.json',changes)
        shock_changes.extend(dict(symbol=symbol,model=model,time=c['time'],status=c['status'],old_route=c['original']['entry_rule'] if c['original'] else None,
            new_route=c['refined']['entry_rule'] if c['refined'] else None,delta_realized=c['delta_realized'],delta_normalized_10000=c['delta_normalized_10000']) for c in changes)
        book=dict(symbol=symbol,model=model,exit_summaries=summaries,shock_original=old['summary'],shock_steeper=new['summary'],
            shock_change_counts={v:sum(c['status']==v for c in changes) for v in ('unchanged','relabelled_only','changed','removed','added')},
            old_2atr_episodes=sum(x['qualifies'] for x in old['shock_reviews']),new_3atr_episodes=sum(x['qualifies'] for x in new['shock_reviews']))
        study['books'].append(book);save(folder/'STUDY.json',study);print(json.dumps(book),flush=True)
    csv_table(folder/'EXIT_SUMMARY.csv',summary_rows);csv_table(folder/'EXIT_TRADES.csv',overlay_rows);csv_table(folder/'SHOCK_CHANGES.csv',shock_changes)
    save(folder/'PRESERVED_BEFORE.json',files)
    for p,h in files.items():assert sha(ROOT/p)==h,p
    for p,h in code.items():assert sha(ROOT/p)==h,p
    assert verify_rules()==study['rule_hashes']
    after=snapshot()
    for k,v in workers.items():assert dict(pid=after[k]['pid'],session=after[k]['session']['id'])==v
    study.update(status='complete',preserved_files=len(files));save(folder/'STUDY.json',study)
    save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)


if __name__=='__main__':run()
