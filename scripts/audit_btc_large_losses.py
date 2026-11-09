"""Fixed-entry audit of every >$500 loss, then an explicitly requested replay."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk import btc_engine
from trading_desk.btc_data import STORE,read,save,ts,iso
from scripts.audit_btc_all_losses import totals,local,audit_losses

BASELINE='20261109T034016Z-30-ab'
FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/large_losses_failed_rebound'


def source_minutes(old):
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        return [dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n)
            for t,o,h,l,c,v,n in db.execute('SELECT t,o,h,l,c,v,n FROM minutes WHERE t>=? AND t<? ORDER BY t',
                (ts(old['warmup_start']),ts(old['end'])))]


def frozen_case(old,p,minutes,version):
    signal=copy.deepcopy(next(s for s in old['signals'] if s['id']==p['signal_id']))
    start=ts(p['entry_time']);end=ts(p['exit_time'])+60
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=btc_engine.create_replay(ts(old['start']),end,db,expanded_b=True,exit_version=version)
    injected=False
    def entry(b):
        nonlocal injected
        if b['t']==start and not injected:
            # Exact archived, causally established entry; isolate exits without
            # pretending a different prior-position sequence chose this setup.
            e.position_id=p['id']-1;e.open_signal(b,signal);injected=True
    e.entry=entry
    for b in minutes:
        if b['t']>=end:break
        e.minute(b)
    result=e.finish()
    if len(result['trades'])!=1:raise ValueError('Frozen-entry study expected exactly one held position')
    trade=result['trades'][0]
    for key in ('entry_time','entry','initial_stop','t1','t2'):
        assert trade[key]==p[key],(p['id'],key)
    rows=[json.loads(body) for (body,) in db.execute('SELECT body FROM ledger WHERE t>=? ORDER BY t',(start//900*900-3600,))]
    for row in rows:
        row['observed_end_exclusive']=iso(min(end,ts(row['end'])))
        row['is_complete']=row['observed_minutes']==15 and ts(row['end'])<=end
    db.close()
    return trade,rows


def compact(p):
    return {k:p.get(k) for k in ('id','status','entry_time','entry','initial_stop','t1','remaining',
        'exit_time','net','net_r','legs','references','gap_exposed','context_partial','same_minute_exit_ambiguity',
        'failed_rebound_history','case_exit_evidence')}


def review():
    old=read(STORE/'runs'/BASELINE/'result.json');minutes=source_minutes(old)
    cases=[]
    for p in old['trades']:
        if p.get('net',0)>=-500:continue
        before,_=frozen_case(old,p,minutes,'turning_consumed_v7')
        assert before['legs']==p['legs'],f"Baseline mismatch #{p['id']}"
        after,rows=frozen_case(old,p,minutes,'current')
        delta=after['net']-p['net']
        case=dict(old_trade_id=p['id'],entry_rule=p['entry_rule'],before=compact(before),after=compact(after),
            net_change=delta,changed=after['legs']!=before['legs'],rows=rows,
            outcome='15分钟结构尚未来得及确认，保留原硬止损' if p['id']==5 and not after.get('failed_rebound_history') else
                '已确认LH后跌破对应低点，独立退出余仓' if after['legs'][-1]['reason']=='failed_rebound_exit_remaining' else
                '没有更早的完整确认／破位，保留先到的原退出',
            limitation='fixed old entry isolates exit change; not a claim the full sequential run retains this trade')
        cases.append(case)
        print(json.dumps(dict(trade=p['id'],before=p['net'],after=after['net'],
            exit=after['exit_time'],reason=after['legs'][-1]['reason'])),flush=True)
    assert [c['old_trade_id'] for c in cases]==[5,11,12,23,32]
    return dict(source_run=BASELINE,policy='confirmed 15m H-L-LH then strict low break; hard stop unchanged',
        cases=cases,numeric_parameters_changed=False,broker_orders=0,month_rerun=False)


def write_report(review,comparison=None):
    lines=['# BTC 超过500美元亏损逐笔修复', '', '固定原入场核对五笔大额亏损，采用已批准的独立失败反弹退出。', '',
        'Last Updated: 2026-11-08  ', 'Status: 已逐笔重放；条件模型，无订单  ', 'Audience: 交易桌使用者与维护者','', '## Overview','',
        f"基准`{BASELINE}`中净亏损严格超过$500的交易为#5、#11、#12、#23、#32。固定每笔原入场、初始止损、目标和2bps每边成本，隔离新退出的影响。$500只是审查筛选条件，不是新止损或仓位上限。",'',
        '## 已批准的新退出', '',
        '完整15分钟波峰H后出现已确认回踩低点L，再出现低于H的已确认波峰LH；LH右侧完整K线结束后才生效。随后严格跌破L，退出实际余仓。每个转折用既有左右各一根完整K线，不增加幅度或ATR阈值。', '',
        '这是独立退出，不是上移初始硬止损；不要求达到1R或再创新高。上涨重夺LH使该组合失效，等待重新确认。缺失分钟／不完整邻居清除尚未确认的新形态；此前已完整确认的退出参考仍保留，仅按后续实际观测触发，并标记缺口中先后关系未知，硬止损也保留。同一分钟破低与重夺／止盈顺序不明时，标记风险优先，不能称为精确tick成交。','',
        '| 原交易# | 入场纽约时间 | 原入场 | 初始止损 | 原净盈亏 | 固定入场的新退出时间 | 新退出价 | 新净盈亏 |',
        '| --- | --- | ---: | ---: | ---: | --- | ---: | ---: |']
    for c in review['cases']:
        a=c['before'];b=c['after'];last=b['legs'][-1]
        lines.append(f"| {c['old_trade_id']} | {local(a['entry_time'])} | {a['entry']:,.4f} | {a['initial_stop']:,.4f} | {a['net']:+,.2f} | {local(b['exit_time'])} | {last['price']:,.4f} | {b['net']:+,.2f} |")
    for c in review['cases']:
        a=c['before'];b=c['after'];proof=next((e for e in reversed(b['case_exit_evidence'] or []) if e['reason']=='failed_rebound_exit_remaining'),None)
        lines+=['',f"## 原交易 #{c['old_trade_id']} · {c['entry_rule']}",'',c['outcome']+'。',
            '',f"原持有{(ts(a['exit_time'])-ts(a['entry_time']))//60}分钟，原初始价格风险{a['entry']-a['initial_stop']:,.4f}美元。新方案毛{sum(l['gross'] for l in b['legs']):+,.2f}、成本{sum(l['cost'] for l in b['legs']):,.2f}、净{b['net']:+,.2f}；与原记录差{c['net_change']:+,.2f}。"]
        if proof:
            anchor=proof['failed_rebound']
            for name,key in [('前波峰H','high'),('回踩低点L','low'),('较低高点LH','lower_high')]:
                point=anchor[key];lines+=['',f"{name}：{local(iso(point['time']))}，{point['price']:,.4f}；至{local(iso(point['known_at']))}才确认。"]
            lines+=['',f"生效：{local(iso(anchor['effective_at']))}。破位退出：{local(proof['time_utc'])}，{proof['price']:,.4f}，退出当时余仓{proof['fraction']:.0%}。"]
        if a['gap_exposed']:lines+=['','原持有期间包含缺失分钟；只重放实际观测，不补足缺口。']
    if comparison:
        lines+=['','## 同源完整30天顺序复测','',
            '固定原入场的五笔对照只隔离退出效果。下面的顺序序列会因更早平仓改变新入场机会，不能直接把五笔差额加回原总收益。','',
            f"新记录`{comparison['current']['run_id']}`；原{comparison['baseline']['entries']}笔，净{comparison['baseline']['closed_net']:+,.2f}；新{comparison['current']['entries']}笔，净{comparison['current']['closed_net']:+,.2f}。",
            '原始记录及工作簿SHA256核验未变。该样本已用于规则研究，尚非样本外或实际ETF收益。']
        effects=review.get('sequence_effects',[])
        lines+=['','## 全样本改变的交易，包括盈利交易','',
            '| 基准交易# | 原净盈亏 | 新净盈亏 | 差额 |','| --- | ---: | ---: | ---: |']
        for row in effects:
            lines.append(f"| {row['old_trade_id']} | {row['before_net']:+,.2f} | {row['after_net']:+,.2f} | {row['net_change']:+,.2f} |")
        lines+=['','新序列仍有#5与#32两笔净亏损超过$500。没有把$500改成硬损失上限，也没有为消除这两笔而缩小仓位或更改入场、止损阈值。']
    (ROOT/'docs/investigations/2026-11-08_BTC_LARGE_LOSSES_FAILED_REBOUND.md').write_text('\n'.join(lines)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--replay',action='store_true');args=parser.parse_args()
    r=review();FOLDER.mkdir(parents=True,exist_ok=True);save(FOLDER/'REVIEW.json',r)
    write_report(r)
    if not args.replay:return
    old=read(STORE/'runs'/BASELINE/'result.json')
    preserved={str(p.relative_to(STORE)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (STORE/'runs').glob('*/*') if p.name in ('result.json','RESEARCH.xlsx','WORKBOOK_DATA.json')}
    new=btc_engine.run(30,expanded_b=True,progress=lambda p:print(json.dumps(p),flush=True))
    assert new['source_minute_sha256']==old['source_minute_sha256']
    assert all(hashlib.sha256((STORE/p).read_bytes()).hexdigest()==h for p,h in preserved.items())
    folder=STORE/'runs'/new['run_id']
    comparison=dict(baseline=totals(old),current=totals(new),same_source=True,
        source_minute_sha256=new['source_minute_sha256'],historical_files_sha256=preserved,
        change_description_zh='仅新增已批准的失败反弹退出：完整15分钟H-L-LH后破低退出。原入场生命周期、硬止损、目标及成本数值保留；顺序持仓机会可改变。')
    for c in r['cases']:
        original=c['before']
        same=next((p for p in new['trades'] if p['entry_time']==original['entry_time'] and p['entry_rule']==c['entry_rule']),None)
        c['sequential_trade_id']=same['id'] if same else None;c['sequential_net']=same.get('net') if same else None
    effects=[]
    for p in old['trades']:
        same=next((q for q in new['trades'] if q['entry_time']==p['entry_time'] and q['entry_rule']==p['entry_rule']),None)
        if same and p.get('net') is not None and same.get('net') is not None and abs(same['net']-p['net'])>1e-7:
            effects.append(dict(old_trade_id=p['id'],new_trade_id=same['id'],before_net=p['net'],after_net=same['net'],net_change=same['net']-p['net']))
    r['sequence_effects']=effects;r['remaining_losses']=audit_losses(new,expected_count=None)
    r['month_rerun']=True;r['full_run_id']=new['run_id']
    save(folder/'COMPARISON.json',comparison);save(folder/'LARGE_LOSS_REVIEW.json',r)
    db=sqlite3.connect((folder/'ledger.sqlite').as_uri()+'?mode=ro',uri=True)
    ledger=[json.loads(body) for (body,) in db.execute('SELECT body FROM ledger ORDER BY t')];db.close()
    save(folder/'WORKBOOK_DATA.json',dict(result=new,ledger=ledger))
    fields=['old_trade_id','entry_time','entry','initial_stop','before_net','new_exit_time','new_exit_price','after_net','net_change','outcome','sequential_trade_id','sequential_net']
    with (folder/'LARGE_LOSS_REVIEW.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in r['cases']:
            a=c['before'];b=c['after'];w.writerow(dict(old_trade_id=c['old_trade_id'],entry_time=a['entry_time'],entry=a['entry'],initial_stop=a['initial_stop'],before_net=a['net'],
                new_exit_time=b['exit_time'],new_exit_price=b['legs'][-1]['price'],after_net=b['net'],net_change=c['net_change'],outcome=c['outcome'],sequential_trade_id=c['sequential_trade_id'],sequential_net=c['sequential_net']))
    write_report(r,comparison)
    print(json.dumps(dict(run_id=new['run_id'],metrics=new['metrics'],net=comparison['current']['closed_net']),indent=2))


if __name__=='__main__':main()
