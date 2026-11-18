"""Render the saved causal audit into readable report tables; no market IO."""
import html
import json
import statistics
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'reports/btc_bounce_audit_2026_11_15'
r=json.loads((FOLDER/'AUDIT.json').read_text())
NY=ZoneInfo('America/New_York')
def epoch(s):return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def stamp(t):
    if isinstance(t,str):t=epoch(t)
    return datetime.fromtimestamp(t,NY).strftime('%m/%d %H:%M:%S')
def hm(t):return stamp(t)[:11]
def price(x):return f'{x:,.2f}' if x is not None else '—'
def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in rows)
frames=r['results']['0.1']['frames']
bottom=epoch('2026-11-14T20:45:00-05:00');end=epoch('2026-11-15T04:15:00-05:00')
selected=[f for f in frames if bottom<=f['bar']['t']<end]
scans=[x for x in r['results']['0.1']['scans'] if bottom<=x['t']<=epoch('2026-11-15T04:12:00-05:00')]
assert len(scans)==448 and all(x['can_trade'] and not x['holding'] and not x['ready_routes'] for x in scans)
assert len(selected)==30 and all(f['bar']['observed_minutes']==15 for f in selected)
assert all(b['observed_minutes']==5 for b in r['five_minute_diagnostic'])
for model in ('E1','E2'):
    other=r['results'][model]['frames']
    assert [(x['bar'],x['gates'],x['max_A_low_count']) for x in frames]==[(x['bar'],x['gates'],x['max_A_low_count']) for x in other]
intro='''# BTC Bounce Entry Audit November 14 and 15

Causal A/B entry-gate diagnosis for the $61,991 to $66,085 recovery, with separate five-minute timing evidence.

Last Updated: 2026-11-15
Status: Read-only diagnostic; frozen 0.2 and original worker unchanged
Audience: Trading Desk owner and maintainers

## Overview

The frozen strategy did not admit a setup during this bounce. A never reached four independent LL phases; B had no active 2-ATR bearish new-low shock episode. A prior-candle high break alone cannot open a position. The missing trade is a strategy-coverage gap for this case, not a broker-hours block or a late high-break trigger.

All times below are New York EST. The $61,991.3285 low occurred November 14 at 20:45; the $66,085.424 high occurred November 15 at 04:12. This was two strong advances separated by a substantial pullback, not one uninterrupted vertical move.

## Exact reproduction and causal boundaries

The isolated replay read 18,258 actual persisted one-minute observations from the original warmup through November 15 05:16 EST. It reproduced all 20 entries and all 20 exit legs per model for 0.1/E1/E2 through that cutoff. It did not call finish(), run a month, fetch prices, write to the live database, change strategy source, or restart a worker. One earlier prefix gap remains absent; every 15m candle shown here has 15 observed minutes and every 5m diagnostic candle has five.

During the low-to-peak interval all 448 observed minutes were flat/available for model entry. In 138 minutes price exceeded the preceding complete 15m candle high plus $0.01. These are crossing minutes, not 138 independent trade opportunities. No A/B route reached the downstream entry screen. Chase, target availability, costs and 2R therefore were not the reason these entries were blocked; 2R remains advisory.

A candle's after-close state cannot be used at its opening. The tables distinguish the state entering the candle from its after-close count. The worker completes a 15m aggregate on processing the next observed minute, usually about another minute after the nominal close; the JSON retains exact receipt times.

## Why A failed

The prior B1 trade #20 entered at the November 14 18:19 reference minute, detected 18:20:13. Its entry consumed prior A/B setup history. Only fresh complete candles from 18:30 could rebuild an entry. This reset happens at entry, not at the later 19:29 exit. Reusing earlier lower lows would contradict the frozen consumed-history rule.

The decline to $61,991 was mostly continuous: several successively lower candles were extensions of one phase, not four independently rebounding wave lows. The bottom's 20:45 candle became the first independent LL only after the 21:00–21:15 right-hand candle completed; the worker knew this at 21:16:04.

The rebound also broke above the old $64,543.885 decline origin. When the $65,553.438 peak in the 22:00 candle became confirmed by the 22:15–22:30 right-hand candle (worker receipt 22:31:01), that older declining A scope was removed. This is why the $61,991 parent D did not carry forward as an A continuation anchor.

The subsequent wider decline had only these three independent lows, confirmed at 23:30, 01:30 and 03:15 respectively: $64,620.60 at 23:09; $64,137.90 at 01:10; $63,735.105 at 02:51. Intermediate rebound peaks were lower highs. The final 03:00 confirmation reached the worker at 03:16:05. At the next upside break A still had three, not four, lows. Price itself did make higher highs; the A validator deliberately does not arm its own HH/HL stage until four LLs are established.

The larger chart sequence $61,991 → $65,553 → $63,735 → $66,085 is reasonably read as a parent-wave HL continuation. That is a different structure from the frozen four-LL reversal. The separate parent-wave continuation research was not promoted into this live worker.

## Why B1 and B2 failed

B requires one complete red 15m candle making a new scope low with max(open, previous close) minus low at least twice the ATR known before that candle. It does not accumulate several moderate red candles into one shock. Recent volatility had already elevated ATR. The decisive examples are:
'''
shock_rows=[]
for f in frames:
    if hm(f['bar']['t']) in ('11/14 20:00','11/14 20:15','11/14 20:30','11/14 20:45','11/15 02:30'):
        b,g=f['bar'],f['gates']
        shock_rows.append([hm(b['t']), 'red' if g['bearish'] else 'green',price(g['down_points']),price(b['atr_before']),price(g['threshold_2atr']),f"{g['down_atr']:.3f}×",'No: green candle' if not g['bearish'] else 'No: below 2×ATR'])
shock_table=table(['15m candle start','Direction','Downward excursion','Prior ATR','Required 2×ATR','Actual multiple','New B episode'],shock_rows)
paragraph='''

The 20:45 bottom candle closed green, so it could not originate a bearish shock. The 02:30 second-leg decline was red and made a fresh scope low, but reached only 1.738×ATR. No shock chain was seeded. B1 could not use a stabilization/high-break without that chain; B2 could not attach the later rebound and HL to a nonexistent valid shock episode. Rebound speed does not override either prerequisite.

## Every completed 15m candle through the recovery peak

A count is the maximum across all eligible declining scopes, not just the selected internal scope. Every row had no ready A/B route while it was being processed. The B column describes whether the completed candle could seed a new episode; it is not a claim that its final values were known intrabar.

'''
rows=[]
for f in selected:
    b,g=f['bar'],f['gates'];first=f['during_bar']['first_scan'];count=first['max_A_low_count'] if first else '—'
    why='green' if not g['bearish'] else 'no new scope low' if not g['fresh_scope_low'] else f"{g['down_atr']:.3f}×ATR < 2"
    rows.append([hm(b['t']),price(b['low']),price(b['high']),price(b['close']),f"{count} → {f['max_A_low_count']}",why,stamp(f['available_to_worker'])])
all_table=table(['15m candle start EST','Low','High','Close','A LL open → after close','B episode failed because','After-close state received EST'],rows)
five_intro='''

B2 was unavailable in every row because there was no valid B shock chain. A had no armed qualifying four-LL → HH → HL sequence. The first previous-15m-high crossing occurred at 20:58; the worker received that complete minute at 20:59:07, yet no route was ready.

## Five-minute timing and velocity diagnostic

Five-minute OHLC is aggregated only from real contiguous observed minutes. This is not the frozen 15m model rerun under new labels. A high break is a price observation, not a qualified A/B entry or a retrospective fill.

- **20:50:** price first crossed the completed 20:45–20:50 five-minute high of $62,327.46. That minute arrived at 20:51:09. This was earlier but more aggressive: no separate full post-D holding bar had completed yet.
- **20:58:** after the separate 20:50–20:55 five-minute candle held above D, price crossed its $62,557.72 high. That minute arrived at 20:59:07. The frozen 15m previous-high threshold ($62,650.22) was also crossed in that same minute. A/B setup eligibility, not trigger speed, was the blocker.
- **03:20:** price crossed the preceding five-minute high $63,948.505; received 03:21:14. The preceding 15m high $64,127.0925 was crossed at 03:21; received 03:22:00. Five-minute timing was approximately one minute earlier, while A still had only three lows and B still had no shock.
- **04:00:** both preceding 5m and 15m highs were $65,211.988. Both were crossed in the same observed minute; shortening the trigger timeframe added no lead here.

Use percentage change per minute or ATR-normalized speed rather than a visual 45°/85° angle, which changes with chart scaling. The following whole-bar measures become available only after the five-minute candle ends, not at its opening. The prior-hour comparison is descriptive, not a fitted trigger:

'''
velocity=[]
for b in r['five_minute_diagnostic']:
    if hm(b['t']) in ('11/14 21:05','11/15 03:20','11/15 04:00'):
        baseline=statistics.median(abs(x['pct_per_minute']) for x in r['five_minute_diagnostic'] if x.get('complete') and b['t']-3600<=x['t']<b['t'])
        velocity.append([hm(b['t']),f"{b['change_pct']:.3f}%",f"{b['pct_per_minute']:.3f}%",f"{b['atr_per_minute']:.3f}",f"{b['pct_per_minute']/baseline:.1f}×",stamp(b['source_data_available_at'])])
velocity_table=table(['5m candle start EST','Open-to-close gain','Gain per minute','Prior 15m ATR per minute','Vs prior hour median absolute speed','Whole 5m data received EST'],velocity)
ending='''

Some breakout minutes were quote-derived with zero recorded venue volume, including the 03:21 15m breakout minute. This feed cannot establish consolidated buying volume, depth, an IBIT price, or an achievable fill. Full five-minute bars and first-cross receipts are retained in AUDIT.json.

## Interpretation and next comparison

This case supports studying a separate fast-recovery/parent-HL entry family. Five minutes can help locate a local hold and trigger, but merely shortening the clock leaves the frozen four-low/shock requirements unresolved. A potential comparison should retain the parent-wave context and structural stop, use five-minute stabilization/high-break evidence as a trigger, and measure speed causally in percent/ATR terms. It must then be tested against failed bounces and normal pullbacks, not selected on this successful bounce alone. No new speed cutoff, entry rule, stop, target or parameter is adopted here, and no hypothetical profit is credited.

The worker remains on its original PID/session with all 13 frozen source hashes, worker scripts, control/session and launch registration unchanged. Detailed original inputs, model reproduction, every after-close scope, every minute's gate state and receipt timestamps are in the adjacent AUDIT.json; PRESERVATION.json records the checks.
'''
text=intro+shock_table+paragraph+all_table+five_intro+velocity_table+ending
(FOLDER/'AUDIT.md').write_text(text)
(ROOT/'docs/investigations/2026-11-15_BTC_BOUNCE_ENTRY_AUDIT.md').write_text(text)
# A text/table report, not an image or synthetic chart. Tables remain readable
# with horizontal scrolling on narrow screens and no fixed screenshot crop.
blocks=[]
lines=text.splitlines();i=0
while i<len(lines):
    line=lines[i]
    if line.startswith('| '):
        tablelines=[]
        while i<len(lines) and lines[i].startswith('| '):tablelines.append(lines[i]);i+=1
        cells=lambda row:[html.escape(c.strip()) for c in row.strip('|').split('|')]
        blocks.append('<div class="scroll"><table><thead><tr>'+''.join('<th>'+c+'</th>' for c in cells(tablelines[0]))+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in cells(row))+'</tr>' for row in tablelines[2:])+'</tbody></table></div>');continue
    if line.startswith('# '):blocks.append('<h1>'+html.escape(line[2:])+'</h1>')
    elif line.startswith('## '):blocks.append('<h2>'+html.escape(line[3:])+'</h2>')
    elif line:blocks.append('<p>'+html.escape(line)+'</p>')
    i+=1
page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BTC bounce entry audit</title><style>body{font:16px/1.55 system-ui;background:#101722;color:#e1e8ef;margin:0}main{max-width:1350px;margin:auto;padding:28px}p{max-width:105ch}h1,h2{color:#8edbc8}h2{margin-top:38px}.scroll{overflow:auto;border:1px solid #34465a;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid #2c3c4d;padding:10px;text-align:left;white-space:nowrap}th{background:#223044}tr:nth-child(even){background:#162231}</style><main>'+''.join(blocks)+'</main></html>'
(FOLDER/'AUDIT.html').write_text(page)
print(str(FOLDER/'AUDIT.html'));print('All 30 bottom-to-peak 15m candles and exact availability states included.')
