"""Real-minute continuation of a frozen position, never a new monthly study."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_night_continuation as audit
from trading_desk.btc_data import ts,STORE


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_original_checkpoint_and_first_profit_are_preserved(reviewed):
    old=json.loads(audit.BASE.read_text())['cases'][1]['trade']
    checkpoint=reviewed['checkpoint_state'];p=reviewed['case']['trade']
    assert reviewed['rule_code_unchanged'] and reviewed['case']['checkpoint_unchanged']
    for key in ('entry_time','entry','initial_stop','t1','t2','remaining','legs','structure_reference',
                'structure_history','active_wave_high','armed_midpoint','giveback_state'):
        assert checkpoint.get(key)==old.get(key)
    assert checkpoint['remaining']==.75
    assert p['legs'][0]==old['legs'][0]
    assert p['entry_time']=='2026-10-13T01:00:00Z' # Oct12 21:00 EDT, not a new 01:45 entry.


def test_earliest_exit_is_structure_break_not_half_profit_giveback(reviewed):
    p=reviewed['case']['trade'];l=p['legs'][-1];e=reviewed['trigger_evidence']
    assert p['status']=='closed' and p['remaining']==0
    assert l['reason']=='structure_exit_remaining'
    assert l['time_utc']=='2026-10-13T08:50:00Z'
    assert l['price']==83550.7475 and l['fraction']==.75
    assert reviewed['exit_minute']['open']>l['price']>reviewed['exit_minute']['low']
    assert e['phase']==1 and e['interval_end']=='2026-10-13T08:51:00Z'
    assert reviewed['trigger_giveback_fraction']==pytest.approx(.19526812005216243)
    assert reviewed['trigger_giveback_fraction']<.5
    assert not p.get('giveback_exits')
    assert reviewed['continuation_max_open_giveback']<.5


def test_confirmed_lows_wait_for_completed_new_high_and_activate_before_exit(reviewed):
    updates=reviewed['structure_updates']
    assert [h['price'] for h in updates]==[83475.153,83550.7475]
    assert [h['known_at'] for h in updates]==[ts('2026-10-13T02:30:00-04:00'),ts('2026-10-13T03:30:00-04:00')]
    assert all(h['effective_at']==ts('2026-10-13T03:45:00-04:00') for h in updates)
    assert all(h['breakout_bar']==ts('2026-10-13T03:30:00-04:00') for h in updates)
    assert all(h['prior_peak']==83816.2 for h in updates)
    assert reviewed['case']['trade']['structure_reference']==updates[-1]


def test_pnl_is_complete_realized_trade_not_old_checkpoint_valuation(reviewed):
    c=reviewed['case'];legs=c['trade']['legs']
    assert len(legs)==2 and sum(l['fraction'] for l in legs)==1
    assert legs[0]['net']==pytest.approx(383.0192816714264)
    assert legs[1]['gross']==pytest.approx(1615.126125)
    assert legs[1]['cost']==pytest.approx(24.742199025)
    assert legs[1]['net']==pytest.approx(1590.383925974999)
    assert c['realized_net']==pytest.approx(1973.4032076464252)
    assert c['realized_net']==pytest.approx(c['realized_gross']-c['realized_cost'])


def test_final_candle_is_explicitly_partial_and_no_future_close_is_claimed(reviewed):
    last=reviewed['continuation_rows'][-1]
    assert len(reviewed['continuation_rows'])==13
    assert last['t']==ts('2026-10-13T04:45:00-04:00')
    assert last['observed_minutes']==6 and last['is_complete'] is False
    assert last['observed_end_exclusive']=='2026-10-13T08:51:00Z'
    assert last['close']==83521.56 # 04:50 minute close, not a future 05:00 close.
    assert all(b['is_complete'] for b in reviewed['continuation_rows'][:-1])
    assert reviewed['minute_coverage']==dict(full_position=471,continuation=186,missing=0)


def test_exit_does_not_need_any_minute_after_exit_and_no_earlier_exit(monkeypatch,reviewed):
    source,m=audit.load();exit_at=ts(reviewed['case']['trade']['exit_time'])
    monkeypatch.setattr(audit,'load',lambda:(source,[b for b in m if b['t']<=exit_at]))
    replay=audit.review()
    assert replay['case']['trade']['legs']==reviewed['case']['trade']['legs']
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=audit.engine_for_case(ts(reviewed['case']['nominated_bar']),exit_at,db)
    for b in m:
        if b['t']>=exit_at:break
        e.minute(b)
    p=e.finish()['trades'][0]
    assert p['status']=='open' and p['remaining']==.75 and len(p['legs'])==1
    db.close()


def test_prior_reports_and_month_registry_are_read_only(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly rerun forbidden'))
    paths=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json',audit.BASE]
    paths+=list(audit.FOLDER.parent.glob('*/REVIEW.json'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=audit.review()
    assert not r['month_rerun'] and not r['broker_orders'] and not r['paper_orders']
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
