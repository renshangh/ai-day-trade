"""Extend one approved evening position beyond its frozen 01:45 checkpoint."""
import copy
import csv
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,iso,ts,save
from trading_desk.btc_guarded_replay import POLICY
from audit_btc_oct12_b_branches import FOLDER,BASELINE,load,local
from audit_btc_oct12_profit_guard import engine_for_case

BASE=FOLDER.parent/'oct12_approved_profit_guard/REVIEW.json'
OUTPUT=FOLDER.parent/'oct12_night_continuation'
CHECKPOINT=ts('2026-10-13T01:45:00-04:00')


def turning_candidates(position,rows):
    """User's new-high failure idea, evidence only; never changes exit legs."""
    by={b['t']:b for b in rows};candidates=[];without_new_high=[]
    for d in position['last_minute_observations']:
        context=d['context']
        if not context:continue
        prev=by.get(context['previous_bar_start'])
        if not prev or prev['observed_minutes']!=15 or prev['close']<=prev['open']:continue
        price=d['reference_price'];midpoint=(prev['high']+prev['low'])/2
        if (price>=midpoint or price>=d['opening_15m'] or not d['direction_passed']
                or d['inside_exempt']):continue
        gross=.75*(price-position['entry']);cost=.75*(price+position['entry'])*.0002
        evidence=dict(time_utc=d['time_utc'],bar_start=iso(ts(d['time_utc'])//900*900),
            reference_price=price,previous_high=prev['high'],previous_low=prev['low'],
            previous_open=prev['open'],previous_close=prev['close'],previous_midpoint=midpoint,
            observed_current_high=d['observed_high'],current_open=d['opening_15m'],
            new_wave_high=d['new_wave_high'],red_at_observation=True,non_inside=True,
            prior_range_retracement=(prev['high']-price)/(prev['high']-prev['low']),
            prior_body_retracement=(prev['close']-price)/(prev['close']-prev['open']),
            hypothetical_net_75=gross-cost,hypothetical_total_net=gross-cost+position['legs'][0]['net'],
            approved=False,is_actual_policy_exit=False,
            condition='last-minute current new wave high + below prior bullish candle midpoint + red + direction + non-inside')
        without_new_high.append(evidence)
        if evidence['new_wave_high']:candidates.append(evidence)
    return dict(with_new_high=candidates,without_new_high_filter=without_new_high,
        approved=False,actual_policy_unchanged=True)


def review():
    source,minutes=load()
    baseline=json.loads(BASE.read_text())
    if baseline['policy']!=POLICY:raise ValueError('Current rule differs from the original checkpoint policy')
    # Pin the historical V4 dispatcher selection; its two strategy modules
    # remain byte-identical even when the public factory gains a new default.
    for name in ('btc_guarded_replay.py','btc_structure_exits.py'):
        relative='trading_desk/'+name
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=baseline['code_sha256'][relative]:
            raise ValueError(f'Rule code changed since checkpoint: {relative}')
    old=next(c for c in baseline['cases'] if c['nominated_bar'].endswith('21:00:00-04:00'))
    if ts(old['cutoff'])!=CHECKPOINT or old['trade']['remaining']!=.75:
        raise ValueError('Expected original 01:45 checkpoint holding 75%')
    entry_at=ts(old['trade']['entry_time']);nominated=ts(old['nominated_bar'])
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=engine_for_case(nominated,minutes[-1]['t']+60,db)
    if e.policy!=baseline['policy']:raise ValueError('Historical continuation policy not pinned')
    apply=e.apply_exits;checkpoint_state=None
    def capture_before_decision(b):
        nonlocal checkpoint_state
        if b['t']==CHECKPOINT:
            # Natural boundary processing has already completed 01:30--01:45.
            # Capture before the first 01:45 decision, never resume a finish()-
            # mutated engine or insert a new entry at the checkpoint.
            checkpoint_state=copy.deepcopy(e.position)
        return apply(b)
    e.apply_exits=capture_before_decision
    for b in minutes:
        e.minute(b)
        if e.trades:break
    if checkpoint_state is None:raise ValueError('Original checkpoint was not reached')
    for key in ('entry_time','entry','initial_stop','t1','t2','remaining','legs','structure_reference',
                'structure_history','active_wave_high','armed_midpoint','giveback_state'):
        if checkpoint_state.get(key)!=old['trade'].get(key):
            raise ValueError(f'Checkpoint changed before continuation: {key}')
    result=e.finish()
    if len(result['trades'])!=1:raise ValueError('Expected the same one position')
    p=result['trades'][0]
    if p['status']!='closed':raise ValueError('Archived data ended without exit; do not force a fill')
    exit_at=ts(p['exit_time'])
    if exit_at<CHECKPOINT:raise ValueError('Position closed before original checkpoint')
    observed=[b for b in minutes if entry_at<=b['t']<=exit_at]
    if [b['t'] for b in observed]!=list(range(entry_at,exit_at+60,60)):
        raise ValueError('Missing position minutes; cannot assert earliest exit across a gap')
    if p['legs'][:len(old['trade']['legs'])]!=old['trade']['legs']:
        raise ValueError('Original first 25% exit changed')
    if sum(l['fraction'] for l in p['legs'])!=1:raise ValueError('Duplicate or incomplete exits')
    rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t',(nominated,))]
    db.close()
    for row in rows:
        row['observed_end_exclusive']=iso(min(row['t']+900,e.last_t+60))
        row['is_complete']=row['observed_minutes']==15 and row['t']+900<=e.last_t+60
        row['partial_reason']=None if row['is_complete'] else 'study stops after actual exit minute; no later observations used'
    continued=[d for d in p['giveback_observations'] if ts(d['time_utc'])>=CHECKPOINT]
    peak=p['giveback_observations'][-1]['highest_known_price']
    last=p['legs'][-1];trigger_giveback=(peak-last['price'])/(peak-p['entry'])
    gross=sum(l['gross'] for l in p['legs']);cost=sum(l['cost'] for l in p['legs'])
    case=dict(nominated_bar=old['nominated_bar'],cutoff=iso(exit_at+60),trade=p,rows=rows,
        realized_gross=gross,realized_cost=cost,realized_net=sum(l['net'] for l in p['legs']),
        checkpoint_unchanged=True,parameters_unchanged=True)
    return dict(status='complete',policy=POLICY,rule_approved=True,source=source,
        base_report_sha256=hashlib.sha256(BASE.read_bytes()).hexdigest(),
        rule_code_unchanged=True,
        checkpoint=iso(CHECKPOINT),checkpoint_state=checkpoint_state,case=case,
        continuation_rows=[b for b in rows if b['t']>=CHECKPOINT],
        structure_updates=[h for h in p['structure_history'] if h['effective_at']>=CHECKPOINT],
        exit_minute=next(b for b in observed if b['t']==exit_at),
        trigger_evidence=p['case_exit_evidence'][-1],trigger_giveback_fraction=trigger_giveback,
        turning_bar_review=turning_candidates(p,rows),
        continuation_max_open_giveback=max(d['giveback_fraction'] for d in continued if d['armed']),
        minute_coverage=dict(full_position=len(observed),continuation=sum(b['t']>=CHECKPOINT for b in observed),missing=0),
        costs=baseline['costs'],month_rerun=False,broker_orders=0,paper_orders=0,orders_enabled=False,
        code_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in
            (Path(__file__).resolve(),ROOT/'trading_desk/btc_guarded_replay.py',ROOT/'trading_desk/btc_structure_exits.py')})


def report(r):
    c=r['case'];p=c['trade'];e=r['trigger_evidence'];m=r['exit_minute'];anchor=e.get('structure')
    out=['# BTC 10月12日晚盘：01:45后余75%的退出复核','',
        '沿用已批准规则，从原01:45状态继续同一持仓，核对最早退出及整笔盈亏。','',
        'Last Updated: 2026-11-08  ','Status: 已平仓单例；规则与原检查点未变；未重跑整月  ',
        'Audience: Trading Desk使用者及研究维护者','', '## Overview','',
        '所有时间为纽约EDT（UTC−4）。从同一原入场自然逐分钟回放，验证01:45决策前的持仓、已知高点、启用状态、结构和原25%止盈与旧归档逐项相同，再继续至首次退出。不把01:45当成新入场，也不重置1R或累计高点。',
        '', '## 时间、价格和整笔盈亏','',
        f"原入场：2026年10月12日21:00–21:01，参考{p['entry']:,.6f}；原初始硬止损{p['initial_stop']:,.9f}。每笔按初始1 BTC归一化。",'',
        '| 事件 | 时间区间（纽约） | 价格参考 | 初始仓位比例 | 毛盈亏 | 价差／滑点成本 | 净盈亏 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    labels={'target_25':'首次目标止盈','structure_exit_remaining':'确认结构破位，退出余仓'}
    for l in p['legs']:
        out.append(f"| {labels.get(l['reason'],l['reason'])} | {local(l['time_utc'])}–{local(ts(l['time_utc'])+60)[11:16]} | {l['price']:,.9f} | {l['fraction']:.0%} | {l['gross']:,.6f} | {l['cost']:,.6f} | {l['net']:,.6f} |")
    out.append(f"| 整笔合计 | 首次退出后剩余0% | — | 100% | {c['realized_gross']:,.6f} | {c['realized_cost']:,.6f} | **{c['realized_net']:,.6f}** |")
    out+=['', '模型每边2bps，零佣金假设；不是ETF实际成交。原01:45浮盈估值保留作历史检查点，本次已平仓净盈亏不再叠加该旧浮盈。',
        '', '## 为什么最早是04:50，而非等待50%回吐','',
        f"退出分钟实际O={m['open']:,.6f}、H={m['high']:,.6f}、L={m['low']:,.6f}、C={m['close']:,.6f}。开盘高于已生效结构{last_price(p):,.6f}，最低价跌破该参考，因此触发所在区间为04:50–04:51，模型下穿参考价{last_price(p):,.6f}。无法从1分钟OHLC验证精确秒或保证实盘成交于此价。",
        f"当时事先已知最高价{p['giveback_observations'][-1]['highest_known_price']:,.6f}，按结构退出参考计算仅回吐约{r['trigger_giveback_fraction']:.4%}最大浮盈；04:50首价的回吐约{p['giveback_observations'][-1]['giveback_fraction']:.4%}，未满足50%。结构破位是独立保护，先触发即退出，不要求同时满足浮盈回吐规则。",'',
        '此前01:45至04:49，没有更早有效结构破位、硬止损、合格长上影或全部条件满足的浮盈退出。中点下穿只预警，不触发卖出。',
        '', '## 结构参考何时上移','',
        '| 回踩K线 | 实际低点时间／价格 | 右侧确认完成 | 突破此前高点的完整K线 | 生效时点 |',
        '| --- | --- | --- | --- | --- |']
    for h in r['structure_updates']:
        out.append(f"| {local(h['t'])} | {local(h['low_time'])}／{h['price']:,.6f} | {local(h['known_at'])} | {local(h['breakout_bar'])}，{local(h['breakout_known_at'])[11:16]}完整可知；越过{h['prior_peak']:,.6f} | {local(h['effective_at'])} |")
    out+=['',
        '02:00低点83,475.153在02:30已确认，03:00低点83,550.7475在03:30已确认；两者都要等03:30–03:45这根完整突破此前83,816.20后，才在03:45取得上移资格。程序同一时点依次检查，最终启用较高的83,550.7475；中间较低参考没有单独交易窗口。',
        '03:44的长上影观察价仍为绿线且高于前收盘，因而不退出。04:16、04:30中点下穿只预警。后续真实低点在04:50才首次跌破有效结构。原硬止损没有因为这项结构退出而改写。',
        '', '## 01:45后的逐根行情','',
        '最后一行是04:45–05:00名义K线，但本次只观测到04:50分钟结束（04:51），实际6/15分钟；其C只是04:50分钟收盘，不是05:00完整收盘。不读取余9分钟来决定04:50退出。','',
        '| 15分钟名义区间 | O / H / L / 当前C | 实际分钟／完整性 | 事件 |',
        '| --- | --- | --- | --- |']
    names={'structure_reference_raised':'结构参考上移','structure_exit_remaining':'结构破位，退余75%',
        'midpoint_warning':'中点预警，不卖','wick_wait':'长上影未过条件，不卖','giveback_exit_remaining':'浮盈保护退出'}
    for b in r['continuation_rows']:
        events='；'.join(f"{local(x['time_utc'])[11:16]} {names[x['type']]}"+(f" @ {x['price']:,.6f}" if x.get('price') is not None else '') for x in b['events'] if x['type'] in names)
        coverage=f"{b['observed_minutes']}/15；"+('完整' if b['is_complete'] else f"仅至{local(b['observed_end_exclusive'])[11:16]}")
        out.append(f"| {local(b['t'])}→{local(b['t']+900)[11:16]} | "+' / '.join(f"{b[k]:,.6f}" for k in ('open','high','low','close'))+f" | {coverage} | {events or '无退出，继续持有'} |")
    out+=['', '## 用户指出的04:30转弱K线：另列候选，不改现行结果','',
        '用户确认指04:15–04:30这根。这里的50%是前一根上涨K线的局部涨幅／振幅回撤，区别于已批准的“自入场以来最大浮盈回吐50%”。04:15–04:30是大实体阴线，上影几乎为零，原长上影条件不会触发。',
        '建议明确补充“当前这根先创持仓波段新高”作为冲高失败候选条件：本根在最后1分钟观察时，先创新高、回到前根完整上涨K线中点下方、当时收阴、不高于前收盘且非内包。只观察当时已有14根分钟和当前首价，不看最终收盘。',
        '', '| 候选观察 | 新高？ | 前根完整中点 | 当时价格 | 前根振幅回撤 | 条件性余75%净盈亏 | 条件性整笔净盈亏 |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for d in r['turning_bar_review']['without_new_high_filter']:
        out.append(f"| {local(d['time_utc'])} | {'是' if d['new_wave_high'] else '否'} | {d['previous_midpoint']:,.6f} | {d['reference_price']:,.6f} | {d['prior_range_retracement']:.4%} | {d['hypothetical_net_75']:,.6f} | {d['hypothetical_total_net']:,.6f} |")
    out+=['',
        '不加本根创新高条件，同样“红线＋跌过前根中点＋非内包”会在01:44先触发；不能事后跳过。加入本根先创新高，首次候选是04:29首价83,835.33，位于04:15–04:30这根内，前根全振幅回撤76.28%、实体涨幅回撤77.21%。该价不是04:15最高价，也不是已经提交的卖单。',
        '若采用该新增候选，余75%条件性净收益约+1,803.78，整笔约+2,186.80；现行已批准程序仍在04:50结构破位退出，净+1,973.40。新增冲高失败候选尚未接入，不能把两条路径拼成一次已实现交易。',
        '', '## 来源与保留范围','',
        f"复用真实Alpaca分钟SHA256 `{r['source']['sha256']}`。原入场至退出分钟共{r['minute_coverage']['full_position']}个连续观测，续核部分{r['minute_coverage']['continuation']}个；缺失0，不补值。",
        '保存为独立续核JSON和CSV；原01:45检查点、早盘、所有旧研究、月度结果及latest_run均不覆盖。策略和参数没有变化，没有重跑整月，没有真实或paper订单。']
    return '\n'.join(out)+'\n'


def last_price(p):return p['legs'][-1]['price']


if __name__=='__main__':
    paths=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json']+list(FOLDER.parent.glob('*/REVIEW.json'))
    paths=[p for p in paths if p.parent!=OUTPUT]
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):raise ValueError('Historical artifact changed')
    if dirs!=sorted(p.name for p in (STORE/'runs').iterdir()):raise ValueError('Monthly run created')
    r['prior_artifact_sha256']={str(p.relative_to(ROOT)):h for p,h in before.items()}
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',r)
    with (OUTPUT/'EXITS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['reason','time_ny','price','fraction','gross','cost','net']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for l in r['case']['trade']['legs']:writer.writerow({k:l[k] for k in fields})
    with (OUTPUT/'LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['start_ny','nominal_end_ny','observed_end_exclusive_ny','observed_minutes','is_complete','open','high','low','close','remaining','events']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for b in r['continuation_rows']:
            writer.writerow(dict(start_ny=local(b['t']),nominal_end_ny=local(b['t']+900),observed_end_exclusive_ny=local(b['observed_end_exclusive']),
                **{k:b[k] for k in ('observed_minutes','is_complete','open','high','low','close','remaining')},events=json.dumps(b['events'],ensure_ascii=False)))
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_NIGHT_CONTINUATION.md').write_text(report(r))
    print(json.dumps(dict(exit=r['case']['trade']['exit_time'],legs=r['case']['trade']['legs'],net=r['case']['realized_net'],trigger_giveback=r['trigger_giveback_fraction'])))
