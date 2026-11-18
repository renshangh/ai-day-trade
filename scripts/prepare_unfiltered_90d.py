"""Independent earlier BTC/SOL observations; never changes shared/live archives."""
from __future__ import annotations
import gzip,hashlib,json,sqlite3,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso,normalize,request_page
from trading_desk.crypto_transfer import STUDIES,sha


def run():
    source=STUDIES/read(STUDIES/'ACTIVE.json')['study_id'];s=read(source/'STUDY.json')
    end=ts(s['end']);start=end-97*86400;join=ts(s['warmup_start'])
    folder=STORE/'unfiltered_90_inputs'/f'{start}-{join}';folder.mkdir(parents=True,exist_ok=True)
    done=read(folder/'QUALITY.json')
    if done and all(sha(folder/(a.replace('/','_')+'_PREFIX.jsonl.gz'))==v['archive_sha256'] for a,v in done.items()):
        print('Existing independently archived prefix verified',flush=True);return
    cache=STORE/'minutes.sqlite';rows=[];digest=hashlib.sha256()
    with sqlite3.connect(cache.as_uri()+'?mode=ro',uri=True) as db:
        for t,o,h,l,c,v,n,vw in db.execute('SELECT t,o,h,l,c,v,n,vw FROM minutes WHERE t>=? AND t<? ORDER BY t',(start,join)):
            raw=dict(t=iso(t),o=o,h=h,l=l,c=c,v=v,n=n,vw=vw)
            normalize([raw],start,join) # Validate stored actual observations, never fill gaps.
            b=dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n);rows.append(b);digest.update((json.dumps(b,sort_keys=True)+'\n').encode())
    if not rows:raise RuntimeError('No cached actual BTC prefix observations; do not fabricate')
    inputs={'BTC/USD':rows};manifest=dict(start=iso(start),end=iso(join),btc_source=dict(type='read-only existing Alpaca cache SELECT',
        path=str(cache.relative_to(ROOT)),selected_observations_sha256=digest.hexdigest(),rows=len(rows)),sol_pages=[])
    log=STORE/'sources.jsonl'
    if log.exists():manifest['btc_source']['cached_source_manifest_sha256']=sha(log)
    rawfolder=folder/'raw';rawfolder.mkdir(exist_ok=True);token=None;seen=set();sol=[]
    while True:
        params=dict(symbols='SOL/USD',timeframe='1Min',start=iso(start),end=iso(join),limit=10000,sort='asc')
        if token:params['page_token']=token
        payload=request_page(params);digest=hashlib.sha256(payload).hexdigest();path=rawfolder/(digest+'.json.gz')
        if not path.exists():path.write_bytes(gzip.compress(payload))
        page=json.loads(payload);received=(page.get('bars') or {}).get('SOL/USD',[]);sol.extend(received)
        manifest['sol_pages'].append(dict(params=params,raw_sha256=digest,file=str(path.relative_to(folder)),received_at=iso(time.time()),rows=len(received)))
        save(folder/'SOURCES.json',manifest);print(json.dumps(dict(sol_page=len(manifest['sol_pages']),sol_rows=len(sol),btc_rows=len(rows))),flush=True)
        token=page.get('next_page_token')
        if not token:break
        if token in seen or len(seen)>=100:raise RuntimeError('Repeated/excessive market-data pagination')
        seen.add(token);time.sleep(.1)
    actual=normalize(sol,start,join)
    if not actual:raise RuntimeError('SOL earlier observations unavailable; no invented 90-day result')
    inputs['SOL/USD']=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in actual]
    quality={};expected=set(range(start,join,60))
    for symbol,bars in inputs.items():
        p=folder/(symbol.replace('/','_')+'_PREFIX.jsonl.gz')
        with gzip.open(p,'wt') as z:
            for b in bars:z.write(json.dumps(b,sort_keys=True)+'\n')
        quality[symbol]=dict(observed=len(bars),expected=len(expected),missing=sorted(expected-{b['t'] for b in bars}),archive_sha256=sha(p),
            first=iso(bars[0]['t']),last=iso(bars[-1]['t']),source='Original read-only Alpaca BTC cache' if symbol=='BTC/USD' else 'New approved Alpaca market-data GET only')
    save(folder/'QUALITY.json',quality);print('PREFIX COMPLETE',folder.name,flush=True)

if __name__=='__main__':run()
