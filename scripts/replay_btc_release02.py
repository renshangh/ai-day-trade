"""Verify and reproduce the frozen 0.2 comparison without API access or orders."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import zipfile


def checked_copy(src,dest):
    if dest.exists():
        if src.read_bytes()!=dest.read_bytes():raise ValueError('Existing artifact differs: '+str(dest))
        return
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dest)


def install(folder,store,manifest,minutes):
    """Install only verified research artifacts; existing differing files fail."""
    store=store.resolve();store.mkdir(parents=True,exist_ok=True)
    for src in sorted((folder/'results').rglob('*')):
        if src.is_file():checked_copy(src,store/'runs'/src.relative_to(folder/'results'))
    target=store/'releases/0.1';baseline=folder/'baseline_release/BTC_STRUCTURE_RELEASE_0.1.zip'
    with zipfile.ZipFile(baseline) as z:
        for name in z.namelist():
            dest=target/name
            if not dest.resolve().is_relative_to(target.resolve()):raise ValueError('Unsafe baseline path')
            if name.endswith('/'):continue
            data=z.read(name)
            if dest.exists() and dest.read_bytes()!=data:raise ValueError('Existing 0.1 differs: '+name)
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    checked_copy(baseline,target/baseline.name)
    target=store/'studies'/manifest['study_id']
    for src in (folder/'study').iterdir():
        if src.is_file():checked_copy(src,target/src.name)
    target=store/'releases/0.2'
    if folder!=target:
        for src in folder.rglob('*'):
            if src.is_file() and '__pycache__' not in src.parts:checked_copy(src,target/src.relative_to(folder))
    dbpath=store/'minutes.sqlite'
    if not dbpath.exists():
        with sqlite3.connect(dbpath) as db:
            db.execute('CREATE TABLE minutes(t INTEGER PRIMARY KEY,o REAL,h REAL,l REAL,c REAL,v REAL,n INTEGER,vw REAL)')
            db.executemany('INSERT INTO minutes VALUES(?,?,?,?,?,?,?,?)',minutes)
    registry=store/'releases/INDEX.json'
    entries=json.loads(registry.read_text()) if registry.exists() else {}
    entries.update(json.loads((folder/'REGISTRY.json').read_text()))
    registry.write_text(json.dumps(entries,ensure_ascii=False)+'\n')
    for relative,value in {
        'releases/ACTIVE.json':dict(version='0.1',reason='0.2 comparison keeps 0.1 as execution baseline'),
        'releases/CURRENT_REVIEW.json':dict(version='0.2',study_id=manifest['study_id']),
        'studies/ACTIVE.json':dict(study_id=manifest['study_id']),
        'latest_run.json':dict(run_id=manifest['run_ids']['E2']),
    }.items():
        dest=store/relative
        if dest.exists() and relative=='releases/ACTIVE.json':continue
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(value)+'\n')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--install-store',type=Path)
    args=parser.parse_args();folder=args.release_dir.resolve()
    manifest=json.loads((folder/'MANIFEST.json').read_text())
    for name,digest in manifest['files_sha256'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Release integrity check failed: '+name)
    sys.path.insert(0,str(folder/'source'))
    from trading_desk.btc_engine import create_replay
    from trading_desk.btc_early_sequential import EarlySequentialReplay
    from trading_desk.btc_data import ts
    from scripts.btc_structure_retest import Config
    minutes=[];digest=hashlib.sha256()
    with gzip.open(folder/'data/MINUTES.jsonl.gz','rt') as f:
        for line in f:
            row=json.loads(line);minutes.append(row)
            digest.update((json.dumps(row,separators=(',',':'))+'\n').encode())
    if digest.hexdigest()!=manifest['source_minute_sha256']:raise ValueError('Source stream differs')
    outcomes={}
    for model,run_id in manifest['run_ids'].items():
        expected=json.loads((folder/'results'/run_id/'result.json').read_text())
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        if model=='0.1':
            engine=create_replay(ts(expected['start']),ts(expected['end']),db,expanded_b=True,exit_version='failed_rebound')
        else:
            engine=EarlySequentialReplay(ts(expected['start']),ts(expected['end']),db,
                Config(first_sale_fraction=.25,resistance_mode='major1h'),early_policy=model,
                expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
        for t,o,h,l,c,v,n,vw in minutes:engine.minute(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
        actual=engine.finish();db.close()
        if len(actual['trades'])!=len(expected['trades']):raise ValueError('Trade count differs: '+model)
        for a,b in zip(actual['trades'],expected['trades'],strict=True):
            for key in ('entry_time','entry','initial_stop','references','t1','t2','legs','status','remaining','net','net_r','gap_exposed','context_partial'):
                if a[key]!=b[key]:raise ValueError(model+' #'+str(b['id'])+' differs: '+key)
        if actual['metrics']!=expected['metrics']:raise ValueError('Metrics differ: '+model)
        # The later serializer adds a null optional B1-confirmation field to
        # the same aggressive-B1 signals. Only that absent/null equivalence
        # is permitted; every substantive signal field must still match.
        def signal_record(s):
            return {k:v for k,v in s.items() if not(k=='b1_confirmation' and v is None)}
        if list(map(signal_record,actual['signals']))!=list(map(signal_record,expected['signals'])):
            raise ValueError('Signal sequence differs: '+model)
        outcomes[model]=dict(trades=len(actual['trades']),net=sum(p['net'] for p in actual['trades']),reproduced=True)
    if args.install_store:install(folder,args.install_store,manifest,minutes)
    print(json.dumps(dict(version='0.2',source_minutes=len(minutes),source_sha256=digest.hexdigest(),
        sequences=outcomes,reproduced=True,installed=bool(args.install_store),orders_enabled=False)))


if __name__=='__main__':main()
