"""Saved sequences and causal case checks with original paper isolation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_parent_memory_view import ParentMemoryView,SEQUENCES
from trading_desk.btc_data import read,ts


@pytest.fixture(scope='module')
def saved():
    v=ParentMemoryView()
    if v.current()[1] is None:pytest.skip('Requires authorized local retained-parent study')
    return v


def test_all_nine_controls_reproduced_and_fifteen_groups_reconcile(saved):
    _,s=saved.current()
    assert s['status']=='complete'
    assert all(all(r.values()) for r in s['controls_reproduced'].values())
    for m in ('0.1','E1','E2'):
        for q in SEQUENCES:
            _,_,r=saved.selection(m,q);a=s['summaries'][m][q]
            assert len(r['trades'])==a['all']['entries']
            assert a['all']['net']==pytest.approx(a['no_flagged_gap']['net']+a['gap_or_partial_context']['net'])


def test_retained_signals_are_single_use_with_fresh_HL_and_unchanged_costs(saved):
    has_retained_parent=False
    for m in ('0.1','E1','E2'):
        for mode in ('retained_combined','retained_standalone'):
            _,_,r=saved.selection(m,mode);seen=set()
            for s in r['signals']:
                if s['route']!='PH5':continue
                ctx=s['setup_evidence'];token=(ctx['parent']['time'],ctx['hl']['time'])
                assert token not in seen;seen.add(token)
                assert ctx['known_at']<=ts(s['time_utc'])
                assert s['hold_bar']['t']>=ctx['known_at'] and s['hold_bar']['observed_minutes']==5
                assert s['initial_stop']==pytest.approx(ctx['parent']['price']-.25*s['atr'])
            previous=None
            for p in r['trades']:
                if previous:assert ts(p['entry_time'])>ts(previous['exit_time'])
                if p['entry_rule']=='PH5' and previous:
                    ctx=p['parent_five']['setup']
                    assert ctx['hl']['bar_time']>=((ts(previous['entry_time'])//900)+1)*900
                    has_retained_parent|=ctx['parent']['time']<ts(previous['entry_time'])
                for l in p['legs']:
                    assert l['cost']==pytest.approx(l['fraction']*(p['entry']+l['price'])*.0002)
                previous=p
    assert has_retained_parent


def test_0320_qualifies_but_is_not_a_second_fill_and_first_exit_is_unchanged(saved):
    f,_=saved.current();case=read(f/'CASE.json')
    for m in ('0.1','E1','E2'):
        c=case['models'][m];s=c['reentry']
        assert s['time_utc']=='2026-11-15T08:20:00Z' and s['qualified_candidate']
        assert s['decision']=='held_position' and s['trade_id'] is None
        assert c['position_at_0320']['entry_time']=='2026-11-15T06:44:00Z'
        assert c['first_exit_unchanged'] and c['prefix_verified']
        trades=c['retained']['trades']
        assert not any(p['entry_time']==s['time_utc'] for p in trades)
        p=next(p for p in trades if p['entry_time']=='2026-11-15T06:44:00Z')
        assert p['status']=='open' and p['net'] is None and p['marked_net']>0
        assert not p['legs'] and p['mark_time']=='2026-11-15T10:15:00Z'


def test_strict_prefix_reproduces_held_decision_without_future_price_data(saved):
    from scripts.retest_btc_parent_memory import make_engine
    from scripts.retest_btc_parent_five import database,CASE_START,CASE_END
    from trading_desk.btc_live import LIVE
    f,_=saved.current();c=read(f/'CASE.json');target=c['models']['0.1']['reentry'];source=LIVE/'sessions'/c['source_session']/'observations.sqlite'
    if not source.exists():pytest.skip('Original observation prefix unavailable')
    db=database();session=read(LIVE/'SESSION.json');e=make_engine('0.1',session['start'],CASE_END,db,'retained_combined');e.ph5_active_from=CASE_START
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as source_db:
        for body, in source_db.execute('SELECT body FROM minutes WHERE t<=? ORDER BY t',(ts(target['time_utc']),)):e.minute(json.loads(body))
    s=next(s for s in e.signals if s['time_utc']==target['time_utc'] and s['route']=='PH5')
    assert s['decision']=='held_position' and s['setup_evidence']==target['setup_evidence']
    assert e.position['entry_time']=='2026-11-15T06:44:00Z'
    count=len(e.signals);e.scan(json.loads(__import__('pathlib').Path('trading_desk/tests/fixtures/ph5_memory_case_20261115.json').read_text())['minute_0320'],can_trade=False)
    assert len(e.signals)==count  # Held crossing is consumed, not queued for later.
    db.close()


def test_saved_hashes_and_original_selector_are_preserved(saved):
    f,s=saved.current();p=read(f/'PRESERVED.json')
    for name,h in p['PH5_files'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
    assert read(saved.store/'parent_five_studies/ACTIVE.json')['study_id']==s['original_PH5_study']


def test_read_only_allowlisted_http_and_exports(saved,monkeypatch):
    import server
    from trading_desk import btc_parent_memory_view
    monkeypatch.setattr(btc_parent_memory_view,'PARENT_MEMORY_VIEW',saved)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/btc-parent-memory') as res:
            d=json.load(res);assert d['available'] and d['read_only'] and not d['orders_enabled']
        with urllib.request.urlopen(base+'/api/btc-parent-memory/export?file=TRADES.csv') as res:assert 'attachment' in res.headers['Content-Disposition']
        for query in ('?sequence=../../','?model=bad','?trade_id=bad'):
            with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/btc-parent-memory'+query)
            assert e.value.code==400
        req=urllib.request.Request(base+'/api/btc-parent-memory',data=b'{"operation":"submit"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
        with pytest.raises(ValueError):saved.export('0.1','retained_combined','../../.env')
    finally:srv.shutdown();srv.server_close();thread.join(3)
