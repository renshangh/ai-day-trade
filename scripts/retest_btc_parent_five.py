"""Bounce first, then fixed-source PH5 comparison. No live writes or fetching."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trading_desk.btc_data import STORE, read, save, ts, iso
from trading_desk.btc_live import LIVE, CONTROLLER, verify_rules
from trading_desk.btc_engine import create_replay, export_csv
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_parent_five import PH5_RULE, ParentFiveBaseline, ParentFiveEarly
from scripts.btc_structure_retest import Config
from scripts.retest_btc_e1_e2_sequential import summarize, sequence_changes

BASE = STORE/'parent_five_studies'
MODELS = ('0.1', 'E1', 'E2')
CASE_START = ts('2026-11-14T18:00:00-05:00')
CASE_END = ts('2026-11-15T05:16:00-05:00')


def engine(model, start, end, db, mode):
    if mode == 'control':
        if model == '0.1':
            return create_replay(start, end, db, expanded_b=True, exit_version='failed_rebound')
        cls = EarlySequentialReplay
    else:
        cls = ParentFiveBaseline if model == '0.1' else ParentFiveEarly
    kw = dict(expanded_b=True, consume_entry_history=True, b1_independent_hold=False)
    if model != '0.1':
        kw['early_policy'] = model
    if mode != 'control':
        kw['ph5_mode'] = mode
    return cls(start, end, db, Config(first_sale_fraction=.25, resistance_mode='major1h'), **kw)


def database(path=':memory:'):
    db = sqlite3.connect(path)
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    return db


def preservation():
    paths = [ROOT/p for p in verify_rules()]
    paths += [ROOT/'trading_desk/btc_live.py', ROOT/'scripts/run_btc_live.py',
        LIVE/'CONTROL.json', LIVE/'SESSION.json',
        Path.home()/'Library/LaunchAgents/com.renshangh.btc-live-comparison.plist']
    paths += [p for p in (STORE/'releases/0.2').rglob('*') if p.is_file()]
    paths += [STORE/p for p in ('p1_studies/ACTIVE.json', 'parent_hl_studies/ACTIVE.json',
        'parent_filter_studies/ACTIVE.json', 'studies/ACTIVE.json', 'latest_run.json', 'releases/ACTIVE.json')]
    paths += list((ROOT/'trading_desk').glob('btc_p1*'))
    status = CONTROLLER.status()
    return dict(files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()},
        worker=dict(pid=status['pid']), session=status['session']['id'])


def verify_preserved(p):
    for name, digest in p['files'].items():
        assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == digest, name
    now = CONTROLLER.status()
    assert now['session']['id'] == p['session']
    assert now['pid'] == p['worker']['pid'], 'Original worker changed; report rather than restart'
    verify_rules()
    return dict(files=len(p['files']), pid=now['pid'], session=now['session']['id'],
                health=now.get('status'), unchanged=True)


def case_first(folder):
    session = read(LIVE/'SESSION.json')
    source = LIVE/'sessions'/session['id']/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro', uri=True) as db:
        records = db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t', (CASE_END,)).fetchall()
    minutes = [json.loads(body) for body,_ in records]
    receipt = {b['t']: r for b,(_,r) in zip(minutes, records)}
    result = dict(start=iso(CASE_START), cutoff=iso(CASE_END), source_session=session['id'],
        source_sha256=hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest(),
        note='Historical completed-minute references, not live fills. No finish() at cutoff. Case is outside frozen month.',
        models={})
    for model in MODELS:
        db = database()
        e = engine(model, session['start'], CASE_END, db, 'combined')
        e.ph5_active_from = CASE_START
        e.ph5_trace_enabled = True
        for b in minutes:
            e.minute(b)
        trades = copy.deepcopy(e.trades+([e.position] if e.position else []))
        selected = [p for p in trades if ts(p['entry_time']) >= CASE_START]
        for p in selected:
            p['entry_received_at'] = iso(receipt[ts(p['entry_time'])])
            for leg in p['legs']:
                leg['received_at'] = iso(receipt[ts(leg['time_utc'])])
            if p['status'] == 'open':
                p['net'] = None
                p['mark_reference'] = minutes[-1]['close']
                p['mark_time'] = iso(minutes[-1]['t'])
                p['marked_net'] = sum(x['net'] for x in p['legs'])+p['remaining']*(
                    (minutes[-1]['close']-p['entry'])-(minutes[-1]['close']+p['entry'])*.0002)
        signals = [copy.deepcopy(s) for s in e.signals if ts(s['time_utc']) >= CASE_START]
        for s in signals:
            s['received_at'] = iso(receipt[ts(s['time_utc'])])
        ledger = [json.loads(body) for body, in db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t', (CASE_START,))]
        result['models'][model] = dict(trades=selected, signals=signals, bars=ledger, trace=e.ph5_trace,
            ph5_entries=sum(p['entry_rule']=='PH5' for p in selected),
            note='Original A/B run from original session start; PH5 entries activated only at 18:00 EST for the nominated case. Earlier PH5 crossings are consumed without trades; no flat-at-bottom assumption.')
        print(json.dumps(dict(stage='bounce', model=model, PH5_entries=result['models'][model]['ph5_entries'])),flush=True)
        db.close()
    save(folder/'CASE.json', result)
    return result


def execute(model, mode, original, rows, folder):
    folder.mkdir(parents=True, exist_ok=False)
    db = database(folder/'ledger.sqlite')
    e = engine(model, ts(original['start']), ts(original['end']), db, mode)
    try:
        for i,b in enumerate(rows, 1):
            e.minute(b)
            if i%15000 == 0:
                db.commit()
                print(json.dumps(dict(stage='month', model=model, mode=mode, processed=i)),flush=True)
        r = e.finish()
        db.commit()
        if mode == 'control':
            assert len(r['trades']) == len(original['trades']), model
            for actual,expected in zip(r['trades'], original['trades'], strict=True):
                for k in ('entry_time','entry','entry_rule','initial_stop','t1','t2','legs','status','remaining'):
                    assert actual[k] == expected[k], (model,expected['id'],k)
            assert r['metrics'] == original['metrics']
        for k in ('start','end','warmup_start','days','source','source_minute_sha256','minute_count',
                  'test_data_quality','cost_model','draft_parameters','entry_mode','expanded_b'):
            r[k] = copy.deepcopy(original[k])
        r.update(status='complete', control_model=model, sequence=mode, orders_enabled=False,
                 live_promoted=False, source_frozen_release='0.2')
        export_csv(folder, r, db)
        save(folder/'result.json', r)
        return r
    finally:
        db.close()


def run(case_only=False):
    # Repository's machine-specific safe-timeout executable is absent here.
    # Bound the entire local replay equivalently; no background worker launched.
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('20 minute research limit')))
    signal.alarm(1200)
    before = preservation()
    ident = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-PH5'
    folder = BASE/ident
    folder.mkdir(parents=True, exist_ok=False)
    save(folder/'PRESERVED.json', before)
    save(folder/'LOCKED_RULE.json', PH5_RULE)
    case = case_first(folder)
    if case_only:
        save(folder/'PRESERVATION_CHECK.json', verify_preserved(before))
        print(json.dumps(dict(case_folder=str(folder))))
        return
    release = STORE/'releases/0.2'
    registry = read(release/'REGISTRY.json')['0.2']
    rows=[]
    digest=hashlib.sha256()
    with gzip.open(release/'data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            digest.update(line)
            t,o,h,l,c,v,n,_ = json.loads(line)
            rows.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    originals={m:read(release/'results'/registry['run_ids'][m]/'result.json') for m in MODELS}
    base=originals['0.1']
    assert digest.hexdigest()==base['source_minute_sha256']
    study=dict(study_id=ident,status='running',start=base['start'],end=base['end'],
        warmup_start=base['warmup_start'],source_minute_sha256=digest.hexdigest(),
        source_quality=base['test_data_quality'],rule=PH5_RULE,controls_reproduced={},summaries={},changes={},
        orders_enabled=False,live_promoted=False,case_outside_month=True,
        measure='Per-entry initial 1 BTC, original 2bps/side cost proxy, no compounding. Closed-trade drawdown, not account MTM drawdown.')
    save(folder/'STUDY.json',study)
    for model in MODELS:
        original=originals[model]
        execute(model,'control',original,rows,folder/model/'control')
        study['controls_reproduced'][model]=True
        study['summaries'][model]={'control':summarize(original)}
        study['changes'][model]={}
        for mode in ('standalone','combined'):
            r=execute(model,mode,original,rows,folder/model/mode)
            study['summaries'][model][mode]=summarize(r)
            study['summaries'][model][mode]['ph5_only']=summarize(dict(trades=[p for p in r['trades'] if p['entry_rule']=='PH5']))
            study['changes'][model][mode]=sequence_changes(original,r)
            save(folder/'STUDY.json',study)
    study.update(status='complete',preservation=verify_preserved(before),
        case_entries={m:case['models'][m]['ph5_entries'] for m in MODELS},
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__),ROOT/'trading_desk/btc_parent_five.py')})
    save(folder/'STUDY.json',study)
    save(BASE/'ACTIVE.json',dict(study_id=ident))
    print(json.dumps(dict(study_id=ident,summaries=study['summaries'],preservation=study['preservation']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case-only',action='store_true')
    run(parser.parse_args().case_only)
