"""Single October 12 evening entry, observed only through October 13 01:45."""
import csv
from dataclasses import replace
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,iso,ts,save
from trading_desk.btc_structure_exits import StructureExitMixin,POLICY,giveback_diagnostic
from audit_btc_oct12_b_branches import NominatedCase,FOLDER,BASELINE,load,local

OUTPUT=FOLDER.parent/'oct12_structure_exit'
NOMINATED=ts('2026-10-12T21:00:00-04:00')
CUTOFF=ts('2026-10-13T01:45:00-04:00')


class Case(StructureExitMixin,NominatedCase):
    def __init__(self,db):
        super().__init__(NOMINATED,db,exit_policy='approved')
        self.end=CUTOFF
        self.cfg=replace(self.cfg,version=POLICY)


def review():
    source,minutes=load()
    old=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][1]['trade']
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=Case(db)
    for b in minutes:
        if b['t']>=CUTOFF:break
        engine.minute(b)
    result=engine.finish()
    if len(result['trades'])!=1:raise ValueError('Expected the single nominated entry only')
    p=result['trades'][0]
    for key in ('entry','entry_time','initial_stop','t1','t2'):
        if p[key]!=old[key]:raise ValueError(f'Unrequested change: {key}')
    if any(l['reason'] in ('target_remaining','midpoint_exit_all') for l in p['legs']):
        raise ValueError('Disabled midpoint/T2 created an exit')
    rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t',(NOMINATED,))]
    db.close()
    observed=[b for b in minutes if NOMINATED<=b['t']<CUTOFF]
    if [b['t'] for b in observed]!=list(range(NOMINATED,CUTOFF,60)):
        raise ValueError('Missing case minutes: do not fill or silently assume survival')
    prev=None
    for row in rows:
        body=sorted((row['open'],row['close']))
        pb=sorted((prev['open'],prev['close'])) if prev else None
        row['completed_colour']='green' if row['close']>row['open'] else 'red' if row['close']<row['open'] else 'doji'
        row['completed_full_inside']=bool(prev and row['high']<=prev['high'] and row['low']>=prev['low'])
        row['completed_body_inside']=bool(prev and body[0]>=pb[0] and body[1]<=pb[1])
        prev=row
    realized_gross=sum(l['gross'] for l in p['legs']);realized_cost=sum(l['cost'] for l in p['legs'])
    mark=observed[-1]['close'];q=engine.cfg.one_way_friction_bps/10000
    remaining=p['remaining'];gross=remaining*(mark-p['entry'])
    entry_cost=remaining*p['entry']*q;estimated_exit_cost=remaining*mark*q
    valuation=dict(as_of=iso(CUTOFF),source_minute=iso(observed[-1]['t']),price=mark,remaining=remaining,
        unrealized_gross=gross,allocated_entry_cost=entry_cost,
        unrealized_after_entry_cost=gross-entry_cost,estimated_future_exit_cost=estimated_exit_cost,
        hypothetical_roundtrip_net=gross-entry_cost-estimated_exit_cost,
        hypothetical_total_net=realized_gross-realized_cost+gross-entry_cost-estimated_exit_cost,
        is_exit=False,exit_cost_is_estimate=True)
    comparison=[]
    v2=json.loads((FOLDER.parent/'oct12_direction_filtered_exits/REVIEW.json').read_text())
    for c in v2['cases']:
        prior=c['trade'];checkpoint=ts(prior['exit_time'])
        minute=next(b for b in minutes if b['t']==checkpoint)
        diagnostic=giveback_diagnostic(prior['entry'],prior['initial_stop'],ts(prior['entry_time']),
            minute,minutes,prior['legs'][0]['price'])
        comparison.append(dict(nominated_bar=c['nominated_bar'],entry_rule='B1',
            checkpoint_basis='previous V2 exit checkpoint only; no new simulated sale',**diagnostic))
    return dict(status='complete',policy=POLICY,scope='one nominated evening entry only; opt-in case, not monthly default',
        source=source,cutoff=iso(CUTOFF),cutoff_ny=local(CUTOFF),nominated_bar=local(NOMINATED),
        trade=p,rows=rows,observed_case_minutes=len(observed),
        realized_gross=realized_gross,realized_cost=realized_cost,realized_net=realized_gross-realized_cost,
        valuation=valuation,month_rerun=False,broker_orders=0,orders_enabled=False,
        giveback_comparison=comparison,
        structure_definition='15m low below both complete adjacent lows; higher than retained reference; later complete bar exceeds prior rally high; activate only after both confirmations',
        costs='per initial 1 BTC; ETF zero commission plus 2bps each way; not actual ETF fills',
        code_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (Path(__file__).resolve(),ROOT/'trading_desk/btc_structure_exits.py')})


def report(r):
    p=r['trade'];v=r['valuation']
    out=['# BTC 10月12日晚盘：中点预警与15分钟结构退出','',
        '只复核21:00这笔至次日01:45，保留首笔25%止盈并让余75%跟随已确认结构。','',
        'Last Updated: 2026-11-08  ','Status: 单例研究；截至观察终点仍持余75%；未重跑整月  ',
        'Audience: Trading Desk使用者及研究维护者','', '## Overview','',
        '所有时间为纽约EDT（UTC−4）。用户选择15分钟结构确认后的低点破位作为余仓退出依据。本次不是按事后最高价选卖点，也没有在观察终点强行平仓。',
        '', '## 本次执行口径','',
        '1. 中点仍按盘中下穿记录，但只作预警，绝不产生卖出。预警本身不要求当前转红。',
        '2. T1及首笔25%比例保持不变；固定T2保留作历史参考但不再执行。',
        '3. 15分钟回踩低点须低于左右各一根完整K线的低点，且高于保留参考；只有其后的完整K线突破回踩前已知的整段反弹高点，才可启用该新结构参考。左右确认和创新高证据两项都已知时生效，不能提前引用候选低点。',
        '4. 盘中严格跌破已生效结构参考，退出实际全部余仓（通常75%）；跳空则用已观察开盘。该结构参考是原价低点，不新增缓冲参数，也不改原初始硬止损。',
        '5. 原无整数关口长上影仍在最后1分钟、只用前14分钟和当前首价判断；保留当时非绿且不高于前收盘条件。观察实体或全振幅仍在前根内部，形态本身不卖。内包并不豁免真实结构破位或硬止损。没有新增“小实体”比例阈值。',
        '6. 同分钟先后不明按原风险优先精神：硬止损→已确认结构破位→目标，并标记歧义，不虚构成交秒；只处理实际余仓。',
        '', '## 入场与退出／估值','',
        '| 事件 | 时间或区间 | 参考价格 | 初始仓位比例 | 毛盈亏 | 成本／净盈亏 |',
        '| --- | --- | ---: | ---: | ---: | --- |',
        f"| 入场 | 10/12 {local(p['entry_time'])[11:16]}–{local(ts(p['entry_time'])+60)[11:16]} | {p['entry']:,.6f} | 100% | — | 假设成交，非真实订单 |",
        f"| 初始硬止损生效 | 入场后立即 | {p['initial_stop']:,.9f} | 保护当时余仓 | — | 原0.25 ATR缓冲及成本不变 |"]
    for l in p['legs']:
        out.append(f"| 首次目标止盈 | {local(l['time_utc'])}–{local(ts(l['time_utc'])+60)[11:16]} | {l['price']:,.9f} | {l['fraction']:.0%} | {l['gross']:,.6f} | 摩擦{l['cost']:,.6f}；已实现净{l['net']:,.6f} |")
    out += [f"| 余仓未退出，观察截止估值 | {r['cutoff_ny']} | {v['price']:,.6f}，最后实际分钟收盘 | {p['remaining']:.0%} | 未实现{v['unrealized_gross']:,.6f} | 仅扣分摊买入摩擦后浮盈{v['unrealized_after_entry_cost']:,.6f}；无卖出成交 |",'',
        f"**实际模型已实现净盈亏仅为+${r['realized_net']:,.2f}。** 余75%没有退出时间、退出成交价或已实现盈亏。若仅按01:45估值并预扣假设卖出摩擦，其净浮盈为+${v['hypothetical_roundtrip_net']:,.2f}；合计估值+${v['hypothetical_total_net']:,.2f}，均不是已平仓收益。",
        '', '## 结构参考的确认与生效','',
        '| 回踩所属K线 | 实际低点时间／价格 | 低点确认 | 新高证据完整可知 | 结构参考生效 |',
        '| --- | --- | --- | --- | --- |']
    for h in p.get('structure_history',[]):
        out.append(f"| {local(h['t'])} | {local(h['low_time'])}／{h['price']:,.6f} | {local(h['known_at'])} | {local(h['breakout_known_at'])}，突破此前{h['prior_peak']:,.6f} | {local(h['effective_at'])} |")
    out+=['', '这几次是新增的15分钟主动退出参考，不是把原1小时硬止损记录改写成15分钟。原硬止损在本笔观察期没有上移。',
        '', '## 为什么01:40没有退出','',
        '01:15–01:30低点83,508.87在01:30才固定；下一根01:30–01:45反而跌到83,485.7775，因此它没有通过右侧反弹确认，不是合格波段HL。',
        '01:40–01:41虽跌破83,508.87，跌破的只是前一根低点。此时已生效结构参考仍为01:00这根低点83,285.235（01:30起生效）；当前最低83,485.7775仍高于该参考约200.54美元。',
        '01:15–01:30长上影最后一分钟首价83,659.85高于本根开盘83,623.60，也高于前收盘83,625.44；当时为绿，不触发长上影退出。01:30中点下穿仅预警。',
        '', '## 新增诊断：早盘与晚盘的浮盈回吐差别','',
        '两笔原入场均为B1，不能用后来走势事后改写入场类型。这里仅在此前V2退出检查点比较持仓延续：浮盈回吐率＝（入场后当时已知高点−当前参考价）÷（当时已知高点−入场价）。',
        '只使用检查点之前完整分钟及当前首价／触发参考，不使用当前分钟尚未结束的H/L/C，也不使用同一15分钟K线后来才形成的最高价。最大浮盈未为正则不计算；很小时该比值不稳定。',
        '', '| 指定入场K线 | 检查点 | 当时已知高点 | 价格参考 | 浮盈回吐率 | 回撤／初始R |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for c in r['giveback_comparison']:
        out.append(f"| {c['nominated_bar'][11:16]} | {local(c['time_utc'])} | {c['highest_known_price']:,.6f} | {c['reference_price']:,.6f} | {c['giveback_fraction']:.4%} | {c['giveback_in_initial_r']:.6f}R |")
    out+=['', '早盘10:05时已知高点仅82,950，不能偷用10:00–10:15整根后来才完成的83,040.768。晚盘仅浅幅回吐。这里没有设50%或其他退出阈值，没有因此新增早盘模拟交易，也没有改写本笔结构退出。该指标用于讨论持仓管理，不能证明未来收益。',
        '', '## 逐根行情与处理','',
        '本表完整颜色和内包关系只能在该行结束后获知；实时退出依据仍使用当时可见数据。','',
        '| 15分钟开始→结束 | O / H / L / C | 完成后颜色／内包 | 当时事件 | 收盘后结构参考 |',
        '| --- | --- | --- | --- | --- |']
    labels={'entry':'入场','target_25':'卖25%止盈','midpoint_warning':'中点预警，不卖',
        'structure_reference_raised':'新结构参考生效','wick_wait':'长上影未过条件，持有',
        'midpoint_armed':'下一根中点预警参考开始生效','entry_skipped':'入场信号未新增仓位'}
    for b in r['rows']:
        events='；'.join(f"{local(e['time_utc'])[11:16]} {labels.get(e['type'],e['type'])}" for e in b['events'] if e['type'] in labels)
        h=b.get('case_structure_reference')
        inside='全根内包' if b['completed_full_inside'] else '实体内包' if b['completed_body_inside'] else '非内包'
        out.append(f"| {local(b['t'])}→{local(b['t']+900)[11:16]} | "+' / '.join(f"{b[k]:,.4f}" for k in ('open','high','low','close'))+f" | {b['completed_colour']}／{inside} | {events or '无退出，继续观察'} | {h['price'] if h else '尚无新增15m参考，初始硬止损保护'} |")
    out+=['', '## 来源与范围','',
        f"Alpaca真实分钟归档SHA256 `{r['source']['sha256']}`。入场至截止共{r['observed_case_minutes']}个连续实际分钟，没有补值；仅处理截止之前的分钟，不读取01:45以后走势作决策。",
        '本次规则是显式单例研究分支，不覆盖早盘、旧V1/V2或月度结果，不更改默认月度程序。JSON和逐根CSV存于`oct12_structure_exit/`，不提交真实或paper订单。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    watched=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json',
        FOLDER.parent/'oct12_approved_exits/REVIEW.json',FOLDER.parent/'oct12_direction_filtered_exits/REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    result=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):raise ValueError('Old artifact changed')
    if folders!=sorted(p.name for p in (STORE/'runs').iterdir()):raise ValueError('Monthly run created')
    result['prior_artifact_sha256']={str(p.relative_to(ROOT)):h for p,h in before.items()}
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',result)
    with (OUTPUT/'LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['time_ny','end_ny','open','high','low','close','completed_colour','completed_full_inside','completed_body_inside','structure_reference','remaining','events']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for b in result['rows']:
            row={k:b[k] for k in ('open','high','low','close','completed_colour','completed_full_inside','completed_body_inside','remaining')}
            row.update(time_ny=local(b['t']),end_ny=local(b['t']+900),
                structure_reference=(b.get('case_structure_reference') or {}).get('price'),events=json.dumps(b['events'],ensure_ascii=False))
            writer.writerow(row)
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_STRUCTURE_EXIT.md').write_text(report(result))
    print(json.dumps(dict(status=result['trade']['status'],legs=result['trade']['legs'],
        realized_net=result['realized_net'],valuation=result['valuation']),ensure_ascii=False))
