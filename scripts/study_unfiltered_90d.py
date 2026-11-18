"""Original BTC/SOL rules over 90 days; isolated offline replay and reporting."""
from __future__ import annotations
import copy,gzip,json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,iso,ts
from trading_desk.crypto_transfer import STUDIES as SOURCES,make_engine,protected_state,sha,enrich,summarize,csv_table
from trading_desk.refined_entry_view import BOOKS
from trading_desk.btc_live import verify_rules
from trading_desk.sol_live import snapshot
from trading_desk.btc_engine import export_csv
from trading_desk.unfiltered_90d import PROTOCOL,funded_account,loss_analysis
from scripts.retest_refined_entries import signature
STUDIES=STORE/'unfiltered_90_studies'


def quality(bars,start,end,warmup):
    times={b['t'] for b in bars};test=[b for b in bars if start<=b['t']<end];daily=[]
    for day in range(start,end,86400):
        n=sum(t in times for t in range(day,day+86400,60));daily.append(dict(date_utc=iso(day)[:10],observed=n,expected=1440,missing=1440-n))
    return dict(status='available',observed=len(bars),expected=(end-warmup)//60,missing=[t for t in range(warmup,end,60) if t not in times],
        test_observed=len(test),test_expected=(end-start)//60,test_missing=(end-start)//60-len(test),
        test_first=iso(test[0]['t']) if test else None,test_last=iso(test[-1]['t']) if test else None,
        zero_volume_minutes=sum(b['volume']==0 for b in bars),daily=daily,completely_missing_test_days=[d['date_utc'] for d in daily if d['observed']==0],
        source='Original saved Alpaca BTC cache/SOL GET prefix + untouched original suffix; no filled observations')


def execute(symbol,model,bars,q,start,end,folder,expected=None):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=make_engine(model,start,end,db)
    try:
        for b in bars:engine.minute(b)
        r=engine.finish();db.commit()
        if expected:
            assert len(r['trades'])==len(expected['trades'])
            for p,a in zip(r['trades'],expected['trades'],strict=True):
                want=signature(a);want['legs']=[{k:v for k,v in l.items() if k!='normalized_10000_net'} for l in a['legs']]
                assert signature(p)==want and p['entry_time']==a['entry_time'] and p['entry_rule']==a['entry_rule'],(symbol,model,p['id'])
            assert r['metrics']==expected['metrics']
        r.update(symbol=symbol,model=model,start=iso(start),end=iso(end),status='complete',last_price=engine.last_price,
            policy=PROTOCOL,source_quality=q,orders_enabled=False,live_promoted=False)
        enrich(r,symbol,model,q);r['summary']=summarize(r)
        account=funded_account(r['trades'],bars,start,end,folder);allocations=account.pop('account_trades')
        for p in r['trades']:p['cash_scenario']=allocations[p['id']]
        r['cash_scenario']=account;r['loss_analysis']=loss_analysis(r['trades']);export_csv(folder,r,db)
        csv_table(folder/'ACCOUNT_TRADES.csv',[dict(trade_id=p['id'],entry_time=p['entry_time'],exit_time=p.get('exit_time'),
            cash_before=p['cash_scenario']['cash_before_entry'],initial_units=p['cash_scenario']['initial_units'],funded_realized=p['cash_scenario']['realized_net'],
            return_on_entry_cash_pct=p['cash_scenario']['return_on_entry_cash_pct'],status=p['status']) for p in r['trades']])
        losses=[p for p in r['trades'] if p['status']=='closed' and p['net']<0]
        csv_table(folder/'LOSSES.csv',[dict(trade_id=p['id'],entry_rule=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],target_25=p['t1'],exit_time=p['exit_time'],
            final_exit=p['legs'][-1]['reason'],net_one_coin=p['net'],net_fixed_10000=p['normalized_10000_realized_net'],net_r=p['net_r'],funded_realized=p['cash_scenario']['realized_net'],
            return_on_entry_cash_pct=p['cash_scenario']['return_on_entry_cash_pct'],gap_exposed=p['gap_exposed'],context_partial=p['context_partial'],missing_while_held=p['actual_missing_minutes_while_held']) for p in losses])
        save(folder/'result.json',r);return r
    finally:db.close()


def run():
    source=SOURCES/read(SOURCES/'ACTIVE.json')['study_id'];src=read(source/'STUDY.json');end=ts(src['end']);start=end-90*86400;warmup=start-7*86400;join=ts(src['warmup_start'])
    prefix=STORE/'unfiltered_90_inputs'/f'{warmup}-{join}';prefix_q=read(prefix/'QUALITY.json')
    if not prefix_q:raise RuntimeError('Run scripts/prepare_unfiltered_90d.py to obtain real earlier observations first')
    files,_=protected_state();before=snapshot();workers={k:dict(pid=before[k]['pid'],session=before[k]['session']['id']) for k in ('btc','sol')}
    for parent in ('entry_indicator_studies','entry_quality_studies','adaptive_shock_studies','followthrough_shock_studies','refined_entry_studies'):
        home=STORE/parent;p=home/'ACTIVE.json';files[str(p.relative_to(ROOT))]=sha(p)
        for p in (home/read(p)['study_id']).rglob('*'):
            if p.is_file():files[str(p.relative_to(ROOT))]=sha(p)
    for p in ('trading_desk/btc_live.py','trading_desk/sol_live.py','scripts/run_btc_live.py','scripts/run_sol_live.py','trading_desk/entry_indicator_ml.py','scripts/study_entry_indicators.py'):
        files[p]=sha(ROOT/p)
    for p in [SOURCES/'ACTIVE.json',source/'STUDY.json']+list(prefix.rglob('*')):
        if p.is_file():files[str(p.relative_to(ROOT))]=sha(p)
    code={p:sha(ROOT/p) for p in ('trading_desk/unfiltered_90d.py','scripts/study_unfiltered_90d.py','scripts/prepare_unfiltered_90d.py')}
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-unfiltered-90d';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',protocol=PROTOCOL,start=iso(start),end=iso(end),warmup_start=iso(warmup),source_study=str(source.relative_to(ROOT)),
        prefix_source=str(prefix.relative_to(ROOT)),original_start=src['start'],books=[],source_quality={},controls_reproduced={},workers=workers,
        code_hashes=code,rule_hashes=verify_rules(),orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files);save(folder/'SOURCE_BUNDLE.json',{p:(ROOT/p).read_text() for p in code})
    inputs={};suffixes={};data=folder/'data';data.mkdir()
    for symbol in ('BTC/USD','SOL/USD'):
        pre=prefix/(symbol.replace('/','_')+'_PREFIX.jsonl.gz');old=source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz')
        assert sha(pre)==prefix_q[symbol]['archive_sha256'];assert sha(old)==src['source_quality'][symbol]['archive_sha256']
        files[str(old.relative_to(ROOT))]=sha(old)
        with gzip.open(pre,'rt') as f:early=[json.loads(x) for x in f]
        with gzip.open(old,'rt') as f:suffix=[json.loads(x) for x in f]
        assert all(warmup<=b['t']<join for b in early) and all(join<=b['t']<end for b in suffix)
        bars=early+suffix;assert all(b['t']>a['t'] for a,b in zip(bars,bars[1:]));inputs[symbol]=bars;suffixes[symbol]=suffix
        q=quality(bars,start,end,warmup);path=data/(symbol.replace('/','_')+'_MINUTES.jsonl.gz')
        with gzip.open(path,'wt') as f:
            for b in bars:f.write(json.dumps(b,sort_keys=True)+'\n')
        q['archive_sha256']=sha(path);q['original_suffix_sha256']=sha(old);q['prefix_sha256']=sha(pre);study['source_quality'][symbol]=q
    save(data/'QUALITY.json',study['source_quality']);save(folder/'STUDY.json',study)
    summaries=[]
    for symbol,model in BOOKS:
        old=source/symbol.replace('/','_')/model/'result.json';files[str(old.relative_to(ROOT))]=sha(old);expected=read(old);base=folder/symbol.replace('/','_')/model
        control=execute(symbol,model,suffixes[symbol],src['source_quality'][symbol],ts(src['start']),end,base/'original30',expected)
        study['controls_reproduced'][symbol+' '+model]=True
        ninety=execute(symbol,model,inputs[symbol],study['source_quality'][symbol],start,end,base/'unfiltered90')
        book=dict(symbol=symbol,model=model,periods={})
        for period,r in [('original30',control),('unfiltered90',ninety)]:
            book['periods'][period]=dict(summary=r['summary'],cash_scenario=r['cash_scenario'],loss_analysis=r['loss_analysis'])
            for group in ('all','no_flagged_gap','flagged_gap_or_context'):
                summaries.append(dict(symbol=symbol,model=model,period=period,group=group,**r['summary'][group]))
        study['books'].append(book);save(folder/'STUDY.json',study);print(json.dumps(dict(symbol=symbol,model=model,cash=ninety['cash_scenario'],losses=ninety['loss_analysis'],summary=ninety['summary']['all'])),flush=True)
    csv_table(folder/'SUMMARY.csv',summaries)
    save(folder/'PRESERVED_BEFORE.json',files)
    for p,h in {**files,**code}.items():assert sha(ROOT/p)==h,p
    assert verify_rules()==study['rule_hashes'];after=snapshot()
    for k,v in workers.items():assert dict(pid=after[k]['pid'],session=after[k]['session']['id'])==v
    study.update(status='complete',preserved_files=len(files));save(folder/'STUDY.json',study);save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)

if __name__=='__main__':run()
