"""Execute approved exit code for two frozen nominated entries, never a month."""
import copy
import hashlib
import inspect
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,ts,iso,save
from trading_desk.btc_engine import Replay
from trading_desk.btc_approved_exits import POLICY_V1,ApprovedExitReplay
from audit_btc_oct12_b_branches import FOLDER,BASELINE,load,local,NominatedCase
from review_btc_nov06_07_swings import scan_exits

OUTPUT=ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_approved_exits'


def review():
    source,minutes=load()
    original=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())
    cases=[]
    for old in original['cases']:
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        engine=NominatedCase(ts(old['nominated_bar']),db,exit_policy='approved_v1')
        for bar in minutes:
            engine.minute(bar)
            if engine.trades:break
        result=engine.finish()
        if len(result['trades'])!=1:raise ValueError('Expected one independently nominated entry')
        trade=result['trades'][0];previous=old['trade']
        for key in ('entry_time','entry','initial_stop','t1','t2'):
            if trade[key]!=previous[key]:raise ValueError(f'Entry/protection/target unexpectedly changed: {key}')
        if trade.get('stop_history')!=previous.get('stop_history'):
            raise ValueError('Protection changes require separate review')
        check=dict(entry=previous['entry'],entry_time=previous['entry_time'],
            source_end_exclusive=iso(ts(previous['exit_time'])+60),references=copy.deepcopy(previous['references']),legs=[])
        expected=scan_exits(check,minutes)
        first=expected['first_candidate'];leg=trade['legs'][-1]
        if not first or ts(leg['time_utc'])!=ts(first['time']) or abs(leg['price']-first['price'])>1e-8:
            raise ValueError('Program disagrees with the previously approved causal exit audit')
        rows=[json.loads(x[0]) for x in db.execute('SELECT body FROM ledger ORDER BY t')]
        db.close()
        cases.append(dict(nominated_bar=old['nominated_bar'],entry_rule='B1',trade=trade,
            original_trade=previous,exit_net_change=trade['net']-previous['net'],
            approved_exit_evidence=trade.get('active_exit_events',[]),
            later_signals_not_fills=[e for e in expected['events'] if ts(e['time'])>ts(leg['time_utc'])],
            rows=[b for b in rows if b['t']>=ts(previous['entry_time'])//900*900],
            entry_and_parameters_unchanged=True))
    baseline=json.loads((STORE/'runs'/BASELINE/'result.json').read_text())
    legacy={n:hashlib.sha256(inspect.getsource(getattr(Replay,n)).encode()).hexdigest()
        for n in ('minute','complete','close_part','targets')}
    if legacy!=baseline['unchanged_exit_contract']:
        raise ValueError('Legacy reference or protective/target code changed')
    return dict(status='complete',policy=POLICY_V1,cases=cases,source=source,
        baseline_case_sha256=hashlib.sha256((FOLDER/'B_BRANCH_REVIEW.json').read_bytes()).hexdigest(),
        comparison_baseline_run=BASELINE,month_rerun=False,orders_enabled=False,broker_orders=0,
        execution='two independent nominated entries; model minute references, exact seconds and fills unverified',
        costs='ETF zero commission assumption plus 2bps each way, per initial 1 BTC',
        legacy_method_reference_sha256=legacy,
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(),ROOT/'scripts/audit_btc_oct12_b_branches.py',
                ROOT/'trading_desk/btc_approved_exits.py',ROOT/'trading_desk/btc_ab_replay.py',
                ROOT/'trading_desk/btc_engine.py',ROOT/'trading_desk/btc_shock_branches.py',
                ROOT/'trading_desk/btc_entry_detector.py',ROOT/'trading_desk/btc_entry_rules.py')})


def report(r):
    labels={'midpoint_exit_all':'前根新高中点退出','wick_exit_all':'末分钟长上影退出'}
    out=['# BTC 10月12日：已批准退出规则的程序复核','',
        '接入中点与无整数关口长上影退出，执行两笔固定入场的新旧对照。','',
        'Last Updated: 2026-11-08  ','Status: 已接入研究程序并复核两笔；未重跑整月  ',
        'Audience: Trading Desk使用者及研究维护者','',
        '## Overview','',
        '时间均为2026年10月12日纽约EDT（UTC−4）。只执行09:30／21:00两根指定K线对应的原入场；初始止损、目标、25%／75%比例、费用及追价均未更改。每个案例独立计算，不代表组合收益。',
        '', '## 更新后的入场与退出','',
        '| 指定K线 | 入场分钟／参考价 | 初始止损 | 最早退出分钟 | 原因 | 退出参考价／初始仓位 | 毛盈亏 | 摩擦 | 净盈亏 |',
        '| --- | --- | ---: | --- | --- | --- | ---: | ---: | ---: |']
    for c in r['cases']:
        p=c['trade'];l=p['legs'][0]
        out.append(f"| {c['nominated_bar'][11:16]} | {local(p['entry_time'])[11:16]} / {p['entry']:,.6f} | {p['initial_stop']:,.6f} | {local(l['time_utc'])[11:16]}–{local(ts(l['time_utc'])+60)[11:16]} | {labels[l['reason']]} | {l['price']:,.6f} / {l['fraction']:.0%} | {l['gross']:,.6f} | {l['cost']:,.6f} | {l['net']:,.6f} |")
    out+=['','两笔都在T1之前退出全部100%，因此本次没有实际发生的25%／75%目标腿，也没有后续止损成交。初始止损仍从入场即保护，持有期间没有上移。','',
        '## 触发证据与生效时点','']
    for c in r['cases']:
        p=c['trade'];e=c['approved_exit_evidence'][0]
        out.append(f"### {c['nominated_bar'][11:16]}案例")
        if p['legs'][0]['reason']=='midpoint_exit_all':
            out.append(f"09:45–10:00完整K线H={e['reference_high']:,.6f}，L={e['reference_low']:,.6f}，中点={(e['reference_high']+e['reference_low'])/2:,.8f}。从10:00起，仅对10:00–10:15下一根生效。10:05分钟开盘高于中点、最低价低于中点，按下穿参考价退出。当前根10:00再创新高，不取消该已知中点。")
        else:
            out.append(f"22:29首价{e['reference_price']:,.6f}，只用22:15–22:28的14根完整分钟及该首价：H={e['observed_high']:,.6f}、L={e['observed_low']:,.6f}、15分钟开盘{e['opening_15m']:,.6f}；上影／全振幅{e['upper_wick_fraction']:.6%}≥50%，并超过此前完整波段高点{e['wave_high_before']:,.6f}。不使用22:29最终H/L/C，不要求整数关口，退出当时全部100%。")
        out.append('此后观察到的信号不是本笔新增成交：'+('；'.join(f"{local(e['time'])[11:16]} {e['type']}" for e in c['later_signals_not_fills']) or '原退出之前没有更晚形态信号')+'。')
        out.append('')
    out+=['## 新旧路径分开保留','',
        '| 案例 | 原退出路径 | 原净盈亏 | 新净盈亏 | 差额 |','| --- | --- | ---: | ---: | ---: |']
    for c in r['cases']:
        old=c['original_trade']
        detail='；'.join(f"{local(l['time_utc'])[11:16]} {l['fraction']:.0%}" for l in old['legs'])
        out.append(f"| {c['nominated_bar'][11:16]} | {detail} | {old['net']:,.6f} | {c['trade']['net']:,.6f} | {c['exit_net_change']:,.6f} |")
    out+=['','晚盘按规则在22:29已平仓，不能再计22:57／23:35后来更高目标的收益。此次两例复核不是为保留每笔最佳结果，也没有证明月度收益改善。','',
        '## 程序规则','',
        '- 前根必须完整、位于入场之后且高于该笔已保留波段参考；中点只对下一根有效，不偷看当前收盘。',
        '- 末分钟上影≥50%、已创新高、观察价高于入场；只读取前14分钟和当前分钟首价，取消整数关口。',
        '- 两种主动退出均卖出当时全部剩余仓位；若先卖过25%，只处理余75%，不重复卖出100%。',
        '- 已知分钟开盘事件先于该分钟尚未知顺序的H/L触及；若多个区间触及先后不明，按止损→中点→目标的风险优先规则并标记歧义，不捏造精确秒。相同开盘观察点的全退优先于部分目标；两档目标仍顺序处理25%／75%。',
        '- 缺失分钟不补值，完整中点／上影参考不成立时不虚构信号；持有过程缺口继续标记。','',
        '## 来源与未变范围','',
        f"复用原Alpaca分钟，SHA256 `{r['source']['sha256']}`。逐分钟驱动真实程序的批准退出分支，并与此前独立审查的最早事件一致。每笔初始1 BTC、原每边2bps成本；价格是模型参考，不是已验证ETF成交。",
        '新结果保存在`oct12_approved_exits/REVIEW.json`。旧两例、旧月度结果及latest_run指针不改写。默认A/B研究程序已使用批准退出，旧Replay及显式legacy模式供历史对照；没有运行整月或提交订单。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    watched=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    runs_before=sorted(p.name for p in (STORE/'runs').iterdir())
    result=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):
        raise ValueError('An existing result changed')
    if sorted(p.name for p in (STORE/'runs').iterdir())!=runs_before:
        raise ValueError('A monthly run folder was created')
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',result)
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_APPROVED_EXIT_REPLAY.md').write_text(report(result))
    print(json.dumps([dict(entry=p['trade']['entry_time'],exit=p['trade']['exit_time'],
        legs=p['trade']['legs'],net=p['trade']['net']) for p in result['cases']]))
