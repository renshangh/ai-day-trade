"""Saved sequential results, immutable controls and read-only delivery."""
import json
from pathlib import Path
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_parent_filter_view import ParentFilterView


@pytest.fixture(scope='module')
def saved():
    view=ParentFilterView()
    if not view.current():pytest.skip('Requires the authorized parent-only sequential study')
    return view


def test_reproduced_controls_and_sequential_delta_reconcile(saved):
    s=saved.current();assert all(s['controls_reproduced'].values())
    for model,pair in s['summaries'].items():
        old=pair['control']['all'];new=pair['variant']['all']
        assert sum(c['delta'] for c in s['changes'][model])==pytest.approx(new['net']-old['net'])
        for which in ('control','variant'):
            groups=pair[which]
            assert groups['all']['net']==pytest.approx(groups['no_flagged_gap']['net']+groups['gap_or_partial_context']['net'])
        assert new['net']<0 and new['net']>old['net']
        assert new['max_closed_trade_drawdown_usd']<old['max_closed_trade_drawdown_usd']


def test_only_clear_parent_blocks_and_unknowns_remain_in_original_paths(saved):
    for model in ('0.1','E1','E2'):
        _,_,r=saved.selection(model,'variant')
        for a in r['parent_filter_audits']:
            assert a['blocked']==bool(a['parent_flag'] and not a['uncertainty'])
            if a['blocked']:assert a['trade_id'] is None
            else:assert a['trade_id'] is not None
            assert a['prefix_last_minute']<a['time_utc']
        s=saved.snapshot(model)
        assert s['selected']['id'] in [c['p1']['id'] for c in s['changes'] if c['status']=='added']
        assert not s['orders_enabled'] and not s['live_promoted'] and s['read_only']


def test_new_view_is_independent_and_exports_are_allowlisted(saved):
    assert saved.export('0.1','variant','PARENT_DECISIONS.csv').is_file()
    assert saved.export('E1','control','CHANGES.csv').name=='CHANGES_E1.csv'
    for model,sequence,trade in [('bad','variant',None),('0.1','../',None),('0.1','variant','bad')]:
        with pytest.raises(ValueError):saved.snapshot(model,sequence,trade)
    with pytest.raises(ValueError):saved.export('0.1','variant','../../.env')


def test_HTTP_cannot_run_or_submit(saved,monkeypatch):
    import server
    from trading_desk import btc_parent_filter_view
    monkeypatch.setattr(btc_parent_filter_view,'PARENT_FILTER_VIEW',saved)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/btc-parent-filter') as r:assert json.load(r)['available']
        with urllib.request.urlopen(base+'/api/btc-parent-filter/export?file=PARENT_DECISIONS.csv') as r:
            assert 'attachment' in r.headers['Content-Disposition']
        request=urllib.request.Request(base+'/api/btc-parent-filter',data=b'{"operation":"submit"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
        assert e.value.code==404
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/btc-parent-filter?model=bad')
        assert e.value.code==400
    finally:srv.shutdown();srv.server_close();thread.join(3)
