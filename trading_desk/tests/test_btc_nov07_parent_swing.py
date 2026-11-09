"""Parent confirmation and a new early-exit clause must not be conflated."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_nov07_parent_swing as audit


@pytest.fixture(scope='module')
def result():
    root=ROOT/'reports/btc_structure_2026_11_08'
    preserved=[root/'major_resistance/MAJOR_RETEST.json',root/'BTC_30_DAY_RETEST.xlsx',
        root/'entry_examples/NOV07_USER_STRUCTURE.json',root/'entry_examples/OCT11_USER_STRUCTURE.json',
        ROOT/'scripts/clarify_btc_nov07_structure.py',
        ROOT/'docs/investigations/2026-11-08_BTC_NOV07_STRUCTURE_CLARIFICATION.md']
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    r=audit.review(root)
    assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in preserved]
    return r


def test_only_completed_same_level_lows_raise_protection(result):
    p=result['parent_stop_only'];events=p['events']
    assert [e['reason'] for e in events]==['raise_parent_stop','raise_parent_stop']
    assert [e['effective_from_ny'] for e in events]==['2026-11-08T03:00:00-05:00','2026-11-08T07:00:00-05:00']
    assert [e['reference_low'] for e in events]==[75655.86,75690]
    assert [e['price_reference'] for e in events]==pytest.approx([75640.70482142858,75674.10142857143])
    for e in events:
        assert audit.stamp(e['parent_low_confirmed_ny'])<=audit.stamp(e['effective_from_ny'])
        assert audit.stamp(e['reference_peak_confirmed_ny'])<=audit.stamp(e['effective_from_ny'])
        assert audit.stamp(e['breakout_interval_start_ny'])+audit.STEP<=audit.stamp(e['effective_from_ny'])
    rows={r['start_ny']:r for r in p['rows']}
    assert rows['2026-11-08T02:45:00-05:00']['active_stop']==result['initial_stop_reference']
    assert rows['2026-11-08T03:00:00-05:00']['active_stop']==events[0]['price_reference']
    assert rows['2026-11-08T06:30:00-05:00']['active_stop']==events[0]['price_reference']
    assert rows['2026-11-08T07:00:00-05:00']['active_stop']==events[1]['price_reference']
    assert rows['2026-11-08T08:15:00-05:00']['active_stop']==events[1]['price_reference']


def test_stop_change_alone_does_not_create_unreached_target_sales(result):
    p=result['parent_stop_only']
    assert result['fixed_target_reference']==pytest.approx(76118.18496428571)
    assert len(p['rows'])==54
    assert max(b['high'] for b in p['rows'])<result['fixed_target_reference']
    assert all(b['low']>b['active_stop'] for b in p['rows'])
    assert p['remaining']==1 and p['pnl_legs']==[]
    assert p['realized_net_per_initial_btc']==0
    assert p['unrealized_gross_at_snapshot']==pytest.approx(316.27)
    assert result['old_micro_stop']['net_per_initial_btc']==pytest.approx(6.68689485714)


def test_candidate_confirmation_fill_order_and_costs_are_explicit(result):
    c=result['additional_early_exit_candidate'];events=c['events']
    assert c['signal_start_ny']=='2026-11-08T08:15:00-05:00'
    assert c['signal_end_ny']=='2026-11-08T08:30:00-05:00'
    assert c['upper_wick_fraction']==pytest.approx(79.37/150.22)
    assert [e['fraction_initial'] for e in events]==[.25,.75]
    assert all(e['known_at_ny']=='2026-11-08T08:30:00-05:00' for e in events)
    assert [e['price_reference'] for e in events]==[75956.20,75944.77]
    assert events[1]['interval_end_ny']=='2026-11-08T08:45:00-05:00'
    # Open is above the already-known trigger: first trim precedes its crossing.
    assert events[0]['price_reference']>c['signal_low']>c['structural_stop_at_trim']
    assert [l['net_pnl'] for l in c['pnl_legs']]==pytest.approx([68.96969,198.3382845])
    assert c['realized_gross_per_initial_btc']==pytest.approx(297.6275)
    assert c['realized_net_per_initial_btc']==pytest.approx(267.3079745)
    assert sum(l['quantity_btc'] for l in c['pnl_legs'])==1
    assert c['status'].startswith('candidate only')


def test_prefixes_cannot_use_unfinished_parent_confirmation(result):
    root=ROOT/'reports/btc_structure_2026_11_08'
    _,bars,_,_=audit.load_source(root)
    frozen=json.loads((root/'major_resistance/MAJOR_RETEST.json').read_text())['runs'][1]
    old=json.loads((root/'entry_examples/NOV07_USER_STRUCTURE.json').read_text())
    atr={audit.stamp(r['start_utc'])+audit.STEP:r['atr'] for r in frozen['ledger']}
    for ending,count in [('2026-11-08T02:45:00-05:00',0),('2026-11-08T03:00:00-05:00',1),
                         ('2026-11-08T06:30:00-05:00',1),('2026-11-08T07:00:00-05:00',2)]:
        end=audit.stamp(ending)
        trace=audit.trace_parent([b for b in bars if b['t']<end],atr,
            audit.stamp(old['entry_interval_start_ny']),old['anchors']['L2'],old['initial_stop_reference'],
            old['target1_reference'],old['next_target_reference'],old['primary_supply_zone']['lower'],
            audit.Config(**frozen['config']),end)
        assert trace['events']==result['parent_stop_only']['events'][:count]
