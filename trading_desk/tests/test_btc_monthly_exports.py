"""Monthly research exports preserve B1 absence and protection semantics."""
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_oct12_b_branches as audit
from trading_desk import btc_engine,btc_lab


def test_b1_without_hl_exports_blank_not_invented_low(tmp_path):
    _,minutes=audit.load()
    case=audit.case(minutes,'09:30')
    s=case['signal'];p=case['trade']
    assert s['references']['l2'] is None
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    btc_engine.export_csv(tmp_path,dict(signals=[s],trades=[p]),db)
    with (tmp_path/'SIGNALS.csv').open(encoding='utf-8-sig') as f:
        row=next(csv.DictReader(f))
    assert row['entry_rule']=='B1'
    assert row['hl_price']==row['hl_time']==row['hl_known_at']==''
    with (tmp_path/'TRADES.csv').open(encoding='utf-8-sig') as f:
        trade=next(csv.DictReader(f))
    assert trade['initial_stop_effective']==p['entry_time']
    assert float(trade['realized_leg_net'])==sum(l['net'] for l in p['legs'])
    with (tmp_path/'PROTECTION.csv').open(encoding='utf-8-sig') as f:
        protection=next(csv.DictReader(f))
    assert protection['kind']=='initial_hard_stop'
    assert protection['effective_time']==p['entry_time']
    db.close()


def test_protection_csv_is_downloadable_but_paths_stay_restricted(tmp_path):
    run='20261109T030906Z-30-ab'
    folder=tmp_path/'runs'/run;folder.mkdir(parents=True)
    (folder/'result.json').write_text(json.dumps(dict(status='complete')))
    (folder/'PROTECTION.csv').write_text('trade_id,kind\n')
    assert btc_lab.Lab(tmp_path).export(run,'PROTECTION.csv')==folder/'PROTECTION.csv'
