"""Apply unchanged E1/E2 to all 38 fixed release-0.1 entries, never replay strategy."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import aggregate
from scripts.audit_btc_release01_early_failure import completed_scan,value_exit,clock,RUN

DEST=STORE/'investigations/RELEASE_0_1_E1_E2_FIXED38.json'


def load_frozen_source():
    release=STORE/'releases/0.1';r=read(release/'results/result.json')
    assert r['run_id']==RUN and len(r['trades'])==38
    digest=hashlib.sha256();minutes={}
    with gzip.open(release/'data/MINUTES.jsonl.gz','rb') as f:
        for raw in f:
            digest.update(raw);t,o,h,l,c,v,n,vw=json.loads(raw)
            assert t not in minutes
            minutes[t]=dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n)
    assert digest.hexdigest()==r['source_minute_sha256']
    return r,minutes,digest.hexdigest()


def fixed_case(p,source):
    floor=ts(p['entry_time'])//900*900;start=floor-900;end=(ts(p['exit_time'])//900+1)*900
    raw=[source[t] for t in range(start,end,60) if t in source]
    bars=[]
    for t in range(start,end,900):
        obs=[source[k] for k in range(t,t+900,60) if k in source]
        if not obs:continue
        b=aggregate(obs,900)
        bars.append(dict(time=iso(t),end=iso(t+900),open=b['open'],high=b['high'],low=b['low'],close=b['close'],
            complete=[m['t'] for m in obs]==list(range(t,t+900,60)),observed_minutes=len(obs)))
    return dict(trade_id=p['id'],entry={k:copy.deepcopy(p[k]) for k in ('entry_time','entry','initial_stop','references','t1')},
        bars=bars,minutes=[dict(**m,time=iso(m['t'])) for m in raw],exit_time=p['exit_time'],legs=copy.deepcopy(p['legs']),net=p['net'],
        observed_minutes=len(raw),missing_minutes=(end-start)//60-len(raw))


def summarize(rows,key):
    available=[r for r in rows if r['alternatives'][key]['net'] is not None]
    missing=[r['trade_id'] for r in rows if r['alternatives'][key]['net'] is None]
    changed=[r for r in available if r['alternatives'][key]['triggered']]
    improved=[r['trade_id'] for r in changed if r['alternatives'][key]['net_change']>1e-8]
    worsened=[r['trade_id'] for r in changed if r['alternatives'][key]['net_change']< -1e-8]
    hurt_winners=[r for r in changed if r['baseline_net']>0 and r['alternatives'][key]['net_change']< -1e-8]
    rescued_losses=[r for r in changed if r['baseline_net']<0 and r['alternatives'][key]['net_change']>1e-8]
    return dict(count=len(rows),valued=len(available),missing_trade_ids=missing,triggered=len(changed),retained=len(rows)-len(changed)-len(missing),
        baseline_net_paired=sum(r['baseline_net'] for r in available),fixed_entry_net=sum(r['alternatives'][key]['net'] for r in available),
        net_change=sum(r['alternatives'][key]['net_change'] for r in available),improved_trade_ids=improved,worsened_trade_ids=worsened,
        hurt_original_winner_ids=[r['trade_id'] for r in hurt_winners],
        hurt_winner_delta=sum(r['alternatives'][key]['net_change'] for r in hurt_winners),
        winners_turned_loss=[r['trade_id'] for r in hurt_winners if r['alternatives'][key]['net']<0],
        helped_original_loss_ids=[r['trade_id'] for r in rescued_losses],
        helped_loss_delta=sum(r['alternatives'][key]['net_change'] for r in rescued_losses),
        no_original_holding_gap_count=sum(not r['gap_exposed'] for r in available),
        no_original_holding_gap_delta=sum(r['alternatives'][key]['net_change'] for r in available if not r['gap_exposed']),
        wins=sum(r['alternatives'][key]['net']>0 for r in available),losses=sum(r['alternatives'][key]['net']<0 for r in available),
        total_cost=sum(sum(l['cost'] for l in r['alternatives'][key]['legs']) for r in available),
        biggest_hurt_winner=next(iter(sorted(hurt_winners,key=lambda r:r['alternatives'][key]['net_change'])),None))


def review():
    original,source,digest=load_frozen_source();rows=[]
    rules=read(STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json')
    for p in original['trades']:
        case=fixed_case(p,source)
        # Original final exit takes precedence at an identical minute. We only
        # attribute strictly earlier candidate exits, never invent a later hold.
        scan=completed_scan(case,cutoff=ts(p['exit_time'])-1)
        alternatives={}
        held_missing=[t for t in range(ts(p['entry_time']),ts(p['exit_time'])+60,60) if t not in source]
        for internal,name in [('A','E1'),('B','E2')]:
            q=value_exit(case,scan[internal])
            q['candidate_name']=name
            valued_exit=ts(q['exit_time']) if q.get('exit_time') else ts(p['exit_time']) if not q['triggered'] else None
            q['missing_held_minutes_before_exit']=(sum(t<=valued_exit for t in held_missing) if valued_exit is not None else None)
            q['exit_precedes_original_gap']=bool(q['triggered'] and valued_exit is not None and held_missing and valued_exit<held_missing[0])
            if not q['triggered']:
                q.update(exit_time=p['exit_time'],interval_end=iso(ts(p['exit_time'])+60),exit_price=p['legs'][-1]['price'],
                    remaining=p['legs'][-1]['fraction'],gross=sum(l['gross'] for l in p['legs']),cost=sum(l['cost'] for l in p['legs']),minutes_earlier=0)
            q['same_minute_original_leg']=q['triggered'] and q.get('exit_time') is not None and any(l['time_utc']==q['exit_time'] for l in p['legs'])
            q['original_winner_hurt']=p['net']>0 and q['net_change'] is not None and q['net_change']< -1e-8
            q['original_winner_turned_loss']=p['net']>0 and q['net'] is not None and q['net']<0
            alternatives[name]=q
        rows.append(dict(trade_id=p['id'],entry_rule=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],
            initial_stop_effective=p['entry_time'],baseline_exit=p['exit_time'],baseline_exit_price=p['legs'][-1]['price'],
            baseline_net=p['net'],baseline_gross=sum(l['gross'] for l in p['legs']),baseline_cost=sum(l['cost'] for l in p['legs']),
            baseline_legs=copy.deepcopy(p['legs']),baseline_winner=p['net']>0,original_d=p['references']['l1'],
            gap_exposed=p['gap_exposed'],context_partial=p['context_partial'],slice_observed_minutes=case['observed_minutes'],
            slice_missing_minutes=case['missing_minutes'],baseline_missing_held_minutes=[iso(t) for t in held_missing],alternatives=alternatives,trace=scan['trace']))
    summary={key:summarize(rows,key) for key in ('E1','E2')}
    return dict(source_run=RUN,source_minute_sha256=digest,source='frozen release 0.1 actual Alpaca minute stream',
        review_date='2026-11-09',timezone='America/New_York',rows=rows,summary=summary,
        baseline=dict(count=38,wins=19,losses=19,net=sum(p['net'] for p in original['trades']),
            total_cost=sum(l['cost'] for p in original['trades'] for l in p['legs'])),
        definitions=rules['definitions'],candidate_labels=dict(E1='连续走弱',E2='收复失败确认'),
        rule_source_sha256=hashlib.sha256((ROOT/'scripts/audit_btc_release01_early_failure.py').read_bytes()).hexdigest(),
        original_two_case_study_sha256=hashlib.sha256((STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json').read_bytes()).hexdigest(),
        scope='38 fixed original entries, two independent alternative exit overlays; not a strategy/monthly replay',
        original_exit_tie_policy='Only strictly earlier confirmation can override; same original final-exit minute retains baseline; earlier T1 legs retained, identical-minute target excluded under candidate-opening risk priority',
        month_rerun=False,strategy_engine_created=False,release_modified=False,rules_modified=False,orders_enabled=False)


def report(r):
    lines=['# BTC 0.1：全部38笔固定入场E1／E2退出对照','',
        '保持原入场、保护和成本，逐笔核对两种原样候选对亏损及盈利交易的影响。','',
        'Last Updated: 2026-11-09  ','Status: 38笔固定入场对照完成；未采用候选、未重跑整月策略  ',
        'Audience: 交易学习手册使用者及交易桌维护者','','## Overview','',
        f"基准`{RUN}`：38笔，19胜19负，净+${r['baseline']['net']:,.2f}／每笔初始1 BTC。读取0.1冻结的真实分钟流，源SHA256 `{r['source_minute_sha256']}` 与原记录完全一致；没有补值或行情更新。",
        '本轮E1／E2函数及判定不改，只把同一定义用于全部38笔。没有选择新的入场、重建持仓顺序或调用策略引擎，因此下面的合计只是固定原入场的退出归因，不能称为新的整月策略收益。', '',
        '## 固定定义与时间口径','',
        '- E1：两次相邻完整15分钟K线同时降低最高、最低，共3根作比较；收阴、≤前收、非实体及全振幅内包，收盘失守原突破价。下一实际分钟首价估算退出。',
        '- E2：先有上述背景，之后完整收复原突破价、完整再次失守、紧接下一根继续降高降低及方向／非内包确认；下一实际分钟首价估算退出。',
        '- 所有15分钟条件到区间结束才已知。E1/E2独立比较，不把两次退出叠加；保留更早已经发生的25%退出，候选退出当时实际余仓。',
        '- 候选必须严格早于原最终退出。同一最终退出分钟保留原0.1；候选开盘与原目标同分钟时不假装知道秒内目标先后，按候选开盘风险退出优先并另作标记。',
        '- 缺失分钟不填补。缺少估价首价时退出价和盈亏留空，仅在有估值的成对样本上比较。', '',
        '## 全38笔固定入场合计','',
        '| 指标 | 0.1原退出 | E1 | E2 |','| --- | ---: | ---: | ---: |']
    a=r['summary']['E1'];b=r['summary']['E2']
    for label,old,x,y in [('有估值笔数',38,a['valued'],b['valued']),('提前退出笔数',0,a['triggered'],b['triggered']),
        ('盈利笔数',19,a['wins'],b['wins']),('亏损笔数',19,a['losses'],b['losses']),
        ('原盈利交易被减利笔数',0,len(a['hurt_original_winner_ids']),len(b['hurt_original_winner_ids']))]:lines.append(f'| {label} | {old} | {x} | {y} |')
    lines +=[f"| 固定入场净额 USD | {r['baseline']['net']:+,.2f} | {a['fixed_entry_net']:+,.2f} | {b['fixed_entry_net']:+,.2f} |",
        f"| 相对各自成对0.1净差 USD | — | {a['net_change']:+,.2f} | {b['net_change']:+,.2f} |", '',
        '## 盈利交易是否被过早退出','',
        '| 候选 | 原盈利被减利 | 盈转亏 | 减利合计 | 原亏损减亏合计 |',
        '| --- | --- | --- | ---: | ---: |']
    for key,s in r['summary'].items():lines.append(f"| {key} | {s['hurt_original_winner_ids']} | {s['winners_turned_loss']} | {s['hurt_winner_delta']:+,.2f} | {s['helped_loss_delta']:+,.2f} |")
    lines +=['',f"数据限制：原#12持有后段缺失7分钟（10月24日02:42、02:43、02:44、02:45、02:46、02:47、02:49 EDT）。E1于10月23日20:45、E2于10月24日00:30均在缺口前退出；相对原退出的差额仍属于带缺口基准的条件估算。无原持有缺口子集{a['no_original_holding_gap_count']}笔中，E1净差+{a['no_original_holding_gap_delta']:,.2f}、E2净差+{b['no_original_holding_gap_delta']:,.2f}；不能仅凭包含#12的总额选择更优候选。"]
    lines+=['','## 逐笔退出时间、价格与盈亏','',
        '时间均为纽约时间，保留EDT／EST以处理夏令时。价格为最终余仓退出价；若此前已卖25%，整笔净额包含其已实现净盈亏。完整分腿与确认依据见交易桌展开项和独立对照表。','',
        '| #／入口 | 原入场时间／价 | 原最终退出时间／价／整笔净额 | E1确认→退出／价／整笔净额／差额 | E2确认→退出／价／整笔净额／差额 |',
        '| --- | --- | --- | --- | --- |']
    def outcome(p):
        if p['net'] is None:return '确认存在，但下一分钟缺失，估值留空'
        return f"{'确认'+clock(p['signal']['confirmed_at'])+' → ' if p['triggered'] else '未触发；保留原退出 '}{clock(p['exit_time'])}／{p['exit_price']:,.4f}／{p['net']:+,.2f}／差{p['net_change']:+,.2f}"
    for row in r['rows']:
        lines.append(f"| {row['trade_id']}／{row['entry_rule']} | {clock(row['entry_time'])}／{row['entry']:,.4f} | {clock(row['baseline_exit'])}／{row['baseline_exit_price']:,.4f}／{row['baseline_net']:+,.2f} | {outcome(row['alternatives']['E1'])} | {outcome(row['alternatives']['E2'])} |")
    lines+=['','## 所有被提前退出的原盈利交易：不只看减亏','',
        '| 候选／原交易# | 原净盈亏 | 候选退出时间／价 | 候选整笔净盈亏 | 差额 |',
        '| --- | ---: | --- | ---: | ---: |']
    hurt=0
    for row in r['rows']:
        for key,p in row['alternatives'].items():
            if p['original_winner_hurt']:
                hurt+=1;lines.append(f"| {key}／#{row['trade_id']} | {row['baseline_net']:+,.2f} | {clock(p['exit_time'])}／{p['exit_price']:,.4f} | {p['net']:+,.2f} | {p['net_change']:+,.2f} |")
    if not hurt:lines.append('| 本样本未出现 | — | — | — | — |')
    lines+=['','## 解释与限制','',
        '原#30在两种候选下的结果必须保持上一轮对照：没有提前退出、仍净+1,454.49；这不保证其他盈利交易不会被误伤。候选带来的减亏、减利及信号缺失均完整展示，不按盈亏选择性排除交易。',
        '没有参数搜索、改变止损／目标、缩小仓位或补齐缺失行情。源研究函数哈希保存，原两笔报告保留。若将来研究完整顺序，提前退出后新增的入场机会、现金和持仓占用都可能改变；本轮未做。',
        '同一月份已多次用于研究，所有候选仍属于样本内；不能只看固定入场合计就宣称可执行收益或升级0.1。零佣金加每边2bps为ETF成本假设，实际分钟可能包含报价参考，未验证秒级真实成交。']
    return '\n'.join(lines)+'\n'


def main():
    paths=[STORE/'latest_run.json',STORE/'releases/ACTIVE.json',STORE/'investigations/RELEASE_0_1_EARLY_FAILURE.json']+list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))+list((STORE/'runs').glob('*/WORKBOOK_DATA.json'))+list((STORE/'releases/0.1').rglob('*'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and '__pycache__' not in str(p)}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=review();save(DEST,r)
    (ROOT/'docs/investigations/2026-11-09_BTC_RELEASE_0_1_E1_E2_FIXED38.md').write_text(report(r))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
    print(json.dumps(dict(baseline=r['baseline'],summary={k:{f:v for f,v in x.items() if f!='biggest_hurt_winner'} for k,x in r['summary'].items()}),indent=2))


if __name__=='__main__':main()
