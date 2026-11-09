"""Alpaca BTC/USD minute archive. GET-only; raw responses and gaps are retained."""
from __future__ import annotations
import fcntl
import gzip
import hashlib
import json
import math
import os
import shlex
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'trading_records/btc_structure'
DATA_URL='https://data.alpaca.markets/v1beta3/crypto/us/bars'


def iso(t):
    return datetime.fromtimestamp(t,timezone.utc).isoformat().replace('+00:00','Z')


def ts(s):
    return int(datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n')
    temp.replace(path)


def read(path,default=None):
    return json.loads(path.read_text()) if path.exists() else default


def connect(store=STORE):
    store.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(store/'minutes.sqlite',timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS minutes(t INTEGER PRIMARY KEY,o REAL,h REAL,l REAL,c REAL,v REAL,n INTEGER,vw REAL)')
    return db


def normalize(rows,start,end):
    out=[];seen=set()
    for b in rows:
        t=ts(b['t'])
        if not start<=t<end:
            continue
        if t%60 or t in seen:
            raise ValueError('Duplicate/unaligned Alpaca minute')
        seen.add(t)
        o,h,l,c,v=(float(b[k]) for k in ('o','h','l','c','v'))
        if not all(math.isfinite(x) for x in (o,h,l,c,v)) or not 0<l<=min(o,c)<=max(o,c)<=h or v<0:
            raise ValueError('Invalid Alpaca OHLCV; missing observations are not filled')
        n=b.get('n');vw=b.get('vw')
        out.append((t,o,h,l,c,v,n,vw))
    return sorted(out)


def quality(store=STORE):
    if not (store/'minutes.sqlite').exists():
        return dict(count=0)
    db=sqlite3.connect(store/'minutes.sqlite',timeout=30)
    try:
        n,first,last,zero=db.execute('SELECT count(*),min(t),max(t),sum(CASE WHEN v=0 THEN 1 ELSE 0 END) FROM minutes').fetchone()
        return dict(count=n,first=iso(first) if first is not None else None,
            last=iso(last) if last is not None else None,zero_volume_bars=zero or 0,
            source='Alpaca US BTC/USD; bars may include quote midprices',
            missing_minutes=((last-first)//60+1-n) if n else 0)
    finally:
        db.close()


def credentials():
    """Read the existing paper credentials without importing an order runner."""
    env=ROOT/'.env'
    for line in env.read_text().splitlines() if env.exists() else []:
        key,sep,value=line.partition('=')
        if sep and key.strip() in ('ALPACA_API_KEY','ALPACA_API_SECRET','ALPACA_IS_PAPER'):
            parts=shlex.split(value,comments=True)
            if parts:os.environ.setdefault(key.strip(),parts[0])
    if os.environ.get('ALPACA_IS_PAPER','').lower()!='true':
        raise ValueError('ALPACA_IS_PAPER must be true')
    if not all(os.environ.get(k) for k in ('ALPACA_API_KEY','ALPACA_API_SECRET')):
        raise ValueError('Alpaca paper credentials are missing')
    return {'APCA-API-KEY-ID':os.environ['ALPACA_API_KEY'],
        'APCA-API-SECRET-KEY':os.environ['ALPACA_API_SECRET']}


def request_page(params):
    req=urllib.request.Request(DATA_URL+'?'+urllib.parse.urlencode(params),headers=credentials())
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):
            return None
    opener=urllib.request.build_opener(NoRedirect)
    for attempt in range(5):
        try:
            with opener.open(req,timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt==4:
                raise RuntimeError(f'Alpaca data HTTP {exc.code}; no credentials logged') from None
            time.sleep(min(30,float(exc.headers.get('Retry-After') or 2**attempt)))


def sync(history='recent',store=STORE,progress=None):
    """Archive all returned pages; recent first is a 37-day warmup+30-day study."""
    if history not in ('recent','all'):
        raise ValueError('history must be recent or all')
    store.mkdir(parents=True,exist_ok=True)
    with (store/'download.lock').open('w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return dict(status='running',message='An archive download is already running')
        end=int(time.time())//900*900
        start=ts('2016-01-01T00:00:00Z') if history=='all' else end-37*86400
        state_path=store/f'sync_{history}.json'
        previous=read(state_path,{})
        if previous.get('status') in ('running','error') and previous.get('next_page_token'):
            start=previous['start'];end=previous['end'];token=previous['next_page_token'];pages=previous['pages']
        else:
            token=None;pages=0
            if history=='all' and previous.get('status')=='complete':
                start=previous['end']
        if start>=end:
            return previous
        db=connect(store);raw_folder=store/'raw';raw_folder.mkdir(exist_ok=True)
        state=dict(status='running',history=history,start=start,end=end,pages=pages,next_page_token=token)
        try:
            seen=set()
            while True:
                params=dict(symbols='BTC/USD',timeframe='1Min',start=iso(start),end=iso(end),limit=10000,sort='asc')
                if token:
                    params['page_token']=token
                payload=request_page(params);page=json.loads(payload)
                rows=normalize((page.get('bars') or {}).get('BTC/USD',[]),start,end)
                sha=hashlib.sha256(payload).hexdigest();name=sha+'.json.gz'
                if not (raw_folder/name).exists():
                    (raw_folder/name).write_bytes(gzip.compress(payload))
                # Compare overlapping cached data instead of silently replacing it.
                for row in rows:
                    hit=db.execute('SELECT t,o,h,l,c,v,n,vw FROM minutes WHERE t=?',(row[0],)).fetchone()
                    if hit is not None and tuple(hit)!=row:
                        raise ValueError('Overlapping Alpaca observation changed; preserved cache requires review')
                db.executemany('INSERT OR IGNORE INTO minutes VALUES(?,?,?,?,?,?,?,?)',rows);db.commit()
                pages+=1;token=page.get('next_page_token')
                if token and token in seen:
                    raise ValueError('Repeated Alpaca pagination token')
                if token:
                    seen.add(token)
                state.update(pages=pages,next_page_token=token,last_page_count=len(rows),
                    last_observed=iso(rows[-1][0]) if rows else state.get('last_observed'),
                    updated_at=iso(int(time.time())),status='running' if token else 'complete')
                save(state_path,state)
                with (store/'sources.jsonl').open('a') as f:
                    f.write(json.dumps(dict(url=DATA_URL,params=params,sha256=sha,file=name,count=len(rows),retrieved_at=state['updated_at']))+'\n')
                if progress:
                    progress(state)
                if not token:
                    break
                time.sleep(.1)
            return state
        except Exception as exc:
            state.update(status='error',error=str(exc),updated_at=iso(int(time.time())))
            save(state_path,state)
            raise
        finally:
            db.close()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--history',choices=('recent','all'),default='recent')
    args=parser.parse_args()
    sync(args.history,progress=lambda s:print(json.dumps({k:s.get(k) for k in ('history','status','pages','last_observed')}),flush=True))
    print(json.dumps(quality()))
