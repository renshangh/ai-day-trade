"""Independent forward pattern discovery and normalized local paper positions.

This process never imports a broker client. Existing BTC workers and frozen
selectors are not used for mutable state. One observed unit is a comparison
convention, not funded allocation or a claimed broker fill.
"""
from __future__ import annotations
import copy
import fcntl
import gzip
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from trading_desk.btc_data import credentials,normalize,iso,ts,read,save
from trading_desk.btc_p1 import P1BaselineReplay
from trading_desk.btc_live import verify_rules
from trading_desk.pattern_library import HOME,features,match,create_library,library_digest
from scripts.btc_structure_retest import Config

NY=ZoneInfo('America/New_York')
DEFAULT_WATCHLIST=['BTC/USD','FN','AXTI','COHR','LITE','CRCL','SPY','QQQ']


def validate_watchlist(symbols):
    if not isinstance(symbols,list) or not 1<=len(symbols)<=24:raise ValueError('Use 1–24 symbols')
    out=list(dict.fromkeys(str(s).strip().upper() for s in symbols))
    if any(s!='BTC/USD' and not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',s) for s in out):
        raise ValueError('Use BTC/USD or US stock/ETF tickers')
    if 'BTC/USD' not in out:out.insert(0,'BTC/USD')
    if len(out)>24:raise ValueError('Maximum 24 symbols including BTC/USD')
    return out


def session_minutes(rows,symbol):
    if symbol=='BTC/USD':return rows
    return [b for b in rows if (d:=datetime.fromtimestamp(b['t'],NY)).weekday()<5
        and 570<=d.hour*60+d.minute<960]


class Source:
    """Read-only, pinned data host. IEX is explicitly a single stock venue."""
    def bars(self,symbol,start,end,folder):
        path='/v1beta3/crypto/us/bars' if symbol=='BTC/USD' else '/v2/stocks/bars'
        params=dict(symbols=symbol,timeframe='1Min',start=iso(start),end=iso(end),limit=10000,sort='asc')
        if symbol!='BTC/USD':params.update(feed='iex',adjustment='raw')
        rows=[];seen=set();raw=folder/'raw';raw.mkdir(parents=True,exist_ok=True)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        opener=urllib.request.build_opener(NoRedirect)
        while True:
            req=urllib.request.Request('https://data.alpaca.markets'+path+'?'+urllib.parse.urlencode(params),
                headers=credentials(),method='GET')
            try:
                with opener.open(req,timeout=15) as response:payload=response.read()
            except urllib.error.HTTPError as exc:
                raise ValueError(f'Alpaca market data HTTP {exc.code}; check data entitlement/credentials') from None
            digest=hashlib.sha256(payload).hexdigest();dest=raw/(digest+'.json.gz')
            if not dest.exists():dest.write_bytes(gzip.compress(payload))
            page=json.loads(payload);rows.extend((page.get('bars') or {}).get(symbol,[]))
            with (folder/'SOURCES.jsonl').open('a') as f:
                f.write(json.dumps(dict(symbol=symbol,params=params,sha256=digest,received_at=iso(time.time())))+'\n')
            token=page.get('next_page_token')
            if not token:break
            if token in seen or len(seen)>=100:raise ValueError('Repeated/excessive market-data pagination')
            seen.add(token);params['page_token']=token
        actual=normalize(rows,start,end)
        return session_minutes([dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in actual],symbol)


class PatternReplay(P1BaselineReplay):
    def __init__(self,*args,symbol,library,**kwargs):
        super().__init__(*args,expanded_b=True,consume_entry_history=True,b1_independent_hold=False,**kwargs)
        self.symbol=symbol;self.library=library;self.decisions=[];self.received_at=None;self.recovering=False

    def targets(self,entry,h1,t,atr):
        if self.symbol=='BTC/USD':return super().targets(entry,h1,t,atr)
        # US regular sessions have no fourteen consecutive hourly bars. Do not
        # quietly reinterpret missing overnight bars as 24h BTC observations.
        # This separate cross-asset draft uses only confirmed prominent 15m pivots.
        recent=list(self.recent);peaks=[]
        for i in range(2,len(recent)-2):
            b=recent[i];w=recent[i-2:i+3]
            if b['t']<t-7*86400 or any(x['observed_minutes']!=15 for x in w):continue
            if any(y['t']!=x['t']+900 for x,y in zip(w,w[1:])):continue
            if not all(b['high']>x['high'] for x in w if x is not b):continue
            prominence=min(b['high']-min(x['low'] for x in w[:2]),b['high']-min(x['low'] for x in w[3:]))
            if prominence>=atr and b['high']>max(entry,h1['high']):peaks.append(b['high'])
        targets=sorted(set(p-.1*atr for p in peaks if p-.1*atr>entry))
        return (targets[0],targets[1] if len(targets)>1 else None) if targets else (None,None)

    def open_signal(self,b,s):
        reason=None;comparison=None
        if s['route']!='B1':reason='No reviewed reference family for this route'
        elif s['context_partial']:reason='Missing/incomplete recent 15-minute entry context'
        else:
            comparison=match(features(s),self.library)
            if not comparison['accepted']:reason='Outside reference radius' if not comparison['within_radius'] else 'At least as close to a losing B1 lookalike'
        delay=self.received_at-(b['t']+60) if self.received_at is not None else None
        # Historical recovery reconstructs past legitimate decisions with their
        # original receipt clocks. Catch-up is never passed off as a fresh trade.
        if delay is None or delay<0 or delay>180:reason='Signal unavailable at a fresh observation time'
        d=dict(symbol=self.symbol,time_utc=s['time_utc'],available_after=s['interval_end'],
            detected_at=iso(self.received_at) if self.received_at is not None else None,delay_seconds=delay,
            route=s['route'],reference=s['entry_reference'],initial_stop=s['initial_stop'],target=s['t1'],
            match=comparison,accepted=reason is None,reason=reason,trade_id=None)
        self.decisions.append(d)
        if reason:
            s['decision']='pattern_rejected';return
        super().open_signal(b,s);d['trade_id']=s['trade_id']
        if self.position:self.position['pattern_match']=copy.deepcopy(comparison)


class Agent:
    def __init__(self,home=HOME,source=None,clock=time.time):
        self.home=home;self.source=source or Source();self.clock=clock
        self.library=None;self.engines={};self.ledgers={};self.db=None;self.local_lock=threading.Lock()

    def setup(self):
        self.home.mkdir(parents=True,exist_ok=True)
        if not (self.home/'LIBRARY.json').exists():
            if self.home!=HOME:raise ValueError('Create an explicit library first')
            create_library()
        self.library=read(self.home/'LIBRARY.json');now=int(self.clock());pinned=verify_rules()
        config=read(self.home/'CONFIG.json')
        if config is None:
            config=dict(watchlist=DEFAULT_WATCHLIST,enabled=True,activation=(now//60+1)*60,
                warmup_start=(now//86400-8)*86400,library_sha256=library_digest(self.library),
                frozen_engine_sha256=pinned,
                unit_convention='1 comparison unit per symbol; no funded account, cash budget or broker orders',
                stock_feed='IEX single venue, regular session only; transfer from BTC is experimental')
            save(self.home/'CONFIG.json',config)
        self.config=config
        if config.get('frozen_engine_sha256')!=pinned:raise ValueError('Frozen engine pin changed; review required')
        if config['library_sha256']!=library_digest(self.library):raise ValueError('Reference library changed; explicit new session required')
        if config['activation']<ts(self.library['training_end']):raise ValueError('Forward paper activation overlaps training history')
        validate_watchlist(config['watchlist'])
        self.db=sqlite3.connect(self.home/'OBSERVATIONS.sqlite',timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS bars(symbol TEXT,t INTEGER,body TEXT,received REAL,PRIMARY KEY(symbol,t))')
        self.db.commit()

    def engine(self,symbol):
        if symbol in self.engines:return self.engines[symbol]
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        e=PatternReplay(self.config['activation'],4102444800,db,
            Config(version='pattern-discovery-draft-1',first_sale_fraction=.25,resistance_mode='major1h'),
            symbol=symbol,library=self.library)
        for body,received in self.db.execute('SELECT body,received FROM bars WHERE symbol=? ORDER BY t',(symbol,)):
            e.received_at=received;e.minute(json.loads(body))
        self.engines[symbol]=e;self.ledgers[symbol]=db;return e

    def cycle(self):
        if not self.local_lock.acquire(blocking=False):return
        self.home.mkdir(parents=True,exist_ok=True)
        try:
            with (self.home/'WORKER.lock').open('a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:return
                if self.db is None:self.setup()
                latest=read(self.home/'CONFIG.json');self.config=latest
                if latest['library_sha256']!=library_digest(self.library):raise ValueError('Library changed; restart in an explicit new session')
                now=self.clock();end=int(now)//60*60
                state=dict(status='running' if latest['enabled'] else 'paused',pid=os.getpid(),updated_at=iso(now),
                    activation=iso(latest['activation']),watchlist=latest['watchlist'],symbols=[],orders_enabled=False,
                    broker_paper_orders=False,mode='local normalized paper comparison',library_version=self.library['version'])
                if not latest['enabled']:
                    state['symbols']=read(self.home/'STATUS.json',{}).get('symbols',[])
                    save(self.home/'STATUS.json',state);return
                for symbol in latest['watchlist']:
                    try:
                        e=self.engine(symbol);start=e.last_minute+60 if e.last_minute is not None else latest['warmup_start']
                        # No current partial minute, backfilled prices or implicit warmup positions.
                        rows=self.source.bars(symbol,start,end,self.home) if start<end else []
                        received=self.clock()
                        if rows and (rows[0]['t']<start or any(y['t']<=x['t'] for x,y in zip(rows,rows[1:]))):
                            raise ValueError('Out-of-order source observations')
                        try:
                            for b in rows:
                                if b['t']+60>end:raise ValueError('Partial/future source minute')
                                self.db.execute('INSERT INTO bars VALUES(?,?,?,?)',(symbol,b['t'],json.dumps(b,sort_keys=True),received))
                                e.received_at=received;e.minute(b)
                            self.db.commit()
                        except Exception:
                            self.db.rollback();self.engines.pop(symbol,None);self.ledgers.pop(symbol).close();raise
                        open_p=copy.deepcopy(e.position)
                        if open_p:
                            open_p['unrealized_net_reference']=open_p['remaining']*(e.last_price-open_p['entry'])-open_p['remaining']*(e.last_price+open_p['entry'])*.0002
                        clean=lambda p:{k:copy.deepcopy(p.get(k)) for k in ('id','entry_time','entry','initial_stop','stop','t1','remaining',
                            'entry_rule','legs','exit_time','net','net_r','references','pattern_match','unrealized_net_reference','gap_exposed','context_partial')}
                        market_open=symbol=='BTC/USD' or (datetime.fromtimestamp(now,NY).weekday()<5 and 570<=datetime.fromtimestamp(now,NY).hour*60+datetime.fromtimestamp(now,NY).minute<960)
                        age=received-(e.last_minute+60) if e.last_minute is not None else None
                        state['symbols'].append(dict(symbol=symbol,status='fresh' if age is not None and 0<=age<=180 else
                            'session closed' if not market_open else 'data stale/unavailable',
                            last_bar=iso(e.last_minute) if e.last_minute is not None else None,last=e.last_price,age_seconds=age,
                            source='Alpaca US crypto' if symbol=='BTC/USD' else latest['stock_feed'],
                            new_minutes=len(rows),open_position=clean(open_p) if open_p else None,
                            closed_trades=[clean(p) for p in e.trades],decisions=copy.deepcopy(e.decisions),
                            realized_net=sum(p['net'] for p in e.trades),observed_minutes=self.db.execute('SELECT count(*) FROM bars WHERE symbol=?',(symbol,)).fetchone()[0],
                            data_gaps=e.counter.get('gap_count',0),setups=e.detector.snapshot()))
                    except Exception as exc:
                        previous=read(self.home/'STATUS.json',{})
                        old=next((x for x in previous.get('symbols',[]) if x['symbol']==symbol),{})
                        state['symbols'].append(dict(copy.deepcopy(old),symbol=symbol,status='unavailable; saved observations only',
                            error=str(exc) if isinstance(exc,ValueError) else type(exc).__name__+'; see local source/setup',
                            previous_saved_results=previous.get('updated_at')))
                    state['updated_at']=iso(self.clock());save(self.home/'STATUS.json',state)
                state['cycle_complete']=True;save(self.home/'STATUS.json',state)
        finally:self.local_lock.release()

    def close(self):
        for db in self.ledgers.values():db.close()
        if self.db:self.db.close()


def snapshot(home=HOME):
    state=read(home/'STATUS.json',dict(status='not started',symbols=[],orders_enabled=False))
    state['heartbeat_age_seconds']=time.time()-ts(state['updated_at']) if state.get('updated_at') else None
    state['worker_fresh']=bool(state['heartbeat_age_seconds'] is not None and 0<=state['heartbeat_age_seconds']<180)
    state['library']=read(home/'LIBRARY.json');state['config']=read(home/'CONFIG.json')
    state['universe_screen']=read(home/'UNIVERSE_SCREEN.json')
    error=read(home/'ERROR.json')
    if error and (not state.get('updated_at') or ts(error['at'])>=ts(state['updated_at'])):
        state['error']=error;state['status']='error';state['worker_fresh']=False
    return state


def configure(symbols,enabled,home=HOME):
    if type(enabled) is not bool:raise ValueError('enabled must be true or false')
    symbols=validate_watchlist(symbols)
    with (home/'WORKER.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Scan in progress; save after this cycle finishes') from None
        config=read(home/'CONFIG.json')
        if not config:raise ValueError('Initialize discovery worker first')
        # Removed symbols with local positions must continue receiving protection.
        state=read(home/'STATUS.json',{})
        held={x['symbol'] for x in state.get('symbols',[]) if x.get('open_position')}
        if held-set(symbols):raise ValueError('Keep symbols with open paper positions in the scan list')
        config.update(watchlist=symbols,enabled=enabled);save(home/'CONFIG.json',config)
    return dict(saved=True,watchlist=symbols,enabled=enabled,orders_enabled=False)
