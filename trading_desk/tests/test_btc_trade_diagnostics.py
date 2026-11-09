"""Frozen-trade diagnostics preserve trading rules and use only real observations."""
import hashlib
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import analyze_btc_simulated_trades as analysis


@pytest.fixture(scope='module')
def report():
    root=ROOT/'reports/btc_structure_2026_11_08'
    frozen=root/'major_resistance/MAJOR_RETEST.json'
    before=hashlib.sha256(frozen.read_bytes()).hexdigest()
    result=analysis.diagnose(root)
    assert hashlib.sha256(frozen.read_bytes()).hexdigest()==before
    return result


def test_context_is_known_before_entry_and_no_strategy_rerun(report):
    assert len(report['rows'])==10
    assert report['baseline_config']['stop_buffer_atr']==.25
    assert report['baseline_config']['major_pivot_hours']==2
    for r in report['rows']:
        at=datetime.fromisoformat(r['entry_time_ny'])
        for key in ('hourly','fourhour'):
            assert datetime.fromisoformat(r[key]['last_end_utc'].replace('Z','+00:00'))<=at


def test_same_entry_bar_stop_keeps_favorable_excursion_uncertain(report):
    r=next(x for x in report['rows'] if x['id']==9)
    assert r['hold_min_minutes']==0 and r['hold_max_minutes']==15
    assert r['favorable_stop_distance_lower']==0
    assert r['favorable_stop_distance_upper']==pytest.approx(.2930427602285174)
    assert not r['stop_bar_also_traded_through_t1']


def test_missing_full_followup_is_not_reported_as_no_recovery(report):
    r=next(x for x in report['rows'] if x['id']==10)
    follow=r['post_exit'][-1]
    assert follow['hours']==24 and follow['complete'] is False
    assert follow['observed_bars']==76 and follow['expected_bars']==96
    assert 'first_close_above_entry_utc' not in follow


def test_losing_stops_and_winning_trailing_exit_are_distinct(report):
    losses=[r for r in report['rows'] if r['net_r']<0]
    winner=next(r for r in report['rows'] if r['net_r']>0)
    assert len(losses)==9 and all(r['initial_stop_touched'] for r in losses)
    assert not winner['initial_stop_touched']
    assert sum(r['favorable_stop_distance_upper']<1 for r in losses)==8
    assert sum(r['fourhour']['sma20_change']<0 for r in losses)==8
    assert winner['fourhour']['sma20_change']<0
