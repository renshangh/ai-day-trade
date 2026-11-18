"""E3 research-only causality on real archived minute observations."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.review_btc_e3_draft1 import RULE,scan_e3
from trading_desk.btc_data import ts


@pytest.fixture
def actual():
    source=json.loads((Path(__file__).parent/'fixtures/e3_draft1_actual.json').read_text())
    data={p['label']:p for p in source['cases']}
    for p in data.values():
        p['atr_by_quarter']={int(t):v for t,v in p['atr_by_quarter'].items()}
        if p['receipts'] is not None:p['receipts']={int(t):v for t,v in p['receipts'].items()}
    return data


def run(p):
    return scan_e3(p['trade'],p['rows'],p['atr_by_quarter'],p['cutoff'],p['receipts'])


def test_exact_case_uses_frozen_pre_window_ATR_and_next_minute_reference(actual):
    r=run(actual['Nov15-0144']);s=r['selected']
    assert s['signal_at']=='2026-11-15T07:45:00Z'
    assert s['execution_at']=='2026-11-15T07:46:00Z'
    assert s['ATR']==pytest.approx(276.1877857142863)
    assert s['down_atr']==pytest.approx(1.253306691694498)
    assert s['signal_reference']==63864.13
    assert s['execution_price']==63836.8905 and s['execution_price']!=s['signal_reference']
    assert s['net']==pytest.approx(-628.9079067000023)
    assert ts(s['inputs_received_at'])<ts(s['execution_at'])
    assert s['remaining']==1 and not s['earlier_original_legs']


def test_strict_prefix_does_not_need_later_recovery(actual):
    p=actual['Nov15-0144'];full=run(p)['selected'];prefix=copy.deepcopy(p)
    due=ts(full['execution_at']);prefix['rows']=[b for b in p['rows'] if b['t']<=due]
    prefix['cutoff']=due+60
    assert run(prefix)['selected']==full
    earlier=copy.deepcopy(prefix);earlier['rows']=[b for b in prefix['rows'] if b['t']<due]
    assert run(earlier)['selected'] is None


def test_missing_exact_execution_is_not_carried_to_the_next_price(actual):
    p=copy.deepcopy(actual['Nov15-0144']);due=ts('2026-11-15T07:46:00Z')
    p['rows']=[b for b in p['rows'] if b['t']!=due]
    r=run(p)
    assert r['attempts'][0]['status']=='missing_exact_execution_minute'
    assert not r['selected'] or r['selected']['execution_at']!='2026-11-15T07:47:00Z'


def test_incomplete_pair_cannot_generate_the_original_signal(actual):
    p=copy.deepcopy(actual['Nov15-0144']);p['rows']=[b for b in p['rows'] if b['t']!=ts('2026-11-15T07:38:00Z')]
    r=run(p);f=next(f for f in r['trace'] if f['known_at']=='2026-11-15T07:45:00Z')
    assert not f['complete'] and not f['qualified']


def test_delayed_receipt_cannot_backfill_a_price(actual):
    p=copy.deepcopy(actual['Nov15-0144'])
    # Fault injection changes delivery metadata only, never market bars.
    p['receipts'][ts('2026-11-15T07:44:00Z')]=ts('2026-11-15T08:00:00Z')
    r=run(p)
    assert r['attempts'][0]['status']=='signal_arrived_after_execution_reference'
    assert not r['selected'] or r['selected']['execution_at']!='2026-11-15T07:46:00Z'


def test_existing_exit_through_due_minute_has_priority(actual):
    p=copy.deepcopy(actual['Nov15-0144'])
    # Policy boundary injection: schedule metadata, not fabricated price data.
    p['trade']['status']='closed';p['trade']['exit_time']='2026-11-15T07:46:00Z'
    r=run(p)
    assert r['selected'] is None
    assert r['attempts'][0]['status']=='original_final_exit_priority'


def test_actual_fast_drop_without_support_failure_is_not_enough(actual):
    r=run(actual['winner-7'])
    assert r['selected'] is None
    rapid=[f for f in r['trace'] if f.get('gates',{}).get('rapid')]
    assert rapid and all(not f['gates']['A_close_below_HL'] for f in rapid)


def test_actual_winner_cut_is_reported_instead_of_threshold_tuning(actual):
    r=run(actual['winner-33']);s=r['selected']
    assert s['signal_at']=='2026-10-18T19:40:00Z'
    assert s['execution_at']=='2026-10-18T19:41:00Z'
    assert s['execution_price']==80754.04 and s['net']<0
    assert actual['winner-33']['trade']['net']>0
    assert RULE['rapid_drop_atr']==1.0 and RULE['execution_delay_seconds']==60


def test_untriggered_real_partial_sale_path_is_unchanged(actual):
    p=actual['winner-7'];original=copy.deepcopy(p['trade'])
    assert run(p)['selected'] is None
    assert p['trade']==original
    assert [l['fraction'] for l in p['trade']['legs']]==[.25,.75]
