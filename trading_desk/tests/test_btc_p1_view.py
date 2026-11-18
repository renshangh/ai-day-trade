"""Saved P1 study reads and all-sequence invariants, without launching a replay."""
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
from trading_desk.btc_data import STORE
from trading_desk.btc_p1_view import P1View


@pytest.fixture(scope='module')
def saved():
    view=P1View()
    if not view.current():pytest.skip('Requires the locally generated, explicitly authorized P1 study')
    return view


def test_full_sequence_matches_all_remaining_B_trades(saved):
    s=saved.current()
    assert all(s['baseline_reproduced'].values())
    for model in ('0.1','E1','E2'):
        changes=s['changes'][model]
        assert sum(c['status']=='unchanged' for c in changes)==36
        assert [c['original']['id'] for c in changes if c['status']=='removed']==[23,26]
        assert not [c for c in changes if c['status'] in ('added','changed')]
        values=s['summaries'][model]
        assert values['p1']['all']['net']-values['frozen']['all']['net']==pytest.approx(448.5594891)
        assert values['p1']['all']['entries']==36
        assert values['p1']['all']['wins']==values['p1']['all']['losses']==18
        assert values['p1']['all']['net']==pytest.approx(
            values['p1']['no_flagged_gap']['net']+values['p1']['gap_or_partial_context']['net'])


def test_saved_view_lists_real_exit_and_preserves_selection_pointers(saved):
    pointers=[STORE/'p1_studies/ACTIVE.json',STORE/'studies/ACTIVE.json',STORE/'releases/ACTIVE.json',
        STORE/'live/SESSION.json',STORE/'live/CONTROL.json']
    before={p:p.read_bytes() for p in pointers if p.exists()}
    d=saved.snapshot('E2','frozen','23')
    assert len(d['trades'])==38 and d['selected']['legs'][0]['fraction']==1
    assert d['selected']['legs'][0]['price']==77030.524
    assert d['p1_audit']['p1_low_count']==3
    assert d['early_case']['points'][2]['time']=='2026-11-09T08:17:00Z'
    assert not d['orders_enabled'] and d['read_only'] and not d['live_promoted']
    assert all(p.read_bytes()==b for p,b in before.items())


@pytest.mark.parametrize(('model','seq','trade'),[
    ('bad','p1',None),('0.1','../',None),('0.1','p1','oops'),('0.1','p1',9999)])
def test_invalid_selections_do_not_read_arbitrary_paths(saved,model,seq,trade):
    with pytest.raises(ValueError):saved.snapshot(model,seq,trade)


def test_export_allowlist(saved):
    assert saved.export('0.1','p1','TRADES.csv').suffix=='.csv'
    with pytest.raises(ValueError):saved.export('0.1','p1','../../.env')


def test_http_reads_have_no_replay_or_order_control(saved,monkeypatch):
    import server
    from trading_desk import btc_p1_view
    monkeypatch.setattr(btc_p1_view,'P1_VIEW',saved)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/btc-p1?sequence=frozen&trade_id=23') as r:
            assert json.load(r)['selected']['id']==23
        with urllib.request.urlopen(base+'/api/btc-p1/export?file=TRADES.csv') as r:
            assert 'attachment' in r.headers['Content-Disposition']
        req=urllib.request.Request(base+'/api/btc-p1',data=b'{"operation":"submit"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/btc-p1?model=bad')
        assert e.value.code==400
    finally:srv.shutdown();srv.server_close();thread.join(3)
