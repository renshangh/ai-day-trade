"""Two predefined, unpromoted early-exit hypotheses on #32/#30 only."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from scripts.audit_btc_release01_pullbacks import RUN,review as read_cases,clock

DEST=STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json'


def completed_scan(case,*,cutoff=None):
    """Use completed actual bars only; later bars cannot alter earlier signals.

    Two downward comparisons require three adjacent complete candles. This
    is an explicit research assumption, not a confirmed parent H/L sequence,
    a new D, or an adopted change to release 0.1.
    """
    trigger=case['entry']['references']['trigger']
    entry=ts(case['entry']['entry_time']);limit=min(ts(case['exit_time']),cutoff or ts(case['exit_time']))
    floor=entry//900*900;previous=None;run=0;first_a=None;first_b=None
    armed=None;armed_peak=None;reclaim=None;failure=None;trace=[]
    for b in case['bars']:
        start=ts(b['time']);known=ts(b['end'])
        if known>limit:break
        if not b['complete'] or b['observed_minutes']!=15:
            previous=None;run=0;armed=None;armed_peak=None;reclaim=None;failure=None;continue
        if start<floor:
            previous=b;continue
        adjacent=previous is not None and ts(previous['end'])==start
        if not adjacent:
            armed=None;armed_peak=None;reclaim=None;failure=None
        lower=bool(adjacent and b['high']<previous['high'] and b['low']<previous['low'])
        run=run+1 if lower else 0
        red=b['close']<b['open']
        prior_close=bool(adjacent and b['close']<=previous['close'])
        full_inside=bool(adjacent and b['high']<=previous['high'] and b['low']>=previous['low'])
        body_inside=bool(adjacent and min(b['open'],b['close'])>=min(previous['open'],previous['close'])
            and max(b['open'],b['close'])<=max(previous['open'],previous['close']))
        direction=adjacent and red and prior_close and not(full_inside or body_inside)
        below=b['close']<trigger
        qualifies_a=bool(run>=2 and below and direction and known<ts(case['exit_time']))
        if qualifies_a and first_a is None:
            first_a=dict(rule='E1_CONTINUOUS_WEAKNESS',confirmed_at=b['end'],signal_bar=b['time'],
                evidence=dict(bars=copy.deepcopy([x for x in case['bars'] if start-1800<=ts(x['time'])<=start]),
                    consecutive_down_comparisons=run,trigger=trigger,close=b['close'],
                    red=red,not_above_previous_close=prior_close,full_inside=full_inside,body_inside=body_inside))
        if qualifies_a and armed is None:
            armed=b['end']
            armed_peak=max(x['high'] for x in case['bars'] if x['complete'] and floor<=ts(x['time']) and ts(x['end'])<=known)
        stage='after_B_exit_baseline_path_only' if first_b is not None else 'waiting_for_weakness' if armed is None else 'waiting_for_reclaim'
        if armed and known>ts(armed) and first_b is None:
            if failure is not None:
                follow=ts(failure['bar']['end'])==start and lower and below and direction
                if follow:
                    first_b=dict(rule='E2_RECLAIM_FAILURE_FOLLOWTHROUGH',confirmed_at=b['end'],signal_bar=b['time'],
                        evidence=dict(weakness_known_at=armed,reclaim=copy.deepcopy(reclaim),
                            failed_reclaim_bar=copy.deepcopy(failure['bar']),followthrough=copy.deepcopy(b),
                            lower_high_than_failure=b['high']<failure['bar']['high'],lower_low_than_failure=b['low']<failure['bar']['low'],
                            known_postentry_high_before_weakness=armed_peak,
                            reclaim_attempt_high=max(reclaim['high'],failure['bar']['high'],b['high']),
                            reclaim_below_known_high=max(reclaim['high'],failure['bar']['high'],b['high'])<armed_peak,
                            trigger=trigger,red=red,not_above_previous_close=prior_close,
                            full_inside=full_inside,body_inside=body_inside))
                    stage='B_confirmed'
                else:
                    # Only the immediately following complete bar can confirm
                    # this attempt. A miss requires another complete reclaim.
                    failure=None;reclaim=None
            if first_b is None:
                if b['close']>trigger:
                    reclaim=copy.deepcopy(b);failure=None;stage='reclaim_complete'
                elif reclaim is not None and direction and below:
                    failure=dict(bar=copy.deepcopy(b));stage='failed_reclaim_wait_next_bar'
                elif reclaim is not None:stage='reclaim_seen_wait_failure'
        trace.append(dict(bar_time=b['time'],confirmed_at=b['end'],open=b['open'],high=b['high'],low=b['low'],close=b['close'],
            lower_pair=lower,consecutive_down_comparisons=run,below_original_trigger=below,red=red,
            not_above_previous_close=prior_close,full_inside=full_inside,body_inside=body_inside,
            A_qualified=qualifies_a,weakness_known_at=armed,B_stage=stage,
            after_A_signal=bool(first_a and known>ts(first_a['confirmed_at'])),
            after_B_signal=bool(first_b and known>ts(first_b['confirmed_at']))))
        previous=b
    return dict(A=first_a,B=first_b,trace=trace)


def value_exit(case,signal):
    if signal is None:
        return dict(triggered=False,original_exit_retained=True,net=case['net'],baseline_net=case['net'],net_change=0,
            legs=copy.deepcopy(case['legs']))
    now=ts(signal['confirmed_at'])
    row=next((m for m in case['minutes'] if ts(m['time'])==now),None)
    if row is None:
        return dict(triggered=True,original_exit_retained=False,signal=signal,execution_observation_available=False,
            exit_time=None,exit_price=None,net=None,net_change=None,legs=None,
            missing_policy='do not carry forward, interpolate or substitute the signal close')
    assert now<ts(case['exit_time'])
    earlier=[copy.deepcopy(l) for l in case['legs'] if ts(l['time_utc'])<now]
    remaining=1-sum(l['fraction'] for l in earlier)
    entry=case['entry']['entry'];price=row['open']
    gross=remaining*(price-entry);cost=remaining*(price+entry)*.0002
    leg=dict(time_utc=iso(now),interval_end=iso(now+60),fraction=remaining,price=price,gross=gross,cost=cost,net=gross-cost,
        reason='unpromoted_'+signal['rule'])
    net=sum(l['net'] for l in earlier)+leg['net']
    return dict(triggered=True,original_exit_retained=False,signal=signal,execution_observation_available=True,
        exit_time=iso(now),interval_end=iso(now+60),exit_price=price,remaining=remaining,
        gross=sum(l['gross'] for l in earlier)+gross,cost=sum(l['cost'] for l in earlier)+cost,
        net=net,baseline_net=case['net'],net_change=net-case['net'],legs=earlier+[leg],
        minutes_earlier=(ts(case['exit_time'])-now)//60,
        sampling='direction/inside checks on complete signal candle; exit proxy is following real 1m opening, not backfilled close')


def review():
    original=read_cases();cases=[]
    for c in original['cases']:
        if c['trade_id'] not in (32,30):continue
        scan=completed_scan(c)
        cases.append(dict(trade_id=c['trade_id'],entry=copy.deepcopy(c['entry']),baseline_net=c['net'],baseline_exit=c['exit_time'],
            baseline_legs=copy.deepcopy(c['legs']),source_minutes=c['source_minutes'],source_rows_sha256=c['source_rows_sha256'],
            missing_minutes=c['missing_minutes'],trace=scan['trace'],
            alternatives={name:value_exit(c,scan[name]) for name in ('A','B')}))
    return dict(source_run=RUN,cases=cases,timezone='America/New_York',review_date='2026-11-09',
        scope='Only frozen #32 and #30; alternative fixed-entry exits, not sequential monthly performance',
        candidate_labels=dict(A='E1 连续走弱',B='E2 收复失败确认'),
        definitions=dict(A='Two consecutive adjacent complete 15m lower-high/lower-low comparisons (3 bars); close below original breakout trigger; red, <= previous close, neither full range nor body inside; following observed 1m opening exit.',
            B='After A establishes weakness, require a later complete close back above the original trigger, a red/non-inside close below it, and the immediately following complete bar also red/non-inside with lower high and low and close below trigger; following observed 1m opening exit.'),
        explicit_research_assumptions=['two downward adjacent-bar comparisons, not independent parent swing lows',
            'direction and inside filters sampled on completed signal bars, unlike release 0.1 intrabar protection',
            'A and B are alternatives, never two exits of the same original shares',
            'first target and earlier legs retained; no missing observations filled'],
        source_run_sha256=original['source_run_sha256'],month_rerun=False,release_modified=False,
        new_exit_rule_adopted=False,numerical_stop_target_cost_parameters_changed=False,orders_enabled=False)


def report(r):
    lines=['# BTC 0.1：#32提前退出与#30回踩对照','',
        '固定原入场，比较两条事先明确的候选退出，保留0.1与整月结果。','',
        'Last Updated: 2026-11-09  ','Status: 两笔研究完成；候选未采用，未重跑整月  ',
        'Audience: 交易学习手册使用者及维护者','','## Overview','',
        '本次只审查#32（2026年11月5日）及#30（11月4日），时间均为纽约EST。只读0.1与真实1分钟行情，未创建回放引擎、改动0.1或重跑整月。',
        '**退出候选E1、E2是两条互斥研究路径，不是先后卖出两次100%，也不改变原入场A/B路线。** #32两者均在首次目标之前，候选退出100%；#30不触发两候选，保留原25%与75%。', '',
        '## 研究定义：先固定，再检查两笔','',
        '### E1：连续走弱并失守原突破价','',
        '至少连续两次相邻完整15分钟K线的最高及最低均下降（共需3根K线作比较），并且当前完整收盘低于原入场突破价、收阴、不高于前收、实体及全振幅均非内包。确认后用下一真实分钟首价估算退出。',
        '“两次”是本轮明确提出的研究门槛，没有试其他长度；相邻K线高低变化不等于已经确认的同级H-L-LH，也不替换原D或硬止损。', '',
        '### E2：收复后再次失败，下一根跟随确认','',
        '先出现E1定义的背景转弱，但暂不按E1退出。之后必须有完整K线收回原突破价上方，再有完整阴线收回其下方，最后紧接的一根完整K线继续降高降低、收阴、不高于前收、非内包且仍在突破价下方。确认后用下一真实分钟首价估算退出。若紧接K线不确认，该次尝试取消，等待新的完整收复。',
        '方向及内包条件在已完成的信号K线上检查，估价使用随后一分钟真实首价；**这不是0.1原有的盘中保护规则**。例如下一分钟首价可能高于信号收盘，仍按实际首价，不回填更好价格。原止损、目标和每边2bps摩擦不变。', '',
        '## 两笔结果：不计算新的整月收益','',
        '| 原交易# | 路径 | 确认时间 | 候选退出分钟 | 原参考／候选退出价 | 候选整笔净盈亏 | 相对0.1净差 |',
        '| --- | --- | --- | --- | ---: | ---: | ---: |']
    for c in r['cases']:
        for name,p in c['alternatives'].items():
            lines.append(f"| {c['trade_id']} | {'E1' if name=='A' else 'E2'} | {clock(p['signal']['confirmed_at']) if p['triggered'] else '未触发'} | {clock(p['exit_time'])+' → '+clock(p['interval_end']) if p['triggered'] and p.get('exit_time') else '保留原退出'} | {p['exit_price']:,.4f} | {p['net']:+,.2f} | {p['net_change']:+,.2f} |" if p['triggered'] else f"| {c['trade_id']} | {'E1' if name=='A' else 'E2'} | 未触发 | 保留原25%／75%退出 | — | {p['net']:+,.2f} | 0.00 |")
    lines+=['','## #32：E1在12:15能知道什么','',
        '| 完整K线 | 高 | 低 | 收 | 当时作用 |','| --- | ---: | ---: | ---: | --- |']
    c32=next(c for c in r['cases'] if c['trade_id']==32)
    for b in c32['trace']:
        if b['bar_time'] in ('2026-11-05T16:30:00Z','2026-11-05T16:45:00Z','2026-11-05T17:00:00Z'):
            lines.append(f"| {clock(b['bar_time'])} → {clock(b['confirmed_at'])} | {b['high']:,.4f} | {b['low']:,.4f} | {b['close']:,.4f} | 连续降高降低比较{b['consecutive_down_comparisons']}次 |")
    a=c32['alternatives']['A'];b=c32['alternatives']['B']
    lines+=['',f"截至12:15，12:00–12:15根已经完整收阴，收76,073.185低于原突破76,260.81；相邻两次高低同时下降，且非内包。只在E1这个研究定义下构成退出，而非事后声称0.1原规则早已触发。随后12:15–12:16实际首价{a['exit_price']:,.4f}，净{a['net']:+,.2f}；较原17:47净{c32['baseline_net']:+,.2f}改善{a['net_change']:,.2f}，提前{a['minutes_earlier']}分钟。", '',
        '## #32：E2逐步确认收复失败','',
        '| 步骤 | 完整K线／已知时间 | 高／低／收 | 含义 |',
        '| --- | --- | --- | --- |']
    evidence=b['signal']['evidence']
    for label,bar in [('收回突破价',evidence['reclaim']),('再次失守',evidence['failed_reclaim_bar']),('下一根跟随',evidence['followthrough'])]:
        lines.append(f"| {label} | {clock(bar['time'])} → {clock(bar['end'])} | {bar['high']:,.4f}／{bar['low']:,.4f}／{bar['close']:,.4f} | 到区间结束才完整已知 |")
    lines+=['',f"15:15才具备E2全部条件，用15:15–15:16真实首价{b['exit_price']:,.4f}，净{b['net']:+,.2f}；较原0.1改善{b['net_change']:,.2f}，提前{b['minutes_earlier']}分钟。等待更多确认的代价是比E1多亏{a['net']-b['net']:,.2f}。",'',
        f"在E1背景确认时，已知入场后波峰为{evidence['known_postentry_high_before_weakness']:,.4f}；后来这次收复尝试最高{evidence['reclaim_attempt_high']:,.4f}，仍低于该波峰。这是当时可知的较弱反弹背景，未追加为另一个参数筛选。", '',
        '14:15旧H-L-LH被重夺取消，不影响E2后来使用14:30–14:45的完整收复。E2是新的研究判定，不能当成原LH破L规则；两者依据和时间必须分开。', '',
        '## #30：为何两种候选没有过早退出','',
        '| 完整K线／已知时间 | 与前根高低比较 | 收盘与原突破价 | 本轮判断 |',
        '| --- | --- | --- | --- |']
    c30=next(c for c in r['cases'] if c['trade_id']==30)
    for bar in c30['trace']:
        if bar['bar_time'] in ('2026-11-04T14:00:00Z','2026-11-04T14:15:00Z','2026-11-04T14:30:00Z'):
            lines.append(f"| {clock(bar['bar_time'])} → {clock(bar['confirmed_at'])} | 连续降高降低比较{bar['consecutive_down_comparisons']}次 | {bar['close']:,.4f}／原突破78,239.91 | {'E1符合' if bar['A_qualified'] else 'E1不符合；E2未启动'} |")
    lines+=['',
        '09:00–09:15有一次相邻降高降低；09:15–09:30却同时抬高高点和低点，连续下降计数归零。虽然收78,209.6105低于原突破78,239.91，也不满足E1的连续走弱背景。E2同样没有先行E1背景，不能仅因此前收回过突破线又跌回就启动。',
        '该处有效15分钟HL仍是08:15生效的78,026.42，未被跌破；未拿以后09:30大涨来倒选持有。直到原14:05退出前，E1与E2均未触发。保留09:40卖25%净+103.53，14:05卖余75%净+1,350.96，合计+1,454.49。', '',
        '## 逐根决策轨迹（不省略）','','以下沿用原0.1持有路径并列展示两种假设；E1触发之后的行情只供独立E2对照，不再属于E1持仓。E2触发之后也仅为原行情对照。','']
    for c in r['cases']:
        lines +=[f"### #{c['trade_id']}",'',
            '| 完整K线开始 | 确认时间 | H／L／C | 连降次数 | 低于原突破 | 方向／非内包合格 | E2状态 |',
            '| --- | --- | --- | ---: | --- | --- | --- |']
        for t in c['trace']:
            direction=t['red'] and t['not_above_previous_close'] and not(t['full_inside'] or t['body_inside'])
            lines.append(f"| {clock(t['bar_time'])} | {clock(t['confirmed_at'])} | {t['high']:,.4f}／{t['low']:,.4f}／{t['close']:,.4f} | {t['consecutive_down_comparisons']} | {'是' if t['below_original_trigger'] else '否'} | {'是' if direction else '否'} | {t['B_stage']} |")
    lines+=['','## 范围与限制','',
        '两种候选在这对案例上均帮助#32且未误伤#30，但这是反复审查后的同一样本，不是充分验证，不能声称整月收益增加521.32或402.42，也不能把两者改善相加。候选没有接入0.1，原月度38笔、净+3,516.46及全部表格、源码快照、最新／ACTIVE指针均保留。',
        '后续若研究推广，需要先检查其他盈利交易及不同月份，再研究完整顺序中的占仓变化；本轮未做。所有价位是BTC真实分钟参考加ETF零佣金／每边2bps成本模型，非ETF真实成交；缺失分钟不补值，秒内执行及真实滑点未验证。']
    return '\n'.join(lines)+'\n'


def main():
    paths=[STORE/'latest_run.json',STORE/'releases/ACTIVE.json']+list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))+list((STORE/'runs').glob('*/WORKBOOK_DATA.json'))+list((STORE/'releases/0.1').rglob('*'))
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and '__pycache__' not in str(p)}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=review();save(DEST,r)
    (ROOT/'docs/investigations/2026-11-09_BTC_RELEASE_0_1_EARLY_FAILURE.md').write_text(report(r))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
    print(json.dumps([dict(trade=c['trade_id'],alternatives={k:{f:p.get(f) for f in ('triggered','exit_time','exit_price','gross','cost','net','net_change')} for k,p in c['alternatives'].items()}) for c in r['cases']],indent=2))


if __name__=='__main__':main()
