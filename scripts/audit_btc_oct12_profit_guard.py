"""Approved current replay policy on two fixed entries, never a monthly run."""
import copy
import csv
import hashlib
import inspect
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,iso,ts,save
from trading_desk.btc_engine import create_replay,Replay
from trading_desk.btc_guarded_replay import POLICY
from audit_btc_oct12_b_branches import FOLDER,BASELINE,load,local

OUTPUT=FOLDER.parent/'oct12_approved_profit_guard'
CUTOFFS=(ts('2026-10-12T11:00:00-04:00'),ts('2026-10-13T01:45:00-04:00'))


def engine_for_case(nominated,cutoff,db,*,exit_version='guarded_v4'):
    # Use the exact public factory selected by future A/B runs. Only its entry
    # permission is restricted to the already-frozen nominated candle.
    e=create_replay(ts('2026-10-12T00:00:00-04:00'),cutoff,db,expanded_b=True,exit_version=exit_version)
    scan=e.scan
    def only_nominated(b,can_trade):
        return scan(b,can_trade=can_trade and b['t']//900*900==nominated and e.position_id==0)
    e.scan=only_nominated
    return e


def review():
    source,minutes=load()
    original=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())
    hypothesis=json.loads((FOLDER.parent/'oct12_giveback_comparison/REVIEW.json').read_text())
    cases=[]
    for old,comparison,cutoff in zip(original['cases'],hypothesis['cases'],CUTOFFS,strict=True):
        nominated=ts(old['nominated_bar']);entry_at=ts(old['trade']['entry_time'])
        observed=[b for b in minutes if entry_at<=b['t']<cutoff]
        if [b['t'] for b in observed]!=list(range(entry_at,cutoff,60)):
            raise ValueError('Case minute data missing; no invented continuity')
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        e=engine_for_case(nominated,cutoff,db)
        for b in minutes:
            if b['t']>=cutoff:break
            e.minute(b)
        r=e.finish()
        if len(r['trades'])!=1:raise ValueError('Expected one original nominated entry')
        p=r['trades'][0]
        for key in ('entry_time','entry','initial_stop','t1','t2'):
            if p[key]!=old['trade'][key]:raise ValueError(f'Entry or original parameter changed: {key}')
        expected=next(v['trade'] for v in comparison['variants'] if v['variant']=='half_1r_direction_inside')
        for actual,prior in zip(p['legs'],expected['legs'],strict=True):
            for k in ('time_utc','price','fraction','gross','cost','net'):
                if actual[k]!=prior[k]:raise ValueError(f'Approved program differs from nominated hypothesis: {k}')
        if p['status']!=expected['status'] or p['remaining']!=expected['remaining']:
            raise ValueError('Position status differs')
        rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t',(nominated,))]
        db.close()
        mark=observed[-1]['close'];remaining=p['remaining'];q=e.cfg.one_way_friction_bps/10000
        gross=remaining*(mark-p['entry']);entry_cost=remaining*p['entry']*q;exit_cost=remaining*mark*q
        cases.append(dict(nominated_bar=old['nominated_bar'],cutoff=iso(cutoff),trade=p,rows=rows,
            realized_gross=sum(l['gross'] for l in p['legs']),realized_cost=sum(l['cost'] for l in p['legs']),
            realized_net=sum(l['net'] for l in p['legs']),
            valuation=dict(as_of=iso(cutoff),source_minute=iso(observed[-1]['t']),price=mark,remaining=remaining,
                unrealized_gross=gross,allocated_entry_cost=entry_cost,unrealized_after_entry_cost=gross-entry_cost,
                hypothetical_roundtrip_net=gross-entry_cost-exit_cost,is_exit=False),
            parameters_unchanged=True,matches_prior_hypothesis=True))
    legacy={name:hashlib.sha256(inspect.getsource(getattr(Replay,name)).encode()).hexdigest()
        for name in ('minute','complete','close_part','targets')}
    if legacy!=json.loads((STORE/'runs'/BASELINE/'result.json').read_text())['unchanged_exit_contract']:
        raise ValueError('Frozen legacy reference changed')
    return dict(status='complete',policy=POLICY,rule_approved=True,source=source,cases=cases,
        month_rerun=False,orders_enabled=False,broker_orders=0,paper_orders=0,
        scope='two nominated entries only, using current replay factory, not new monthly performance',
        costs='ETF zero commission assumption plus 2bps each way, per initial 1 BTC; not actual ETF fills',
        parameters=dict(initial_risk_basis='entry minus original initial stop, never rebased after partial sales',
            min_favourable_excursion_r=1,giveback_fraction=.5,observation='actual 1m open, unfinished 15m state',
            first_target_fraction=.25,fixed_second_target_enabled=False,midpoint_action='warning_only',
            inside_exemption='either body OR observed full range inside preceding complete candle blocks profit guard',
            entry_minute_high='excluded due unknown pre/post entry ordering',
            gaps='no filling; incomplete prefix/previous candle withholds profit guard; original hard protection remains'),
        legacy_method_reference_sha256=legacy,
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (Path(__file__).resolve(),ROOT/'trading_desk/btc_guarded_replay.py',ROOT/'trading_desk/btc_structure_exits.py',ROOT/'trading_desk/btc_engine.py')})


def report(r):
    out=['# BTC 10月12日：已批准浮盈保护的程序复核','',
        '接入1R、回吐一半、当时方向与非内包条件，仅核对两个原指定入场。','',
        'Last Updated: 2026-11-08  ','Status: 已接入当前退出程序并核对两例；未重跑整月  ',
        'Audience: Trading Desk使用者与研究维护者','', '## Overview','',
        '所有时间均为纽约EDT（UTC−4）。运行的是未来A/B复测使用的同一程序工厂，只把入场权限限制到原09:30、21:00两根指定K线；原入场、初始保护、T1及成本没有变化。',
        '', '## 批准后的执行口径','',
        '- 最大浮盈至少达到原初始1R；浮盈回吐率≥50%；当时价格≤本根15分钟开盘且≤前根完整收盘；当时实体和截至当时全振幅均非内包。所有条件须同时满足。等于开盘不算绿，等于前收盘允许。',
        '- 历史复核按每个实际1分钟首价检查；不等15分钟收盘，不使用该分钟尚未知的H/L/C。累计高点只取已完成入场后分钟，排除入场分钟高点。不能把新规则说成每笔行情或精确秒回放。',
        '- 1R固定为最初入场价−初始止损的价格距离；每初始1 BTC折算美元。卖25%或上移结构参考后不重置R。',
        '- T1正常卖首次25%；中点仅预警；固定T2不执行；原硬止损、已确认15分钟结构破位、末分钟长上影退出继续有效。主动保护处理当时全部余仓：未减仓时100%，减仓后75%，不重复卖出。',
        '- 硬止损和真实结构破位不被内包豁免。已知首价事件先于本分钟未知先后的高低价；同一观察点按硬止损→结构→浮盈保护→长上影→目标排序。未知区间顺序仍标记，不虚构成交。',
        '', '## 入场、启用、止盈与余仓退出','',
        '| 指定K线 | 事件 | 时间或区间 | 价格参考 | 初始仓位比例 | 毛盈亏 | 成本 | 净盈亏／状态 |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | --- |']
    labels={'target_25':'首次目标止盈','giveback_exit_remaining':'浮盈保护退出余仓'}
    for c in r['cases']:
        p=c['trade'];name=c['nominated_bar'][11:16]
        out.append(f"| {name} | 入场，初始保护{p['initial_stop']:,.9f}立即生效 | {local(p['entry_time'])}–{local(ts(p['entry_time'])+60)[11:16]} | {p['entry']:,.6f} | 100% | — | — | 原入场不变 |")
        armed=p.get('giveback_state',{}).get('armed_at')
        out.append(f"| {name} | 1R保护首次启用 | {local(armed) if armed else '未启用'} | 初始R={p['entry']-p['initial_stop']:,.6f} | — | — | — | 仅启用，非卖出 |")
        for l in p['legs']:
            out.append(f"| {name} | {labels.get(l['reason'],l['reason'])} | {local(l['time_utc'])}–{local(ts(l['time_utc'])+60)[11:16]} | {l['price']:,.9f} | {l['fraction']:.0%} | {l['gross']:,.6f} | {l['cost']:,.6f} | {l['net']:,.6f} |")
        out.append(f"| {name} | 已实现合计 | 截至{local(c['cutoff'])} | — | 已退出{1-p['remaining']:.0%} | {c['realized_gross']:,.6f} | {c['realized_cost']:,.6f} | {c['realized_net']:,.6f} |")
        if p['remaining']:
            v=c['valuation'];out.append(f"| {name} | 未退出余仓，仅估值 | {local(c['cutoff'])} | {v['price']:,.6f}，非卖价 | {p['remaining']:.0%} | 浮盈{v['unrealized_gross']:,.6f} | 分摊买入{v['allocated_entry_cost']:,.6f} | 未实现{v['unrealized_after_entry_cost']:,.6f}；未扣实际不存在的卖出成本 |")
    out+=['', '## 早盘10:19触发证据','']
    early=r['cases'][0]['trade'];trigger=early['giveback_exits'][0]['guard']
    out += [f"当时已知高点{trigger['highest_known_price']:,.6f}，入场{early['entry']:,.6f}，最大浮盈{trigger['max_favourable_excursion']:,.6f}＝{trigger['mfe_r']:.6f}R；首价{trigger['reference_price']:,.6f}对应回吐{trigger['giveback_fraction']:.6%}。",
        f"当时价格低于本根开盘{trigger['direction_bar_open']:,.6f}及前根收盘{trigger['previous_bar_close']:,.6f}。当时已知全振幅H={trigger['observed_high']:,.6f}、L={trigger['observed_low']:,.6f}；全根及实体均非内包。所有条件通过，只退出剩余75%。",
        '10:06虽回吐超过一半，但实体仍内包，因此不卖。10:11正常执行原T1的25%。10:17／10:18仍被内包拦截。10:15–10:30这根最终收绿不参与10:19决定；这是获利保护，不是事后声称已经确认完整阴线。',
        '', '## 晚盘至次日01:45','',
        '相同规则下，22:57原T1卖25%。其余75%没有满足浮盈回吐退出，已生效结构参考83,285.235也未被破坏；截止01:45仍持有。不强制平仓，也不把估值记为已实现盈利。',
        '', '## 逐根事件与保护状态','',
        '本表状态从本行结束后起生效，不能倒用于本行；事件保留其实际分钟。每个案例结束后未持仓的行只作行情对照。']
    labels.update(giveback_armed='1R启用',midpoint_warning='中点预警',structure_reference_raised='结构参考上移',entry='入场')
    for c in r['cases']:
        out+=['',f"### {c['nominated_bar'][11:16]}指定案例",'',
            '| 15分钟开始→结束 | 完整O / H / L / C | 事件 | 行末余仓 |',
            '| --- | --- | --- | ---: |']
        for b in c['rows']:
            events='；'.join(f"{local(e['time_utc'])[11:16]} {labels[e['type']]}" for e in b['events'] if e['type'] in labels)
            out.append(f"| {local(b['t'])}→{local(b['t']+900)[11:16]} | "+' / '.join(f"{b[k]:,.4f}" for k in ('open','high','low','close'))+f" | {events or '无退出'} | {b['remaining']:.0%} |")
    out+=['', '## 来源与不变范围','',
        f"Alpaca真实分钟归档SHA256 `{r['source']['sha256']}`。不填补缺失分钟；缺少完整前根或本根前缀时不判断浮盈退出，硬保护照常。旧Replay方法哈希未变。",
        '程序结果与此前唯一被批准的候选路径逐腿时间、价格、比例及盈亏完全一致。当前退出策略已接入未来A/B研究工厂，但本次仅执行两例；旧月度、latest_run、V1/V2/V3与候选比较原件不改写。没有真实或paper订单；模型参考不是ETF实际成交。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    watched=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json']+list(FOLDER.parent.glob('*/REVIEW.json'))+[FOLDER/'B_BRANCH_REVIEW.json']
    watched=[p for p in watched if p.parent!=OUTPUT]
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    result=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):raise ValueError('Old artifact changed')
    if folders!=sorted(p.name for p in (STORE/'runs').iterdir()):raise ValueError('Monthly run created')
    result['prior_artifact_sha256']={str(p.relative_to(ROOT)):h for p,h in before.items()}
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',result)
    with (OUTPUT/'EXITS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['nominated_bar','reason','time_ny','price','fraction','gross','cost','net','status_at_cutoff']);w.writeheader()
        for c in result['cases']:
            for l in c['trade']['legs']:
                w.writerow(dict(nominated_bar=c['nominated_bar'],**{k:l[k] for k in ('reason','time_ny','price','fraction','gross','cost','net')},status_at_cutoff=c['trade']['status']))
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_APPROVED_PROFIT_GUARD.md').write_text(report(result))
    print(json.dumps([dict(entry=c['nominated_bar'],status=c['trade']['status'],legs=c['trade']['legs'],realized_net=c['realized_net']) for c in result['cases']]))
