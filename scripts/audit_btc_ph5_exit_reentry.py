"""Single-case causal audit only; no parameter changes, new trades or month run."""
from __future__ import annotations
import copy
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso
from trading_desk.btc_live import LIVE
from trading_desk.btc_engine import aggregate
from trading_desk.btc_parent_five import ParentFiveDetector,five_signal
from trading_desk.btc_parent_five_view import PARENT_FIVE_VIEW
from scripts.retest_btc_parent_five import engine,database,preservation,verify_preserved,CASE_START,CASE_END

NY=ZoneInfo('America/New_York')
OUT=ROOT/'reports/btc_ph5_exit_reentry_2026_11_15'


def clock(t):
    if t is None:return '—'
    if isinstance(t,str):t=ts(t)
    return datetime.fromtimestamp(t,NY).strftime('%m/%d %H:%M:%S')


def main():
    before=preservation()
    folder,study=PARENT_FIVE_VIEW.current()
    case=read(folder/'CASE.json')
    protected=[p for p in folder.rglob('*') if p.is_file()]
    protected += [ROOT/'trading_desk/btc_parent_five.py',ROOT/'scripts/retest_btc_parent_five.py',
        folder.parent/'ACTIVE.json']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    original=case['models']['0.1']
    trade=next(p for p in original['trades'] if p['entry_rule']=='PH5')
    decision=ts('2026-11-15T03:20:00-05:00')
    source=LIVE/'sessions'/case['source_session']/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(CASE_END,)).fetchall()
    assert hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest()==case['source_sha256']
    bars=[json.loads(body) for body,_ in records]
    by_time={b['t']:b for b in bars}
    receipt={b['t']:r for b,(_,r) in zip(bars,records)}
    session=read(LIVE/'SESSION.json')
    audits={}
    for model in ('0.1','E1','E2'):
        db=database()
        e=engine(model,session['start'],CASE_END,db,'combined')
        e.ph5_active_from=CASE_START
        timeline=[]
        exit_prefix=None
        for b in bars:
            if b['t']>decision:break
            if b['t']==ts(trade['entry_time']):
                parent_before_entry=copy.deepcopy(e.ph5.parent)
            e.minute(b)
            if b['t']==ts(trade['entry_time']):
                timeline.append(dict(time=iso(b['t']),kind='entry_consumption',
                    before=parent_before_entry,after=copy.deepcopy(e.ph5.parent),
                    fresh_from=iso(e.ph5.floor)))
            if b['t']==ts(trade['exit_time']):
                p=next(p for p in e.trades if p['entry_rule']=='PH5' and p['entry_time']==trade['entry_time'])
                expected=next(p for p in case['models'][model]['trades'] if p['entry_rule']=='PH5')
                actual_legs=[{k:v for k,v in leg.items() if k!='received_at'} for leg in expected['legs']]
                assert p['legs']==actual_legs
                exit_prefix=dict(last_input=iso(b['t']),known_no_earlier_than=iso(b['t']+60),
                    source_received_at=iso(receipt[b['t']]),legs=copy.deepcopy(p['legs']),
                    no_later_candles_used=True)
        assert e.last_t==decision
        minute=by_time[decision]
        actual_setup=e.ph5.ready(e.atr)
        assert actual_setup is None and e.position is None
        # Conditional context check only. Supply genuine earlier D/H references
        # to a fresh validator; never install it in e, call open_signal(), alter
        # the actual sequence, or invent a replacement trade/exit/P&L.
        retained=ParentFiveDetector()
        retained.parent=copy.deepcopy(trade['parent_five']['setup']['parent'])
        retained.highs=copy.deepcopy(e.ph5.highs)+[copy.deepcopy(trade['parent_five']['setup']['rebound'])]
        retained.lows=copy.deepcopy(e.ph5.lows)
        retained.now=e.ph5.now
        for observed in bars:
            if ts(trade['entry_time'])<observed['t']<=decision:retained.invalidate(observed)
        setup=retained.ready(e.atr)
        assert setup is not None and not retained.parent['broken']
        assert setup['hl']['price']==63735.105 and setup['known_at']==ts('2026-11-15T03:15:00-05:00')
        assert setup['hl']['bar_time']>=e.entry_history_start
        assert (setup['parent']['time'],setup['hl']['time']) not in e.ph5_emitted
        five=e.previous_five
        t1,t2=e.targets(max(five['high']+.01,minute['open']),dict(high=setup['rebound']['price']),decision,e.atr)
        conditional=five_signal(setup,five,minute,e.atr,t1)
        assert conditional['qualified_candidate']
        audits[model]=dict(entry_consumption=timeline,exit_prefix=exit_prefix,
            actual_at_0320=dict(parent=copy.deepcopy(e.ph5.parent),ready=actual_setup,
                confirmed_highs=copy.deepcopy(e.ph5.highs),confirmed_lows=copy.deepcopy(e.ph5.lows),
                previous_five=five,atr=e.atr,position=None,
                A_max_LL=max((len(s['lows']) for s in e.detector.a_scopes),default=0),
                ready_AB_routes=[r for r,_ in e.detector.setups()]),
            retained_context_check=dict(label='Conditional validation only; NOT an emitted signal, new policy, trade, fill or alternative P/L',
                parent_unbroken=True,setup=setup,hold=five,minute=minute,t1=t1,t2=t2,validation=conditional,
                new_HL_after_consumed_entry=True,distinct_unconsumed_episode=True,
                earliest_minute_availability=iso(decision+60),source_received_at=iso(receipt[decision])))
        db.close()
    first_hl_break=next(b for b in bars if ts(trade['entry_time'])<b['t']<decision and b['low']<trade['references']['l2']['price'])
    rows=[]
    for b in original['bars']:
        if ts('2026-11-14T23:45:00-05:00')<=b['t']<ts('2026-11-15T03:45:00-05:00'):
            row={k:copy.deepcopy(b[k]) for k in ('t','open','high','low','close','low_t','high_t','observed_minutes')}
            row.update(known_at=iso(b['t']+900),available_to_worker=iso(receipt[b['t']+900]),
                failed_rebound=copy.deepcopy(b.get('failed_rebound_state')),
                events=copy.deepcopy(b['events']))
            rows.append(row)
    selected_minutes=[dict(**by_time[t],received_at=iso(receipt[t]))
        for start,end in [('2026-11-15T00:44:00-05:00','2026-11-15T00:55:00-05:00'),
                          ('2026-11-15T03:15:00-05:00','2026-11-15T03:23:00-05:00')]
        for t in range(ts(start),ts(end),60)]
    check=audits['0.1']['retained_context_check']
    d=trade['references']['l1']['price'];l2=trade['references']['l2']['price']
    low=check['setup']['hl']['price']
    result=dict(study=study['study_id'],source_sha256=case['source_sha256'],models=audits,
        entry={k:trade[k] for k in ('entry','entry_time','initial_stop','stop','references','t1','legs','net','peak')},
        failed_rebound=trade['failed_rebound_history'],bars_15m=rows,minute_evidence=selected_minutes,
        entry_hl_first_break=first_hl_break,
        scale_comparison=dict(old_parent_D=d,original_entry_HL=l2,new_HL=low,
            new_HL_above_parent=low-d,new_HL_below_original_HL=l2-low,
            post_exit_downside_from_exit_to_new_low=trade['legs'][0]['price']-low,
            entry_to_new_low_gross_distance=trade['entry']-low),
        assumptions_changed=False,month_rerun=False,replacement_trade_simulated=False)
    for name,digest in hashes.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
    result['preservation']=verify_preserved(before)
    result['preservation']['additional_PH5_files_verified']=len(hashes)
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'AUDIT.json',result)
    write_report(result,original['trace'])
    print(json.dumps(dict(report=str(OUT/'AUDIT.html'),conditional_check=check['validation'],
        actual_parent=audits['0.1']['actual_at_0320']['parent'],preservation=result['preservation']),indent=2))


def write_report(r,trace):
    a=r['failed_rebound'][0];x=r['entry'];c=r['models']['0.1']['retained_context_check'];v=c['validation']
    lines=['# BTC PH5退出与再次入场逐根核对','',
        '区分局部反弹失败、大级别父波段存续与已成交入场机会的消耗。','',
        'Last Updated: 2026-11-15  ','Status: 单例分析；未调参数，未重跑整月，未改变原研究或live worker  ',
        'Audience: Trading Desk owner and maintainers','','## Overview','',
        '00:48符合现有局部失败反弹退出规则，但不代表$61,991父低点已失效。03:20未再入场的关键是23:47成交时清除了父波段背景，之后又要求重建完整D→反弹→HL。两者是不同层级、不同状态的问题。后续确实跌破原入场HL，故不能只因最终上涨就断言第一次退出只是误杀正常回踩。',
        '全部时间为纽约EST。价格来自原始已归档的一分钟观察；十五分钟和五分钟均为这些真实观察的聚合。分析只重放此单例前缀，没有创建替代交易、利润或新参数。','',
        '## 00:48退出如何形成','',
        '| 结构 | 发生时间及价格 | 完整15分钟结构确认时间 | 原worker收到确认所需观察 |', '| --- | --- | --- | --- |']
    available={ts(b['known_at']):b['available_to_worker'] for b in r['bars_15m']}
    for k,label in [('high','H'),('low','L'),('lower_high','LH')]:
        p=a[k];lines.append(f"| {label} | {clock(p['time'])} / ${p['price']:,.4f} | {clock(p['known_at'])} | {clock(available[p['known_at']])} |")
    lines += ['',
        '23:45–00:00的高点$65,132.251，随后00:00–00:15低点$64,716.855，再到00:15–00:30较低高点$65,001.735。00:30–00:45的右侧K线结束后，H-L-LH才全部确认，$64,716.855从模型时间00:45起成为独立退出参考；原worker在00:46:05才收到处理确认所需的下一分钟观察。该规则不要求先创新高到原父峰$65,553，也不要求先浮盈1R。',
        '00:47分钟最低$64,724.845，仍未穿过参考；00:48最低$64,707.8035，首次下穿$64,716.855，因此模型按参考价退出100%。00:48一分钟收盘$64,721.838又回到参考上方，但规则是盘中穿越触发，不等一分钟或十五分钟收盘。不是偷用00:45–01:00最后的大阴线。原始00:48分钟实际在00:49:10收到；参考价不是当时可保证的真实成交价。',
        f"实际模型毛额${x['legs'][0]['gross']:,.2f}，成本代理${x['legs'][0]['cost']:,.2f}，净额${x['net']:,.2f}。硬止损${x['initial_stop']:,.2f}未触发、未上移；第一25%目标${x['t1']:,.2f}未触及。最高浮盈只有${x['peak']-x['entry']:,.2f}，约0.103个价差风险R，尚未启动1R回吐退出。0.1/E1/E2均由同一个失败反弹退出首先触发。",'',
        '## 从入场到03:30的每根15分钟K线','',
        '下表高低收均为事后完整观察，不能提前用于当时决策。确认时间=该行区间结束；独立低点/高点通常还需右邻K线结束。AUDIT.json保留每根实际送达时间、事件和退出状态。','',
        '| 15分钟开始EST | 高 | 低 | 收 | 当时结构与后续确认 |', '| --- | ---: | ---: | ---: | --- |']
    notes={
        '23:45':'23:47买入；23:52局部H，至00:15确认。成交即清空PH5父背景。',
        '00:00':'00:08局部L；至00:30确认。它仍高于入场HL $64,620.60。',
        '00:15':'00:19 LH；至00:45确认。位于23:45大K区间内，本根结束尚无完整H-L-LH。',
        '00:30':'本根结束确认LH，00:45起启用$64,716.855破位退出参考。',
        '00:45':'00:48盘中破局部L退出；00:54进一步跌破原入场HL。完整大阴线当时尚未结束。',
        '01:00':'01:10低点$64,137.90；至01:30确认，被清空后的检测器当作新D。',
        '01:15':'反弹高$64,608.815在01:27；至01:45确认。',
        '01:30':'第二根完整15m守D；01:45才使该新D通过独立性要求。',
        '01:45':'局部降高，尚无新的合格HL。',
        '02:00':'低$64,200.10相对新D构成局部HL，至02:30确认。',
        '02:15':'本根结束才确认02:00的HL；下一根立即下破，未形成合格5m守稳突破。',
        '02:30':'跌破$64,137.90新D；更低的候选底尚未获右侧确认。',
        '02:45':'02:51低点$63,735.105；相对旧D为HL，相对新D是更低低点。至03:15确认。',
        '03:00':'右侧守住$63,735；03:15确认这个低点，但重建检测器只把它当新D，且仅1根post-D完整守稳。',
        '03:15':'03:15–03:20完成5m守稳，03:20破5m高。新D独立性仍未完成，且没有后续15m反弹峰→再HL。',
        '03:30':'03:30开盘才有2根完整15m守稳（本根结束有3根），但仍没有之后确认的反弹峰和新HL；不能倒填03:20入场。'}
    for b in r['bars_15m']:
        key=datetime.fromtimestamp(b['t'],NY).strftime('%H:%M')
        lines.append(f"| {clock(b['t'])} | {b['high']:,.3f} | {b['low']:,.3f} | {b['close']:,.3f} | {notes[key]} |")
    lines += ['', '## 这是正常回踩还是突破失败','',
        '在00:48当时，只能确认局部H-L-LH后的盘中破L。原入场HL $64,620.60及父D $61,991.33仍未跌破；不能声称整个父波段已失败。两根内部小K本身也不是全仓退出条件，真正触发的是之后的局部低点下穿。',
        f"后续00:54确实跌破原入场HL，02:51达到${r['scale_comparison']['new_HL']:,.3f}，比入场低${r['scale_comparison']['entry_to_new_low_gross_distance']:,.2f}，比退出参考再低${r['scale_comparison']['post_exit_downside_from_exit_to_new_low']:,.2f}。这说明有一段真实下跌，不能仅因04:12后来创新高就定性为不该退出。该后续信息只用于复核，不参与00:48决策。",
        '同时，整个观察区间都没有跌破大D，较大波段背景继续成立。局部退出和保留较大背景并不矛盾。','',
        '## 03:20为何没有重新入场','',
        '清除发生于23:47成交，不是00:48卖出。它消耗了已使用的入场机会，同时删除父D、父反弹峰和转折历史；只有00:00以后完整K线才能重新建构。父D不是被市场跌破，而是被程序清空。',
        '01:10的$64,137.90于是被当成新D，后来02:30跌破。02:51的$63,735.105在03:15确认后，又变成新D。到03:20，它只有一根已完成的post-D 15分钟守稳K线，且没有D之后确认的反弹峰再接HL，因此不是合格PH5 setup；五分钟价格突破不能覆盖这些前置条件。',
        '', '## 仅保留旧父背景的条件核对','',
        '以下是静态条件诊断：在一个未安装到回放引擎的新验证对象中放入真实、当时已知且仍未跌破的旧D/H，再核对新HL和实际五分钟K线。没有发出新信号、开仓、替代退出或计算替代利润。它用于定位丢失的状态，不是另一轮参数回测。','',
        '| 条件 | 03:20前已知的证据 | 结果 |', '| --- | --- | --- |',
        '| 旧父D仍有效 | $61,991.3285；观察中未跌破，21:30已通过独立性要求 | 通过 |',
        '| 已确认父反弹峰 | 22:03的$65,553.438，22:30确认 | 通过 |',
        '| 新15m HL相对旧D | 02:51的$63,735.105，03:15确认；发生于00:00消费边界之后，D/HL组合与旧买点不同 | 通过 |',
        '| 独立5m守稳 | 03:15–03:20，低$63,834.15 > 新HL；高$63,948.505 | 通过 |',
        f"| 盘中突破 | 03:20分钟高${c['minute']['high']:,.4f} > 前5m高+$0.01，即${v['trigger']:,.4f} | 通过 |",
        f"| 原追价、风险、已知目标空间 | 原15m ATR ${r['models']['0.1']['actual_at_0320']['atr']:,.4f}；相同价差缓冲及正净目标规则 | {'通过' if v['qualified_candidate'] else '不通过'} |",
        f"| 可观察时间 | 完整分钟不早于{clock(c['earliest_minute_availability'])}，原始观察收到{clock(c['source_received_at'])} | 非03:20瞬时可保证成交 |",'',
        '因此，保留未失效的父背景时，03:20的结构和共享风险检查会通过；现有实现没有保留它，这是漏掉再次评估的直接原因。注意，新HL低于先前入场HL，且03:20尚未突破较大反弹峰。这不是连续HL上升已被完整确认，也不是保证成功的买点。',
        '', '## 本次结论与未执行的下一步','',
        '本例更明确地暴露了背景状态与入场机会状态混在一起：防止重复使用同一买点，并不必然要求删除未失效的父波段。00:48退出则符合现有局部风险规则，尚无证据据此取消该退出或硬拿到之后新高。',
        '若继续研究，应先区分“已成交的D/HL入场机会不可复用”与“未破父D的背景可保留”，再独立检查新的HL是否足以支持重入。这里只提出待验证的状态区分，没有接入程序、改变参数或重新计算整月。',
        f"已核验原132个保护文件及额外{r['preservation']['additional_PH5_files_verified']}个PH5源码/研究文件保持不变；原worker PID {r['preservation']['pid']}、session {r['preservation']['session']}保持运行。"]
    text='\n'.join(lines)+'\n'
    (OUT/'AUDIT.md').write_text(text)
    (ROOT/'docs/investigations/2026-11-15_BTC_PH5_EXIT_REENTRY_AUDIT.md').write_text(text)
    # Native text/table rendering, no generated image or plotted placeholder.
    import re
    sections=[];table=False
    for line in lines:
        if line.startswith('|'):
            if re.match(r'^\|\s*---',line):continue
            if not table:sections.append('<div class="scroll"><table>');table=True
            cells=line.strip('|').split('|')
            sections.append('<tr>'+''.join('<td>'+escape(cell.strip())+'</td>' for cell in cells)+'</tr>')
        else:
            if table:sections.append('</table></div>');table=False
            if line.startswith('# '):sections.append('<h1>'+escape(line[2:])+'</h1>')
            elif line.startswith('## '):sections.append('<h2>'+escape(line[3:])+'</h2>')
            elif line:sections.append('<p>'+escape(line)+'</p>')
    if table:sections.append('</table></div>')
    (OUT/'AUDIT.html').write_text('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BTC PH5 exit and reentry audit</title><style>body{font:16px/1.7 system-ui;margin:2rem auto;padding:0 1rem;max-width:1200px;color:#162334}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;min-width:700px}td{border:1px solid #ccd4df;padding:8px;vertical-align:top}tr:first-child{font-weight:bold;background:#eef3fa}</style>'+''.join(sections))


if __name__=='__main__':main()
