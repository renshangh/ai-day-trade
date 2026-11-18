"""Parent-only experimental execution: scope, causal prefix and consumed history."""
import copy
from pathlib import Path
import sqlite3
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.btc_parent_filter import blocks_parent,ParentFilteredBaselineReplay,ParentFilteredEarlyReplay
from trading_desk.btc_parent_hl import ContinuationBaselineReplay,ContinuationEarlyReplay
from scripts.retest_btc_parent_filter import make_engine
from scripts.audit_btc_c_blind_review import OUT,load_saved,case_key,locked


@pytest.fixture(scope='module')
def saved():
    if not (OUT/'ALL_FIXED_CLASSIFICATIONS.json').exists():pytest.skip('Requires authorized archived parent/trigger review')
    locked();study,models,rows=load_saved()
    return models['0.1'],rows,read(OUT/'ALL_FIXED_CLASSIFICATIONS.json')


def test_trigger_only_and_uncertain_parent_cases_are_retained(saved):
    r,_,reviews=saved
    find=lambda ident:reviews[case_key(next(p for p in r['trades'] if p['id']==ident))]
    trigger=find(89);unknown=find(13);clear=find(5)
    assert trigger['trigger_flag'] and not trigger['parent_flag'] and not blocks_parent(trigger)
    assert unknown['parent_flag'] and unknown['uncertainty'] and not blocks_parent(unknown)
    assert clear['parent_flag'] and not clear['uncertainty'] and blocks_parent(clear)


def test_stop_targets_and_exits_are_inherited_without_numeric_changes():
    for new,old in [(ParentFilteredBaselineReplay,ContinuationBaselineReplay),(ParentFilteredEarlyReplay,ContinuationEarlyReplay)]:
        for name in ('additional_exit_candidates','close_part','targets'):
            assert getattr(new,name) is getattr(old,name)


def test_real_first_rejection_has_no_fill_or_entry_history_reset_and_no_future_input(saved,monkeypatch):
    from trading_desk import btc_parent_filter
    r,rows,_=saved;target=next(p for p in r['trades'] if p['id']==5)
    boundary=ts(target['entry_time']);seen=[];original=btc_parent_filter.classify
    def inspect(case):
        assert all(b['t']<ts(case['entry_time']) for b in case['minutes'])
        seen.append(case['entry_time']);return original(case)
    monkeypatch.setattr(btc_parent_filter,'classify',inspect)
    connections=[];engines=[]
    try:
        for enabled in (False,True):
            db=sqlite3.connect(':memory:');connections.append(db)
            db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
            e=make_engine('0.1',ts(r['start']),ts(r['end']),db,enabled)
            before=None
            for b in rows:
                if b['t']>boundary:break
                if b['t']==boundary:before=e.entry_history_start
                e.minute(b)
            engines.append((e,before))
        control,_=engines[0];filtered,before=engines[1]
        # finish() removes this transient empty construction list. Compare the
        # still-running prefix with the saved, finished path equivalently.
        finished=lambda trades:[{k:v for k,v in p.items() if k!='pending_lows'} for p in trades]
        assert finished(control.trades)==r['trades'][:4] and finished(filtered.trades)==r['trades'][:4]
        assert control.position['entry_time']==target['entry_time'] and control.position['entry_rule']=='C'
        assert filtered.position is None and filtered.position_id==4
        assert filtered.entry_history_start==before
        assert target['continuation']['hl']['time'] in filtered.c_emitted
        signal=next(s for s in filtered.signals if s['time_utc']==target['entry_time'] and s['route']=='C')
        assert signal['qualified_candidate'] and signal['decision']=='parent_filter_rejected' and signal['trade_id'] is None
        assert signal['parent_filter']['prefix_last_minute']<target['entry_time']
        assert target['entry_time'] in seen
    finally:
        for db in connections:db.close()
