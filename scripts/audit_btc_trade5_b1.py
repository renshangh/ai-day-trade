"""Read-only bar-by-bar explanation of trade #5; no strategy replay or tuning."""
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
from trading_desk.btc_shock_branches import expanded_shock_setup
from trading_desk.btc_entry_rules import entry_signal

RUN='20261109T041525Z-30-ab'
FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/trade5_b1_bar_audit'
NY=ZoneInfo('America/New_York')


def clock(value):return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(NY).strftime('%H:%M')


def review():
    original=read(STORE/'runs'/RUN/'result.json')
    p=next(p for p in original['trades'] if p['id']==5)
    s=next(s for s in original['signals'] if s['id']==p['signal_id']);w=s['setup_evidence']
    start=ts('2026-10-15T08:15:00-04:00');end=ts('2026-10-15T10:00:00-04:00')
    with sqlite3.connect((STORE/'minutes.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        minutes=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n)
            for t,o,h,l,c,v,n in db.execute('SELECT t,o,h,l,c,v,n FROM minutes WHERE t>=? AND t<? ORDER BY t',(start,end))]
        atr_start=ts('2026-10-15T04:45:00-04:00');atr_end=ts(p['entry_time'])
        atr_minutes=[dict(t=t,open=o,high=h,low=l,close=c,volume=v)
            for t,o,h,l,c,v in db.execute('SELECT t,o,h,l,c,v FROM minutes WHERE t>=? AND t<? ORDER BY t',(atr_start,atr_end))]
    assert [b['t'] for b in minutes]==list(range(start,end,60))
    indexed={b['t']:b for b in minutes}
    assert [b['t'] for b in atr_minutes]==list(range(atr_start,atr_end,60))
    atr_bars=[aggregate([b for b in atr_minutes if t<=b['t']<t+900],900) for t in range(atr_start,atr_end,900)]
    def atr_at(known_at):
        prior=[b for b in atr_bars if b['t']+900<=known_at][-15:]
        assert len(prior)==15 and all(b['observed_minutes']==15 for b in prior)
        return sum(max(b['high']-b['low'],abs(b['high']-a['close']),abs(b['low']-a['close']))
            for a,b in zip(prior,prior[1:]))/14
    verified_impulse_atr=atr_at(w['impulse']['t']);verified_entry_atr=atr_at(ts(p['entry_time']))
    assert abs(verified_impulse_atr-w['atr_before_impulse'])<1e-8
    assert abs(verified_entry_atr-s['atr'])<1e-8
    bars=[aggregate([b for b in minutes if t<=b['t']<t+900],900) for t in range(start,end,900)]
    entry=ts(p['entry_time']);exit_at=ts(p['exit_time'])
    prev=next(b for b in bars if b['t']+900==entry)
    state=expanded_shock_setup(w,entry,'B1')
    validated=entry_signal(state,dict(previous_bar=prev,minute=indexed[entry],
        atr_before_entry=s['atr'],atr_known_at=entry,hl_unbroken_before_trigger=True,
        target=dict(price=p['t1'],known_at=entry)))
    assert validated['qualified_candidate'] and validated['entry_reference']==p['entry']
    assert validated['initial_stop']==p['initial_stop']
    b2=expanded_shock_setup(w,entry,'B2')
    assert not b2['setup_passed'] and s['references']['l2'] is None
    notes={
        '08:30':'首次达到急跌标准；完整阴线至08:45才确认。',
        '08:45':'继续创低，D延伸至80446.642；尚未止跌。',
        '09:00':'再创低80277.80；小幅拉回仍未形成15分钟HL。',
        '09:15':'再创低80136.2672，收盘贴近低点。',
        '09:30':'本根自己创低80003.855后收成长阳；09:45完整后同时成为新D与B1参考。',
        '09:45':'买入后所在的大阴线；10:00的完整形状属于事后信息，09:55最低也在退出之后。',
    }
    fifteen=[]
    for b in bars:
        key=clock(iso(b['t']))
        fifteen.append(dict(**b,time=iso(b['t']),end=iso(b['t']+900),close_known_at=iso(b['t']+900),
            known_complete_at_entry=b['t']+900<=entry,role=notes.get(key,'急跌前的对照K线。')))
    turns=[]
    for left,middle,right in zip(minutes,minutes[1:],minutes[2:]):
        low=middle['low']<min(left['low'],right['low']);high=middle['high']>max(left['high'],right['high'])
        if low==high:continue
        kind='low' if low else 'high'
        turns.append(dict(kind=kind,time=iso(middle['t']),price=middle[kind],known_at=iso(right['t']+60),
            known_at_entry=right['t']+60<=entry))
    labels={
        '09:30':'旧15分钟D被下破，原准备状态失效；本根新D尚未完整确认。',
        '09:31':'实际低点80003.855；作为本根15分钟D要到09:45完整后才可引用。',
        '09:33':'1分钟局部反弹高点80392.2205；右邻完成后09:35可确认。',
        '09:36':'1分钟较高低点80039.90；右邻完成后09:38可确认，仍在同一根15分钟K线内。',
        '09:39':'突破1分钟局部高点并继续反弹；新15分钟D尚未完成，不能回填更早B1成交。',
        '09:41':'第二个1分钟较高低点80483.355，09:43可确认；不等同于独立15分钟HL。',
        '09:43':'本根15分钟最高80655.70发生；整根最高价至09:45才最终确定。',
        '09:44':'本分钟收盘80625.008至09:45才知道；09:44的1分钟低点要到09:46才有右邻确认。',
        '09:45':'本分钟高80682.245越过触发80655.71，条件入场；收80508.782跌回突破下方，须到09:46才知道。',
        '09:46':'开80496.2255，低于前分钟低点；整分钟最高也未收复突破线。',
        '09:47':'短暂反弹后形成1分钟低点，不能据此认定15分钟止跌。',
        '09:48':'短反弹最高80420.80，仍低于突破；该分钟收盘仅当09:49才完整可知。',
        '09:49':'反弹再次回落；初始止损和D均未被触及。',
        '09:50':'跌破前一个1分钟低点；这不是已采用的15分钟退出触发。',
        '09:51':'继续接近D，但仍未触及本笔止损。',
        '09:52':'最低80004.995，仍比D高1.14；不能提前记止损。',
        '09:53':'本分钟最低79821.987，首次穿D和79925.0756止损；模型在止损参考价退出100%。',
        '09:55':'整根15分钟的最终最低79691.8665出现在退出后，仅作行情对照。',
        '09:59':'整根15分钟收盘80096.98要到10:00才知道；不能用它撤销09:53已触发的止损。',
    }
    one=[]
    for b in minutes:
        one.append(dict(**b,time=iso(b['t']),end=iso(b['t']+60),close_known_at=iso(b['t']+60),
            known_complete_at_entry=b['t']+60<=entry,
            phase='入场前' if b['t']<entry else '入场分钟' if b['t']==entry else '持有／退出分钟' if b['t']<=exit_at else '退出后对照',
            role=labels.get(clock(iso(b['t'])),'本分钟无独立关键事件；保留实际OHLC，不省略。')))
    risk=p['entry']-p['initial_stop'];d=w['d']['price']
    summary=dict(entry_interval=[p['entry_time'],p['entry_interval_end']],entry=p['entry'],d=d,
        d_occurrence=iso(w['d']['time']),d_known_at=iso(w['d']['known_at']),initial_stop=p['initial_stop'],
        initial_stop_effective=p['entry_time'],stop_interval=[p['exit_time'],iso(exit_at+60)],
        price_risk=risk,cost=sum(l['cost'] for l in p['legs']),net=p['net'],
        observed_interval_start_difference_minutes=(exit_at-entry)//60,
        impulse_atr_multiple=(max(w['impulse']['open'],w['previous_close'])-w['impulse']['low'])/w['atr_before_impulse'],
        stabilization_close_location=(prev['close']-prev['low'])/(prev['high']-prev['low']),
        rebound_from_d_to_entry=p['entry']-d,stop_buffer=d-p['initial_stop'],
        buffer_share_of_price_risk=(d-p['initial_stop'])/risk,
        entry_minute_high=indexed[entry]['high'],entry_minute_close=indexed[entry]['close'],
        entry_minute_high_above_entry=indexed[entry]['high']-p['entry'],
        confirmed_post_entry_peak=max(b['high'] for b in minutes if entry<b['t']<exit_at),
        earliest_completed_false_break_evidence=iso(entry+60),
        b1_passed=validated['qualified_candidate'],b2_passed=b2['setup_passed'],
        fifteen_minute_hl_present=False,minute_pivots_present=True)
    payload=json.dumps(minutes,separators=(',',':')).encode()
    return dict(source_run=RUN,trade_id=5,date='2026-10-15',timezone='America/New_York',
        source='Alpaca BTC/USD archived observed 1m; no ticks or actual ETF fills',
        source_rows_sha256=hashlib.sha256(payload).hexdigest(),source_minutes=len(minutes),
        missing_minutes=0,zero_volume_minutes=sum(b['volume']==0 for b in minutes),
        independent_atr=dict(impulse_before=verified_impulse_atr,entry_before=verified_entry_atr,
            actual_source_minutes=len(atr_minutes),start=iso(atr_start),end_exclusive=iso(atr_end)),
        summary=summary,formal_b1=state,formal_entry=validated,formal_b2=b2,
        bars_15m=fifteen,minutes_1m=one,minute_turns=turns,
        parameters_changed=False,month_rerun=False,broker_orders=0,
        conclusion='按现有B1机械条件成立；属于首次止跌尝试突破，不是15分钟HL或底部确认。1分钟已有微型HL，突破本身很快失败。')


def report(r):
    s=r['summary'];lines=['# BTC 交易5：B1急跌反弹逐根审查','',
        '仅用真实15分钟和1分钟行情区分机械入场通过、止跌尝试与反转确认。','',
        'Last Updated: 2026-11-08  ','Status: 只读审查；参数和月度结果未改  ',
        'Audience: 交易桌使用者及维护者','','## Overview','',
        r['conclusion'],'',
        '全部时间为2026年10月15日纽约时间EDT。1分钟标签表示该分钟区间起点；09:45和09:53之间差8分钟，精确成交秒未知，不能声称恰好持有480秒。','',
        f"固定原记录：入场09:45–09:46，参考{s['entry']:,.4f}；D={s['d']:,.4f}（09:31发生、09:45才作为完整15分钟参考生效）；初始止损{s['initial_stop']:,.4f}，假设成交后立即保护。09:53–09:54止损100%，毛−{s['price_risk']:,.4f}、成本{s['cost']:,.4f}、净{s['net']:,.4f}／每初始1 BTC。",'',
        '## 15分钟：急跌、止跌尝试、触发与失败','',
        '| 区间 | 开 | 高 | 低 | 收 | 收盘／全形态何时可知 | 含义 |',
        '| --- | ---: | ---: | ---: | ---: | --- | --- |']
    for b in r['bars_15m']:
        lines.append(f"| {clock(b['time'])}–{clock(b['end'])} | {b['open']:,.2f} | {b['high']:,.2f} | {b['low']:,.2f} | {b['close']:,.2f} | {clock(b['close_known_at'])} | {b['role']} |")
    lines+=['','## 为什么程序允许09:45买入','',
        f"08:30急跌的向下幅度=max(开盘80,962.3375、前收80,969.955)−80,483.9755=485.9795，为事前ATR14的{s['impulse_atr_multiple']:.4f}倍，超过原2倍阈值。随后四次向下延伸D都等各自15分钟完整后才引用。",'',
        f"另用04:45–09:45的300根完整真实分钟独立核验：急跌前ATR14={r['independent_atr']['impulse_before']:.6f}，入场前ATR14={r['independent_atr']['entry_before']:.6f}，与归档一致；止损=D−0.25×入场前ATR，不含09:45之后行情。",'',
        f"09:30–09:45阳线自身创低后收在全振幅的{s['stabilization_close_location']:.2%}位置，是明显的单根拉回。当前B1只要求完整K线收盘高于其低点、低点不低于当时D（允许等于）、D未再被破，以及盘中突破前根完整最高价。它没有要求另有一根完整15分钟回踩K线。",'',
        '因此，同一根09:30阳线被同时用作D所在K线及B1止跌参考。09:45才完整知道其最高80,655.70；下一分钟最高越过80,655.71，机械条件通过。记录中的rebound和HL均为空：这不阻止B1，但B2不会通过。净目标空间约2.983R只说明目标与风险之比，不证明反弹成功概率。','',
        '09:39已有1分钟局部突破，但旧15分钟D已在09:30–09:31被破、新D尚未完整确认，不能把09:45之后才知道的新D回填成09:39的更好入场。','',
        '## 1分钟结构：入场前有微型HL，但没有独立15分钟HL','',
        '| 转折类型 | 发生分钟 | 价格 | 右邻完成后才可确认 | 入场时已知？ |',
        '| --- | --- | ---: | --- | --- |']
    for p in r['minute_turns']:
        if ts('2026-10-15T09:30:00-04:00')<=ts(p['time'])<ts('2026-10-15T09:50:00-04:00'):
            lines.append(f"| {'低点' if p['kind']=='low' else '高点'} | {clock(p['time'])} | {p['price']:,.4f} | {clock(p['known_at'])} | {'是' if p['known_at_entry'] else '否'} |")
    lines+=['','09:36的80,039.90高于09:31的80,003.855，09:41再形成80,483.355；这些1分钟微型HL在入场前可以确认，但都位于同一根09:30–09:45的15分钟K线内部。09:44的微低点需09:46才确认，不能提前用于09:45入场。','',
        '## 关键24根1分钟：09:30至止损','',
        '| 区间 | 开 | 高 | 低 | 收 | 该分钟收盘可知时间 | 阶段／事件 |',
        '| --- | ---: | ---: | ---: | ---: | --- | --- |']
    for b in r['minutes_1m']:
        if ts('2026-10-15T09:30:00-04:00')<=b['t']<=ts(s['stop_interval'][0]):
            lines.append(f"| {clock(b['time'])}–{clock(b['end'])} | {b['open']:,.2f} | {b['high']:,.2f} | {b['low']:,.2f} | {b['close']:,.2f} | {clock(b['close_known_at'])} | {b['role']} |")
    lines+=['','## 为什么8分钟内止损','',
        '09:45只短暂突破，高80,682.245，较参考入场仅高26.535；该分钟最终收80,508.782，直到09:46才能完整知道突破未守住。09:46开80,496.2255，已低于前分钟低点80,508.782，最高也只有80,503.10，此后没有重回入场参考价。','',
        f"本笔从D到入场已反弹{s['rebound_from_d_to_entry']:,.3f}；价格风险{s['price_risk']:,.3f}中，只有{s['stop_buffer']:,.3f}（{s['buffer_share_of_price_risk']:.2%}）是原0.25 ATR缓冲，其余来自入场距离D较远。亏损并不是把止损上移到了内部小低点造成的。",'',
        '09:52最低80,004.995，仍高于D约1.14，不能提前记止损。09:53开80,079.55高于止损，但该分钟最低79,821.987已穿D及79,925.0756，因此按止损参考价条件退出；不把最低或收盘当成交价。09:55的更低价和10:00才知道的15分钟收盘都在退出之后，不能倒用于改变这次止损。','',
        '入场分钟的高点在突破／成交前后先后未由tick验证，所以程序不把该分钟高点算成已确认浮盈；后续完整分钟最高也低于入场。原1R浮盈保护未启用。09:53之前连第一根入场后的完整15分钟K线都没有，独立15分钟H-L-LH退出无法形成。','',
        '## 审查结论：B1成立到什么程度','',
        '- 当前B1机械定义：通过，未发现未来15分钟收盘被用于09:45入场。',
        '- 价格结构：确有单根强拉回及1分钟微型HL；15分钟层面只有第一次新低后的反弹尝试，没有独立回踩确认，不能叫底部已确认。',
        '- 失败性质：盘中突破缺少跟进，首分钟收回后继续走弱。属于激进B1允许承担的假突破风险，不能仅因后来亏损反推它违反原规则。',
        '- 若“止跌”意指D所在K线之后，还须一根独立完整15分钟K线守住D，这笔尚未满足那个更严格定义；当前程序没有这个额外要求。本次只明确语义差异，不新增条件、改变阈值或重跑整月。','',
        f"来源：归档Alpaca BTC/USD，105根实际1分钟，缺失0；其中{r['zero_volume_minutes']}根零成交量观测不能当作真实成交证明。源行SHA256：`{r['source_rows_sha256']}`。一分钟OHLC只能支持条件成交区间，不验证真实ETF成交秒数、报价或滑点。",'',
        '## 附录：全部105根实际1分钟，不省略','',
        '| 纽约区间起点 | 开 | 高 | 低 | 收 | 来源成交量 | 阶段 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | --- |']
    for b in r['minutes_1m']:
        lines.append(f"| {clock(b['time'])} | {b['open']:,.4f} | {b['high']:,.4f} | {b['low']:,.4f} | {b['close']:,.4f} | {b['volume']:.9f} | {b['phase']} |")
    return '\n'.join(lines)+'\n'


def main():
    watched=[STORE/'latest_run.json']+list((STORE/'runs').glob('*/result.json'))+list((STORE/'runs').glob('*/RESEARCH.xlsx'))
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in watched}
    r=review();FOLDER.mkdir(parents=True,exist_ok=True);save(FOLDER/'REVIEW.json',r)
    (ROOT/'docs/investigations/2026-11-08_BTC_TRADE5_B1_BAR_AUDIT.md').write_text(report(r))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in before.items())
    print(json.dumps(dict(source_run=RUN,minutes=r['source_minutes'],b1=r['summary']['b1_passed'],b2=r['summary']['b2_passed'],month_rerun=False)))


if __name__=='__main__':main()
