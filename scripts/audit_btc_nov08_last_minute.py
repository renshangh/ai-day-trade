"""Verify one last-minute full-exit observation using archived real 1m bars.

Uses the 08:29 minute's first trade and only the fourteen already-completed
minutes. Its own final high/low/close never enter the trigger calculation.
No broker clients, orders, monthly replay or synthesized observations.
"""
import hashlib
import json
import math
from pathlib import Path

from audit_btc_nov07_parent_swing import trace_parent
from btc_structure_retest import Config, STEP, local, reward_risk
from clarify_btc_nov07_structure import leg_pnl
from clarify_btc_oct11_structure import stamp
from retest_btc_major_resistance import load_source


def load_minutes(folder):
    meta=json.loads((folder/'SOURCE.json').read_text())
    payload=(folder/'COINBASE_BTCUSD_1M_RAW.json').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=meta['sha256']:
        raise ValueError('Minute raw-response hash changed')
    if meta['granularity_seconds']!=60 or meta['http_status']!=200:
        raise ValueError('Not a successful one-minute source response')
    rows=[];seen=set()
    for t,low,high,opening,close,volume in json.loads(payload):
        if t in seen or int(t)!=t or t%60:
            raise ValueError('Duplicate or unaligned real minute timestamp')
        seen.add(t)
        if not all(math.isfinite(x) for x in (low,high,opening,close,volume)):
            raise ValueError('Nonfinite minute value')
        if not 0<low<=min(opening,close)<=max(opening,close)<=high or volume<0:
            raise ValueError('Invalid minute OHLCV')
        rows.append(dict(t=t,open=opening,high=high,low=low,close=close,volume=volume))
    return meta,sorted(rows,key=lambda b:b['t'])


def target_minutes(rows,start):
    selected=[b for b in rows if start<=b['t']<start+STEP]
    if [b['t'] for b in selected]!=list(range(start,start+STEP,60)):
        raise ValueError('Missing real minute observations; never fill gaps')
    return selected


def snapshot_at_minute_open(prefix,price,minute_t,signal_start,opening,previous_high,previous_close,
                            watch_level=76000.0,minimum_wick_fraction=.5):
    if not prefix or any(b['t']+60>minute_t for b in prefix):
        raise ValueError('Prefix must contain only already-completed minute bars')
    h=max(price,max(b['high'] for b in prefix));lo=min(price,min(b['low'] for b in prefix))
    wick=h-max(opening,price);span=h-lo
    in_window=signal_start+STEP-60<=minute_t<signal_start+STEP
    ratio=wick/span if span>0 else None
    shape=bool(ratio is not None and ratio>=minimum_wick_fraction and price<watch_level
               and previous_close>=watch_level and h>previous_high)
    return dict(observation_minute_start_ny=local(minute_t),observation_minute_end_ny=local(minute_t+60),
        precision='First trade in this minute bucket; exact trade second is not returned',
        in_last_minute=in_window,shape_condition=shape,trigger=in_window and shape,
        last_closed_minute_end_ny=local(prefix[-1]['t']+60),
        current_price_reference=price,known_high=h,known_low=lo,opening_15m=opening,
        upper_wick=wick,range=span,upper_wick_fraction=ratio,watch_level=watch_level,
        used_current_minute_final_high_low_close=False)


def review(root):
    folder=root/'entry_examples/minute_rejection_2026_11_08'
    meta,raw_minutes=load_minutes(folder)
    start=stamp('2026-11-08T08:15:00-05:00')
    minutes=target_minutes(raw_minutes,start)
    _,bars,_,end=load_source(root)
    parent=next(b for b in bars if b['t']==start)
    previous=next(b for b in bars if b['t']==start-STEP)
    rollup=dict(open=minutes[0]['open'],high=max(b['high'] for b in minutes),
        low=min(b['low'] for b in minutes),close=minutes[-1]['close'],volume=sum(b['volume'] for b in minutes))
    if any(rollup[k]!=parent[k] for k in ('open','high','low','close')) or not math.isclose(rollup['volume'],parent['volume'],abs_tol=1e-8,rel_tol=1e-12):
        raise ValueError('1m data do not reproduce the archived 15m candle; do not mix them')
    window=start+STEP-60
    minute=next(b for b in minutes if b['t']==window)
    prefix=[b for b in minutes if b['t']<window]
    observed=snapshot_at_minute_open(prefix,minute['open'],window,start,minutes[0]['open'],previous['high'],previous['close'])
    old=json.loads((root/'entry_examples/NOV07_USER_STRUCTURE.json').read_text())
    frozen=json.loads((root/'major_resistance/MAJOR_RETEST.json').read_text())['runs'][1]
    cfg=Config(**frozen['config'])
    atr={stamp(b['start_utc'])+STEP:b['atr'] for b in frozen['ledger']}
    at=stamp(old['entry_interval_start_ny'])
    initial_d=old['anchors']['L1']
    stop=initial_d['low']-cfg.stop_buffer_atr*atr[at]
    # Only initial protection changes to the previous D. Later promotion still
    # requires a new same-level low after the already-existing entry L2.
    protection=trace_parent(bars,atr,at,old['anchors']['L2'],stop,
        old['target1_reference'],old['next_target_reference'],old['primary_supply_zone']['lower'],cfg,end)
    earlier_fills=[e for e in protection['events'] if e['fraction_initial']>0
                   and stamp(e['interval_start_ny'])<window]
    if earlier_fills:
        raise ValueError('Earlier exits exist; cannot assume the entire original position remains')
    active=next(b for b in protection['rows'] if stamp(b['start_ny'])<=window<stamp(b['end_ny']))
    if not observed['trigger']:
        pnl=None
    else:
        pnl=leg_pnl(old['entry_reference'],observed['current_price_reference'],1.0,cfg.one_way_friction_bps)
    minute_rows=[dict(start_ny=local(b['t']),end_ny=local(b['t']+60),
        **{k:b[k] for k in ('open','high','low','close','volume')},
        role='last-minute first-trade observation; final HLC excluded from trigger' if b['t']==window
             else 'completed before last-minute observation') for b in minutes]
    return dict(scope='Only the Nov 8 08:15--08:30 candle and this nominated trade; no monthly rerun',
        source=meta,source_venue='Coinbase BTC-USD; kept consistent with the original chart',
        source_rollup_matches_archived_15m=True,rollup=rollup,
        signal_start_ny=local(start),signal_end_ny=local(start+STEP),
        eligible_window_start_ny=local(window),eligible_window_end_exclusive_ny=local(start+STEP),
        observed_trigger=observed,
        entry_start_ny=old['entry_interval_start_ny'],entry_end_ny=old['entry_interval_end_ny'],
        entry_reference=old['entry_reference'],initial_d_start_ny=initial_d['start_ny'],
        initial_d_price=initial_d['low'],initial_stop_reference=stop,
        original_entry_l2_price=old['anchors']['L2']['low'],
        protection_updates=protection['events'],active_structural_stop_at_observation=active['active_stop'],
        unchanged_first_target=old['target1_reference'],
        initial_net_reward_risk=reward_risk(old['entry_reference'],stop,old['target1_reference'],cfg.one_way_friction_bps),
        exit_fraction=1.0 if observed['trigger'] else 0.0,model_pnl_per_initial_btc=pnl,
        execution_basis='Observed minute first-trade price as a paper reference, not a bid/ask quote or confirmed order fill',
        cost_basis='ETF zero-commission learning assumption plus unchanged 2bps per side friction; not an Alpaca crypto fee model',
        minutes=minute_rows)


def report_text(r):
    o=r['observed_trigger'];p=r['model_pnl_per_initial_btc']
    lines=['# BTC 08:29最后一分钟：盘中长上影全退复核','',
        '用同场所真实1分钟行情验证最后一分钟首个可观察价格，不借用本分钟最终K线。','',
        '**Last Updated:** 2026-11-08','',
        '**Status:** 单根复核完成；一分钟首笔观察点满足条件，秒级触发与订单成交未验证','',
        '**Audience:** 交易学习手册使用者与维护者','', '## Overview','',
        '用户将“临近结束”明确为最后1分钟：**2026年11月8日纽约时间08:29:00至08:30:00（不含）**。'
        '当前信号触发后退出全部剩余仓位，不等15分钟收盘。本例固定目标76,118.18未到，仍为原始100%。','',
        '本次继续使用Coinbase BTC-USD，避免把另一个场所价格拼接到旧图。'
        '15根真实1分钟K线完整连续，合并O/H/L/C及成交量17.20151920均与原归档15分钟K线一致。'
        '原API响应和来源哈希保存在本报告对应的数据目录；没有填补、插值或生成行情。','',
        '## 最后一分钟首个观察点','',
        f"08:15–08:28共14根完整分钟K线在08:29时均已结束。此前已知最高**{o['known_high']:,.2f}**、"
        f"最低**{o['known_low']:,.2f}**，15分钟开盘**{o['opening_15m']:,.2f}**。"
        f"08:29这一分钟的首笔成交价为**{o['current_price_reference']:,.2f}**。",'',
        f"当时上影＝{o['known_high']:,.2f}−max({o['opening_15m']:,.2f}, {o['current_price_reference']:,.2f})＝**{o['upper_wick']:.2f}**；"
        f"振幅＝**{o['range']:.2f}**；上影占**{o['upper_wick_fraction']:.2%}**。"
        '同时现价低于76,000，前一根完整15分钟已收在76,000上方，且此前本根已超过前根高76,017.37。'
        '**因此最后一分钟的首个可观察成交点已满足本次条件，可以参考该点全退100%。**','',
        '这不等于证明成交发生在08:29:00整。Coinbase分钟时间戳标记桶起点，open是桶内第一笔成交价格，'
        '响应不提供那一笔的精确秒数或可成交买卖报价。正确记录是**08:29分钟首笔观察点**；'
        '不补写08:29:00整成交，也不声称订单已成交。评估没有使用08:29分钟最终高、低、收或08:30下一分钟开盘。','',
        '## 本笔统一时间与盈亏','',
        '全部纽约时间EST（UTC−5），按初始1 BTC折算。支撑参考与缓冲后的止损价分列。','',
        '| 事件 | 触发／生效时间 | 结构参考低点 | 价格／保护参考 | 仓位 | 模拟退出毛／净盈亏 |',
        '| --- | --- | ---: | ---: | --- | --- |',
        '| 入场 | 2026-11-07 21:30–21:45内；秒数未知 | 入场L2 75,545.34 | **75,650.00** | 100% | — |',
        f"| 初始保护 | 假设入场成交后立即 | 前D **{r['initial_d_price']:,.2f}**，2026-11-07 16:30–16:45 | **{r['initial_stop_reference']:,.5f}** | 全部剩余仓位 | — |"]
    for e in r['protection_updates']:
        if e['reason']=='raise_parent_stop':
            lines.append(f"| 同级低点上移保护 | {e['effective_from_ny'][:16].replace('T',' ')}起 | "
                f"{e['reference_low']:,.2f} | **{e['price_reference']:,.5f}** | 全部剩余仓位 | — |")
    lines += [f"| 盘中长上影全退 | **2026-11-08 08:29分钟首笔观察点**；精确秒数未知 | "
        f"观察阻力76,000；结构保护{r['active_structural_stop_at_observation']:,.2f} | **{p['exit_reference']:,.2f}**首笔成交观察价 | **100%** | **+${p['gross_pnl']:.2f}／+${p['net_pnl']:.2f}** |",'',
        f"模拟毛盈亏＝{p['exit_reference']:,.2f}−75,650＝**+${p['gross_pnl']:.2f}**。"
        f"按原每边2bps价差／滑点，往返估计摩擦为**${p['assumed_roundtrip_friction']:.6f}**，"
        f"模拟净盈亏为**+${p['net_pnl']:.6f}**。这里没有25%/75%分批退出；普通目标没有触发。",'',
        '该价格是成交历史的观察参考，不是当时买一价，更不是提交、撮合或实际成交记录。'
        '上述成本沿用ETF零佣金学习模型；不能据此宣称BTC现货交易或Alpaca paper的实际净收益。'
        f"更宽的前D初始保护下，原固定目标净收益／风险仍约{r['initial_net_reward_risk']:.2f}倍，"
        '未通过原净2倍门槛。本例是已知案例的执行教学复核，不倒改筛选标准或整月结果。','',
        '## 逐分钟原始读数','',
        '| 开始（11/8纽约） | 结束 | 开 | 高 | 低 | 收 | 在08:29观察时的作用 |',
        '| --- | --- | ---: | ---: | ---: | ---: | --- |']
    for b in r['minutes']:
        role='只使用首笔open；本分钟最终H/L/C不用于触发' if b['start_ny']==r['eligible_window_start_ny'] else '此前已完成'
        lines.append(f"| {b['start_ny'][11:16]} | {b['end_ny'][11:16]} | {b['open']:,.2f} | {b['high']:,.2f} | "
            f"{b['low']:,.2f} | {b['close']:,.2f} | {role} |")
    lines += ['', '## 来源与复现','',
        '[Coinbase分钟桶与open定义](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)；'
        '[归档来源与哈希](../../reports/btc_structure_2026_11_08/entry_examples/minute_rejection_2026_11_08/SOURCE.json)；'
        '[单例JSON](../../reports/btc_structure_2026_11_08/entry_examples/minute_rejection_2026_11_08/LAST_MINUTE_AUDIT.json)。',
        '', '运行`scripts/audit_btc_nov08_last_minute.py`只读取归档并生成该单例报告，不发请求、不导入broker client，'
        '也不修改原月度数据、微观退出、同级保护对照或10月11日案例。','']
    return '\n'.join(lines)


def main():
    root=Path('reports/btc_structure_2026_11_08')
    result=review(root)
    folder=root/'entry_examples/minute_rejection_2026_11_08'
    (folder/'LAST_MINUTE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    Path('docs/investigations/2026-11-08_BTC_LAST_MINUTE_REVIEW.md').write_text(report_text(result))
    print(json.dumps({k:result[k] for k in ('observed_trigger','exit_fraction','model_pnl_per_initial_btc')},ensure_ascii=False))


if __name__=='__main__':
    main()
