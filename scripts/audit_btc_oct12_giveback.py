"""Two fixed October 12 cases: diagnostic comparison, not approved exits.

Numerical hypotheses are declared, not optimized: 1 initial R of favourable
excursion, then half-profit giveback. Compare confirmation policies at actual
minute opens. No monthly engine, broker, saved run or prior audit is changed.
"""
import copy
import csv
from dataclasses import replace
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from audit_btc_oct12_b_branches import FOLDER,BASELINE,NominatedCase,load,local
from trading_desk.btc_data import STORE,ts,iso,save
from trading_desk.btc_engine import aggregate
from trading_desk.btc_structure_exits import StructureExitMixin,giveback_diagnostic

OUTPUT=FOLDER.parent/'oct12_giveback_comparison'
VARIANTS=('baseline','half_1r','half_1r_direction_inside','lastminute_1r_direction_inside')
CUTOFFS=(ts('2026-10-12T11:00:00-04:00'),ts('2026-10-13T01:45:00-04:00'))


def observation(position,b,observations):
    period=b['t']//900*900
    prior=[x for x in observations if period-900<=x['t']<period]
    prefix=[x for x in observations if period<=x['t']<b['t']]
    d=giveback_diagnostic(position['entry'],position['initial_stop'],ts(position['entry_time']),
        b,observations,b['open'])
    risk=position['entry']-position['initial_stop']
    d.update(initial_risk=risk,mfe_r=d['max_favourable_excursion']/risk if risk>0 else None,
        arm_1r=risk>0 and d['max_favourable_excursion']>=risk,
        reference_context_complete=False,non_green=None,not_above_previous_close=None,
        full_range_inside=None,body_inside=None,inside_exempt=None,last_minute=b['t']%900==840)
    if ([x['t'] for x in prior]!=list(range(period-900,period,60))
            or [x['t'] for x in prefix]!=list(range(period,b['t'],60))):return d
    prev=aggregate(prior,900)
    opening=prefix[0]['open'] if prefix else b['open']
    high=max([b['open']]+[x['high'] for x in prefix]);low=min([b['open']]+[x['low'] for x in prefix])
    body=sorted((opening,b['open']));previous_body=sorted((prev['open'],prev['close']))
    d.update(reference_context_complete=True,opening_15m=opening,previous_close=prev['close'],
        previous_high=prev['high'],previous_low=prev['low'],observed_high=high,observed_low=low,
        non_green=b['open']<=opening,not_above_previous_close=b['open']<=prev['close'],
        full_range_inside=high<=prev['high'] and low>=prev['low'],
        body_inside=body[0]>=previous_body[0] and body[1]<=previous_body[1])
    d['inside_exempt']=d['full_range_inside'] or d['body_inside']
    return d


def qualifies(d,variant):
    if variant=='baseline':return False
    core=d['arm_1r'] and d['giveback_fraction'] is not None and d['giveback_fraction']>=.5
    if variant=='half_1r':return core
    confirmed=core and d['reference_context_complete'] and d['non_green'] and d['not_above_previous_close'] and not d['inside_exempt']
    if variant=='half_1r_direction_inside':return confirmed
    if variant=='lastminute_1r_direction_inside':return confirmed and d['last_minute']
    raise ValueError('Unknown declared hypothesis; do not optimize thresholds')


class StudyCase(StructureExitMixin,NominatedCase):
    def __init__(self,nominated,cutoff,db,minutes,variant):
        super().__init__(nominated,db,exit_policy='approved')
        self.end=cutoff;self.study_minutes=minutes;self.variant=variant
        self.policy='giveback-two-case-hypothesis-'+variant
        self.cfg=replace(self.cfg,version=self.policy)

    def apply_exits(self,b):
        p=self.position;d=observation(p,b,self.study_minutes)
        # Known opening protection precedes all other opening decisions. A
        # qualifying opening exit precedes unresolved later H/L within a minute.
        if qualifies(d,self.variant) and b['open']>p['stop']:
            p.setdefault('giveback_candidate_exits',[]).append(copy.deepcopy(d))
            self.event('giveback_candidate_exit',b['t'],trade_id=p['id'],price=b['open'],
                variant=self.variant,reason='unapproved two-case hypothesis, actual minute-open reference')
            self.close_part(b,b['open'],p['remaining'],'giveback_candidate_exit')
            return
        super().apply_exits(b)


def simulate(old,minutes,cutoff,variant):
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=StudyCase(ts(old['nominated_bar']),cutoff,db,minutes,variant)
    for b in minutes:
        if b['t']>=cutoff:break
        e.minute(b)
    r=e.finish();db.close()
    if len(r['trades'])!=1:raise ValueError('Expected one fixed entry, no replacements')
    p=r['trades'][0]
    if any(p[k]!=old['trade'][k] for k in ('entry','entry_time','initial_stop','t1','t2')):
        raise ValueError('Entry/stop/target changed')
    return dict(variant=variant,trade=p,realized_net=sum(l['net'] for l in p['legs']),
        approved_for_execution=False,valuation_is_realized=False)


def review():
    source,minutes=load()
    original=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())
    cases=[]
    for old,cutoff in zip(original['cases'],CUTOFFS,strict=True):
        p=old['trade'];entry_at=ts(p['entry_time']);risk=p['entry']-p['initial_stop']
        observed=[b for b in minutes if entry_at<b['t']<cutoff]
        if [b['t'] for b in observed]!=list(range(entry_at+60,cutoff,60)):
            raise ValueError('Missing minutes; do not invent continuity')
        diagnostics=[observation(p,b,minutes) for b in observed]
        by_t={ts(d['time_utc']):d for d in diagnostics}
        rows=[];peak=p['entry']
        first_raw=None;upper_bound=None
        # First-touch illustration uses only the peak already known at that
        # minute's opening; never combine its unknown new high with its low.
        for b in observed:
            known=max(peak,b['open']);level=(known+p['entry'])/2
            if first_raw is None and known-p['entry']>=risk and b['low']<=level:
                price=b['open'] if b['open']<=level else level
                first_raw=dict(time_utc=iso(b['t']),interval_end=iso(b['t']+60),reference_price=price,
                    highest_known_price=known,exact_second_unverified=True,
                    current_minute_high_used=False,not_a_simulated_leg=True)
            peak=max(peak,b['high'])
            if peak-p['entry']>=risk:
                bound=(peak-b['low'])/(peak-p['entry'])
                if upper_bound is None or bound>upper_bound['fraction']:
                    upper_bound=dict(time_utc=iso(b['t']),fraction=bound,high=peak,low=b['low'],
                        actual_order_known=False,
                        basis='conservative high-first/low-second envelope, not an actual path or fill')
        for period in range(entry_at//900*900,cutoff,900):
            group=[b for b in minutes if period<=b['t']<period+900]
            if [b['t'] for b in group]!=list(range(period,period+900,60)):
                raise ValueError('Incomplete 15m group; cannot report a complete candle')
            bar=aggregate(group,900)
            observations=[by_t[b['t']] for b in group if b['t'] in by_t]
            eligible=[d for d in observations if d['arm_1r']]
            worst=max(eligible,key=lambda d:d['giveback_fraction']) if eligible else None
            last=by_t.get(period+840)
            final_known=[b for b in minutes if entry_at<b['t']<period+900]
            closing_peak=max([p['entry'],bar['close']]+[b['high'] for b in final_known])
            close_giveback=(closing_peak-bar['close'])/(closing_peak-p['entry']) if closing_peak>p['entry'] else None
            rows.append(dict(time_utc=iso(period),time_ny=local(period),end=iso(period+900),
                ohlc={k:bar[k] for k in ('open','high','low','close')},completed_colour='green' if bar['close']>bar['open'] else 'red' if bar['close']<bar['open'] else 'doji',
                close_giveback_fraction=close_giveback,closing_peak=closing_peak,
                eligible_worst_open_observation=worst,last_minute_observation=last,
                first_qualifying_by_variant={v:next((d for d in observations if qualifies(d,v)),None) for v in VARIANTS[1:]},
                note='full candle/closing metrics known at end only; minute-open candidates use only their own known context'))
        cases.append(dict(nominated_bar=old['nominated_bar'],cutoff=iso(cutoff),entry=p['entry'],entry_time=p['entry_time'],
            initial_stop=p['initial_stop'],initial_risk=risk,rows=rows,
            first_intrabar_half_touch=first_raw,
            intraminute_giveback_upper_bound=upper_bound,
            variants=[simulate(old,minutes,cutoff,v) for v in VARIANTS],
            minute_open_diagnostics=diagnostics,
            maximum_armed_giveback=max((d['giveback_fraction'] for d in diagnostics if d['arm_1r']),default=None),
            initial_ratio_warning=next((d for d in diagnostics if d['giveback_fraction'] is not None and d['giveback_fraction']>=.5),None)))
    return dict(status='complete',source=source,cases=cases,month_rerun=False,broker_orders=0,
        approved_for_execution=False,parameters=dict(minimum_favourable_excursion_initial_r=1,giveback_fraction=.5,
            numeric_search_performed=False,sampling='actual 1m opening observations, current 15m state; not final candle colour'),
        costs='unchanged 2bps each way, per initial BTC; zero commission signal model, not actual ETF fills',
        baseline='same V3 structure policy for both entries; warnings only, T1 25%, no fixed T2',
        conclusion='in-sample two-case separation only; a profitable early exit is not evidence of trend reversal',
        code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__).resolve(),ROOT/'trading_desk/btc_structure_exits.py')})


def report(r):
    labels={'baseline':'V3结构基准','half_1r':'1R启用＋回吐一半（不保留内包豁免）',
        'half_1r_direction_inside':'1R＋一半回吐＋当时转弱＋非内包',
        'lastminute_1r_direction_inside':'同上，但只在最后1分钟观察'}
    out=['# BTC 10月12日：浮盈回吐与两笔逐根退出对照','',
        '固定两个入场，比较盘中保护、内包豁免和末分钟确认的取舍，不搜索参数或推广月度。','',
        'Last Updated: 2026-11-08  ','Status: 两例研究假设；未批准为执行规则；未重跑整月  ',
        'Audience: Trading Desk使用者及研究维护者','', '## Overview','',
        '所有时间为纽约EDT。早盘观察09:33入场至11:00，晚盘观察21:00入场至次日01:45。两笔都为B1，不能用事后走势重新定义入场。相同V3基准保留T1卖25%、中点仅预警、无固定T2、原硬止损及已确认15分钟结构保护。',
        '', '## 指标怎样使用','',
        '- 浮盈回吐率G＝（入场后当时已知高点H−当前参考P）÷（H−入场E）。它衡量让出了多少最大浮盈，不是预测下跌概率。',
        '- 先有足够浮盈才讨论保护：本次明确用最大浮盈≥初始1R作研究启用条件。没有该条件，刚入场的微小波动就可能得到很高回吐率。1R是新增候选条件，不是此前已批准参数。',
        '- 回吐一半（50%）仅作为单个易解释的假设，沿用此前讨论的一半概念；未扫描40%、45%等数值来优化结果。这两笔仍属于样本内研究，不能据此认定50%最佳。',
        '- 区分“当时可卖”与“后来证明走弱”：即使触发获利保护，下一分钟仍可能恢复上涨。等待完整15分钟确认会更慢；当前最终颜色不能提前使用。',
        '', '## 明确比较的三个候选','',
        '1. 1R启用后G≥50%，在实际1分钟开盘观察点退出余仓。该版本会覆盖内包整理持有，单独展示而不替代已批准规则。',
        '2. 保留内包豁免：在1的基础上，还要求当时价格≤本根15分钟开盘且≤前根完整收盘，并且当时实体和截至当时全振幅均不在前根内部。所有条件同时满足才退出。',
        '3. 条件同2，但只在15分钟的最后1分钟首价检查。这个更慢的观察政策单独对照，不偷用最终收盘。',
        '', '## 条件对照的模拟结果','',
        '| 指定入场 | 版本 | 实际模型退出腿（纽约） | 已实现净盈亏 | 截止时余仓 |',
        '| --- | --- | --- | ---: | ---: |']
    for c in r['cases']:
        for v in c['variants']:
            p=v['trade'];legs='；'.join(f"{local(l['time_utc'])} {l['fraction']:.0%} @ {l['price']:,.6f} ({l['reason']})" for l in p['legs'])
            out.append(f"| {c['nominated_bar'][11:16]} | {labels[v['variant']]} | {legs or '无退出'} | {v['realized_net']:,.6f} | {p['remaining']:.0%} |")
    out+=['', '均按初始1 BTC及原成本计算。已平仓路径不能再算后来T1／反弹的收益；晚盘未卖75%没有已实现盈亏，本表不把浮盈混进净收益。',
        '', '## 早盘的逐步区别','',
        '10:05盘中，事先已知高点82,950，对应一半浮盈保护参考82,760.6725，实际分钟低点已穿过；该触及只定位10:05–10:06区间，未模拟成精确秒成交。',
        '10:06分钟首价82,752.0485，回吐52.28%，但当时实体仍在09:45完整K线实体内部。候选1会退出，候选2必须继续持有。10:06这根1分钟随后又涨到82,891.8455收盘，10:11触及T1——早退属于获利保护取舍，不能称为已经确认趋势反转。',
        '10:17首价回吐57.32%，10:18首价回吐63.13%，当时仍内包。10:18分钟后来下探前根低点以下，这件事到10:19首价观察时已知。',
        '10:19首价82,754.706，回吐60.94%，当时非绿、不高于前收盘，实体和已观察振幅均非内包；候选2首次同时满足。此前10:11已卖25%，这里只卖余75%。10:15–10:30这根后来仍收绿，不能用未来收绿倒改盘中决定。',
        '若坚持只在最后1分钟检查全部条件，10:14因内包、10:29因回吐不足且当时绿线均不卖，直到10:44才触发；这说明等到末分钟会归还更多利润。',
        '', '## 晚盘为什么继续持有','',
        f"在本次实际分钟开盘样本中，启用1R后最大回吐率为{r['cases'][1]['maximum_armed_giveback']:.4%}，没有达到50%。22:31先前V2退出点的7.57%不代表全程最大值。小阴线或中点预警不单独导致卖出；T1仍在22:57卖25%，所有候选余75%到01:45仍持有。",
        f"另作分钟内上限核对：即使保守地把每分钟最高放在最低之前，启用1R后的最大回吐上限也只有{r['cases'][1]['intraminute_giveback_upper_bound']['fraction']:.4%}（{local(r['cases'][1]['intraminute_giveback_upper_bound']['time_utc'])}），仍低于50%。这不是声称实际高低发生顺序，只用于证明并非分钟首价采样漏掉了本例的一半回吐。",
        '不是给晚盘更宽的参数：两笔使用同一个启用条件和回吐阈值。晚盘实际回吐浅，结构也未破，故没有该获利保护候选。',
        '', '## 两笔逐根表','',
        '“本根最深回吐”仅统计满足1R启用后的实际分钟首价，不能当作逐笔行情全程极值；“完整收盘回吐”只在该行结束后可知。首次候选不等于在每根重复卖出，实际腿见上表。一旦某版本平仓，后续行仅为行情对照，不再算该版本持仓浮盈。']
    for c in r['cases']:
        out+=['',f"### 指定{c['nominated_bar'][11:16]}入场案例",'',
            '| 15分钟开始→结束 | 完整收盘／颜色 | 完整收盘回吐 | 本根启用后最深首价回吐／时间 | 最后1分钟回吐／当时内包 | 非内包盘中候选首次观察 |',
            '| --- | --- | ---: | --- | --- | --- |']
        for b in c['rows']:
            w=b['eligible_worst_open_observation'];last=b['last_minute_observation'];event=b['first_qualifying_by_variant']['half_1r_direction_inside']
            worst=f"{w['giveback_fraction']:.2%} / {local(w['time_utc'])[11:16]}" if w else '尚无1R启用观察'
            lp=f"{last['giveback_fraction']:.2%} / {'内包' if last['inside_exempt'] else '非内包'}" if last and last['giveback_fraction'] is not None else '不可计算'
            ep=f"{local(event['time_utc'])[11:16]} @ {event['reference_price']:,.6f}" if event else '无'
            cg=f"{b['close_giveback_fraction']:.2%}" if b['close_giveback_fraction'] is not None else '不可计算'
            out.append(f"| {b['time_ny']}→{local(b['end'])[11:16]} | {b['ohlc']['close']:,.6f} / {b['completed_colour']} | {cg} | {worst} | {lp} | {ep} |")
    out+=['', '## 解读与范围','',
        '尊重既有内包豁免时，候选2是本次较一致的研究方案：先有至少1R最大浮盈，一半以上回吐作为风险预警，再等当时方向转弱且非内包；结构保护和硬止损继续独立。它不是已确认最优规则，也不保证避免所有亏损。',
        '早盘10:19仍在随后收绿的15分钟K线内部。因此，“不等整根收盘”与“保证不卖在最终收绿的K线”不能同时实现；是否采用获利保护而承受卖早，需要作为明确策略取舍。',
        f"真实Alpaca来源SHA256 `{r['source']['sha256']}`。每项诊断仅使用其检查时点已知数据；没有补值，没有月度重跑、真实或paper订单，没有覆盖旧研究或默认退出参数。",
        '同目录REVIEW.json包含每分钟证据与所有条件性路径，LEDGER.csv包含两笔逐根对照。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    watched=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json',
        FOLDER.parent/'oct12_structure_exit/REVIEW.json',FOLDER.parent/'oct12_direction_filtered_exits/REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    result=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):raise ValueError('Prior result changed')
    if dirs!=sorted(p.name for p in (STORE/'runs').iterdir()):raise ValueError('Monthly run created')
    result['prior_artifact_sha256']={str(p.relative_to(ROOT)):h for p,h in before.items()}
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'REVIEW.json',result)
    with (OUTPUT/'LEDGER.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['nominated_bar','time_ny','end_ny','open','high','low','close','completed_colour','close_giveback_fraction','worst_armed_open_giveback','worst_armed_open_time','last_minute_giveback','last_minute_inside','candidate2_first_time','candidate2_first_price'])
        writer.writeheader()
        for c in result['cases']:
            for b in c['rows']:
                w=b['eligible_worst_open_observation'] or {};l=b['last_minute_observation'] or {};e=b['first_qualifying_by_variant']['half_1r_direction_inside'] or {}
                writer.writerow(dict(nominated_bar=c['nominated_bar'],time_ny=b['time_ny'],end_ny=local(b['end']),**b['ohlc'],completed_colour=b['completed_colour'],close_giveback_fraction=b['close_giveback_fraction'],worst_armed_open_giveback=w.get('giveback_fraction'),worst_armed_open_time=w.get('time_utc'),last_minute_giveback=l.get('giveback_fraction'),last_minute_inside=l.get('inside_exempt'),candidate2_first_time=e.get('time_utc'),candidate2_first_price=e.get('reference_price')))
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_GIVEBACK_COMPARISON.md').write_text(report(result))
    print(json.dumps([dict(entry=c['nominated_bar'],max_open_giveback=c['maximum_armed_giveback'],variants=[dict(name=v['variant'],status=v['trade']['status'],legs=v['trade']['legs'],realized_net=v['realized_net']) for v in c['variants']]) for c in result['cases']]))
