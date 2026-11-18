"""Real saved sequence, preservation and GET-only endpoint integration."""
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_parent_five_view import ParentFiveView
from trading_desk.btc_data import ts


@pytest.fixture(scope='module')
def saved():
    v=ParentFiveView()
    if v.current()[1] is None:pytest.skip('Requires authorized local PH5 study')
    return v


def test_saved_reproduction_and_complementary_gap_groups(saved):
    _,s=saved.current()
    assert s['status']=='complete' and all(s['controls_reproduced'].values())
    assert s['preservation']['unchanged']
    for model in ('0.1','E1','E2'):
        for mode in ('control','standalone','combined'):
            _,_,r=saved.selection(model,mode)
            a=s['summaries'][model][mode]
            assert len(r['trades'])==a['all']['entries']
            assert a['all']['net']==pytest.approx(a['no_flagged_gap']['net']+a['gap_or_partial_context']['net'])
            if mode=='standalone':assert all(p['entry_rule']=='PH5' for p in r['trades'])


def test_every_new_entry_has_causal_confirmation_and_real_five_bar(saved):
    for model in ('0.1','E1','E2'):
        for mode in ('standalone','combined'):
            _,_,r=saved.selection(model,mode)
            previous=None
            for p in r['trades']:
                if previous:assert ts(p['entry_time'])>ts(previous['exit_time'])
                if p['entry_rule']=='PH5':
                    q=p['parent_five'];c=q['setup'];h=q['hold'];t=ts(p['entry_time'])
                    assert c['parent']['time']<c['rebound']['time']<c['hl']['time']
                    assert c['known_at']<=h['t'] and h['t']+300<=t
                    assert h['observed_minutes']==5 and h['low']>c['hl']['price']
                    signal=next(s for s in r['signals'] if s['trade_id']==p['id'])
                    assert p['initial_stop']==pytest.approx(c['parent']['price']-.25*signal['atr'])
                    if previous:assert c['parent']['bar_time']>ts(previous['entry_time'])//900*900
                previous=p


def test_bounce_reports_loss_not_retroactive_rally_profit(saved):
    d=saved.snapshot();p=next(p for p in d['case']['trades'] if p['entry_rule']=='PH5')
    assert p['entry_time']=='2026-11-15T04:47:00Z'
    assert ts(p['entry_received_at'])>=ts(p['entry_time'])+60
    assert p['legs'][0]['time_utc']=='2026-11-15T05:48:00Z'
    assert p['legs'][0]['reason']=='failed_rebound_exit_remaining'
    assert p['net']==pytest.approx(-135.66369299999738)
    assert len(p['legs'])==1 and p['legs'][0]['fraction']==1
    assert not d['orders_enabled'] and d['read_only']


def test_export_and_query_are_allowlisted(saved):
    for model,mode,ident in [('bad','combined',None),('0.1','../',None),('0.1','combined','bad')]:
        with pytest.raises(ValueError):saved.snapshot(model,mode,ident)
    with pytest.raises(ValueError):saved.export('0.1','combined','../../.env')
    assert saved.export('0.1','combined','TRADES.csv').is_file()


def test_bounce_entry_reproduces_on_prefix_without_later_rally(saved):
    import sqlite3
    from scripts.retest_btc_parent_five import engine, database, CASE_START, CASE_END
    from trading_desk.btc_live import LIVE
    from trading_desk.btc_data import read
    folder,_=saved.current()
    case=read(folder/'CASE.json')
    signal=next(s for s in case['models']['0.1']['signals'] if s['route']=='PH5')
    source=LIVE/'sessions'/case['source_session']/'observations.sqlite'
    if not source.is_file():pytest.skip('Original live observation prefix not available')
    session=read(LIVE/'SESSION.json')
    db=database();e=engine('0.1',session['start'],CASE_END,db,'combined');e.ph5_active_from=CASE_START
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as source_db:
        for body, in source_db.execute('SELECT body FROM minutes WHERE t<=? ORDER BY t',(ts(signal['time_utc']),)):
            e.minute(json.loads(body))
    actual=next(s for s in e.signals if s['route']=='PH5')
    for key in ('entry_reference','initial_stop','t1','decision','time_utc','setup_evidence','hold_bar'):
        assert actual[key]==signal[key]
    assert e.position and e.position['entry_rule']=='PH5'
    db.close()


def test_endpoint_is_read_only_and_saved_only(saved,monkeypatch):
    import server
    from trading_desk import btc_parent_five_view
    monkeypatch.setattr(btc_parent_five_view,'PARENT_FIVE_VIEW',saved)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/btc-parent-five') as response:assert json.load(response)['available']
        with urllib.request.urlopen(base+'/api/btc-parent-five/export?file=TRADES.csv') as response:assert 'attachment' in response.headers['Content-Disposition']
        req=urllib.request.Request(base+'/api/btc-parent-five',data=b'{"operation":"start"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();thread.join(3)
