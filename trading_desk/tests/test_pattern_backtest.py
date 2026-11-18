"""Saved actual observations, split provenance and full cross-asset trade paths."""
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.pattern_backtest import BACKTESTS,grid,split_events,PatternReplay
from trading_desk.pattern_backtest_view import BacktestView
from scripts.btc_structure_retest import Config


@pytest.fixture(scope='module')
def saved():
    view=BacktestView();folder,s=view.current()
    if not s or s['status']!='complete':pytest.skip('Requires authorized saved stock/ETF replay')
    return view,folder,s


def test_same_window_all_symbols_and_real_calendar_coverage(saved):
    view,folder,s=saved
    assert s['start']=='2026-10-10T00:00:00Z' and s['end']=='2026-11-09T00:00:00Z'
    assert len(s['symbols'])==13
    assert all(s['results'][symbol]['status']=='complete' for symbol in s['symbols'])
    for symbol in s['symbols']:
        d=view.snapshot(symbol);q=next(x['coverage'] for x in d['summaries'] if x['symbol']==symbol)
        assert q['test_expected']==(43200 if symbol=='BTC/USD' else 7800)
        assert q['test_observed']+q['test_missing']==q['test_expected']
        assert not d['orders_enabled'] and d['read_only']
    assert view.snapshot('BTC/USD')['summaries'][0]['coverage']['test_missing']==558


def test_real_split_factor_rounding_and_genuine_event():
    p=ROOT/'outputs/pattern_watchlist_30d/SPLIT_REGRESSION/SOXX_DAILY.json'
    if not p.exists():pytest.skip('Requires actual observed raw/adjusted daily regression series')
    d=read(p)
    events=split_events(d['raw'],d['split'],ts('2026-10-03T00:00:00Z'),ts('2026-11-09T00:00:00Z'))
    assert [e['date'] for e in events]==['2026-11-05']
    assert events[0]['adjustment_ratio_change']==pytest.approx(3,rel=1e-4)


def test_per_symbol_leg_profits_normalized_returns_and_no_forced_sale(saved):
    view,folder,s=saved
    for symbol in s['symbols']:
        r=view.result(folder,symbol);summary=r['summary']
        assert summary['realized_net']==pytest.approx(sum(l['net'] for p in r['trades'] for l in p['legs']))
        for p in r['trades']:
            assert sum(l['fraction'] for l in p['legs'])+p['remaining']==pytest.approx(1)
            assert p['normalized_10000_realized_net']==pytest.approx(sum(l['net'] for l in p['legs'])/p['entry']*10000)
            for l in p['legs']:
                assert p['entry_time']<=l['time_utc']<s['end']
                assert l['cost']==pytest.approx(l['fraction']*(l['price']+p['entry'])*.0002)
            if p['remaining']:assert p['net'] is None and not p.get('exit_time')
            else:assert p['net']==pytest.approx(sum(l['net'] for l in p['legs']))
        for d in r['pattern_decisions']:
            assert d['detected_at']==d['available_after'] and 'assumed' in d['clock_basis']
            if d['accepted']:assert d['route']=='B1' and d['match']['accepted']


def test_prefix_replay_reproduces_real_entry_without_future_market_bars(saved):
    view,folder,s=saved;r=view.result(folder,'NBIS');p=r['trades'][0];boundary=ts(p['entry_time'])
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=PatternReplay(ts(s['start']),ts(s['end']),db,Config(first_sale_fraction=.25,resistance_mode='major1h'),symbol='NBIS',library=read(folder/'LIBRARY.json'))
    try:
        with gzip.open(folder/'data/NBIS_MINUTES.jsonl.gz','rt') as f:
            for line in f:
                b=json.loads(line)
                if b['t']>boundary:break
                e.received_at=b['t']+60;e.minute(b)
        assert e.position
        for key in ('entry','entry_time','initial_stop','t1','references'):assert e.position[key]==p[key]
    finally:db.close()


def test_empty_symbols_show_no_fabricated_trade_and_safe_exports(saved):
    view,_,_=saved
    d=view.snapshot('CIFR');assert d['trades']==[] and d['selected'] is None and d['rows']==[]
    assert d['decisions']
    for symbol,name in [('all','TRADES.csv'),('TQQQ','PROTECTION.csv'),('SOXX','result.json')]:assert view.export(symbol,name).is_file()
    with pytest.raises(ValueError):view.snapshot('../.env')
    with pytest.raises(ValueError):view.snapshot('CIFR',1)
    with pytest.raises(ValueError):view.export('all','../.env')


def test_read_only_http_never_starts_jobs_or_orders(saved,monkeypatch):
    import threading,urllib.request,urllib.error
    from http.server import ThreadingHTTPServer
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    from trading_desk import pattern_backtest_view as module
    view,_,_=saved;monkeypatch.setattr(module,'BACKTEST_VIEW',view)
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
    base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/pattern-backtest?symbol=TQQQ') as response:
            d=json.load(response);assert d['selected']['symbol']=='TQQQ' and not d['orders_enabled']
        with urllib.request.urlopen(base+'/api/pattern-backtest/export?symbol=all&file=TRADES.csv') as response:
            assert 'attachment' in response.headers['Content-Disposition']
        req=urllib.request.Request(base+'/api/pattern-backtest',data=b'{"operation":"submit"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
