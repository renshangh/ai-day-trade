"""Only two nominated October 12 cases; preserve all prior audits and months."""
import hashlib
import inspect
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,ts,save
from trading_desk.btc_engine import Replay
from trading_desk.btc_approved_exits import POLICY
from audit_btc_oct12_b_branches import FOLDER,BASELINE,load,local,NominatedCase

PRIOR=FOLDER.parent/'oct12_approved_exits/REVIEW.json'
OUTPUT=FOLDER.parent/'oct12_direction_filtered_exits'


def review():
    source,minutes=load()
    original=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())
    prior=json.loads(PRIOR.read_text())
    cases=[]
    for old,previous in zip(original['cases'],prior['cases'],strict=True):
        if old['nominated_bar']!=previous['nominated_bar']:raise ValueError('Case alignment changed')
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        engine=NominatedCase(ts(old['nominated_bar']),db,exit_policy='approved')
        for bar in minutes:
            engine.minute(bar)
            if engine.trades:break
        result=engine.finish()
        if len(result['trades'])!=1:raise ValueError('Expected exactly one nominated trade')
        trade=result['trades'][0]
        for key in ('entry_time','entry','initial_stop','t1','t2','stop_history'):
            if trade.get(key)!=old['trade'].get(key):raise ValueError(f'Frozen parameter changed: {key}')
        evidence=trade['active_exit_events']
        for e in evidence:
            price=e['direction_reference_price']
            if not (e['direction_filter_applied'] and price<=e['direction_bar_open']
                    and price<=e['previous_bar_close']):raise ValueError('Direction filter failed')
        rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM ledger ORDER BY t')]
        db.close()
        entry_at=ts(trade['entry_time']);exit_at=ts(trade['exit_time'])
        observed=[b for b in minutes if entry_at<=b['t']<=exit_at]
        if [b['t'] for b in observed]!=list(range(entry_at,exit_at+60,60)):
            raise ValueError('Case holding interval has missing observations; surface instead of filling')
        cases.append(dict(nominated_bar=old['nominated_bar'],entry_rule='B1',trade=trade,
            original_trade=old['trade'],prior_approved_trade=previous['trade'],
            exit_net_change=trade['net']-old['trade']['net'],
            direction_filter_net_change=trade['net']-previous['trade']['net'],
            approved_exit_evidence=evidence,
            filter_rejections=trade.get('direction_filter_rejections',[]),
            rows=[r for r in rows if r['t']>=entry_at//900*900],
            observed_exit_minutes=[b for b in observed if b['t']>=exit_at//900*900-900],
            entry_and_parameters_unchanged=True,holding_minutes_contiguous=True))
    baseline=json.loads((STORE/'runs'/BASELINE/'result.json').read_text())
    hashes={n:hashlib.sha256(inspect.getsource(getattr(Replay,n)).encode()).hexdigest()
        for n in ('minute','complete','close_part','targets')}
    if hashes!=baseline['unchanged_exit_contract']:raise ValueError('Frozen Replay changed')
    return dict(status='complete',policy=POLICY,cases=cases,source=source,
        comparison_baseline_run=BASELINE,month_rerun=False,orders_enabled=False,broker_orders=0,
        costs='ETF zero commission assumption plus 2bps each way, per initial 1 BTC',
        execution='two independent nominated entries; minute references, exact seconds and fills unverified',
        legacy_method_reference_sha256=hashes,
        prior_artifact_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (PRIOR,FOLDER/'B_BRANCH_REVIEW.json')},
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(),ROOT/'trading_desk/btc_approved_exits.py',
                ROOT/'trading_desk/btc_ab_replay.py',ROOT/'scripts/audit_btc_oct12_b_branches.py')})


def report(r):
    out=['# BTC 10月12日：两种主动退出的方向过滤复核','',
        '按触发当时的非绿K线与前根收盘条件复核两笔固定入场。','',
        'Last Updated: 2026-11-08  ','Status: 两例已复核；未重跑整月；无订单  ',
        'Audience: Trading Desk使用者及维护者','', '## Overview','',
        '全部时间为2026年10月12日纽约EDT（UTC−4）。复用已归档Alpaca真实分钟；仅更改两种主动退出的方向过滤。入场、初始止损、同级低点上移、目标、25%／75%比例及每边2bps成本均不变。',
        '', '## 同一张交易表','',
        '| 指定K线 | 入场分钟／价格 | 初始止损（入场即生效） | 退出分钟／参考价 | 退出比例／原因 | 毛盈亏 | 摩擦 | 净盈亏 |',
        '| --- | --- | ---: | --- | --- | ---: | ---: | ---: |']
    for c in r['cases']:
        p=c['trade'];l=p['legs'][0]
        out.append(f"| {c['nominated_bar'][11:16]} | {local(p['entry_time'])[11:16]}–{local(ts(p['entry_time'])+60)[11:16]} / {p['entry']:,.6f} | {p['initial_stop']:,.6f} | {local(l['time_utc'])[11:16]}–{local(ts(l['time_utc'])+60)[11:16]} / {l['price']:,.6f} | {l['fraction']:.0%}／中点盘中退出 | {l['gross']:,.6f} | {l['cost']:,.6f} | {l['net']:,.6f} |")
    out+=['','每笔按初始1 BTC归一化，不是ETF实际成交或收益。两笔都在T1之前全退，没有25%／75%目标成交，持有期没有符合原规则的止损上移。',
        '', '## 时点与门槛','',
        '- 中点仍盘中判断，仅对前根完整创新高K线的下一根有效；长上影仍在最后1分钟判断。两者都不等本根完整收盘。',
        '- 当时价格≤本根15分钟开盘，且≤前一根完整15分钟收盘，才通过方向过滤。等于开盘是中性十字，不算绿；等于前收盘允许。',
        '- 中点已经跌破但方向未满足时继续等待。新有效参考价是同时满足三个界限的当时价格，不得回填更早、更高的中点价格。',
        '- 1分钟OHLC只定位触发所在分钟，无法验证精确秒或真实成交。区间内触及参考不等于保证在该价成交；原价差／滑点成本仍保留。缺失参考则暂停主动退出判断，结构止损不受此过滤限制。',
        '', '## 早盘：10:05仍满足','',
        '09:45–10:00完整K线H=82,946.42、L=82,593.4755，中点82,769.94775，从10:00起生效至10:15。',
        '10:00本根开盘82,873.79、前根完整收盘82,875.745。10:05分钟开盘82,823.02，最低82,732.55；下穿中点时已低于两个方向界限，故仍在10:05–10:06全退，不等10:15。',
        '', '## 晚盘：22:29不退出，22:31才同时满足','',
        '| 观察时点 | 当时参考价 | 本根15分钟开盘 | 前根完整收盘 | 结论 |',
        '| --- | ---: | ---: | ---: | --- |',
        '| 22:29分钟首价 | 82,637.30 | 82,646.936 | 82,627.021 | 非绿，但高于前收盘；拒绝长上影退出 |',
        '| 22:30分钟首价 | 82,658.58 | 82,658.58 | 82,655.0085 | 已低于中点82,683.75025，但高于前收盘；继续等待 |',
        '| 22:31–22:32盘中下穿 | 82,655.0085 | 82,658.58 | 82,655.0085 | 三个界限同时满足，退出全部余仓 |',
        '',
        '22:15–22:30完整K线H=82,757.985、L=82,609.5155，中点82,683.75025从22:30起生效。22:30分钟最低仍未触及82,655.0085，下一分钟才下穿。卖出参考使用82,655.0085，不能用较早中点82,683.75025。',
        '“不是绿线”指触发当时的价格与本根开盘比较，不是等整根最终颜色。即便本根随后收绿，也不能用未来收盘倒改此前满足条件的盘中退出。',
        '', '## 三个版本分开','',
        '| 案例 | 原历史路径净盈亏 | 无方向过滤V1 | 本次方向过滤V2 | V2−V1 |',
        '| --- | ---: | ---: | ---: | ---: |']
    for c in r['cases']:
        out.append(f"| {c['nominated_bar'][11:16]} | {c['original_trade']['net']:,.6f} | {c['prior_approved_trade']['net']:,.6f} | {c['trade']['net']:,.6f} | {c['direction_filter_net_change']:,.6f} |")
    out+=['', '## 来源与保留范围','',
        f"真实Alpaca观测分钟SHA256 `{r['source']['sha256']}`。两笔持有区间均连续；整个暖机归档的缺失分钟仍保持缺失。",
        '结果保存在`oct12_direction_filtered_exits/REVIEW.json`，包含两笔逐根事件、触发证据及被方向条件拦截的旧信号。旧B1/B2案例、V1结果、月度结果及latest_run均保留；没有重跑整月，没有真实或模拟订单。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    watched=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json',PRIOR]
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    result=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):raise ValueError('Prior artifact changed')
    if sorted(p.name for p in (STORE/'runs').iterdir())!=folders:raise ValueError('Monthly run created')
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',result)
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_DIRECTION_FILTERED_EXITS.md').write_text(report(result))
    print(json.dumps([dict(entry=c['trade']['entry_time'],exit=c['trade']['exit_time'],
        price=c['trade']['legs'][0]['price'],net=c['trade']['net']) for c in result['cases']]))
