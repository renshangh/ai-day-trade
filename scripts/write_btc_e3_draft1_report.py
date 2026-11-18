"""Render the locked ten-case E3 study, without changing rules or outcomes."""
from __future__ import annotations
from datetime import datetime
from html import escape
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts

OUT=ROOT/'reports/btc_e3_draft1_2026_11_15'
NY=ZoneInfo('America/New_York')


def clock(t):
    if t is None:return '—'
    if isinstance(t,str):t=ts(t)
    return datetime.fromtimestamp(t,NY).strftime('%m/%d %H:%M:%S %Z')


def cash(v):return '—' if v is None else f'${v:,.2f}'


def explanation(p):
    if p['triggered']:
        return '原已知赢家提前退出后转亏' if p['baseline_status']=='closed' and p['E3_net']<=0 else '原仓未平；按同一历史截点的标记值比较'
    rows=[f for f in p['scan']['trace'] if f.get('complete')]
    if not any(f['gates']['A_close_below_HL'] for f in rows):
        return '未出现完整5m收盘失守HL；盘中低点下穿不够'
    others=[f for f in rows if all(v for k,v in f['gates'].items() if k!='rapid')]
    if others:
        maximum=max(f['down_atr'] for f in others)
        return f'其余条件通过时最大10m净跌{maximum:.3f}ATR，未达1ATR'
    if p['scan']['attempts']:return '; '.join(a['status'] for a in p['scan']['attempts'])
    return '失守、持续未收复、方向和非内包没有同时满足'


def run():
    r=read(OUT/'RESULT.json');lock=read(OUT/'LOCKED_RULE.json')
    assert r['rule']==lock['definition']['rule']
    assert r['cohort']==[6,7,33,39,40,70,78,114,123]
    cases=[r['example']]+r['winners'];summary=r['winners_summary']
    lines=['# E3草案1十笔固定入场对照','',
        '先锁定急跌、支撑失守与持续未收复，再复核01:44案例及九笔已知赢家。','',
        'Last Updated: 2026-11-15  ','Status: 十笔对照完成；误伤三笔赢家；未接入0.2或live worker  ',
        'Audience: Trading Desk owner and maintainers','','## Overview','',
        f"E3草案1在锁定的九笔赢家中触发{summary['triggered']}笔，三笔均从原盈利变成模拟亏损。九笔固定入场原净额合计{cash(summary['original_net'])}，加入本退出后{cash(summary['E3_net'])}，差额{cash(summary['delta'])}。这不是重新运行的月度收益，不包含因提前卖出而可能产生的新买点。",
        f"01:44案例在02:45确认、02:46以真实分钟开盘$63,836.8905作模拟退出，净额{cash(r['example']['E3_net'])}。原仓在相同历史截点仍未平，标记净浮盈{cash(r['example']['baseline_same_cutoff_net'])}；按同一截点估值的差额为{cash(r['example']['same_cutoff_delta'])}，不是与已实现原利润比较。",
        f"定义锁定时间：{lock['locked_at']}。九笔ID来自上轮审查的0.1保留父背景组合，未重新挑选：{r['cohort']}。本次只是固定十笔入场的退出研究，没有整月重跑、重入、参数搜索或结果后回调。",'',
        '## E3草案1的量化定义','',
        '令H为入场时已完整确认的15分钟HL，整笔固定；不把后来的内部小低点换进来。A、B为紧邻的两根完整5分钟K线，均始于入场分钟之后的完整5分钟边界。',
        '1. 急跌：A开盘减B收盘 ≥ 1.0 × ATR。ATR采用A开始前已知的原14根完整15分钟ATR，整个10分钟窗口冻结，不拿急跌后的ATR回填。',
        '2. 支撑失守：A收盘严格低于H。A不必是整笔第一次失守；更晚的新完整窗口仍可单独符合条件。',
        '3. 持续未收复：B最高价严格低于H，且B收盘也低于H；第二根整段5分钟都没有碰回H。',
        '4. 方向过滤：B严格收阴、收盘不高于A收盘；B全振幅及实体均不得内包于A。无需达到1R浮盈或另等H-L-LH。',
        '5. 模拟执行：B完整结束后统一等待60秒，用该精确真实1分钟的开盘价作退出参考，卖出当时剩余仓位。不是按信号收盘或HL价格回填更好的卖价。',
        '6. 原有更早及同执行分钟的退出优先；原25%卖出腿若已发生则保留，只退出余量。同分钟先后不能确认时保留原腿并标记；原整仓退出已发生则不再应用E3。',
        '7. 缺分钟不拼接、不插值；不完整A/B不合格，缺精确执行分钟取消该次尝试。案例真实输入必须在选定执行分钟之前收到；九笔历史源没有同期收讯记录，+60秒只是统一模型假设。',
        '原入场、初始止损、目标和每边2bps成本代理保持不变。此处退出为独立假设，不是已执行订单或live信号。','',
        '## 十笔触发时间价格与盈亏','',
        '时间使用对应日期的纽约EDT/EST。信号收盘仅为确认参考，模拟退出使用其后一整分钟的真实首价。未触发则保留原退出及全部原卖出腿。',
        '', '| 案例 | 确认时间 / 信号收盘 | 模拟退出时间 / 价格 | 原净额或历史标记 | E3后净额 | 差额 | 结论 |',
        '| --- | --- | --- | ---: | ---: | ---: | --- |']
    for p in cases:
        s=p['E3_selected']
        signal=f"{clock(s['signal_at'])} / {cash(s['signal_reference'])}" if s else '未触发'
        exit_=f"{clock(s['execution_at'])} / {cash(s['execution_price'])}" if s else '保留原退出'
        base=cash(p['baseline_same_cutoff_net'])+('（浮盈标记）' if p['baseline_marked_not_realized'] else '')
        lines.append(f"| {p['label']} | {signal} | {exit_} | {base} | {cash(p['E3_net'])} | {cash(p['same_cutoff_delta'])} | {explanation(p)} |")
    lines += ['',
        'winner-114保留原缺口/入场背景不完整标记；在本次入场后的5分钟扫描窗口内没有缺失分钟。未触发不等于全部更早背景数据完整。',
        '这十笔被有意挑作诊断：九笔为先前已知赢家，另有一笔未平仓案例。因此不能据此估计E3整体胜率、全月净额或对所有亏损的保护效果。',
        '', '## 01:44案例逐步发生了什么','',
        '固定入场$64,440.143，原HL为$64,137.90，原硬止损$61,905.1148。02:36的一分钟低点/收盘失守，只是观察，不满足完整E3；02:30–02:35的5m还收$64,217.89，高于HL，因此02:40虽有快速下跌，仍未通过持续失守的两根组合。',
        '第一组完整合格组合为A=02:35–02:40、B=02:40–02:45：A开$64,210.278、收$64,037.0735；B高$64,053.15、开$64,033.9405、收$63,864.13。原HL已失守且整根B未收复；B收阴、低于前收且非内包。冻结ATR=$276.1877857，10m开收净跌$346.148/ATR=1.2533。',
        '02:45确认，实际完整输入在02:45:01收到，早于预先规定的02:46执行参考。02:46真实开盘$63,836.8905，毛额-$603.2525，成本代理$25.6554，净额-$628.9079；未发生首次25%止盈，所以假设退出100%。',
        '原持仓最后历史参考在05:15为$65,555.132，05:16截点仍未平，净标记浮盈$1,088.9899。E3让该固定入场更早离场，但本次对照没有把空仓转成03:20新买点，也没有把原仓强制在05:15平掉。',
        '', '## 每笔完整轨迹与原退出腿','',
        '第一根完整5m仅提供A，不能独立触发。HTML报告每笔可展开全部相邻5m组合，完整JSON及BAR_TRACE.csv也不省略。E3退出后的行只是原持仓行情对照，不能当作E3仍在持仓或再次卖出。']
    for p in cases:
        lines += ['',f"### {p['label']}",'',
            f"原入场 {clock(p['entry_time'])} / {cash(p['entry'])}；H={cash(p['H'])}；初始止损{cash(p['initial_stop'])}。{explanation(p)}。",
            f"原退出/标记截点：{clock(p['baseline_exit'] or p['cutoff'])}；原状态{p['baseline_status']}；含缺口/部分背景标记：{p['gap_or_partial_context']}；扫描缺失窗口{p['scan']['missing_windows']}。",'',
            '| 原退出腿 | 时间 | 比例 | 价格 | 净额 |','| --- | --- | ---: | ---: | ---: |']
        for l in p['baseline_legs']:lines.append(f"| {l['reason']} | {clock(l['time_utc'])} | {l['fraction']:.0%} | {cash(l['price'])} | {cash(l['net'])} |")
        if not p['baseline_legs']:lines.append('| 未平仓，无已实现退出腿 | — | — | — | — |')
    lines += ['', '## 保留与限制','',
        '锁定文件LOCKED_RULE.json在核对结果前保存，复跑仅接受完全相同定义与样本ID。本次选择1ATR、两个5分钟和60秒是初稿假设，不能称为已验证的最佳设置。原始分钟、原ATR、原盈亏均未改写。',
        f"原{r['preservation']['files']}个保护文件和额外{r['extra_protected_files']}个研究文件通过哈希保留检查。原worker PID {r['preservation']['pid']}、session {r['preservation']['session']}保持运行；0.2、PH5/父背景研究和原选择器未变。",
        '参考价格有quote-derived和零场内成交量分钟，无法据此断言真实深度、点差、可成交量或保证在该开盘价成交。九笔历史缺同期收讯记录；固定+60秒不能证明当年真实数据延迟足够短。首次25%或其他原腿同分钟优先只是一致的保守比较口径，不是假定已知秒内次序。',
        '当前版本在这组固定入场中误伤明显，不宜接入现有系统。尚未重跑整月，也没有研究E3后重入，不能把九笔净差当成整月变化。没有为了使结果好看而改门槛。']
    md='\n'.join(lines)+'\n';(OUT/'REPORT.md').write_text(md)
    (ROOT/'docs/investigations/2026-11-15_BTC_E3_DRAFT1_TEN_CASE_REVIEW.md').write_text(md)
    html=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>E3草案1十笔对照</title><style>body{font:16px/1.65 system-ui;color:#18283c;max-width:1400px;margin:24px auto;padding:0 16px}.scroll{overflow-x:auto;max-width:100%}table{border-collapse:collapse;min-width:1050px;width:100%;font-size:14px}td,th{border:1px solid #cbd5e1;padding:7px;vertical-align:top;text-align:left}th{background:#edf2f8}details{padding:12px 0;border-bottom:1px solid #cbd5e1}summary{cursor:pointer;font-weight:bold}.bad{background:#fff2ee}p{max-width:1100px}small{display:block;color:#526174}</style>']
    in_table=False
    for line in lines:
        if line.startswith('|'):
            if line.startswith('| ---'):continue
            if not in_table:html.append('<div class="scroll"><table>');in_table=True;header=True
            else:header=False
            tag='th' if header else 'td';cells=line.strip('|').split('|')
            html.append('<tr>'+''.join(f'<{tag}>'+escape(c.strip())+f'</{tag}>' for c in cells)+'</tr>')
            continue
        if in_table:html.append('</table></div>');in_table=False
        if line.startswith('# '):html.append('<h1>'+escape(line[2:])+'</h1>')
        elif line.startswith('### '):html.append('<h3>'+escape(line[4:])+'</h3>')
        elif line.startswith('## '):html.append('<h2>'+escape(line[3:])+'</h2>')
        elif line:html.append('<p>'+escape(line)+'</p>')
    if in_table:html.append('</table></div>')
    html.append('<h2>完整逐根5分钟组合：十笔均可展开</h2><p>横向滚动可查看右侧全部条件。通过=该根已完成时满足；后续原路径不能提前用于决策。</p>')
    total=0
    for p in cases:
        html.append('<details><summary>'+escape(p['label']+' · '+explanation(p))+'</summary><div class="scroll"><table><tr><th>A开始</th><th>B开始→确认</th><th>A开/收</th><th>B开/高/低/收</th><th>原HL</th><th>事前ATR</th><th>10m下降ATR</th><th>全部条件</th><th>未通过条件</th><th>是否E3退出后的原路径</th></tr>')
        for b in p['scan']['trace']:
            total+=1
            if not b.get('complete'):
                html.append('<tr><td>'+escape(clock(b['window_start']))+'</td><td colspan="9">真实分钟缺失，不补值，不用作信号</td></tr>');continue
            a=b['A'];bb=b['B'];values=[clock(a['t']),clock(bb['t'])+' → '+clock(b['known_at']),
                '/'.join(cash(a[k]) for k in ('open','close')),'/'.join(cash(bb[k]) for k in ('open','high','low','close')),
                cash(b['H']),cash(b['ATR']),f"{b['down_atr']:.3f}",'通过' if b['qualified'] else '未通过',
                ', '.join(b['reasons']) or '—','是，仅作原路径对照' if b['after_E3'] else '否']
            html.append('<tr'+(' class="bad"' if b['qualified'] else '')+'>'+''.join('<td>'+escape(v)+'</td>' for v in values)+'</tr>')
        html.append('</table></div></details>')
    html.append('<p>完整轨迹行数：'+str(total)+'。<a href="COMPARISON.csv">汇总CSV</a> · <a href="BAR_TRACE.csv">逐根CSV</a> · <a href="RESULT.json">完整结果JSON</a> · <a href="LOCKED_RULE.json">锁定定义</a></p></html>')
    (OUT/'REPORT.html').write_text(''.join(html))
    print(json.dumps(dict(report=str(OUT/'REPORT.html'),cases=len(cases),trace_rows=total),ensure_ascii=False))


if __name__=='__main__':run()
