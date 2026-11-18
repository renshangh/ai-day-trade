"""SOL E1 uses actual archived observations, isolated recovery and no orders."""
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk import sol_live as sol,btc_live,btc_data
from trading_desk.crypto_transfer import STUDIES


@pytest.fixture(scope='module')
def actual():
    folder=STUDIES/btc_data.read(STUDIES/'ACTIVE.json')['study_id'];s=btc_data.read(folder/'STUDY.json')
    r=btc_data.read(folder/'SOL_USD/E1/result.json');p=r['trades'][0];end=btc_data.ts(p['exit_time'])+60
    with gzip.open(folder/'data/SOL_USD_MINUTES.jsonl.gz','rt') as f:rows=[json.loads(l) for l in f if json.loads(l)['t']<=end]
    session=dict(id='20261010T000000Z',start=btc_data.ts(s['start']),warmup_start=btc_data.ts(s['warmup_start']),
        symbol='SOL/USD',models=['E1'],rule_sha256=btc_live.verify_rules())
    return session,p,rows


def test_exact_e1_recovery_on_real_sol_and_no_other_models(tmp_path,actual):
    s,p,rows=actual;c=sol.Comparison(tmp_path,s);received=rows[-1]['t']+65
    c.ingest(rows,received,'actual-SOL-archive')
    assert list(c.engines)==['E1']
    first=c.engines['E1'].trades[0]
    assert first['entry']==p['entry'] and first['initial_stop']==p['initial_stop']
    assert first['exit_time']==p['exit_time'] and first['net']==pytest.approx(p['net'])
    events=c.db.execute('SELECT * FROM events ORDER BY id').fetchall();snap=c.snapshot(received)
    c.close();c=sol.Comparison(tmp_path,s);c.recover()
    assert c.db.execute('SELECT * FROM events ORDER BY id').fetchall()==events
    assert c.snapshot(received)==snap;c.close()


def test_proposals_delivery_and_approval_never_change_benchmark(tmp_path,actual):
    s,p,rows=actual;root=tmp_path/'sol';clock=[s['start']]
    out=sol.Outbox(root,tmp_path/'unavailable-btc',lambda:clock[0]);out.open().close()
    c=sol.Comparison(root/'sessions'/s['id'],s)
    entry=btc_data.ts(p['entry_time']);prefix=[b for b in rows if b['t']<=entry]
    clock[0]=entry+65;c.ingest(prefix,clock[0],'actual-prefix')
    btc_data.save(root/'STATUS.json',dict(session=s));out.collect();out.collect()
    proposals=out.list(unnotified=True);assert len(proposals)==1
    q=proposals[0];assert q['action']=='entry' and q['initial_stop']==p['initial_stop']
    assert q['detected_at']==btc_data.iso(clock[0]) and q['decision']=='pending'
    before=c.snapshot(clock[0]);out.decide(q['id'],'approved');out.decide(q['id'],'approved')
    assert c.snapshot(clock[0])==before
    assert len(out.list(unnotified=True))==1
    out.acknowledge([q['id']]);assert out.list(unnotified=True)==[]
    later=[b for b in rows if b['t']>entry];clock[0]=rows[-1]['t']+65
    c.ingest(later,clock[0],'actual-later');out.collect()
    exits=out.list(unnotified=True);assert len(exits)==2
    assert sorted(x['fraction'] for x in exits)==[.25,.75]
    assert all(x['action']=='exit' and not x['orders_enabled'] and not x['broker_fill'] for x in exits)
    assert len([x for x in exits if x['decision']=='superseded'])==1
    assert c.engines['E1'].trades[0]['net']==pytest.approx(p['net']);c.close()
    with pytest.raises(ValueError):out.decide('missing','approved')
    with pytest.raises(ValueError):out.decide(q['id'],'rejected')
    with pytest.raises(ValueError):out.decide(q['id'],'submit')


def test_no_historical_notifications_and_btc_source_is_unchanged(tmp_path,actual):
    release=btc_data.STORE/'releases/0.1';r=btc_data.read(release/'results/result.json')
    p=r['trades'][0];end=btc_data.ts(p['entry_time'])+60
    s=dict(id='20261010T000000Z',start=btc_data.ts(r['start']),warmup_start=btc_data.ts(r['warmup_start']))
    rows=[]
    with gzip.open(release/'data/MINUTES.jsonl.gz','rt') as f:
        for line in f:
            t,o,h,l,c,v,n,vw=json.loads(line)
            if t>end:break
            rows.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    root=tmp_path/'btc';folder=root/'sessions'/s['id']
    c=btc_live.Comparison(folder,s);c.ingest(rows,rows[-1]['t']+65,'actual-observations')
    btc_data.save(root/'STATUS.json',dict(session=s));c.close()
    path=folder/'observations.sqlite';before=hashlib.sha256(path.read_bytes()).hexdigest()
    out=sol.Outbox(tmp_path/'sol',root,lambda:rows[-1]['t']+1000);out.collect()
    assert out.list()==[]
    forward=sol.Outbox(tmp_path/'fresh',root,lambda:s['start']);forward.open().close();forward.collect();forward.collect()
    pending=forward.list()
    assert len(pending)==3 and {x['model'] for x in pending}=={'0.1','E1','E2'}
    assert all(x['symbol']=='BTC/USD' and x['action']=='entry' and x['initial_stop']==p['initial_stop'] for x in pending)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before


def test_get_only_sol_source_provenance_and_missing_data(tmp_path,actual,monkeypatch):
    s,p,rows=actual;b=rows[0]
    real=dict(t=btc_data.iso(b['t']),o=b['open'],h=b['high'],l=b['low'],c=b['close'],v=b['volume'],n=b['n'])
    def request(params):
        assert params['symbols']=='SOL/USD';return json.dumps({'bars':{'SOL/USD':[real]},'next_page_token':None}).encode()
    monkeypatch.setattr(btc_data,'request_page',request)
    found,_=sol.AlpacaSource().bars(b['t'],b['t']+120,tmp_path)
    assert found==[b] # No second observed minute is fabricated.
    record=json.loads((tmp_path/'SOURCES.jsonl').read_text());raw=gzip.decompress((tmp_path/record['path']).read_bytes())
    assert record['symbol']=='SOL/USD' and hashlib.sha256(raw).hexdigest()==record['sha256']


def test_missing_minute_and_incomplete_bar_contract(tmp_path,actual):
    s,p,rows=actual;c=sol.Comparison(tmp_path,s)
    with pytest.raises(ValueError):c.ingest(rows[:1],rows[0]['t']+59,'unfinished')
    selected=rows[:30];kept=[b for i,b in enumerate(selected) if i!=10]
    c.ingest(kept,selected[-1]['t']+65,'actual-removed-minute')
    with pytest.raises(btc_live.DataConflict):c.ingest([selected[10]],selected[-1]['t']+125,'late-backfill')
    assert c.db.execute('SELECT count(*) FROM minutes').fetchone()[0]==29;c.close()


def test_own_startup_registration_and_immutable_original_files():
    from scripts.run_sol_live import agent_document,LABEL
    d=agent_document(ROOT,sys.executable,Path.home())
    assert d['Label']==LABEL and LABEL!='com.renshangh.btc-live-comparison'
    assert d['KeepAlive'] and d['RunAtLoad'] and d['WorkingDirectory']==str(Path.home())
    assert d['ProgramArguments'][-1]=='--launchd-worker'
    proof=btc_data.read(sol.HOME/'PRESERVED_BEFORE.json')
    # Later owner-authorized display panels are mutable UI, not the
    # frozen BTC rules or original worker/process configuration.
    for p,h in proof['files'].items():
        if p in {'trading_desk/btc_live.html','trading_desk/btc_live.js','trading_desk/btc_live.css'}:continue
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    assert len(btc_live.verify_rules())==13


def test_http_no_order_or_approval_mutation(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(sol,'CONTROLLER',sol.Controller(tmp_path/'sol'))
    monkeypatch.setattr(sol,'OUTBOX',sol.Outbox(tmp_path/'sol',tmp_path/'btc'))
    monkeypatch.setattr(sol.AlpacaSource,'bars',lambda *a:pytest.fail('HTTP fetched market data'))
    from http.server import ThreadingHTTPServer
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/crypto-live') as r:d=json.load(r)
        assert not d['orders_enabled'] and d['sol']['instrument']=='SOL/USD'
        assert not (tmp_path/'sol/approvals.sqlite').exists()
        for payload in ({'operation':'submit'},{'operation':'start','quantity':1},{'operation':'approve','id':'123'}):
            req=urllib.request.Request(base+'/api/sol-live',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
            with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
            assert e.value.code==400
        req=urllib.request.Request(base+'/api/sol-live',data=b'{"operation":"start"}',headers={'Content-Type':'application/json','Origin':'https://evil.example'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==403
        assert not (tmp_path/'sol/CONTROL.json').exists()
    finally:srv.shutdown();srv.server_close();t.join(3)


def test_page_paper_review_is_strict_and_does_not_change_model(tmp_path,actual,monkeypatch):
    import server
    from trading_desk import crypto_live_review
    s,p,rows=actual;root=tmp_path/'sol';entry=btc_data.ts(p['entry_time'])
    out=sol.Outbox(root,tmp_path/'btc',lambda:s['start']);out.open().close()
    c=sol.Comparison(root/'sessions'/s['id'],s)
    c.ingest([b for b in rows if b['t']<=entry],entry+65,'actual-SOL-prefix')
    btc_data.save(root/'STATUS.json',dict(session=s));out.collect();q=out.list()[0]
    before=c.snapshot(entry+65);events=c.db.execute('SELECT * FROM events ORDER BY id').fetchall()
    monkeypatch.setattr(crypto_live_review,'OUTBOX',out)
    from http.server import ThreadingHTTPServer
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    url='http://127.0.0.1:'+str(srv.server_address[1])+'/api/crypto-live/review'
    def request(body,origin=None):
        headers={'Content-Type':'application/json'}
        if origin:headers['Origin']=origin
        return urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers))
    try:
        for body in ({'id':q['id'],'decision':'submit'},{'id':q['id'],'decision':'approved','quantity':1},
                     {'id':'../oops','decision':'approved'},{'id':'f'*24,'decision':'approved'}):
            with pytest.raises(urllib.error.HTTPError) as e:request(body)
            assert e.value.code==400
        with pytest.raises(urllib.error.HTTPError) as e:request({'id':q['id'],'decision':'approved'},'https://elsewhere.example')
        assert e.value.code==403 and out.list()[0]['decision']=='pending'
        with request({'id':q['id'],'decision':'approved'}) as response:result=json.load(response)
        assert result['recorded'] and not result['orders_enabled'] and not result['fill_created']
        assert out.list()[0]['decision']=='approved' and out.list()[0]['notified_at'] is None
        assert c.snapshot(entry+65)==before and c.db.execute('SELECT * FROM events ORDER BY id').fetchall()==events
    finally:srv.shutdown();srv.server_close();t.join(3);c.close()
