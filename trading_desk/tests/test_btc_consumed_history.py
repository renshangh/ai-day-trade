"""A filled entry consumes setup history; archived market bars remain unchanged."""
import hashlib
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_oct12_consumed_history as audit
from scripts.audit_btc_oct12_b_branches import load
from trading_desk.btc_data import ts
from trading_desk.btc_engine import create_replay


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_same_impulse_b2_is_removed_without_altering_first_trade(reviewed):
    before=reviewed['variants']['before'];after=reviewed['variants']['after']
    assert [p['entry_rule'] for p in before['trades']]==['B1','B2']
    assert [p['entry_rule'] for p in after['trades']]==['B1']
    assert before['trades'][0]['legs']==after['trades'][0]['legs']
    assert after['trades'][0]['net']==pytest.approx(218.89633641039558)
    assert after['at_old_reentry']['ready_routes']==[]
    assert not any(s['time_utc']=='2026-10-12T14:31:00Z' for s in after['signals'])


def test_entry_candle_cannot_repopulate_pre_entry_history(reviewed):
    after=reviewed['variants']['after']
    event=next(e for row in after['rows'] for e in row['events'] if e['type']=='entry_history_consumed')
    assert event['time_utc']=='2026-10-12T13:33:00Z'
    assert event['fresh_bars_from']=='2026-10-12T13:45:00Z'
    entry_bar=next(row for row in after['rows'] if row['time']=='2026-10-12T13:30:00Z')
    assert entry_bar['entry_setups']=={}
    for row in after['rows']:
        if row['time']<reviewed['fresh_bars_from']:continue
        for state in row.get('entry_setups',{}).values():
            assert state['d']['time']>=ts(reviewed['fresh_bars_from'])


def test_b2_still_valid_when_no_prior_entry_consumed_the_episode():
    _,minutes=load();db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    # A new run with no earlier fill may choose B2 independently. This does
    # not disable a branch globally or consume setups merely for a signal.
    e=create_replay(audit.START,audit.END,db,expanded_b=True)
    scan=e.scan
    e.scan=lambda b,can_trade:scan(b,can_trade=can_trade and b['t']>=ts('2026-10-12T10:30:00-04:00'))
    for b in minutes:
        if b['t']>=audit.END:break
        e.minute(b)
    result=e.finish()
    assert result['trades'][0]['entry_rule']=='B2'
    assert result['trades'][0]['entry_time']=='2026-10-12T14:31:00Z'
    db.close()


def test_local_audit_leaves_monthly_results_and_pointer_unchanged(reviewed):
    assert reviewed['month_rerun'] is False and reviewed['broker_orders']==0
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
        for path,digest in reviewed['historical_sha256'].items())
