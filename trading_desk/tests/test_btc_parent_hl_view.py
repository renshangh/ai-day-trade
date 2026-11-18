"""Saved continuation evidence, causal bounds and read-only HTTP delivery."""
import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'trading_desk'))
from trading_desk.btc_data import ts
from trading_desk.btc_parent_hl_view import ContinuationView


@pytest.fixture(scope='module')
def saved():
    v=ContinuationView()
    if not v.current():pytest.skip('Requires the explicitly authorized local parent-HL study')
    return v


def test_saved_controls_reproduced_and_groups_reconcile(saved):
    s=saved.current()
    assert all(s['controls_reproduced'].values())
    for model in ('0.1','E1','E2'):
        for sequence in ('variant','control','frozen'):
            d=saved.snapshot(model,sequence)
            assert not d['orders_enabled'] and not d['live_promoted'] and d['read_only']
            group=s['summaries'][model][sequence]
            assert group['all']['net']==pytest.approx(group['no_flagged_gap']['net']+group['gap_or_partial_context']['net'])
            assert len(d['trades'])==group['all']['entries']
        assert s['summaries'][model]['variant']['all']['net']<0


def test_each_C_entry_has_known_parent_and_unchanged_larger_D_stop(saved):
    for model in ('0.1','E1','E2'):
        _,_,r=saved.selection(model,'variant')
        emitted=set()
        for s in (s for s in r['signals'] if s['route']=='C'):
            ctx=s['setup_evidence'];t=ts(s['time_utc'])
            assert all(ctx[k]['known_at']<=t for k in ('parent','hl','rebound'))
            assert ctx['parent']['time']<ctx['rebound']['time']<ctx['hl']['time']
            assert s['initial_stop']==pytest.approx(ctx['parent']['price']-.25*s['atr'])
            assert ctx['hl']['time'] not in emitted
            emitted.add(ctx['hl']['time'])
        prior=None
        for p in r['trades']:
            if prior:assert ts(p['entry_time'])>ts(prior['exit_time'])
            if p['entry_rule']=='C':
                ctx=p['continuation']
                if prior:assert ctx['hl']['bar_time']>ts(prior['entry_time'])//900*900
            prior=p


def test_0317_is_a_signal_not_an_extra_broker_fill(saved):
    d=saved.snapshot();c=d['case'];s=c['signal']
    assert c['status']=='passed' and c['isolated_case'] and not c['full_nov9_portfolio']
    assert s['time_utc']=='2026-11-09T08:17:00Z'
    assert c['known_no_earlier_than']=='2026-11-09T08:18:00Z'
    assert s['decision']=='held_position' and s['trade_id'] is None
    assert c['existing_priority_position']['entry_time']==s['time_utc']
    assert not c['nearer_hl_diagnostic']['active_risk_change']


def test_parallel_model_reads_cannot_evict_another_inflight_result(saved):
    from concurrent.futures import ThreadPoolExecutor
    requests=[(model,sequence) for model in ('0.1','E1','E2') for sequence in ('variant','control','frozen')]*3
    def select(args):
        _,folder,result=saved.selection(*args)
        return folder.name,len(result['trades'])
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers=list(pool.map(select,requests))
    for (_,sequence),(_,count) in zip(requests,answers,strict=True):
        assert count in ((143,181,147) if sequence=='variant' else (36,) if sequence=='control' else (38,))


def test_bad_selection_or_export_cannot_escape_saved_research(saved):
    for args in [('bad','variant',None),('0.1','../',None),('0.1','variant','bad')]:
        with pytest.raises(ValueError):saved.snapshot(*args)
    with pytest.raises(ValueError):saved.export('0.1','variant','../../.env')
    assert saved.export('0.1','variant','TRADES.csv').is_file()


def test_HTTP_has_no_order_or_replay_mutation(saved,monkeypatch):
    import server
    from trading_desk import btc_parent_hl_view
    monkeypatch.setattr(btc_parent_hl_view,'CONTINUATION_VIEW',saved)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/btc-parent-hl') as response:
            assert json.load(response)['selected']['entry_rule']=='C'
        with urllib.request.urlopen(base+'/api/btc-parent-hl/export?file=TRADES.csv') as response:
            assert 'attachment' in response.headers['Content-Disposition']
        request=urllib.request.Request(base+'/api/btc-parent-hl',data=b'{"operation":"submit"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
        assert e.value.code==404
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+'/api/btc-parent-hl?model=bad')
        assert e.value.code==400
    finally:srv.shutdown();srv.server_close();thread.join(3)
