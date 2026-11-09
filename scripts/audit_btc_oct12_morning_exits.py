"""Morning-only exit audit: preserve model, compare already-approved exits.

No run(), parameter search, fabricated candles, target changes or broker calls.
Later signals are conditional after an earlier full exit, never additive fills.
"""
import copy
import hashlib
import inspect
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from trading_desk.btc_data import STORE,ts,iso,save
from trading_desk.btc_engine import Replay,aggregate
from audit_btc_oct12_b_branches import FOLDER,load,local,BASELINE
from audit_btc_nov07_2145_timeline import confirmed_lows
from review_btc_nov06_07_swings import groups,complete,scan_exits

OUT=ROOT/'reports/btc_structure_2026_11_08/entry_examples/oct12_morning_exits'


def money_leg(entry,price,fraction):
    e,p,f=(Decimal(str(x)) for x in (entry,price,fraction))
    gross=f*(p-e);cost=f*(p+e)*Decimal('0.0002')
    return dict(fraction=fraction,price=price,gross=float(gross),cost=float(cost),net=float(gross-cost))


def review():
    source,minutes=load()
    original=json.loads((FOLDER/'B_BRANCH_REVIEW.json').read_text())
    case=original['cases'][0];trade=case['trade'];signal=case['signal']
    end=ts(trade['exit_time'])+60;entry_at=ts(trade['entry_time'])
    baseline=json.loads((STORE/'runs'/BASELINE/'result.json').read_text())
    hashes={n:hashlib.sha256(inspect.getsource(getattr(Replay,n)).encode()).hexdigest()
        for n in ('minute','complete','close_part','targets')}
    if hashes!=baseline['unchanged_exit_contract']:
        raise ValueError('Original protective/exit behavior changed')
    buckets=groups(minutes)
    by={t:aggregate(g,900) for t,g in buckets.items() if complete(g)}
    # Both anchors exist before entry. The B1 stored H1 is its local trigger
    # high; cross-check with the actual prior completed rebound, not a peak
    # selected later to improve the exit price.
    impulse=signal['setup_evidence']['impulse']
    dbar=signal['setup_evidence']['d']['time']//900*900
    rebound=max((b for t,b in by.items() if impulse['t']<t<dbar),key=lambda b:b['high'])
    prior_rebound=dict(price=rebound['high'],time=local(rebound['high_t']),
        bar=local(rebound['t']),known_at=local(rebound['t']+900))
    model=dict(entry=trade['entry'],entry_time=trade['entry_time'],source_end_exclusive=iso(end),
        references=copy.deepcopy(trade['references']),legs=[])
    local_review=scan_exits(model,minutes)
    model['references']['h1']['price']=rebound['high']
    wave_review=scan_exits(model,minutes)
    if [(e['type'],e['time'],e['price']) for e in local_review['events']] != [(e['type'],e['time'],e['price']) for e in wave_review['events']]:
        raise ValueError('Anchor choice affects signals; requires explicit scope review')

    first=wave_review['first_candidate'];events=wave_review['events']
    midpoint=next(e for e in events if e['type']=='next_bar_below_previous_new_high_midpoint')
    wick=next(e for e in events if e['type']=='last_minute_new_wave_high_upper_wick')
    later_mid=next(e for e in events if e['type']=='next_bar_below_previous_new_high_midpoint' and ts(e['time'])>ts(wick['time']))
    first_target=trade['legs'][0]
    first_path=money_leg(trade['entry'],first['price'],1.)
    conditional_wick=money_leg(trade['entry'],wick['price'],.75)
    conditional_mid=money_leg(trade['entry'],later_mid['price'],.75)

    lows15=confirmed_lows(minutes,900);lows60=confirmed_lows(minutes,3600)
    eligible15=[p for p in lows15 if entry_at<ts(p['low_time']) and ts(p['known_at'])<=ts(trade['exit_time'])]
    eligible60=[p for p in lows60 if entry_at<ts(p['low_time']) and ts(p['known_at'])<=ts(trade['exit_time'])]
    # The B2 entry reference has different confirmation requirements from
    # the parent's protective stop. Its later bounce does not exceed H=83,040.
    b2=next(s for s in case['later_structure_signals'] if s['route']=='B2')
    parent_peak=by[ts('2026-10-12T10:00:00-04:00')]
    after_hl=[b for b in minutes if ts(b2['references']['l2']['known_at'])<=b['t']<end]

    minute_by={b['t']:b for b in minutes}
    critical={clock:minute_by[ts('2026-10-12T'+clock+':00-04:00')]
        for clock in ('09:44','09:59','10:05','10:11','10:14','10:15','10:31','10:49')}
    period=ts(wick['reference_bar']);previous=by[period-900]
    watch=int(previous['close']//1000)*1000
    old_gate=dict(watch=watch,entry=trade['entry'],previous_close=previous['close'],
        open_observation=wick['price'],upper_wick_fraction=wick['upper_wick_fraction'],
        watch_above_entry=watch>trade['entry'],previous_close_above_watch=previous['close']>=watch,
        observation_below_watch=wick['price']<watch,
        new_high=wick['observed_high']>wick['peak_before'],shape_passed=wick['upper_wick_fraction']>=.5)
    period_rows=[];peak=rebound['high']
    for t in range(entry_at//900*900,end//900*900+1,900):
        bar=by.get(t)
        if not bar:continue
        new_high=bar['high']>peak
        first_break=next((b for b in buckets[t] if b['t']>=entry_at and b['high']>peak),None) if new_high else None
        period_rows.append(dict(**bar,start_ny=local(t),end_ny=local(t+900),
            completed_before_original_exit=t+900<=ts(trade['exit_time']),
            previous_wave_high=peak,new_wave_high=new_high,
            first_high_break=local(first_break['t']) if first_break else None,
            midpoint=(bar['high']+bar['low'])/2 if new_high else None,
            initial_stop=trade['initial_stop'],stop_raised=False))
        peak=max(peak,bar['high'])
    observed=[b for b in minutes if entry_at//900*900<=b['t']<end]
    if [b['t'] for b in observed]!=list(range(entry_at//900*900,end,60)):
        raise ValueError('Missing source minutes in holding interval; no interpolation')

    return dict(scope='Only October 12 09:33 B1 morning entry, no rerun or execution changes',
        source=source,original_case=copy.deepcopy(case),prior_rebound=prior_rebound,
        approved_exit_events=events,stored_local_anchor_events=local_review['events'],
        first_approved_exit=first,
        stop_audit=dict(initial_stop=trade['initial_stop'],automatic_breakeven_on_target=False,
            new_confirmed_15m_lows_before_exit=eligible15,new_confirmed_hour_lows_before_exit=eligible60,
            stop_history=trade.get('stop_history',[]),b2_reference=b2['references']['l2'],
            higher_wave_peak=parent_peak['high'],highest_after_b2_hl=max(b['high'] for b in after_hl),
            b2_candidate_stop=b2['initial_stop'],b2_stop_does_not_replace_held_b1=True),
        original_wick_gate=old_gate,critical_minutes=critical,chronological_bars=period_rows,
        paths=dict(original=dict(legs=trade['legs'],net=trade['net']),
            approved_earliest=dict(time=first['time'],legs=[first_path],net=first_path['net'],
                first_25_target_occurs=False),
            conditional_after_target_wick=dict(time=wick['time'],legs=[first_target,conditional_wick],
                net=first_target['net']+conditional_wick['net'],conditional_after_earlier_full_exit=True),
            conditional_later_midpoint=dict(time=later_mid['time'],legs=[first_target,conditional_mid],
                net=first_target['net']+conditional_mid['net'],conditional_after_earlier_full_exit=True)),
        method_sha256=hashes,month_rerun=False,orders=0,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def report(r):
    t=r['original_case']['trade'];s=r['stop_audit'];e=r['first_approved_exit'];w=r['original_wick_gate'];p=r['paths']
    out=['# BTC 10月12日早盘：止盈后的保护与更早退出审查','',
        '逐根区分同级低点上移、已批准的主动退出与旧网页引擎的实际行为。','',
        'Last Updated: 2026-11-08  ','Status: 单笔只读审查；不改参数，不重跑整月  ',
        'Audience: 交易学习手册使用者与研究维护者','',
        '## Overview','',
        '**原同级低点条件没有允许上移；但已批准的主动退出在10:05已触发，早于10:11首次目标。** 原−$104.11是旧网页退出实现的结果，不代表按最新手册也必然持有到10:49。',
        '以下均为2026年10月12日纽约EDT（UTC−4），每笔初始1 BTC，原每边2bps成本。没有真实订单，也不修改已保存的原案例。','',
        '## 为什么25%止盈后没有上移','',
        '- 25%目标本身不触发保本。原规则要求：新的同级低点已完成确认，且价格已突破该回踩之前的同级峰。',
        '- 原持仓期间没有入场后新形成、已确认的1小时波段低点；也没有入场后且在10:49之前确认的严格左右各一根15分钟波段低点。原D09:26发生于09:33入场之前，不能另当成新的保护锚点。',
        '- B2的10:18回踩参考82,711.40到10:30已知，但B2局部入场参考不等于已确认的同级保护D；其后反弹最高82,962.03，仍低于10:11峰83,040.768，未完成新的同级破峰。',
        f"- B2假设新交易的初始止损{s['b2_candidate_stop']:.6f}仍从原较大D计算；它既不是本笔B1的止损上移，也不允许覆盖原止损向下调整。原保护始终{t['initial_stop']:.6f}。",'',
        '## 逐根15分钟审查','',
        '| 完整区间 | O／H／L／C | 当时结构与退出判断 |',
        '| --- | --- | --- |']
    notes={
        '09:30':'09:33入场。最高未破入场前反弹峰82,886.91；没有新的同级D。',
        '09:45':'盘中过82,886.91形成波段新高；10:00收盘后，中点82,769.94775才可用于下一根。',
        '10:00':'10:00盘中也已超过前根高点；现规则未规定这会取消前根中点。10:05跌破中点，应退出100%。旧网页10:11才卖25%；10:14又有54.18%长上影。',
        '10:15':'开盘82,844.255已低于前根新高中点82,886.659；若还持有，触发退出余仓。10:18回踩只是候选，不能自动上移。',
        '10:30':'10:31只到82,962.03，未破83,040.768；之后下穿HL，不能当成新的父级转强。',
        '10:45':'旧网页10:49触发原止损。11:00收盘数据属于退出后观察，不用于事前决策。'}
    for b in r['chronological_bars']:
        out.append(f"| {b['start_ny'][11:16]}–{b['end_ny'][11:16]} | "+'／'.join(f"{b[k]:,.6f}" for k in ('open','high','low','close'))+f" | {notes[b['start_ny'][11:16]]} |")
    out+=['','## 主动退出的时序与价格','',
        f"1. **10:05–10:06，中点退出最早。** 09:45完整K线H82,946.42、L82,593.4755，中点{e['threshold']:.8f}，从10:00才生效。10:05分钟开盘82,823.02在中点上，最低82,732.55在中点下，模型按下穿中点价退出全部100%。确切秒数／可成交报价未知。此时尚未触及T1，因此这条路径不发生10:11的25%止盈。",
        '10:00这一根在盘中已超过前根高点，随后才发生10:05回落。现有中点条款没有“当前根创新高则取消前根中点”的豁免；本次保持原条款，不事后加豁免来保留后来更高的退出价。',
        f"2. **10:14–10:15，末分钟长上影。** 若条件性沿旧路径持有到10:11卖25%，则10:14只用前14根完整分钟及当前首价82,844.68，已知H83,040.768、L82,732.55，15分钟开盘82,873.79，上影／全振幅{w['upper_wick_fraction']:.8%}≥50%，且创新高。按已批准的无整数关口条款，应退出全部剩余75%。这是发生在更早整仓退出之后的条件案例。",
        '3. **10:15–10:16，下一根开盘已低于新高中点。** 前根中点82,886.659已知，当前开盘82,844.255已低于中点，模型使用开盘观察价，不能乐观地填更高中点价。此路径又晚于10:14，不能重复计收益。','',
        '## 为什么旧网页未执行','',
        f"- 旧引擎没有中点主动退出分支，因此10:05／10:15不检查。10:14虽然新高及上影形态通过，旧关口floor(前根收盘82,875.745／1000)×1000={w['watch']}；关口不高于入场价82,571.345，且当前观察价不低于关口，两个旧门槛均不通过。这些旧门槛早已被手册的新退出定义取消，但上一轮按用户要求保持了网页实现不变。",
        '- 本次识别的是实现与手册的版本差异，没有为使本笔盈利添加新参数、缩小止损或更换目标。','',
        '## 各路径分别记账，不能相加','',
        '| 路径 | 退出时点及仓位 | 净盈亏 USD／初始1 BTC |',
        '| --- | --- | ---: |',
        f"| 原网页 | 10:11卖25%；10:49原止损卖75% | {p['original']['net']:.6f} |",
        f"| 已批准条款，最早事件优先 | 10:05退出100%；没有25%目标腿 | {p['approved_earliest']['net']:.6f} |",
        f"| 条件对照：忽略10:05后继续持有 | 10:11卖25%；10:14长上影退出75% | {p['conditional_after_target_wick']['net']:.6f} |",
        f"| 更晚条件对照：再忽略10:14 | 10:11卖25%；10:15开盘退出75% | {p['conditional_later_midpoint']['net']:.6f} |",'',
        '原网页第一腿净+$106.174494、余75%净−$210.281763，合计−$104.107269。早期获利比例较小，不足以覆盖较大余仓的原风险。这不授权在首次止盈后自动保本。','',
        '## 来源、可知时间与未变范围','',
        f"复用两例审查的实际Alpaca分钟，SHA256 `{r['source']['sha256']}`；本次09:30–10:50区间逐分钟连续，无插值或缺失填补。关键分钟原始O/H/L/C在EXIT_REVIEW.json保留。",
        f"本笔记录的本地H1={r['original_case']['signal']['references']['h1']['price']}。另用入场前已完成的08:45反弹峰82,886.91交叉核对，同样得到10:05、10:14、10:15的候选时序；没有用后来的峰倒选参照。",
        '小时、15分钟严格转折都按右侧完整K线结束才可知；B2的已完成回踩参考不能与父级止损确认混用。10:45–11:00的收盘读数只作事后图表上下文。',
        '只审查早盘这一笔；原两例JSON、月度结果和latest_run指针均保留，不改变引擎或运行整月，也未提交任何订单。']
    return '\n'.join(out)+'\n'


if __name__=='__main__':
    watched=[STORE/'latest_run.json',STORE/'runs'/BASELINE/'result.json',FOLDER/'B_BRANCH_REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    result=review()
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=h for p,h in before.items()):
        raise ValueError('Existing result changed')
    OUT.mkdir(parents=True,exist_ok=True);save(OUT/'EXIT_REVIEW.json',result)
    (ROOT/'docs/investigations/2026-11-08_BTC_OCT12_MORNING_EXIT_REVIEW.md').write_text(report(result))
    print(json.dumps(dict(first=result['first_approved_exit'],stop=result['stop_audit'],
        paths={k:v['net'] for k,v in result['paths'].items()}),ensure_ascii=False))
