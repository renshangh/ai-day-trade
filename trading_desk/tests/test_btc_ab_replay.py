"""Entry-only integration, on archived real minutes; no synthetic OHLC bars."""
import copy
import json
import sqlite3
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk import btc_engine,btc_data,btc_lab
from trading_desk.btc_ab_replay import ABReplay
import review_btc_nov06_07_swings as old_case
import audit_btc_nov08_1745_shock as shock_case


def engine(cls,start=0,**kwargs):
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    return cls(start,9999999999,db,**kwargs)


def test_auto_a_recovers_owner_2145_bar_without_annotation_overrides():
    _,minutes=old_case.load()
    e=engine(ABReplay,btc_data.ts('2026-11-07T00:00:00-04:00'))
    for b in minutes:e.minute(b)
    r=e.finish()
    s=next(s for s in r['signals'] if s['time_ny'].startswith('2026-11-07T21:58'))
    assert 'A' in s['routes'] and s['structural_price_signal']
    assert s['entry_reference']==pytest.approx(75655.545)
    assert s['references']['l1']['price']==75462.2
    assert len(s['setup_evidence']['lows'])>=4
    assert s['setup_evidence']['hl']['price']==75545.7915
    assert all(p['known_at']<=btc_data.ts(s['time_utc']) for p in s['setup_evidence']['lows'])
    assert s['time_utc'] < s['interval_end']
    # Selection is structural; there are no injected owner low times in the detector.
    assert 'owner' not in s['setup_evidence']


def test_auto_b_retains_signal_even_when_no_target_or_2r_qualification():
    _,minutes,_,_=shock_case.load()
    e=engine(ABReplay)
    for b in minutes:e.minute(b)
    r=e.finish()
    s=next(s for s in r['signals'] if s['time_ny'].startswith('2026-11-08T17:58'))
    assert s['route']=='B' and s['structural_price_signal']
    assert s['entry_reference']==pytest.approx(74429.2125)
    assert s['initial_stop']==pytest.approx(73454.89409821428)
    assert not s['qualified_candidate'] and s['trade_id'] is None
    assert s['decision']=='risk_rejected'
    assert r['metrics']['closed']==0
    # Without the nine-day target context, absence stays explicit, not invented.
    assert s['t1'] is None and s['net_reward_risk'] is None


def test_later_bars_do_not_rewrite_earlier_signals():
    _,minutes,_,_=shock_case.load()
    e=engine(ABReplay)
    cutoff=btc_data.ts('2026-11-08T18:00:00-05:00')
    for b in minutes:
        if b['t']<cutoff:e.minute(b)
    before=copy.deepcopy(e.signals)
    for b in minutes:
        if b['t']>=cutoff:e.minute(b)
    assert before==e.signals[:len(before)]


def test_exit_methods_are_inherited_and_identical_on_real_minutes():
    assert ABReplay.close_part is btc_engine.Replay.close_part
    assert ABReplay.targets is btc_engine.Replay.targets
    path=ROOT/'reports/btc_structure_2026_11_08/entry_examples/minute_rejection_2026_11_08/COINBASE_BTCUSD_1M_RAW.json'
    minutes=sorted([dict(t=t,low=l,high=h,open=o,close=c,volume=v) for t,l,h,o,c,v in json.loads(path.read_text())],key=lambda b:b['t'])
    rows=[b for b in minutes if 1794143700<=b['t']<1794144600]
    outputs=[]
    for cls in (btc_engine.Replay,ABReplay):
        e=engine(cls,**({"exit_policy":"approved_v1"} if cls is ABReplay else {}))
        # Hypothetical held position; source candles are never altered.
        e.position=dict(id=1,entry=75650,initial_risk=244,stop=75674.10142857143,
            t1=76118.18496,t2=None,remaining=1.,legs=[],peak=76094.99,
            peak_before_period=76017.37,protected_t=1794140000,protected_low=75690,
            pending_lows=[],entry_period=1794083400,gap_exposed=False,context_partial=False)
        e.minutes=rows[:14];e.bucket=rows[0]['t'];e.prev={'close':76015.63}
        e.last_minute=rows[13]['t'];e.minute(rows[-1])
        outputs.append(e.trades[0]['legs'])
    assert outputs[0]==outputs[1]


def test_gap_resets_structure_without_filling_market_data():
    _,minutes,_,_=shock_case.load();e=engine(ABReplay)
    omitted=btc_data.ts('2026-11-08T17:00:00-05:00')
    actual=[b for b in minutes if not omitted<=b['t']<omitted+900]
    for b in actual:e.minute(b)
    r=e.finish()
    assert r['counts']['missing_minutes']==15
    assert e.detector.generation>0
    assert not any(s['time_ny'].startswith('2026-11-08T17:58') for s in r['signals'])
    assert e.db.execute('SELECT count(*) FROM ledger WHERE t=?',(omitted,)).fetchone()[0]==0


def test_exports_whitelist_and_legacy_runs_remain_readable(tmp_path):
    run='20261109T000000Z-30-ab';folder=tmp_path/'runs'/run;folder.mkdir(parents=True)
    btc_data.save(folder/'result.json',dict(status='complete'))
    (folder/'SIGNALS.csv').write_text('id\n1\n')
    lab=btc_lab.Lab(tmp_path)
    assert lab.result(run)['status']=='complete'
    assert lab.export(run,'SIGNALS.csv').name=='SIGNALS.csv'
    for name in ('../result.json','result.json','.env'):
        with pytest.raises(ValueError):lab.export(run,name)
    with pytest.raises(ValueError):lab.export('../'+run,'SIGNALS.csv')
