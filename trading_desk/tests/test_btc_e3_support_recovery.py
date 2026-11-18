"""Causal recovery explanations on actual archived observations only."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.audit_btc_e3_support_recovery import observed_bars, confirmed_pivots, snapshot
from trading_desk.btc_data import ts


@pytest.fixture
def actual():
    data = json.loads((Path(__file__).parent/'fixtures/e3_draft1_actual.json').read_text())
    cases = {p['label']: p for p in data['cases']}
    for p in cases.values():
        if p['receipts'] is not None:
            p['receipts'] = {int(t): v for t, v in p['receipts'].items()}
    return cases


def test_future_bottom_not_available_at_E3(actual):
    p = actual['Nov15-0144']
    at = max(p['receipts'][b['t']] for b in p['rows']
             if ts('2026-11-15T07:35:00Z') <= b['t'] < ts('2026-11-15T07:45:00Z'))
    result = snapshot(p['rows'], p['trade'], at, p['receipts'])
    assert result['local_HL_broken'] and not result['parent_D_broken']
    assert all(x['price'] != 63735.105 for x in result['confirmed_post_entry_pivots'])
    assert any(x['price'] == 64519.06 for x in result['confirmed_post_entry_pivots'])
    prefix = [b for b in p['rows'] if b['t'] + 60 <= at]
    assert snapshot(prefix, p['trade'], at, p['receipts']) == result


def test_bottom_requires_right_bar_and_actual_delivery(actual):
    p = actual['Nov15-0144']
    pivots = confirmed_pivots(observed_bars(p['rows'], 900, p['receipts']))
    bottom = next(x for x in pivots if x['price'] == 63735.105)
    assert bottom['time'] == ts('2026-11-15T07:51:00Z')
    assert bottom['known_at'] == ts('2026-11-15T08:15:00Z')
    assert bottom['available_at'] > bottom['known_at']
    before = snapshot(p['rows'], p['trade'], bottom['available_at'] - .001, p['receipts'])
    after = snapshot(p['rows'], p['trade'], bottom['available_at'], p['receipts'])
    assert bottom not in before['confirmed_post_entry_pivots']
    assert bottom in after['confirmed_post_entry_pivots']


def test_reclaim_bar_not_complete_before_last_minute_arrives(actual):
    p = actual['Nov15-0144']
    bars = observed_bars(p['rows'], 900, p['receipts'])
    reclaim = next(b for b in bars if b['t'] == ts('2026-11-15T08:15:00Z'))
    assert reclaim['close'] == pytest.approx(64469.47)
    before = snapshot(p['rows'], p['trade'], reclaim['end'], p['receipts'])
    assert before['last_complete_15m']['t'] < reclaim['t']
    after = snapshot(p['rows'], p['trade'], reclaim['available_at'], p['receipts'])
    assert after['last_complete_15m']['t'] == reclaim['t']


def test_missing_actual_minute_is_partial_and_cannot_confirm_bottom(actual):
    p = actual['Nov15-0144']
    # Remove an observation, never invent or change a market price.
    rows = [b for b in p['rows'] if b['t'] != ts('2026-11-15T08:14:00Z')]
    bars = observed_bars(rows, 900, p['receipts'])
    right = next(b for b in bars if b['t'] == ts('2026-11-15T08:00:00Z'))
    assert not right['complete'] and right['observed_minutes'] == 14
    assert not any(x['price'] == 63735.105 for x in confirmed_pivots(bars))


def test_parent_and_local_support_are_separate_at_original_winner_exit(actual):
    p = actual['winner-33']
    at = ts('2026-10-18T19:40:00Z')
    result = snapshot(p['rows'], p['trade'], at)
    assert result['local_HL_broken'] and not result['parent_D_broken']
    assert p['trade']['references']['l1']['price'] == 79691.8665
    assert result['lowest_since_entry'] < p['trade']['references']['l2']['price']
    assert result['lowest_since_entry'] > p['trade']['references']['l1']['price']


def test_snapshot_never_consumes_later_recovery(actual):
    p = actual['winner-33']; at = ts('2026-10-18T19:41:00Z')
    full = snapshot(p['rows'], p['trade'], at)
    prefix = [b for b in p['rows'] if b['t'] + 60 <= at]
    assert snapshot(prefix, p['trade'], at) == full
    assert full['lowest_since_entry'] > 80583.6565

