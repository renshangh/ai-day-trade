"""Fixed 38 original entries: immutable rules/data and winning-trade controls."""
import hashlib
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.audit_btc_release01_early_failure_all import review,RUN
from trading_desk.btc_data import STORE,read,ts


@pytest.fixture(scope='module')
def reviewed():return review()


def test_all_original_entries_and_original_source_match_frozen_release(reviewed):
    original=read(STORE/'releases/0.1/results/result.json')
    assert len(reviewed['rows'])==38
    assert [r['trade_id'] for r in reviewed['rows']]==list(range(1,39))
    assert reviewed['source_minute_sha256']==original['source_minute_sha256']
    previous=read(STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json')
    assert reviewed['definitions']==previous['definitions']
    for x,p in zip(reviewed['rows'],original['trades']):
        assert (x['entry_time'],x['entry'],x['initial_stop'])==(p['entry_time'],p['entry'],p['initial_stop'])
        assert x['baseline_legs']==p['legs'] and x['baseline_net']==p['net']


def test_only_three_losses_change_and_all_profitable_trades_are_retained(reviewed):
    a,b=(reviewed['summary'][key] for key in ('E1','E2'))
    assert a['improved_trade_ids']==[11,12,32] and a['triggered']==3
    assert b['improved_trade_ids']==[12,32] and b['triggered']==2
    assert a['fixed_entry_net']==pytest.approx(4159.666612705426)
    assert b['fixed_entry_net']==pytest.approx(4195.148015005418)
    assert a['net_change']==pytest.approx(643.2103321999926)
    assert b['net_change']==pytest.approx(678.6917344999849)
    for q in (a,b):
        assert q['valued']==38 and q['wins']==q['losses']==19
        assert q['hurt_original_winner_ids']==q['winners_turned_loss']==q['worsened_trade_ids']==[]
    winners=[x for x in reviewed['rows'] if x['baseline_winner']]
    assert len(winners)==19
    assert all(not p['triggered'] and p['net']==x['baseline_net'] for x in winners for p in x['alternatives'].values())


def test_each_original_leg_and_alternative_costs_reconcile(reviewed):
    for x in reviewed['rows']:
        for p in x['alternatives'].values():
            assert sum(l['fraction'] for l in p['legs'])==pytest.approx(1)
            assert sum(l['net'] for l in p['legs'])==pytest.approx(p['net'])
            for l in p['legs']:
                assert l['net']==pytest.approx(l['fraction']*((l['price']-x['entry'])-(l['price']+x['entry'])*.0002))
            if p['triggered']:
                assert p['signal']['confirmed_at']==p['exit_time']
                assert ts(p['exit_time'])<ts(x['baseline_exit'])
                earlier=[l for l in x['baseline_legs'] if ts(l['time_utc'])<ts(p['exit_time'])]
                assert p['legs'][:-1]==earlier
            else:assert p['legs']==x['baseline_legs']


def test_previous_two_case_controls_remain_identical(reviewed):
    previous=read(STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json')
    for c in previous['cases']:
        x=next(x for x in reviewed['rows'] if x['trade_id']==c['trade_id'])
        for old_key,key in [('A','E1'),('B','E2')]:
            old=c['alternatives'][old_key];new=x['alternatives'][key]
            assert old['triggered']==new['triggered'] and old['net']==new['net']
            if old['triggered']:
                assert old['exit_price']==new['exit_price'] and old['exit_time']==new['exit_time']


def test_gap_comparison_flag_is_preserved_not_optimized_away(reviewed):
    x=next(x for x in reviewed['rows'] if x['trade_id']==12)
    assert x['gap_exposed'] and len(x['baseline_missing_held_minutes'])==7
    assert x['baseline_missing_held_minutes'][0]=='2026-10-24T06:42:00Z'
    for q in x['alternatives'].values():
        assert q['exit_precedes_original_gap'] and q['missing_held_minutes_before_exit']==0
    assert reviewed['summary']['E1']['no_original_holding_gap_count']==36
    assert reviewed['summary']['E1']['no_original_holding_gap_delta']==pytest.approx(585.9037957999933)
    assert reviewed['summary']['E2']['no_original_holding_gap_delta']==pytest.approx(402.42199949998775)


def test_no_strategy_or_monthly_run_or_release_mutation(monkeypatch):
    from trading_desk import btc_engine,btc_lab
    paths=[STORE/'latest_run.json',STORE/'releases/ACTIVE.json',STORE/'runs'/RUN/'result.json',STORE/'runs'/RUN/'RESEARCH.xlsx',STORE/'releases/0.1/BTC_STRUCTURE_RELEASE_0.1.zip',STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('No monthly replay authorized'))
    monkeypatch.setattr(btc_engine,'create_replay',lambda *a,**k:pytest.fail('No strategy engine needed'))
    r=review();assert not any(r[k] for k in ('month_rerun','strategy_engine_created','release_modified','rules_modified','orders_enabled'))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
    lab=btc_lab.Lab();assert len(lab.detail(RUN)['early_failure_fixed38']['rows'])==38
    assert lab.detail('20261109T122648Z-30-ab')['early_failure_fixed38'] is None
    if (STORE/'investigations/E1_E2_FIXED38.xlsx').exists():
        assert lab.export(RUN,'E1_E2_FIXED38.xlsx')==STORE/'investigations/E1_E2_FIXED38.xlsx'
    with pytest.raises(ValueError):lab.export('20261109T122648Z-30-ab','E1_E2_FIXED38.xlsx')
    with pytest.raises(ValueError):lab.export(RUN,'../investigations/E1_E2_FIXED38.xlsx')
