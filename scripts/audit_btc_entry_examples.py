"""Audit two user-nominated intrabar examples; never changes the frozen replay.

Price-trigger tests are distinct from full setup/RR eligibility. Conditional
exit traces illustrate existing rules only; no trades/PnL enter the backtest.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from btc_structure_retest import Config, MajorResistance, STEP, exit_intrabar, iso, local, reward_risk, write_csv
from retest_btc_major_resistance import load_source


def ts(value):
    return int(datetime.fromisoformat(value).timestamp())


CASES=[
    dict(name='OCT11',entry_start='2026-10-11T10:00:00-04:00',
         context_start='2026-10-11T08:00:00-04:00',review_end='2026-10-11T12:30:00-04:00'),
    dict(name='NOV07',entry_start='2026-11-07T21:30:00-05:00',
         context_start='2026-11-07T19:30:00-05:00',review_end='2026-11-08T08:45:00-05:00')]


def confirmed_lows(bars, known_at):
    output=[]
    for i in range(1,len(bars)-1):
        a,p,c=bars[i-1:i+2]
        if c['t']+STEP>known_at:
            break
        if c['t']==p['t']+STEP and p['t']==a['t']+STEP and p['low']<a['low'] and p['low']<c['low']:
            output.append(dict(t=p['t'],price=p['low'],known_at=c['t']+STEP))
    return output


def conditional_path(bars, before_atr, entry_at, entry, stop, target1, target2, resistance, cfg):
    """Not eligible-trade replay: no eligibility bypass is counted as a trade.

    Copy existing exit conventions solely to explain the nominated price path.
    """
    p=dict(entry=entry,stop=stop,t1=target1,t2=target2,remaining=1.0,trimmed=False,pending_weak_exit=False)
    events=[]
    for i,b in enumerate(bars):
        if b['t']<entry_at:
            continue
        if p['pending_weak_exit']:
            events.append(dict(interval_start_ny=local(b['t']),reason='wick_failure_next_open',
                               price_reference=b['open'],fraction_initial=p['remaining'],time_basis='next actual open model'))
            return events
        for reason,price,fraction in exit_intrabar(p,b):
            events.append(dict(interval_start_ny=local(b['t']),interval_end_ny=local(b['t']+STEP),
                               reason=reason,price_reference=price,fraction_initial=fraction,
                               time_basis='15m interval only; not a verified fill'))
            p['remaining']=round(p['remaining']-fraction,8)
            if p['remaining']==0:
                return events
            if reason=='target1':
                p['trimmed']=True
        # Exactly as in the existing exit model: a newly known pivot can move
        # protection upward at this close, effective on the following bar only.
        if p['trimmed'] and i>=2:
            a,pivot,c=bars[i-2:i+1]
            atr=before_atr.get(b['t']+STEP)
            if atr and pivot['low']<a['low'] and pivot['low']<c['low']:
                proposed=pivot['low']-cfg.stop_buffer_atr*atr
                if proposed<b['close'] and proposed>p['stop']:
                    p['stop']=proposed
                    events.append(dict(known_at_ny=local(b['t']+STEP),effective_from_ny=local(b['t']+STEP),
                                       reason='raise_protection',price_reference=proposed,fraction_initial=0))
        span=b['high']-b['low'];wick=b['high']-max(b['open'],b['close'])
        if span>0 and b['high']>=resistance and wick/span>=cfg.upper_wick_fraction and b['close']<resistance:
            p['pending_weak_exit']=True
    return events


def audit(root):
    _,bars,_,_=load_source(root)
    path=root/'major_resistance/MAJOR_RETEST.json'
    frozen=json.loads(path.read_text())['runs'][1]
    cfg=Config(**frozen['config'])
    lookup={b['t']:b for b in bars}
    ledger={ts(x['start_utc']):x for x in frozen['ledger']}
    atr_before={t+STEP:x['atr'] for t,x in ledger.items()}
    cases=[]
    for spec in CASES:
        at=ts(spec['entry_start']);prev=lookup[at-STEP];bar=lookup[at]
        atr=atr_before[at]
        # One cent above the recorded high is an arithmetic illustration, not
        # a new optimized buffer or a claim about an actual tradable fill.
        entry=round(prev['high']+.01,2)
        stop=prev['low']-cfg.stop_buffer_atr*atr
        clock=MajorResistance(cfg)
        for b in bars:
            if b['t']+STEP<=at:
                clock.observe(b)
        zones=clock.zones(entry,at)
        t1=zones[0]['lower']-cfg.target_buffer_atr*atr if zones else None
        t2=zones[1]['lower']-cfg.target_buffer_atr*atr if len(zones)>1 else None
        ratio=reward_risk(entry,stop,t1,cfg.one_way_friction_bps) if t1 else None
        lows=confirmed_lows(bars,at)
        higher_low=prev['low']>lows[-1]['price']+cfg.min_higher_low_atr*atr
        row=dict(**spec,previous_complete_bar=prev,entry_bar=bar,price_crossed=bar['high']>prev['high'],
                 candidate_entry_reference=entry,entry_time_basis='within nominated 15m interval, exact tick/fill unknown',
                 atr_known_before_entry=atr,atr_known_at_ny=local(at),candidate_low=prev['low'],
                 candidate_stop=stop,latest_previously_confirmed_micro_low=lows[-1],
                 higher_low_relative_to_latest_micro_low=higher_low,
                 candidate_low_first_confirmable_ny=local(at+STEP),
                 t1=t1,t2=t2,resistance_zones=zones[:2],net_reward_risk=ratio,
                 passes_rr=bool(ratio is not None and ratio>=cfg.min_reward_risk),
                 passes_same_micro_anchor_and_rr=higher_low and bool(ratio is not None and ratio>=cfg.min_reward_risk),
                 frozen_decision_on_entry_bar=ledger[at]['decision'],
                 frozen_decision_just_before_entry=ledger[at-STEP]['decision'])
        sample=[b for b in bars if at<=b['t']<ts(spec['review_end'])]
        row['first_candidate_stop_touch_ny']=next((local(b['t']) for b in sample if b['low']<=stop),None)
        row['first_t1_trade_through_ny']=next((local(b['t']) for b in sample if t1 and b['high']>t1),None)
        row['conditional_exit_trace_not_backtest']=conditional_path(bars,atr_before,at,entry,stop,t1,t2,zones[0]['lower'],cfg)
        if spec['name']=='NOV07':
            row['classroom_75990_first_trade_through_ny']=next((local(b['t']) for b in sample if b['high']>75990),None)
            row['user_proposed_exit_time_ny']='2026-11-08T08:15:00-05:00'
        rows=[]
        for b in bars:
            if not ts(spec['context_start'])<=b['t']<ts(spec['review_end']):
                continue
            p=lookup[b['t']-STEP]
            rows.append(dict(start_ny=local(b['t']),end_ny=local(b['t']+STEP),
                             open=b['open'],high=b['high'],low=b['low'],close=b['close'],
                             previous_completed_high=p['high'],intrabar_price_cross=b['high']>p['high'],
                             close_above_previous_high=b['close']>p['high'],
                             atr_available_at_bar_start=atr_before.get(b['t']),
                             nominated_entry_bar=b['t']==at,candidate_stop=stop if b['t']>=at else None,
                             candidate_t1=t1 if b['t']>=at else None,
                             frozen_decision=ledger[b['t']]['decision']))
        row['bars']=rows
        cases.append(row)
    return dict(scope='Two-example diagnostic; existing configuration, baseline trades, workbook and monthly results unchanged.',
                fill_warning='Price crossed does not prove order fill. Candidate exits are conditional illustrations for rejected entries, not new strategy trades.',
                frozen_report_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),config=frozen['config'],cases=cases)


def write_report(root,result):
    text='''# BTC两个盘中入场例子的逐根核对

核对用户指出的价格触发、已知止损与现有退出规则，不改其他参数或整月结果。

**Last Updated:** 2026-11-08

**Status:** 两例诊断完成；没有修改策略、原工作簿或月度回测

**Audience:** 交易桌使用者与维护者

## Overview

本次唯一采用的新入场口径是：**盘中价格超过前一根已完成十五分钟K线的含影线最高价，不等当前K线收盘。**
两根指定K线均出现价格触发；然而原有微观L1/L2识别和最近重要小时阻力下的2倍净收益风险筛选仍不通过。
因此不把它们写成新增的合格交易，不修改原十笔模拟结果。条件退出路径只用于说明：
假定已经另行获准入场，原退出机制会怎样处理该段真实价格路径。

沿用原参数：L2下方0.25个十五分钟ATR缓冲；T1取最近已知小时阻力区下沿减0.10个十五分钟ATR；
2倍净收益风险门槛；每边2bps假设价差/滑点；T1卖初始50%，余下按T2、上移结构保护或既有影线失败条件退出。
ATR周期仍为14根真实波幅简单平均。改成盘中触发后，只能使用触发前已完成K线的ATR，不能偷用当前K线最终ATR。

价格为Coinbase BTCUSD归档真实读数。时间采用America/New_York：10月11日为EDT，11月7–8日为EST。
前高上方一美分仅作金额核算参考，不是新增优化参数或保证成交价；OHLC只能确定触价区间，不能确定秒数、路径顺序或挂单成交。

## 一 10月11日10:00–10:15

**后续结构澄清：**用户已明确该例按D低点82,869.45下方的82,865保护较大波段。
本节82,931.40仅保留为旧微观核算，不是用户澄清后的止损方案；见
[10月11日D结构澄清](2026-11-08_BTC_OCT11_STRUCTURE_CLARIFICATION.md)。

| 项目 | 当时已知数据或条件核算 |
| --- | --- |
| 前一根完整K线 | 09:45–10:00；H 83,017.48，L 82,949.22 |
| 盘中破高参考 | 高于83,017.48；算术参考E=83,017.49 |
| 指定K线 | 10:00–10:15；H 83,025.06，C 82,992.78 |
| 触发时点 | 10:00–10:15内；具体时刻未知。当前收盘规则不会确认，但盘中规则有价格触发 |
| 触发前ATR | 09:45–10:00完成后已知：71.2742857 |
| 以前一根回踩低点核算的止损 | 82,949.22−0.25×71.2742857＝**82,931.40** |
| 原小时阻力区 | **83,049.55–83,115.80**，当时已经确认 |
| 按原阻力规则计算T1 | **83,042.42**；T2约83,113.15 |
| 原成本下净收益/风险 | **约−0.069倍**；目标价差约24.93，不足覆盖约33.21的往返摩擦，更达不到2倍 |

这里的低点82,949.22是为核对用户指向的前一根回踩K线而作的候选结构，**不是原程序当时已经认定的合格L2**。
原程序最近确认的微观低点是09:00–09:15的82,980.01；09:45这次低点更低，旧结构已被判失效。
它没有自动把更早、更大波浪的低点改作L1。不得为了让这个例子通过而回头选择一个更远L1或跳过近阻力。

**条件价格路径，不能计入策略交易：**

- 10:00–10:15最高越过参考入场，且最低82,977.72高于候选止损；本根不碰该止损。
- 10:15–10:30最低**82,929.08**，低于候选止损约**2.32**；最高83,029.62仍未到T1。
  假定此前已成交，原保护会在这一根内退出全部，而不会保留到后面的强涨。
- 10:30–10:45才首次越过候选T1，已经晚于上述止损区间。
- 后来11:30和11:45两根大幅上涨，不能据此回头移动10:00本来应设的止损。

原模型最终在12:00以83,818.51入场，其依据是后续新形成的微观更高低点及收盘突破。
这笔原模型交易与用户指出的早期机会，入场阶段、结构锚点和价格都不同；不是同一笔订单简单晚报了时间。

## 二 11月7日21:30–21:45及11月8日08:15

**后续单例澄清：**用户已选择与10月11日相同的较大波段目标约76,118，采用25%/75%及创新高后重算保护的口径。
本节50%/50%、近端目标及旧退出仅保留为历史解释，不代表新版条件路径；见
[11月7日结构与盈亏澄清](2026-11-08_BTC_NOV07_STRUCTURE_CLARIFICATION.md)。

| 项目 | 当时已知数据或条件核算 |
| --- | --- |
| 前一根完整K线 | 21:15–21:30；H **75,649.99**，L **75,545.34**，C 75,622.14 |
| 盘中破高参考 | 高于75,649.99；算术参考E=**75,650.00** |
| 指定K线 | 21:30–21:45；O 75,622.14，H **75,652.28**，L 75,570.85，C **75,579.84** |
| 触发时点 | 21:30–21:45内；具体时刻未知。盘中过前高，但收盘又退回，旧收盘规则不确认 |
| 75,624的区别 | 靠近本根开盘/实体上沿75,622.14，**低于前一根最高75,649.99**，不能作为本次含影线破高的入场价 |
| 触发前ATR | 21:15–21:30完成后已知：65.0457143 |
| 候选结构止损 | 75,545.34−0.25×65.0457143＝**75,529.08** |
| 原最近小时阻力区 | **75,766.06–75,836.14**，入场前已确认 |
| 按原阻力规则计算T1 | **75,759.55**；T2约**76,118.18** |
| 原成本下净收益/风险 | **约0.524倍**，不满足原2倍门槛 |

原程序最近确认的微观低点为19:30–19:45的75,608.82；21:15这次75,545.34更低，不会按原算法被选成更高L2。
如果用户看的是更大的同级波浪，需要先明确并固定那个L1，不能在看到次日上涨后挑一个最合适的早期低点。

**仅用于说明原退出机制的条件路径，不是新增成交或盈利回测：**

| 时段/完成时点 | 条件处理或观察 |
| --- | --- |
| 11/7 21:30–21:45 | 盘中过75,649.99；最低仍高于75,529.08，未触候选初始止损 |
| 22:00–22:15 | 首次严格越过原T1 75,759.55；若此前另有合法持仓，原方案在这里处理初始50% |
| 22:15以后 | 本次回踩低点已被后续完整K线确认，按旧规则上移剩余保护；该次候选保护75,547.28 |
| 23:00以后 | 已确认22:30回踩低点，剩余保护上移到75,686.44 |
| 11/8 00:15以后 | 新完整确认低点，保护上移到**75,700.43** |
| 00:30–00:45 | 触及这条移动保护；假定的剩余50%在该区间已按原规则退出 |
| 08:00–08:15 | H 76,017.37，C 76,015.63；是旧教学T1 75,990首次被越过的区间，但并非V1.2的首个目标区间 |
| 08:15–08:30 | H 76,094.99，C 75,956.19；长上影及收回76,000以下，要到**08:30**才能完整确认 |

所以，在不改原目标和移动保护的前提下，不能把08:15直接写为这笔持仓的首次或最终退出：
按照上述条件路径，该仓位早已分两次退出。若希望保留到次日08:15，需要另行对齐目标/结构保护的级别与持有目标；本次不作调整。
此前讨论过的76,000/75,990教学阻力不能用来悄悄替换本次“最近小时阻力区”的机械规则。
即便在单独采用教学T1的情景里，也只能说08:00–08:15内越价，不能证明精确08:15成交。

## 程序漏掉价格触发的具体原因

1. **时机不同：**现有replay检查`close > setup.trigger`，并在下一根开盘模型入场；并非盘中`price > previous_complete_bar.high`。
   两根指定K线都是“最高超过前高、收盘未过前高”，所以这项差异确实会漏掉价格触发。
2. **波浪结构不同：**程序只用最近一次确认的微观低点作为L1，并等待低点右侧一根完整K线才承认L2。
   在指定盘中时点，用户指向的前一根低点尚未通过该确认，而且相对最近微观L1更低。
   更大波浪的更高低点与这种相邻微观低点比较不能混为一谈。
3. **触发参照不同：**程序确认L2后，把右侧确认K线的最高价设为trigger，再等后续收盘突破；不是直接对每根当前K线使用前一根完整K线最高价。
   这会进一步推迟信号；只把`close`改成`high`仍不能确保参照的K线和结构级别正确。
4. **其余筛选仍在：**即使先认可用户所指的候选低点并核算盘中入场，原最近小时阻力与2倍净收益风险条件仍拒绝这两个例子。
   价格触发、结构成立、风险收益通过、真实订单成交四件事必须分别记录。

结论：两个例子证实旧程序没有准确实现用户现已明确的价格触发方式，且揭示结构与退出级别仍有定义差异。
但本次不能把它们补成两笔盈利交易；没有修改任何阈值、原交易结果、表格或月度统计。
下一步应先对齐同级L1/L2与目标/保护的含义，而不是为了复现事后走势扩大止损或跳过近阻力。

## 完整逐根记录

下面“盘中过前高”只代表单一价格条件，不表示该根已通过完整入场筛选。
CSV还保留每根开始时可用的ATR、原程序判断、候选保护及目标。数字来自归档真实行情，不含合成K线。
'''
    for c in result['cases']:
        title='10月11日' if c['name']=='OCT11' else '11月7日晚至8日早'
        text+=f'\n### {title}：{len(c["bars"])}根\n\n'
        text+='| 开始 纽约 | 结束 | 开盘 | 最高 | 最低 | 收盘 | 前根最高 | 盘中过前高 |\n| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |\n'
        for b in c['bars']:
            values=[b['start_ny'][:16].replace('T',' '),b['end_ny'][11:16]]
            values += [f'{b[k]:,.2f}' for k in ('open','high','low','close','previous_completed_high')]
            values += ['是' if b['intrabar_price_cross'] else '否']
            text+='| '+' | '.join(values)+' |\n'
    text+='''
## 来源与复核

数据与配置：[两例审计JSON](../../reports/btc_structure_2026_11_08/entry_examples/AUDIT.json)。
[10月11日逐根CSV](../../reports/btc_structure_2026_11_08/entry_examples/OCT11_BARS.csv)，
[11月7日逐根CSV](../../reports/btc_structure_2026_11_08/entry_examples/NOV07_BARS.csv)。
原始源哈希由读取器验证；未重新请求行情。
`scripts/audit_btc_entry_examples.py`只读原月度结果，并在独立目录生成诊断，不连接订单API。
'''
    (root.parents[1]/'docs/investigations/2026-11-08_BTC_INTRABAR_ENTRY_EXAMPLES.md').write_text(text)


def main():
    root=Path('reports/btc_structure_2026_11_08')
    result=audit(root)
    out=root/'entry_examples'
    out.mkdir(exist_ok=True)
    (out/'AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for c in result['cases']:
        write_csv(out/(c['name']+'_BARS.csv'),c['bars'])
        brief={k:c[k] for k in ('name','entry_start','price_crossed','candidate_entry_reference','atr_known_before_entry',
                               'candidate_stop','t1','t2','net_reward_risk','higher_low_relative_to_latest_micro_low',
                               'first_candidate_stop_touch_ny','first_t1_trade_through_ny','conditional_exit_trace_not_backtest')}
        print(json.dumps(brief,ensure_ascii=False))
    write_report(root,result)


if __name__=='__main__':
    main()
