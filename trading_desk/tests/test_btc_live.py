"""Forward comparison recovery on real frozen BTC minutes; no fabricated bars."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk import btc_live,btc_data


@pytest.fixture(scope='module')
def observed():
    release=btc_data.STORE/'releases/0.1'
    original=json.loads((release/'results/result.json').read_text())
    first=original['trades'][0];end=btc_data.ts(first['exit_time'])+60;rows=[]
    with gzip.open(release/'data/MINUTES.jsonl.gz','rt') as f:
        for line in f:
            t,o,h,l,c,v,n,vw=json.loads(line)
            if t>=end:break
            rows.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    return original,rows


def session(original):
    return dict(id='20261109T000000Z',start=btc_data.ts(original['start']),
        warmup_start=btc_data.ts(original['warmup_start']),rule_sha256=btc_live.verify_rules(),
        created_at=original['start'],release='0.2',mode='comparison_only')


def test_forward_recovery_and_receipt_time_are_idempotent(tmp_path,observed):
    original,rows=observed;s=session(original);received=rows[-1]['t']+65
    c=btc_live.Comparison(tmp_path,s)
    c.ingest(rows,received,'actual-frozen-stream')
    state=c.snapshot(received)
    for m in state['models']:
        assert m['closed']==1 and m['position'] is None
        assert m['closed_net']==pytest.approx(original['trades'][0]['net'])
    count=c.db.execute('SELECT count(*) FROM events').fetchone()[0]
    signals=c.db.execute('SELECT id,body FROM signals ORDER BY id').fetchall()
    assert len(signals)==3
    for ident,body in signals:
        p=json.loads(body)
        assert btc_data.ts(p['detected_at'])==received
        assert p['detection_delay_seconds']>=60 and not p['broker_fill']
    expected=c.db.execute('SELECT id,detected,body FROM events ORDER BY id').fetchall()
    c.ingest(rows,received+90,'same-actual-stream')
    assert c.db.execute('SELECT count(*) FROM events').fetchone()[0]==count
    c.close()
    recovered=btc_live.Comparison(tmp_path,s);recovered.recover()
    assert recovered.db.execute('SELECT id,detected,body FROM events ORDER BY id').fetchall()==expected
    assert recovered.db.execute('SELECT id,body FROM signals ORDER BY id').fetchall()==signals
    assert recovered.snapshot(received)['models']==state['models']
    recovered.close()


def test_missing_real_minute_stays_missing_and_late_backfill_is_rejected(tmp_path,observed):
    original,rows=observed;s=session(original);omit=btc_data.ts(original['trades'][0]['entry_time'])+120
    kept=[b for b in rows if b['t']!=omit];received=rows[-1]['t']+65
    c=btc_live.Comparison(tmp_path,s);c.ingest(kept,received,'actual-with-removed-observation')
    assert c.db.execute('SELECT body FROM minutes WHERE t=?',(omit,)).fetchone() is None
    assert all(e.trades[0]['gap_exposed'] for e in c.engines.values())
    with pytest.raises(btc_live.DataConflict):c.ingest([next(b for b in rows if b['t']==omit)],received+60,'late-actual-minute')
    assert c.db.execute('SELECT count(*) FROM minutes').fetchone()[0]==len(kept)
    c.close()


def test_unfinished_observation_is_not_accepted(tmp_path,observed):
    original,rows=observed;c=btc_live.Comparison(tmp_path,session(original))
    with pytest.raises(ValueError,match='Incomplete'):c.ingest(rows[:1],rows[0]['t']+59,'real-but-not-complete')
    assert c.db.execute('SELECT count(*) FROM minutes').fetchone()[0]==0
    c.close()


def test_partial_target_mark_keeps_realized_and_open_fractions_separate(tmp_path,observed):
    original,rows=observed;first=original['trades'][0];target=btc_data.ts(first['legs'][0]['time_utc'])
    prefix=[b for b in rows if b['t']<=target]
    c=btc_live.Comparison(tmp_path,session(original));c.ingest(prefix,target+65,'real-prefix-through-target')
    for m in c.snapshot(target+65)['models']:
        assert m['position']['remaining']==.75
        assert m['realized_leg_net']==pytest.approx(first['legs'][0]['net'])
        expected=.75*((prefix[-1]['close']-first['entry'])-(prefix[-1]['close']+first['entry'])*.0002)
        assert m['open_benchmark_net']==pytest.approx(expected)
        assert m['marked_benchmark_net']==pytest.approx(expected+first['legs'][0]['net'])
    c.close()


def test_pinned_rules_and_archives_are_unchanged():
    assert len(btc_live.verify_rules())==13
    folder=btc_data.STORE/'releases/0.2'
    m=btc_data.read(folder/'MANIFEST.json')
    for name,digest in m['files_sha256'].items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest
    assert 'finish(' not in __import__('inspect').getsource(btc_live.Comparison)


def test_controller_staleness_and_order_boundary(tmp_path,monkeypatch):
    now=btc_data.ts('2026-11-09T18:00:00Z')
    monkeypatch.setattr(btc_live.time,'time',lambda:now)
    c=btc_live.Controller(tmp_path);c.control('start')
    btc_data.save(tmp_path/'STATUS.json',dict(status='running',heartbeat_epoch=now,
        minute_end=btc_data.iso(now-181),data_age_seconds=5,session={}))
    assert c.status()['health']=='stale'
    c.control('pause');assert c.status()['health']=='paused'
    assert c.status()['orders_enabled'] is c.status()['broker_orders_enabled'] is False
    with pytest.raises(ValueError):c.control('submit')
    with pytest.raises(ValueError):c.status('../../')
    with pytest.raises(ValueError):c.status(day='not-a-date')


def test_rejected_batch_never_publishes_uncommitted_model_state(tmp_path,observed,monkeypatch):
    original,rows=observed;s=session(original)
    boundary=btc_data.ts(original['trades'][0]['entry_time'])+60
    prefix=[b for b in rows if b['t']<=boundary]
    omitted=prefix[20] # A real earlier observation, deliberately absent.
    kept=[b for b in prefix if b is not omitted]
    received=boundary+65
    c=btc_live.Comparison(tmp_path/'session',s);c.ingest(kept,received,'actual-prefix')
    worker=btc_live.Worker(root=tmp_path,clock=lambda:received+120)
    worker.comparison=c;worker.publish('running')
    before=btc_data.read(tmp_path/'STATUS.json')
    following=next(b for b in rows if b['t']==boundary+60)
    def conflicting():
        worker.comparison.ingest([following,omitted],received+120,'actual-forward-then-late')
    monkeypatch.setattr(worker,'tick',conflicting)
    worker.cycle()
    after=btc_data.read(tmp_path/'STATUS.json')
    assert after['status']=='data_conflict'
    assert after['models']==before['models']
    assert after['last_observed']==before['last_observed']
    assert worker.comparison is None
    assert not btc_data.read(tmp_path/'CONTROL.json')['enabled']
    with sqlite3.connect(tmp_path/'session/observations.sqlite') as db:
        assert db.execute('SELECT count(*) FROM minutes WHERE t=?',(following['t'],)).fetchone()[0]==0


def test_provider_provenance_contains_valid_separate_json_lines(tmp_path,observed,monkeypatch):
    _,rows=observed;source=btc_live.AlpacaSource()
    for b in rows[:2]:
        real=dict(t=btc_data.iso(b['t']),o=b['open'],h=b['high'],l=b['low'],c=b['close'],v=b['volume'],n=b['n'])
        payload=json.dumps({'bars':{'BTC/USD':[real]},'next_page_token':None}).encode()
        monkeypatch.setattr(btc_data,'request_page',lambda params,value=payload:value)
        found,_=source.bars(b['t'],b['t']+60,tmp_path)
        assert found==[b]
    records=[json.loads(line) for line in (tmp_path/'SOURCES.jsonl').read_text().splitlines()]
    assert len(records)==2
    for record in records:
        assert record['count']==1
        assert (tmp_path/record['path']).is_file()


def test_date_selection_respects_25_hour_new_york_day(tmp_path):
    root=tmp_path/'live';ident='20261109T000000Z';db=btc_live.open_store(root/'sessions'/ident)
    path=btc_data.STORE/'runs/20261109T041525Z-30-ab/ledger.sqlite'
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source:
        raw=source.execute("SELECT t,body FROM ledger WHERE day IN ('2026-10-31','2026-11-01','2026-11-02') ORDER BY t").fetchall()
    db.executemany('INSERT INTO ledger VALUES(?,?,?)',[('0.1',t,body) for t,body in raw]);db.commit();db.close()
    btc_data.save(root/'STATUS.json',dict(session=dict(id=ident)))
    selected=btc_live.Controller(root).status(day='2026-11-01')['rows']
    expected=[json.loads(body) for _,body in raw if json.loads(body)['time_ny'].startswith('2026-11-01')]
    assert selected==expected[:100]
    assert all(datetime.fromtimestamp(row['t'],btc_live.NY).date().isoformat()=='2026-11-01' for row in selected)


@pytest.fixture
def http(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(btc_live,'CONTROLLER',btc_live.Controller(tmp_path))
    # GET/POST controls may never invoke a feed or broker.
    monkeypatch.setattr(btc_live.AlpacaSource,'bars',lambda *a:pytest.fail('UI request started a data job'))
    from http.server import ThreadingHTTPServer
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(srv.server_address[1])
    srv.shutdown();srv.server_close();thread.join(3)


def test_http_reads_do_not_start_worker_and_controls_do_not_accept_orders(http):
    with urllib.request.urlopen(http+'/api/btc-live') as r:
        state=json.load(r)
    assert state['mode']=='comparison_only' and not state['orders_enabled']
    body=json.dumps(dict(operation='start')).encode()
    with urllib.request.urlopen(urllib.request.Request(http+'/api/btc-live',data=body,
            headers={'Content-Type':'application/json'})) as r:
        assert json.load(r)['enabled']
    for payload in (dict(operation='submit'),dict(operation='start',quantity=1)):
        req=urllib.request.Request(http+'/api/btc-live',data=json.dumps(payload).encode(),
            headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as exc:urllib.request.urlopen(req)
        assert exc.value.code==400
    req=urllib.request.Request(http+'/api/btc-live',data=body,
        headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
    with pytest.raises(urllib.error.HTTPError) as exc:urllib.request.urlopen(req)
    assert exc.value.code==403
