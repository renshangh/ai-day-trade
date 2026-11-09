"""Causal alternative exits on two real cases; no monthly or release changes."""
import copy
import hashlib
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.audit_btc_release01_early_failure import review,completed_scan,value_exit,RUN
from scripts.audit_btc_release01_pullbacks import review as source_review
from trading_desk.btc_data import STORE,ts


@pytest.fixture(scope='module')
def source_cases():return {c['trade_id']:c for c in source_review()['cases'] if c['trade_id'] in (32,30)}


@pytest.fixture(scope='module')
def reviewed():return {c['trade_id']:c for c in review()['cases']}


def test_trade32_both_alternatives_use_next_observed_open_and_existing_costs(reviewed):
    c=reviewed[32];a=c['alternatives']['A'];b=c['alternatives']['B']
    assert c['baseline_exit']=='2026-11-05T22:47:00Z'
    assert a['signal']['confirmed_at']==a['exit_time']=='2026-11-05T17:15:00Z'
    assert a['exit_price']==76079.9285 and a['exit_price']!=a['signal']['evidence']['close']
    assert a['net']==pytest.approx(-211.34964770000315) and a['net_change']==pytest.approx(521.3167157999875)
    assert b['signal']['confirmed_at']==b['exit_time']=='2026-11-05T20:15:00Z'
    assert b['exit_price']==75961.01 and b['net']==pytest.approx(-330.2443640000029)
    assert b['net_change']==pytest.approx(402.42199949998775)
    for p in (a,b):
        assert p['remaining']==1 and len(p['legs'])==1
        assert p['cost']==pytest.approx((p['exit_price']+c['entry']['entry'])*.0002)
        assert p['gross']-p['cost']==pytest.approx(p['net'])
        assert p['legs'][0]['fraction']==1
    assert a['minutes_earlier']==332 and b['minutes_earlier']==152


def test_reclaim_failure_evidence_cannot_be_backdated(reviewed):
    e=reviewed[32]['alternatives']['B']['signal']['evidence']
    assert e['weakness_known_at']=='2026-11-05T17:15:00Z'
    assert e['reclaim']['time']=='2026-11-05T19:30:00Z'
    assert e['reclaim']['end']=='2026-11-05T19:45:00Z'
    assert e['reclaim']['close']>e['trigger']
    assert e['failed_reclaim_bar']['end']=='2026-11-05T20:00:00Z'
    assert e['followthrough']['end']=='2026-11-05T20:15:00Z'
    assert e['lower_high_than_failure'] and e['lower_low_than_failure']
    assert e['known_postentry_high_before_weakness']==76927.482
    assert e['reclaim_attempt_high']==76438.1345 and e['reclaim_below_known_high']
    assert e['red'] and e['not_above_previous_close'] and not e['full_inside'] and not e['body_inside']


def test_trade30_preserves_both_original_legs_and_resets_downward_count(reviewed):
    c=reviewed[30]
    for p in c['alternatives'].values():
        assert not p['triggered'] and p['original_exit_retained']
        assert p['net']==pytest.approx(1454.4912061761684) and p['net_change']==0
        assert p['legs']==c['baseline_legs']
        assert [l['fraction'] for l in p['legs']]==[.25,.75]
    bar=next(t for t in c['trace'] if t['bar_time']=='2026-11-04T14:15:00Z')
    assert bar['confirmed_at']=='2026-11-04T14:30:00Z'
    assert bar['red'] and bar['below_original_trigger']
    assert bar['consecutive_down_comparisons']==0 and not bar['A_qualified']
    assert all(t['weakness_known_at'] is None for t in c['trace'])


def test_actual_prefixes_give_identical_first_signals_without_later_data(source_cases):
    c=source_cases[32];all_signals=completed_scan(c)
    assert completed_scan(c,cutoff=ts('2026-11-05T17:14:00Z'))['A'] is None
    first=completed_scan(c,cutoff=ts('2026-11-05T17:15:00Z'))
    assert first['A']==all_signals['A'] and first['B'] is None
    assert completed_scan(c,cutoff=ts('2026-11-05T20:14:00Z'))['B'] is None
    assert completed_scan(c,cutoff=ts('2026-11-05T20:15:00Z'))['B']==all_signals['B']
    limited=copy.deepcopy(c)
    limited['bars']=[b for b in c['bars'] if ts(b['end'])<=ts('2026-11-05T20:15:00Z')]
    limited['minutes']=[m for m in c['minutes'] if ts(m['time'])<=ts('2026-11-05T20:15:00Z')]
    scan=completed_scan(limited)
    assert scan['A']==all_signals['A'] and scan['B']==all_signals['B']
    assert value_exit(limited,scan['B'])['exit_price']==75961.01


def test_missing_actual_execution_minute_is_not_filled(source_cases):
    c=copy.deepcopy(source_cases[32]);signal=completed_scan(c)['A']
    c['minutes']=[m for m in c['minutes'] if m['time']!=signal['confirmed_at']]
    p=value_exit(c,signal)
    assert p['triggered'] and not p['execution_observation_available']
    assert p['net'] is p['exit_price'] is p['exit_time'] is p['net_change'] is p['legs'] is None


def test_research_does_not_create_replays_or_change_baseline(monkeypatch):
    from trading_desk import btc_engine,btc_lab
    paths=[STORE/'latest_run.json',STORE/'releases/ACTIVE.json',STORE/'runs'/RUN/'result.json',STORE/'runs'/RUN/'RESEARCH.xlsx',STORE/'releases/0.1/BTC_STRUCTURE_RELEASE_0.1.zip']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly replay forbidden'))
    monkeypatch.setattr(btc_engine,'create_replay',lambda *a,**k:pytest.fail('No strategy engine needed'))
    r=review();assert not r['month_rerun'] and not r['new_exit_rule_adopted'] and not r['release_modified']
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
    assert [c['trade_id'] for c in btc_lab.Lab().detail(RUN)['early_failure_review']['cases']]==[32,30]
    assert btc_lab.Lab().detail('20261109T122648Z-30-ab')['early_failure_review'] is None
