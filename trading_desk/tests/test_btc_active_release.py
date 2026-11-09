"""Owner-selected baseline cannot be displaced by a newer experimental run."""
import hashlib
import inspect
import json
from pathlib import Path
import sys
import threading
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk import btc_engine,btc_lab
from trading_desk.btc_data import STORE,read
from scripts.investigate_btc_release01_performance import investigate


def test_active_reference_is_separate_from_latest_experiment():
    lab=btc_lab.Lab();status=lab.status()
    assert status['default_run']=='20261109T041525Z-30-ab'
    assert status['active_release']['version']=='0.1'
    assert status['latest']['run_id']==status['current_study']['run_ids']['E2']
    assert status['orders_enabled'] is False
    assert lab.detail(status['default_run'])['performance_review']['baseline_net']==pytest.approx(3516.456280505433)


def test_new_desk_run_explicitly_selects_release_policy(monkeypatch,tmp_path):
    seen=[];done=threading.Event()
    def fake_run(*args,**kwargs):
        seen.append(kwargs);done.set()
        return dict(run_id='test',minute_count=0,last_observed=None)
    monkeypatch.setattr(btc_engine,'run',fake_run)
    lab=btc_lab.Lab(tmp_path);lab.start('backtest',30)
    assert done.wait(2)
    assert seen==[dict(research_policy='release_0_1')]


def test_default_policy_keeps_original_b1_and_experiment_is_explicit():
    assert inspect.signature(btc_engine.run).parameters['research_policy'].default=='release_0_1'
    import sqlite3
    db=sqlite3.connect(':memory:')
    release=btc_engine.create_replay(0,1,db,expanded_b=True,exit_version='failed_rebound')
    experiment=btc_engine.create_replay(0,1,db,expanded_b=True,exit_version='current')
    assert not release.b1_independent_hold and experiment.b1_independent_hold
    assert release.policy==experiment.policy and release.cfg.first_sale_fraction==experiment.cfg.first_sale_fraction==.25
    assert release.cfg.one_way_friction_bps==experiment.cfg.one_way_friction_bps==2
    db.close()


def test_diagnostics_do_not_change_frozen_artifacts_or_latest(monkeypatch):
    files=[STORE/'latest_run.json',STORE/'runs/20261109T041525Z-30-ab/result.json',STORE/'runs/20261109T041525Z-30-ab/RESEARCH.xlsx',STORE/'releases/0.1/BTC_STRUCTURE_RELEASE_0.1.zip']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Diagnostics must not replay a month'))
    r=investigate()
    assert r['baseline_net']==pytest.approx(3516.456280505433)
    assert r['losses_after_1r']==[3] and len(r['losses_below_1r'])==18
    q=r['failed_breakout_probe'];assert not q['adopted'] and q['delta']==pytest.approx(-325.52622414227807)
    assert len(q['changed'])==15 and q['improved']==9 and q['worsened']==6
    assert all(x['confirmed_at']==x['exit_time'] for x in q['changed'])
    assert next(x for x in q['changed'] if x['trade_id']==32)['net_change']==pytest.approx(521.3167157999875)
    assert next(x for x in q['changed'] if x['trade_id']==30)['net_change']==pytest.approx(-1500.5092251761596)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
