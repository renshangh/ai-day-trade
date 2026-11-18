"""Frozen 0.2 SOL/ETH transfer replay, independent of every forward worker."""
from __future__ import annotations
import bisect
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from trading_desk.btc_data import ROOT,STORE,read,save,iso,ts,request_page,normalize
from trading_desk.btc_engine import create_replay,export_csv
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_live import verify_rules,CONTROLLER,MODELS
from scripts.btc_structure_retest import Config

STUDIES=STORE/'crypto_transfer_studies'
ASSETS=('BTC/USD','SOL/USD','ETH/USD')
POLICY=dict(strategy='Exact frozen 0.2 constructors used by btc-live: 0.1 baseline, E1 and E2',
    entries='Original A/B1/B2; expanded B enabled; consumed entry history; aggressive B1; no P1, C or top-ten-library filter',
    exits='Original 0.1/E1/E2 full sequential exits, first 25% target, remainder protection and hard stops',
    unchanged='All numerical parameters, including absolute $0.01 trigger increment and 2bps per side, unchanged',
    source='Real Alpaca US crypto 1-minute OHLCV, 24/7; may include quote midprices/zero-volume observations; missing bars stay absent',
    sizing='1 initial coin per trade; also fixed $10,000 entry-notional normalization per independent trade',
    costs='Frozen ETF 2bps/side spread-slippage proxy, not actual SOL/ETH/BTC spot trading fees',
    timing='Historical minute OHLC reference model; exact crossing seconds, actual receipt and broker fills unverified',
    validation='Same BTC development window, cross-asset transfer; no SOL/ETH-specific tuning, not an unseen chronological validation',
    capital='Independent symbol/model books; no combined account, cash constraint, compounding or automatic orders',
    open_positions='No forced final sale; remaining size marked separately at last actual observed close',
    original_live_unchanged=True,orders_enabled=False,live_promoted=False)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def make_engine(model,start,end,db):
    if model=='0.1':return create_replay(start,end,db,expanded_b=True,exit_version='failed_rebound')
    if model not in ('E1','E2'):raise ValueError('Choose frozen 0.1, E1 or E2')
    return EarlySequentialReplay(start,end,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),
        early_policy=model,expanded_b=True,consume_entry_history=True,b1_independent_hold=False)


def protected_state():
    from scripts.audit_btc_c_blind_review import locked,preservation
    locked();live=preservation();verify_rules()
    files={ROOT/p:h for p,h in read(ROOT/'reports/btc_c_blind_review_2026_11_09/PRESERVED_BEFORE.json')['files'].items()}
    for name in ('CONFIG.json','LIBRARY.json','UNIVERSE_SCREEN.json'):
        p=ROOT/'trading_records/pattern_discovery'/name
        if p.exists():files[p]=sha(p)
    for parent in (STORE/'p1_studies',STORE/'parent_hl_studies',STORE/'parent_filter_studies',ROOT/'trading_records/pattern_discovery/backtests'):
        p=parent/'ACTIVE.json'
        if p.exists():files[p]=sha(p)
    return {str(p.relative_to(ROOT)):h for p,h in files.items()},live


def download(folder,start,end):
    folder.mkdir(parents=True,exist_ok=True);raw=folder/'raw';raw.mkdir()
    collected={'SOL/USD':[],'ETH/USD':[]};pages=[];token=None;seen=set()
    while True:
        params=dict(symbols='SOL/USD,ETH/USD',timeframe='1Min',start=iso(start),end=iso(end),limit=10000,sort='asc')
        if token:params['page_token']=token
        payload=request_page(params);digest=hashlib.sha256(payload).hexdigest();name=digest+'.json.gz'
        (raw/name).write_bytes(gzip.compress(payload));page=json.loads(payload)
        for symbol in collected:collected[symbol].extend((page.get('bars') or {}).get(symbol,[]))
        pages.append(dict(params=copy.deepcopy(params),raw_sha256=digest,file='raw/'+name,
            received_at=iso(time.time()),counts={k:len((page.get('bars') or {}).get(k,[])) for k in collected}))
        save(folder/'SOURCES.json',dict(url='https://data.alpaca.markets/v1beta3/crypto/us/bars',pages=pages))
        print(json.dumps(dict(download_page=len(pages),observed={k:len(v) for k,v in collected.items()})),flush=True)
        token=page.get('next_page_token')
        if not token:break
        if token in seen or len(seen)>=100:raise ValueError('Repeated/excessive crypto pagination')
        seen.add(token)
    output={};quality={}
    for symbol,rows in collected.items():
        try:
            actual=normalize(rows,start,end)
            if not actual:raise ValueError('No real crypto minutes returned for requested interval')
            output[symbol]=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in actual]
        except ValueError as exc:quality[symbol]=dict(status='unavailable',reason=str(exc))
    source_sha=hashlib.sha256();btc=[]
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            source_sha.update(line);t,o,h,l,c,v,n,vw=json.loads(line)
            if start<=t<end:btc.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    output['BTC/USD']=btc
    expected=set(range(start,end,60))
    for symbol,bars in output.items():
        missing=sorted(expected-{b['t'] for b in bars})
        quality[symbol]=dict(status='available',observed=len(bars),expected=len(expected),missing=missing,
            zero_volume_minutes=sum(b['volume']==0 for b in bars),
            source='Exact frozen BTC stream' if symbol=='BTC/USD' else 'Alpaca US crypto historical observations')
        if symbol=='BTC/USD':quality[symbol]['frozen_source_sha256']=source_sha.hexdigest()
        p=folder/(symbol.replace('/','_')+'_MINUTES.jsonl.gz')
        with gzip.open(p,'wt') as f:
            for b in bars:f.write(json.dumps(b,sort_keys=True)+'\n')
        quality[symbol]['archive_sha256']=sha(p)
    save(folder/'QUALITY.json',quality);return output,quality


def enrich(result,symbol,model,quality):
    missing=quality['missing'];last=result['last_observed'];end=ts(last)
    for p in result['trades']:
        p.update(symbol=symbol,model=model,units=symbol.split('/')[0])
        finish=ts(p.get('exit_time') or last)
        p['actual_missing_minutes_while_held']=bisect.bisect_right(missing,finish)-bisect.bisect_left(missing,ts(p['entry_time']))
        p['realized_leg_net']=sum(l['net'] for l in p['legs'])
        p['unrealized_net_reference']=p['remaining']*(result['last_price']-p['entry'])-p['remaining']*(result['last_price']+p['entry'])*.0002 if p['remaining'] else 0
        p['normalized_10000_realized_net']=p['realized_leg_net']/p['entry']*10000
        p['normalized_10000_unrealized_net']=p['unrealized_net_reference']/p['entry']*10000
        p.update(mark_price=result['last_price'],mark_time=last)
        for l in p['legs']:l['normalized_10000_net']=l['net']/p['entry']*10000
    return result


def summarize(result):
    trades=result['trades'];closed=[p for p in trades if p['status']=='closed']
    def group(rows):
        completed=[p for p in rows if p['status']=='closed']
        return dict(trades=len(rows),closed=len(completed),open=sum(p['remaining']>0 for p in rows),
            wins=sum(p['net']>0 for p in completed),losses=sum(p['net']<=0 for p in completed),
            realized_net=sum(p['realized_leg_net'] for p in rows),unrealized_net=sum(p['unrealized_net_reference'] for p in rows),
            normalized_10000_realized=sum(p['normalized_10000_realized_net'] for p in rows),
            normalized_10000_unrealized=sum(p['normalized_10000_unrealized_net'] for p in rows),
            net_r=sum(p['net_r'] for p in completed))
    return dict(all=group(trades),no_flagged_gap=group([p for p in trades if not(p['gap_exposed'] or p['context_partial'])]),
        flagged_gap_or_context=group([p for p in trades if p['gap_exposed'] or p['context_partial']]),
        max_closed_trade_drawdown_r=result['metrics']['max_drawdown_r'],signal_counts=result['signal_counts'])


def execute(symbol,model,bars,quality,start,end,folder,control=None):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)');engine=make_engine(model,start,end,db)
    try:
        for b in bars:engine.minute(b)
        result=engine.finish();db.commit()
        if control is not None:
            assert result['trades']==control['trades'],model+' BTC control paths differ'
            assert result['metrics']==control['metrics'],model+' BTC control metrics differ'
        result.update(symbol=symbol,model=model,start=iso(start),end=iso(end),last_price=engine.last_price,
            policy=copy.deepcopy(POLICY),source_quality=quality,orders_enabled=False,status='complete')
        enrich(result,symbol,model,quality);result['summary']=summarize(result)
        export_csv(folder,result,db);save(folder/'result.json',result);return result
    finally:db.close()


def csv_table(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['status']);w.writeheader();w.writerows(rows)


def run():
    files,live=protected_state();release=STORE/'releases/0.2';ids=read(release/'REGISTRY.json')['0.2']['run_ids']
    controls={m:read(release/'results'/ids[m]/'result.json') for m in MODELS}
    ref=controls['0.1'];start=ts(ref['start']);end=ts(ref['end']);warmup=ts(ref['warmup_start'])
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-frozen02-crypto';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    code={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'scripts/retest_frozen_crypto.py')}
    study=dict(study_id=ident,status='downloading',start=iso(start),end=iso(end),warmup_start=iso(warmup),assets=list(ASSETS),
        models=list(MODELS),policy=POLICY,results={},source_quality={},btc_controls_reproduced={},original_live=live,
        rule_sha256=verify_rules(),study_code_sha256=code,orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files)
    inputs,quality=download(folder/'data',warmup,end)
    assert quality['BTC/USD']['frozen_source_sha256']==ref['source_minute_sha256']
    study.update(status='replaying',source_quality=quality);save(folder/'STUDY.json',study)
    results={}
    for symbol in ASSETS:
        study['results'][symbol]={}
        for model in MODELS:
            if symbol not in inputs:
                study['results'][symbol][model]=dict(status='unavailable',reason=quality[symbol]['reason']);continue
            r=execute(symbol,model,inputs[symbol],quality[symbol],start,end,folder/symbol.replace('/','_')/model,
                control=controls[model] if symbol=='BTC/USD' else None)
            results[(symbol,model)]=r;study['results'][symbol][model]=dict(status='complete',summary=r['summary'])
            if symbol=='BTC/USD':study['btc_controls_reproduced'][model]=True
            save(folder/'STUDY.json',study)
            print(json.dumps(dict(symbol=symbol,model=model,summary=r['summary'])),flush=True)
    trades=[];legs=[];summaries=[]
    for (symbol,model),r in results.items():
        for group,v in r['summary'].items():
            if group not in ('all','no_flagged_gap','flagged_gap_or_context'):continue
            summaries.append(dict(symbol=symbol,model=model,group=group,**v))
        for p in r['trades']:
            trades.append(dict(symbol=symbol,model=model,trade_id=p['id'],entry_rule=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],
                initial_stop_effective=p['entry_time'],initial_stop=p['initial_stop'],last_stop=p['stop'],target_25=p['t1'],
                status=p['status'],exit_time=p.get('exit_time'),remaining=p['remaining'],net=p.get('net'),
                realized_net=p['realized_leg_net'],unrealized_net=p['unrealized_net_reference'],
                normalized_10000_realized=p['normalized_10000_realized_net'],normalized_10000_unrealized=p['normalized_10000_unrealized_net'],
                gap_exposed=p['gap_exposed'],context_partial=p['context_partial'],actual_missing_minutes_while_held=p['actual_missing_minutes_while_held']))
            legs.extend(dict(symbol=symbol,model=model,trade_id=p['id'],**l) for l in p['legs'])
    csv_table(folder/'SUMMARY.csv',summaries);csv_table(folder/'TRADES.csv',trades);csv_table(folder/'EXITS.csv',legs)
    assert all(sha(ROOT/p)==h for p,h in files.items());assert all(sha(ROOT/p)==h for p,h in code.items())
    _,after=protected_state();assert after['pid']==live['pid'] and after['session']==live['session']
    study.update(status='complete',preserved_files_verified=len(files));save(folder/'STUDY.json',study)
    save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True);return study
