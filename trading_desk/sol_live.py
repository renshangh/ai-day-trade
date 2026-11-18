"""Isolated SOL/USD E1 forward benchmark and durable human-review outbox.

Reuse the immutable BTC observation/recovery contract, without mutating its
worker, data, session, models or strategy files. No broker client is loaded.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager, closing
from datetime import datetime
from zoneinfo import ZoneInfo

from trading_desk import btc_data, btc_live
from trading_desk.btc_early_sequential import EarlySequentialReplay
from scripts.btc_structure_retest import Config

HOME=btc_data.ROOT/'trading_records/sol_live'
SYMBOL='SOL/USD'
MODEL='E1'


class Comparison(btc_live.Comparison):
    def __init__(self,folder,session):
        self.folder=folder;self.session=session;self.db=btc_live.open_store(folder)
        ledger=sqlite3.connect(':memory:')
        ledger.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        self.engines={MODEL:EarlySequentialReplay(session['start'],4102444800,ledger,
            Config(first_sale_fraction=.25,resistance_mode='major1h'),early_policy=MODEL,
            expanded_b=True,consume_entry_history=True,b1_independent_hold=False)}
        self.ledgers={MODEL:ledger};self.last_rows={MODEL:-1};self.signal_counts={MODEL:0};self.last=None


class AlpacaSource:
    """Only pinned Alpaca market-data GET requests; no broker/order endpoint."""
    def bars(self,start,end,folder):
        token=None;seen=set();output=[];raw=folder/'raw';raw.mkdir(exist_ok=True)
        while True:
            params=dict(symbols=SYMBOL,timeframe='1Min',start=btc_data.iso(start),
                end=btc_data.iso(end),limit=10000,sort='asc')
            if token:params['page_token']=token
            payload=btc_data.request_page(params);page=json.loads(payload)
            digest=hashlib.sha256(payload).hexdigest();path=raw/(digest+'.json.gz')
            if not path.exists():path.write_bytes(gzip.compress(payload))
            rows=btc_data.normalize((page.get('bars') or {}).get(SYMBOL,[]),start,end)
            output.extend(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in rows)
            with (folder/'SOURCES.jsonl').open('a') as f:
                f.write(json.dumps(dict(symbol=SYMBOL,params=params,sha256=digest,count=len(rows),
                    received_at=btc_data.iso(time.time()),path=str(path.relative_to(folder))))+'\n')
            token=page.get('next_page_token')
            if not token:break
            if token in seen:raise ValueError('Repeated provider page token')
            seen.add(token)
        if any(b['t']<=a['t'] for a,b in zip(output,output[1:])):raise ValueError('Repeated/unordered observations')
        return output,hashlib.sha256(json.dumps(output,sort_keys=True).encode()).hexdigest()

    def quote(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        request=urllib.request.Request(btc_live.QUOTE_URL+'?'+urllib.parse.urlencode({'symbols':SYMBOL}),
            headers=btc_data.credentials(),method='GET')
        with urllib.request.build_opener(NoRedirect).open(request,timeout=10) as r:body=json.load(r)
        q=(body.get('quotes') or {}).get(SYMBOL)
        if not q:raise ValueError('No SOL/USD quote')
        btc_data.ts(q['t']);bid=float(q['bp']);ask=float(q['ap'])
        if not all(math.isfinite(x) for x in (bid,ask)) or not 0<bid<=ask:raise ValueError('Invalid quote')
        return dict(time=q['t'],bid=bid,ask=ask,mid=(bid+ask)/2,source='Alpaca SOL/USD quote',
            execution='reference_only_not_a_fill')


class Outbox:
    """Own review database; source BTC/SOL observation databases are read-only.

    Approving acknowledges a paper proposal. It never fills, changes an engine,
    or creates a broker order. Delivery and human decisions are separate fields.
    """
    def __init__(self,root=HOME,btc_root=btc_live.LIVE,clock=time.time):
        self.root=root;self.btc_root=btc_root;self.clock=clock

    def open(self):
        self.root.mkdir(parents=True,exist_ok=True)
        db=sqlite3.connect(self.root/'approvals.sqlite',timeout=15)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS proposals(id TEXT PRIMARY KEY,symbol TEXT,model TEXT,session TEXT,event_id TEXT,ref INTEGER,detected REAL,created REAL,body TEXT,decision TEXT,decided REAL,notified REAL)')
        db.execute('INSERT OR IGNORE INTO meta VALUES(?,?)',('activation',str(self.clock())))
        db.commit();return db

    @contextmanager
    def store(self):
        db=self.open()
        try:
            with db:yield db
        finally:db.close()

    def collect(self):
        with self.store() as db:
            activation=float(db.execute("SELECT value FROM meta WHERE key='activation'").fetchone()[0])
            for symbol,root in (('BTC/USD',self.btc_root),(SYMBOL,self.root)):
                state=btc_data.read(root/'STATUS.json',{});session=state.get('session',{});ident=session.get('id')
                if not ident or not all(c.isdigit() or c in 'TZ-' for c in ident):continue
                path=root/'sessions'/ident/'observations.sqlite'
                if not path.exists():continue
                with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)) as source:
                    events=source.execute('SELECT id,model,ref,detected,body FROM events WHERE ref>=? AND detected>=? ORDER BY ref,detected,id',(activation,activation)).fetchall()
                    for event_id,model,ref,detected,raw in events:
                        e=json.loads(raw)
                        if e['type']!='entry' and not(e.get('fraction',0)>0):continue
                        key=hashlib.sha256(json.dumps([symbol,ident,event_id]).encode()).hexdigest()[:24]
                        if db.execute('SELECT 1 FROM proposals WHERE id=?',(key,)).fetchone():continue
                        entry=None
                        for body, in source.execute("SELECT body FROM signals WHERE model=? AND ref<=? ORDER BY ref DESC",(model,ref)):
                            candidate=json.loads(body)
                            if candidate.get('decision')=='entry' and candidate.get('trade_id')==e.get('trade_id'):
                                entry=candidate;break
                        payload=dict(id=key,symbol=symbol,model=model,session=ident,trade_id=e.get('trade_id'),
                            action='entry' if e['type']=='entry' else 'exit',reason=e['type'],
                            reference_time=e['reference_time'],known_no_earlier_than=btc_data.iso(ref+60),
                            detected_at=e['detected_at'],price=e.get('price'),fraction=1 if e['type']=='entry' else e['fraction'],
                            initial_stop=entry.get('initial_stop') if entry else None,target_25=entry.get('t1') if entry else None,
                            entry_rule=entry.get('route') if entry else None,references=entry.get('references') if entry else None,
                            comparison_only=True,broker_fill=False,orders_enabled=False,
                            approval_effect='Paper review acknowledgment only; no fill or strategy modification')
                        # Later exits supersede unreviewed entries/partial exits;
                        # the original events remain visible as historical evidence.
                        if payload['action']=='exit':
                            for prior_id,prior_body in db.execute("SELECT id,body FROM proposals WHERE symbol=? AND model=? AND session=? AND decision='pending'",(symbol,model,ident)).fetchall():
                                prior=json.loads(prior_body)
                                if prior['trade_id']==payload['trade_id'] and (prior['action']=='entry' or payload['fraction']>=.75):
                                    db.execute("UPDATE proposals SET decision='superseded' WHERE id=?",(prior_id,))
                        db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                            (key,symbol,model,ident,event_id,ref,detected,self.clock(),json.dumps(payload),'pending',None,None))

    def list(self,unnotified=False):
        if not (self.root/'approvals.sqlite').exists():return []
        with closing(sqlite3.connect((self.root/'approvals.sqlite').as_uri()+'?mode=ro',uri=True,timeout=10)) as db:
            sql='SELECT body,decision,decided,notified FROM proposals'
            if unnotified:sql+=' WHERE notified IS NULL'
            rows=db.execute(sql+' ORDER BY ref DESC,detected DESC,id LIMIT 150').fetchall()
        return [dict(json.loads(b),decision=d,decided_at=btc_data.iso(t) if t else None,
            notified_at=btc_data.iso(n) if n else None,age_seconds=max(0,self.clock()-btc_data.ts(json.loads(b)['reference_time'])),
            delayed=self.clock()-btc_data.ts(json.loads(b)['reference_time'])>180) for b,d,t,n in rows]

    def acknowledge(self,ids):
        with self.store() as db:
            for ident in ids:
                if not db.execute('SELECT 1 FROM proposals WHERE id=?',(ident,)).fetchone():raise ValueError('Unknown proposal')
            db.executemany('UPDATE proposals SET notified=COALESCE(notified,?) WHERE id=?',[(self.clock(),i) for i in ids])

    def decide(self,ident,decision):
        if decision not in ('approved','rejected'):raise ValueError('Use approved or rejected for paper review only')
        with self.store() as db:
            row=db.execute('SELECT decision FROM proposals WHERE id=?',(ident,)).fetchone()
            if not row:raise ValueError('Unknown proposal')
            if row[0]==decision:return
            if row[0]!='pending':raise ValueError('Proposal is already decided or superseded')
            db.execute('UPDATE proposals SET decision=?,decided=? WHERE id=?',(decision,self.clock(),ident))


class Controller(btc_live.Controller):
    def __init__(self,root=HOME):super().__init__(root)
    def status(self,model=MODEL,day=None):
        if model!=MODEL:raise ValueError('SOL comparison uses E1 only')
        d=super().status(model,day)
        d.update(instrument=SYMBOL,selected_model=MODEL,
            cost_note='1 initial SOL per benchmark trade; frozen 2bps/side proxy, excluding actual spot crypto fees.',
            execution_blockers=['Comparison only; human paper review cannot create broker orders'])
        return d


class Worker(btc_live.Worker):
    def __init__(self,root=HOME,source=None,clock=time.time,rule_check=btc_live.verify_rules,supervision=None,btc_root=btc_live.LIVE):
        super().__init__(root,source or AlpacaSource(),clock,rule_check,supervision)
        self.outbox=Outbox(root,btc_root,clock)

    def publish(self,status,**extra):
        for k in ('error','quote_error'):
            if isinstance(extra.get(k),str):extra[k]=extra[k].replace('BTC','SOL')
        super().publish(status,**extra)

    def initialize(self):
        hashes=self.rule_check();session=btc_data.read(self.root/'SESSION.json')
        if not session:
            now=self.clock();start=(int(now)//60+1)*60
            session=dict(id=datetime.fromtimestamp(now,ZoneInfo('UTC')).strftime('%Y%m%dT%H%M%SZ'),
                start=start,created_at=btc_data.iso(now),warmup_start=start-btc_live.WARMUP,
                rule_sha256=hashes,release='0.2',mode='comparison_only',symbol=SYMBOL,models=[MODEL])
            btc_data.save(self.root/'SESSION.json',session)
        if session['rule_sha256']!=hashes or session.get('symbol')!=SYMBOL or session.get('models')!=[MODEL]:
            raise ValueError('Persisted SOL session configuration differs')
        self.comparison=Comparison(self.root/'sessions'/session['id'],session)
        self.publish('recovering',session=session,error=None)
        self.comparison.recover();self.publish('warming_up',session=session,error=None)

    def cycle(self):
        super().cycle()
        try:self.outbox.collect();self.state['approval_error']=None
        except Exception:self.state['approval_error']='Approval outbox unavailable; comparison only, no order attempted'
        self.publish(self.state.get('status','starting'))


CONTROLLER=Controller()
OUTBOX=Outbox()


def snapshot():
    return dict(btc=btc_live.CONTROLLER.status(),sol=CONTROLLER.status(),proposals=OUTBOX.list(),
        orders_enabled=False,mode='comparison_only',approval_effect='Separate human paper review; frozen benchmark positions continue automatically')
