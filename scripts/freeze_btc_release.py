"""Build an immutable local strategy release, separate from LumiBot's version."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts

VERSION='0.1'
RUN='20261109T041525Z-30-ab'
ARCHIVE='BTC_STRUCTURE_RELEASE_0.1.zip'


def freeze():
    folder=STORE/'releases'/VERSION
    registry=STORE/'releases/INDEX.json'
    if folder.exists():
        manifest=read(folder/'MANIFEST.json')
        assert manifest['source_run']==RUN and manifest['version']==VERSION
        for name,digest in manifest['files_sha256'].items():
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
        registered=read(registry,{})[VERSION]
        digest=hashlib.sha256((folder/ARCHIVE).read_bytes()).hexdigest()
        assert digest==registered['archive_sha256']
        assert hashlib.sha256((STORE/'runs'/RUN/ARCHIVE).read_bytes()).hexdigest()==digest
        assert hashlib.sha256((folder/'MANIFEST.json').read_bytes()).hexdigest()==registered['manifest_sha256']
        return folder,manifest
    baseline=STORE/'runs'/RUN;result=read(baseline/'result.json')
    assert len(result['trades'])==38 and result['metrics']['closed']==38
    net=sum(p['net'] for p in result['trades'])
    assert abs(net-3516.456280505433)<1e-8
    stage=folder.with_name(VERSION+'.building');stage.mkdir(parents=True,exist_ok=False)
    (stage/'source/trading_desk').mkdir(parents=True);(stage/'source/scripts').mkdir()
    for path in sorted((ROOT/'trading_desk').glob('btc_*.py')):
        shutil.copy2(path,stage/'source/trading_desk'/path.name)
    for name in ('btc_lab.html','btc_lab.js','btc_lab.css'):
        shutil.copy2(ROOT/'trading_desk'/name,stage/'source/trading_desk'/name)
    shutil.copy2(ROOT/'scripts/btc_structure_retest.py',stage/'source/scripts/btc_structure_retest.py')
    shutil.copy2(ROOT/'scripts/replay_btc_release.py',stage/'REPRODUCE.py')
    (stage/'results').mkdir();(stage/'data').mkdir()
    for name in ('result.json','RESEARCH.xlsx','TRADES.csv','EXITS.csv','SIGNALS.csv','PROTECTION.csv',
            'LEDGER.csv','COMPARISON.json','LARGE_LOSS_REVIEW.json','LARGE_LOSS_REVIEW.csv'):
        shutil.copy2(baseline/name,stage/'results'/name)
    stream_digest=hashlib.sha256();count=0
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        with (stage/'data/MINUTES.jsonl.gz').open('wb') as raw:
            with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as out:
                for row in db.execute('SELECT * FROM minutes WHERE t>=? AND t<? ORDER BY t',
                        (ts(result['warmup_start']),ts(result['end']))):
                    data=(json.dumps(list(row),separators=(',',':'))+'\n').encode()
                    stream_digest.update(data);out.write(data);count+=1
    assert stream_digest.hexdigest()==result['source_minute_sha256']
    notes='''# BTC Structure Research Release 0.1

Frozen on November 9, 2026. This version belongs to the BTC research desk;
it does not change the parent LumiBot package version.

Reference run: 20261109T041525Z-30-ab. Window: October 9 20:00 EDT to
November 8 19:00 EST, 2026, exclusive end, with seven days of actual warmup.
38 closed trades, 19 wins/19 losses, model net +$3,516.46 per initial 1 BTC.
Zero commission plus 2bps each way; no actual ETF fills or orders.

Rules: A/B1/B2 entries, consumed setup history after entry, original D/ATR
hard stops, first target 25%, no fixed T2, original active protection plus
independent confirmed 15m H-L-LH failure exit. B1 in this frozen release
allows the D candle itself as stabilization. The later independent post-D
confirmation rule is intentionally excluded from the frozen execution path.

Unzip, then run Python 3.10+:

    python3 REPRODUCE.py

No broker credentials, downloads, account changes or live orders are needed.
The replay verifies every bundled file, source hash, entry, initial stop,
target and exit leg against the original result. Missing source minutes
remain absent. Results/RESEARCH.xlsx is the preserved review workbook.
The source stream has 558 missing test minutes; performance is conditional
observed-path, in-sample research, not independently validated profitability.
'''
    (stage/'README.md').write_text(notes)
    files={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(stage.rglob('*')) if p.is_file()}
    manifest=dict(version=VERSION,release_date='2026-11-09',kind='frozen_btc_research_release',
        source_run=RUN,strategy_version=result['strategy_version'],start=result['start'],end=result['end'],
        warmup_start=result['warmup_start'],source_minute_sha256=stream_digest.hexdigest(),
        source_minutes=count,source_missing_test_minutes=result['test_data_quality']['missing_minutes'],
        metrics=result['metrics'],closed_net=net,b1_independent_post_d_hold=False,
        orders_enabled=False,files_sha256=files)
    save(stage/'MANIFEST.json',manifest)
    # Validate the exact shipped sources/data before making the release visible.
    completed=subprocess.run([sys.executable,str(stage/'REPRODUCE.py'),'--release-dir',str(stage)],
        capture_output=True,text=True,check=True)
    verification=json.loads(completed.stdout.strip().splitlines()[-1])
    assert verification['reproduced'] is True
    with zipfile.ZipFile(stage/ARCHIVE,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file() and path.name!=ARCHIVE and '__pycache__' not in path.parts:
                z.write(path,str(path.relative_to(stage)))
    stage.rename(folder)
    archive_hash=hashlib.sha256((folder/ARCHIVE).read_bytes()).hexdigest()
    target=baseline/ARCHIVE
    if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==archive_hash
    else:shutil.copy2(folder/ARCHIVE,target)
    entries=read(registry,{})
    if VERSION in entries:raise ValueError('Release version already registered')
    entries[VERSION]=dict(version=VERSION,run_id=RUN,release_date='2026-11-09',
        archive=ARCHIVE,archive_sha256=archive_hash,manifest_sha256=hashlib.sha256((folder/'MANIFEST.json').read_bytes()).hexdigest(),
        closed_net=net,metrics=result['metrics'],status='frozen',reproduced=True)
    save(registry,entries)
    return folder,manifest


if __name__=='__main__':
    folder,manifest=freeze()
    print(json.dumps(dict(version=manifest['version'],run_id=manifest['source_run'],
        net=manifest['closed_net'],bundle=str(folder/ARCHIVE),frozen=True)))
