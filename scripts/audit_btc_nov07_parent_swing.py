"""One nominated case: parent-swing protection, plus a labeled exit proposal.

Never rewrites the micro-trailing audit, October case or monthly replay. The
08:30/08:30--08:45 staged exits require an additional early-exit clause; they
must not be presented as consequences of changing the stop hierarchy alone.
"""
import hashlib
import json
from pathlib import Path

from analyze_btc_simulated_trades import aggregate
from btc_structure_retest import Config, STEP, local
from clarify_btc_nov07_structure import leg_pnl
from clarify_btc_oct11_structure import stamp
from retest_btc_major_resistance import load_source


def parent_pivots(bars):
    hours=aggregate(bars,3600)
    lows=[];highs=[]
    for i in range(1,len(hours)-1):
        a,p,c=hours[i-1:i+2]
        if c['end']-a['t']!=10800:
            continue
        members=[b for b in bars if p['t']<=b['t']<p['end']]
        if p['low']<a['low'] and p['low']<c['low']:
            b=min(members,key=lambda x:x['low'])
            lows.append(dict(t=b['t'],price=p['low'],known_at=c['end'],hour_start=p['t']))
        if p['high']>a['high'] and p['high']>c['high']:
            b=max(members,key=lambda x:x['high'])
            highs.append(dict(t=b['t'],price=p['high'],known_at=c['end'],hour_start=p['t']))
    return lows,highs


def trace_parent(bars,atr_before,at,anchor,initial_stop,t1,t2,resistance,cfg,end):
    lows,highs=parent_pivots(bars)
    protected=dict(t=anchor['t'],price=anchor['low'])
    stop=initial_stop;remaining=1.0;trimmed=False;pending_weak=False
    rows=[];events=[]
    for b in bars:
        if not at<=b['t']<end:
            continue
        now=b['t']+STEP
        row=dict(start_ny=local(b['t']),end_ny=local(now),
            **{k:b[k] for k in ('open','high','low','close')},active_stop=stop,
            protected_low=protected['price'],new_stop=None,effective_from_ny=None,
            action='持有；尚无同时完成同级低点确认与破前峰的新锚点')
        rows.append(row)
        if pending_weak or b['low']<=stop:
            events.append(dict(reason='wick_failure_next_open' if pending_weak else 'stop',
                interval_start_ny=local(b['t']),interval_end_ny=local(now),
                price_reference=b['open'] if pending_weak else min(b['open'],stop),fraction_initial=remaining))
            row['action']='退出全部剩余仓位'
            return dict(rows=rows,events=events,remaining=0.0)
        if not trimmed and b['high']>t1:
            events.append(dict(reason='target1',interval_start_ny=local(b['t']),interval_end_ny=local(now),
                price_reference=t1,fraction_initial=.25))
            remaining=.75;trimmed=True
        if t2 is not None and b['high']>t2:
            events.append(dict(reason='target2',interval_start_ny=local(b['t']),interval_end_ny=local(now),
                price_reference=t2,fraction_initial=remaining))
            return dict(rows=rows,events=events,remaining=0.0)
        # Only pivots whose full right-hand hour has closed may be promoted.
        # A breakout can precede that confirmation; both must be known now.
        for candidate in lows:
            if candidate['known_at']>now or candidate['t']<=protected['t'] or candidate['price']<=protected['price']:
                continue
            peaks=[p for p in highs if p['known_at']<=now and protected['t']<p['t']<candidate['t']]
            if not peaks:
                continue
            peak=max(peaks,key=lambda p:p['price'])
            after=[x for x in bars if candidate['t']<x['t'] and x['t']+STEP<=now]
            if not after or any(x['low']<candidate['price'] for x in after):
                continue
            breakout=next((x for x in after if x['high']>peak['price']),None)
            if breakout is None:
                continue
            atr=atr_before.get(breakout['t'])
            if atr is None:
                raise ValueError('Missing actual pre-breakout ATR; do not fabricate it')
            proposed=candidate['price']-cfg.stop_buffer_atr*atr
            if proposed<=stop:
                continue
            assert max(candidate['known_at'],peak['known_at'],breakout['t']+STEP)<=now
            events.append(dict(reason='raise_parent_stop',fraction_initial=0,
                known_at_ny=local(now),effective_from_ny=local(now),
                reference_low=candidate['price'],reference_low_start_ny=local(candidate['t']),
                parent_low_confirmed_ny=local(candidate['known_at']),
                reference_peak=peak['price'],reference_peak_confirmed_ny=local(peak['known_at']),
                breakout_interval_start_ny=local(breakout['t']),
                atr_known_before_breakout=atr,price_reference=proposed))
            row.update(new_stop=proposed,effective_from_ny=local(now),
                action='同级低点与破前峰均已确认；本根结束后上移保护')
            stop=proposed;protected=candidate
        span=b['high']-b['low'];wick=b['high']-max(b['open'],b['close'])
        if span>0 and b['high']>=resistance and wick/span>=cfg.upper_wick_fraction and b['close']<resistance:
            pending_weak=True
    return dict(rows=rows,events=events,remaining=remaining)


def early_exit_proposal(bars,parent,at,entry,t1,cfg,watch_level=76000.0):
    """Additional candidate, not the approved fixed-target baseline.

    After a prior close above a preselected watch resistance, a new-high candle
    with >=50% upper wick and a close back below it trims 25% next actual open.
    A subsequent intrabar break of that completed rejection candle's low exits
    the remaining 75%. This tactical exit does not replace the parent stop.
    """
    by_time={stamp(r['start_ny']):r for r in parent['rows']}
    active=[b for b in bars if b['t']>=at and b['t'] in by_time]
    peak=max(b['high'] for b in bars if at-STEP<=b['t']<at)
    signal=None
    for i,b in enumerate(active):
        span=b['high']-b['low'];wick=b['high']-max(b['open'],b['close'])
        previous=next(x for x in bars if x['t']==b['t']-STEP)
        if b['high']>t1:
            raise ValueError('This proposal comparison requires no prior fixed-target fill')
        if (span>0 and previous['close']>=watch_level and b['high']>peak
                and b['high']>=watch_level and wick/span>=cfg.upper_wick_fraction
                and entry<b['close']<watch_level):
            signal=b;break
        peak=max(peak,b['high'])
    if signal is None:
        return dict(status='no candidate rejection signal',events=[])
    next_bar=next((b for b in active if b['t']==signal['t']+STEP),None)
    if next_bar is None:
        return dict(status='signal known, no next actual open available',events=[])
    events=[dict(reason='candidate_rejection_trim',known_at_ny=local(signal['t']+STEP),
        interval_start_ny=local(next_bar['t']),price_reference=next_bar['open'],fraction_initial=.25,
        time_basis='next actual BTC bar open model; not verified fill')]
    for b in active:
        if b['t']<next_bar['t']:
            continue
        structural_stop=by_time[b['t']]['active_stop']
        if b['open']<=structural_stop:
            price=b['open'];reason='candidate_structural_gap_exit'
        elif b['low']<=signal['low']:
            price=min(b['open'],signal['low']);reason='candidate_rejection_low_break'
        elif b['low']<=structural_stop:
            price=min(b['open'],structural_stop);reason='candidate_structural_stop'
        else:
            continue
        events.append(dict(reason=reason,known_at_ny=local(signal['t']+STEP),
            interval_start_ny=local(b['t']),interval_end_ny=local(b['t']+STEP),
            price_reference=price,fraction_initial=.75,
            time_basis='intrabar crossing interval only; stop/market fill not verified'))
        break
    return dict(status='candidate only; new early-profit clause, not implied by parent-stop change',
        watch_level=watch_level,watch_level_source='existing learning-manual 76,000 chart reference; not historical pre-entry commitment proof',
        signal_start_ny=local(signal['t']),signal_end_ny=local(signal['t']+STEP),
        upper_wick=signal['high']-max(signal['open'],signal['close']),
        range=signal['high']-signal['low'],upper_wick_fraction=(signal['high']-max(signal['open'],signal['close']))/(signal['high']-signal['low']),
        signal_low=signal['low'],structural_stop_at_trim=by_time[next_bar['t']]['active_stop'],events=events,
        note='Prospective early-exit design, evaluated on this known example; not out-of-sample evidence')


def review(root):
    _,bars,_,end=load_source(root)
    old=json.loads((root/'entry_examples/NOV07_USER_STRUCTURE.json').read_text())
    frozen=json.loads((root/'major_resistance/MAJOR_RETEST.json').read_text())['runs'][1]
    cfg=Config(**frozen['config'])
    atr={stamp(r['start_utc'])+STEP:r['atr'] for r in frozen['ledger']}
    at=stamp(old['entry_interval_start_ny']);entry=old['entry_reference']
    parent=trace_parent(bars,atr,at,old['anchors']['L2'],old['initial_stop_reference'],
        old['target1_reference'],old['next_target_reference'],old['primary_supply_zone']['lower'],cfg,end)
    proposal=early_exit_proposal(bars,parent,at,entry,old['target1_reference'],cfg)
    for scenario in (parent,proposal):
        scenario['pnl_legs']=[dict(reason=e['reason'],interval_start_ny=e['interval_start_ny'],
            **leg_pnl(entry,e['price_reference'],e['fraction_initial'],cfg.one_way_friction_bps))
            for e in scenario['events'] if e['fraction_initial']>0]
        scenario['realized_gross_per_initial_btc']=sum(e['gross_pnl'] for e in scenario['pnl_legs'])
        scenario['realized_net_per_initial_btc']=sum(e['net_pnl'] for e in scenario['pnl_legs'])
    parent['unrealized_gross_at_snapshot']=parent['remaining']*(bars[-1]['close']-entry)
    parent['last_close_reference']=bars[-1]['close']
    return dict(scope='November 7 single-case review only; old audit, October case and monthly results remain frozen',
        entry_reference=entry,initial_stop_reference=old['initial_stop_reference'],
        fixed_target_reference=old['target1_reference'],cost_bps_each_way=cfg.one_way_friction_bps,
        source_end_exclusive_ny=local(end),normalization='per 1 initial BTC; not actual ETF fills',
        parent_stop_only=parent,additional_early_exit_candidate=proposal,
        old_micro_stop=dict(events=old['conditional_exit_trace'],
            pnl_legs=old['realized_legs_per_initial_btc'],net_per_initial_btc=old['realized_net_total_per_initial_btc']),
        comparison_limit='Candidate changes two things: parent protection and early-profit exits. Do not attribute all P/L difference to stop hierarchy.',
        old_audit_sha256=hashlib.sha256((root/'entry_examples/NOV07_USER_STRUCTURE.json').read_bytes()).hexdigest())


def report_text(r):
    parent=r['parent_stop_only'];proposal=r['additional_early_exit_candidate']
    old=r['old_micro_stop'];entry=r['entry_reference']
    lines=['# BTC 11月7日：同级保护复核与提前卖点候选','',
        '单独比较同级止损、原01:00退出及阻力失败的新增分批退出方案，不重跑整月。','',
        '**Last Updated:** 2026-11-08','',
        '**Status:** 同级保护已按单例复核；提前分批卖出仅为新增候选条款，未推广到策略或整月','',
        '**Audience:** 交易桌使用者与维护者','', '## Overview','',
        '保留入场参考75,650、原始L2 75,545.34、初始止损75,529.07857及固定第一目标76,118.18496。'
        '用户认可本次用已完成1小时的三根转折结构识别同级低点，15分钟盘中突破给触发。'
        '当前只在新审计脚本和新报告做单例复核，不改原微观退出审计、10月11日文件、月度结果或工作簿。','',
        '需要分清两项变化：**仅采用同级止损并不会自然产生08:30的25%/75%退出**，因为原固定目标未到达。'
        '若希望08:15–08:30的形态触发主动止盈，需要另写提前退出条款；下文将它标为新增候选，不能冒充原规则已有的成交。','',
        '## 同级保护：每次何时可以上移','',
        '| 可用/生效时间（纽约） | 新锚点所在15分钟K线 | 锚点 | 破前峰发生时段 | 触发前已知ATR | 上移后止损 |',
        '| --- | --- | ---: | --- | ---: | ---: |',
        '| 11/7入场时 | 21:15–21:30 | 75,545.34 | 原入场触发 | 65.0457143 | **75,529.07857** |']
    for e in parent['events']:
        if e['reason']=='raise_parent_stop':
            lines.append(f"| {e['effective_from_ny'][5:16].replace('T',' ')} | {e['reference_low_start_ny'][11:16]}起15分钟 | "
                f"{e['reference_low']:,.2f} | {e['breakout_interval_start_ny'][11:16]}起15分钟 | "
                f"{e['atr_known_before_breakout']:.7f} | **{e['price_reference']:,.5f}** |")
    lines += ['',
        '计算继续沿用0.25个15分钟ATR缓冲，ATR固定取盘中突破开始前已经完成的数据，不改为小时ATR，也不改缓冲倍数。'
        '01:30低点到03:00才能获得右侧小时确认；02:45已破前峰，所以两项证据03:00齐备。'
        '05:30低点在06:15虽已出现破前峰，右侧小时到07:00才结束，故不能提前在06:30上移。','',
        '22:30的小回踩、07:30的小回踩均未取得同级低点资格。08:00和08:15继续创新高也不创造新的合格低点。'
        '截至归档终点11/8 11:00（不含），本版只有上述两次上移。','',
        f"**只换同级止损：没有触及活动止损，也没有到固定目标{r['fixed_target_reference']:,.2f}。** "
        f"条件持仓仍为100%；最后10:45–11:00收盘{parent['last_close_reference']:,.2f}，"
        f"按初始1 BTC的未实现毛盈亏为+${parent['unrealized_gross_at_snapshot']:.2f}，不是已实现退出收益。",'',
        '## 08:15–08:30这根如何定义为卖出信号','',
        '固定第一目标76,118.18继续保留。另以手册早已讨论的**76,000观察关口**检验提前兑现候选；'
        '不是把固定T1下移，也不把最高76,094.99事后设置成止盈目标。'
        '手册有该观察关口，不等于证明11月7日原入场时已经承诺采用这条退出规则。','',
        '新增候选定义如下，供评审而非直接替换原策略：','',
        '1. 提前标出观察阻力；前一根完整15分钟已收在其上，本根继续创新高后回落。',
        '2. 本根完成时，上影线至少占全根振幅50%，且收回观察阻力下方，同时仍高于本笔入场价。'
        '这是**拒绝预警**：下一根实际开盘尝试卖出初始25%。50%影线阈值沿用既有草案。',
        '3. 预警K线低点在完成后固定；随后盘中跌破它，作为**延续失败确认**，一次退出剩余75%。'
        '结构保护仍按同级低点管理；主动止盈条件另行记录，不把预警K线低点冒充新的同级波段低点。',
        '4. 固定目标或结构止损若更早触发，按实际剩余仓位处理；止损不拆批，不能重复卖出。','',
        '该根实际为：O76,015.62、H76,094.99、L75,944.77、C75,956.19。'
        f"上影79.37，全振幅150.22，上影占**{proposal['upper_wick_fraction']:.2%}**，收回76,000下方。"
        '**完整信号最早08:30才知道，不能写成08:15已经确认长上影。**', '',
        '06:15–06:30也有较长上影，但最高75,920.56未到预先选择的76,000关口；'
        '所以本候选不会仅凭那根上影提前触发。若取消位置条件，只凭长上影，退出时间会不同。','',
        '08:30下一根真实开盘75,956.20，高于已知预警低点75,944.77；因此可以先记录25%的开盘模型退出，'
        '再核对该根盘中是否跌破低点。本根低75,800.01，确实越过75,944.77；'
        '75%的触发只能定位于**08:30–08:45内**，精确秒数及实际成交价不可从OHLC得出。','',
        '如果要求在08:15–08:30盘中就卖，需要预先另定“跌回关口”等盘中触发，不能同时使用本根最终上影比例。'
        '本次没有增加那个盘中版本。既有手册若将完整阻力失败直接定义为退出全部剩余仓位，则08:30会是100%退出；'
        '这里的“先预警25%、后破低点75%”是新增分批方案，不能与旧失败全退出规则混用。','',
        '## 候选分批退出的盈亏','',
        '按初始1 BTC折算；零佣金，保留每边2bps假设价差/滑点。不是ETF真实成交。','',
        '| 部分 | 确认/触发时间（11/8纽约） | 出场参考 | 毛盈亏 | 假设摩擦 | 净盈亏 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for leg in proposal['pnl_legs']:
        timing='08:30，确认后下一根实际开盘模型' if leg['fraction_initial']==.25 else '08:30–08:45内，盘中过预警低点'
        lines.append(f"| {leg['fraction_initial']:.0%} | {timing} | {leg['exit_reference']:,.2f} | "
            f"+${leg['gross_pnl']:.2f} | ${leg['assumed_roundtrip_friction']:.2f} | **+${leg['net_pnl']:.2f}** |")
    lines += [f"| 合计 | 两部分合计100% | — | **+${proposal['realized_gross_per_initial_btc']:.2f}** | "
        f"${sum(p['assumed_roundtrip_friction'] for p in proposal['pnl_legs']):.2f} | **+${proposal['realized_net_per_initial_btc']:.2f}** |",'',
        '75,944.77是模型触发参考，不是保证的止损成交价。跳空、价差及价格跳变可能使实际退出更差。'
        '本候选参考价使用0.25与0.75份额分别分配入场及出场摩擦，未把入场成本重复扣两次。','',
        '## 与原01:00整仓退出比较','',
        '| 情景 | 退出/持仓状态 | 已实现模拟净盈亏/初始1 BTC | 未实现毛盈亏/初始1 BTC |',
        '| --- | --- | ---: | ---: |',
        f"| 原微观跟踪 | 01:00–01:15，100%于75,686.95参考退出 | **+${old['net_per_initial_btc']:.2f}** | $0.00 |",
        f"| 只改同级保护，固定目标不变 | 11:00归档终点仍持有100% | **$0.00** | **+${parent['unrealized_gross_at_snapshot']:.2f}** |",
        f"| 同级保护＋新增提前分批退出候选 | 08:30卖25%，08:30–08:45破低点卖余75% | **+${proposal['realized_net_per_initial_btc']:.2f}** | $0.00 |",'',
        f"第三种比原情景的模拟已实现净值高${proposal['realized_net_per_initial_btc']-old['net_per_initial_btc']:.2f}，"
        '**但它同时改变了保护层级与提前兑现触发，不能把全部差异归功于止损改进。** '
        '这是在已知案例上提出并检查的候选规则，不是独立样本盈利证据；不据此调整整月参数或宣称胜率改善。','',
        '## 同级保护逐根记录','',
        '列出入场至归档终点全部54根真实15分钟K线。活动止损是本根开始时已经生效的值；'
        '新值若在本根结束时才可确认，从下一根起使用。最后一列另标候选分批事件。','',
        '| 开始（纽约） | 结束 | 高 | 低 | 收 | 活动同级止损 | 本根结束后的变化 | 候选卖出事件 |',
        '| --- | --- | ---: | ---: | ---: | ---: | --- | --- |']
    for b in parent['rows']:
        note='无新触发'
        if b['start_ny']==proposal['signal_start_ny']:
            note='信号形成中；08:30收盘后才确认'
        if b['start_ny']=='2026-11-08T08:30:00-05:00':
            note='开盘25%；随后过75,944.77退出余75%'
        elif b['start_ny']>'2026-11-08T08:30:00-05:00':
            note='候选方案已退出；同级止损单独情景继续观察'
        change=f"{b['effective_from_ny'][11:16]}起{b['new_stop']:,.5f}" if b['new_stop'] is not None else '不变'
        lines.append(f"| {b['start_ny'][5:16].replace('T',' ')} | {b['end_ny'][11:16]} | {b['high']:,.2f} | "
            f"{b['low']:,.2f} | {b['close']:,.2f} | {b['active_stop']:,.5f} | {change} | {note} |")
    lines += ['', '## 来源与复核范围','',
        '真实行情来自原归档Coinbase BTCUSD源，逐根与原API原文及哈希验证一致；未新增抓取、填充或插值。'
        '结构、因果确认时点、价格与成本明细保存在'
        '[单例对照JSON](../../reports/btc_structure_2026_11_08/entry_examples/NOV07_PARENT_SWING_REVIEW.json)。'
        '原11月7日微观方案、10月11日案例、原十笔交易统计、月度工作簿及任何账户均未改动。','',
        '复现：`python3 scripts/audit_btc_nov07_parent_swing.py`；'
        '核对：`python3 -m pytest trading_desk/tests/test_btc_nov07_parent_swing.py -q`。','']
    return '\n'.join(lines)


def main():
    root=Path('reports/btc_structure_2026_11_08')
    result=review(root)
    (root/'entry_examples/NOV07_PARENT_SWING_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    Path('docs/investigations/2026-11-08_BTC_NOV07_PARENT_SWING_REVIEW.md').write_text(report_text(result))
    print(json.dumps({k:v for k,v in result.items() if k not in ('parent_stop_only','old_micro_stop')},ensure_ascii=False))


if __name__=='__main__':
    main()
