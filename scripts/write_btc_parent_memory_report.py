"""Publish saved retained-parent research without changing a model or selector."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read
from trading_desk.btc_parent_memory_view import PARENT_MEMORY_VIEW,dollar_drawdown


def clock(x):
    if x is None:return '—'
    d=datetime.fromtimestamp(x,ZoneInfo('America/New_York')) if isinstance(x,(float,int)) else datetime.fromisoformat(x.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
    return d.strftime('%m/%d %H:%M:%S %Z')


def run():
    folder,s=PARENT_MEMORY_VIEW.current();assert s['status']=='complete'
    case=read(folder/'CASE.json')
    lines=['# BTC父背景保留与买点消耗独立对照','',
        '保持退出和风险参数，区分未失效父波段与已使用的入场机会。','',
        'Last Updated: 2026-11-15  ','Status: 完成；未推广；保留背景组合仍全部亏损  ',
        'Audience: Trading Desk owner and maintainers','','## Overview','',
        '交易桌 `/btc-parent-memory` 展示原A/B、原PH5清空背景、PH5保留背景的完整顺序。原0.2、原PH5策略源码/结果/选择器、P1与live worker保持不变。原A/B和PH5两种模式的九个对照都逐笔复现，再计算新实验，没有后续调参。',
        f"固定原窗口 `[{s['start']}, {s['end']})`，同样七天预热；源SHA256 `{s['source_minute_sha256']}`。案例在该月窗口之外，不能混入月度收益。",'',
        '## 唯一改变的状态保存方式','',
        '原PH5每次成交后清空父D、已确认高低点及转折窗口。新实验仅将其拆开：仍有效的父D/峰值/实际K线背景保留；另存新买点起始边界，只允许上一笔成交K线之后的新完整15分钟HL。',
        '每个D/HL组合仍只消费一次，暖机/持仓/被风险拒绝的首次穿越同样消耗该组合，不留下可事后成交的排队买单。仍然单一持仓，退出分钟不重入；原A/B同时刻优先权及其原有消费规则不变。',
        '父D失效和缺口处理不变：价格触及/跌破父D会令其失效，缺分钟/不完整聚合仍清空父背景。没有新增到期时长、波动权重或价格门槛。新HL仍只须高于保留父D加原0.1ATR容差，并不额外要求高于上笔HL。',
        '同一15m ATR、0.1ATR追价上限、0.25ATR止损缓冲、重大阻力目标算法、25%首次卖出、全部退出方法及每边2bps成本代理均保持不变。先保存LOCKED_RULE，再核对案例和完整月份。',
        '', '## 03:20条件成立但并非再次成交','',
        '完整顺序没有强制等待03:20。它先在01:44重入，03:20候选虽然合格，却因已有仓位而跳过。旧父D与新HL不是同一已使用买点；但保留背景也允许较早、后来仍会回落的HL触发，不能只挑03:20这个后来有利的例子。',
        '', '| 模型 | 第一笔退出保持原样 | 更早的实际模型重入 | 03:20参考 / 决策 | 历史截点状态 |',
        '| --- | --- | --- | --- | --- |']
    for m in ('0.1','E1','E2'):
        c=case['models'][m];p=next(p for p in c['retained']['trades'] if p['entry_time']==c['position_at_0320']['entry_time'])
        lines.append(f"| {m} | 00:48 / $64,716.855 / 100%，净-$135.66 | {clock(p['entry_time'])} / ${p['entry']:,.4f} | ${c['reentry']['entry_reference']:,.4f} / {c['reentry']['decision']} | {p['status']}；已平仓净额{p['net']}，历史标记净额${p.get('marked_net',0):,.2f} |")
    p=next(p for p in case['models']['0.1']['retained']['trades'] if p['entry_time']=='2026-11-15T06:44:00Z')
    lines += ['',
        f"01:44重入的父D为$61,991.3285，HL为01:10的$64,137.90（01:30确认）；原五分钟守稳和突破检查通过。初始止损${p['initial_stop']:,.4f}，第一25%目标${p['t1']:,.4f}。截至案例cutoff 11/15 05:16 EST，最后观察分钟为{clock(p['mark_time'])}，真实参考收价${p['mark_price']:,.4f}；仍未触及目标或触发退出，不能把标记浮盈${p['marked_net']:,.2f}当成已实现利润。它也不是当前报价。",'',
        '03:20的新HL为02:51的$63,735.105，03:15完整结构确认。03:15–03:20五分钟守稳低$63,834.15、高$63,948.505，03:20分钟高越过$63,948.515。该分钟不早于03:21完整，原始观察03:21:14收到。各模型严格截在03:20分钟的独立前缀，均复现同一合格但held_position的候选，没有后来价格或替代成交。',
        '本例首次退出及其亏损仍原样保留。没有过滤01:44去强行制造03:20成交，也没有新增仓位叠加或延迟持仓候选的成交。',
        '', '## 同一30天组合净额','',
        '| 退出模型 | 原A/B | 原PH5加A/B | 保留背景PH5加A/B | 对原PH5差额 | 原PH5→保留笔数 |',
        '| --- | ---: | ---: | ---: | ---: | --- |']
    for m,modes in s['summaries'].items():
        o=modes['original']['all'];c=modes['cleared_combined']['all'];r=modes['retained_combined']['all']
        lines.append(f"| {m} | ${o['net']:,.2f} | ${c['net']:,.2f} | ${r['net']:,.2f} | ${r['net']-c['net']:,.2f} | {c['entries']} → {r['entries']} |")
    lines += ['',
        '净额按每笔初始1 BTC、原2bps每边价差滑点代理计算，是已平仓模拟净额，不是实际BTC/ETF成交、实际加密交易费或账户复利。全部月度交易已在窗口内平仓；窗口外案例浮盈不计入月份。原A/B仍优于三个组合实验。',
        '', '## 完整组合与单独PH5结果及回撤','',
        '| 模型 / 序列 | 笔数 / 胜 / 负 / 未平仓 | 已平仓净额 | 已平仓美元回撤 | 已平仓R回撤 | 平均初始风险USD |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for m,modes in s['summaries'].items():
        for q,v in modes.items():
            _,_,r=PARENT_MEMORY_VIEW.selection(m,q);a=v['all'];risk=sum(p['initial_risk'] for p in r['trades'])/len(r['trades']) if r['trades'] else 0
            lines.append(f"| {m} / {q} | {a['entries']} / {a['wins']} / {a['losses']} / {a['open']} | ${a['net']:,.2f} | ${dollar_drawdown(r['trades']):,.2f} | {a['max_drawdown_r']:.3f} | ${risk:,.2f} |")
    lines += ['',
        '保留更深的父D会扩大推导出的止损距离，并可能改变目标与1R退出启动；这来自不同的背景输入，计算公式和阈值没有变。R的分母随之变大，所以R回撤下降不能单独证明美元风险更低。对照同时给出美元回撤；这两类回撤按已平仓交易累积计算，均不是含持仓浮亏的逐分钟账户权益回撤。',
        '', '## 缺口分组','',
        '无标记缺口=持仓无观察缺口且入场前14根15分钟完整相邻；标记组为其互补。它不证明全部更早阻力背景完整。缺失观察不插值、不补齐、不带价跨越。',
        '', '| 模型 / 序列 | 无标记缺口净额 | 标记缺口或入场背景不完整净额 |', '| --- | ---: | ---: |']
    for m,modes in s['summaries'].items():
        for q,v in modes.items():lines.append(f"| {m} / {q} | ${v['no_flagged_gap']['net']:,.2f} | ${v['gap_or_partial_context']['net']:,.2f} |")
    lines += ['', '## 顺序变化与解释','']
    for m,variants in s['changes'].items():
        for q,c in variants.items():
            x=c['vs_cleared'];lines.append(f"- {m} / {q}：新增{len(x['added'])}笔，原交易未再采用{len(x['baseline_entries_not_taken'])}笔，同入场时点改变{len(x['changed_same_entry'])}笔。")
    lines += ['',
        '保留背景使更多后续回踩被视为旧D上的HL，也扩大部分单笔风险。不同退出模型因此有不同持仓与新买点序列，E1新增交易尤其多。这里只报告状态改变的完整后果，不把局部案例成功或R回撤下降解释为整体改善。该月已多次用于研究，属于样本内比较，不是独立验证。没有因结果好坏再次调参。',
        '', '## 交易桌审查与保留','',
        '页面分别展示旧、新案例、03:20候选与01:44持仓、每根状态变化、15组月度结果及缺口分组。逐笔可查入场、父D/HL、初始止损、25%目标及实际卖出、余仓/全仓退出时间价格净额、五分钟入场数据、完整15分钟事件和与原PH5的顺序变化。TRADES/EXITS/PROTECTION/SIGNALS/LEDGER CSV和结果JSON可下载。页面GET只读，不启动回放或worker，不请求新报价，不含订单操作。',
        f"研究路径 `{folder}`。原{s['preservation']['files']}个保护文件及{s['PH5_preserved_files']}个PH5文件哈希不变；原worker PID {s['preservation']['pid']}、session `{s['preservation']['session']}`保持不变。原0.2包、原PH5 ACTIVE及研究、P1和原研究选择器均未覆盖。只更新独立parent_memory_studies选择器。",'',
        '实现：trading_desk/btc_parent_memory.py只增加背景保留/买点边界适配；仓位初始化仍调用原PH5所用基类，退出、目标和风险方法直接继承。缺口仍清空背景。新增回归覆盖首次退出不变、严格前缀、03:20持仓阻止重复成交、D/HL单次使用、可用HL边界、真实数据、成本和只读HTTP。']
    text='\n'.join(lines)+'\n';(folder/'REPORT.md').write_text(text)
    dest=ROOT/'docs/investigations/2026-11-15_BTC_PARENT_MEMORY_COMPARISON.md';dest.write_text(text);print(dest)


if __name__=='__main__':run()
