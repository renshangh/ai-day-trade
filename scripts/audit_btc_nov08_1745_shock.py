"""Nominated Nov 8 chart case: research-only shock route, no monthly replay."""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import ts,normalize
from trading_desk.btc_engine import aggregate
from scripts.btc_structure_retest import reward_risk

FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/nov08_1745'
RAW_SHA='50232b0e395f56e243ba4784164c731560df0cfccd74c38cc4a9c3ab8fbff74f'
SCREEN_SHA='421a1f1ceea1bad9cbd9a5ebca014cefcb1076fed46d2c7f040fdf6dafa619b6'
NY=ZoneInfo('America/New_York')


def local(t):return datetime.fromtimestamp(t,NY).isoformat()
def at(s):return ts('2026-11-08T'+s+':00-05:00')


def load(folder=FOLDER):
    raw=(folder/'ALPACA_RAW.json').read_bytes();screen=(folder/'UNCHANGED_TARGET_SCREEN.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=RAW_SHA or hashlib.sha256(screen).hexdigest()!=SCREEN_SHA:
        raise ValueError('Frozen source or target-state evidence changed')
    meta=json.loads((folder/'SOURCE.json').read_text());start=ts(meta['params']['start']);end=ts(meta['params']['end'])
    data=json.loads(raw);rows=normalize(data['bars']['BTC/USD'],start,end)
    minutes=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in rows]
    if [b['t'] for b in minutes]!=list(range(start,end,60)):
        raise ValueError('Missing real minute observations; never fill')
    # Alpaca may return an inclusive end observation. Only fully observed
    # half-open 15m windows are strategy inputs, never the 18:30 boundary bar.
    bars=[]
    for i in range(0,len(minutes),15):
        group=minutes[i:i+15]
        if len(group)!=15 or group[0]['t']%900:raise ValueError('Partial 15m context')
        bars.append(aggregate(group,900))
    return meta,minutes,bars,json.loads(screen)


def review(folder=FOLDER,shock_atr_multiple=2.0):
    meta,minutes,bars,screen=load(folder);by={b['t']:b for b in bars};trs=[];atr={};true_range={}
    for a,b in zip(bars,bars[1:]):
        if len(trs)>=14:atr[b['t']]=sum(trs[-14:])/14
        value=max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close']))
        true_range[b['t']]=value;trs.append(value)
    entry_period=at('17:45')
    shocks=[]
    for b in bars:
        if b['t']>=entry_period or b['t'] not in atr:continue
        previous=[x['low'] for x in bars if x['t']<b['t']]
        previous_close=by[b['t']-900]['close']
        down=max(b['open'],previous_close)-b['low']
        if (b['close']<b['open'] and down>=shock_atr_multiple*atr[b['t']]
                and b['low']<min(previous)):
            shocks.append(b)
    if not shocks:raise ValueError('No known shock candidate under the declared draft rule')
    shock=shocks[-1]
    bounce=next(b for b in bars if shock['t']<b['t'] and b['t']+900<=entry_period
        and b['close']>b['open'] and b['low']>shock['low'])
    pullback=[b for b in bars if bounce['t']+900<=b['t']<entry_period]
    l2=min(pullback,key=lambda b:b['low']);prior=by[entry_period-900];trigger=prior['high']+.01
    hit=next((b for b in minutes if entry_period<=b['t']<entry_period+900 and b['high']>trigger),None)
    if hit is None:raise ValueError('No breakout in the nominated bar')
    known_path=[b for b in minutes if shock['t']+900<=b['t']<hit['t']]
    hl=(l2['low']>shock['low']+.1*atr[entry_period] and all(b['low']>shock['low'] for b in known_path))
    l2_held=all(b['low']>=l2['low'] for b in minutes if entry_period<=b['t']<hit['t'])
    price=max(trigger,hit['open']);chase=price<=trigger+.1*atr[entry_period]
    stop=shock['low']-.25*atr[entry_period]
    if abs(stop-screen['stop'])>1e-8 or abs(price-screen['entry'])>1e-8:
        raise ValueError('The source-only case no longer reproduces the frozen target screen')
    t1=screen['target1'];ratio=reward_risk(price,stop,t1,2)
    before_hit=[b for b in minutes if bounce['t']+900<=b['t']<hit['t']]
    already_reclaimed=any(b['high']>bounce['high'] for b in before_hit)
    later=next((b for b in minutes if b['t']>=hit['t'] and b['high']>bounce['high']),None)
    nearest_target=bounce['high']-.1*atr[entry_period]
    return dict(scope='Only Nov 8 08:00 through completed 18:15 bar; candidate rule revision after observing this case, not out-of-sample validation',
        source=meta['source'],source_sha256=RAW_SHA,source_count=len(minutes),
        source_end_exclusive=meta['params']['end'],source_last_minute=local(minutes[-1]['t']),
        timeframe='15Min',alternate_timeframes_run=False,monthly_replay_run=False,orders_submitted=False,
        proposed_routes=dict(gradual_decline='Keep four independent LL phases separated by LH; child rebounds do not reset the whole-cycle count.',
            shock_rebound='Separate draft route: completed bearish new-low impulse with max(open, previous close)-low >= 2 pre-impulse ATR14, completed bullish rebound, pullback holds above impulse D, intrabar break of previous completed 15m high.',
            status='Research draft; explicit new route, not a reduction from four to three and not yet applied to the frozen engine.',
            draft_shock_atr_multiple=shock_atr_multiple,threshold_search_performed=False,
            shared='Previous-D protection, 0.25 ATR buffer, no chase beyond 0.10 ATR, target/cost/net-2R checks and exits remain separate.'),
        day_decline_reference=[dict(time=local(at(clock)),low=by[at(clock)]['low']) for clock in ('09:00','12:30','16:45')],
        internal_higher_low=dict(time=local(at('14:00')),low=by[at('14:00')]['low'],prior_low=by[at('12:30')]['low']),
        shock=dict(start=local(shock['t']),end=local(shock['t']+900),open=shock['open'],high=shock['high'],low=shock['low'],close=shock['close'],
            low_minute=local(shock['low_t']),atr_before=atr[shock['t']],true_range=true_range[shock['t']],atr_multiple=true_range[shock['t']]/atr[shock['t']]),
        rebound=dict(start=local(bounce['t']),known_at=local(bounce['t']+900),high=bounce['high'],low=bounce['low'],close=bounce['close']),
        higher_low=dict(start=local(l2['t']),known_low_at=local(l2['t']+900),low=l2['low'],higher_than_shock_d=hl),
        signal=dict(bar_start=local(entry_period),bar_end=local(entry_period+900),reference_previous_high=prior['high'],trigger=trigger,
            minute_start=local(hit['t']),minute_end=local(hit['t']+60),price_reference=price,
            l2_held_before_trigger=l2_held,chase_cap_passed=chase,exact_second_verified=False,
            price_reference_not_actual_fill=True,quote_reference_minute=hit['volume']==0,
            intrabar_signal=True,final_15m_close=by[entry_period]['close'],close_still_above_trigger=by[entry_period]['close']>trigger),
        initial_stop=dict(d=shock['low'],atr_before_entry=atr[entry_period],buffer_multiple=.25,price=stop),
        larger_structure=dict(rebound_high=bounce['high'],reclaimed_before_signal=already_reclaimed,
            later_reclaim_minute=local(later['t']) if later else None,later_information_not_used_for_entry=True),
        target_screen=dict(target1=t1,target2=screen['target2'],net_reward_risk=ratio,net_2r_passed=ratio is not None and ratio>=2,
            unchanged_target_state=screen,nearest_rebound_resistance=bounce['high'],before_nearest_target=nearest_target,
            net_rr_to_nearest=reward_risk(price,stop,nearest_target,2)),
        signal_passed_under_proposed_route=bool(hl and l2_held and chase),qualified_order=False,
        qualification_reason='Local signal and draft shock route pass; unchanged larger-D protection and original target yield only 1.6323 net R, below 2. No order or eligible-strategy P/L is asserted.')


def report_text(r):
    s=r['shock'];b=r['rebound'];l=r['higher_low'];e=r['signal'];p=r['initial_stop'];q=r['target_screen']
    return '\n'.join(['# BTC 11/8 17:45：急跌反弹与四低点规则的分支修订','',
        '核对08:00后的15分钟走势，区分局部触发、急跌研究入口及完整买入资格。','',
        'Last Updated: 2026-11-08  ','Status: 单例研究草案；未推广执行引擎，未重跑整月  ',
        'Audience: 交易学习手册使用者与研究维护者','', '## Overview','',
        '**确认17:45–18:00这根存在局部入场触发，首次在17:58–17:59，参考74,429.2125。** '
        '但它不是“已经满足所有买单条件”的结论。原较大D止损、目标及成本下仅约1.6323净R，未过原2R。','',
        '全部纽约时间EST（UTC−5），15分钟时间为K线起点。用户指出16:15后的下跌，'
        '本次Alpaca和Coinbase交叉核对，最大急跌K线均是**16:45–17:00**。'
        '两种来源价格分别保存；下表仅用Alpaca，不把Coinbase高点拼进Alpaca信号。','',
        '## 从08:00看完整结构','',
        '08:15高点后，主要逐次降低的低点可标在09:00（75,769.51）、12:30（75,561.4305）、'
        '16:45（73,530.0885）。14:00回踩75,728.5535高于12:30低点，是内部HL，不能硬凑第四个LL。'
        '16:30与16:45是同一段尚未反弹的连续下探，不能分算两次独立波段低点。','',
        '## 四低点规则的调整草案','',
        '- **缓跌分支A：** 保留至少4个独立LL、其间有LH；计数属于同级完整下降setup，内部反弹不清零。',
        '- **急跌反弹分支B：** 不以凑满4个LL为前提，另识别已完成异常大阴线、已完成反弹、回踩不破急跌D及局部突破。'
            '向下急跌幅度＝max(本根开盘、前根收盘)−本根最低，暂要求≥2×下跌前ATR14，且阴线并创setup新低。借用手册既有异常大K线尺度作为新分支待测参数；没有做阈值搜索，不能说已验证有效。',
        '- 两分支保留相同的风险／成本、较大D保护、追价限制和退出要求；不是把4改3，也不将大阴线本身当买点。'
            '同一信号如果同时符合两分支，后续研究须去重，不能重复算收益。','',
        '本例急跌TR1,973.9765，事前ATR90.6142857，约**21.78倍ATR**。'
        '这项急跌标签只用16:45开始前的ATR，未用急跌后被放大的ATR来反选类别。','',
        '## 单例确认表','',
        '| 阶段 | 纽约时间 | Alpaca实际／模型数据 | 当时判断 |',
        '| --- | --- | --- | --- |',
        '| 急跌D | 16:45–17:00 | O75,500；L73,530.0885；C74,051.849，最低在16:55分钟 | 完成急跌后才能得到该D |',
        '| 首次反弹 | 17:00–17:15 | H74,660.945；L73,939.98；C74,428.627 | 17:15已有完整反弹证据 |',
        '| 回踩L2 | 17:30–17:45 | L74,090.65；H74,429.2025 | 17:45前已知，未破较大D |',
        '| 局部触发 | **17:58–17:59**，属于17:45这根 | 前根H＋0.01＝**74,429.2125**；当前分钟H74,447.5425 | 盘中触发成立，不等本根收盘 |',
        '| 本根完成后复核 | 18:00 | 17:45这根C74,386.017，低于触发线 | 不能事后写成收盘站稳，但不撤销已经发生的盘中触发 |',
        '| 较大一级转强 | 18:00–18:01 | 价格才越过首轮反弹峰74,660.945 | 这是较晚证据，不偷用来确认17:58入场 |',
        '| 原初始保护 | 假设触发后立即 | D73,530.0885−0.25×入场前ATR300.7776071＝**73,454.8940982** | 保留较大D，不为凑2R临时换成较浅L2 |',
        '| 原目标筛选 | 17:45前已知状态 | T1 **76,097.9977214**；净收益／风险 **1.6323215R** | 原净2R未通过，故没有合格买单 |','',
        '若只看到最近首轮反弹峰74,660.945，其前方目标扣原缓冲约74,630.8672，净收益／风险更只有0.1712R。'
        '因此本例证明“急跌后可能产生较早局部触发”，不能用18:00之后的上涨倒推17:58一定值得买。','',
        '## 来源与复现','',
        '- [Alpaca原始响应](../../reports/btc_structure_2026_11_08/entry_examples/nov08_1745/ALPACA_RAW.json)及来源SHA256：`'+RAW_SHA+'`。',
        '- 仅纳入08:00–18:30（不含）的630根完整分钟记录，无缺失；接口边界18:30记录不进入策略。',
        '- Coinbase15分钟原始响应与来源另存同目录，只交叉核对时间，不拼接价格。',
        '- [单例审查JSON](../../reports/btc_structure_2026_11_08/entry_examples/nov08_1745/SHOCK_REVIEW.json)。',
        '- 原目标用9天真实行情做单点只读重建，禁用入场；375根重叠分钟与冻结缓存完全一致。不是整月回测。',
        '- 当前只是新分支的单例研究。没有修改旧引擎、共享行情缓存、原月度表，也没有paper或真实订单。',''])


if __name__=='__main__':
    r=review();(FOLDER/'SHOCK_REVIEW.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    (ROOT/'docs/investigations/2026-11-08_BTC_1745_SHOCK_ENTRY_REVIEW.md').write_text(report_text(r))
    print(json.dumps({k:r[k] for k in ('signal','initial_stop','qualified_order')},ensure_ascii=False))
