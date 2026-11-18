"""Same archived 30 days; isolated BTC 0.1/E1/E2 and SOL E1 entry experiment."""
from __future__ import annotations
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso,STORE
from trading_desk.crypto_transfer import STUDIES as SOURCES,make_engine,enrich,summarize,csv_table,protected_state,sha
from trading_desk.btc_engine import export_csv
from trading_desk.btc_live import verify_rules
from trading_desk.sol_live import snapshot
from trading_desk.refined_entries import RefinedBaseline,RefinedEarly,PROTOCOL
from scripts.btc_structure_retest import Config

STUDIES=STORE/'refined_entry_studies'
BOOKS=(('BTC/USD','0.1'),('BTC/USD','E1'),('BTC/USD','E2'),('SOL/USD','E1'))


def signature(p):
    return {k:copy.deepcopy(p.get(k)) for k in ('entry','initial_stop','t1','t2','legs','status','remaining')}


def compare(old,new):
    before={p['entry_time']:p for p in old['trades']};after={p['entry_time']:p for p in new['trades']};rows=[]
    reviews={p['time_utc']:p for p in new.get('original_entry_reviews',[])}
    for stamp in sorted(before.keys()|after.keys()):
        a=before.get(stamp);b=after.get(stamp)
        same=bool(a and b and signature(a)==signature(b))
        status=('unchanged' if a['entry_rule']==b['entry_rule'] else 'relabelled_only') if same else 'changed' if a and b else 'removed' if a else 'added'
        av=a['realized_leg_net'] if a else 0;bv=b['realized_leg_net'] if b else 0
        rows.append(dict(time=stamp,status=status,original=a,refined=b,delta_realized=bv-av,
            delta_normalized_10000=(b['normalized_10000_realized_net'] if b else 0)-(a['normalized_10000_realized_net'] if a else 0),
            original_entry_review=reviews.get(stamp)))
    return rows


def execute(symbol,model,bars,quality,start,end,folder,baseline,refined):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    if refined:
        cls=RefinedBaseline if model=='0.1' else RefinedEarly
        args={} if model=='0.1' else dict(early_policy=model)
        engine=cls(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),
            expanded_b=True,consume_entry_history=True,b1_independent_hold=True,
            original_entry_times=[ts(p['entry_time']) for p in baseline['trades']],**args)
    else:engine=make_engine(model,start,end,db)
    try:
        for i,b in enumerate(bars):
            engine.minute(b)
            if i and i%15000==0:print(json.dumps(dict(asset=symbol,model=model,refined=refined,minutes=i)),flush=True)
        r=engine.finish();db.commit()
        if not refined:
            # Transfer files were enriched after original replay. Compare only
            # original path/risk/exit fields, and the complete original metrics.
            assert len(r['trades'])==len(baseline['trades'])
            for a,b in zip(r['trades'],baseline['trades'],strict=True):
                assert signature(a)=={k:({**b}.get(k) if k!='legs' else [{k:v for k,v in l.items() if k!='normalized_10000_net'} for l in b['legs']]) for k in signature(a)},(symbol,model,a['id'])
                assert a['entry_time']==b['entry_time'] and a['entry_rule']==b['entry_rule']
            assert r['metrics']==baseline['metrics']
        r.update(symbol=symbol,model=model,start=iso(start),end=iso(end),last_price=engine.last_price,
            status='complete',policy=copy.deepcopy(baseline['policy']),source_quality=quality,
            orders_enabled=False,live_promoted=False)
        r['policy']['entries']=PROTOCOL if refined else baseline['policy']['entries']
        enrich(r,symbol,model,quality);r['summary']=summarize(r)
        export_csv(folder,r,db);save(folder/'result.json',r);return r
    finally:db.close()


def run():
    source=SOURCES/read(SOURCES/'ACTIVE.json')['study_id'];source_study=read(source/'STUDY.json')
    start=ts(source_study['start']);end=ts(source_study['end'])
    files,_=protected_state();live=snapshot();workers={k:dict(pid=live[k]['pid'],session=live[k]['session']['id']) for k in ('btc','sol')}
    for name in ('trading_desk/btc_live.py','trading_desk/sol_live.py','scripts/run_btc_live.py','scripts/run_sol_live.py','trading_desk/btc_p1.py'):
        files[name]=sha(ROOT/name)
    for p in [SOURCES/'ACTIVE.json',source/'STUDY.json',source/'data/QUALITY.json']:
        files[str(p.relative_to(ROOT))]=sha(p)
    for symbol,model in BOOKS:
        p=source/symbol.replace('/','_')/model/'result.json';files[str(p.relative_to(ROOT))]=sha(p)
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-refined-AB';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    code={n:sha(ROOT/n) for n in ('trading_desk/refined_entries.py','scripts/retest_refined_entries.py')}
    study=dict(study_id=ident,status='running',source_study=str(source.relative_to(ROOT)),start=iso(start),end=iso(end),
        warmup_start=source_study['warmup_start'],protocol=PROTOCOL,books=[],workers=workers,
        rule_hashes=verify_rules(),code_hashes=code,controls_reproduced={},orders_enabled=False,live_promoted=False,
        sizing='1 initial coin; also sum of fixed $10,000 independent entry normalization, not account return',
        costs='Original 2bps/side ETF proxy, excluding actual spot crypto fees',
        gaps='Original actual observations and gaps; no filled/interpolated minutes; per-trade exposure partitions retained')
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files)
    inputs={}
    for symbol in {s for s,m in BOOKS}:
        p=source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz')
        assert sha(p)==source_study['source_quality'][symbol]['archive_sha256']
        inputs[symbol]=[json.loads(l) for l in gzip.open(p,'rt')]
        files[str(p.relative_to(ROOT))]=sha(p)
    save(folder/'PRESERVED_BEFORE.json',files)
    summary=[];all_changes=[];trade_rows=[];leg_rows=[]
    for symbol,model in BOOKS:
        baseline=read(source/symbol.replace('/','_')/model/'result.json');quality=source_study['source_quality'][symbol]
        book=folder/symbol.replace('/','_')/model
        control=execute(symbol,model,inputs[symbol],quality,start,end,book/'original',baseline,False)
        study['controls_reproduced'][symbol+' '+model]=True
        revised=execute(symbol,model,inputs[symbol],quality,start,end,book/'refined',baseline,True)
        changes=compare(control,revised);save(book/'CHANGES.json',changes)
        for sequence,result in [('original',control),('refined',revised)]:
            for group in ('all','no_flagged_gap','flagged_gap_or_context'):
                summary.append(dict(symbol=symbol,model=model,sequence=sequence,group=group,**result['summary'][group]))
            for p in result['trades']:
                trade_rows.append(dict(symbol=symbol,model=model,sequence=sequence,trade_id=p['id'],route=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],stop=p['initial_stop'],target=p['t1'],
                    exit_time=p.get('exit_time'),remaining=p['remaining'],realized=p['realized_leg_net'],unrealized=p['unrealized_net_reference'],
                    normalized_10000_realized=p['normalized_10000_realized_net'],normalized_10000_unrealized=p['normalized_10000_unrealized_net'],
                    gap_exposed=p['gap_exposed'],context_partial=p['context_partial']))
                leg_rows.extend(dict(symbol=symbol,model=model,sequence=sequence,trade_id=p['id'],**l) for l in p['legs'])
        simple=[]
        for c in changes:
            a=c['original'];b=c['refined'];simple.append(dict(symbol=symbol,model=model,time=c['time'],status=c['status'],old_id=a['id'] if a else None,new_id=b['id'] if b else None,
                old_route=a['entry_rule'] if a else None,new_route=b['entry_rule'] if b else None,old_entry=a['entry'] if a else None,new_entry=b['entry'] if b else None,
                old_exit=a.get('exit_time') if a else None,new_exit=b.get('exit_time') if b else None,delta_realized=c['delta_realized'],delta_normalized_10000=c['delta_normalized_10000']))
        all_changes.extend(simple);csv_table(book/'CHANGES.csv',simple)
        study['books'].append(dict(symbol=symbol,model=model,original=control['summary'],refined=revised['summary'],
            change_counts={v:sum(c['status']==v for c in changes) for v in ('unchanged','relabelled_only','changed','removed','added')}))
        save(folder/'STUDY.json',study);print(json.dumps(study['books'][-1]),flush=True)
    for p,h in files.items():assert sha(ROOT/p)==h,p
    for p,h in code.items():assert sha(ROOT/p)==h,p
    after=snapshot()
    for k,v in workers.items():assert dict(pid=after[k]['pid'],session=after[k]['session']['id'])==v
    assert verify_rules()==study['rule_hashes']
    csv_table(folder/'SUMMARY.csv',summary);csv_table(folder/'CHANGES.csv',all_changes);csv_table(folder/'TRADES.csv',trade_rows);csv_table(folder/'EXITS.csv',leg_rows)
    study.update(status='complete',preserved_files=len(files));save(folder/'STUDY.json',study)
    save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)


if __name__=='__main__':run()
