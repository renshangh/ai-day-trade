"""Authorized same-source full-sequence E1/E2 studies, preserving release 0.1."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import create_replay,export_csv
from trading_desk.btc_early_sequential import EarlySequentialReplay
from scripts.btc_structure_retest import Config
from scripts.audit_btc_release01_early_failure_all import load_frozen_source
from scripts.audit_btc_release01_pullbacks import RUN,clock


def stats(trades):
    closed=[p for p in trades if p['status']=='closed']
    balance=peak=dd=0
    for p in closed:
        balance+=p['net_r'];peak=max(peak,balance);dd=max(dd,peak-balance)
    return dict(entries=len(trades),closed=len(closed),open=len(trades)-len(closed),
        wins=sum(p['net']>0 for p in closed),losses=sum(p['net']<=0 for p in closed),
        win_rate=sum(p['net']>0 for p in closed)/len(closed) if closed else None,
        net=sum(p['net'] for p in closed),net_r=balance,max_drawdown_r=dd,
        realized_leg_net=sum(l['net'] for p in trades for l in p['legs']),
        cost=sum(l['cost'] for p in trades for l in p['legs']),
        holding_gap=sum(p['gap_exposed'] for p in trades),partial_context=sum(p['context_partial'] for p in trades))


def summarize(result):
    all_trades=result['trades']
    clean=[p for p in all_trades if not(p['gap_exposed'] or p['context_partial'])]
    flagged=[p for p in all_trades if p['gap_exposed'] or p['context_partial']]
    return dict(all=stats(all_trades),no_flagged_gap=stats(clean),gap_or_partial_context=stats(flagged),
        holding_gap_only=stats([p for p in all_trades if p['gap_exposed']]))


def sequence_changes(baseline,new):
    def key(p):return p['entry_time'],p['entry_rule']
    old={key(p):p for p in baseline['trades']};fresh={key(p):p for p in new['trades']}
    added=[];changed=[];missing=[]
    early=[(p,l) for p in new['trades'] for l in p['legs'] if l['reason'] in ('e1_exit_remaining','e2_exit_remaining')]
    for p in new['trades']:
        before=old.get(key(p))
        if before is None:
            blockers=[o['id'] for o in baseline['trades'] if ts(o['entry_time'])<=ts(p['entry_time']) and
                (o['status']=='open' or ts(p['entry_time'])<ts(o['exit_time']))]
            prior=next(((q,l) for q,l in reversed(early) if ts(l['time_utc'])<ts(p['entry_time'])),None)
            added.append(dict(trade_id=p['id'],entry_rule=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],
                exit_time=p.get('exit_time'),net=p['net'],remaining=p['remaining'],baseline_blocker_ids=blockers,
                preceding_early_exit_trade=prior[0]['id'] if prior else None,preceding_early_exit=prior[1]['time_utc'] if prior else None,
                explanation='earlier exit freed a slot while baseline held' if blockers else 'changed subsequent setup/position sequence',
                gap_exposed=p['gap_exposed'],context_partial=p['context_partial']))
        elif before['legs']!=p['legs'] or before['initial_stop']!=p['initial_stop']:
            changed.append(dict(baseline_trade_id=before['id'],new_trade_id=p['id'],entry_time=p['entry_time'],
                baseline_net=before['net'],new_net=p['net'],net_change=p['net']-before['net'] if p['net'] is not None and before['net'] is not None else None,
                baseline_exit=before.get('exit_time'),new_exit=p.get('exit_time'),
                initial_stop_changed=before['initial_stop']!=p['initial_stop'],
                baseline_gap=before['gap_exposed'] or before['context_partial'],new_gap=p['gap_exposed'] or p['context_partial']))
    for p in baseline['trades']:
        if key(p) not in fresh:
            owner=next((q for q in new['trades'] if ts(q['entry_time'])<=ts(p['entry_time']) and
                (q['status']=='open' or ts(p['entry_time'])<=ts(q['exit_time']))),None)
            missing.append(dict(baseline_trade_id=p['id'],entry_time=p['entry_time'],entry_rule=p['entry_rule'],baseline_net=p['net'],
                held_by_new_trade=owner['id'] if owner else None,
                explanation='new position occupied this time' if owner else 'entry-history sequence no longer qualified the same setup'))
    windows=[]
    for old_key,p in fresh.items():
        before=old.get(old_key)
        if not before or p['status']!='closed' or ts(p['exit_time'])>=ts(before['exit_time']):continue
        if not any(l['reason'] in ('e1_exit_remaining','e2_exit_remaining') for l in p['legs']):continue
        signals=[q for q in new['signals'] if ts(p['exit_time'])<ts(q['time_utc'])<ts(before['exit_time'])]
        windows.append(dict(baseline_trade_id=before['id'],new_trade_id=p['id'],from_time=p['exit_time'],to_time=before['exit_time'],
            minutes=(ts(before['exit_time'])-ts(p['exit_time']))//60,crossed_signal_count=len(signals),
            qualified_signal_count=sum(q['qualified_candidate'] for q in signals),signal_ids=[q['id'] for q in signals]))
    return dict(freed_windows=windows,added=added,changed_same_entry=changed,baseline_entries_not_taken=missing,
        early_exit_count=len(early),matched_entry_count=len(old.keys()&fresh.keys()))


def verify_baseline(original,minutes):
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=create_replay(ts(original['start']),ts(original['end']),db,expanded_b=True,exit_version='failed_rebound')
    for b in minutes.values():e.minute(b)
    actual=e.finish();db.close()
    assert len(actual['trades'])==len(original['trades'])
    for a,b in zip(actual['trades'],original['trades'],strict=True):
        for k in ('entry_time','entry','initial_stop','t1','t2','legs','status','remaining'):assert a[k]==b[k],(b['id'],k)
    assert actual['metrics']==original['metrics']


def run_variant(policy,original,minutes,study_id,progress=None):
    now=datetime.now(timezone.utc)
    while True:
        run_id=now.strftime('%Y%m%dT%H%M%SZ')+'-30-ab';folder=STORE/'runs'/run_id
        if not folder.exists():break
        now+=timedelta(seconds=1)
    folder.mkdir(parents=True)
    db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)');db.execute('CREATE INDEX ledger_day ON ledger(day,t)')
    e=EarlySequentialReplay(ts(original['start']),ts(original['end']),db,
        Config(version='Alpaca-BTC-release-0.1-'+policy+'-sequential-v1',first_sale_fraction=.25,resistance_mode='major1h'),
        early_policy=policy,expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
    try:
        for count,b in enumerate(minutes.values(),1):
            e.minute(b)
            if count%10000==0:
                db.commit()
                if progress:progress(dict(processed=count,time=iso(b['t']),run_id=run_id,candidate=policy))
        result=e.finish();db.commit()
        for key in ('start','end','warmup_start','days','source','source_minute_sha256','minute_count','test_data_quality','cost_model','draft_parameters','entry_mode','expanded_b'):
            result[key]=copy.deepcopy(original[key])
        result.update(run_id=run_id,status='complete',strategy_version=e.cfg.version,research_policy=policy,
            study_id=study_id,sequential_exit_policy=policy,source_frozen_release='0.1')
        result['draft_parameters']['early_exit_candidate']=policy+' unchanged completed-bar definition, exact next-minute opening, full sequential entries'
        result['draft_parameters']['early_exit_priority']='known opening exits: existing hard/structure/failed-rebound/giveback/turning/wick, then E1/E2, then T1; all known openings before unresolved minute range'
        result['code_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            list((ROOT/'trading_desk').glob('btc_*.py'))+[ROOT/'scripts/btc_structure_retest.py',ROOT/'scripts/audit_btc_release01_early_failure.py']}
        export_csv(folder,result,db);save(folder/'result.json',result)
        rows=[json.loads(body) for (body,) in db.execute('SELECT body FROM ledger ORDER BY t')]
        save(folder/'WORKBOOK_DATA.json',dict(result=result,ledger=rows))
        return result
    finally:db.close()


def write_report(study):
    lines=['# BTC 0.1对照：E1／E2同源30天完整顺序重跑','',
        '允许提前平仓后的新买点自然进入，其他入场、保护及成本参数保持0.1。','',
        'Last Updated: 2026-11-09  ','Status: 本轮完整顺序完成；0.1仍为冻结对照  ',
        'Audience: 交易桌使用者及维护者','','## Overview','',
        f"窗口{clock(study['start'])}至{clock(study['end'])}（不含），与0.1相同的真实分钟流及7天预热；SHA256 `{study['source_minute_sha256']}`。",
        '0.1基准先逐笔重放核对，入场、止损、目标、每腿退出与指标全部一致；原文件未改。E1/E2各自完整重跑，原激进B1、A/B2入场、消费旧入场结构、一笔持仓限制、止损／目标参数、T1卖25%及每边2bps成本不变。',
        '本轮不是固定38笔入场的退出归因。两条新序列可以自然产生或跳过买点；每笔仍按初始1 BTC，非账户复利或ETF真实成交。','',
        '## 全部与缺口分组','',
        '互斥分组：无已标记缺口=持有无观测缺口且入场前14根15分钟完整相邻；含缺口／窗口不完整=其补集。不保证更早阻力背景完全。另列持有期缺口笔数。提前退出可能在原缺口之前离场，因此分组样本自然变化，不是固定配对比较。','',
        '| 方案／分组 | 入场／平仓／未平仓 | 胜／负 | 已平仓净USD | 净R | 最大回撤R | 持有缺口／入场窗口不完整 |',
        '| --- | --- | --- | ---: | ---: | ---: | --- |']
    names={'all':'全部','no_flagged_gap':'无已标记缺口','gap_or_partial_context':'含缺口／窗口不完整'}
    for model in ('0.1','E1','E2'):
        for group,label in names.items():
            s=study['summaries'][model][group]
            lines.append(f"| {model}／{label} | {s['entries']}／{s['closed']}／{s['open']} | {s['wins']}／{s['losses']} | {s['net']:+,.2f} | {s['net_r']:+.6f} | {s['max_drawdown_r']:.6f} | {s['holding_gap']}／{s['partial_context']} |")
    for model in ('E1','E2'):
        c=study['changes'][model]
        lines+=['',f'## {model}完整顺序变化','',
            f"实际{model}退出{c['early_exit_count']}次；保留相同时间和路线入场{c['matched_entry_count']}笔，新增入场{len(c['added'])}笔，未再采取的原入场{len(c['baseline_entries_not_taken'])}笔。",'',
            '| 新交易# | 入场纽约时间／价 | 初始止损 | 原0.1当时持有# | 本序列此前提前退出 | 新净盈亏 |',
            '| --- | --- | ---: | --- | --- | ---: |']
        if not c['added']:lines.append('| 本轮没有新增买点 | — | — | — | — | — |')
        for p in c['added']:
            lines.append(f"| {p['trade_id']} | {clock(p['entry_time'])}／{p['entry']:,.4f} | {p['initial_stop']:,.4f} | {p['baseline_blocker_ids']} | {clock(p['preceding_early_exit']) if p['preceding_early_exit'] else '无直接提前退出对应'} | {p['net'] if p['net'] is not None else '未平仓'} |")
        lines+=['','### 提前释放的空仓窗口','', '| 原#／新# | 新退出至原退出（纽约） | 释放分钟 | 新越价信号／合格候选 |', '| --- | --- | ---: | --- |']
        for w in c['freed_windows']:
            lines.append(f"| {w['baseline_trade_id']}／{w['new_trade_id']} | {clock(w['from_time'])} → {clock(w['to_time'])} | {w['minutes']} | {w['crossed_signal_count']}／{w['qualified_signal_count']} |")
        lines+=['','### 相同入场的退出或结构参考变化','',
            '| 原#／新# | 入场时间 | 原净USD | 新净USD | 净差 | 原退出／新退出 |','| --- | --- | ---: | ---: | ---: | --- |']
        for p in c['changed_same_entry']:
            lines.append(f"| {p['baseline_trade_id']}／{p['new_trade_id']} | {clock(p['entry_time'])} | {p['baseline_net']} | {p['new_net']} | {p['net_change']} | {clock(p['baseline_exit']) if p['baseline_exit'] else '未平仓'}／{clock(p['new_exit']) if p['new_exit'] else '未平仓'} |")
    lines+=['','## 展示与保留','',
        '交易桌本轮只展示0.1、E1、E2及最新独立工作簿；先前单例、固定入场、独立守D和旧月度研究从当前界面与新表格移除，保留原路径和归档索引，不删除行情缓存。0.1冻结源码、结果、原工作簿与ZIP均核验未改。',
        '完整新序列仍为已反复审查月份的样本内条件研究；缺失分钟不补值，缺口内可能存在未观测触发。窗口末未平仓不虚构平仓价，已平仓净额和已实现腿收益分开。']
    (ROOT/'docs/investigations/2026-11-09_BTC_E1_E2_SEQUENTIAL_30D.md').write_text('\n'.join(lines)+'\n')


def run_study(progress=None):
    protected=[STORE/'releases/ACTIVE.json']+list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))+list((STORE/'releases/0.1').rglob('*'))
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected if p.is_file() and '__pycache__' not in str(p)}
    original,minutes,digest=load_frozen_source()
    study_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-E1-E2-sequential'
    folder=STORE/'studies'/study_id;folder.mkdir(parents=True,exist_ok=False)
    verify_baseline(original,minutes)
    results={k:run_variant(k,original,minutes,study_id,progress) for k in ('E1','E2')}
    study=dict(study_id=study_id,status='complete',baseline_run=RUN,run_ids={'0.1':RUN,**{k:v['run_id'] for k,v in results.items()}},
        start=original['start'],end=original['end'],warmup_start=original['warmup_start'],source_minute_sha256=digest,
        source_quality=original['test_data_quality'],baseline_reproduced=True,
        summaries={'0.1':summarize(original),**{k:summarize(v) for k,v in results.items()}},
        changes={k:sequence_changes(original,v) for k,v in results.items()},
        gap_definition='gap_exposed OR context_partial; complementary no-flagged-gap subset',
        promoted_release=False,orders_enabled=False)
    save(folder/'STUDY.json',study)
    archived=[]
    for p in sorted((STORE/'runs').glob('*/result.json')):
        if p.parent.name not in study['run_ids'].values():archived.append(dict(run_id=p.parent.name,path=str(p.relative_to(STORE)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    save(folder/'ARCHIVED_RESEARCH_INDEX.json',dict(hidden_from_current_ui=archived,files_preserved=True))
    source=folder/'source';source.mkdir()
    for p in list((ROOT/'trading_desk').glob('btc_*.py'))+[ROOT/'scripts/audit_btc_release01_early_failure.py',Path(__file__).resolve()]:
        dest=source/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for p,h in hashes.items():assert hashlib.sha256(p.read_bytes()).hexdigest()==h,p
    save(folder/'PRESERVED_FILES_SHA256.json',{str(p.relative_to(STORE)):h for p,h in hashes.items()})
    write_report(study)
    save(STORE/'studies/ACTIVE.json',dict(study_id=study_id))
    save(STORE/'latest_run.json',dict(run_id=results['E2']['run_id']))
    return study


if __name__=='__main__':
    s=run_study(progress=lambda p:print(json.dumps(p),flush=True))
    print(json.dumps(dict(study_id=s['study_id'],run_ids=s['run_ids'],summaries=s['summaries'],changes={k:{f:v for f,v in x.items() if f in ('early_exit_count','matched_entry_count')} for k,x in s['changes'].items()}),indent=2))
