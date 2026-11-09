"""Three frozen trades: causal 15m/1m pullback versus failure review, no replay."""
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import aggregate

RUN='20261109T041525Z-30-ab'
NY=ZoneInfo('America/New_York')
DEST=STORE/'investigations/RELEASE_0_1_PULLBACK_CASES.json'


def clock(t):
    return datetime.fromisoformat(t.replace('Z','+00:00')).astimezone(NY).strftime('%m/%d %H:%M %Z')


NOTES={
5:{'08:30':'本根首次达到既有2ATR急跌标准，至08:45完整后可知；不事后回填更早入场。',
   '08:45':'继续创低，候选D向下延伸；未持仓，原旧D不能算守住。',
   '09:00':'继续下探，尚未出现入场后的独立15分钟结构。',
   '09:15':'最低80,136.2672，收盘贴近低位；本根结束后才能确认。',
   '09:30':'本根D到09:45才完整确认；它仍是0.1允许的激进B1参考，并非独立HL。',
   '09:45':'09:46可知第一分钟已跌回突破价；09:53–09:54穿D及硬止损。10:00的完整形状属于退出后对照，不能提前用于卖出。'},
32:{'11:00':'本根低点高于原D，至11:15完整后提供原突破参考；L2仍为空。',
    '11:15':'突破后上冲至76,927.482；11:30完整时仍高于买入价。波峰确认需等待右邻。',
    '11:30':'这是前根全振幅内部的回撤，不能仅因阴线判失败。',
    '11:45':'相较前根同时降低高点与低点；到12:00才能确认本根形状。',
    '12:00':'到12:15已连续两根较低高点／较低低点，并收回原突破价下方：转弱警告，尚无已确认H-L-LH破低卖点。两根只是本例描述，不是新增门槛。',
    '12:15':'继续下探，但原D仍未破；1R浮盈门槛也没有达到。',
    '12:30':'虽收阳，最高及最低仍低于前根；颜色本身不代表结构转强。',
    '13:00':'本根低点75,558.5075仍高于原D；到13:30右邻完整后才可确认该L。',
    '13:15':'本根完成后可确认13:00的回踩L；不能把L的发生时间当作已确认时间。',
    '13:45':'形成局部较低高点候选，右邻完成至14:15才确认。',
    '14:00':'14:15才首次生效H-L-LH对应的75,558.5075破位参考；生效不等于已经卖出。',
    '14:15':'随后实际分钟重夺当时LH，旧组合取消；不能仍按已失效形态预先卖出。',
    '14:30':'本根完整收回原突破价上方，说明12:15失守不能单独证明不可逆失败；仍未收复早先76,927.482波峰。',
    '14:45':'仍在原波峰下方，回收突破线不等于再创新高。',
    '15:00':'再次收回突破价下方；15:15确认新的失败反弹参考，仍需真正破低。',
    '17:15':'最终LH候选75,998.10，须等17:30右邻完成。',
    '17:30':'至17:45最终LH完整确认，75,558.5075退出参考生效。',
    '17:45':'17:47–17:48严格破已确认L，按0.1退出100%；18:00完整收盘不用于17:47决定。'},
30:{'07:15':'较大D77,905.3175与前根最高78,239.90到07:30已知；保留原D及硬止损。',
    '07:30':'07:31盘中突破入场；07:45完成时已收回突破线下方，尚不足以判失败。',
    '07:45':'再回踩至78,026.42，仍在原D之上；随后反弹和创新高才能确认有效HL保护，不能提前使用。',
    '08:00':'本根新高78,439.2275；到08:15，前述HL及破高都已知，15分钟结构参考78,026.42才生效。',
    '09:00':'回撤低点78,093.095仍高于已生效78,026.42；当时是待确认的较高低点，不是已破结构。',
    '09:15':'09:30可知完整阴线收在突破价下方，但它比前根高点及低点都高；78,026.42结构参考未破，不能仅因失守买入价卖出。',
    '09:30':'只有随后真实行情才确认延续：09:40原T1卖25%；09:45新高完成后结构参考上移78,093.095。不能把这根大涨倒用于09:30开盘决策。',
    '10:15':'新波峰81,119.625；完整波峰确认还需右邻。',
    '10:45':'较高区域回踩L80,072.859，至11:15右邻完成才确认。',
    '13:00':'最后用于退出的LH候选80,646.982，尚需右邻确认。',
    '13:15':'到13:30最终LH完整确认，80,072.859破位参考生效。',
    '14:00':'14:05–14:06破已确认L，退出余75%；14:15完整K线形状属于退出后对照。'}
}


def review():
    result=read(STORE/'runs'/RUN/'result.json');cases=[]
    ledger=sqlite3.connect((STORE/'runs'/RUN/'ledger.sqlite').as_uri()+'?mode=ro',uri=True)
    try:
      with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for ident in (5,32,30):
            p=next(p for p in result['trades'] if p['id']==ident)
            signal=next(s for s in result['signals'] if s['id']==p['signal_id'])
            entry=ts(p['entry_time']);exit_at=ts(p['exit_time'])
            start=min(entry//900*900-3600,signal['setup_evidence']['impulse']['t']-900)
            end=(exit_at//900+1)*900
            raw=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n)
                for t,o,h,l,c,v,n in db.execute('SELECT t,o,h,l,c,v,n FROM minutes WHERE t>=? AND t<? ORDER BY t',(start,end))]
            raw_map={b['t']:b for b in raw}
            events=[];saved_rows={}
            for (body,) in ledger.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(start,end)):
                row=json.loads(body);saved_rows[row['t']]=row
                events.extend(e for e in row['events'] if e.get('trade_id')==ident)
            selected_types={'entry','stop','target_25','structure_reference_raised','failed_rebound_reference','failed_rebound_reclaimed','failed_rebound_exit_remaining'}
            selected_events=[copy.deepcopy(e) for e in events if e['type'] in selected_types]
            bars=[];previous=None;down_count=0
            for t in range(start,end,900):
                observed=[raw_map[k] for k in range(t,t+900,60) if k in raw_map]
                if not observed:previous=None;down_count=0;continue
                b=aggregate(observed,900);full=[x['t'] for x in observed]==list(range(t,t+900,60))
                if full:
                    assert t in saved_rows,'Original 15m ledger row absent'
                    assert all(abs(b[k]-saved_rows[t][k])<1e-7 for k in ('open','high','low','close'))
                lower_pair=bool(full and previous and previous['complete'] and b['high']<previous['high'] and b['low']<previous['low'])
                higher_pair=bool(full and previous and previous['complete'] and b['high']>previous['high'] and b['low']>previous['low'])
                down_count=down_count+1 if lower_pair else 0
                inside=None;body_inside=None
                if full and previous and previous['complete']:
                    inside=b['high']<=previous['high'] and b['low']>=previous['low']
                    body_inside=min(b['open'],b['close'])>=min(previous['open'],previous['close']) and max(b['open'],b['close'])<=max(previous['open'],previous['close'])
                known=t+900
                active=[h for h in p.get('structure_history',[]) if h['effective_at']<=min(known,exit_at)]
                ref=active[-1] if active else None
                bar_events=[e for e in selected_events if t<=ts(e['time_utc'])<known]
                close_events=[e for e in selected_events if ts(e['time_utc'])==known]
                note=NOTES[ident].get(datetime.fromtimestamp(t,NY).strftime('%H:%M'),'本根无新增已执行规则；按当时已知参考继续观察。')
                bars.append(dict(time=iso(t),end=iso(known),open=b['open'],high=b['high'],low=b['low'],close=b['close'],
                    observed_minutes=len(observed),complete=full,close_known_at=iso(known) if full else None,
                    completed_after_exit=known>exit_at,entirely_before_entry=known<=entry,
                    below_original_trigger=b['close']<p['references']['trigger'] if full else None,
                    original_d=p['references']['l1']['price'],d_held_over_full_bar=b['low']>=p['references']['l1']['price'],
                    lower_high_lower_low=lower_pair,higher_high_higher_low=higher_pair,consecutive_lower_pairs=down_count,
                    full_inside=inside,body_inside=body_inside,active_15m_reference=copy.deepcopy(ref),
                    events=bar_events,events_at_close=close_events,note=note))
                previous=dict(**b,complete=full)
            minutes=[]
            for b in raw:
                t=b['t']
                minutes.append(dict(**b,time=iso(t),end=iso(t+60),close_known_at=iso(t+60),
                    phase='before_entry' if t<entry else 'entry_minute_range_order_unknown' if t==entry else 'exit_minute_range_order_unknown' if t==exit_at else 'held' if t<exit_at else 'after_exit_comparison_only',
                    below_original_trigger=b['close']<p['references']['trigger'],d_breached=b['low']<p['references']['l1']['price'],
                    stop_touched=b['low']<=p['initial_stop']))
            failure_events=[e for e in selected_events if e['type'] in ('failed_rebound_reference','failed_rebound_reclaimed')]
            cases.append(dict(trade_id=ident,entry=copy.deepcopy({k:p[k] for k in ('entry_time','entry','initial_stop','references','t1')}),
                original_d=p['references']['l1'],entry_reference_bar_time=signal['previous_bar_time'],
                entry_reference_bar_low=signal['setup_evidence']['stabilization_bar']['low'],
                initial_price_risk=p['entry']-p['initial_stop'],
                max_known_price_mfe_r=max((o.get('mfe_r') or 0 for o in p.get('giveback_observations',[])),default=0),
                bars=bars,minutes=minutes,source_minutes=len(raw),missing_minutes=(end-start)//60-len(raw),
                source_rows_sha256=hashlib.sha256(json.dumps(raw,separators=(',',':')).encode()).hexdigest(),
                legs=p['legs'],net=p['net'],exit_time=p['exit_time'],structure_history=p.get('structure_history',[]),
                failed_rebound_history=p.get('failed_rebound_history',[]),failure_events=failure_events,
                final_exit_evidence=p.get('case_exit_evidence',[])[-1],hard_stop_moved=bool(p.get('stop_history'))))
    finally:ledger.close()
    return dict(source_run=RUN,review_date='2026-11-09',source='Alpaca BTC/USD archived observed minutes',
        timezone='America/New_York',cases=cases,scope='three frozen cases only; no strategy replay or parameter change',
        source_run_sha256=hashlib.sha256((STORE/'runs'/RUN/'result.json').read_bytes()).hexdigest(),
        month_rerun=False,release_modified=False,new_exit_rule_adopted=False,orders_enabled=False)


def report(r):
    lines=['# BTC 0.1：正常回踩与突破失败三笔逐根核验','',
        '固定#5、#32与盈利对照#30，区分警告、结构确认和实际退出。','',
        'Last Updated: 2026-11-09  ','Status: 三笔逐根核验完成；未采用新规则、未重跑整月  ',
        'Audience: 交易学习手册使用者及交易桌维护者','','## Overview','',
        '所有时间为纽约时间；#5为10月15日EDT，#32为11月5日EST，#30为11月4日EST。完整15分钟的OHLC到区间结束才可知。实际触发定位到1分钟区间，秒内顺序及真实ETF成交不明。',
        '源为冻结Release 0.1原38笔中的三笔；只读真实分钟及原逐根记录，不运行策略／回测，不改原止损、目标、成本或表格。',
        '表中升高升低／降高降低只比较相邻两根完整K线的最高与最低，不能当成已确认的独立同级波段H、L、LH，也不用于替换原较大D。波段确认及生效时间另列。', '',
        '## 结论先行','',
        '- 跌回原突破价只是入场动量失守警告，不能单独等同于结构失败。#30在09:30已知收回突破线下方，但回踩低点仍高于已生效结构低点，原条件仍允许持有。随后上涨属于之后的确认，不可倒用于早先决定。',
        '- 原较大D、初始硬止损、已确认15分钟HL、独立H-L-LH退出参考是四种不同用途，不能互相偷换。较大D守住也不保证反弹成功；#32最终在原D之上因已确认失败反弹破低退出。',
        '- #5在09:46已有一分钟跌回突破线的警告，但直到09:53–09:54才穿D及原硬止损；不存在能在8分钟内完成的入场后独立15分钟H-L-LH。不能把10:00完整大阴线当成09:46已知。',
        '- #32在12:15已有连续降高降低的警告，但13:00的L到13:30才确认、首个LH组合到14:15才生效，且随后被重夺LH取消。不是一见转弱就已有可执行的旧规则卖点。',
        '- #30在回踩时守住有效HL，09:15根较前根的高点和低点都高；之后才在09:40卖25%。它最终也出现H-L-LH破位，14:05退出余75%，并非无限期持有。', '',
        '## 三笔关键参考（原0.1）','',
        '| 交易# | 入场时间／价 | 原较大D | 初始止损 | 原净盈亏 |',
        '| --- | --- | ---: | ---: | ---: |']
    for c in r['cases']:
        p=c['entry'];lines.append(f"| {c['trade_id']} | {clock(p['entry_time'])}／{p['entry']:,.4f} | {c['original_d']['price']:,.4f} | {p['initial_stop']:,.4f} | {c['net']:+,.2f} |")
    lines+=['','另一个差异：#32初始价格风险为$960.5097，已知最大价格浮盈约$666.672（0.694R），因此原1R利润保护从未启用；这不等于行情完全没涨过。#30最终上涨及T1都发生在09:30判断之后，不用于倒选持有。']
    for c in r['cases']:
        lines+=['',f"## #{c['trade_id']}：全部15分钟K线（不省略）",'',
            f"本例读取{c['source_minutes']}个真实分钟，缺失{c['missing_minutes']}个；原始切片SHA256 `{c['source_rows_sha256']}`。",
            '“之后才完整”表示该根完整形状在原退出后才知道；仅为行情对照，不用于持有期间卖出。', '',
            '| 纽约K线区间 | O／H／L／C | 完整可知时间／覆盖 | 收盘低于原突破？ | 当根比较／行末结构参考 | 当时解释 |',
            '| --- | --- | --- | --- | --- | --- |']
        for b in c['bars']:
            relation='降高降低' if b['lower_high_lower_low'] else '升高升低' if b['higher_high_higher_low'] else '高低不同时升降'
            ref=b['active_15m_reference'];reftext=f"；15m参考{ref['price']:,.4f}，{clock(iso(ref['effective_at']))}起" if ref else '；无新增15m保护参考'
            available=(clock(b['close_known_at']) if b['complete'] else '不完整')+f"／{b['observed_minutes']}/15"+('；退出后才完整' if b['completed_after_exit'] else '')
            lines.append(f"| {clock(b['time'])} → {clock(b['end'])} | {b['open']:,.4f}／{b['high']:,.4f}／{b['low']:,.4f}／{b['close']:,.4f} | {available} | {'是' if b['below_original_trigger'] else '否' if b['below_original_trigger'] is False else '不可判'} | {relation}{reftext} | {b['note']} |")
        if c['trade_id']==5:
            lines+=['','### #5入场后逐分钟（含退出后对照）','',
                '| 纽约分钟 | O／H／L／C | 完整可知 | 原D是否被本分钟跌破 | 保护是否被触及 | 阶段 |',
                '| --- | --- | --- | --- | --- | --- |']
            for m in c['minutes']:
                if ts(m['time'])<ts(c['entry']['entry_time']):continue
                lines.append(f"| {clock(m['time'])} → {clock(m['end'])} | {m['open']:,.4f}／{m['high']:,.4f}／{m['low']:,.4f}／{m['close']:,.4f} | {clock(m['close_known_at'])} | {'是' if m['d_breached'] else '否'} | {'是' if m['stop_touched'] else '否'} | {m['phase']} |")
            lines+=['','09:53这一分钟的真实范围同时涵盖D与止损。连续价格通常会先经过D，但这里没有tick顺序，不能声称能先在D价无滑点离场；原0.1的止损参考及净-$762.75保持不变。']
        lines+=['','### 原0.1已确认保护与退出事件','']
        for h in c['structure_history']:
            lines.append(f"- 15m HL发生{clock(iso(h['low_time']))}，低点{h['price']:,.4f}；确认{clock(iso(h['known_at']))}，破高确认{clock(iso(h['breakout_known_at']))}，生效{clock(iso(h['effective_at']))}。初始硬止损不变。")
        for e in c['failure_events']:
            if e['type']=='failed_rebound_reference':
                h,l,lh=(e[k] for k in ('high','low','lower_high'))
                lines.append(f"- {clock(e['time_utc'])}失败反弹参考生效：H {h['price']:,.4f}（发生{clock(iso(h['time']))}、确认{clock(iso(h['known_at']))}）；L {l['price']:,.4f}（发生{clock(iso(l['time']))}、确认{clock(iso(l['known_at']))}）；LH {lh['price']:,.4f}（发生{clock(iso(lh['time']))}、确认{clock(iso(lh['known_at']))}）。仍须严格破L才退出。")
            else:lines.append(f"- {clock(e['time_utc'])}重夺LH，之前组合取消；不得按旧组合提前卖出。")
        for l in c['legs']:
            lines.append(f"- 原退出：{clock(l['time_utc'])} → {clock(iso(ts(l['time_utc'])+60))}，{l['fraction']:.0%}，{l['reason']}，价{l['price']:,.4f}，毛{l['gross']:+,.2f}、摩擦{l['cost']:,.2f}、净{l['net']:+,.2f}。")
    lines+=['','## 如何避免误伤#30：先按信息层级判断','',
        '| 当时已知状态 | 能说明什么 | 本次三笔依据 |',
        '| --- | --- | --- |',
        '| 只跌回买入突破价 | 动量警告，不能单独判定失败 | #5、#32、#30都会出现 |',
        '| 仍守住已生效HL／原D，没有已确认LH后破L | 可继续观察，不能承诺反弹一定成功 | #30 09:30仍守78,026.42；#32 12:15原D也仍守住 |',
        '| 连续降低高点及低点且反弹无法恢复原波峰 | 反弹质量恶化，优先审查；不是本次新增卖出门槛 | #32 11:45及12:00两根完成至12:15后可知；#30 09:15则高低同时抬高 |',
        '| 已确认H-L-LH，再严格破对应L | 原0.1独立失败反弹退出可执行，不需要再创新高或达到1R | #32 17:45生效、17:47破75,558.5075；#30 13:30生效、14:05破80,072.859 |',
        '| 原硬止损触发 | 不等待15分钟、颜色或内包过滤，退出实际余仓 | #5 09:53–09:54退出100% |', '',
        '上述观察区分“允许持有”“转弱警告”和“旧规则已触发”，不是提出一条已证明能同时挽救#5、#32并保留#30的规则。#5需要1分钟层面研究才可能更早发现失败，代价是误报更多；#32需要研究如何更早确认持续弱反弹，不能事后把最终L及LH移到过去。', '',
        '## 盈亏与不变项','',
        '#5净-$762.75；#32净-$732.67；#30先25%净+$103.53，再75%净+$1,350.96，合计+$1,454.49。每笔初始1 BTC，ETF零佣金加每边2bps假设，非实盘收益。',
        '0.1、所有月度结果、原工作簿、最新记录与ACTIVE基准均通过前后哈希保护。只有新增三笔审查JSON、本文及交易桌只读展示；未更改策略或提交订单。']
    return '\n'.join(lines)+'\n'


def main():
    paths=[STORE/'latest_run.json',STORE/'releases/ACTIVE.json']+list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))+list((STORE/'runs').glob('*/WORKBOOK_DATA.json'))+list((STORE/'releases/0.1').rglob('*'))
    hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file() and '__pycache__' not in str(p)}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=review();save(DEST,r)
    (ROOT/'docs/investigations/2026-11-09_BTC_RELEASE_0_1_PULLBACK_CASES.md').write_text(report(r))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in hashes.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
    print(json.dumps(dict(cases=[dict(trade=c['trade_id'],bars=len(c['bars']),minutes=c['source_minutes'],missing=c['missing_minutes'],net=c['net']) for c in r['cases']],month_rerun=False,release_modified=False)))


if __name__=='__main__':main()
