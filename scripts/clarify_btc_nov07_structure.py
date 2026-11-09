"""Audit the nominated November 7 setup, preserving frozen and October data.

The owner explicitly chose the same larger-wave target selection as October
11, not the earlier $75,990 classroom target. Unreached exits stay absent.
"""
import hashlib
import json
from pathlib import Path

from analyze_btc_simulated_trades import aggregate
from btc_structure_retest import Config, MajorResistance, STEP, iso, local, reward_risk
from clarify_btc_oct11_structure import stamp
from retest_btc_major_resistance import load_source


def leg_pnl(entry, exit_price, fraction, bps):
    """Reference P/L per one initial BTC; costs allocated once to each leg."""
    gross=fraction*(exit_price-entry)
    friction=fraction*(entry+exit_price)*bps/10000
    return dict(fraction_initial=fraction,quantity_btc=fraction,
                entry_reference=entry,exit_reference=exit_price,
                gross_pnl=gross,assumed_roundtrip_friction=friction,
                net_pnl=gross-friction)


def trace_case(bars, before_atr, at, peak_bar, initial_stop, target, next_target, resistance, cfg, end):
    """Owner clarified trailing starts after entry, not after first profit.

    Use only completed bars between the prior wave peak and the breakout bar.
    Carry no prospective bar lows/ATR back into a stop. A raised stop takes
    effect on the next real 15m bar. Existing stop wins over targets on ties.
    """
    peak=peak_bar['high'];peak_at=peak_bar['t'];stop=initial_stop
    pullback=[b for b in bars if peak_at<b['t'] and b['t']+STEP<=at]
    events=[];rows=[];remaining=1.0;trimmed=False;pending_weak_exit=False
    for b in bars:
        if not at<=b['t']<end:
            continue
        row=dict(start_ny=local(b['t']),end_ny=local(b['t']+STEP),
            **{k:b[k] for k in ('open','high','low','close')},active_stop=stop,
            previous_wave_high=peak,previous_wave_high_start_ny=local(peak_at),
            new_high=False,reference_low=None,reference_low_start_ny=None,
            proposed_stop=None,new_stop=None,effective_from_ny=None,
            atr_known_at_start=before_atr.get(b['t']),remaining_fraction_start=remaining,
            action='持有；未超过前波峰，不调整止损')
        rows.append(row)
        exit_reason=None
        if pending_weak_exit:
            exit_reason='wick_failure_next_open';price=b['open']
        elif b['low']<=stop:
            exit_reason='stop';price=min(b['open'],stop)
        if exit_reason:
            events.append(dict(interval_start_ny=local(b['t']),interval_end_ny=local(b['t']+STEP),
                reason=exit_reason,price_reference=price,fraction_initial=remaining,
                time_basis='15m interval only; conditional model reference, not verified fill'))
            row['action']=f'触发保护，退出剩余{remaining:.0%}；不是目标止盈'
            return dict(rows=rows,events=events,remaining=0.0,first_target_hit=trimmed)
        if not trimmed and b['high']>target:
            events.append(dict(interval_start_ny=local(b['t']),interval_end_ny=local(b['t']+STEP),
                reason='target1',price_reference=target,fraction_initial=.25,
                time_basis='15m interval only; conditional model reference, not verified fill'))
            remaining=.75;trimmed=True
            row['action']='首次目标止盈25%；剩余75%继续跟踪，止盈本身不移动止损'
        if next_target is not None and b['high']>next_target:
            events.append(dict(interval_start_ny=local(b['t']),interval_end_ny=local(b['t']+STEP),
                reason='target2',price_reference=next_target,fraction_initial=remaining,
                time_basis='15m interval only; conditional model reference, not verified fill'))
            row['action']='下一目标触发，退出当时全部剩余仓位'
            return dict(rows=rows,events=events,remaining=0.0,first_target_hit=True)
        if b['high']>peak:
            row['new_high']=True
            row['action']='盘中创新高；没有已完成的中间回踩则不移动止损'
            if pullback:
                anchor=min(pullback,key=lambda p:p['low'])
                assert anchor['t']+STEP<=b['t']
                atr=before_atr.get(b['t'])
                if atr is None:
                    raise ValueError('Missing actual pre-breakout ATR; no default permitted')
                proposed=anchor['low']-cfg.stop_buffer_atr*atr
                row.update(reference_low=anchor['low'],reference_low_start_ny=local(anchor['t']),proposed_stop=proposed)
                row['action']='盘中创新高，但计算值不高于旧保护位；不下调'
                if stop<proposed<peak:
                    row.update(new_stop=proposed,effective_from_ny=local(b['t']+STEP),
                        action='盘中创新高；以这次回踩低点重算，下一根起上移止损')
                    events.append(dict(reason='raise_after_new_high',fraction_initial=0,
                        breakout_interval_start_ny=local(b['t']),known_at_ny=local(b['t']+STEP),
                        effective_from_ny=local(b['t']+STEP),price_reference=proposed,
                        reference_low=anchor['low'],reference_low_start_ny=local(anchor['t']),
                        atr_known_at_breakout_start=atr))
                    stop=proposed
            peak=b['high'];peak_at=b['t'];pullback=[]
        else:
            pullback.append(b)
        span=b['high']-b['low'];wick=b['high']-max(b['open'],b['close'])
        if span>0 and b['high']>=resistance and wick/span>=cfg.upper_wick_fraction and b['close']<resistance:
            pending_weak_exit=True
            row['action']+='；阻力长上影失败，下一实际开盘退出'
    return dict(rows=rows,events=events,remaining=remaining,first_target_hit=trimmed)


def clarify(root):
    _,bars,_,end=load_source(root)
    frozen_path=root/'major_resistance/MAJOR_RETEST.json'
    frozen=json.loads(frozen_path.read_text())['runs'][1]
    cfg=Config(**frozen['config'])
    lookup={b['t']:b for b in bars}
    atr_before={stamp(r['start_utc'])+STEP:r['atr'] for r in frozen['ledger']}
    at=stamp('2026-11-07T21:30:00-05:00')
    anchors={
        'L1':lookup[stamp('2026-11-07T16:30:00-05:00')],
        'H1':lookup[stamp('2026-11-07T18:45:00-05:00')],
        'L2':lookup[at-STEP],
    }
    assert all(b['t']+STEP<=at for b in anchors.values())
    assert anchors['L2']['low']>anchors['L1']['low']
    entry=round(anchors['L2']['high']+.01,2)
    atr=atr_before[at]
    stop=anchors['L2']['low']-cfg.stop_buffer_atr*atr
    major=MajorResistance(cfg)
    for b in bars:
        if b['t']+STEP<=at:
            major.observe(b)
    zones=major.zones(entry,at)
    h4=[h for h in aggregate(bars,14400) if h['end']<=at]
    # Same pre-entry 4h ranking as October, not the post-entry best-fit peak.
    peaks=[]
    for i in range(2,len(h4)-2):
        p=h4[i]
        if p['t']<at-7*86400:
            continue
        if p['high']>anchors['H1']['high'] and all(p['high']>h['high'] for h in h4[i-2:i]+h4[i+1:i+3]):
            peaks.append(dict(time_utc=iso(p['t']),price=p['high'],known_at_utc=iso(h4[i+2]['end'])))
    if not peaks:
        raise ValueError('No already-confirmed larger-wave target; do not invent one')
    peak=min(peaks,key=lambda p:p['price'])
    zone=next(z for z in zones if any(p['price']==peak['price'] for p in z['members']))
    target=zone['lower']-cfg.target_buffer_atr*atr
    next_zone=next((z for z in zones if z['lower']>zone['upper']),None)
    next_target=next_zone['lower']-cfg.target_buffer_atr*atr if next_zone else None
    path=[b for b in bars if at<=b['t']<end]
    trailing=trace_case(bars,atr_before,at,anchors['H1'],stop,target,next_target,zone['lower'],cfg,end)
    events=trailing['events']
    first=next((e for e in events if e['reason']=='target1'),None)
    exits=[e for e in events if e['fraction_initial']>0]
    pnl=[dict(reason=e['reason'],interval_start_ny=e['interval_start_ny'],
              **leg_pnl(entry,e['price_reference'],e['fraction_initial'],cfg.one_way_friction_bps)) for e in exits]
    last=path[-1]
    remaining_fraction=1-sum(e['fraction_initial'] for e in exits)
    # List every real candle, including ones that do not establish a reference.
    named={b['t']:name for name,b in anchors.items()}
    labels={};running_high=anchors['H1']['high'];high_at=anchors['H1']['t']
    for b in path:
        is_high=b['high']>running_high
        labels[b['t']]=dict(price_new_wave_high=is_high,previous_wave_high=running_high,
                             previous_wave_high_start_ny=local(high_at))
        if is_high:
            running_high=b['high'];high_at=b['t']
    trailing_by_time={stamp(r['start_ny']):r for r in trailing['rows']}
    rows=[]
    for b in bars:
        if not anchors['L1']['t']<=b['t']<end:
            continue
        row=dict(start_ny=local(b['t']),end_ny=local(b['t']+STEP),
                 **{k:b[k] for k in ('open','high','low','close')},
                 structure_label=named.get(b['t'],''),active_stop=None,action='观察；不作为本次入场或退出参考')
        if b['t'] in named:
            row['action']={'L1':'本次较大结构前低参考','H1':'本次较大结构前峰参考',
                           'L2':'候选较大回踩低点；完成后可计算下一根触发价和初始风险'}[named[b['t']]]
        if b['t']>=at:
            row.update(labels[b['t']],action='已整仓退出；本根仅作事后行情观察，不用于本笔收益')
        if b['t'] in trailing_by_time:
            row.update(trailing_by_time[b['t']])
        if b['t']==at:
            row['action']='盘中过前一根完整K线最高价；入场参考75,650.00'
        rows.append(row)
    return dict(scope='November 7 single-case conditional audit, same larger-wave target; no monthly replay.',
        time_zone='America/New_York; EST UTC-5 for all observations',
        source_end_exclusive_ny=local(end),last_complete_bar_start_ny=local(last['t']),
        original_replay_sha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),
        anchors={k:dict(**b,start_ny=local(b['t']),end_ny=local(b['t']+STEP)) for k,b in anchors.items()},
        entry_interval_start_ny=local(at),entry_interval_end_ny=local(at+STEP),
        entry_reference=entry,initial_stop_reference=stop,atr_known_at_entry=atr,
        l2_right_neighbor_first_complete_ny=local(at+STEP),
        initial_stop_basis='completed candidate L2 minus existing 0.25 pre-entry ATR; not an owner-confirmed order',
        larger_resistance_peak=peak,primary_supply_zone=zone,
        intermediate_obstacles=[z for z in zones if z['lower']<zone['lower']],
        target1_reference=target,next_target_reference=next_target,
        net_t1_reward_risk=reward_risk(entry,stop,target,cfg.one_way_friction_bps),
        first_target_interval_start_ny=first['interval_start_ny'] if first else None,
        initial_stop_touched=any(b['low']<=stop for b in path),
        highest_price_since_entry=max(b['high'] for b in path),
        highest_price_while_active=max(b['high'] for b in trailing['rows']),
        minimum_price_since_entry=min(b['low'] for b in path),last_close_reference=last['close'],
        remaining_fraction_initial=remaining_fraction,conditional_exit_trace=events,
        realized_legs_per_initial_btc=pnl,
        realized_gross_total_per_initial_btc=sum(p['gross_pnl'] for p in pnl),
        realized_net_total_per_initial_btc=sum(p['net_pnl'] for p in pnl),
        unrealized_gross_total_per_initial_btc=remaining_fraction*(last['close']-entry),
        hypothetical_first_target_leg_per_initial_btc=leg_pnl(entry,target,.25,cfg.one_way_friction_bps),
        cost_basis='Zero commission; unchanged assumed 2bps per side price friction, not observed ETF execution',
        pnl_normalization='One initial BTC; no actual position or ETF quantity inferred',
        exit_policy=dict(first_profit_fraction=.25,remaining_profit_fraction=.75,
            protective_exit='all currently remaining shares at once; 100% before first profit, 75% afterward',
            trailing_phase='from entry; owner explicitly confirmed no first-target prerequisite',
            new_high='intrabar break of prior wave peak',pullback='completed intervening bars only',
            stop_buffer_atr=cfg.stop_buffer_atr,atr_timing='known before breakout bar',
            stop_effective='next bar',may_lower_stop=False),
        bars=rows)


def write_report(root,result):
    r=result
    lines=['# BTC 11月7日：新高调整保护与整仓止损核对','',
        '止盈保留25%/75%，止损一次退出全部剩余仓位；仅复核第二例，不重跑整月。','',
        '**Last Updated:** 2026-11-08','',
        '**Status:** 单例逐根核对完成；首次止盈前触发上移保护，条件退出100%','',
        '**Audience:** 交易桌使用者与维护者','', '## Overview','',
        '用户明确选择沿用10月11日的较大波段阻力选法，首次目标约$76,118；不切换至此前$75,990课堂目标，'
        '也不采用原微观小时目标$75,759.55来倒造本版的首笔止盈。原始十笔回测、月度工作簿及10月11日例子均不改动。','',
        f"观察截至**{r['source_end_exclusive_ny']}（不含）**，最后一根完整K线为10:45–11:00；不是此后行情的结论。"
        '全部时间采用纽约EST（UTC−5）。源数据与归档API原文哈希及每根价格核验一致，无插值或补齐。','',
        '用户最后明确：**入场后逢新高即可重算保护；盈利兑现仍按25%/75%；止损不分批，'
        '一次退出当时所有剩余仓位**。首次25%未卖时触发止损，退出100%；已卖25%后触发止损，只退出余75%，不能再卖原始100%。'
        '因此撤销此前临时推演中“必须首次止盈后才启用跟踪”和“所有止盈也改成100%”两种误解。','',
        '## L1、L2与入场','',
        '| 标记 | K线时段 | 参考 |','| --- | --- | ---: |',
        '| 较大结构L1 | 11/7 16:30–16:45 | 低点 **75,452.88** |',
        '| H1 | 11/7 18:45–19:00 | 高点 **75,811.88** |',
        '| 候选较大结构L2 | 11/7 21:15–21:30 | 低点 **75,545.34**，高于L1 |',
        '| 入场 | 11/7 21:30–21:45内 | 盘中过前根含影线最高75,649.99；算术参考 **75,650.00** |',
        f"| 初始结构止损参考 | 入场前可计算 | 75,545.34−0.25×{r['atr_known_at_entry']:.7f}＝**{r['initial_stop_reference']:,.5f}** |",'',
        'L1/H1/L2是本次人工较大波浪标注，不把19:30的微观低点75,608.82混作同级L1。'
        'L2 K线21:30已完成，价格与缓冲可用；若坚持左右各一根的严格分形确认，则须等21:45，'
        '不能声称这种确认在21:30已经完成。本版使用此前明确的盘中突破口径，而非旧分形筛选程序。','',
        '此前口述的$75,624低于触发参考75,649.99，不能冒充本版含影线突破的入场价。'
        '价格过高点只证明触发区间，不证明具体秒数、排队或实际成交。','',
        '## 目标与是否产生退出','',
        f"入场前已确认的最近较大四小时波峰为**{r['larger_resistance_peak']['price']:,.2f}**，"
        f"最早可知时间为{local(stamp(r['larger_resistance_peak']['known_at_utc']))}。"
        f"沿用小时区域合并及宽度规则，所属区域为**{r['primary_supply_zone']['lower']:,.2f}–{r['primary_supply_zone']['upper']:,.2f}**。",'',
        f"T1＝区域下沿−0.10×入场前ATR＝**{r['target1_reference']:,.5f}**。"
        f"按原每边2bps摩擦，第一目标净收益/计划风险约**{r['net_t1_reward_risk']:.3f}倍**；"
        '这仅说明该目标价格筛选通过，不验证整体系统或真实执行。近端75,766–75,836区域仍是观察关口，未被当作本波段强制主目标。','',
        f"本笔有效持仓期间最高**{r['highest_price_while_active']:,.2f}**，未到T1。"
        '随后先触发上移保护，所以**没有首次25%止盈，直接退出100%**。止损单可以锁定小幅盈利，不一定形成亏损。','',
        '## 新高与保护价：从入场就开始核对','',
        '- 入场时以已知H1高点75,811.88作为波段新高参考，不把任意上一根小K线高点当作整段新高。',
        '- **22:00–22:15**最高75,830.11，盘中过H1。对应回踩最低为21:15–21:30的75,545.34。'
        '用突破前ATR68.5078571计算：75,545.34−0.25×68.5078571＝75,528.21304。'
        '它低于原保护75,529.07857，所以**只重算，不下调**。',
        '- **22:30–22:45**回踩低点75,704.58先记录为候选，尚未再创新高，不能仅凭该低点立即上移。',
        '- **23:15–23:30**最高75,868.27，超过前波峰75,830.11。取两峰之间已完成K线最低价75,704.58，'
        '减0.25×突破前已知ATR70.5028571，得到**75,686.95429**；按同样复核约定，**23:30起生效**。',
        '- **00:30–00:45**最低75,695.76，未触保护；**00:45–01:00**最低75,688.00，'
        '仍比保护高约1.05美元，不能误写为这一根已经止损。',
        '- **11月8日01:00–01:15**开75,724.73、最低75,656.16，穿过活动保护75,686.95429；'
        '**一次退出100%**。不是先止损25%再等待75%。','',
        '缓冲沿用原0.25 ATR，不用突破K线最终ATR或未完成低点。新保护下一根生效是15分钟OHLC复核约定；'
        '实际保护触发不等收盘，精确秒数及成交滑点无法由这些K线还原。','',
        '02:45以后及08:15的高点属于退出后的行情，不能追加到这笔持仓的盈利里，'
        '也不能把08:15倒写成该笔退出。以后重新入场必须是另一笔单独核对的机会。','',
        '## 本笔盈亏：止损不拆成25%/75%','',
        '按**初始1枚BTC**折算；这是条件模拟，不推定用户实际数量，也不是ETF真实账户盈亏。'
        '零佣金，保留原每边2bps的价差/滑点假设；不重复扣佣金或把未知成交补成已验证成交。','',
        '| 退出时段 | 原始仓位比例 | 入场参考 | 退出参考 | 模拟毛盈亏 | 模拟净盈亏 |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for leg in r['realized_legs_per_initial_btc']:
        lines.append(f"| {leg['interval_start_ny'][5:16].replace('T',' ')}起15分钟内 | {leg['fraction_initial']:.0%} | "
                     f"{leg['entry_reference']:,.2f} | {leg['exit_reference']:,.5f} | **+${leg['gross_pnl']:.2f}** | **+${leg['net_pnl']:.2f}** |")
    lines += ['',
        '每1 BTC毛盈亏＝75,686.9542857−75,650＝**+36.9542857美元**。'
        '估计往返摩擦＝（75,650＋75,686.9542857）×0.0002＝**30.2673909美元**；'
        '模拟净盈亏＝**+6.6868949美元**。成本接近毛收益，实际价差/滑点略有变化就可能变成净亏，不能仅凭“止损价高于买价”宣称实际盈利。','',
        '首次25%目标未成交，故不提供独立的25%止盈或随后75%退出盈亏；'
        '两者只在真正分批退出时分列。此次为一次整仓保护退出，盈亏只列这一笔。','',
        '## 全部逐根记录','',
        '从L1到归档终点共74根真实15分钟K线，逐一列出；没有参考作用的K线明确注明。','',
        '| 开始（纽约） | 结束 | 高 | 低 | 收 | 活动保护 | 标记/判断 |','| --- | --- | ---: | ---: | ---: | ---: | --- |']
    for b in r['bars']:
        label=(b['structure_label']+'；' if b['structure_label'] else '')+b['action']
        active=f"{b['active_stop']:,.5f}" if b['active_stop'] is not None else '—'
        lines.append(f"| {b['start_ny'][5:16].replace('T',' ')} | {b['end_ny'][11:16]} | {b['high']:,.2f} | {b['low']:,.2f} | {b['close']:,.2f} | {active} | {label} |")
    lines += ['', '## 保存与限制','',
        '结构、全部读数、费用假设和条件退出流水保存在'
        '[单例JSON](../../reports/btc_structure_2026_11_08/entry_examples/NOV07_USER_STRUCTURE.json)。'
        '原NOV07_BARS.csv、旧两例AUDIT.json、10月11日文件、月度结果及工作簿保持原样。'
        '本版取代旧例50%/50%与最近微观阻力退出解读的适用性，不擦除历史解释，也不加入原十笔统计。','',
        '复现只运行`scripts/clarify_btc_nov07_structure.py`；没有新的行情请求、整月回测或订单操作。','']
    return '\n'.join(lines)


def main():
    root=Path('reports/btc_structure_2026_11_08')
    result=clarify(root)
    out=root/'entry_examples/NOV07_USER_STRUCTURE.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    report=Path('docs/investigations/2026-11-08_BTC_NOV07_STRUCTURE_CLARIFICATION.md')
    report.write_text(write_report(root,result))
    print(json.dumps({k:result[k] for k in ('entry_reference','initial_stop_reference','target1_reference',
        'first_target_interval_start_ny','conditional_exit_trace','highest_price_since_entry',
        'realized_legs_per_initial_btc','remaining_fraction_initial')},ensure_ascii=False))


if __name__=='__main__':
    main()
