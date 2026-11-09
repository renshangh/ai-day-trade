"""Read-only audit uses complete archived observations and explicit known times."""
import hashlib
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_trade5_b1 as audit
from trading_desk.btc_data import STORE,ts


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_b1_passes_but_no_independent_15m_hl_is_claimed(reviewed):
    assert reviewed['summary']['b1_passed'] is True
    assert reviewed['summary']['b2_passed'] is False
    assert reviewed['summary']['fifteen_minute_hl_present'] is False
    assert reviewed['source_minutes']==105 and reviewed['missing_minutes']==0
    assert len(reviewed['bars_15m'])==7
    assert all(b['observed_minutes']==15 for b in reviewed['bars_15m'])
    assert reviewed['summary']['stabilization_close_location']==pytest.approx(.9529151868925966)


def test_micro_higher_lows_have_distinct_confirmation_times(reviewed):
    points={p['time']:p for p in reviewed['minute_turns']}
    for when,price,known in [('13:36',80039.9,'13:38'),('13:41',80483.355,'13:43')]:
        p=points['2026-10-15T'+when+':00Z']
        assert p['kind']=='low' and p['price']==price and p['known_at_entry']
        assert p['known_at']=='2026-10-15T'+known+':00Z'
    late=points['2026-10-15T13:44:00Z']
    assert late['known_at']=='2026-10-15T13:46:00Z' and not late['known_at_entry']


def test_failed_minute_close_is_not_used_at_its_open(reviewed):
    s=reviewed['summary']
    assert s['entry_interval']==['2026-10-15T13:45:00Z','2026-10-15T13:46:00Z']
    assert s['earliest_completed_false_break_evidence']=='2026-10-15T13:46:00Z'
    assert s['entry_minute_high']>s['entry']>s['entry_minute_close']
    assert s['confirmed_post_entry_peak']<s['entry']


def test_stop_first_cross_and_post_exit_full_candle_are_separate(reviewed):
    s=reviewed['summary'];bars={b['time']:b for b in reviewed['minutes_1m']}
    assert bars['2026-10-15T13:52:00Z']['low']>s['d']>s['initial_stop']
    assert bars['2026-10-15T13:53:00Z']['open']>s['initial_stop']>bars['2026-10-15T13:53:00Z']['low']
    assert s['observed_interval_start_difference_minutes']==8
    final=reviewed['bars_15m'][-1]
    assert final['close_known_at']=='2026-10-15T14:00:00Z'
    assert not final['known_complete_at_entry']
    assert final['low_t']==ts('2026-10-15T09:55:00-04:00')>ts(s['stop_interval'][0])


def test_atr_and_loss_are_independently_reconciled(reviewed):
    a=reviewed['independent_atr'];s=reviewed['summary']
    assert a['actual_source_minutes']==300
    assert a['impulse_before']==pytest.approx(195.35164285714356)
    assert a['entry_before']==pytest.approx(315.1177425483215)
    assert s['initial_stop']==pytest.approx(s['d']-.25*a['entry_before'])
    assert s['net']==pytest.approx(-s['price_risk']-s['cost'])


def test_audit_does_not_replay_or_rewrite_the_month(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly run forbidden'))
    files=[STORE/'latest_run.json',STORE/'runs'/audit.RUN/'result.json',STORE/'runs'/audit.RUN/'RESEARCH.xlsx']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    r=audit.review()
    assert not r['parameters_changed'] and not r['month_rerun'] and r['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
