"""Two nominated October 12 cases only; no run(), latest pointer or orders."""
import copy
import hashlib
import inspect
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,ts,iso,save
from trading_desk.btc_engine import Replay
from trading_desk.btc_ab_replay import ABReplay
from scripts.btc_structure_retest import Config

FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_b_branches'
BASELINE='20261109T002127Z-30-ab'
NY=ZoneInfo('America/New_York')


def local(t):
    if isinstance(t,str):t=ts(t)
    return datetime.fromtimestamp(t,NY).isoformat()


def load(folder=FOLDER):
    source=json.loads((folder/'SOURCE.json').read_text())
    payload=(folder/'ALPACA_OBSERVED_MINUTES.json').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=source['sha256']:
        raise ValueError('Archived source hash changed')
    return source,json.loads(payload)


def snapshot(folder=FOLDER):
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'SOURCE.json').exists():return load(folder)
    old=json.loads((STORE/'runs'/BASELINE/'result.json').read_text())
    start=ts(old['warmup_start']);end=ts('2026-10-14T00:00:00-04:00')
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        rows=[dict(t=t,open=o,high=h,low=l,close=c,volume=v) for t,o,h,l,c,v in db.execute(
            'SELECT t,o,h,l,c,v FROM minutes WHERE t>=? AND t<? ORDER BY t',(start,end))]
    payload=(json.dumps(rows,separators=(',',':'),allow_nan=False)+'\n').encode()
    (folder/'ALPACA_OBSERVED_MINUTES.json').write_bytes(payload)
    source=dict(source='Alpaca US BTC/USD real observed minute archive',
        baseline_run=BASELINE,start=iso(start),end_exclusive=iso(end),count=len(rows),
        missing_minutes=(end-start)//60-len(rows),sha256=hashlib.sha256(payload).hexdigest(),
        policy='Absent minutes stay absent; no interpolation or synthetic bars')
    save(folder/'SOURCE.json',source)
    return source,rows


class NominatedCase(ABReplay):
    def __init__(self,nominated,db,*,exit_policy='legacy'):
        self.nominated=nominated
        day_start=ts('2026-10-12T00:00:00-04:00')
        super().__init__(day_start,ts('2026-10-14T00:00:00-04:00'),db,
            cfg=Config(version='BTC-B1-B2-direction-filter-v2' if exit_policy=='approved' else 'BTC-B1-B2-approved-exits-two-case-v1' if exit_policy=='approved_v1' else 'BTC-B1-B2-two-case-draft-1',first_sale_fraction=.25,resistance_mode='major1h'),
            expanded_b=True,exit_policy=exit_policy)

    def scan(self,b,can_trade):
        chosen=b['t']//900*900==self.nominated and self.position_id==0
        before=len(self.signals)
        super().scan(b,can_trade=can_trade and chosen)
        if not chosen:
            for s in self.signals[before:]:
                if s['decision']=='exit_minute_no_reentry':s['decision']='outside_nominated_case'


def case(minutes,time):
    nominated=ts('2026-10-12T'+time+':00-04:00')
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=NominatedCase(nominated,db)
    held_minutes=[]
    for b in minutes:
        e.minute(b)
        if e.position or e.trades:held_minutes.append(copy.deepcopy(b))
        if e.trades:break
    r=e.finish()
    selected=[s for s in r['signals'] if s['route']=='B1' and nominated<=ts(s['time_utc'])<nominated+900]
    if not selected:raise ValueError('No B1 signal in nominated bar; do not fabricate an entry')
    s=selected[0]
    p=next((p for p in r['trades'] if p['signal_id']==s['id']),None)
    ledger=[json.loads(body) for body, in db.execute('SELECT body FROM ledger ORDER BY t')]
    db.close()
    return dict(nominated_bar=local(nominated),nominated_end=local(nominated+900),
        signal=s,trade=p,earlier_signals=[x for x in r['signals'] if ts(x['time_utc'])<nominated],
        later_structure_signals=[x for x in r['signals'] if ts(x['time_utc'])>=nominated+900],
        rows=[x for x in ledger if x['t']>=nominated-3600],held_minute_count=len(held_minutes),
        scope='Independent nominated entry, not a one-position full-day/month portfolio replay')


def review(folder=FOLDER):
    source,minutes=load(folder)
    baseline=json.loads((STORE/'runs'/BASELINE/'result.json').read_text())
    current={name:hashlib.sha256(inspect.getsource(getattr(Replay,name)).encode()).hexdigest()
        for name in ('minute','complete','close_part','targets')}
    if current!=baseline['unchanged_exit_contract']:
        raise ValueError('Frozen protective/target/exit methods changed')
    return dict(source=source,cases=[case(minutes,'09:30'),case(minutes,'21:00')],
        unchanged_exit_contract=current,
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__).resolve(),ROOT/'trading_desk/btc_shock_branches.py',ROOT/'trading_desk/btc_entry_rules.py',ROOT/'trading_desk/btc_ab_replay.py')},
        parameters=dict(stop_buffer_atr=.25,friction_bps_each_way=2,trigger_increment=.01,chase_atr=.1,
            b2_hl_tolerance_atr=.1,preferred_net_rr=2,minimum_net_target_reward='strictly positive',first_sale_fraction=.25),
        month_rerun=False,broker_orders=0,
        implementation='Expanded B opt-in only; default monthly engine and stored results unchanged')


def report(r):
    lines=['# BTC 10月12日：B1首次止跌与B2回踩突破','',
        '连续急跌入口的两条分支定义，以及09:30／21:00两个指定单例的因果核对。','',
        'Last Updated: 2026-11-08  ','Status: 两例研究；不重跑整月，不提交订单  ',
        'Audience: 交易学习手册使用者与Trading Desk维护者','',
        '## Overview','',
        '时间全部为2026年10月12日纽约EDT（UTC−4）；分钟区间是已观测参考，不是实际成交秒。两个指定例子分别独立评估，不假定前一候选仓位不存在或可以重叠。',
        '', '## B扩展定义','',
        '- **共同急跌锚点：** 完整15分钟阴线创setup新低，向下幅度≥2倍事前ATR14。只用当时数据。',
        '- **连续下跌继承：** 首根急跌成立后，在首次完整阳线反弹且其最低价守住D之前，后续完整K线创新低可延伸D，不要求每根仍≥2ATR或仍收阴。未完成K线的最低价不能提前用作D。完整反弹出现后再破D，则原准备失效；不得无限继承。',
        '- **B1首次止跌突破：** 前一根完整K线收盘离开其最低价（可以仍收阴），当前盘中守住当时已完成D并越过前根完整最高价＋$0.01。止跌由随后突破确认，单有下影不买。无HL则明确留空；不虚构HL，不套用B2的HL容差。每个完成D只记一次B1；延伸成新D才可重新准备。',
        '- **B2反弹回踩突破：** 先有完整阳线反弹守住D，再有已完成回踩HL，HL高于D至少0.10倍入场前ATR且触发前未破，随后盘中越前根完整最高价。B1和B2分别标记；持有B1时不因B2再次自动加仓。',
        '- 任何已开仓的止损都不随候选D向下延伸。初始保护仍为当时D−0.25倍入场前ATR；目标、追价、费用与退出沿用已有引擎。2R仅提示，净目标空间仍须严格为正。',
        '', '## 入场、初始保护与全部退出','',
        '| 指定K线 | 事件 | 纽约时间／区间 | 参考价 USD | 初始仓位比例 | 毛盈亏／净盈亏 USD |',
        '| --- | --- | --- | ---: | ---: | ---: |']
    for c in r['cases']:
        s=c['signal'];p=c['trade'];name=c['nominated_bar'][11:16]
        lines.append(f"| {name} | B1价格触发 | {local(s['time_utc'])} → {local(s['interval_end'])[11:16]} | {s['entry_reference']:.6f} | — | — |")
        lines.append(f"| {name} | 已完成D及其已知时点 | {local(s['references']['l1']['time'])}；{local(s['references']['l1']['known_at'])}起已知 | {s['references']['l1']['price']:.6f} | — | — |")
        lines.append(f"| {name} | 初始止损，假设成交立即生效 | {local(s['time_utc'])}起 | {s['initial_stop']:.6f} | 100% | — |")
        if p:
            for h in p.get('stop_history',[]):
                lines.append(f"| {name} | 止损上移，引用新低点{h['reference_low']:.6f} | {local(h['effective_time'])}起 | {h['price']:.6f} | — | — |")
            for leg in p['legs']:
                label={'target_25':'第一目标止盈','target_remaining':'第二目标退出余仓','stop':'保护止损退出余仓'}.get(leg['reason'],leg['reason'])
                lines.append(f"| {name} | {label} | {local(leg['time_utc'])} → {local(ts(leg['time_utc'])+60)[11:16]} | {leg['price']:.6f} | {leg['fraction']:.0%} | {leg['gross']:.6f}／{leg['net']:.6f} |")
            lines.append(f"| {name} | {'已平仓合计' if p['status']=='closed' else '归档末仍持仓'} | — | — | — | {sum(x['gross'] for x in p['legs']):.6f}／{sum(x['net'] for x in p['legs']):.6f} |")
        else:lines.append(f"| {name} | 不模拟入场 | 未过结构／风险资格 | — | — | — |")
    for c in r['cases']:
        s=c['signal'];p=c['trade'];w=s['setup_evidence']
        lines+=['',f"## {c['nominated_bar'][11:16]}指定例子的结构说明",'',
            f"锚点{local(w['impulse']['t'])}；初始D{w['impulse']['low']:.6f}。其后延伸D："+'；'.join(f"{local(x['time'])} {x['price']:.6f}（{local(x['known_at'])}起已知）" for x in w['extensions'])+'。',
            f"本例为**B1**，HL为不存在，不把首次反弹倒写成已回踩确认。入场前ATR={s['atr']:.9f}，T1={s['t1']}，T2={s['t2']}，净收益风险比={s['net_reward_risk']}（2R仅提示）。"]
        earlier=[x for x in c['earlier_signals'] if x['route'].startswith('B') and ts(x['time_utc'])>=w['impulse']['t']]
        lines.append('该急跌锚点之后、指定K线之前的候选：'+('；'.join(f"{x['route']} {local(x['time_utc'])}，{x['decision']}，D={x['references']['l1']['price']:.6f}" for x in earlier) if earlier else '未观察到更早B价格触发')+'。')
        later=[x for x in c['later_structure_signals'] if x['route'].startswith('B')]
        lines.append('本笔持有期间后续B候选：'+('；'.join(f"{x['route']} {local(x['time_utc'])}，{x['decision']}" for x in later) if later else '本次观察范围内无新增有效B候选')+'。')
        for x in later:
            if x['route']=='B2':
                hl=x['references']['l2']
                lines.append(f"该B2的HL={hl['price']:.6f}，发生于{local(hl['time'])}，从{local(hl['known_at'])}起已知；候选初始保护{x['initial_stop']:.6f}只属于假设的新B2交易，不覆盖本笔B1止损，也不构成已发生的上移／下移。")
        lines.append('本笔B1持有期间没有已生效的止损上移。' if not p or not p.get('stop_history') else '已生效止损变化见上表。')
    lines+=['','## 边界与复现','',
        '模型每笔按初始1 BTC归一化，ETF零佣金假设但保留每边2bps价差／滑点；不代表ETF实际收益。目标必须入场前已知，不因后来上涨替换更远目标。退出沿用网页原draft-3，包括历史整数关口长上影实现；未加入后来手册无整数关口／中点退出。',
        f"真实分钟来源：{r['source']['count']}个，SHA256 `{r['source']['sha256']}`；缺失{r['source']['missing_minutes']}分钟，未补值。保存`SOURCE.json`和原观测分钟。",
        '结果、完整事件与信号依据保存为同目录`B_BRANCH_REVIEW.json`。仅两笔独立条件案例，不是整月收益；默认月度入口仍冻结，历史结果与latest_run指针没有改写。']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    pointer=(STORE/'latest_run.json').read_bytes()
    snapshot();result=review()
    if (STORE/'latest_run.json').read_bytes()!=pointer:raise ValueError('Monthly pointer unexpectedly changed')
    save(FOLDER/'B_BRANCH_REVIEW.json',result)
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_B1_B2_CASES.md').write_text(report(result))
    print(json.dumps([dict(bar=c['nominated_bar'],entry=c['signal']['entry_reference'],time=c['signal']['time_ny'],
        stop=c['signal']['initial_stop'],status=c['trade']['status'] if c['trade'] else 'not entered',
        legs=c['trade']['legs'] if c['trade'] else []) for c in result['cases']],ensure_ascii=False))
