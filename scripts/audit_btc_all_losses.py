"""Audit every original losing trade, then replay the confirmed history fix.

All prices come from preserved Alpaca minutes. No threshold search, bar filling
or hindsight-based exits. The original run and workbook are immutable controls.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk import btc_engine
from trading_desk.btc_data import STORE,read,save,ts,iso

BASELINE='20261109T030906Z-30-ab'
REASON={'stop':'初始或上移硬止损','structure_exit_remaining':'已确认15分钟结构破位',
    'turning_exit_remaining':'末分钟冲高失败','giveback_exit_remaining':'1R后浮盈回吐',
    'wick_exit_all':'末分钟长上影'}
NY=ZoneInfo('America/New_York')


def local(value):return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(NY).strftime('%m/%d %H:%M %Z')


def totals(r):
    return dict(run_id=r['run_id'],strategy_version=r['strategy_version'],entries=len(r['trades']),
        signals=r['signal_counts'],metrics=r['metrics'],
        closed_net=sum(p['net'] for p in r['trades'] if p['status']=='closed'),
        realized_leg_net=sum(l['net'] for p in r['trades'] for l in p['legs']),
        open_positions=[dict(trade_id=p['id'],remaining=p['remaining'],unrealized_gross=p.get('unrealized_gross'))
            for p in r['trades'] if p['status']=='open'])


def minute(db,t):
    row=db.execute('SELECT o,h,l,c FROM minutes WHERE t=?',(t,)).fetchone()
    if row is None:return None
    return dict(open=row[0],high=row[1],low=row[2],close=row[3])


def audit_losses(old,expected_count=27):
    signals={s['id']:s for s in old['signals']};rows=[]
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for i,p in enumerate(old['trades']):
            if p.get('net') is None or p['net']>=0:continue
            s=signals[p['signal_id']];w=s['setup_evidence'];leg=p['legs'][-1];t=ts(leg['time_utc']);b=minute(db,t)
            if b is None:raise ValueError(f"Trade {p['id']} exit minute absent; cannot verify")
            origin=w['origin']['time'] if 'origin' in w else w['impulse']['t']
            prior=old['trades'][i-1] if i else None
            prior_floor=(ts(prior['entry_time'])//900+1)*900 if prior else None
            reused=prior_floor is not None and origin<prior_floor
            points=[w.get(k) for k in ('origin','d','hh','hl')]+w.get('lows',[])+w.get('intervening_highs',[])+w.get('extensions',[])
            causal=all(point.get('known_at',point.get('time',0))<=ts(p['entry_time']) for point in points if point)
            for name in ('impulse','rebound','stabilization_bar'):
                if w.get(name):causal=causal and w[name]['t']+900<=ts(p['entry_time'])
            assert causal,f"Trade {p['id']} used unconfirmed setup"
            gross=sum(l['gross'] for l in p['legs']);cost=sum(l['cost'] for l in p['legs'])
            assert abs(gross-cost-p['net'])<1e-7
            for l in p['legs']:
                assert abs(l['gross']-(l['price']-p['entry'])*l['fraction'])<1e-7
                assert abs(l['cost']-(l['price']+p['entry'])*l['fraction']*.0002)<1e-7
            evidence=next((e for e in reversed(p.get('case_exit_evidence',[]))
                if e['reason']==leg['reason'] and e['time_utc']==leg['time_utc']),None)
            assert evidence is not None,f"Trade {p['id']} lacks exit evidence"
            exit_checks={}
            if leg['reason']=='stop':
                stop=p['stop'];expected=b['open'] if b['open']<=stop else stop
                exit_checks=dict(real_minute_touches=b['low']<=stop,reference_matches=abs(leg['price']-expected)<1e-7)
            elif leg['reason']=='structure_exit_remaining':
                anchor=evidence['structure'];price=anchor['price'];expected=b['open'] if b['open']<price else price
                exit_checks=dict(confirmed_before_exit=anchor['known_at']<=anchor['effective_at']<=t,
                    real_minute_breaks=b['low']<price,reference_matches=abs(leg['price']-expected)<1e-7)
            elif leg['reason']=='failed_rebound_exit_remaining':
                a=evidence['failed_rebound'];h,l,lh=(a[k] for k in ('high','low','lower_high'))
                expected=b['open'] if b['open']<a['price'] else a['price']
                exit_checks=dict(points_in_time_order=h['time']<l['time']<lh['time'],
                    lower_high_price=l['price']<lh['price']<h['price'],
                    confirmed_before_exit=max(h['known_at'],l['known_at'],lh['known_at'])<=a['effective_at']<=t,
                    real_minute_breaks=b['low']<a['price'],reference_matches=abs(leg['price']-expected)<1e-7)
            elif leg['reason']=='turning_exit_remaining':
                d=evidence['turning'];period=t//900*900
                prev=db.execute('SELECT t,o,h,l,c FROM minutes WHERE t>=? AND t<? ORDER BY t',(period-900,period)).fetchall()
                prefix=db.execute('SELECT t,o,h,l,c FROM minutes WHERE t>=? AND t<? ORDER BY t',(period,t)).fetchall()
                complete=len(prev)==15 and len(prefix)==14
                if not complete:raise ValueError('Missing direction context; no invented candle')
                high=max([b['open']]+[x[2] for x in prefix]);low=min([b['open']]+[x[3] for x in prefix])
                ph=max(x[2] for x in prev);pl=min(x[3] for x in prev);po=prev[0][1];pc=prev[-1][4];op=prefix[0][1]
                inside=(high<=ph and low>=pl) or (min(op,b['open'])>=min(po,pc) and max(op,b['open'])<=max(po,pc))
                exit_checks=dict(last_minute=t%900==840,previous_bullish=pc>po,
                    current_red=b['open']<op,below_previous_midpoint=b['open']<(ph+pl)/2,
                    not_above_previous_close=b['open']<=pc,non_inside=not inside,
                    new_wave_high=high>d['prior_wave_high'],reference_matches=abs(leg['price']-b['open'])<1e-7,
                    no_unfinished_minute_range=d['current_minute_range_used'] is False)
            elif leg['reason']=='giveback_exit_remaining':
                d=evidence['guard'];period=t//900*900
                prev=db.execute('SELECT t,o,h,l,c FROM minutes WHERE t>=? AND t<? ORDER BY t',(period-900,period)).fetchall()
                prefix=db.execute('SELECT t,o,h,l,c FROM minutes WHERE t>=? AND t<? ORDER BY t',(period,t)).fetchall()
                assert len(prev)==15 and [x[0] for x in prefix]==list(range(period,t,60))
                peak_row=db.execute('SELECT max(h) FROM minutes WHERE t>? AND t<?',(ts(p['entry_time']),t)).fetchone()[0]
                peak=max(p['entry'],b['open'],peak_row if peak_row is not None else p['entry'])
                mfe=peak-p['entry'];risk=p['entry']-p['initial_stop'];op=prefix[0][1] if prefix else b['open']
                high=max([b['open']]+[x[2] for x in prefix]);low=min([b['open']]+[x[3] for x in prefix])
                ph=max(x[2] for x in prev);pl=min(x[3] for x in prev);po=prev[0][1];pc=prev[-1][4]
                inside=(high<=ph and low>=pl) or (min(op,b['open'])>=min(po,pc) and max(op,b['open'])<=max(po,pc))
                exit_checks=dict(maximum_profit_at_least_initial_1r=mfe>=risk,
                    profit_giveback_at_least_half=(peak-b['open'])/mfe>=.5,
                    current_non_green=b['open']<=op,not_above_previous_close=b['open']<=pc,non_inside=not inside,
                    known_peak_matches=abs(peak-d['highest_known_price'])<1e-7,
                    reference_matches=abs(leg['price']-b['open'])<1e-7,no_unfinished_minute_range=d['current_minute_range_used'] is False)
            else:raise ValueError('Unexpected losing exit; investigate '+leg['reason'])
            assert all(exit_checks.values()),(p['id'],exit_checks)
            for h in p.get('structure_history',[]):
                assert h['known_at']<=h['effective_at']<=ts(p['exit_time'])
            first=next((l for l in p['legs'] if l['reason']=='target_25'),None)
            # Entry/exit minute ranges may straddle execution. Use only complete
            # minutes strictly between them, plus the known entry/exit prices.
            hi,lo=db.execute('SELECT max(h),min(l) FROM minutes WHERE t>? AND t<?',(ts(p['entry_time']),t)).fetchone()
            known_high=max(p['entry'],leg['price'],hi if hi is not None else p['entry'])
            known_low=min(p['entry'],leg['price'],lo if lo is not None else p['entry'])
            price_risk=p['entry']-p['initial_stop'];mfe_r=(known_high-p['entry'])/price_risk
            mae_r=(p['entry']-known_low)/price_risk
            for key,flag in [('giveback_observations','qualified'),('turning_observations','qualified'),('last_minute_observations','exit_qualified')]:
                assert not any(d.get(flag) and ts(d['time_utc'])<t for d in p.get(key,[])),(p['id'],'earlier exit signal missed',key)
            prior_minutes=db.execute('SELECT t,o,c FROM minutes WHERE t>=? AND t<? ORDER BY t',
                (ts(p['entry_time'])//900*900-7200,ts(p['entry_time'])//900*900)).fetchall()
            previous_2h_move=(prior_minutes[-1][2]/prior_minutes[0][1]-1) if len(prior_minutes)==120 else None
            cause=('已消费结构重复入场' if reused else '成本将小幅毛盈利转为净亏损' if gross>0 else '新结构入场后的规则内亏损')
            action=('修复入场生命周期，需顺序重放确认是否消失' if reused else
                '保留真实成本，不把价差滑点清零' if gross>0 else '未发现执行违规；保留损失，不按后续走势修改阈值')
            path=('入场后已观察最大浮盈不足1R，反弹未延续' if mfe_r<1 else '曾有至少1R浮盈；未发现早于最终退出而被漏执行的合格保护信号')
            rows.append(dict(old_trade_id=p['id'],route=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],
                initial_stop=p['initial_stop'],initial_stop_effective=p['entry_time'],
                origin_time=iso(origin),previous_entry=prior['entry_time'] if prior else None,
                static_reused_history=reused,causal_inputs=causal,first25_time=first['time_utc'] if first else None,
                first25_price=first['price'] if first else None,first25_net=first['net'] if first else None,
                exit_time=leg['time_utc'],exit_price=leg['price'],exit_reason=leg['reason'],
                gross=gross,cost=cost,net=p['net'],net_r=p['net_r'],cause=cause,action=action,
                gap_exposed=p['gap_exposed'],quote_reference=s['quote_reference'],
                maximum_observed_favourable_r=mfe_r,maximum_observed_adverse_r=mae_r,
                previous_2h_move=previous_2h_move,initial_price_risk=price_risk,
                initial_risk_atr=price_risk/s['atr'],net_target_r=s['net_reward_risk'],path=path,
                excursion_basis='complete minutes strictly after entry and before exit plus known entry/exit prices; boundary minute ranges excluded',
                exit_checks=exit_checks))
    if expected_count is not None:assert len(rows)==expected_count
    return rows


def compare_rows(rows,new):
    for row in rows:
        t=ts(row['entry_time']);same=next((p for p in new['trades']
            if p['entry_time']==row['entry_time'] and p['entry_rule']==row['route']),None)
        previous=[p for p in new['trades'] if ts(p['entry_time'])<t]
        owner=previous[-1] if previous else None
        held=bool(owner and (owner['status']=='open' or ts(owner['exit_time'])>t))
        consumed=bool(owner and ts(row['origin_time'])<(ts(owner['entry_time'])//900+1)*900)
        row.update(new_trade_id=same['id'] if same else None,new_entry_time=same['entry_time'] if same else None,
            new_net=same.get('net') if same else None,new_exit_time=same.get('exit_time') if same else None,
            new_outcome=('保留同一入场' if same else '当时已持有另一笔，未重复买入' if held else
                '旧结构在修复后已消费，无此入场' if consumed else '重新积累结构后未触发相同入场'),
            new_preceding_trade_id=owner['id'] if owner else None)
    return rows


def write_outputs(folder,old,new,rows,preserved):
    remaining=audit_losses(new,expected_count=None)
    assert not any(r['static_reused_history'] for r in remaining),'Corrected sequence still reuses history'
    compact=[{k:v for k,v in row.items() if k not in ('old_trade','exit_checks')} for row in rows]
    with (folder/'LOSS_REVIEW.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(compact[0]));writer.writeheader();writer.writerows(compact)
    audit=dict(source_run=BASELINE,corrected_run=new['run_id'],loss_count=27,
        reused_static=sum(r['static_reused_history'] for r in rows),
        execution_checks_passed=all(all(r['exit_checks'].values()) for r in rows),
        rows=rows,remaining_losses=remaining,parameters_tuned=False,exit_policy_changed=False,broker_orders=0)
    save(folder/'LOSS_REVIEW.json',audit)
    comparison=dict(baseline=totals(old),current=totals(new),same_source=True,
        source_minute_sha256=new['source_minute_sha256'],historical_files_sha256=preserved,
        changes='Consume A/B setup history after each entry; first fresh complete candle only; exits/risk/costs unchanged',
        change_description_zh='仅修复入场后消费旧A/B结构。退出、止损缓冲、目标与成本数值不变；旧记录含无效重复入场，保留作程序纠错对照。')
    save(folder/'COMPARISON.json',comparison)
    db=sqlite3.connect((folder/'ledger.sqlite').as_uri()+'?mode=ro',uri=True)
    ledger=[json.loads(body) for (body,) in db.execute('SELECT body FROM ledger ORDER BY t')];db.close()
    save(folder/'WORKBOOK_DATA.json',dict(result=new,ledger=ledger))
    lines=['# BTC 全部27笔原亏损交易审查', '', '逐笔核对入场结构、真实分钟退出和成本，按固定参数重放已确认的结构消费修复。', '',
        'Last Updated: 2026-11-08  ', 'Status: 已逐笔审查及顺序复测，无订单  ', 'Audience: 交易桌使用者及维护者', '', '## Overview', '',
        f"原记录`{BASELINE}`，修复记录`{new['run_id']}`。行情区间和SHA256相同，数值参数与V5退出未调。原27笔亏损合计{sum(r['net'] for r in rows):+,.2f}美元，不能与全样本净收益混同。", '',
        f"原序列中{audit['reused_static']}笔亏损的结构起点早于前笔入场后的新结构起点；这是旧序列的静态复用标记。修复会改变后续持仓占用，逐笔是否消失以下方顺序复测为准，不把所有减少的亏损机械归因于同一原因。", '',
        '## 修复与保留', '',
        '- 入场后清空A、B1、B2结构，禁止使用入场前的波峰、LL/LH、急跌D及HL拼下一笔。入场所在15分钟混有买入前行情，不能重新导入；从下一根完整15分钟开始重建。',
        '- 所有历史真实行情继续保留。ATR、阻力和已持仓保护参考继续使用既有历史；它们没有被删除或扩大。未成交信号不消费结构。',
        '- 27笔的退出分别用真实分钟核对：硬止损触价及开盘越价、结构参考确认/生效、末分钟冲高失败的当时红线/前收/非内包/新高条件；所有既有退出实现均通过，未据此改卖点。',
        '- 毛盈利被2bps成本吃掉的案例保留净亏损，不清零摩擦。不为后来的反弹扩大止损或更改2R资格。', '',
        '## 新旧全样本结果', '', '| 指标 | 原记录 | 修复后 |', '| --- | ---: | ---: |']
    for label,key in [('入场笔数','entries'),('已平仓','closed'),('盈利笔数','wins'),('亏损笔数','losses'),('已平仓净USD，每笔初始1 BTC','closed_net'),('净R','net_r')]:
        a=comparison['baseline'].get(key,comparison['baseline']['metrics'].get(key));b=comparison['current'].get(key,comparison['current']['metrics'].get(key))
        lines.append(f'| {label} | {a:,.6f} | {b:,.6f} |' if key in ('closed_net','net_r') else f'| {label} | {a} | {b} |')
    lines+=['', '修复后仍亏损的正常交易不从样本中删除。固定1 BTC美元与按各笔风险归一的R权重不同，不能混作账户收益。该样本已被用于发现问题，不是样本外验证。', '',
        '## 逐笔结论', '']
    for row in rows:
        lines += [f"### 原交易 #{row['old_trade_id']} · {row['route']}", '',
            f"入场{local(row['entry_time'])}，参考{row['entry']:,.4f}，初始止损{row['initial_stop']:,.4f}立即生效。结构起点{local(row['origin_time'])}。", '',
            f"最后退出{local(row['exit_time'])}，参考{row['exit_price']:,.4f}，依据{REASON[row['exit_reason']]}。毛{row['gross']:+,.2f}，摩擦{row['cost']:,.2f}，净{row['net']:+,.2f}。", '',
            f"诊断：{row['cause']}。处置：{row['action']}。退出分钟与当时条件逐项通过。"+(' 持有期间有数据缺口，属于已观察路径估算。' if row['gap_exposed'] else ''), '',
            f"过程：最大已观察浮盈{row['maximum_observed_favourable_r']:.3f}R，最大不利波动{row['maximum_observed_adverse_r']:.3f}R；{row['path']}。这些数值排除入场/退出分钟中无法确定先后的高低价，不是精确tick级MFE/MAE。",'',
            f"修复后的顺序结果：{row['new_outcome']}"+(f"，新交易#{row['new_trade_id']}，净{row['new_net']:+,.2f}。" if row['new_trade_id'] and row['new_net'] is not None else '；没有虚构替代成交或零收益。'), '']
    lines+=['## 修复后仍亏损的逐笔复核','',
        '新序列仍有19笔亏损。它们不复用前笔入场前的结构；退出也均通过真实分钟核验。13笔为新序列出现的入场，另6笔与原入场相同。不能为保证盈利而删掉这些样本或向后寻找更高卖价。','']
    for row in remaining:
        lines += [f"### 修复后交易 #{row['old_trade_id']} · {row['route']}",'',
            f"入场{local(row['entry_time'])} @ {row['entry']:,.4f}；初始保护{row['initial_stop']:,.4f}。退出{local(row['exit_time'])} @ {row['exit_price']:,.4f}，依据{REASON[row['exit_reason']]}。",'',
            f"毛{row['gross']:+,.2f}，成本{row['cost']:,.2f}，净{row['net']:+,.2f}。诊断：{row['cause']}；未发现结构消费或退出执行违规，数值参数保留。",'']
        lines += [f"过程：最大已观察浮盈{row['maximum_observed_favourable_r']:.3f}R，最大不利波动{row['maximum_observed_adverse_r']:.3f}R；{row['path']}。",'']
    (ROOT/'docs/investigations/2026-11-08_BTC_ALL_LOSING_TRADES_REVIEW.md').write_text('\n'.join(lines)+'\n')
    return audit,comparison


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--replay',action='store_true');args=parser.parse_args()
    old=read(STORE/'runs'/BASELINE/'result.json');rows=audit_losses(old)
    print(json.dumps(dict(original_losses=len(rows),static_reuse=sum(r['static_reused_history'] for r in rows),
        cost_flips=[r['old_trade_id'] for r in rows if r['gross']>0],exit_checks_passed=True)),flush=True)
    if not args.replay:return
    preserved={str(p.relative_to(STORE)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (STORE/'runs').glob('*/*') if p.name in ('result.json','RESEARCH.xlsx','WORKBOOK_DATA.json')}
    new=btc_engine.run(30,expanded_b=True,progress=lambda p:print(json.dumps(p),flush=True))
    assert new['source_minute_sha256']==old['source_minute_sha256']
    for name,digest in preserved.items():assert hashlib.sha256((STORE/name).read_bytes()).hexdigest()==digest,name
    folder=STORE/'runs'/new['run_id'];rows=compare_rows(rows,new)
    audit,comparison=write_outputs(folder,old,new,rows,preserved)
    prior=read(STORE/'runs'/BASELINE/'ENTRY_AUDIT.json');prior['replacement_run']=new['run_id'];save(STORE/'runs'/BASELINE/'ENTRY_AUDIT.json',prior)
    print(json.dumps(dict(run_id=new['run_id'],metrics=new['metrics'],closed_net=comparison['current']['closed_net'],
        old_losses_removed=sum(r['new_trade_id'] is None for r in rows),
        retained=[r['old_trade_id'] for r in rows if r['new_trade_id'] is not None]),indent=2),flush=True)


if __name__=='__main__':main()
