"""Single-case causal check of the newly approved B1 independent post-D hold."""
import hashlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import audit_btc_trade5_b1 as original_audit
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_shock_branches import independent_b1_setup

FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/trade5_independent_post_d_hold'


def review():
    source=original_audit.review()
    run=read(STORE/'runs'/original_audit.RUN/'result.json')
    old=next(p for p in run['trades'] if p['id']==5)
    signal=next(s for s in run['signals'] if s['id']==old['signal_id'])
    setup=signal['setup_evidence'];d=setup['d'];bars=source['bars_15m']
    start=d['known_at'];confirmation_end=start+900
    hold=next(b for b in bars if b['t']==start)
    dbar=next(b for b in bars if b['t']+900==start)
    entry_check=independent_b1_setup(setup,start,dbar)
    assert not entry_check['setup_passed'] and entry_check['trigger_reference'] is None
    history=[];d_intact=True;first_break=None
    for minute in source['minutes_1m']:
        if not start<=minute['t']<confirmation_end:continue
        known=[b for b in bars if b['t']+900<=minute['t']]
        reference=known[-1] if known else None
        check=independent_b1_setup(setup,minute['t'],reference,d_intact=d_intact)
        # No new entry is eligible before a separate candle finishes. Record
        # the breach only as observed within the minute, not at its opening.
        assert not check['setup_passed']
        breached=minute['low']<d['price']
        if breached and first_break is None:
            first_break=dict(interval_start=minute['time'],interval_end=minute['end'],
                known_by=minute['end'],open=minute['open'],low=minute['low'])
        history.append(dict(time=minute['time'],end=minute['end'],open=minute['open'],high=minute['high'],
            low=minute['low'],close=minute['close'],candidate_eligible_at_open=check['setup_passed'],
            d_intact_at_open=d_intact,breaches_d_in_interval=breached,
            state_at_interval_end='invalid_original_d_breached' if breached or not d_intact else 'waiting_for_complete_confirmation'))
        if breached:d_intact=False
    final=independent_b1_setup(setup,confirmation_end,hold,d_intact=d_intact)
    assert first_break and not final['setup_passed'] and final['trigger_reference'] is None
    assert hold['observed_minutes']==15 and hold['low']<d['price']
    return dict(source_run=original_audit.RUN,trade_id=5,date='2026-10-15',timezone='America/New_York',
        rule='B1_INDEPENDENT_POST_D_HOLD',rule_approved=True,monthly_default_changed=False,
        d=dict(**d,occurrence=iso(d['time']),known_at_utc=iso(d['known_at']),
            candle_start=iso(dbar['t']),candle_end=dbar['end']),
        original_entry=dict(time=old['entry_time'],price=old['entry'],initial_stop=old['initial_stop'],net=old['net']),
        confirmation=dict(time=hold['time'],end=hold['end'],open=hold['open'],high=hold['high'],
            low=hold['low'],close=hold['close'],observed_minutes=hold['observed_minutes'],
            completion_known_at=hold['end'],passed=False),
        old_entry_validation=entry_check,first_d_break=first_break,
        final_validation=final,minute_history=history,
        earliest_possible_entry_if_confirmation_passed=iso(confirmation_end),
        actual_entry_time=None,actual_entry_price=None,initial_stop_activated_at=None,
        candidate_trigger_active=False,modeled_trades=[],realized_net=None,
        outcome='not_traded_original_d_breached',original_entry_avoided=True,
        numerical_risk_parameters_changed=False,month_rerun=False,broker_orders=0,
        source_rows_sha256=source['source_rows_sha256'])


def report(r):
    d=r['d'];c=r['confirmation'];b=r['first_d_break'];clock=original_audit.clock
    lines=['# BTC #5：B1独立守D确认单笔核验','',
        'D所在K线之后再等独立完整15分钟守D，本例排除原入场。','',
        'Last Updated: 2026-11-09  ','Status: 已批准规则定义，#5单笔核验完成；月度默认及结果未切换  ',
        'Audience: 交易桌使用者及维护者','','## Overview','',
        '**可以避开原#5。新规则下09:45不买，09:53–09:54原D破位，10:00确认失败；本轮无入场、无持仓止损、无成交盈亏。**',
        '', '所有行情时间为2026年10月15日纽约时间EDT。当前文档更新日期为2026年11月9日。', '',
        '## 已明确的新B1顺序','',
        '1. 急跌D所在15分钟K线完整结束，D才成为本轮参考。',
        '2. 等D所在K线之后至少一根独立、完整、含15个真实分钟的K线，最低不跌破同一个D。',
        '3. 该确认K线完成后，才允许随后盘中突破前根完整K线最高价加原$0.01增量；仍保留原追价、目标、成本和止损参数。',
        '4. 等待中原D被实际观测跌破，本轮准备状态失效。不能把D向下移动后，仍称旧D守住。若要研究新的D，必须另起候选并重新等待，不能直接补一笔延迟买入。','',
        '## 本笔发生、确认与入场时间','',
        '| 时间 | 当时已知信息 | 新B1状态 |', '| --- | --- | --- |',
        f"| 09:30–09:45 | D所在K线；09:31低点{d['price']:,.3f} | 完成前不能用作已确认D |",
        f"| 09:45 | D所在K线完整结束，D={d['price']:,.3f}成为参考 | 开始等待09:45–10:00独立K线；禁止原09:45买入 |",
        f"| 09:45–09:46 | 价格曾越过原触发{r['original_entry']['price']:,.2f} | 独立守D确认未完成，不能买 |",
        f"| {clock(b['interval_start'])}–{clock(b['interval_end'])} | 本分钟最低{b['low']:,.3f}已跌破D | 原候选失效；这不是新模式的持仓止损 |",
        f"| 10:00 | 独立K线完整：最低{c['low']:,.4f}，低于D | 守D失败，无入场资格 |",
        '| 10:00之后 | 只有确认通过时，才可能开始等待盘中突破 | 本例没有通过，实际入场时间与价格均为空 |', '',
        '因此，“10:00”是这个D对应的**最早可能开始考虑入场的时间边界**，不是实际买入时间。旧09:30参考高点80,655.70也不能一直当成之后的前根高点；确认若通过，突破仍须引用当时最新的完整K线。本例没有生效的突破价。','',
        '## 独立确认K线的实际OHLC','',
        f"09:45–10:00：开{c['open']:,.4f}、高{c['high']:,.4f}、低{c['low']:,.4f}、收{c['close']:,.4f}，15/15分钟有实际观测。这些完整数值到10:00才全部知道。D在09:53–09:54已经被实际分钟跌破，无需假装等到10:00才发现破位。",'',
        '## 等待期间逐分钟状态','',
        '| 纽约分钟 | 开 | 高 | 低 | 收 | 当分钟开始可入场？ | 分钟结束后的状态 |',
        '| --- | ---: | ---: | ---: | ---: | --- | --- |']
    for row in r['minute_history']:
        status='原D已破，候选失效' if row['state_at_interval_end']=='invalid_original_d_breached' else '等待独立K线完成'
        lines.append(f"| {clock(row['time'])}–{clock(row['end'])} | {row['open']:,.3f} | {row['high']:,.3f} | {row['low']:,.3f} | {row['close']:,.3f} | 否 | {status} |")
    lines+=['','## 结果与边界','',
        f"旧记录原成交净亏{r['original_entry']['net']:,.2f}／每初始1 BTC仍保留。新规则本轮是**未交易**，盈亏留空，不虚构0美元交易或把旧损失直接加回月度收益。后续持仓占用及其他买点会受入场规则影响，未经整月重放不更新月度胜率或收益。",'',
        '只新增明确的独立确认校验并核对此案例；没有运行策略／整月回测、改变原风险数值参数、改写月度结果或工作簿，也没有订单。原B1审查保留为历史口径。', '',
        f"来源与上次只读审查相同，源105根分钟SHA256：`{r['source_rows_sha256']}`。原始分钟未补值，成交秒数／实际ETF成交未验证。"]
    return '\n'.join(lines)+'\n'


def main():
    files=[STORE/'latest_run.json']+list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    r=review();FOLDER.mkdir(parents=True,exist_ok=True);save(FOLDER/'REVIEW.json',r)
    (ROOT/'docs/investigations/2026-11-09_BTC_TRADE5_INDEPENDENT_D_HOLD.md').write_text(report(r))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
    print(dict(avoided=r['original_entry_avoided'],earliest_possible=r['earliest_possible_entry_if_confirmation_passed'],
        actual_entry=r['actual_entry_time'],first_d_break=r['first_d_break']['interval_start'],month_rerun=False))


if __name__=='__main__':main()
