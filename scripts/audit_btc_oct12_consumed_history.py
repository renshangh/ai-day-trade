"""Audit the first entry and the stale B2 re-entry on real archived minutes only."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_btc_oct12_b_branches import load
from trading_desk.btc_data import STORE,ts,iso,save,read
from trading_desk.btc_engine import create_replay

FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_consumed_entry_history'
RUN='20261109T030906Z-30-ab'
START=ts('2026-10-12T09:30:00-04:00')
END=ts('2026-10-12T10:45:00-04:00')


def review():
    source,minutes=load()
    old_folder=STORE/'runs'/RUN
    preserved={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [STORE/'latest_run.json',old_folder/'result.json',old_folder/'RESEARCH.xlsx']}
    old=read(old_folder/'result.json');variants={}
    for label,version in [('before','turning_v5'),('after','turning_consumed_v7')]:
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        engine=create_replay(START,END,db,expanded_b=True,exit_version=version)
        at_reentry=None
        for b in minutes:
            if b['t']>=END:break
            engine.minute(b)
            if b['t']==ts(old['trades'][1]['entry_time']):
                at_reentry=dict(time=iso(b['t']),entry_setups=engine.detector.snapshot(),
                    ready_routes=[route for route,_ in engine.detector.setups()])
        result=engine.finish()
        rows=[json.loads(body) for (body,) in db.execute('SELECT body FROM ledger ORDER BY t')]
        variants[label]=dict(strategy_version=engine.cfg.version,trades=result['trades'],
            signals=result['signals'],rows=rows,at_old_reentry=at_reentry)
        db.close()
    before=variants['before'];after=variants['after']
    assert len(before['trades'])==2 and len(after['trades'])==1
    assert before['trades'][0]['legs']==after['trades'][0]['legs']==old['trades'][0]['legs']
    assert before['trades'][1]['entry_time']==old['trades'][1]['entry_time']
    assert before['trades'][1]['references']==old['trades'][1]['references']
    assert not after['at_old_reentry']['ready_routes']
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in preserved.items())
    return dict(source=source,source_run=RUN,start=iso(START),end_exclusive=iso(END),
        variants=variants,month_rerun=False,broker_orders=0,
        historical_sha256=preserved,
        finding='trade 2 reuses trade 1 impulse and D; entry consumes all A/B setup history; new full bars only',
        first_entry_unchanged=True,invalid_trade_id=2,
        fresh_bars_from=iso((ts(old['trades'][0]['entry_time'])//900+1)*900))


def main():
    result=review();FOLDER.mkdir(parents=True,exist_ok=True)
    save(FOLDER/'REVIEW.json',result)
    save(STORE/'runs'/RUN/'ENTRY_AUDIT.json',dict(
        status='requires_replay',invalid_trade_ids=[2],
        reason='Trade #2 reuses #1 pre-entry impulse/D; consumed setup history was not reset',
        checked_start=result['start'],checked_end_exclusive=result['end_exclusive'],
        fresh_bars_from=result['fresh_bars_from'],
        note='Saved monthly metrics/workbook remain the original run, not corrected totals; other trades not fully audited; no monthly rerun',
        review='reports/btc_structure_2026_11_08/entry_examples/oct12_consumed_entry_history/REVIEW.json'))
    print(json.dumps(dict(before_trades=len(result['variants']['before']['trades']),
        after_trades=len(result['variants']['after']['trades']),
        fresh_bars_from=result['fresh_bars_from'],first_entry_unchanged=True,
        old_1031_ready_routes=result['variants']['after']['at_old_reentry']['ready_routes'])))


if __name__=='__main__':main()
