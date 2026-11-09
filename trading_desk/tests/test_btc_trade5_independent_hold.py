"""Post-D confirmation cannot reuse D's candle or hindsight on real minutes."""
import hashlib
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_trade5_independent_hold as audit
from trading_desk.btc_data import STORE,read,ts
from trading_desk.btc_shock_branches import independent_b1_setup


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def test_old_entry_is_blocked_and_not_relabelled_as_a_delayed_trade(reviewed):
    assert reviewed['original_entry_avoided'] is True
    assert reviewed['old_entry_validation']['setup_passed'] is False
    assert reviewed['actual_entry_time'] is reviewed['actual_entry_price'] is None
    assert reviewed['initial_stop_activated_at'] is None
    assert reviewed['modeled_trades']==[] and reviewed['realized_net'] is None


def test_confirmation_occurrence_and_earliest_entry_are_distinct(reviewed):
    assert reviewed['d']['occurrence']=='2026-10-15T13:31:00Z'
    assert reviewed['d']['known_at_utc']=='2026-10-15T13:45:00Z'
    assert reviewed['confirmation']['time']=='2026-10-15T13:45:00Z'
    assert reviewed['confirmation']['completion_known_at']=='2026-10-15T14:00:00Z'
    assert reviewed['earliest_possible_entry_if_confirmation_passed']=='2026-10-15T14:00:00Z'


def test_intraminute_d_break_invalidates_even_though_final_close_recovers(reviewed):
    assert reviewed['first_d_break']['interval_start']=='2026-10-15T13:53:00Z'
    assert reviewed['first_d_break']['known_by']=='2026-10-15T13:54:00Z'
    assert reviewed['first_d_break']['low']<reviewed['d']['price']
    assert reviewed['confirmation']['low']<reviewed['d']['price']<reviewed['confirmation']['close']
    assert reviewed['final_validation']['setup_passed'] is False
    assert reviewed['candidate_trigger_active'] is False


def test_no_minute_in_the_waiting_candle_is_eligible(reviewed):
    assert len(reviewed['minute_history'])==15
    assert not any(m['candidate_eligible_at_open'] for m in reviewed['minute_history'])
    after=[m for m in reviewed['minute_history'] if ts(m['time'])>=ts('2026-10-15T09:54:00-04:00')]
    assert all(m['d_intact_at_open'] is False for m in after)


def test_real_independent_hold_can_pass_but_not_before_its_close():
    folder=ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_b_branches'
    saved=read(folder/'B_BRANCH_REVIEW.json')['cases'][0]['signal']
    setup=saved['setup_evidence'];bar=setup['stabilization_bar']
    # This archived 09:15 candle contains D. The separate 09:30 candle
    # appears in the frozen real-minute archive; no bars are invented.
    from trading_desk.btc_engine import aggregate
    minutes=read(folder/'ALPACA_OBSERVED_MINUTES.json')
    start=setup['d']['known_at']
    hold=aggregate([m for m in minutes if start<=m['t']<start+900],900)
    assert hold['low']>setup['d']['price'] and hold['observed_minutes']==15
    assert not independent_b1_setup(setup,start+899,hold)['setup_passed']
    ready=independent_b1_setup(setup,start+900,hold)
    assert ready['setup_passed'] is True
    assert ready['trigger_reference']==pytest.approx(hold['high']+.01)
    assert not independent_b1_setup(setup,start+900,hold,d_intact=False)['setup_passed']


def test_no_month_or_historical_results_are_changed(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly replay forbidden'))
    files=[STORE/'latest_run.json',STORE/'runs'/audit.original_audit.RUN/'result.json',STORE/'runs'/audit.original_audit.RUN/'RESEARCH.xlsx']
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    r=audit.review()
    assert not r['month_rerun'] and not r['monthly_default_changed'] and r['broker_orders']==0
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items())
    assert folders==sorted(p.name for p in (STORE/'runs').iterdir())
