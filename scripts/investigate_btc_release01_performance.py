"""Read-only release 0.1 diagnostics; no strategy tuning, replay or orders."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts
from scripts.audit_btc_all_losses import audit_losses

RUN='20261109T041525Z-30-ab'


def fixed_entry_failed_breakout_probe(db,p):
    """Unpromoted hypothesis: complete red/non-inside close loses entry trigger.

    Keep all original entries and earlier partial exits. A confirmation is
    actionable only at the following observed minute open; no missing bars,
    same-minute original exits, or future prices can create the signal.
    This is attribution, not a sequential/monthly strategy replay.
    """
    for start in range(ts(p['entry_time'])//900*900,ts(p['exit_time']),900):
        known=start+900
        if known>=ts(p['exit_time']):break
        bars=db.execute('SELECT t,o,h,l,c FROM minutes WHERE t>=? AND t<? ORDER BY t',(start-900,known)).fetchall()
        if [x[0] for x in bars]!=list(range(start-900,known,60)):continue
        previous=bars[:15];bar=bars[15:]
        op=bar[0][1];close=bar[-1][4];high=max(x[2] for x in bar);low=min(x[3] for x in bar)
        po=previous[0][1];pc=previous[-1][4];ph=max(x[2] for x in previous);pl=min(x[3] for x in previous)
        inside=(high<=ph and low>=pl) or (min(op,close)>=min(po,pc) and max(op,close)<=max(po,pc))
        if not(close<op and close<=pc and close<p['references']['trigger'] and not inside):continue
        nxt=db.execute('SELECT o FROM minutes WHERE t=?',(known,)).fetchone()
        if nxt is None:continue
        earlier=[l for l in p['legs'] if ts(l['time_utc'])<known]
        remaining=1-sum(l['fraction'] for l in earlier);price=nxt[0]
        net=sum(l['net'] for l in earlier)+remaining*((price-p['entry'])-(price+p['entry'])*.0002)
        from trading_desk.btc_data import iso
        return dict(trade_id=p['id'],signal_bar=iso(start),confirmed_at=iso(known),exit_time=iso(known),exit_price=price,
            signal_open=op,signal_close=close,original_trigger=p['references']['trigger'],remaining=remaining,
            baseline_net=p['net'],probe_net=net,net_change=net-p['net'])
    return None


def investigate():
    folder=STORE/'runs'/RUN;r=read(folder/'result.json')
    audited=audit_losses(r,expected_count=19)
    rows=[];probes=[]
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for p in r['trades']:
            candidate=fixed_entry_failed_breakout_probe(db,p)
            if candidate:probes.append(candidate)
            signal=next(s for s in r['signals'] if s['id']==p['signal_id'])
            obs=p.get('giveback_observations',[])
            risk=p['entry']-p['initial_stop']
            max_r=max((o.get('mfe_r') or 0 for o in obs),default=0)
            benchmark=[]
            for o in obs:
                # Strictly earlier exits are known at this opening. Never infer
                # whether an unresolved same-minute target filled first.
                legs=[l for l in p['legs'] if ts(l['time_utc'])<ts(o['time_utc'])]
                remaining=1-sum(l['fraction'] for l in legs)
                price=o['reference_price']
                net=sum(l['net'] for l in legs)+remaining*((price-p['entry'])-(price+p['entry'])*.0002)
                benchmark.append((net,o['time_utc']))
            best=max(benchmark,key=lambda x:x[0]) if benchmark else None
            blocked=next((o for o in obs if o.get('armed') and (o.get('giveback_fraction') or 0)>=.5),None)
            entry=ts(p['entry_time'])
            before=db.execute('SELECT t,o,c FROM minutes WHERE t>=? AND t<? ORDER BY t',(entry-7200,entry)).fetchall()
            complete=[x[0] for x in before]==list(range(entry-7200,entry,60))
            rows.append(dict(trade_id=p['id'],route=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],
                exit_time=p['exit_time'],exit_reason=p['legs'][-1]['reason'],net=p['net'],
                cost=sum(l['cost'] for l in p['legs']),gross=sum(l['gross'] for l in p['legs']),
                initial_risk_atr=risk/signal['atr'],max_known_price_mfe_r=max_r,
                historical_best_open_liquidation_net=best[0] if best else None,
                historical_best_open_time=best[1] if best else None,
                hindsight_giveback=best[0]-p['net'] if best else None,
                first_1r_half_giveback=blocked,first_target=next((l for l in p['legs'] if l['reason']=='target_25'),None),
                pre_entry_2h_complete=complete,pre_entry_2h_move=before[-1][2]/before[0][1]-1 if complete else None,
                gap_exposed=p['gap_exposed'],context_partial=p['context_partial']))
    losing=[x for x in rows if x['net']<0];wins=[x for x in rows if x['net']>0]
    groups=[]
    for route in sorted(set(p['route'] for p in rows)):
        group=[p for p in rows if p['route']==route]
        groups.append(dict(route=route,count=len(group),wins=sum(p['net']>0 for p in group),net=sum(p['net'] for p in group)))
    return dict(failed_breakout_probe=dict(kind='fixed original entries only; not sequential monthly performance',changed=probes,
            delta=sum(p['net_change'] for p in probes),conditional_net=sum(p['net'] for p in rows)+sum(p['net_change'] for p in probes),
            improved=sum(p['net_change']>0 for p in probes),worsened=sum(p['net_change']<0 for p in probes),adopted=False),
        source_run=RUN,source_sha256=r['source_minute_sha256'],baseline_net=sum(p['net'] for p in rows),
        trade_count=len(rows),gross_wins=sum(p['net'] for p in wins),gross_losses=sum(p['net'] for p in losing),
        total_cost=sum(p['cost'] for p in rows),profit_factor=sum(p['net'] for p in wins)/-sum(p['net'] for p in losing),
        top_losses=sorted(losing,key=lambda p:p['net'])[:5],
        losses_below_1r=[p['trade_id'] for p in losing if p['max_known_price_mfe_r']<1],
        losses_after_1r=[p['trade_id'] for p in losing if p['max_known_price_mfe_r']>=1],
        top_hindsight_givebacks=sorted([p for p in rows if p['hindsight_giveback'] is not None],key=lambda p:p['hindsight_giveback'],reverse=True)[:5],
        groups=groups,rows=rows,loss_exit_audits=audited,
        hindsight_benchmark='Post-trade diagnostic only: best observed minute-open liquidation value, costs included and earlier legs retained. Not an executable exit signal, recoverable profit or optimization target.',
        no_month_rerun=True,parameters_changed=False,orders_enabled=False)


def main():
    files=list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))+list((STORE/'releases/0.1').rglob('*'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file() and '__pycache__' not in str(p)}
    out=investigate();save(STORE/'investigations/RELEASE_0_1_PERFORMANCE.json',out)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    ny=ZoneInfo('America/New_York')
    clock=lambda t:datetime.fromisoformat(t.replace('Z','+00:00')).astimezone(ny).strftime('%m/%d %H:%M %Z')
    lines=['# BTC Release 0.1后续绩效调查','',
        '保留0.1为基准，分析真实亏损与已观察利润回吐，未修改交易规则。','',
        'Last Updated: 2026-11-09  ','Status: 第一轮诊断完成；候选规则尚未验证  ',
        'Audience: 交易桌使用者与维护者','','## Overview','',
        f"冻结记录`{RUN}`，{out['trade_count']}笔、净+${out['baseline_net']:,.2f}／每笔初始1 BTC。原源码、真实行情、原表格及所有月度结果保留，未重跑整月。",
        '新B1独立守D记录仍留作实验对照，不升级为0.1。交易桌默认展示0.1，新回测默认明确采用0.1入场／退出；实验须显式选择。',
        '', '## 月度损益组成','',
        f"盈利交易净额合计+${out['gross_wins']:,.2f}，亏损交易净额合计${out['gross_losses']:,.2f}；相抵后净+${out['baseline_net']:,.2f}。全部模型摩擦成本${out['total_cost']:,.2f}，盈利交易净额／亏损交易净额绝对值={out['profit_factor']:.3f}。",'',
        '| 路线 | 笔数 | 盈利笔数 | 净盈亏 |','| --- | ---: | ---: | ---: |']
    for x in out['groups']:lines.append(f"| {x['route']} | {x['count']} | {x['wins']} | {x['net']:+,.2f} |")
    lines+=['','## 最大亏损：优先审查','',
        '| 0.1交易# | 纽约入场 | 净盈亏 | 初始价差／ATR | 已知最大价格浮盈R | 退出 | 持有缺口 |',
        '| --- | --- | ---: | ---: | ---: | --- | --- |']
    for p in out['top_losses']:lines.append(f"| {p['trade_id']} | {clock(p['entry_time'])} | {p['net']:+,.2f} | {p['initial_risk_atr']:.3f} | {p['max_known_price_mfe_r']:.3f} | {p['exit_reason']} | {'有' if p['gap_exposed'] else '无已标记缺口'} |")
    lines+=['','## 区分入场问题与保护问题','',
        f"19笔亏损中，{len(out['losses_below_1r'])}笔未观察到1R价格浮盈：{out['losses_below_1r']}；{len(out['losses_after_1r'])}笔曾达到1R后仍亏：{out['losses_after_1r']}。1R使用入场减初始止损，保持原定义。仅使用保存的当时观察，排除入场分钟尚不能确定先后的高价。",'',
        '未达1R的交易应先查急跌后的反弹力度、突破失败和原D宽度；不能指望已设为1R启用的利润保护处理尚未达到1R的交易。曾达1R的交易应逐分钟查颜色、前收盘、内包和结构确认，是条件豁免还是实际未触发，而不是直接收紧全体止损。', '',
        '所有19笔亏损的原退出条件及实际1分钟价位已按现有规则逐项核验。通过核验不代表策略有效，只说明不能把合规亏损改称程序错误。', '',
        '## 利润回吐审查队列（事后诊断）','',
        '**下列“最好首价清仓估值”使用持有期间真实观察到的1分钟首价，扣成本并保留更早25%退出。它是事后观察上界样本，不是当时已确认卖点，不可直接加回收益。**', '',
        '| 交易# | 最好首价观察时间 | 当时净清仓估值 | 最终实际模型净额 | 两者差额（非可实现改善） |',
        '| --- | --- | ---: | ---: | ---: |']
    for p in out['top_hindsight_givebacks']:lines.append(f"| {p['trade_id']} | {clock(p['historical_best_open_time'])} | {p['historical_best_open_liquidation_net']:+,.2f} | {p['net']:+,.2f} | {p['hindsight_giveback']:,.2f} |")
    lines+=['','## 下一轮实验应回答的具体问题','',
        '1. 先逐根核对最大亏损#5与#32：入场后首次完整15分钟是否重新跌回突破参考，原D与急跌结构是否仍有效，是否存在早于原止损的可知失败信号。当前仅研究，尚不把该条件作为新退出。',
        '2. 对曾达1R后亏损及利润回吐队列，逐分钟列出保护被颜色／前收盘／内包过滤的原因，区分合乎持有逻辑的整理与已确认转弱。先保留原过滤，再检验一个有因果依据的改动。',
        '3. 同样的候选条件必须检查全部盈利交易，记录错失上涨、成本和占仓顺序变化；不只展示被避免的亏损。先固定入场做退出归因，再经授权重放完整顺序。',
        '4. 只用入场前完整真实行情分组检查趋势背景；缺少完整2小时数据时标为空，不补值。观察到相关性不等于批准新趋势过滤，也不能事后排除不利日期。',
        '5. 提升候选必须同时看美元净收益、最大回撤、交易成本、交易数、盈利集中度、缺口及窗口外表现；不做参数网格搜索。对反复审查的同一月份不能声称样本外有效。', '',
        '## 数据与执行边界','',
        '本次只读保存的Alpaca分钟与0.1结果，没有新市场请求、订单或策略重放。缺失分钟不填补；真实分钟输入SHA256保持原值。BTC全天信号及ETF零佣金加每边2bps摩擦仍是条件模型，非实盘或真实ETF收益。']
    q=out['failed_breakout_probe']
    lines+=['','## 首个未采用候选：完整K线失守原突破价','',
        '事先限定一条候选：完整15分钟收阴、收盘不高于前收、非实体／全振幅内包，且收盘跌回原入场突破参考以下；下一真实分钟首价退出当时实际余仓。保留此前25%及原入场；缺少完整行情不产生信号，不回填确认价。没有搜索阈值。', '',
        f"逐笔检查全部38笔，{len(q['changed'])}笔退出受影响：{q['improved']}笔改善、{q['worsened']}笔变差；固定原入场净差{q['delta']:+,.2f}，条件净额{q['conditional_net']:+,.2f}。**这不是新整月策略收益**，因为新的空仓时间会影响后续入场。当前未采用，0.1完全不变。", '',
        '| 原交易# | 确认／候选退出 纽约 | 候选首价 | 原净盈亏 | 固定入场候选净盈亏 | 差额 |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for x in q['changed']:lines.append(f"| {x['trade_id']} | {clock(x['confirmed_at'])} | {x['exit_price']:,.4f} | {x['baseline_net']:+,.2f} | {x['probe_net']:+,.2f} | {x['net_change']:+,.2f} |")
    (ROOT/'docs/investigations/2026-11-09_BTC_RELEASE_0_1_PERFORMANCE.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:out[k] for k in ('baseline_net','gross_wins','gross_losses','total_cost','profit_factor','groups','losses_below_1r','losses_after_1r')},indent=2))
    print('probe',json.dumps(out['failed_breakout_probe']))
    print('largest losses',[(p['trade_id'],round(p['net'],2)) for p in out['top_losses']])
    print('giveback review',[(p['trade_id'],round(p['hindsight_giveback'],2)) for p in out['top_hindsight_givebacks']])


if __name__=='__main__':main()
