"""Every losing record is audited against preserved real market observations."""
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_all_losses as audit
from trading_desk.btc_data import STORE,read,ts


@pytest.fixture(scope='module')
def original():return audit.audit_losses(read(STORE/'runs'/audit.BASELINE/'result.json'))


def test_every_original_loss_is_included_and_execution_is_checked(original):
    result=read(STORE/'runs'/audit.BASELINE/'result.json')
    assert [r['old_trade_id'] for r in original]==[p['id'] for p in result['trades'] if p['net']<0]
    assert len(original)==27
    assert sum(r['static_reused_history'] for r in original)==19
    assert all(r['causal_inputs'] and all(r['exit_checks'].values()) for r in original)
    assert [r['old_trade_id'] for r in original if r['gross']>0]==[38,41,42]


def test_corrected_sequence_never_reuses_pre_entry_structure():
    folder=STORE/'runs'/'20261109T034016Z-30-ab'
    if not (folder/'result.json').exists():pytest.skip('Requires saved corrected real-minute run')
    result=read(folder/'result.json');previous=None
    signals={s['id']:s for s in result['signals']}
    for p in result['trades']:
        setup=signals[p['signal_id']]['setup_evidence']
        origin=setup['origin']['time'] if 'origin' in setup else setup['impulse']['t']
        if previous:assert origin>=(ts(previous['entry_time'])//900+1)*900
        previous=p
    losses=audit.audit_losses(result,expected_count=None)
    assert len(losses)==19
    assert not any(r['static_reused_history'] for r in losses)
    assert all(all(r['exit_checks'].values()) for r in losses)


def test_auditing_losses_cannot_submit_orders_or_run_a_month(monkeypatch,original):
    monkeypatch.setattr(audit.btc_engine,'run',lambda *a,**kw:pytest.fail('Audit must not rerun month'))
    result=read(STORE/'runs'/audit.BASELINE/'result.json')
    assert len(audit.audit_losses(result))==len(original)
