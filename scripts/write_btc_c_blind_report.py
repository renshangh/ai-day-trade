"""Render the completed, locked read-only comparison; no classification edits."""
from pathlib import Path
import csv
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from scripts.audit_btc_c_blind_review import OUT,locked,preservation,load_saved,table
from scripts.audit_btc_parent_hl_losses import local

NAMES={'evidence_insufficient':'证据不足，待审','failed_parent_branch_rebound':'旧父段失效后的反抽',
    'failed_local_rebound_reentry':'原反弹未收复的再入场','normal_continuation_candidate':'正常延续候选',
    'parent_support_retest_probe':'父底回测试探'}
cash=lambda n:f'{n:,.2f}'


def run():
    locked();preservation()
    with (OUT/'REVEALED_20.csv').open(encoding='utf-8-sig') as f:twenty=list(csv.DictReader(f))
    with (OUT/'ALL_FIXED_C_TRADES.csv').open(encoding='utf-8-sig') as f:all_rows=list(csv.DictReader(f))
    sample=read(OUT/'SEALED_OUTCOMES.json');summary=read(OUT/'ALL_FIXED_SUMMARY.json')
    _,results,_=load_saved();legs=[]
    samples_by_id={p['id']:code for code,p in sample.items()}
    for model,result in results.items():
        for p in result['trades']:
            if p['entry_rule']!='C':continue
            for i,leg in enumerate(p['legs'],1):
                legs.append(dict(model=model,trade_id=p['id'],entry_ny=local(ts(p['entry_time'])),entry=p['entry'],
                    initial_stop=p['initial_stop'],target1=p['t1'],leg=i,fraction=leg['fraction'],
                    exit_ny=local(ts(leg['time_utc'])),reason=leg['reason'],price=leg['price'],gross=leg['gross'],
                    cost=leg['cost'],net=leg['net'],blind_sample_code=samples_by_id.get(p['id'],'') if model=='0.1' else ''))
            assert abs(sum(l['net'] for l in p['legs'])-p['net'])<1e-8
    table(OUT/'ALL_ORIGINAL_EXIT_LEGS.csv',legs)
    sample_stats=read(OUT/'REVEALED_20_SUMMARY.json')
    lines=['# C 父波段结构：20 笔盲判与全量固定交易对照','',
        '先锁定口径、再判读入场前数据、最后揭示原结果；不修改任何交易路径。','',
        'Last Updated: 2026-11-09','Status: Research diagnosis only; no filter promoted',
        'Audience: 交易桌使用者与研究维护者','', '## Overview','',
        '**主要结论：父段失效值得继续核对；触发线下移不能直接作为硬过滤器。**',
        '20 笔样本看起来较好，但同一锁定口径用于全量固定交易后，触发线标记会排除更多盈利金额，',
        '组合标记的损失/盈利金额接近抵消。没有因此调整定义或重新运行策略。','',
        '## 方法与可知性','',
        '- 先写入 PROTOCOL.json 并锁定分类代码哈希，再抽样；随后保存 CLASSIFICATIONS.json，最后才打开结果文件。',
        '- 样本来自 0.1+C 原 109 笔，排除此前已查看的 #3/#13/#22/#60/#90/#95/#112/#124。',
        '- 在剩余 101 笔中，以固定 SHA256 顺序从盈利和非盈利组各选 10 笔，盲号顺序也由固定哈希决定。',
        '- 分类函数只接收父段、原入场时间/参考价格和入场前分钟；拒绝原入场分钟、未来 OHLC、退出和盈亏字段。',
        '- 这是程序输入隔离、结果揭示前锁定标签；不是独立人工盲审，也不是样本外检验。研究者此前看过月度汇总。',
        '- 10 盈/10 亏是分层抽样设计，不代表整月胜率；全量仍是同一历史窗口，且包含这 20 笔，不是第二份独立验证集。',
        '- 没有调 ATR、止损、退出、2R、P1 或 C；P1 未用于新增分类。没有运行策略、替代入场或新交易顺序。','',
        '## 抽样前锁定的两项检查','',
        '父段检查：固定当前 C 已选 D/H，查 H 后完整确认的小时 L、随后完整小时 LH，再在两者已知之后观察严格破 L。',
        '新选定 D 开始新范围；只出现更新的底却未被当前 C 采用，不会自动恢复旧父段。若后来重新收复原 H，归属列待审。','',
        '触发检查：结构整体已知时的前根高 + 0.01 是初始参考。需同时看到参考降低、初始线未在入场前被穿越、',
        '已有确认的 HL 后反弹峰、原买价仍低于该峰及初始参考、而峰后新 HL 尚未确认，才给出明确标记。',
        '初始参考只是结构参考，不代表当时其他风险/目标条件已经准入。单独参考降低只记警告。','',
        '缺失分钟、父段回撤中的小时 outside turn、HL 后十五分钟 outside turn、或旧失败后的父峰收复，均列证据不足，',
        '保留已观察风险证据，但不算明确排除候选。缺失不补，outside 极值也未假装不存在。','',
        '## 20 笔揭示结果','',
        '| 检查 | 明确标记笔数 | 原盈利 / 原亏损笔数 | 原盈利净额 | 原亏损净额 |',
        '|---|---:|---|---:|---:|']
    for k,name in [('parent_flag','父段失效'),('trigger_flag','触发线下移且反弹未修复'),('either_clear','两者任一，去重')]:
        s=sample_stats[k];lines.append(f'| {name} | {s["count"]} | {s["wins"]} / {s["losses"]} | ${cash(s["original_winning_net"])} | ${cash(s["original_losing_net"])} |')
    lines+=['','组合明确标记 7 笔，其中 5 亏、2 盈；另外 3 笔证据不足，没有当作被删除。',
        '原盈利和亏损是保存路径的净额，均按初始 1 BTC、原成本；不是过滤后策略收益。两个检查有重叠，不相加。','',
        '| 盲号 | 原 C 编号 | 入场纽约时间 | 入场前分类 | 两项证据 | 明确标记？ | 揭示原净额 |',
        '|---|---:|---|---|---|---|---:|']
    for r in twenty:
        evidence='/'.join(x for k,x in [('parent_flag','父段'),('trigger_flag','触发')] if r[k]=='True') or '无'
        lines.append(f'| {r["label"]} | #{r["original_trade_id"]} | {r["entry_ny"]} | {NAMES[r["category"]]} | {evidence} | {"是" if r["screen_candidate"]=="True" else "否"} | ${cash(float(r["original_net"]))} |')
    lines+=['','样本中的被标记盈利：S03 / #69（10/25 22:48）+$272.17；S15 / #129（11/06 20:01）+$41.71。',
        '盈利不能证明风险证据不存在，但若直接删除交易，盈利同样会丢失。','',
        '## 原三例控制与自动分类的局限','',
        '#90 仍是正常延续候选，03:17 仍是父底回测试探，都没有明确排除标记。',
        '#13 的父段失败和触发下移两项证据仍在，但中途小时 outside bar 令锁定的保守自动口径列为待审。',
        '这与此前人工能够指出确定失败链的解释存在置信度差异；没有为让它得到预期标签而改代码。',
        '20 个新样本恰好没有被归为正常延续候选，所以不能声称已独立验证“不会误伤所有正常回踩”；#90 是已知控制。','',
        '## 同一口径的全量固定交易归因','',
        f'读取原保存的 {summary["model_trade_rows"]} 个模型交易行，合并为 {summary["unique_entry_contexts"]} 个不同入场/结构。',
        '三个模型有大量重叠，不能当成 368 次独立验证。分类文件先保存，再连接原出场与盈亏。原 20 笔标签完全一致。','',
        '| 模型 / 检查 | 明确标记 | 原盈利 / 原亏损 | 原盈利净额 | 原亏损净额 | 标记组原净额 |',
        '|---|---:|---|---:|---:|---:|']
    for model,m in summary['models'].items():
        for k,name in [('parent_flag','父段失效'),('trigger_flag','触发线下移'),('either_clear','任一，去重')]:
            s=m[k];lines.append(f'| {model} / {name} | {s["count"]} | {s["wins"]} / {s["losses"]} | ${cash(s["original_winning_net"])} | ${cash(s["original_losing_net"])} | ${cash(s["original_net"])} |')
    lines+=['','0.1 原 C 为 37 盈/72 亏。组合标记碰到 10/37 笔盈利（约 27%），以及 15/72 笔亏损（约 21%）；',
        '仅看“标记到的亏损笔数更多”会忽略总体原本就有更多亏损。触发检查单独碰到 10 盈/8 亏，标记组反而原净赚 $1,619.16。',
        '父段检查单独为 2 盈/8 亏、原净亏 $1,478.52，有进一步核对价值，但并没有解决大多数 C 亏损。',
        '0.1/E1/E2 分别另有 16/27/16 行列证据不足，未算作明确删除。','',
        '## 触发标记误伤的具体反证','',
        '0.1 C #89（10/28 10:50）原净盈 +$708.03，父段失败检查不触发；触发检查却会标记：',
        '结构已知后的参考依次为 10:15 的 $80,752.425、10:30 的 $80,582.68、10:45 的 $80,504.3525。',
        '当时已有确认峰 $80,752.415，而更新的回踩低尚未完成三根确认。它与亏损案例一样满足这组价格证据，却最终盈利。',
        '另有 #114（11/03 03:15）+$469.24、#118（11/04 00:18）+$313.85 被同项标记。',
        '这些结果不证明入口无风险，但直接硬拦会丢掉实质盈利，不能用已知 #13 的解释替代全量证据。','',
        '## 结论与下一步边界','',
        '1. 保留父段归属检查作为后续逐根研究重点，先核对它标记的盈利及 outside-bar 待审项；尚不接入交易。',
        '2. 触发线下移维持研究警告，当前证据不支持直接当硬过滤器；不为改善结果加最小跌幅、等待根数等新参数。',
        '3. 组合检查也不升级：全量标记组的原亏损与原盈利接近抵消，而且大量亏损未识别。',
        '4. 未运行完整顺序回测。固定交易归因不能回答提前跳过后是否产生新买点、资金占用变化或新组合收益。','',
        '## 文件与核验','',
        '`reports/btc_c_blind_review_2026_11_09/` 保存锁定口径、匿名入场前资料、分类锁、揭示表、全量原交易、',
        '全量原出场腿、汇总和分阶段哈希记录。主要表格为 `REVEALED_20.csv`、`ALL_FIXED_C_TRADES.csv`、`ALL_ORIGINAL_EXIT_LEGS.csv`。',
        '四项针对真实案例的检查通过：正常控制不被小时峰未确认排除、缺失观察降为待审、拒绝未来/盈亏输入、',
        '20 笔锁定标签可重复。冻结文件和原 C/P1 结果逐项核验，Live Paper 同一 worker 继续运行，订单始终禁用。','']
    report=ROOT/'docs/investigations/2026-11-09_BTC_C_BLIND_REVIEW.md';report.write_text('\n'.join(lines))
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    title='BTC C Blinded Structure Review'
    public='''
:Last Updated: 2026-11-09
:Status: Fixed-entry diagnostic only; no filter promoted
:Audience: Trading Desk owner and research maintainers

Overview
--------

The locked protocol classifies twenty new baseline C entries using only
pre-entry observations, with exit/P&L fields withheld. The sample is stratified
ten wins/ten losses by a fixed SHA256 selection. This is procedural input
blinding in the same historical window, not independent human or out-of-sample
validation. Labels are saved before outcomes are joined.

Seven clear flags include five losing and two winning original trades. The
unchanged classifier then annotates 368 saved model rows / 149 unique entry
contexts, without replaying any strategy or changing trade paths. On baseline
C, the parent-failure flag marks 8 losses/2 wins; the trigger-lowering flag
marks 8 losses/10 wins whose original net is positive $1,619.16. This does not
support promoting trigger lowering to a hard filter. Unknown outside/gap
contexts remain manual review, including the known #13 control.

The complete Chinese report is in
``docs/investigations/2026-11-09_BTC_C_BLIND_REVIEW.md``. Tables and stage hashes
are in ``reports/btc_c_blind_review_2026_11_09/``. Original P1/C, frozen 0.2,
entries, exits, costs and the running Live Paper session remain unchanged.
No replacement opportunities, new monthly returns or broker orders are created.

Reproduction
------------

``scripts/audit_btc_c_blind_review.py`` has separate prepare, classify, reveal
and fixed-entry-all phases. The protocol and classifier hashes are locked
before labels. Prepare refuses to overwrite the existing study. Read the saved
artifacts for review rather than rerunning or altering the locked investigation.
'''
    (ROOT/'docsrc/BTC_C_BLIND_REVIEW.rst').write_text(title+'\n'+'='*len(title)+'\n'+public)
    preservation();print(dict(report=str(report),sample_rows=len(twenty),full_rows=len(all_rows),original_exit_legs=len(legs)))


if __name__=='__main__':run()
