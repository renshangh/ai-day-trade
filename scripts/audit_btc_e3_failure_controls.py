"""Saved losing PH5 trades versus recoveries; descriptive evidence, no replay."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import gzip
import hashlib
from html import escape
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_live import LIVE
from trading_desk.btc_parent_memory_view import PARENT_MEMORY_VIEW
from scripts.audit_btc_e3_support_recovery import observed_bars,confirmed_pivots,snapshot
from scripts.review_btc_e3_draft1 import clock
from scripts.retest_btc_parent_five import preservation,verify_preserved

OUT=ROOT/'reports/btc_e3_failure_controls_2026_11_15'
PRIOR=ROOT/'reports/btc_e3_support_recovery_2026_11_15'
LOSS_IDS=[22,111,75,2]


def measure(trade, source, cutoff, receipts=None):
    """Common observation checkpoints; absent recovery stays None, never filled."""
    start=ts(trade['entry_time'])
    final=ts(trade['exit_time']) if trade.get('status')=='closed' else cutoff
    rows=[b for b in source if start//900*900-900<=b['t']<min(final+60,cutoff)]
    held=[b for b in rows if start<b['t']<final]
    h=trade['references']['l2']['price'];d=trade['references']['l1']['price']
    five=observed_bars(rows,300,receipts);fifteen=observed_bars(rows,900,receipts)
    eligible=lambda b: b['complete'] and b['t']>=start and b['end']<=final
    below5=next((b for b in five if eligible(b) and b['close']<h),None)
    below15=next((b for b in fifteen if eligible(b) and b['close']<h),None)
    breach=next((b for b in held if b['low']<h),None)
    d_wick=next((b for b in held if b['low']<=d),None)
    d_close=next((b for b in held if b['close']<d),None)
    d_five=next((b for b in five if eligible(b) and b['close']<d),None)
    d_fifteen=next((b for b in fifteen if eligible(b) and b['close']<d),None)
    anchor=below15['end'] if below15 else None
    recoveries={}
    for seconds,bars in [(300,five),(900,fifteen)]:
        recoveries[str(seconds)]=next((b for b in bars if eligible(b) and anchor is not None
                                       and b['end']>anchor and b['close']>=h),None)
    # Earlier reclaims before the first failed 15m close remain visible in
    # the full trace, but are not confused with recovery after that failure.
    later_minute=next((b for b in held if anchor is not None and b['t']>=anchor and b['close']>=h),None)
    points={}
    for label,b in [('first_5m_failure',below5),('first_15m_failure',below15)]:
        if b is None:continue
        at=b['available_at'] if receipts else b['end']
        if at>final:  # A known-at-market-time bar can arrive after original exit.
            points[label]=dict(bar=b,unavailable_before_original_exit=True)
            continue
        full=snapshot(rows,trade,at,receipts)
        prefix=[row for row in rows if row['t']+60<=at]
        assert snapshot(prefix,trade,at,receipts)==full
        points[label]=dict(bar=b,snapshot=full,prefix_verified=True,
                           same_original_exit_minute=int(at//60)==int(final//60))
    reclaim=recoveries['900']
    failed_reclaim=next((b for b in fifteen if eligible(b) and reclaim is not None
                         and b['end']>reclaim['end'] and b['close']<h),None)
    maximum_below=0;run=0
    for b in fifteen:
        if not eligible(b):run=0;continue
        if b['close']<h:run+=1;maximum_below=max(maximum_below,run)
        else:run=0
    return dict(id=trade['id'],entry_time=trade['entry_time'],entry=trade['entry'],
        original_status=trade['status'],original_exit=trade.get('exit_time'),cutoff=iso(cutoff),
        original_net=trade.get('net'),original_marked_net=trade.get('marked_net'),
        original_legs=trade['legs'],initial_stop=trade['initial_stop'],
        local_HL=trade['references']['l2'],parent_D=trade['references']['l1'],
        parent_initial_risk_distance=trade['entry']-trade['initial_stop'],
        first_HL_breach=breach,first_5m_below_HL=below5,first_15m_below_HL=below15,
        parent_first_wick_before_exit=d_wick,parent_first_1m_close_before_exit=d_close,
        parent_first_5m_close_before_exit=d_five,parent_first_15m_close_before_exit=d_fifteen,
        first_1m_reclaim_after_15m_failure=later_minute,reclaims_after_15m_failure=recoveries,
        first_failed_15m_reclaim=failed_reclaim,maximum_consecutive_15m_closes_below_HL=maximum_below,
        checkpoints=points,original_failed_rebound_history=trade.get('failed_rebound_history',[]),
        pivots=confirmed_pivots(fifteen),bars_5m=five,bars_15m=fifteen,
        observed_minute_rows=rows,receipts={str(b['t']):receipts[b['t']] for b in rows} if receipts else None,
        pre_exit_observed_minimum=min((b['low'] for b in held),default=None),
        original_exit_minute=next((b for b in rows if b['t']==final),None),
        gap_exposed=trade['gap_exposed'],context_partial=trade['context_partial'])


def run():
    before=preservation();folder,study=PARENT_MEMORY_VIEW.current()
    protected_paths=[p for base in [PRIOR,ROOT/'reports/btc_e3_draft1_2026_11_15',folder]
                     for p in base.rglob('*') if p.is_file()]
    protected_paths += [folder.parent/'ACTIVE.json',ROOT/'trading_desk/btc_parent_memory.py',
                        ROOT/'trading_desk/btc_parent_five.py',ROOT/'scripts/review_btc_e3_draft1.py',
                        ROOT/'scripts/audit_btc_e3_support_recovery.py']
    protected={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected_paths}
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'PRESERVED.json',dict(original=before,research_files=protected))
    original=read(folder/'0.1/retained_combined/result.json')
    candidates=[p for p in original['trades'] if p.get('entry_rule')=='PH5' and p.get('net',0)<0
                and not p['gap_exposed'] and not p['context_partial']]
    ranked=sorted(candidates,key=lambda p:(p['net'],p['id']))
    assert [p['id'] for p in ranked[:4]]==LOSS_IDS
    definition=dict(source_study=study['study_id'],model='0.1 retained_combined',
        selection='Four largest original net losses among PH5 trades with neither gap_exposed nor context_partial; ties by id. Outcome-selected diagnostic controls, not a prospective trading filter.',
        eligible_count=len(candidates),loss_ids=LOSS_IDS,
        recovery_cases=['winner-33','winner-39','winner-40','Nov15-0144'],
        observation='Original entry through original exit minute, or original Nov15 05:16 EST cutoff. Exit-minute OHLC is separately labeled and never used to anticipate the exit.',
        checkpoint='First complete post-entry 5m close below original HL, and first complete 15m close below it. Market completion and actual receipt are separate.',
        parameters_changed=False,monthly_replay=False,new_exit_simulation=False,new_entries=False)
    if (OUT/'COHORT.json').exists():assert read(OUT/'COHORT.json')['definition']==definition
    else:save(OUT/'COHORT.json',dict(recorded_at=datetime.now(timezone.utc).isoformat(),definition=definition))
    archive=[];digest=hashlib.sha256()
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            digest.update(line);t,o,h,l,c,v,n,_=json.loads(line)
            archive.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    previous=read(PRIOR/'AUDIT.json')
    assert digest.hexdigest()==previous['monthly_source_sha256']==study['source_minute_sha256']
    cases=[]
    for ident in LOSS_IDS+[33,39,40]:
        trade=next(p for p in original['trades'] if p['id']==ident)
        row=measure(trade,archive,ts(trade['exit_time'])+60)
        row.update(label=('loss-' if ident in LOSS_IDS else 'recovery-')+str(ident),
                   cohort='loss' if ident in LOSS_IDS else 'recovery')
        cases.append(row)
    live_case=read(folder/'CASE.json');cutoff=ts(previous['cases'][-1]['cutoff'])
    trade=next(p for p in live_case['models']['0.1']['retained']['trades']
               if p['entry_time']=='2026-11-15T06:44:00Z')
    dbpath=LIVE/'sessions'/live_case['source_session']/'observations.sqlite'
    with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(cutoff,)).fetchall()
    assert hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest()==previous['case_source_sha256']
    minutes=[json.loads(body) for body,_ in records];receipts={b['t']:r for b,(_,r) in zip(minutes,records)}
    row=measure(trade,minutes,cutoff,receipts);row.update(label='Nov15-0144',cohort='recovery')
    cases.append(row)
    for path,h in protected.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
    result=dict(created_at=datetime.now(timezone.utc).isoformat(),definition=definition,cases=cases,
        monthly_source_sha256=digest.hexdigest(),case_source_sha256=previous['case_source_sha256'],
        preservation=verify_preserved(before),protected_research_files=len(protected),
        analysis_only=True,new_exit_prices=False,new_PnL=False,month_rerun=False,rules_changed=False)
    save(OUT/'AUDIT.json',result);write_report(result)
    print(json.dumps(dict(report=str(OUT/'AUDIT.html'),loss_ids=LOSS_IDS,eligible=len(candidates),
                         preservation=result['preservation']),indent=2))


def money(v):return '—' if v is None else f'${v:,.2f}'
def bar_at(b):return '无（观察期内）' if b is None else clock(b['end'])+' / '+money(b['close'])


NOTES={
 'loss-22':[
  '10/16 10:20入场$82,278.86，局部HL $81,585.60，父D $79,691.8665。11:05刺破HL；11:00–11:15的15m却收回$81,627.935，说明第一次刺破并未立即持续失守。11:15–11:30才首次完整15m收在HL下。',
  '11:35又出现完整5m收$81,604.255，高于HL，但11:45完整15m只收$81,567.317，仍在下方。之后反弹高11:47 $81,628.51、12:26 $81,581.455依次降低；前者略越过HL，后者已够不到HL。低点则从11:22 $81,362.10降到12:03 $81,141.50，不能只看某一次收复。',
  '原H-L-LH参考12:15生效，后于12:45更新低点参考为$81,141.50；13:06原规则退出参考$81,141.50，原净亏$1,170.04。父D全过程未破，证明“父D完整”不能阻止局部反弹失败。不得把12:03发生的新低当成12:03之前已确认的卖点。'],
 'loss-111':[
  '11/05 06:44入场$80,275.3155，HL $80,143.90，父D $75,576.58。07:01盘中破HL，但07:00–07:15仍收$80,159.04，暂时收回。07:15–07:30才收$79,991.546，确认15m失守。',
  '自07:30确认后，观察至09:15原退出，没有一根完整5m或15m收回HL。07:53低$79,453.3245要到08:15才确认；08:47反弹高$79,789.6245，要到09:15才确认，并且远低于原06:51峰$80,316.548，也远未收复原HL。',
  '09:00–09:15已经下探$79,275.135；直到09:15右侧完成，原H-L-LH才武装，原退出使用09:15实际分钟开盘$79,320.817，不能倒填为更高的$79,453.3245。净亏$986.42，父D仍未破。这个慢确认问题与是否最终破父D是两件事。'],
 'loss-75':[
  '10/29 18:36入场$78,963.375，HL $78,480.4025，父D $78,202.25。19:37首次盘中破HL，19:40首次5m收盘确认失守。19:42低$78,187.50刺穿父D，但该分钟收$78,235.682，收回D；不能称作持续收盘失守。',
  '19:30–19:45的15m最终收$78,207.86，比D仍高$5.61，但低于HL。19:45这一根刚确认，同一分钟又触及原硬止损$78,070.8019464，原净亏$923.98。19:45整分钟低$77,930.90只能在该分钟结束后知道，不可用于19:45之前的决定，也不能称为该最低价成交。',
  '这笔从首次破HL到止损只有8分钟，完整15m失守确认与原止损在同一分钟；历史收讯与秒内顺序没有记录。等待父D完整5m或15m收盘失守，可能慢于原硬止损，不能让结构确认取代已存在的保护。'],
 'loss-2':[
  '10/12 12:05入场$82,795.12，HL $82,556.911，父D $82,309.10。12:50盘中破HL，13:00确认12:45–13:00收$82,409.356；之后至原退出没有完整5m或15m收回HL。13:16反弹高$82,544.596已够不到HL，13:45才完成严格高点确认。',
  '13:38低$82,282.95刺穿父D，但该分钟收$82,360.05，立即收回。13:45–14:45的完整15m收盘仍均高于D，却一直低于HL；因此不是父D连续收盘破位，而是原HL下方、父D附近的弱反弹区间。',
  '14:48原止损参考$82,241.6447857触发，原净亏$586.48。完整的父D收盘失守证据在原退出前没有出现；退出分钟OHLC只能事后观察。父D影线破位又收回也不能证明较大波段安全。'],
 'recovery-33':[
  '对照#22：两笔都出现降高降低和仍完整的同一父D。#33后来也于17:00武装原H-L-LH，但之后没有再破$80,583.6565，反而向上越过LH，17:45完整15m收回HL；#22最终继续破掉已确认L。分歧是在后续新低是否延续、收复能否维持中出现，不能从第一次HL失守时提前知道。'],
 'recovery-39':[
  '对照#111：两笔第一次分钟破HL后的15m都曾暂时收回，故早期刺破/收回本身不能分开。#39在首次15m失守后，下一根守住低点，21:35完整5m收回、21:45完整15m收回；#111首次15m失守后至原退出始终没有完整5m收回。区别逐步可见，但#40证明不能把等待时长直接设成止损阈值。'],
 'recovery-40':[
  '对照所有败例的反证：03:45第一次15m失守，至08:45才第一次完整15m收回，期间连续20根15m收盘在HL下，远长于这些败例。08:45收回后09:00又失守，09:31再创新低；故“长时间未收复”“收回后又失守”“还在创新低”单独使用，都会切掉这笔原赢家。其后09:45再次收回，10:00下一根低点和收盘都在HL之上，才出现更持续修复。'],
 'Nov15-0144':[
  '对照#75：01:44案例的父D仍远且未破；02:51新底直到03:15确认，实际输入03:15:04到齐，03:30十五分钟收回HL、输入03:30:13到齐。#75则原HL与父D更近，跌破HL后8分钟即触发原硬止损。距离只能描述原风险结构，本次不新增ATR/时间门槛，也不据此承诺某笔应持有。']}


def write_report(r):
    cases=r['cases']; lines=['# E3恢复与突破失败样本逐根对照','',
      '用同一已归档PH5组合的四笔最大干净亏损，对照四笔先破HL后恢复的案例。','',
      'Last Updated: 2026-11-15  ','Status: 只读个案对照；未调参、未重跑、未模拟新退出  ',
      'Audience: Trading Desk owner and maintainers','','## Overview','',
      '父D未破、曾经收回HL、或者刺破父D后收回，都不能单独区分恢复与真正失败。#22和#111在父D完整时已发生局部反弹失败；#75和#2在原止损之前虽刺穿父D，却没有完整1m/5m/15m收盘持续失守父D的证据。原硬止损仍必须与结构确认分开。',
      '相对更有信息的是后续反弹能否完整收回原HL、是否守住已确认L，以及下一次回落是否再次破低。但#40长时间未收复、首次收复后再破低仍最终获利，不能把这些现象直接升级为新卖出规则。本次是病例对照，不是分类器验证。',
      '', '## 选择方式和观察边界','',
      f"同一0.1 retained_combined保存结果中，先取entry_rule=PH5、原净亏、gap_exposed=false且context_partial=false的{r['definition']['eligible_count']}笔，按原净亏从大到小取前四笔：#22、#111、#75、#2。没有按是否符合E3或是否破父D再挑样本，也没有剔除不支持结论的样本。选择利用了最终盈亏，只用于事后诊断，不能称为前瞻过滤器。",
      '全部价格来自原归档分钟；时间为纽约EDT/EST。每笔只看原入场至原退出，另把原退出分钟OHLC独立标出；01:44仍截止原11/15 05:16。所谓“失败”指该笔原仓最终亏损，不声称退出后再无反弹。没有新卖价、新盈亏、反事实重入或整月重跑。',
      '为公平对照，八笔统一以“首次完整5m收盘低于原HL”和“首次完整15m收盘低于原HL”作为观察截点，不拿赢家后来恢复的底点作为当时已知。未完成K线、退出分钟最终高低价和未到达的输入均不提前使用。',
      '', '| 案例 | 原入场 / 价格 | 局部HL / 原父D | 原退出 / 原因 | 原净额 |',
      '| --- | --- | --- | --- | ---: |']
    for c in cases:
        legs=c['original_legs'];exit_=(clock(c['original_exit'])+' / '+legs[-1]['reason']) if legs else '历史截点仍未平'
        pnl=money(c['original_net'] if c['original_status']=='closed' else c['original_marked_net'])
        if c['original_status']!='closed':pnl+='（历史浮盈）'
        lines.append(f"| {c['label']} | {clock(c['entry_time'])} / {money(c['entry'])} | {money(c['local_HL']['price'])} / {money(c['parent_D']['price'])} | {exit_} | {pnl} |")
    lines+=['','## 在相同失守截点能看到什么','',
      '| 案例 | 首次破HL分钟 | 首次完整5m失守确认 | 首次完整15m失守确认 | 首次5m确认时父D是否已破 |',
      '| --- | --- | --- | --- | --- |']
    for c in cases:
        point=c['checkpoints'].get('first_5m_failure',{});snap=point.get('snapshot')
        state=('已盘中破' if snap['parent_D_broken'] else '尚未破') if snap else '无可用观察'
        suffix='（同原退出分钟）' if c['checkpoints'].get('first_15m_failure',{}).get('same_original_exit_minute') else ''
        lines.append(f"| {c['label']} | {clock(c['first_HL_breach']['t']) if c['first_HL_breach'] else '无'} | {bar_at(c['first_5m_below_HL'])} | {bar_at(c['first_15m_below_HL'])}{suffix} | {state} |")
    lines+=['','八笔在首次完整5m失守时，原父D均尚未观测到被破；因此这个早期二元条件在本组不能区分输赢。完整K线的已知时间是区间结束；11/15另有原始收讯延迟，表中区间完成不能当作实际worker处理或成交时间。',
      '', '## 失守后的收复过程','',
      '下表从首次完整15m失守之后开始比较，较早的影线/分钟收回仍保留在完整逐根表。最长连续根数只是描述，不是新阈值。',
      '', '| 案例 | 后续首次完整5m收回HL | 后续首次完整15m收回HL | 首次15m收回后再失守 | 最长连续15m收在HL下 |',
      '| --- | --- | --- | --- | ---: |']
    for c in cases:
        lines.append(f"| {c['label']} | {bar_at(c['reclaims_after_15m_failure']['300'])} | {bar_at(c['reclaims_after_15m_failure']['900'])} | {bar_at(c['first_failed_15m_reclaim'])} | {c['maximum_consecutive_15m_closes_below_HL']} |")
    lines+=['','## 父D影线与收盘必须分开','',
      '| 案例 | 原退出前首次刺破父D分钟 / 当分钟低与收 | 原退出前首个1m收在D下 | 首个完整5m / 15m收在D下 |',
      '| --- | --- | --- | --- |']
    for c in cases:
        wick=c['parent_first_wick_before_exit'];close=c['parent_first_1m_close_before_exit']
        w='无' if not wick else clock(wick['t'])+' / 低'+money(wick['low'])+' / 收'+money(wick['close'])
        cl='无' if not close else clock(close['t']+60)+' / '+money(close['close'])
        lines.append(f"| {c['label']} | {w} | {cl} | {bar_at(c['parent_first_5m_close_before_exit'])} / {bar_at(c['parent_first_15m_close_before_exit'])} |")
    for c in cases:
        lines+=['',f"## {c['label']}逐根解释",'']
        for paragraph in NOTES[c['label']]:lines += [paragraph,'']
        for name,p in c['checkpoints'].items():
            snap=p.get('snapshot')
            if not snap:continue
            desc='；'.join(f"{x['kind']} {money(x['price'])}，发生{clock(x['time'])}、确认{clock(x['known_at'])}" for x in snap['confirmed_post_entry_pivots']) or '无'
            lines += [f"{name}截点 {clock(snap['at'])}，已确认入场后严格15m转折：{desc}。",'']
    lines+=['## 有哪些可知区别 还有哪些不能判定','',
      '1. 父D完整不等于局部交易可继续。#22、#111是直接反例；同样父D完整的#33、#39后来恢复。父D只限定失效的波段层级，不能单独做退出开关。',
      '2. 一次收复也不够。#22完整5m曾收回，但完整15m始终未收回；#39随后5m、15m逐步收回并维持。#40第一次15m收回后仍再次失守、创新低，故一次收复失败也不是必然结束。',
      '3. 已确认低点的后续表现更接近真正分歧。#22和#111最终延续破低，原失败反弹规则退出；#33虽出现相似H-L-LH，后续没有再破当时的L。这个区别要等价格实际延续或收复才知道，不能在HL首次失守时提前标签化。',
      '4. 不收复的持续时间单独不可靠。#40有20根连续15m收在HL下仍最终盈利；它比本组选定败例等待更久。以这些亏损退出前的短时间去倒定时限，会误伤已知赢家。',
      '5. 父D要“等完整收盘”可能太慢。#75与#2直到原退出前都没有父D下方的完整1m、5m或15m收盘证据，但原硬止损随后仍被触发。不得因缺乏结构确认而取消已有止损，亦不得用退出分钟的完整OHLC提前证明当时能卖。',
      '这组对照支持继续研究“波段身份固定、收复后能否维持、已确认L是否再破”的完整顺序；尚不支持一个新卖点或保证不误伤的分界。本次没有给这些现象拟合分数、时间/ATR阈值或新退出规则。',
      '', '## 数据与保留','',
      '原始分钟没有填补或插值。边缘不完整K线明确标记；严格转折复用既有相邻三根完整15m约定。历史月度没有同期收讯和秒内顺序，11/15只列可核实输入到齐时间。quote-derived价格及稀疏场内量不能证明谁在吸筹、真实深度或可保证成交价。',
      f"原{r['preservation']['files']}个保护文件与{r['protected_research_files']}个既有研究文件核验未变。原worker PID {r['preservation']['pid']}、session {r['preservation']['session']}继续运行。原E3定义和上一轮盈亏不变；本次没有新E3模拟、月度重跑、订单或参数变更。",'']
    md='\n'.join(lines)+'\n';(OUT/'AUDIT.md').write_text(md)
    (ROOT/'docs/investigations/2026-11-15_BTC_E3_FAILURE_CONTROLS.md').write_text(md)
    html=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E3恢复与失败样本逐根对照</title>',
      '<style>body{font:16px/1.65 system-ui;color:#17283b;max-width:1440px;margin:24px auto;padding:0 16px}.scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;min-width:1100px;width:100%;font-size:14px}td,th{border:1px solid #cbd5e1;padding:7px;vertical-align:top;text-align:left}th{background:#edf2f8}summary{cursor:pointer;font-weight:600}details{padding:14px 0;border-bottom:1px solid #cbd5e1}p{max-width:1160px}.partial{background:#fff1de}</style>']
    table=False
    for line in lines:
        if line.startswith('|'):
            if line.startswith('| ---'):continue
            tag='td' if table else 'th'
            if not table:html.append('<div class="scroll"><table>');table=True
            html.append('<tr>'+''.join(f'<{tag}>{escape(x.strip())}</{tag}>'for x in line.strip('|').split('|'))+'</tr>');continue
        if table:html.append('</table></div>');table=False
        if line.startswith('# '):html.append('<h1>'+escape(line[2:])+'</h1>')
        elif line.startswith('## '):html.append('<h2>'+escape(line[3:])+'</h2>')
        elif line:html.append('<p>'+escape(line)+'</p>')
    if table:html.append('</table></div>')
    export=[]
    for c in cases:
        h=c['local_HL']['price'];d=c['parent_D']['price']
        for key,seconds in [('bars_15m',900),('bars_5m',300)]:
            html.append(f"<details><summary>{escape(c['label'])} 全部{seconds//60}分钟K线</summary><div class='scroll'><table><tr>"+''.join('<th>'+x+'</th>'for x in ['区间开始','结束／完整性','实际输入到齐','开／高／低／收','局部HL','父D影线／收盘','新确认转折'])+'</tr>')
            for b in c[key]:
                ps=[p for p in c['pivots'] if p['known_at']==b['end']] if seconds==900 else []
                same_exit=bool(c['original_exit'] and b['end']==ts(c['original_exit']))
                desc='；'.join(f"{p['kind']} {money(p['price'])}，发生{clock(p['time'])}"for p in ps) or '无'
                end=clock(b['end']) if b['complete'] else f"未完成 {b['observed_minutes']}/{seconds//60}分钟"
                if same_exit:end+='（同原退出分钟，先后未证实）'
                cells=[clock(b['t']),end,clock(b['available_at'])if b['available_at']else'历史收讯不可核实',
                   ' / '.join(money(b[k])for k in ['open','high','low','close']),
                   '收下方'if b['close']<h else'收上方',
                   ('刺破'if b['low']<=d else'未破')+' / '+('收下方'if b['close']<d else'收上方'),desc]
                html.append('<tr'+(' class="partial"'if not b['complete']else'')+'>'+''.join('<td>'+escape(x)+'</td>'for x in cells)+'</tr>')
                export.append(dict(case=c['label'],cohort=c['cohort'],minutes=seconds//60,start=iso(b['t']),end=iso(b['end']),
                  complete=b['complete'],observed_minutes=b['observed_minutes'],same_exit_minute=same_exit,
                  available_at=iso(b['available_at'])if b['available_at']else'',
                  open=b['open'],high=b['high'],low=b['low'],close=b['close'],HL=h,D=d,
                  HL_close_below=b['close']<h,D_wick_below=b['low']<=d,D_close_below=b['close']<d,
                  confirmed_pivots=json.dumps(ps,ensure_ascii=False)))
            html.append('</table></div></details>')
        html.append(f"<details><summary>{escape(c['label'])} 全部原持仓1分钟观察及退出分钟</summary><div class='scroll'><table><tr><th>分钟开始</th><th>OHLC仅在分钟结束后已知</th><th>开／高／低／收</th><th>实际收到</th><th>说明</th></tr>")
        for b in c['observed_minute_rows']:
            is_exit=c['original_exit'] and b['t']==ts(c['original_exit'])
            note='原退出分钟；OHLC不是退出前已知，也不是新成交价'if is_exit else('入场前/入场分钟背景'if b['t']<=ts(c['entry_time'])else'原持仓路径')
            receipt=c['receipts'].get(str(b['t']))if c['receipts']else None
            cells=[clock(b['t']),clock(b['t']+60),' / '.join(money(b[k])for k in ['open','high','low','close']),clock(receipt)if receipt else'历史收讯不可核实',note]
            html.append('<tr>'+''.join('<td>'+escape(x)+'</td>'for x in cells)+'</tr>')
        html.append('</table></div></details>')
    (OUT/'AUDIT.html').write_text('\n'.join(html+['</html>']))
    with (OUT/'BAR_REVIEW.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(export)


if __name__=='__main__':run()
