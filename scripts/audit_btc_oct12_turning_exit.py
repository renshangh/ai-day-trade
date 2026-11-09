"""Approved new-high-failure exit: evening continuation plus morning regression."""
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,iso,ts,save
from trading_desk.btc_turning_replay import POLICY
from audit_btc_oct12_b_branches import FOLDER,BASELINE,load,local
from audit_btc_oct12_profit_guard import engine_for_case

OUTPUT=FOLDER.parent/'oct12_approved_turning_exit'


def review():
    source,minutes=load();cases=[]
    previous=json.loads((FOLDER.parent/'oct12_approved_profit_guard/REVIEW.json').read_text())
    continuation=json.loads((FOLDER.parent/'oct12_night_continuation/REVIEW.json').read_text())
    for i,old in enumerate(previous['cases']):
        end=ts(old['cutoff']) if i==0 else minutes[-1]['t']+60
        nominated=ts(old['nominated_bar']);entry_at=ts(old['trade']['entry_time'])
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        e=engine_for_case(nominated,end,db,exit_version='turning_consumed_v7')
        if e.policy!=POLICY:raise ValueError('Current factory does not use approved turning policy')
        for b in minutes:
            if b['t']>=end:break
            e.minute(b)
            if e.trades:break
        r=e.finish()
        if len(r['trades'])!=1 or r['trades'][0]['status']!='closed':raise ValueError('No closed nominated trade; do not fabricate an exit')
        p=r['trades'][0];exit_at=ts(p['exit_time'])
        if any(p[k]!=old['trade'][k] for k in ('entry','entry_time','initial_stop','t1','t2')):
            raise ValueError('Original entry/risk/target changed')
        if p['legs'][0]!=old['trade']['legs'][0]:raise ValueError('Original 25% profit leg changed')
        if i==0 and p['legs']!=old['trade']['legs']:raise ValueError('Morning regression changed')
        actual=[b for b in minutes if entry_at<=b['t']<=exit_at]
        if [b['t'] for b in actual]!=list(range(entry_at,exit_at+60,60)):
            raise ValueError('Missing holding minutes, no synthetic fill')
        rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t',(nominated,))]
        db.close()
        for b in rows:
            b['observed_end_exclusive']=iso(min(b['t']+900,exit_at+60))
            b['is_complete']=b['observed_minutes']==15 and b['t']+900<=exit_at+60
        cases.append(dict(nominated_bar=old['nominated_bar'],cutoff=iso(exit_at+60),trade=p,rows=rows,
            realized_gross=sum(l['gross'] for l in p['legs']),realized_cost=sum(l['cost'] for l in p['legs']),
            realized_net=sum(l['net'] for l in p['legs']),parameters_unchanged=True,missing_holding_minutes=0))
    night=cases[1];last=night['trade']['case_exit_evidence'][-1]
    if last['reason']!='turning_exit_remaining':raise ValueError('Different earliest exit; inspect instead of forcing target bar')
    selected=continuation['turning_bar_review']['with_new_high'][0]
    if last['time_utc']!=selected['time_utc'] or last['price']!=selected['reference_price']:
        raise ValueError('Program differs from previously reviewed turning observation')
    return dict(status='complete',policy=POLICY,rule_approved=True,cases=cases,source=source,
        month_rerun=False,orders_enabled=False,broker_orders=0,paper_orders=0,
        previous_v4_net=continuation['case']['realized_net'],
        exit_net_change=night['realized_net']-continuation['case']['realized_net'],
        costs=previous['costs'],
        scope='one evening continuation plus fixed morning regression; no monthly study',
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__).resolve(),ROOT/'trading_desk/btc_turning_replay.py',ROOT/'trading_desk/btc_engine.py')})


def report(r):
    c=r['cases'][1];p=c['trade'];d=p['case_exit_evidence'][-1]['turning']
    out=['# BTC 10月12日晚盘：已批准冲高失败退出','',
        '接入本根创新高后局部回撤转弱，保留首笔25%和原有保护，核对04:15–04:30这根退出。','',
        'Last Updated: 2026-11-08  ','Status: 已接入并复核；晚盘全平；未重跑整月  ',
        'Audience: Trading Desk使用者与研究维护者','', '## Overview','',
        '时间均为纽约EDT（UTC−4）。本次“04:30转弱K线”指04:15–04:30区间，按已约定最后一分钟观察，实际模型退出参考在04:29，不是04:15开盘卖在最高点，也不等04:30最终收盘。',
        '', '## 新增且独立的退出条件','',
        '最后1分钟，用此前14根完整分钟和当前首价判断：本根已超过持仓此前完整K线保留的波段高点；前一根完整15分钟K线为阳线；当时价格跌到前根全振幅中点下方；本根当时为红线，价格不高于前根收盘；实体与已观察全振幅均非内包。全部通过退出当前余仓。',
        '这个50%比较的是**前根上涨K线的全振幅**，沿用已讨论的(H＋L)/2；不是从入场起全部浮盈回吐50%。原1R／50%利润保护、硬止损、已确认结构、长上影仍各自有效；T1卖25%，固定T2不执行。没有新增ATR或实体比例阈值。',
        '', '## 时间、价格与整笔盈亏','',
        f"入场：10月12日21:00–21:01，{p['entry']:,.6f}；初始硬止损{p['initial_stop']:,.9f}。",'',
        '| 事件 | 纽约时间区间 | 模型价格参考 | 初始仓位比例 | 毛盈亏 | 成本 | 净盈亏 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for l in p['legs']:
        label='首次目标止盈' if l['reason']=='target_25' else '冲高失败，退出余仓'
        out.append(f"| {label} | {local(l['time_utc'])}–{local(ts(l['time_utc'])+60)[11:16]} | {l['price']:,.9f} | {l['fraction']:.0%} | {l['gross']:,.6f} | {l['cost']:,.6f} | {l['net']:,.6f} |")
    out.append(f"| 整笔合计 | 余仓0% | — | 100% | {c['realized_gross']:,.6f} | {c['realized_cost']:,.6f} | **{c['realized_net']:,.6f}** |")
    out+=['', '按初始1 BTC、零佣金及每边2bps成本模型；不是ETF实际成交。未把04:29分钟的最后收盘、最高或最低用于当时退出决定。',
        '', '## 04:29当时可见的证据','',
        f"前根04:00–04:15已经完整：O={d['previous_open']:,.6f}、H={d['previous_high']:,.6f}、L={d['previous_low']:,.6f}、C={d['previous_close']:,.6f}。中点{d['previous_midpoint']:,.8f}从04:15起已知。",
        f"本根已观察最高{d['observed_high']:,.6f}超过此前波段高{d['prior_wave_high']:,.6f}。04:29首价{d['reference_price']:,.6f}低于中点，前根全振幅回撤{d['prior_range_retracement']:.6%}；且低于本根开盘{d['opening_15m']:,.6f}与前收盘。实体及已观察振幅均非内包。",
        '01:44虽然红线、非内包并跌过前根中点，但本根没有创新高，被新增规则明确拦截；不是事后跳过更早信号。04:29上影占比为零，但这是独立的冲高失败形态，不要求长上影。',
        '', '## 版本和范围','',
        f"旧V4仅靠结构保护会在04:50退出，整笔净+{r['previous_v4_net']:,.2f}；当前V5按最早新信号在04:29退出，整笔净+{c['realized_net']:,.2f}。模型差额+{r['exit_net_change']:,.2f}，不能据单例认定长期最优。",
        f"早盘兼容性核对仍为10:11卖25%、10:19退余75%，整笔净+{r['cases'][0]['realized_net']:,.2f}；没有改入场、初始止损、目标或成本。",
        '历史V4调度显式固定guarded_v4，旧01:45检查点及04:50结果原样保留；当前工厂默认V5。没有重跑整月、改写latest_run或提交真实/paper订单。',
        f"真实Alpaca分钟SHA256 `{r['source']['sha256']}`，持有区间缺失0。",'',
        'JSON保留全部逐根事件与当时观察；EXITS.csv列出新程序退出及盈亏。最后一分钟判断意味着04:29–04:30区间参考，精确秒与ETF实际成交未验证。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    paths=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json']+list(FOLDER.parent.glob('*/REVIEW.json'))
    paths=[p for p in paths if p.parent!=OUTPUT]
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):raise ValueError('Historical result changed')
    if dirs!=sorted(p.name for p in (STORE/'runs').iterdir()):raise ValueError('Monthly run created')
    r['prior_artifact_sha256']={str(p.relative_to(ROOT)):h for p,h in before.items()}
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',r)
    with (OUTPUT/'EXITS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['nominated_bar','reason','time_ny','price','fraction','gross','cost','net']);writer.writeheader()
        for c in r['cases']:
            for l in c['trade']['legs']:writer.writerow(dict(nominated_bar=c['nominated_bar'],**{k:l[k] for k in ('reason','time_ny','price','fraction','gross','cost','net')}))
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_APPROVED_TURNING_EXIT.md').write_text(report(r))
    print(json.dumps([dict(case=c['nominated_bar'],legs=c['trade']['legs'],net=c['realized_net']) for c in r['cases']]))
