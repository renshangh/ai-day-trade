"""Freeze the approved E1/E2 comparison as research release 0.2."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save

VERSION='0.2'
ARCHIVE='BTC_STRUCTURE_RELEASE_0.2.zip'
TAG='btc-research-v0.2'


def freeze():
    folder=STORE/'releases'/VERSION
    if folder.exists():
        manifest=read(folder/'MANIFEST.json')
        for name,digest in manifest['files_sha256'].items():
            assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==digest,name
        return folder,manifest
    study=read(STORE/'studies'/read(STORE/'studies/ACTIVE.json')['study_id']/'STUDY.json')
    original=STORE/'releases/0.1'
    prior=read(original/'MANIFEST.json')
    for name,digest in prior['files_sha256'].items():
        assert hashlib.sha256((original/name).read_bytes()).hexdigest()==digest,name
    stage=folder.with_name('0.2.building');stage.mkdir(exist_ok=True)
    for path in sorted((ROOT/'trading_desk').glob('btc_*')):
        if path.suffix in ('.py','.js','.html','.css'):
            dest=stage/'source/trading_desk'/path.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    sources=set((ROOT/'scripts').glob('*btc*.py'))
    for path in sorted(sources):
        dest=stage/'source/scripts'/path.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    shutil.copy2(ROOT/'scripts/replay_btc_release02.py',stage/'REPRODUCE.py')
    (stage/'data').mkdir(exist_ok=True);shutil.copy2(original/'data/MINUTES.jsonl.gz',stage/'data/MINUTES.jsonl.gz')
    (stage/'baseline_release').mkdir(exist_ok=True);shutil.copy2(original/'BTC_STRUCTURE_RELEASE_0.1.zip',stage/'baseline_release/BTC_STRUCTURE_RELEASE_0.1.zip')
    for run in study['run_ids'].values():
        dest=stage/'results'/run;dest.mkdir(parents=True,exist_ok=True)
        for name in ('result.json','ledger.sqlite','WORKBOOK_DATA.json','SIGNALS.csv','TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv'):
            shutil.copy2(STORE/'runs'/run/name,dest/name)
    (stage/'study').mkdir(exist_ok=True)
    current=STORE/'studies'/study['study_id']
    for name in ('STUDY.json','ARCHIVED_RESEARCH_INDEX.json','DELIVERY_VERIFICATION.json','E1_E2_SEQUENTIAL_30D.xlsx'):
        shutil.copy2(current/name,stage/'study'/name)
    registry=read(STORE/'releases/INDEX.json')
    registry['0.2']=dict(version='0.2',kind='frozen_sequential_comparison',run_id=None,
        run_ids=study['run_ids'],study_id=study['study_id'],release_date='2026-11-09',
        archive=ARCHIVE,tag=TAG,status='frozen',baseline_version='0.1',reproduced=True)
    save(stage/'REGISTRY.json',registry)
    notes="""# BTC Structure Research Release 0.2

Frozen November 9, 2026. This is the 0.1/E1/E2 comparison release,
independent of the parent LumiBot package version. The baseline execution
policy stays 0.1; E1 and E2 remain separately selectable alternatives.

Same 30-day source: October 10 to November 9 UTC, exclusive end, with
seven actual warmup days. Each model has 38 closed trades, 19 wins/19 losses.
Per initial 1 BTC, ETF zero commission plus 2bps per side:
0.1 +$3,516.46; E1 +$4,159.67; E2 +$4,195.15.
No new buys appear after earlier exits. Original winners are unchanged.
558 missing source minutes remain absent; gap groups are separate and
membership changes when #12 exits before a later gap. In-sample model
estimates are not actual ETF fills or validated future profitability.

Unzip and verify/reproduce all three full sequences offline:

    python3 REPRODUCE.py

Python 3.10+ and standard library only. No credentials or network required.
Every file, source minute hash, signal, entry, stop, exit leg and metric
is verified. The original 0.1 ZIP remains bundled byte-for-byte unchanged.
Review study/E1_E2_SEQUENTIAL_30D.xlsx (five current-only sheets).

To install verified results into a fresh Trading Desk checkout:

    python3 REPRODUCE.py --install-store "/path/to/ai-day-trade/trading_records/btc_structure"

Installation preserves existing different artifacts by refusing to overwrite
them. It creates an observed-only local minute archive only when none exists.
The page /btc-lab then shows the three current sequences. No order is enabled.
"""
    (stage/'README.md').write_text(notes)
    files={str(p.relative_to(stage)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*'))
        if p.is_file() and p.name not in ('MANIFEST.json',ARCHIVE,'REPRODUCTION.json') and '__pycache__' not in p.parts}
    manifest=dict(version=VERSION,kind='frozen_sequential_comparison',release_date='2026-11-09',
        tag=TAG,study_id=study['study_id'],run_ids=study['run_ids'],baseline_version='0.1',
        source_minute_sha256=study['source_minute_sha256'],start=study['start'],end=study['end'],
        summaries=study['summaries'],files_sha256=files,orders_enabled=False)
    save(stage/'MANIFEST.json',manifest)
    completed=subprocess.run([sys.executable,str(stage/'REPRODUCE.py'),'--release-dir',str(stage)],
        capture_output=True,text=True,timeout=1200)
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    verification=json.loads(completed.stdout.strip().splitlines()[-1])
    assert verification['reproduced']
    save(stage/'REPRODUCTION.json',verification)
    manifest['files_sha256']['REPRODUCTION.json']=hashlib.sha256((stage/'REPRODUCTION.json').read_bytes()).hexdigest()
    save(stage/'MANIFEST.json',manifest)
    with zipfile.ZipFile(stage/ARCHIVE,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file() and p.name!=ARCHIVE and '__pycache__' not in p.parts:z.write(p,str(p.relative_to(stage)))
    stage.rename(folder)
    registry['0.2'].update(archive_sha256=hashlib.sha256((folder/ARCHIVE).read_bytes()).hexdigest(),
        manifest_sha256=hashlib.sha256((folder/'MANIFEST.json').read_bytes()).hexdigest())
    save(STORE/'releases/INDEX.json',registry)
    save(STORE/'releases/CURRENT_REVIEW.json',dict(version='0.2',study_id=study['study_id']))
    return folder,manifest


if __name__=='__main__':
    folder,manifest=freeze()
    print(json.dumps(dict(version=VERSION,tag=TAG,archive=str(folder/ARCHIVE),frozen=True)))
