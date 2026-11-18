"""Render the saved PH5 comparison without rerunning or adjusting any model."""
from __future__ import annotations
from collections import Counter
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read
from trading_desk.btc_parent_five_view import PARENT_FIVE_VIEW


def clock(value):
    if value is None:return '—'
    d=datetime.fromtimestamp(value,ZoneInfo('America/New_York')) if isinstance(value,(int,float)) else datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))
    return d.strftime('%m/%d %H:%M:%S %Z')


def run():
    folder,s=PARENT_FIVE_VIEW.current()
    assert s['status']=='complete'
    lines=['# BTC 15-Minute Parent HL and Five-Minute Trigger Comparison','',
        'Separate locked PH5 definition, nominated bounce first, then the unchanged frozen-source month.','',
        'Last Updated: 2026-11-15  ','Status: Complete; all experimental variants lose money; not promoted  ',
        'Audience: Trading Desk owner and maintainers','','## Overview','',
        'Open `/btc-parent-five`. The experiment reproduces the three original controls exactly, then tests PH5 alone and A/B + PH5 as separate complete position sequences. Frozen 0.2, P1 and the original live worker are unchanged. The nominated bounce is outside the month and is not included in monthly P/L.',
        f"Study: `{s['study_id']}`. Fixed UTC window: `[{s['start']}, {s['end']})`, seven-day warmup, source SHA256 `{s['source_minute_sha256']}`.",
        'The research metric is full-sequence net P/L, closed-trade drawdown, turnover and explicit data quality, not whether one chosen bounce produces a profitable entry.','',
        '## Definition locked before monthly evaluation','']
    for k,v in s['rule'].items():lines.append(f'- **{k}**: {v}')
    lines += ['',
        'This is an operational draft, not proof of discretionary same-wave identity. The parent uses the lowest intact 15m D in fresh setup history, rather than replacing it with each higher internal low. Its independence uses existing P1 distances; original P1 source/selection and A rules are not modified. A later HL is a strict confirmed 15m turn. The separate 5m hold begins only after that HL is known. No upside velocity cutoff was fitted.',
        'The module implements the original economic entry arithmetic with a genuine 300-second adjacency check; no five-minute bar is relabeled as a fifteen-minute observation. All exits and stop-raising methods remain inherited from the original engines.',
        '', '## Bounce prefix test','',
        'Original A/B entries run from the original live-session start. PH5 entries are activated at November 14 18:00 EST, before the bottom, without assuming flat at a later desirable HL. Earlier PH5 crossings are consumed without opening positions. The source stops at November 15 05:16 EST; no finish() flush, later rally or hypothetical target fill is used. A strict entry-time prefix independently reproduces the candidate.',
        '', '| Reference | Occurrence / confirmation EST | Price |', '| --- | --- | ---: |']
    case=read(folder/'CASE.json')['models']['0.1']
    sig=next(x for x in case['signals'] if x['route']=='PH5')
    q=sig['setup_evidence']
    for k,label in [('parent','Parent D'),('rebound','Confirmed rebound'),('hl','Later 15m HL')]:
        p=q[k];lines.append(f"| {label} | {clock(p['time'])} / known {clock(p['known_at'])} | ${p['price']:,.4f} |")
    lines += [f"| Parent independence complete | {clock(q['parent']['independence_at'])} | — |",
        f"| Separate 5m holding bar | {clock(sig['hold_bar']['t'])}–{clock(sig['hold_bar']['t']+300)} | Low ${sig['hold_bar']['low']:,.4f}; high ${sig['hold_bar']['high']:,.4f} |",
        f"| Entry reference | {clock(sig['time_utc'])}; actual observation receipt {clock(sig['received_at'])} | ${sig['entry_reference']:,.4f} |",
        f"| Initial stop, effective after modeled entry | {clock(sig['time_utc'])} reference, not an executable live order | ${sig['initial_stop']:,.4f} |",
        f"| Planned first 25% target | Known at entry, never reached | ${sig['t1']:,.4f} |",'',
        '| Exit model | Reference exit / observation receipt EST | Fraction / reason | Price | Gross / cost / net |',
        '| --- | --- | --- | ---: | ---: |']
    for model in ('0.1','E1','E2'):
        c=read(folder/'CASE.json')['models'][model]
        p=next(p for p in c['trades'] if p['entry_rule']=='PH5')
        for leg in p['legs']:
            lines.append(f"| {model} | {clock(leg['time_utc'])} / {clock(leg['received_at'])} | {leg['fraction']:.0%} / {leg['reason']} | ${leg['price']:,.4f} | ${leg['gross']:,.2f} / ${leg['cost']:,.2f} / ${leg['net']:,.2f} |")
    lines += ['',
        'This definition does not catch the initial straight-up leg because no later confirmed 15m HL exists yet. It buys the first qualifying HL continuation at 23:47, but the unchanged failed-rebound exit closes 100% at 00:48 for -$135.66 per initial BTC; no 25% sale occurred. That entry consumes the old parent setup. At the later 03:20 rally the fresh $63,735 low is a new D rather than a later HL above the old $61,991 anchor, so no second PH5 entry occurs. Retaining that old D across an entry would be a different consumption rule, not silently added here.',
        '', '## Same-month full trade sequences','',
        'Each entry starts at 1 BTC. Original 2bps per side spread/slippage proxy; zero ETF commissions assumed, but these are BTC 24/7 signals, not executed ETF returns, actual crypto fees, compounded account returns or broker fills. No positions are retrospectively marked at the bounce peak. Open trades are not invented as closed. Drawdown is closed-trade cumulative R, not account minute-level mark-to-market.',
        '', '| Model | Sequence | Entries / W / L / open | Net USD | Delta vs original | Max drawdown R | PH5 entries / net |',
        '| --- | --- | --- | ---: | ---: | ---: | --- |']
    for m,modes in s['summaries'].items():
        base=modes['control']['all']['net']
        for mode,r in modes.items():
            a=r['all'];p=r.get('ph5_only',{}).get('all')
            lines.append(f"| {m} | {mode} | {a['entries']} / {a['wins']} / {a['losses']} / {a['open']} | ${a['net']:,.2f} | ${a['net']-base:,.2f} | {a['max_drawdown_r']:.2f} | "+(f"{p['entries']} / ${p['net']:,.2f}" if p else '—')+' |')
    lines += ['', '## Gap groups','',
        'No-flagged-gap = no holding-path gap and 14 complete adjacent entry-context bars. The flagged complement includes holding gaps or partial entry context. It does not prove all earlier resistance context is gap-free. Missing minutes remain absent and clear PH5 setup context; no interpolation or carry-forward.','',
        '| Model / sequence | No-flagged-gap net | Flagged complement net |','| --- | ---: | ---: |']
    for m,modes in s['summaries'].items():
        for mode,r in modes.items():lines.append(f"| {m} / {mode} | ${r['no_flagged_gap']['net']:,.2f} | ${r['gap_or_partial_context']['net']:,.2f} |")
    lines += ['', '## Sequence changes and outcome','']
    for m in ('0.1','E1','E2'):
        c=s['changes'][m]['combined'];_,_,r=PARENT_FIVE_VIEW.selection(m,'combined')
        ps=[p for p in r['trades'] if p['entry_rule']=='PH5']
        reasons=Counter(p['legs'][-1]['reason'] for p in ps if p['legs'])
        lines.append(f"- {m}: {len(c['added'])} added entries, {len(c['baseline_entries_not_taken'])} original entries not taken; {c['matched_entry_count']} matched original entry times/routes, {len(c['changed_same_entry'])} changed same-entry exits. PH5 has {len(ps)} entries and only {sum(any(l['reason']=='target_25' for l in p['legs']) for p in ps)} reach the first 25% sale. Final reasons: {dict(reasons)}.")
    lines += ['',
        'The additional candidate increases turnover and admits many losing continuations; all PH5-only and combined variants lose money, including the no-flagged-gap groups. Capturing an HL is not sufficient to improve the original system. This repeatedly studied month is in-sample, not independent validation. No threshold, target, exit, ATR weight or stop was changed after seeing results.',
        '', '## Review, exports and preservation','',
        'The page lists every trade, entry/initial-stop/planned-target, first-25% and remaining/full exits with prices and net P/L, separate source-quality groups, added/removed trades, every PH5 candidate including rejected/held, and chronological 15m and actual 5m entry observations. Download TRADES, EXITS, PROTECTION, SIGNALS and LEDGER CSVs or result JSON. Opening the page only reads saved data; POST is rejected.',
        f"Saved study: `{folder}`. Verified {s['preservation']['files']} protected files, original worker PID {s['preservation']['pid']} and session `{s['preservation']['session']}` unchanged. All 13 frozen source hashes match. Existing research selectors/results, P1, release bundles and original live data are preserved. Only the independent PH5 ACTIVE selector is written.",
        'Some observations are quote-derived with zero recorded venue volume. No claim of consolidated volume, depth, exact-second sequencing or achievable fill is made. A minute crossing both support and trigger is rejected as ambiguous. Broader historical feed gaps and crypto execution costs remain limitations.']
    text='\n'.join(lines)+'\n'
    (folder/'REPORT.md').write_text(text)
    target=ROOT/'docs/investigations/2026-11-15_BTC_PARENT_FIVE_COMPARISON.md'
    target.write_text(text)
    print(target)


if __name__=='__main__':run()
