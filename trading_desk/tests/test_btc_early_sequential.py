"""Full sequence and actual-minute controls for opt-in E1/E2 execution."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,ts
from trading_desk.btc_early_sequential import EarlySequentialReplay
from scripts.audit_btc_release01_early_failure_all import load_frozen_source
from scripts.btc_structure_retest import Config


@pytest.fixture(scope='module')
def source():return load_frozen_source()


def frozen_case(source,ident,policy,*,omit=None):
    original,minutes,_=source;p=next(p for p in original['trades'] if p['id']==ident)
    signal=copy.deepcopy(next(s for s in original['signals'] if s['id']==p['signal_id']))
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=EarlySequentialReplay(ts(original['start']),ts(p['exit_time'])+60,db,
        Config(first_sale_fraction=.25,resistance_mode='major1h'),early_policy=policy,
        expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
    attempted=[]
    def entry(b):
        attempted.append(b['t'])
        if b['t']==ts(p['entry_time']):
            e.position_id=ident-1;e.open_signal(b,signal)
    e.entry=entry
    for b in minutes.values():
        if b['t']>ts(p['exit_time']):break
        if b['t']==omit:continue
        e.minute(b)
    result=e.finish()
    rows=[json.loads(row[0]) for row in db.execute('SELECT body FROM ledger')];db.close()
    return result['trades'][0],rows,attempted


@pytest.mark.parametrize('policy,time,price,net',[('E1','2026-11-05T17:15:00Z',76079.9285,-211.34964770000315),('E2','2026-11-05T20:15:00Z',75961.01,-330.2443640000029)])
def test_streaming_single_case_matches_prior_fixed_entry_study(source,policy,time,price,net):
    p,rows,attempts=frozen_case(source,32,policy)
    assert p['exit_time']==time and p['legs'][-1]['price']==price
    assert p['net']==pytest.approx(net)
    assert p['legs'][-1]['reason']==policy.lower()+'_exit_remaining'
    assert ts(time) not in attempts # No re-entry in the observed exit minute.
    proof=p['case_exit_evidence'][-1]
    assert proof['confirmed_at']==time and proof['phase']==0 and proof['priority']==25


@pytest.mark.parametrize('policy',['E1','E2'])
def test_profitable_trade30_preserves_original_staged_exits(source,policy):
    p,_,_=frozen_case(source,30,policy)
    original=next(p for p in source[0]['trades'] if p['id']==30)
    assert p['legs']==original['legs'] and p['net']==original['net']


def test_missing_exact_opening_expires_signal_without_fabricated_fill(source):
    p,rows,_=frozen_case(source,32,'E1',omit=ts('2026-11-05T17:15:00Z'))
    assert not any(l['reason']=='e1_exit_remaining' for l in p['legs'])
    assert p['gap_exposed']
    events=[e for row in rows for e in row['events'] if e['type']=='early_exit_observation_missing']
    assert len(events)==1 and events[0]['missed_at']=='2026-11-05T17:15:00Z'


def test_completed_study_full_sequence_and_gap_partition():
    active=read(STORE/'studies/ACTIVE.json');study=read(STORE/'studies'/active['study_id']/'STUDY.json')
    assert study['baseline_reproduced'] and study['source_minute_sha256']=='6676741b2e47d6fd45e5bde450f8e308eb4546df830a54e281412a1e1fdfc05b'
    original=read(STORE/'runs'/study['baseline_run']/'result.json')
    for policy,net in [('E1',4159.666612705426),('E2',4195.148015005418)]:
        r=read(STORE/'runs'/study['run_ids'][policy]/'result.json')
        assert not r['b1_independent_hold'] and r['consume_entry_history']
        assert [(p['entry_time'],p['entry'],p['initial_stop'],p['t1']) for p in r['trades']]==[(p['entry_time'],p['entry'],p['initial_stop'],p['t1']) for p in original['trades']]
        assert sum(p['net'] for p in r['trades'])==pytest.approx(net)
        assert not study['changes'][policy]['added'] and not study['changes'][policy]['baseline_entries_not_taken']
        assert all(w['crossed_signal_count']==w['qualified_signal_count']==0 for w in study['changes'][policy]['freed_windows'])
        a=study['summaries'][policy]
        assert a['all']['entries']==38 and a['no_flagged_gap']['entries']==37 and a['gap_or_partial_context']['entries']==1
        assert a['all']['net']==pytest.approx(a['no_flagged_gap']['net']+a['gap_or_partial_context']['net'])
        for p in r['trades']:
            assert sum(l['fraction'] for l in p['legs'])==pytest.approx(1)
            assert sum(l['net'] for l in p['legs'])==pytest.approx(p['net'])
            for l in p['legs']:assert l['cost']==pytest.approx(l['fraction']*(l['price']+p['entry'])*.0002)
    preserved=read(STORE/'studies'/study['study_id']/'PRESERVED_FILES_SHA256.json')
    assert all(hashlib.sha256((STORE/p).read_bytes()).hexdigest()==h for p,h in preserved.items())


def test_current_ui_hides_old_research_without_deleting_archive():
    from trading_desk.btc_lab import Lab
    lab=Lab();s=lab.status();study=s['current_study']
    assert {r['run_id'] for r in s['runs']}==set(study['run_ids'].values())
    assert len(s['runs'])==3 and s['active_release']['version']=='0.1'
    assert lab.result('20261109T122648Z-30-ab')['status']=='complete' # Archived, still intact.
    for run in study['run_ids'].values():
        d=lab.detail(run)
        assert d['current_study']['study_id']==study['study_id'] and d['comparison'] is None
        assert 'E1_E2_FIXED38.xlsx' not in d['exports'] and 'RESEARCH.xlsx' not in d['exports']
    html=(ROOT/'trading_desk/btc_lab.html').read_text()
    for legacy in ('HISTORICAL V5','HISTORICAL V3','APPROVED EXITS / TWO CASES','id="early-failure-fixed38"','id="profit-guard"'):
        assert legacy not in html
