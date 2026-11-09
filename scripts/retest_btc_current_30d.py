"""Authorized fixed-rule monthly replay; preserve every historical run."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk import btc_data,btc_engine


def write_report(result,comparison):
    """Render the completed run only; calling this never replays market data."""
    ny=ZoneInfo('America/New_York')
    def clock(value):
        return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ny).strftime('%m/%d %H:%M %Z')
    def leg(value):
        return ('未触及' if value is None else
            f"{clock(value['time_utc'])} @ {value['price']:,.4f}；净 {value['net']:+,.2f}")
    old=comparison['baseline'];cur=comparison['current'];m=result['metrics']
    lines=['# BTC 批准规则最近30天复测',
        '', '使用已批准A、B1、B2入口和V5退出，数值参数冻结并保留旧结果。',
        '', 'Last Updated: 2026-11-08  ',
        'Status: 已完成，条件模型；固定每笔1 BTC仍净亏损  ',
        'Audience: 交易桌使用者及维护者', '', '## Overview', '',
        f"新记录 `{result['run_id']}`；旧记录 `{old['run_id']}`。",
        f"区间 **{clock(result['start'])} 至 {clock(result['end'])}（不含）**，30×24小时，前7天真实行情预热。",
        'BTC全天信号，ETF零佣金加每边2bps价差滑点假设；未调用订单接口。', '',
        '## 固定规则', '',
        '- A：四个独立、反弹确认的LL及LH后，出现HH、HL，再盘中突破前根完整15分钟最高价。',
        '- B1：≥2倍事前ATR的完整急跌，延伸低点后首次止跌突破，不虚构HL。B2：急跌后完整反弹及HL回踩突破。',
        '- 原初始缓冲0.25 ATR、HL容差0.10 ATR、追价上限0.10 ATR、突破增量$0.01不变。2R仅提示，已知目标净空间须严格为正。',
        '- 初始硬保护成交后立即生效。保留较大波段硬保护上移与已确认15分钟HL后新高的结构参考，两者分开记录。结构参考严格破位退出。',
        '- 首次目标卖25%；没有固定T2。最大浮盈≥初始价格1R且回吐≥50%，当时非绿、不高于前收盘且非内包可退出。',
        '- 末分钟冲高失败：本根创新波段高点，前根完整阳线，价格跌破前根全振幅中点，当时红、≤前收盘、非内包。独立于整笔浮盈回吐率。',
        '- 长上影≥本根已观察振幅50%，最后1分钟检查方向与内包豁免，无整数关口门槛。普通中点下穿只预警。',
        '- 同一观察先硬保护、结构、浮盈回吐、冲高失败、上影、目标。已知首价早于未解析分钟内高低；不偷用最终15分钟收盘。',
        '- 月度一次仅持一笔。不用指定课堂入场覆盖持仓；本次两笔10/12示例均自然被纳入，分别为#1和#4。', '',
        '## 新旧结果', '',
        '| 指标 | 旧版 | 本次 |', '| --- | ---: | ---: |',
        f"| 去重信号／合格 | {old['signals']['all']}／{old['signals']['risk_passed']} | {cur['signals']['all']}／{cur['signals']['risk_passed']} |",
        f"| 入场／已平仓／未平仓 | {old['entries']}／{old['metrics']['closed']}／{len(old['open_positions'])} | {cur['entries']}／{m['closed']}／{len(cur['open_positions'])} |",
        f"| 胜率 | {old['metrics']['win_rate']:.1%} | {m['win_rate']:.1%} |",
        f"| 已平仓净美元，每笔初始1 BTC | {old['closed_net']:+,.2f} | {cur['closed_net']:+,.2f} |",
        f"| 各笔净R之和 | {old['metrics']['net_r']:+.6f}R | {m['net_r']:+.6f}R |",
        f"| 最大R序列回撤 | {old['metrics']['max_drawdown_r']:.6f}R | {m['max_drawdown_r']:.6f}R |", '',
        '**净R为正不代表固定每笔1 BTC盈利。** 各笔净R以各自不同的含摩擦初始风险归一，固定1 BTC对大止损交易承担更大美元风险。两种权重不同。本次固定仓位结果仍亏$1,253.88。旧版期末未平仓毛估值另列，不并入已实现。',
        '', '新旧输入SHA256完全相同。旧B扩展为已批准B1/B2，退出同时采用已批准V5；不能将整体改善只归因于某个退出条件，也不能视为独立样本外验证。',
        '', '## 数据质量与审查口径', '',
        f"实际{result['test_data_quality']['observed_minutes']:,}分钟，预期43,200分钟，缺失558分钟；缺失保持缺失，零量报价记录不是成交证明。",
        '89信号包括44次入场、35次占仓跳过、8次目标缺失及2次结构价格未过；59次不足2R保留。A交易16笔、B1交易16笔、B2交易12笔。',
        '44笔均已平仓，17赢27亏。8笔先卖25%再退75%，另36笔未触及首次目标即退出100%。43次保护上移另表区分较大硬保护与15分钟结构参考。',
        '持有缺口交易#21、#25；其盈亏只是在已观察路径的条件估算。无已标记缺口子集42笔，16赢26亏，净+1.724325R。此标签不保证更早阻力背景完整。',
        '时间是实际1分钟区间起点，精确秒及真实成交未验证；另列UTC消除11月1日重复01点歧义。', '',
        '## 逐笔入场、保护、分批退出及净盈亏', '',
        '金额为美元，每笔初始1 BTC；下表初始保护与入场同时生效。每次上移的低点、确认及生效时间见工作簿“保护变更”及PROTECTION.csv。', '',
        '| #／入口 | 入场时间 | 入场参考 | 初始止损 | 首次25%：时间／价格／净盈亏 | 实际余仓：比例／时间／价格／净盈亏 | 整笔净盈亏 |',
        '| --- | --- | ---: | ---: | --- | --- | ---: |']
    for p in result['trades']:
        first=next((l for l in p['legs'] if l['reason']=='target_25'),None)
        rest=[l for l in p['legs'] if l['reason']!='target_25']
        last=rest[-1] if rest else None
        rest_text=f"{sum(l['fraction'] for l in rest):.0%}；{leg(last)}" if last else '仍持有'
        lines.append(f"| {p['id']}／{p['entry_rule']} | {clock(p['entry_time'])} | {p['entry']:,.4f} | {p['initial_stop']:,.4f} | {leg(first)} | {rest_text} | {p['net']:+,.2f} |")
    lines.extend(['', '## 交付与校验', '',
        f"交易桌默认新记录，研究下拉仍可选旧版。XLSX及SIGNALS、TRADES、EXITS、PROTECTION、LEDGER各CSV保存在独立新记录目录 `{result['run_id']}`。",
        'COMPARISON.json保留全部历史结果／工作簿的SHA256清单，复核未改写。逐笔公式与引擎净收益、R及回撤勾稽。未提交真实或paper订单。'])
    target=ROOT/'docs/investigations/2026-11-08_BTC_APPROVED_RULES_30_DAY_RETEST.md'
    target.write_text('\n'.join(lines)+'\n')


def main():
    store=btc_data.STORE
    old_id='20261109T002127Z-30-ab'
    old=btc_data.read(store/'runs'/old_id/'result.json')
    preserved={str(p.relative_to(store)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (store/'runs').glob('*/*')
        if p.name in ('result.json','RESEARCH.xlsx','WORKBOOK_DATA.json')}
    result=btc_engine.run(30,store,expanded_b=True,
        progress=lambda p:print(json.dumps(p),flush=True))
    folder=store/'runs'/result['run_id']
    for name,digest in preserved.items():
        assert hashlib.sha256((store/name).read_bytes()).hexdigest()==digest,name
    assert result['source_minute_sha256']==old['source_minute_sha256'], 'Different source snapshot: review comparability'
    db=sqlite3.connect(folder/'ledger.sqlite')
    ledger=[json.loads(row[0]) for row in db.execute('SELECT body FROM ledger ORDER BY t')]
    db.close()
    btc_data.save(folder/'WORKBOOK_DATA.json',dict(result=result,ledger=ledger))
    def totals(r):
        return dict(run_id=r['run_id'],strategy_version=r['strategy_version'],
            entries=len(r['trades']),signals=r['signal_counts'],metrics=r['metrics'],
            closed_net=sum(p['net'] for p in r['trades'] if p['status']=='closed'),
            realized_leg_net=sum(l['net'] for p in r['trades'] for l in p['legs']),
            open_positions=[dict(trade_id=p['id'],remaining=p['remaining'],
                unrealized_gross=p.get('unrealized_gross')) for p in r['trades'] if p['status']=='open'])
    comparison=dict(baseline=totals(old),current=totals(result),
        same_source=True,source_minute_sha256=result['source_minute_sha256'],
        changes='Previously approved B1/B2 entries and V5 exits; numerical parameters unchanged',
        historical_files_sha256=preserved)
    btc_data.save(folder/'COMPARISON.json',comparison)
    write_report(result,comparison)
    print(json.dumps({k:v for k,v in comparison.items() if k!='historical_files_sha256'},indent=2),flush=True)


if __name__=='__main__':main()
