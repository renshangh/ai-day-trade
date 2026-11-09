"""Persistent, GET-only BTC/USD forward comparison. Never submits broker orders.

The frozen engines consume completed observed minutes. Their historical
reference events are benchmarks, NOT live fills: receipt/detection time is
stored separately and never backdated. Restart reconstructs from immutable
observations and inserts events idempotently, without finish() mutating state.
"""
from __future__ import annotations

import copy
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo

from trading_desk import btc_data
from trading_desk.btc_engine import create_replay
from trading_desk.btc_early_sequential import EarlySequentialReplay
from scripts.btc_structure_retest import Config

ROOT=btc_data.ROOT
LIVE=btc_data.STORE/'live'
MODELS=('0.1','E1','E2')
WARMUP=7*86400
POLL_SECONDS=15
STALE_SECONDS=180
QUOTE_URL='https://data.alpaca.markets/v1beta3/crypto/us/latest/quotes'
RULE_FILES=['trading_desk/'+n+'.py' for n in (
    'btc_engine','btc_ab_replay','btc_entry_detector','btc_entry_rules',
    'btc_shock_branches','btc_approved_exits','btc_guarded_replay',
    'btc_structure_exits','btc_turning_replay','btc_failed_rebound','btc_early_sequential')]
RULE_FILES+=['scripts/btc_structure_retest.py','scripts/audit_btc_release01_early_failure.py']
NY=ZoneInfo('America/New_York')


class DataConflict(ValueError):
    pass


def verify_rules(root=ROOT):
    manifest=btc_data.read(root/'trading_records/btc_structure/releases/0.2/MANIFEST.json')
    if not manifest or manifest.get('version')!='0.2':
        raise ValueError('Install the verified BTC research 0.2 bundle first')
    hashes={}
    for name in RULE_FILES:
        digest=hashlib.sha256((root/name).read_bytes()).hexdigest()
        if digest!=manifest['files_sha256'].get('source/'+name):
            raise ValueError('Trading rule source differs from release 0.2: '+name)
        hashes[name]=digest
    return hashes


def open_store(folder):
    folder.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(folder/'observations.sqlite',timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS minutes(t INTEGER PRIMARY KEY,body TEXT NOT NULL,received REAL NOT NULL,sha TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,model TEXT,kind TEXT,ref INTEGER,detected REAL,body TEXT)')
    db.execute('CREATE INDEX IF NOT EXISTS event_clock ON events(detected,ref)')
    db.execute('CREATE TABLE IF NOT EXISTS signals(id TEXT PRIMARY KEY,model TEXT,ref INTEGER,detected REAL,body TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS ledger(model TEXT,t INTEGER,body TEXT,PRIMARY KEY(model,t))')
    return db


def compact_position(p):
    if not p:return None
    fields=('id','entry','entry_time','initial_stop','stop','t1','remaining','entry_rule',
        'references','legs','gap_exposed','context_partial','structure_history',
        'failed_rebound_history','stop_history','initial_risk')
    return copy.deepcopy({k:p.get(k) for k in fields if k in p})


class Comparison:
    """One process-local engine per model; durable input/event records own recovery."""
    def __init__(self,folder,session):
        self.folder=folder;self.session=session;self.db=open_store(folder)
        self.engines={};self.ledgers={};self.last_rows={};self.signal_counts={}
        self.last=None
        for model in MODELS:
            ledger=sqlite3.connect(':memory:')
            ledger.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
            if model=='0.1':
                engine=create_replay(session['start'],4102444800,ledger,expanded_b=True,exit_version='failed_rebound')
            else:
                engine=EarlySequentialReplay(session['start'],4102444800,ledger,
                    Config(first_sale_fraction=.25,resistance_mode='major1h'),early_policy=model,
                    expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
            self.engines[model]=engine;self.ledgers[model]=ledger
            self.last_rows[model]=-1;self.signal_counts[model]=0

    def recover(self):
        for body,received in self.db.execute('SELECT body,received FROM minutes ORDER BY t'):
            self.feed(json.loads(body),received)
        self.db.commit()

    def event(self,model,event,received):
        ref=btc_data.ts(event['time_utc'])
        if ref<self.session['start']:return
        payload=dict(model=model,**copy.deepcopy(event),reference_time=event['time_utc'],
            detected_at=btc_data.iso(received),detection_delay_seconds=max(0,received-ref),
            comparison_execution='reference_only',broker_fill=False)
        key=hashlib.sha256(json.dumps([model,event],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?)',
            (key,model,event['type'],ref,received,json.dumps(payload,ensure_ascii=False)))

    def feed(self,bar,received):
        if self.last is not None and bar['t']<=self.last:raise ValueError('Non-monotonic observation')
        if received<bar['t']+60:raise ValueError('Minute was not complete at receipt')
        for model,engine in self.engines.items():
            engine.minute(bar)
            for t,body in engine.db.execute('SELECT t,body FROM ledger WHERE t>? ORDER BY t',(self.last_rows[model],)):
                row=json.loads(body)
                self.db.execute('INSERT OR IGNORE INTO ledger VALUES(?,?,?)',(model,t,body))
                for event in row['events']:self.event(model,event,received)
                self.last_rows[model]=t
            for event in engine.events:self.event(model,event,received)
            for signal in engine.signals[self.signal_counts[model]:]:
                payload=dict(**copy.deepcopy(signal),model=model,detected_at=btc_data.iso(received),
                    detection_delay_seconds=max(0,received-btc_data.ts(signal['time_utc'])),
                    comparison_execution='reference_only',broker_fill=False)
                key=hashlib.sha256(json.dumps([model,signal['time_utc'],signal['route'],
                    signal['references']],sort_keys=True).encode()).hexdigest()
                self.db.execute('INSERT OR IGNORE INTO signals VALUES(?,?,?,?,?)',
                    (key,model,btc_data.ts(signal['time_utc']),received,json.dumps(payload,ensure_ascii=False)))
            self.signal_counts[model]=len(engine.signals)
        self.last=bar['t']

    def ingest(self,rows,received,sha):
        for bar in rows:
            if received<bar['t']+60:raise ValueError('Incomplete minute')
            body=json.dumps(bar,sort_keys=True,separators=(',',':'))
            old=self.db.execute('SELECT body FROM minutes WHERE t=?',(bar['t'],)).fetchone()
            if old:
                if old[0]!=body:raise DataConflict('Provider revised an already used observation')
                continue
            if self.last is not None and bar['t']<=self.last:
                raise DataConflict('Late earlier observation requires explicit replay review')
            self.db.execute('INSERT INTO minutes VALUES(?,?,?,?)',(bar['t'],body,received,sha))
            self.feed(bar,received)
        self.db.commit()

    def snapshot(self,now):
        models=[]
        for model,engine in self.engines.items():
            closed=engine.trades
            realized=sum(l['net'] for p in closed for l in p['legs'])
            if engine.position:realized+=sum(l['net'] for l in engine.position['legs'])
            unrealized=0
            if engine.position:
                p=engine.position
                unrealized=p['remaining']*((engine.last_price-p['entry'])-(engine.last_price+p['entry'])*.0002)
            models.append(dict(model=model,closed=len(closed),wins=sum(p['net']>0 for p in closed),
                losses=sum(p['net']<=0 for p in closed),closed_net=sum(p['net'] for p in closed),
                realized_leg_net=realized,open_benchmark_net=unrealized,marked_benchmark_net=realized+unrealized,
                mark_price=engine.last_price,mark_minute=btc_data.iso(engine.last_t) if engine.last_t is not None else None,
                position=compact_position(engine.position),
                setups=engine.detector.snapshot(),next_previous_high_trigger=engine.prev['high']+.01 if engine.prev else None,
                trigger_note='Reference only; eligibility still requires all unchanged entry checks',
                last_completed_15m=btc_data.iso(engine.prev['t']) if engine.prev else None,
                atr=engine.atr,signals=len(engine.signals),gap_count=engine.counter.get('gap_count',0),
                missing_minutes=engine.counter.get('missing_minutes',0)))
        count,first,last=self.db.execute('SELECT count(*),min(t),max(t) FROM minutes').fetchone()
        return dict(models=models,observed_minutes=count,first_observed=btc_data.iso(first) if first is not None else None,
            last_observed=btc_data.iso(last) if last is not None else None,
            minute_end=btc_data.iso(last+60) if last is not None else None,
            data_age_seconds=max(0,now-last-60) if last is not None else None)

    def close(self):
        self.db.commit();self.db.close()
        for db in self.ledgers.values():db.close()


class AlpacaSource:
    """Pinned data host, GET-only, no broker client or order endpoint."""
    def quote(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        request=urllib.request.Request(QUOTE_URL+'?'+urllib.parse.urlencode({'symbols':'BTC/USD'}),
            headers=btc_data.credentials(),method='GET')
        with urllib.request.build_opener(NoRedirect).open(request,timeout=10) as r:
            body=json.load(r)
        q=(body.get('quotes') or {}).get('BTC/USD')
        if not q:raise ValueError('No BTC/USD quote')
        btc_data.ts(q['t']);bid=float(q['bp']);ask=float(q['ap'])
        if not all(math.isfinite(x) for x in (bid,ask)) or not 0<bid<=ask:raise ValueError('Invalid quote')
        return dict(time=q['t'],bid=bid,ask=ask,mid=(bid+ask)/2,source='Alpaca BTC/USD quote',
            execution='reference_only_not_a_fill')

    def bars(self,start,end,folder):
        token=None;seen=set();output=[];raw=folder/'raw';raw.mkdir(exist_ok=True)
        while True:
            params=dict(symbols='BTC/USD',timeframe='1Min',start=btc_data.iso(start),
                end=btc_data.iso(end),limit=10000,sort='asc')
            if token:params['page_token']=token
            payload=btc_data.request_page(params);page=json.loads(payload)
            digest=hashlib.sha256(payload).hexdigest()
            path=raw/(digest+'.json.gz')
            if not path.exists():path.write_bytes(gzip.compress(payload))
            rows=btc_data.normalize((page.get('bars') or {}).get('BTC/USD',[]),start,end)
            output.extend(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in rows)
            with (folder/'SOURCES.jsonl').open('a') as f:
                f.write(json.dumps(dict(start=start,end=end,sha256=digest,count=len(rows),
                    received_at=btc_data.iso(time.time()),path=str(path.relative_to(folder))))+'\n')
            token=page.get('next_page_token')
            if not token:break
            if token in seen:raise ValueError('Repeated provider page token')
            seen.add(token)
        if any(b['t']<=a['t'] for a,b in zip(output,output[1:])):raise ValueError('Repeated/unordered provider bars')
        return output,hashlib.sha256(json.dumps(output,sort_keys=True).encode()).hexdigest()


class Controller:
    """UI controls record intent; a separately supervised worker owns engines."""
    def __init__(self,root=LIVE):self.root=root;self.lock=threading.Lock()

    def control(self,operation):
        if operation not in ('start','pause'):raise ValueError('Choose start or pause')
        with self.lock:
            self.root.mkdir(parents=True,exist_ok=True)
            value=dict(enabled=operation=='start',updated_at=btc_data.iso(time.time()),mode='comparison_only')
            btc_data.save(self.root/'CONTROL.json',value)
        return value

    def status(self,model='0.1',day=None):
        if model not in MODELS:raise ValueError('Unknown comparison model')
        if day:
            try:datetime.strptime(day,'%Y-%m-%d')
            except (ValueError,TypeError):raise ValueError('Use YYYY-MM-DD for date') from None
        state=btc_data.read(self.root/'STATUS.json',{})
        control=btc_data.read(self.root/'CONTROL.json',{})
        now=time.time();heartbeat=state.get('heartbeat_epoch')
        online=heartbeat is not None and 0<=now-heartbeat<max(60,POLL_SECONDS*4)
        age=state.get('data_age_seconds')
        last=state.get('minute_end')
        if last:age=max(0,now-btc_data.ts(last))
        quote=state.get('quote')
        quote_age=now-btc_data.ts(quote['time']) if quote else None
        health=('paused' if not control.get('enabled') else 'offline' if not online
            else state.get('status','starting'))
        if health=='running' and (age is None or age>STALE_SECONDS):health='stale'
        result=dict(state)
        result.update(health=health,online=online,enabled=bool(control.get('enabled')),
            data_age_seconds=age,quote_age_seconds=quote_age,quote_fresh=quote_age is not None and 0<=quote_age<=60,
            orders_enabled=False,broker_orders_enabled=False,mode='comparison_only',
            instrument='BTC/USD',release='0.2',poll_seconds=POLL_SECONDS,
            cost_note='Frozen benchmark: initial 1 BTC per trade; 2bps/side ETF-cost proxy. Not actual BTC fees, ETF returns or broker paper fills.',
            timing_note='Completed observed 1m bars, polled every 15s. Market reference time differs from detection/receipt time; no backdated fills.',
            execution_blockers=['Comparison-only mode selected by owner; no broker order client is loaded'],
            selected_model=model,signals=[],events=[],rows=[])
        result['supervision']=btc_data.read(self.root/'SUPERVISION.json',{})
        session=state.get('session',{});ident=session.get('id')
        if not ident or not isinstance(ident,str) or not all(c.isdigit() or c in 'TZ-' for c in ident):return result
        path=self.root/'sessions'/ident/'observations.sqlite'
        if not path.exists():return result
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10) as db:
            result['signals']=[json.loads(x[0]) for x in db.execute('SELECT body FROM signals WHERE model=? ORDER BY ref DESC LIMIT 100',(model,))]
            result['events']=[json.loads(x[0]) for x in db.execute('SELECT body FROM events WHERE model=? ORDER BY ref DESC,detected DESC LIMIT 150',(model,))]
            if day:
                midnight=datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=NY)
                end=midnight+timedelta(days=1)
                result['rows']=[json.loads(x[0]) for x in db.execute(
                    'SELECT body FROM ledger WHERE model=? AND t>=? AND t<? ORDER BY t LIMIT 100',
                    (model,int(midnight.timestamp()),int(end.timestamp())))]
            else:
                result['rows']=list(reversed([json.loads(x[0]) for x in db.execute('SELECT body FROM ledger WHERE model=? ORDER BY t DESC LIMIT 80',(model,))]))
        return result


class Worker:
    def __init__(self,root=LIVE,source=None,clock=time.time,rule_check=verify_rules,supervision=None):
        self.root=root;self.source=source or AlpacaSource();self.clock=clock;self.rule_check=rule_check
        self.comparison=None;self.state={}
        self.supervision=supervision

    def publish(self,status,**extra):
        now=self.clock()
        self.state.update(status=status,heartbeat_epoch=now,heartbeat=btc_data.iso(now),
            pid=os.getpid(),**extra)
        if self.comparison:self.state.update(self.comparison.snapshot(now))
        btc_data.save(self.root/'STATUS.json',self.state)

    def initialize(self):
        hashes=self.rule_check()
        session=btc_data.read(self.root/'SESSION.json')
        if not session:
            now=self.clock();start=(int(now)//60+1)*60
            session=dict(id=datetime.fromtimestamp(now,ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ'),
                start=start,created_at=btc_data.iso(now),warmup_start=start-WARMUP,
                rule_sha256=hashes,release='0.2',mode='comparison_only')
            btc_data.save(self.root/'SESSION.json',session)
        if session['rule_sha256']!=hashes:raise ValueError('Persisted session trading rule hashes differ')
        folder=self.root/'sessions'/session['id']
        self.comparison=Comparison(folder,session)
        self.publish('recovering',session=session,error=None)
        self.comparison.recover()
        self.publish('warming_up',session=session,error=None)

    def tick(self):
        self.root.mkdir(parents=True,exist_ok=True)
        control=btc_data.read(self.root/'CONTROL.json',{})
        if not control.get('enabled'):
            self.publish('paused');return
        if self.comparison is None:self.initialize()
        now=self.clock();engine=self.comparison;end=int(now)//60*60
        start=(engine.last+60 if engine.last is not None else engine.session['warmup_start'])
        if start<end:
            self.publish('catching_up' if engine.last else 'warming_up',error=None)
            # Only append later observations; do not retroactively insert missing
            # minutes or revise the used stream. Gaps remain explicit in engines.
            rows,sha=self.source.bars(start,end,engine.folder)
            received=self.clock();engine.ingest(rows,received,sha)
        quote=None;quote_error=None
        try:
            quote=self.source.quote();age=self.clock()-btc_data.ts(quote['time'])
            if not 0<=age<=60:quote_error='Quote is stale or future-dated; reference unavailable'
        except Exception:
            quote_error='Current BTC/USD quote unavailable; no substituted quote'
        self.publish('running',quote=quote,quote_error=quote_error,error=None)

    def discard_uncommitted(self):
        if self.comparison:
            self.comparison.db.rollback()
            self.comparison.close()
            self.comparison=None

    def cycle(self):
        try:self.tick()
        except DataConflict:
            # Keep the last committed snapshot, never the in-memory state from
            # a rejected batch, while pausing for explicit data review.
            self.discard_uncommitted()
            btc_data.save(self.root/'CONTROL.json',dict(enabled=False,reason='data_conflict'))
            self.publish('data_conflict',error='A used observation conflicts with provider data; comparison paused for review.')
        except Exception as exc:
            self.discard_uncommitted()
            self.publish('error',error=type(exc).__name__+': BTC data/initialization unavailable; comparison only, no order attempted.')

    def run(self):
        self.root.mkdir(parents=True,exist_ok=True)
        with (self.root/'worker.lock').open('w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('A BTC comparison worker already owns this store') from None
            if self.supervision:
                # Publish ownership only after taking the writer lock. A second
                # launchd attempt must not overwrite a running owner's metadata.
                btc_data.save(self.root/'SUPERVISION.json',dict(self.supervision,
                    worker_pid=os.getpid(),parent_pid=os.getppid(),verified_at=btc_data.iso(self.clock())))
                print(json.dumps(dict(event='comparison_worker_owned',time=btc_data.iso(self.clock()),
                    mode=self.supervision['mode'],pid=os.getpid(),orders_enabled=False)),flush=True)
            while True:
                self.cycle()
                time.sleep(POLL_SECONDS)


CONTROLLER=Controller()
