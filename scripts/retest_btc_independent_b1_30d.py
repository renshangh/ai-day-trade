"""Authorized same-source monthly B1 confirmation rollout; release 0.1 immutable."""
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk import btc_data,btc_engine
from scripts.audit_btc_all_losses import totals

BASELINE='20261109T041525Z-30-ab'


def main():
    store=btc_data.STORE;old=btc_data.read(store/'runs'/BASELINE/'result.json')
    paths=list((store/'runs').glob('*/result.json'))+list((store/'runs').glob('*/RESEARCH.xlsx'))+list((store/'runs').glob('*/WORKBOOK_DATA.json'))
    paths+=list((store/'releases'/'0.1').rglob('*'))
    preserved={str(p.relative_to(store)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and '__pycache__' not in str(p)}
    result=btc_engine.run(30,store,expanded_b=True,research_policy='independent_b1',window_end=btc_data.ts(old['end']),
        progress=lambda p:print(json.dumps(p),flush=True))
    folder=store/'runs'/result['run_id']
    for key in ('start','end','warmup_start','source_minute_sha256','test_data_quality'):
        assert result[key]==old[key],key
    for name,digest in preserved.items():assert hashlib.sha256((store/name).read_bytes()).hexdigest()==digest,name
    assert result['b1_independent_hold'] and result['cost_model']==old['cost_model']
    # Only the B1 entry gate changes; numerical risk and exit declarations match.
    changed={k for k in old['draft_parameters'] if old['draft_parameters'][k]!=result['draft_parameters'][k]}
    assert changed<=set(['entry','b1_confirmation']),changed
    with sqlite3.connect(folder/'ledger.sqlite') as db:
        ledger=[json.loads(row[0]) for row in db.execute('SELECT body FROM ledger ORDER BY t')]
    btc_data.save(folder/'WORKBOOK_DATA.json',dict(result=result,ledger=ledger))
    comparison=dict(baseline=totals(old),current=totals(result),baseline_label='Release 0.1（冻结）',
        current_label='B1独立守D（月度核验）',same_source=True,source_minute_sha256=result['source_minute_sha256'],
        change_description_zh='仅B1增加D之后独立完整15分钟守D确认；下破后新D重新等待。A、B2及全部止损、退出、成本数值不变。顺序持仓变化也会影响后续交易；不是样本外验证。',historical_files_sha256=preserved)
    btc_data.save(folder/'COMPARISON.json',comparison)
    accepted=[]
    for s in result['signals']:
        c=s.get('b1_confirmation')
        if c and s['trade_id'] is not None:
            d=s['references']['l1']
            assert c['passed'] and c['independent'] and c['observed_minutes']==15
            assert c['time']>=d['known_at'] and c['known_at']<=s['time_utc'] and c['low']>=d['price']
            p=next(p for p in result['trades'] if p['id']==s['trade_id'])
            accepted.append(dict(trade_id=p['id'],signal_id=s['id'],d_time=d['time'],d_known_at=d['known_at'],d_price=d['price'],
                confirmation=c,entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],net=p.get('net')))
    rows=[]
    for p in old['trades']:
        matches=[n for n in result['trades'] if n['entry_time']==p['entry_time']]
        same=next((n for n in matches if n['entry_rule']==p['entry_rule']),None)
        crossed=[s for s in result['signals'] if s['time_utc']==p['entry_time']]
        disposition='原时间同路线保留' if same else '原时间由其他路线入场' if matches else '原时间无入场；按新月度结构与占仓重新判定'
        if p['id']==5:disposition='原D尚未独立确认，09:45禁止；09:53原D下破。后续新D不是原笔延迟成交'
        rows.append(dict(old_trade_id=p['id'],old_route=p['entry_rule'],old_entry_time=p['entry_time'],old_entry=p['entry'],old_net=p['net'],
            disposition=disposition,new_trade_id=matches[0]['id'] if matches else None,new_route=matches[0]['entry_rule'] if matches else None,
            new_entry=matches[0]['entry'] if matches else None,new_net=matches[0].get('net') if matches else None,
            observed_signal_ids=[s['id'] for s in crossed],decisions=[s['decision'] for s in crossed]))
    rejected=[s for s in result['signals'] if s.get('b1_confirmation') and not s['b1_confirmation']['passed']]
    audit=dict(baseline_run=BASELINE,current_run=result['run_id'],rows=rows,accepted_b1=accepted,
        waiting_cross_count=len(rejected),waiting_signal_ids=[s['id'] for s in rejected],
        original_trade5=btc_data.read(ROOT/'reports/btc_structure_2026_11_08/entry_examples/trade5_independent_post_d_hold/REVIEW.json'),
        all_b1_confirmation_checks_pass=True,orders_enabled=False)
    btc_data.save(folder/'B1_CONFIRMATION_REVIEW.json',audit)
    with (folder/'B1_CONFIRMATION_REVIEW.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(dict(run_id=result['run_id'],baseline=comparison['baseline'],current=comparison['current'],
        accepted_b1=len(accepted),waiting_crosses=len(rejected),retained_entries=sum(x['new_trade_id'] is not None for x in rows)),indent=2),flush=True)


if __name__=='__main__':main()
