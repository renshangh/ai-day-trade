"""Export completed parent-only sequential study and human-readable report."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,ts
from trading_desk.btc_parent_filter_view import PARENT_FILTER_VIEW as VIEW
from scripts.audit_btc_c_blind_review import table,preservation,locked
from scripts.audit_btc_parent_hl_losses import local

OUT=ROOT/'reports/btc_parent_filter_2026_11_09'
money=lambda v:f'{v:,.2f}'


def run():
    locked();preservation();s=VIEW.current();assert s['status']=='complete'
    OUT.mkdir(parents=True,exist_ok=True);summaries=[];trades=[];legs=[];decisions=[]
    for model,pair in s['summaries'].items():
        for group in ('all','no_flagged_gap','gap_or_partial_context'):
            a=pair['control'][group];b=pair['variant'][group]
            summaries.append(dict(model=model,group=group,control_entries=a['entries'],filtered_entries=b['entries'],
                control_net=a['net'],filtered_net=b['net'],net_change=b['net']-a['net'],
                control_cost=a['cost'],filtered_cost=b['cost'],control_drawdown_R=a['max_drawdown_r'],filtered_drawdown_R=b['max_drawdown_r'],
                control_closed_trade_drawdown_USD=a['max_closed_trade_drawdown_usd'],filtered_closed_trade_drawdown_USD=b['max_closed_trade_drawdown_usd']))
        for sequence in ('control','variant'):
            _,_,r=VIEW.selection(model,sequence)
            for a in r['parent_filter_audits']:
                decisions.append(dict(model=model,sequence=sequence,signal_id=a['signal_id'],time_ny=local(ts(a['time_utc'])),
                    reference=a['entry_reference'],parent_flag=a['parent_flag'],uncertainty='; '.join(a['uncertainty']),
                    trigger_flag_ignored=a['trigger_flag_ignored'],would_block=a['would_block'],blocked=a['blocked'],trade_id=a['trade_id']))
            for p in r['trades']:
                first=next((l for l in p['legs'] if l['reason']=='target_25'),None)
                final=[l for l in p['legs'] if l['reason']!='target_25'];last=final[-1] if final else None
                trades.append(dict(model=model,sequence=sequence,trade_id=p['id'],route=p['entry_rule'],
                    entry_ny=local(ts(p['entry_time'])),entry=p['entry'],initial_stop=p['initial_stop'],stop_effective_ny=local(ts(p['entry_time'])),
                    target1=p['t1'],first_25_ny=local(ts(first['time_utc'])) if first else None,
                    first_25_price=first['price'] if first else None,first_25_net=first['net'] if first else None,
                    remainder_ny=local(ts(last['time_utc'])) if last else None,remainder_price=last['price'] if last else None,
                    remainder_fraction=sum(l['fraction'] for l in final),remainder_net=sum(l['net'] for l in final) if final else None,
                    net=p['net'],holding_gap=p['gap_exposed'],partial_context=p['context_partial']))
                for l in p['legs']:
                    legs.append(dict(model=model,sequence=sequence,trade_id=p['id'],route=p['entry_rule'],
                        entry_ny=local(ts(p['entry_time'])),entry=p['entry'],exit_ny=local(ts(l['time_utc'])),
                        price=l['price'],fraction=l['fraction'],reason=l['reason'],gross=l['gross'],cost=l['cost'],net=l['net']))
        table(OUT/f'CHANGES_{model}.csv',s['attribution'][model])
    for name,rows in [('SUMMARY.csv',summaries),('ALL_TRADES.csv',trades),('ALL_EXIT_LEGS.csv',legs),('ALL_PARENT_DECISIONS.csv',decisions)]:table(OUT/name,rows)
    lines=['# C 父段失效过滤：独立完整顺序回测','',
        '同一三十天真实行情，对照 P1+C 与仅增加父段失效过滤的独立实验。','',
        'Last Updated: 2026-11-09','Status: Complete research comparison; improved but all variants remain negative; not promoted',
        'Audience: 交易桌使用者与研究维护者','', '## Overview','',
        '**三个退出模型的亏损与已平仓交易回撤均下降，但三个过滤版本仍然亏损。**',
        '本轮没有后续调参，没有加入触发线下降过滤，没有以 #13 人工复核覆盖锁定的待审标签。',
        'P1、原 C、冻结 0.2、原报告与 Live Paper 保持不变。','',
        f'研究编号：`{s["study_id"]}`。交易桌独立页面：`/btc-parent-filter`。',
        '0.1/E1/E2 在本页指 P1+C 的三种退出模型，不是重新发布 frozen 0.2。','',
        '## 全部交易结果','',
        '| 模型 | P1+C 对照净额 | 父段过滤净额 | 改善 | 对照→实验笔数 | 已平仓最大回撤 R | 已平仓最大回撤 USD |',
        '|---|---:|---:|---:|---|---|---|']
    for model,pair in s['summaries'].items():
        a=pair['control']['all'];b=pair['variant']['all']
        lines.append(f'| {model} | ${money(a["net"])} | ${money(b["net"])} | ${money(b["net"]-a["net"])} | {a["entries"]} → {b["entries"]} | {a["max_drawdown_r"]:.2f} → {b["max_drawdown_r"]:.2f} | ${money(a["max_closed_trade_drawdown_usd"])} → ${money(b["max_closed_trade_drawdown_usd"])} |')
    lines+=['','所有交易在窗口内已关闭。固定每笔初始 1 BTC、原每边 2bps 价差/滑点代理成本。',
        '这是归一化模型结果，不是复利账户收益、实际 ETF 或实际加密交易费结果。回撤按已平仓交易',
        '净额/原 R 累计计算，不是包含持仓浮亏的账户逐分钟权益回撤。','',
        '## 缺口分组','',
        '| 模型 | 无持仓/初始上下文缺口：对照→实验净额 | 含标记缺口/上下文：对照→实验净额 |',
        '|---|---|---|']
    for model,pair in s['summaries'].items():
        lines.append(f'| {model} | ${money(pair["control"]["no_flagged_gap"]["net"])} → ${money(pair["variant"]["no_flagged_gap"]["net"])} | ${money(pair["control"]["gap_or_partial_context"]["net"])} → ${money(pair["variant"]["gap_or_partial_context"]["net"])} |')
    lines+=['','本轮改善都出现在无标记缺口的分组；缺口分组净额未变。两个分组互补，但“无标记缺口”',
        '不保证全部更早的阻力上下文完全无缺失；缺口窗口仍是条件结果。','',
        '## 固定口径与执行顺序','',
        '- 完整重放同一真实分钟源和七天预热，测试窗口仍为 `[2026-10-10T00:00Z, 2026-11-09T00:00Z)`。',
        f'- 测试期真实观察 {s["source_quality"]["observed_minutes"]} 分钟，缺失 {s["source_quality"]["missing_minutes"]} 分钟，全部保持缺失。',
        f'- 源分钟 SHA256：`{s["source_minute_sha256"]}`。',
        '- 先原样复现每个 P1+C 对照的完整交易状态、入场、止损、目标、出场腿与指标，三者完全一致。',
        '- 对照每个原 C 买点的父段/触发证据与锁定全量盲审也逐项一致。',
        '- 实验仅在原本会开仓的合格 C 信号处，调用同一个锁定分类函数；只有 parent_flag 且 uncertainty 为空才拒绝。',
        '- 分类输入不含当前入场分钟或未来数据。A/B 优先，持仓/退出分钟不重入；触发下降只记录，不参与拒绝。',
        '- outside/gap/reclaim 等待审情况继续保留，#13 原自动待审继续有效。没有使用人工例外。',
        '- C 第一次穿越仍消耗原 HL；拒绝没有成交，所以不伪造持仓、不重置 A/B 入场历史。随后新信号按原状态自然形成。',
        '- 原买价、追价、父 D 止损、25% 首次目标、余量退出、原成本的公式全部继承。新信号对应的新结构仍按原公式计算。','',
        '## 交易顺序如何改变','',
        '| 模型 | 旧交易未再出现 | 新交易 | 同买点出场变化 | 完全匹配 | 新交易原实验净额 | 未再出现旧交易原净额 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for model,diff in s['changes'].items():
        a=[x for x in diff if x['status']=='added'];removed=[x for x in diff if x['status']=='removed']
        lines.append(f'| {model} | {len(removed)} | {len(a)} | {sum(x["status"]=="changed" for x in diff)} | {sum(x["status"]=="unchanged" for x in diff)} | ${money(sum(x["p1"]["net"] for x in a))} | ${money(sum(x["original"]["net"] for x in removed))} |')
    lines+=['','例如 0.1：新增七笔含三盈四亏，合计 -$1,080.23；少掉十四笔原交易（三盈十一亏），',
        '它们原净额 -$2,857.73；两者净差约 +$1,777.50。没有把所有被跳过的亏损直接算成新收益。',
        '新增买点不全是原持仓占位造成，也有拒绝后未消费入场历史而产生的 B1；A/B 定义没有改变。','',
        '| 模型 | 实验 C 实际检查 | 拒绝 | 待审保留 | 原对照中本会被父段过滤的 C |',
        '|---|---:|---:|---:|---:|']
    for model,c in s['filter_counts'].items():lines.append(f'| {model} | {c["evaluated"]} | {c["blocked"]} | {c["uncertain_kept"]} | {c["control_would_block"]} |')
    lines+=['','拒绝数量不能全部对应旧交易盈亏：顺序变化会产生原对照未开仓的新 C 候选，不能为这些拒绝项',
        '虚构原盈亏。表格区分直接拒绝原买点、实验持仓占位、以及后续历史/结构变化。','',
        '## 被跳过的盈利也保留','',
        '| 模型 | 原交易编号 | 原入场纽约时间 | 原净盈利 | 原因 |','|---|---:|---|---:|---|']
    for model,rows in s['attribution'].items():
        for x in rows:
            if x['status']=='removed' and x['control_net']>0:
                reason='直接父段过滤' if x['directly_parent_blocked'] else '实验持有其他仓位'
                lines.append(f'| {model} | {x["control_id"]} | {local(ts(x["entry_time"]))} | ${money(x["control_net"])} | {reason} |')
    lines+=['','0.1/E2 直接丢掉此前复核的两笔盈利（+$260.44、+$272.17），还间接丢掉一笔 +$75.85。',
        'E1 只丢掉前两笔原盈利。不能据净亏损缩小而隐藏这些代价。','',
        '## 文件、边界与结论','',
        '`reports/btc_parent_filter_2026_11_09/` 提供 SUMMARY、ALL_TRADES、ALL_EXIT_LEGS、',
        'ALL_PARENT_DECISIONS 及三份 CHANGES CSV。交易桌可切换控制/实验与三个退出模型，',
        '查看完整顺序、每笔真实十五分钟图、入场/所有出场标记、结构时间、实际拒绝和待审记录。','',
        '本轮确实改善 P1+C 的这段样本，但仍未扭亏；这不是保留 C 已优于 P1-only 的证明，',
        '也不是样本外验证。没有为改善结果继续调参、发布新版本或接入 Live Paper。','',
        '实验适配器为 `trading_desk/btc_parent_filter.py`，重放器为 `scripts/retest_btc_parent_filter.py`。',
        '实验与原控制、冻结文件和盲审的哈希分别记录；仅新增独立 parent_filter_studies 指针，',
        '未改原 P1/C/冻结选择、策略文件、Live Paper 控制或运行会话。','']
    text='\n'.join(lines);(ROOT/'docs/BTC_PARENT_FILTER_RESEARCH.md').write_text(text);(OUT/'REPORT.md').write_text(text)
    title='BTC Parent-Only Sequential Comparison'
    rst='''
:Last Updated: 2026-11-09
:Status: Separate research; improved but still negative; not promoted
:Audience: Trading Desk users and maintainers

Overview
--------

Open ``/btc-parent-filter`` for the independent full-sequence comparison of
P1+C controls against the locked parent-failure-only C filter. The original
controls reproduce exactly. The same minute stream, seven-day warmup, stops,
targets, exit methods and costs are retained. Uncertain cases remain eligible;
trigger lowering is diagnostic only. No manual #13 override is used.

The filtered 0.1/E1/E2 model nets are -$6,797.67 / -$8,866.65 / -$7,113.90,
improving their P1+C controls by $1,777.50 / $1,757.28 / $1,777.50. All remain
negative. Closed-trade drawdowns fall; these are fixed-1-BTC model outcomes,
not compounded or mark-to-market account returns. Each gap group is separate.

Full sequences permit replacement A/B/C opportunities after a rejected C.
These are not fixed-entry deletion sums: baseline adds seven trades with net
-$1,080.23 while fourteen old entries disappear. Lost winners and all actual
exit legs remain visible, with charts, chronological protection and CSVs.

Preservation
------------

``docs/BTC_PARENT_FILTER_RESEARCH.md`` documents the exact contract and results.
``scripts/retest_btc_parent_filter.py`` writes separate runs/study folders;
opening the read-only result page never starts it. Existing P1/C, frozen 0.2,
blind labels, original selectors and the Live Paper worker remain unchanged.
The research is not promoted and no broker orders are sent.
'''
    (ROOT/'docsrc/BTC_PARENT_FILTER_RESEARCH.rst').write_text(title+'\n'+'='*len(title)+'\n'+rst)
    locked();preservation();print(dict(study_id=s['study_id'],trade_rows=len(trades),exit_legs=len(legs),decisions=len(decisions)))


if __name__=='__main__':run()
