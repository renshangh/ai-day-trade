"""Four saved E3 exits: causal support/recovery audit, never a strategy run."""
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trading_desk.btc_data import STORE, read, save, ts, iso
from trading_desk.btc_engine import aggregate
from trading_desk.btc_live import LIVE
from trading_desk.btc_parent_memory_view import PARENT_MEMORY_VIEW
from scripts.review_btc_e3_draft1 import clock
from scripts.retest_btc_parent_five import preservation, verify_preserved

PRIOR = ROOT / 'reports/btc_e3_draft1_2026_11_15'
OUT = ROOT / 'reports/btc_e3_support_recovery_2026_11_15'
LABELS = ['winner-33', 'winner-39', 'winner-40', 'Nov15-0144']


def observed_bars(rows, seconds, receipts=None):
    """Aggregate observed minutes only; partial groups remain explicitly partial."""
    groups = {}
    for row in rows:
        groups.setdefault(row['t'] // seconds * seconds, []).append(row)
    result = []
    for start, group in sorted(groups.items()):
        group = sorted(group, key=lambda b: b['t'])
        assert len({b['t'] for b in group}) == len(group)
        bar = aggregate(group, seconds)
        bar['end'] = start + seconds
        bar['complete'] = [b['t'] for b in group] == list(range(start, start + seconds, 60))
        bar['available_at'] = max(bar['end'], max(receipts[b['t']] for b in group)) if receipts else None
        result.append(bar)
    return result


def confirmed_pivots(bars):
    """Existing strict three-15m-bar convention; outside turns excluded."""
    pivots = []
    for left, middle, right in zip(bars, bars[1:], bars[2:]):
        if not all(b['complete'] for b in (left, middle, right)):
            continue
        if not (middle['t'] == left['t'] + 900 and right['t'] == middle['t'] + 900):
            continue
        low = middle['low'] < min(left['low'], right['low'])
        high = middle['high'] > max(left['high'], right['high'])
        if low == high:
            continue
        kind = 'low' if low else 'high'
        availability = [b['available_at'] for b in (left, middle, right)]
        pivots.append(dict(kind=kind, price=middle[kind], time=middle[kind + '_t'],
                           bar_time=middle['t'], known_at=right['end'],
                           available_at=max(availability) if all(availability) else None))
    return pivots


def snapshot(rows, trade, at, receipts=None):
    """No unfinished or not-yet-received minute can enter a decision snapshot."""
    known = [b for b in rows if b['t'] + 60 <= at and (not receipts or receipts[b['t']] <= at)]
    start = ts(trade['entry_time'])
    holding = [b for b in known if b['t'] > start]  # Entry minute's intraminute order is unknown.
    h = trade['references']['l2']['price']
    d = trade['references']['l1']['price']
    bars = observed_bars(known, 900, receipts)
    pivots = confirmed_pivots(bars)
    pivots = [p for p in pivots if p['known_at'] <= at and
              (p['available_at'] is None or p['available_at'] <= at)]
    return dict(at=at, latest_minute=known[-1]['t'] if known else None,
                last_complete_15m=next((b for b in reversed(bars) if b['complete']), None),
                local_HL_broken=any(b['low'] < h for b in holding),
                parent_D_broken=any(b['low'] <= d for b in holding),
                lowest_since_entry=min((b['low'] for b in holding), default=None),
                confirmed_post_entry_pivots=[p for p in pivots if p['time'] > start])


def first_close(bars, h, earliest, last=None):
    return next((b for b in bars if b['complete'] and b['end'] >= earliest and
                 (last is None or b['end'] <= last) and b['close'] >= h), None)


def describe_case(label, trade, previous, source, cutoff, receipts, ledger):
    start = ts(trade['entry_time'])
    end = ts(trade['exit_time']) if trade.get('status') == 'closed' else cutoff
    rows = [b for b in source if start // 900 * 900 - 900 <= b['t'] < min(end + 60, cutoff)]
    scan = [b for b in rows if start < b['t'] < end]
    h = trade['references']['l2']['price']; d = trade['references']['l1']['price']
    selected = previous['E3_selected']; signal = ts(selected['signal_at']); due = ts(selected['execution_at'])
    first_breach = next(b for b in scan if b['low'] < h)
    first_below_close = next(b for b in scan if b['close'] < h)
    five = observed_bars(rows, 300, receipts); fifteen = observed_bars(rows, 900, receipts)
    first_five = next(b for b in five if b['complete'] and b['t'] > start and b['close'] < h)
    first_fifteen = next(b for b in fifteen if b['complete'] and b['t'] > start and b['close'] < h)
    post = [b for b in scan if b['t'] >= due]
    recovery_minute = next(b for b in post if b['close'] >= h)
    recovery_five = first_close(five, h, due)
    recovery_fifteen = first_close(fifteen, h, due)
    # Include every observed minute through the first completed 15m reclaim,
    # then separately retain the full original holding-path minimum.
    before_first_recovery = [b for b in post if b['t'] < recovery_fifteen['end']]
    bottom = min(before_first_recovery, key=lambda b: b['low'])
    full_bottom = min(scan, key=lambda b: b['low'])
    parent_path = [b for b in source if ts(trade['references']['l1']['known_at']) <= b['t'] < end]
    parent_gaps = sum(max(0, (b['t'] - a['t']) // 60 - 1) for a,b in zip(parent_path, parent_path[1:]))
    pivots = confirmed_pivots(fifteen)
    # Existing presentation ISO timestamps round away receipt sub-seconds.
    # Retain original receipt floats for causality rather than excluding an
    # observation that arrived during the displayed confirmation second.
    signal_known = max(signal, max(receipts[b['t']] for b in rows
                                  if selected['A']['t'] <= b['t'] < signal)) if receipts else signal
    signal_snap = snapshot(rows, trade, signal_known, receipts)
    due_snap = snapshot(rows, trade, due, receipts)
    # Independently recalculate snapshots from an input prefix. These checks
    # forbid later bottoms/recoveries from entering the E3-time conclusions.
    for at, expected in [(signal_known, signal_snap), (due, due_snap)]:
        prefix = [b for b in rows if b['t'] + 60 <= at]
        assert snapshot(prefix, trade, at, receipts) == expected
    orig_cutoff = previous['baseline_same_cutoff_net']
    last_complete = signal_snap['last_complete_15m']
    base_latest = ledger.get(last_complete['t']) if last_complete else None
    failure_state = base_latest.get('failed_rebound_state') if base_latest else None
    result = dict(label=label, original_trade_id=trade['id'], entry_time=trade['entry_time'],
        entry=trade['entry'], local_HL=trade['references']['l2'], parent_D=trade['references']['l1'],
        initial_stop=trade['initial_stop'], original_rebound=trade['references']['h1'],
        first_breach_minute=first_breach, first_below_close_minute=first_below_close,
        first_five_below=first_five, first_fifteen_below=first_fifteen,
        E3=selected, snapshot_signal=signal_snap, snapshot_execution=due_snap,
        parent_distance_at_signal=selected['signal_reference']-d,
        parent_distance_in_E3_ATR=(selected['signal_reference']-d)/selected['ATR'],
        parent_age_hours_at_signal=(signal-ts(trade['references']['l1']['time']))/3600,
        parent_observed_minimum=min(b['low'] for b in parent_path), parent_path_missing_minutes=parent_gaps,
        parent_path_broken=any(b['low'] <= d for b in parent_path),
        original_failed_rebound_state_at_signal=failure_state,
        original_failed_rebound_history=trade.get('failed_rebound_history', []),
        original_stop_history=trade.get('stop_history', []),
        recovery_minute=recovery_minute, recovery_minute_known_at=recovery_minute['t']+60,
        recovery_minute_received=receipts[recovery_minute['t']] if receipts else None,
        recovery_five=recovery_five, recovery_fifteen=recovery_fifteen,
        bottom_before_first_15m_reclaim=bottom, full_holding_minimum=full_bottom,
        max_adverse_from_entry=trade['entry']-full_bottom['low'],
        low_above_parent=full_bottom['low']-d,
        low_parent_rebound_retrace=(trade['references']['h1']['price']-full_bottom['low']) /
                                  (trade['references']['h1']['price']-d),
        original_net_or_marked=orig_cutoff, original_is_marked=previous['baseline_marked_not_realized'],
        E3_net=previous['E3_net'], difference=previous['same_cutoff_delta'],
        original_legs=previous['baseline_legs'], cutoff=iso(cutoff),
        bars_5m=five, bars_15m=fifteen, pivots=pivots, prefix_verified=True,
        minute_detail=[dict(b,received=receipts[b['t']] if receipts else None) for b in rows
                       if first_breach['t'] <= b['t'] < recovery_fifteen['end']+900])
    assert not result['parent_path_broken']
    assert not result['parent_path_missing_minutes']
    assert result['snapshot_execution']['local_HL_broken']
    assert not result['snapshot_execution']['parent_D_broken']
    return result


def run():
    before = preservation(); OUT.mkdir(parents=True, exist_ok=True)
    folder, study = PARENT_MEMORY_VIEW.current()
    paths = [p for p in PRIOR.rglob('*') if p.is_file()]
    paths += [p for p in folder.rglob('*') if p.is_file()]
    paths += [folder.parent/'ACTIVE.json', ROOT/'trading_desk/btc_parent_memory.py',
              ROOT/'trading_desk/btc_parent_five.py', ROOT/'scripts/review_btc_e3_draft1.py']
    protected = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    save(OUT/'PRESERVED.json', dict(original=before, research_files=protected))
    previous = read(PRIOR/'RESULT.json')
    data = []; digest = hashlib.sha256()
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz', 'rb') as f:
        for line in f:
            digest.update(line);t,o,h,l,c,v,n,_=json.loads(line)
            data.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    assert digest.hexdigest() == previous['monthly_source_sha256'] == study['source_minute_sha256']
    monthly = read(folder/'0.1/retained_combined/result.json')
    with sqlite3.connect((folder/'0.1/retained_combined/ledger.sqlite').as_uri()+'?mode=ro', uri=True) as db:
        ledger = {t:json.loads(body) for t,body in db.execute('SELECT t,body FROM ledger')}
    cases=[]
    for i in [33,39,40]:
        trade=next(p for p in monthly['trades'] if p['id']==i)
        prev=next(p for p in previous['winners'] if p['trade_id']==i)
        cases.append(describe_case('winner-'+str(i),trade,prev,data,ts(trade['exit_time'])+60,None,ledger))
    case=read(folder/'CASE.json');retained=case['models']['0.1']['retained']
    trade=next(p for p in retained['trades'] if p['entry_time']==previous['example']['entry_time'])
    cutoff=ts(previous['example']['cutoff'])
    src=LIVE/'sessions'/case['source_session']/'observations.sqlite'
    with sqlite3.connect(src.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(cutoff,)).fetchall()
    assert hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest()==previous['case_source_sha256']
    rows=[json.loads(body) for body,_ in records];receipts={b['t']:r for b,(_,r) in zip(rows,records)}
    cases.append(describe_case('Nov15-0144',trade,previous['example'],rows,cutoff,receipts,
                              {b['t']:b for b in retained['bars']}))
    for path,h in protected.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==h,path
    result=dict(created_at=datetime.now(timezone.utc).isoformat(),analysis_only=True,
        new_rule=False,parameters_changed=False,monthly_rerun=False,trades_resimulated=False,
        new_entries=False,orders_enabled=False,prior_report=str(PRIOR/'REPORT.html'),
        monthly_source_sha256=digest.hexdigest(),case_source_sha256=previous['case_source_sha256'],
        pivot_convention='Existing strict adjacent complete 3x15m pivot; outside turns excluded. Descriptive, not a new trading rule.',
        cases=cases,preservation=verify_preserved(before),protected_research_files=len(protected))
    save(OUT/'AUDIT.json',result)
    write_report(result)
    print(json.dumps(dict(report=str(OUT/'AUDIT.html'),cases=[dict(label=c['label'],
        parent_distance_ATR=c['parent_distance_in_E3_ATR'],
        first_15m_reclaim=clock(c['recovery_fifteen']['end']),
        maximum_adverse=c['max_adverse_from_entry']) for c in cases],
        preservation=result['preservation']),indent=2))


def cash(v):
    return f'${v:,.2f}'


def when(t):
    return clock(t)


NARRATIVES = {
 'winner-33': [
  '15:24首次破局部HL；15:30确认15:15–15:30收$80,963.80，低于HL。15:40的E3确认不是单纯影线误判：当时已经持续走弱，但父D尚远，且新的入场后低点尚未完成确认。',
  'E3后仍先跌：15:45低$80,701.20，16:16又创新低$80,583.6565。16:15–16:30从该低点拉回、收$80,842.67，是下方拒绝继续下跌的观察，不能在16:16低点出现时预知这根的最终收盘；该严格15m低点至16:45才确认。',
  '17:00原失败反弹状态已形成H=$81,126→L=$80,583.6565→LH=$80,893.12，只有再破L才是原规则的卖点。后续并未跌破该L，反而向上越过LH。17:39得到第一根1m收回HL，17:40完整5m收回，17:45完整15m收回。这是后来出现的恢复证据，不属于15:40时已知的信息。',
  '因此这笔不是破HL后马上恢复的轻微回踩，而是局部结构失败、继续下探，再在仍完整的父波段内部修复；仅把未破父D当作“正常回踩”会掩盖这段真实风险。'],
 'winner-39': [
  '21:09首次破HL；21:15完整15m收$81,165.124，明显低于$81,352.15。E3确认时21:14的$81,103.405只能叫当时已见最低价，右侧15m尚未完成，不能先把它当成已确认底部。',
  '21:15–21:30没有再破$81,103.405，反弹高$81,407.80，最终收$81,350.78：虽接近HL，仍差约$1.37。21:21–21:22的1m先收回HL，但21:25–21:30又收回下方，所以第一次1m收复没有保证持续。',
  '21:30才确认21:14低点；21:35完整5m收$81,514.29，21:45完整15m收$81,586.39，并且21:30–21:45低$81,323.658高于21:14低点。逐步出现“低点不再破→收复→更高低点”的恢复证据，而非靠父D未破单独判断。',
  '这笔恢复最快，但在21:15 E3确认或21:16模拟卖出时，后面的守低、收复仍不可知。'],
 'winner-40': [
  '03:25首次跌破HL，03:45首次完整15m收在HL下方。08:35 E3距第一次分钟失守已超过5小时；期间06:15、07:00、07:15、07:45等15m区间虽有上影触及HL，却没有完整15m收复。因此E3识别的是旧失守区间内的新一段速度，并不是首次跌破。',
  '08:30时已经可知：08:11低$81,225.40（08:30确认）高于05:50区间底$81,208.488（06:15确认），但低于中间06:42低$81,366.7075（07:00确认）。所以相对区间底尚未破底、相对紧邻内部低点却是LL，不能笼统标为HL。07:41高$81,550.8375仅略高于07:11高$81,547.99，也不足以证明同级结构转强。08:35时08:11低点暂未被当轮急跌破掉，是可知的暂时守低；两处区间低点只差约$16.91，不能认定为强独立父HL。',
  '08:43第一根1m收回HL，08:45的5m与15m同时收$81,582.451。但08:45–09:00又收$81,494.273，09:31甚至跌至$81,176.754，破掉前述两个局部低点。故一次收复或短小HL并不足以保证安全。',
  '09:30–09:45相对前根形成大幅拉回的外包K线，收$81,527.976；09:45–10:00低$81,518.366守在原HL之上并收$82,035.668，随后反弹延续。右侧09:45K的最高价高于09:30K，因此按既有三根比较，09:30K只满足严格低点条件、不同时满足严格高点条件；09:31低点可于10:00确认，不能在09:31提前确认。这里没有制造新确认规则或新卖价。'],
 'Nov15-0144': [
  '02:36破HL，02:40确认5m收$64,037.0735，02:45的完整15m与第二根5m均收$63,864.13。E3确认输入实际于02:45:01收到；当时入场局部支撑失效、当前下行仍延续，尚无已确认新底或收复证据。',
  '02:51还会跌至$63,735.105，这不是02:45已知的支撑。02:45–03:00转绿并收$63,974.79，虽较前收改善，仍低于HL；03:00–03:15又收$63,857.20。因此此时只能说下跌有停顿，不能提前宣告恢复。',
  '03:15模型时间才确认02:51低点，实际完整输入03:15:04到齐；03:18回踩低$63,834.15高于$63,735.105，但需右侧完整K线至03:45才确认这个HL，输入03:45:10到齐。03:22首根1m收回原HL，03:25完整5m收回（输入03:25:05到齐），03:30完整15m收$64,469.47（输入03:30:13到齐），之后03:30–03:45整根最低$64,464.382也保持在原HL上方。输入到齐时间不等于已证明策略在同一秒处理或成交。',
  '父D=$61,991.3285始终未破，提供仍可修复的较大背景；这不等于01:44入场已经正确或02:45必须持有。其后恢复和05:15浮盈只能用于事后对照，不能倒推02:46应当知道会反弹。']}


def write_report(r):
    lines=['# E3局部HL失守与父波段支撑恢复对照','',
        '逐根复核#33、#39、#40及11月15日01:44案例，区分当时可知风险和后来恢复。','',
        'Last Updated: 2026-11-15  ','Status: 四例只读分析；不调参、不重跑、不推广  ',
        'Audience: Trading Desk owner and maintainers','','## Overview','',
        '四笔都真正失守了入场局部HL，但仍在原记录的父D上方。E3识别了局部失败，却把这种失败直接等同于整笔较大波段应终止。父D未破是背景存续的证据，不能单凭它保证反弹或把每次深跌归为正常回踩。四例均为后来恢复样本，没有新的真正失败对照组，因此本次不能证明一条能区分所有赢家与输家的退出规则。',
        '全部时间为纽约当地EDT/EST。1m时间为该分钟开始；收盘及完整结构只能在区间结束后知道。案例有实际收讯记录时另列可用时间，历史三赢家没有同期收讯记录。只读已归档真实分钟，保留原E3和原交易全部结果；没有运行新策略、改变盈亏、扩大观察截点或新增再入场。',
        '', '## 同一个15m时间框架内仍有不同波段层级','',
        '局部HL是原入场最近一次回踩低点，回答“这次突破的近处支撑还在吗”；父D是该笔入场原记录中更早、更大的反弹起点，回答“较大反弹背景是否仍完整”。两者都来自15m结构，但不能因为时间框架相同就认为属于同一个波段层级。本次不事后换父D，也不把后来的低点升级为父支撑。',
        '三笔10月交易共用10/15 09:55 EDT的父D $79,691.8665，10:15确认；E3时已过去约3–5天。11/15案例父D为11/14 20:45 EST的$61,991.3285，21:15确认。这个按原模型保留的D是结构参考，并非根据订单簿/成交量验证出的强支撑；老D很远，意味着更大的容忍亏损。',
        '', '| 案例 | 入场 | 局部HL及确认时间 | 原父D及确认时间 | E3收盘距父D / 事前ATR | 首次收回HL的完整15m结束 |',
        '| --- | --- | --- | --- | --- | --- |']
    for c in r['cases']:
        h=c['local_HL'];d=c['parent_D']
        lines.append(f"| {c['label']} | {when(c['entry_time'])} / {cash(c['entry'])} | {cash(h['price'])} / {when(h['known_at'])} | {cash(d['price'])} / {when(d['known_at'])} | {cash(c['parent_distance_at_signal'])} / {c['parent_distance_in_E3_ATR']:.2f}ATR | {when(c['recovery_fifteen']['end'])} / {cash(c['recovery_fifteen']['close'])} |")
    lines+=['','## E3当时可以知道什么','',
        '| 案例 | 首次破HL分钟 / 首次完整15m失守确认 | E3确认 / 模拟退出 | 当时原失败反弹参考 | 当时判断的边界 |',
        '| --- | --- | --- | --- | --- |']
    for c in r['cases']:
        state=c['original_failed_rebound_state_at_signal'] or {}; ref=state.get('reference')
        state_text='尚无完整H-L-LH破低参考' if not ref else json.dumps(ref,ensure_ascii=False)
        distinction='新低和收复尚未确认；父D仍完整'
        if c['label']=='winner-40':distinction='相对05:50区间底未破，但相对06:42内部低点为LL；旧HL已失守5小时'
        lines.append(f"| {c['label']} | {when(c['first_breach_minute']['t'])} / {when(c['first_fifteen_below']['end'])} | {when(c['E3']['signal_at'])} / {when(c['E3']['execution_at'])} | {state_text} | {distinction} |")
    lines+=['','## 恢复过程和原风险','',
        '| 案例 | E3后首次1m收回HL的可知时间 | 首次完整5m收回 | 模拟退出分钟起至首次15m收回前最低 | 原持仓全程最低 / 距父D | 原入场最大逆行 |',
        '| --- | --- | --- | --- | --- | --- |']
    for c in r['cases']:
        b=c['bottom_before_first_15m_reclaim'];f=c['full_holding_minimum']
        lines.append(f"| {c['label']} | {when(c['recovery_minute_known_at'])} / {cash(c['recovery_minute']['close'])} | {when(c['recovery_five']['end'])} / {cash(c['recovery_five']['close'])} | {when(b['t'])} / {cash(b['low'])} | {when(f['t'])} / {cash(f['low'])}；高于父D {cash(c['low_above_parent'])} | {cash(c['max_adverse_from_entry'])}/BTC |")
    for c in r['cases']:
        lines+=['',f"## {c['label']}逐步解释",'']
        for paragraph in NARRATIVES[c['label']]:lines += [paragraph,'']
        s=c['snapshot_signal']; known=s['confirmed_post_entry_pivots']
        lines += [f"E3信息截点 {when(s['at'])}；最后可见分钟开始 {when(s['latest_minute'])}。入场后已确认严格15m转折："+
                  ('；'.join(f"{p['kind']} {cash(p['price'])}，发生{when(p['time'])}、确认{when(p['known_at'])}" for p in known) or '无')+'。','',
                  f"原初始硬止损 {cash(c['initial_stop'])}；本次不改、不移。原固定持仓最大逆行 {cash(c['max_adverse_from_entry'])}/BTC，所以保留父背景并非无成本等待。",'']
        if c['label']=='winner-33':
            state=next(x for x in c['original_failed_rebound_history'] if x['effective_at']>=ts(c['E3']['signal_at']))
            lines += [f"原失败反弹参考生效 {when(state['effective_at'])}，破低线 {cash(state['price'])}；这是原规则本来就有的条件，本次没有新设。",'']
    lines+=['## 盈亏结果保持原样','',
        '沿用上一轮初始1 BTC、每边2bps的比较结果；没有新模拟卖价或按未来低点/恢复价改写任何利润。',
        '', '| 案例 | 原净额 | 原E3草案净额 | 差额 |', '| --- | ---: | ---: | ---: |']
    for c in r['cases']:
        lines.append(f"| {c['label']} | {cash(c['original_net_or_marked'])}"+('（历史浮盈，未实现）' if c['original_is_marked'] else '')+
                     f" | {cash(c['E3_net'])} | {cash(c['difference'])} |")
    lines+=['','01:44原仓截至11/15 05:16 EST仍未平，最后实际分钟参考05:15；不能把标记浮盈称为已实现利润。这四笔也不能用来估计全月表现或E3总体误伤率。',
        '', '## 哪些区别有依据 哪些仍不能判断','',
        '1. E3时即可分层：局部HL失守是真的；原父D未破也是真的。E3收盘距离父D仍有约6.8–10.1个当时ATR，说明局部破位离父结构失效很远，不说明这段距离可以放心承受。',
        '2. #40有当时已知的区别：不是首次失守，已有长时间震荡，区间底暂未破。不过08:11对05:50是较高，对紧邻06:42低点却是较低，不能随意选参考来称为HL。其余三笔在E3时也没有已确认恢复底；#40后来又破掉区间底，故不能直接把暂时守底升格成可靠过滤器。',
        '3. 后续才可确认恢复：跌后停止创新低、局部低点完整确认、完整K线收回HL，随后回踩保持更高低点。#39是较快修复；#33较慢；#40两次收复之间又失守；01:44则先停顿再形成较高低点。恢复不是一次触及原HL。',
        '4. 真正失败需要指出失败层级：新的完整H-L-LH后再破L，是局部反弹延续失败；原父D也被破，是较大背景失效。父D完整时局部策略仍可合理止损。把二者强行合并，会在更大的跌势里承受过深风险。',
        '5. 这四例缺少最终继续下跌的对照，不能证明任何新判别条件。若进一步研究，应在查看结局前固定要记录的父/局部层级和收复顺序，再用败例对照；本次没有定义新门槛、改变E3或重跑交易。',
        '', '## 数据与保留核验','',
        '所有OHLC来自原月度真实分钟及原live历史前缀；缺一分钟不会补。表内不完整边缘K线标明实际分钟数，不参与完整K线或转折确认。严格转折仅复用既有三根完整15m约定，不计同时符合严格高点和严格低点的双向外包转折；仅相对左侧外包不自动排除。父D确认至各笔原退出/历史截点间没有缺失分钟，也没有观测到跌破原父D。',
        '部分价格为quote-derived，分钟场内成交量很小或为零；无法判断是谁在买、真实买盘深度、资金吸筹或全市场量价确认。本报告说明图形结构如何修复，不能声称找到了真实资金流原因。',
        f"0.2及原worker相关{r['preservation']['files']}个保护文件和{r['protected_research_files']}个既有研究文件未变。原worker PID {r['preservation']['pid']}、session {r['preservation']['session']}保持运行。四笔E3时点均通过严格输入前缀核对。",'',
        '下方完整15m、5m与已确认转折表不省略K线。分钟表只展开从首次失守至首次15m收复后的一个完整15m区间，完整分钟来源仍由原归档和已有ACTUAL_INPUTS保留。表中恢复后的走势属于事后对照，不能用于提前决策。']
    md='\n'.join(lines)+'\n';(OUT/'AUDIT.md').write_text(md)
    (ROOT/'docs/investigations/2026-11-15_BTC_E3_SUPPORT_RECOVERY.md').write_text(md)
    html=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E3支撑层级与恢复逐根核对</title>',
          '<style>body{font:16px/1.65 system-ui;color:#17283b;max-width:1400px;margin:24px auto;padding:0 16px}.scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;min-width:1100px;width:100%;font-size:14px}td,th{border:1px solid #cbd5e1;padding:7px;text-align:left;vertical-align:top}th{background:#edf2f8}summary{cursor:pointer;font-weight:600}details{padding:14px 0;border-bottom:1px solid #cbd5e1}p{max-width:1150px}.warn{background:#fff1de}</style>']
    in_table=False
    for line in lines:
        if line.startswith('|'):
            if line.startswith('| ---'):continue
            tag='td' if in_table else 'th'
            if not in_table:html.append('<div class="scroll"><table>');in_table=True
            html.append('<tr>'+''.join(f'<{tag}>{escape(c.strip())}</{tag}>' for c in line.strip('|').split('|'))+'</tr>')
            continue
        if in_table:html.append('</table></div>');in_table=False
        if line.startswith('# '):html.append('<h1>'+escape(line[2:])+'</h1>')
        elif line.startswith('## '):html.append('<h2>'+escape(line[3:])+'</h2>')
        elif line:html.append('<p>'+escape(line)+'</p>')
    if in_table:html.append('</table></div>')
    exports=[]
    for c in r['cases']:
        h=c['local_HL']['price'];d=c['parent_D']['price']
        for key in ['bars_15m','bars_5m']:
            step=900 if key=='bars_15m' else 300
            html.append(f"<details><summary>{escape(c['label'])} 完整{step//60}分钟记录（含明确标出的边缘未完成K线）</summary><div class='scroll'><table><tr>"+
                ''.join(f'<th>{s}</th>' for s in ['区间开始','区间结束／结构可知','实际输入可用','开／高／低／收','实际分钟／应有分钟','局部HL状态','父D状态','本时刻新确认转折'])+'</tr>')
            for b in c[key]:
                ps=[p for p in c['pivots'] if p['known_at']==b['end']] if step==900 else []
                row=dict(case=c['label'],timeframe_minutes=step//60,start=iso(b['t']),end=iso(b['end']),
                    available_at=iso(b['available_at']) if b['available_at'] else '',complete=b['complete'],
                    observed_minutes=b['observed_minutes'],open=b['open'],high=b['high'],low=b['low'],close=b['close'],
                    local_HL=h,parent_D=d,close_below_local_HL=b['close']<h,parent_D_broken=b['low']<=d,
                    confirmed_pivots=json.dumps(ps,ensure_ascii=False))
                exports.append(row)
                cells=[when(b['t']),when(b['end']) if b['complete'] else '未完成，不用于确认',
                    when(b['available_at']) if b['available_at'] else '历史收讯不可核实',
                    ' / '.join(cash(b[k]) for k in ['open','high','low','close']),
                    f"{b['observed_minutes']}/{step//60}",'收下方' if b['close']<h else '收上方',
                    '破位' if b['low']<=d else '未破',
                    '；'.join(f"{p['kind']} {cash(p['price'])}，实际发生{when(p['time'])}" for p in ps) or '无']
                html.append('<tr'+(' class="warn"' if not b['complete'] else '')+'>'+''.join('<td>'+escape(str(s))+'</td>' for s in cells)+'</tr>')
            html.append('</table></div></details>')
        html.append(f"<details><summary>{escape(c['label'])} 首次失守至首次15m收复后的1m明细</summary><div class='scroll'><table><tr><th>分钟开始</th><th>分钟结束</th><th>实际输入收到</th><th>开／高／低／收</th></tr>")
        for b in c['minute_detail']:
            html.append('<tr>'+''.join('<td>'+escape(v)+'</td>' for v in [when(b['t']),when(b['t']+60),
                when(b['received']) if b.get('received') else '历史收讯不可核实',
                ' / '.join(cash(b[k]) for k in ['open','high','low','close'])])+'</tr>')
        html.append('</table></div></details>')
    html.append('</html>');(OUT/'AUDIT.html').write_text('\n'.join(html))
    with (OUT/'BAR_REVIEW.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(exports[0]));w.writeheader();w.writerows(exports)


if __name__=='__main__':
    run()
