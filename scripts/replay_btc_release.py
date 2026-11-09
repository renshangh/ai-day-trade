"""Replay an extracted frozen BTC research release using its actual minutes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release-dir',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args();folder=args.release_dir.resolve()
    manifest=json.loads((folder/'MANIFEST.json').read_text())
    for name,digest in manifest['files_sha256'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Release integrity check failed: '+name)
    sys.path.insert(0,str(folder/'source'))
    from trading_desk.btc_engine import create_replay
    from trading_desk.btc_data import ts
    reference=json.loads((folder/'results/result.json').read_text())
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=create_replay(ts(reference['start']),ts(reference['end']),db,
        expanded_b=True,exit_version='failed_rebound',consume_entry_history=True)
    digest=hashlib.sha256();count=0
    with gzip.open(folder/'data/MINUTES.jsonl.gz','rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);t,o,h,l,c,v,n,vw=row
            digest.update((json.dumps(row,separators=(',',':'))+'\n').encode())
            engine.minute(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n));count+=1
    result=engine.finish();db.close()
    if digest.hexdigest()!=reference['source_minute_sha256']:raise ValueError('Source stream hash mismatch')
    if len(result['trades'])!=len(reference['trades']):raise ValueError('Trade count mismatch')
    for actual,expected in zip(result['trades'],reference['trades'],strict=True):
        for key in ('entry_time','entry','initial_stop','t1','t2','status','remaining','legs'):
            if actual[key]!=expected[key]:raise ValueError(f"Trade {expected['id']} {key} mismatch")
    if result['metrics']!=reference['metrics']:raise ValueError('Metric mismatch')
    print(json.dumps(dict(release=manifest['version'],source_minutes=count,
        trades=len(result['trades']),net=sum(p['net'] for p in result['trades'] if p['status']=='closed'),
        source_sha256=digest.hexdigest(),reproduced=True)))


if __name__=='__main__':main()
