"""Read-only feasibility notes for an E3 exit; no E3 rule, replay or trades."""
from __future__ import annotations
import bisect
from collections import Counter,defaultdict
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_live import LIVE
from trading_desk.btc_engine import aggregate
from trading_desk.btc_parent_memory_view import PARENT_MEMORY_VIEW
from scripts.retest_btc_parent_five import preservation,verify_preserved,CASE_END

OUT=ROOT/'reports/btc_e3_feasibility_2026_11_15'
NY=ZoneInfo('America/New_York')


def clock(t):
    if isinstance(t,str):t=ts(t)
    return datetime.fromtimestamp(t,NY).strftime('%m/%d %H:%M:%S %Z')


def full_bar(rows,t,seconds):
    group=[b for b in rows if t<=b['t']<t+seconds]
    if [b['t'] for b in group]!=list(range(t,t+seconds,60)):return None
    return aggregate(group,seconds)


def main():
    before=preservation();folder,study=PARENT_MEMORY_VIEW.current();case=read(folder/'CASE.json')
    protected=[p for p in folder.rglob('*') if p.is_file()]
    protected += [folder.parent/'ACTIVE.json',ROOT/'trading_desk/btc_parent_memory.py',
        ROOT/'trading_desk/btc_parent_five.py',ROOT/'scripts/retest_btc_parent_memory.py']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    source=LIVE/'sessions'/case['source_session']/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(CASE_END,)).fetchall()
    assert hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest()==case['source_sha256']
    rows=[json.loads(body) for body,_ in records]
    receipts={b['t']:r for b,(_,r) in zip(rows,records)}
    c=case['models']['0.1']['retained'];first=next(p for p in c['trades'] if p['entry_time']=='2026-11-15T04:47:00Z')
    second=next(p for p in c['trades'] if p['entry_time']=='2026-11-15T06:44:00Z')
    fifteen={b['t']:b for b in c['bars']}
    entry=ts(second['entry_time']);hl=second['references']['l2']['price']
    held=[b for b in rows if entry<b['t']<ts('2026-11-15T03:20:00-05:00')]
    breaches={field:next(b for b in held if b[field]<hl) for field in ('low','close','open')}
    five=[]
    for t in range(ts('2026-11-15T02:15:00-05:00'),ts('2026-11-15T03:30:00-05:00'),300):
        b=full_bar(rows,t,300);assert b is not None
        atr=fifteen[t//900*900]['atr_before']
        b.update(prior_15m_atr=atr,open_close_down_atr=(b['open']-b['close'])/atr,
            down_pct=100*(1-b['close']/b['open']),known_after=iso(t+300),
            raw_inputs_received_at=iso(max(receipts[m] for m in range(t,t+300,60))),
            below_original_entry_HL=b['close']<hl)
        five.append(b)
    top_before_break=max(b['high'] for b in rows if entry<=b['t']<breaches['low']['t'])
    bottom=min(held,key=lambda b:b['low'])
    traces={m:[x for x in next(p for p in case['models'][m]['retained']['trades']
        if p['entry_time']==second['entry_time']).get('early_exit_trace',[])
        if ts('2026-11-15T01:45:00-05:00')<=ts(x['bar_time'])<=ts('2026-11-15T03:00:00-05:00')]
        for m in ('E1','E2')}
    assert all(not x['A_qualified'] and x['B_stage']=='waiting_for_weakness' for values in traces.values() for x in values)
    assert breaches['low']['t']==ts('2026-11-15T02:36:00-05:00')
    assert top_before_break==64519.06
    assert second['status']=='open' and second['net'] is None
    assert not second['legs']
    # Inspect archived outcomes only. No engine or exit simulation is created.
    monthly=read(folder/'0.1/retained_combined/result.json')
    archive=[];digest=hashlib.sha256()
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            digest.update(line);t,o,h,l,c_,v,n,_=json.loads(line)
            archive.append(dict(t=t,open=o,high=h,low=l,close=c_,volume=v,n=n))
    assert digest.hexdigest()==study['source_minute_sha256']
    times=[b['t'] for b in archive];index={b['t']:b for b in archive}
    counts=Counter();comparisons=[]
    with sqlite3.connect((folder/'0.1/retained_combined/ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for p in monthly['trades']:
            if p['entry_rule']!='PH5':continue
            outcome='winner' if p['net']>0 else 'loser';counts['all_'+outcome]+=1
            start,end=ts(p['entry_time']),ts(p['exit_time']);level=p['references']['l2']['price']
            path=archive[bisect.bisect_right(times,start):bisect.bisect_left(times,end)]
            breach=next((b for b in path if b['low']<level),None)
            if breach is None:continue
            counts['HLbreak_before_exit_'+outcome]+=1
            target=next((ts(l['time_utc']) for l in p['legs'] if l['reason']=='target_25'),None)
            before_target=target is None or breach['t']<target
            if not before_target:continue
            counts['HLbreak_before_T1_'+outcome]+=1
            t=breach['t']//300*300
            minute_group=[index[m] for m in range(t,t+300,60) if m in index]
            b=aggregate(minute_group,300) if len(minute_group)==5 else None
            ledger=db.execute('SELECT body FROM ledger WHERE t=?',(t//900*900,)).fetchone()
            atr=json.loads(ledger[0])['atr_before'] if ledger else None
            usable=bool(b and t+300<end and (target is None or t+300<target))
            comparisons.append(dict(trade_id=p['id'],entry_time=p['entry_time'],original_net=p['net'],
                entry_HL=level,first_breach=iso(breach['t']),five_bar=b,prior_15m_atr=atr,
                five_close_known_before_original_exit_and_T1=usable,
                open_close_down_atr=(b['open']-b['close'])/atr if b and atr else None,
                five_close_below_HL=bool(b and b['close']<level),
                gap_or_partial=bool(p['gap_exposed'] or p['context_partial']),
                remark='Original saved net, NOT E3 result; first breach excludes entry/exit minutes. No candidate threshold applied.'))
    winners=sorted((p for p in comparisons if p['original_net']>0 and not p['gap_or_partial']
        and p['five_close_known_before_original_exit_and_T1'] and p['five_close_below_HL']
        and p['open_close_down_atr'] is not None),key=lambda p:p['open_close_down_atr'],reverse=True)[:3]
    assert counts['all_winner']==37 and counts['all_loser']==63
    assert counts['HLbreak_before_T1_winner']==9 and counts['HLbreak_before_T1_loser']==35
    assert winners and winners[0]['open_close_down_atr']>1
    result=dict(study=study['study_id'],analysis_only=True,E3_defined=False,E3_enabled=False,
        thresholds_selected=False,month_rerun=False,trades_resimulated=False,
        source_sha256=case['source_sha256'],monthly_sha256=study['source_minute_sha256'],
        old_exit=first['failed_rebound_history'],old_exit_leg=first['legs'][0],
        retained_entry={k:second[k] for k in ('entry_time','entry','initial_stop','initial_risk','references','mark_time','mark_price','marked_net')},
        entry_HL_first_breach={k:dict(bar=b,received_at=iso(receipts[b['t']])) for k,b in breaches.items()},
        pre_breach_MFE=top_before_break-second['entry'],price_stop_distance=second['entry']-second['initial_stop'],
        local_bottom=dict(time=iso(bottom['t']),price=bottom['low'],entry_adverse_distance=second['entry']-bottom['low'],
            entry_adverse_pct=100*(second['entry']-bottom['low'])/second['entry']),
        five_minute_bars=five,early_exit_trace=traces,
        failed_rebound_states=[dict(time=iso(b['t']),known_at=iso(b['t']+900),state=b.get('failed_rebound_state'))
            for b in c['bars'] if ts('2026-11-15T01:45:00-05:00')<=b['t']<=ts('2026-11-15T03:00:00-05:00')],
        archived_outcome_counts=dict(counts),archived_first_HL_breaks=comparisons,winner_counterexamples=winners)
    for name,h in hashes.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
    result['preservation']=verify_preserved(before);result['preservation']['additional_files']=len(hashes)
    OUT.mkdir(parents=True,exist_ok=True);save(OUT/'AUDIT.json',result)
    write_report(result)
    print(json.dumps(dict(report=str(OUT/'AUDIT.md'),counts=counts,
        counterexamples=[dict(trade=p['trade_id'],original_net=p['original_net'],down_atr=p['open_close_down_atr']) for p in winners],
        preservation=result['preservation']),indent=2))


def write_report(r):
    p=r['retained_entry'];hl=p['references']['l2']['price'];risk=r['price_stop_distance']
    lines=['# BTC局部退出父背景与E3急跌保护可行性','',
        '只读复核00:48退出、03:20两种不成交原因，以及01:44重入后的快速失守。','',
        'Last Updated: 2026-11-15  ','Status: 分析完成；E3未定义阈值、未实施，未重跑或重算交易  ',
        'Audience: Trading Desk owner and maintainers','','## Overview','',
        '00:48符合现有局部H-L-LH破低退出，不代表大父D失效。原PH5因23:47成交时清除父背景而不能识别03:20重入；保留背景版本则已在01:44重入，03:20被单一持仓规则阻止。E3若立项，应处理急跌时现有退出尚未准备好的空档，而不是用它解决背景清除或强行制造03:20成交。',
        '时刻均为纽约时间：11月15日案例为EST，月度反例按各自日期标EDT或EST。均为历史观察，不是当前报价或实际成交。原逐根16根15分钟审查在 `reports/btc_ph5_exit_reentry_2026_11_15/AUDIT.html`。本次只读已保存结果和真实分钟数据，未建立E3、未选择数值门槛、未改变任何交易盈亏。',
        '', '## 首笔00:48退出与两个版本的03:20','',
        '| 时刻/区间 | 已知事件 | 含义 |','| --- | --- | --- |',
        '| 23:45–00:00 | 局部高点$65,132.251，00:15确认 | 不是要求突破原父峰$65,553 |',
        '| 00:00–00:15 | 局部低$64,716.855，00:30确认 | 当时仍高于原入场HL $64,620.60 |',
        '| 00:15–00:30 | 较低高点$65,001.735，00:45确认 | H-L-LH参考成立 |',
        '| 00:48 | 分钟低$64,707.8035跌破局部L；一分钟收盘又收回至$64,721.838 | 原规则盘中触发，不等收盘；净亏$135.66 |',
        '| 00:54 | 原入场HL $64,620.60也被跌破 | 后续确实有更深回落，不能仅因后来反弹而认定退出误杀 |',
        '| 原PH5至03:20 | 旧父背景成交时被清除；$63,735被当成新D | 新D缺独立守稳和后续反弹→HL，不可入场 |',
        '| 保留背景至03:20 | 结构和五分钟突破合格，但01:44仓位仍在 | held_position；不会在已有仓位上再买一次 |',
        '', '## E3候选的实际空档在01:44重入之后','',
        f"01:44入场${p['entry']:,.4f}，已确认的战术入场HL为${hl:,.2f}，大父D为$61,991.3285，硬止损${p['initial_stop']:,.4f}。原风险公式没变，但止损价差已有${risk:,.2f}/BTC。急跌发生前最高浮盈只有${r['pre_breach_MFE']:,.2f}，约{r['pre_breach_MFE']/risk:.3f}R，未启动1R浮盈回吐保护。",'',
        '| 观察时刻 | 当时证据 | 不是一个已定义E3退出点 |', '| --- | --- | --- |',
        '| 02:36–02:37分钟 | 低及收盘首次低于$64,137.90，收$64,124.975 | 这是入场HL失守的观察，不是新订单或替代成交 |',
        '| 02:35–02:40 | 完整5m收$64,037.0735，仍低于入场HL | 能研究更快确认，不能使用尚未完成的15m最终数据 |',
        '| 02:40–02:45 | 下一完整5m继续收$63,864.13，未收回HL | 持续失守，不只是首次触及的一根影线 |',
        f"| 02:51 | 低${r['local_bottom']['price']:,.3f} | 相对入场下探${r['local_bottom']['entry_adverse_distance']:,.2f}，约{r['local_bottom']['entry_adverse_pct']:.3f}%，不是已实现亏损 |",'',
        '失败反弹退出需要入场后被完整确认的H-L-LH。02:36失守HL时，这笔还没有确认的入场后H；02:15峰值要等02:30–02:45右侧结束才确认。随后也没有再反弹形成完整LH供其破低，所以该规则没有及时武装。',
        'E1须至少连续两次完整15m降高降低：02:15K抬高高低点使计数归零，02:30K结束时只有一次；02:45K结束累计两次，但它是绿K且收盘高于前收，方向过滤阻止退出。03:00K又抬高高低点，计数归零。E2尚无先行走弱阶段，仍等待，不会启动收复失败流程。',
        '', '## 完整五分钟观察','',
        'ATR来自原案例15分钟账本的atr_before，发生在该15分钟K线之前。下降倍数是该完整5分钟的开收跌幅/当时既知15m ATR，负数代表上涨；是描述性测量，不是E3门槛。每行仅在区间结束且所有原始输入收到后可知。',
        '', '| 5m开始 EST | 高 / 低 / 收 | 开收下降ATR | 收盘低于入场HL | 完整输入实际收到 |', '| --- | --- | ---: | --- | --- |']
    for b in r['five_minute_bars']:
        lines.append(f"| {clock(b['t'])} | {b['high']:,.3f} / {b['low']:,.3f} / {b['close']:,.3f} | {b['open_close_down_atr']:.3f} | {'是' if b['below_original_entry_HL'] else '否'} | {clock(b['raw_inputs_received_at'])} |")
    lines += ['', '## 已保存赢家对简单急跌退出的反例','',
        '只读保留背景0.1组合中的100笔PH5交易：37笔最终获利、63笔亏损。退出前且首次25%目标之前，9笔赢家和35笔亏损交易都曾盘中下穿原入场HL。统计排除入场/退出分钟内的未知先后顺序；没有对这些交易应用任何新退出规则。',
        '以下是无标记缺口、且完整5m结束在原退出和首次目标之前的赢家。按“发生HL失守的5m开收下降ATR”从大到小展示反例，而非测试某个E3阈值。数字是它们原有、未改变的模型净额。',
        '', '| 当前保留背景0.1组合交易# | 入场EST | 首次破HL分钟 | 当根完整5m下降ATR | 原净额 |', '| --- | --- | --- | ---: | ---: |']
    for p_ in r['winner_counterexamples']:
        lines.append(f"| {p_['trade_id']} | {clock(p_['entry_time'])} | {clock(p_['first_breach'])} | {p_['open_close_down_atr']:.3f} | ${p_['original_net']:,.2f} |")
    lines += ['',
        '所以“破HL就卖”或“单根5m跌得快就卖”都可能过早切掉赢家。必须独立研究失守后的持续性/收复行为及完整顺序。不能用本例05:15的浮盈来倒选持有，也不能只看02:51低点来倒选退出。01:44本身也可能属于过早重入，急跌退出不能替代入场质量问题的检查。',
        '', '## E3研究边界','',
        'E3可单列为“急跌时的入场失败保护”：结合原本已确认的入场级支撑失守、用事前ATR衡量的下行速度，以及未能收回支撑的观察。它不应等到浮盈1R，也不必等完整H-L-LH；否则仍会重复现有空档。父背景是否保留是独立状态问题，E3不能代替这项处理。',
        '本次没有固定速度阈值、连续分钟数、退出比例或估算新卖价。下一步若获授权，应先锁定E3定义和可观察/执行时间，再以固定入场对照亏损与赢家，之后才研究完整顺序和重入；不得屏蔽01:44或强制03:20成交。',
        f"案例01:44仓在同一历史截点仍未退出；最后真实参考{clock(p['mark_time'])}、${p['mark_price']:,.3f}，未实现标记浮盈${p['marked_net']:,.2f}。新E3若提前退出，有可能避免回撤，也有可能错过这段修复；未做反事实交易，不能声称净改善。",'',
        f"原{r['preservation']['files']}个保护文件和额外{r['preservation']['additional_files']}个研究/策略文件核验未变；0.2、PH5、父背景实验及live worker PID {r['preservation']['pid']}、session {r['preservation']['session']}不变。数据含quote-derived/零场内成交量分钟，不等于综合成交量或可保证成交价。"]
    text='\n'.join(lines)+'\n';(OUT/'AUDIT.md').write_text(text)
    (ROOT/'docs/investigations/2026-11-15_BTC_E3_RAPID_DROP_FEASIBILITY.md').write_text(text)


if __name__=='__main__':main()
