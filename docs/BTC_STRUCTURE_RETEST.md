# BTC Structure Retest — November 8, 2026

A dated, read-only test of a mechanical interpretation of the trading learning manual.

**Last Updated:** 2026-11-08

**Status:** V1.2 research update; important-swing model has entries but negative in-sample results

**Audience:** Trading Desk owner and research maintainers

## Overview

### Current update: V1.2 major hourly resistance

On the owner's follow-up, the November 8 workbook now compares important swing
resistance with the original all-minor-highs definition. **The previous V1.1
results below are historical**. Its original source, results and archived XLSX
remain intact; the primary workbook has been updated and includes model trade
legs. No current quotes were refreshed and no real orders were requested.

The audit found that the original 114 candidates had a median planned target
distance of only **0.0322 fifteen-minute ATR**; **48/114** had T1 at or below
the signal-close reference. The original algorithm treated very small local
fluctuations as barriers, even when their target buffer erased the available
price space. This explains why zero entries alone was insufficient to judge
the discretionary learning method.

Before the new replay, one fixed definition was selected, without a parameter
search: aggregate only four contiguous real fifteen-minute observations into
each UTC-aligned completed hour; a major high must exceed each of its two
neighboring completed hours on both sides. Both its preceding rise and following
decline must be at least **one hourly ATR(14)** measured at the peak. This ATR is
also a simple true-range average. A peak is therefore usable only at the close
of the second right-hand hour, **three hours after the peak hour starts**.

Each qualified peak defines a zone of peak price **plus/minus 0.15 hourly ATR**.
Overlapping zones merge. Use the closest zone's **lower edge**, less the same
0.10 fifteen-minute ATR target buffer as before. A zone containing entry is
not skipped; its unfavorable price space rejects the candidate. A zone wholly
below entry no longer blocks the current upward path. If no eligible zone is
known, reject rather than invent a target. The local H1 alone is no longer a
resistance unless represented by the important hourly structure. This is the
requested change in resistance hierarchy, not a claim that minor levels never
matter.

General support/resistance interpretation is discussed by
[Fidelity's Trading Strategy Desk](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/support-and-resistance).
The precise two-hour, one-ATR and zone-width parameters here are our research
choices, not Fidelity recommendations or empirically established optima.
All other entry, stop, expiration, minimum 2R, friction and 50% exit rules
remain unchanged. No additional trend filter was introduced.

| Same 30-day data / fixed 2bps each way | V1.1 minor highs | V1.2 important swings |
| --- | ---: | ---: |
| Completed test bars | 2,880 | 2,880 |
| Original candidates compared independently of holdings | 114 | 114 |
| Price screen passes | 0 | 14 |
| Model entries, one position at a time | 0 | 10 |
| Closed model trades | 0 | 10 |
| Winning / losing trades | Not applicable | 1 / 9 |
| Total closed result | Not applicable | **-6.7190R** |
| Win rate | Not applicable | **10.0%** |
| Close-marked maximum drawdown | Not applicable | **7.1656R** |

Four of the fourteen independent price-screen passes happened while a model
position was already open, so they are not four additional executable trades.
The full execution path evaluated 103 candidates; its different count reflects
position occupancy and suppressed overlapping setups. The 114-signal comparison
keeps the original signal times, closes, stops and ATR fixed to isolate the
effect of the resistance definition.

| Friction assumed each way | Same-signal passes | Closed model trades | Closed result |
| --- | ---: | ---: | ---: |
| 0bps | 18 | 13 | -9.4499R |
| 2bps | 14 | 10 | -6.7190R |
| 5bps | 9 | 7 | -4.0542R |

Different cost settings change which trades qualify; the smaller loss at a
higher cost is not evidence that worse execution helps a fixed set of trades.
1R is each trade's own initial planned risk, including modeled costs. These
totals are normalized model results, not dollar P&L, compounded portfolio
returns or actual ETF results. Prices are observed bars; fills are explicitly
estimated using the existing adverse-first OHLC conventions.

For example, the **October 11, 12:00 EDT** signal closed at $83,818.50 with the
same $82,985.56 planned stop in both definitions. V1.1 selected a tiny nearby
high at $83,914.54 and T1 at $83,902.65, giving about **0.058R** of planned net
reward/risk. V1.2's already-confirmed important zone started at $85,691.50;
T1 was $85,679.61, giving about **2.109R**. The model entered at the next real
bar's $83,818.51 open, but ultimately stopped out for **-1R**. This concrete
case shows both the overly restrictive old target and the fact that extra
theoretical room does not ensure a profitable trade.

The one profitable trade, entered October 30 at 18:45 EDT, sold half at its
modeled first target and exited the remaining half at raised structural
protection, producing about **+2.281R** overall. The other nine lost about 1R
each. It would be inaccurate to treat a protective-stop exit label on the
winning trade as a full-position loss, or to count its two exit legs as two
winning trades.

**Interpretation:** the resistance definition was too granular, but this single
revision does not establish an edge. The downtrend/反弹 context and the existing
fifteen-minute stop structure remain potential issues for later review. This
month was used to detect a problem and revise the specification; these new
results are **in-sample**, not independent validation. Do not adjust further
parameters on this month simply to improve its P&L.

New artifacts are under `reports/btc_structure_2026_11_08/major_resistance/`:
`MAJOR_RETEST.json`, the same-signal `COMPARISON.csv`, execution `CANDIDATES.csv`,
`TRADES.csv`, `FILLS.csv`, and `LEDGER.csv`. Every selected zone records its
constituent peak times, earliest known times, hourly ATR and prominence.
`BTC_30_DAY_RETEST_V1_1.xlsx` archives the original workbook. The updated primary
workbook preserves original R1/T1/RR in candidate columns R–T, adds important
zone evidence in U–W and a model-trades sheet with all eleven exit legs.
The previous current-chart audit and original bars remain unchanged snapshots.

To reproduce the revision using the archived source, without new API requests:

```bash
python3 scripts/retest_btc_major_resistance.py
python3 -m pytest trading_desk/tests/test_btc_structure_retest.py -q
node scripts/update_btc_major_workbook.mjs
```

The update builder imports the archived V1.1 workbook and changes the affected
summary, candidates and parameters; it adds the necessary transaction detail.
Editable candidate cost/2R inputs only recalculate the independent price screen.
The model trade ledger and cost-case results remain fixed to their saved replay
settings, requiring a new replay for changes. Eleven focused tests cover causal
hour aggregation, confirmation timing, fixed signal comparison, real-source
crosschecks, trade-leg reconciliation and prefix independence. Workbook formulas
are checked against the model and unchanged raw/current views are compared
with the original import.

## Original V1.1 study (preserved)

The owner requested a current Chrome BTCUSD 15-minute review and a 30-day
spreadsheet, then explicitly selected **BTC signals around the clock**, rather
than limiting research to US ETF hours. This supports the desk's existing North
Star of sourced, explicit trading decisions. No broker credentials or order
endpoints are used.

The [learning manual](TRADING_LEARNING_MANUAL.md) is partly discretionary.
This **V1.1 research version** quantifies previously unset parameters below;
it is not a claim that the manual was already a complete mechanical strategy.
In particular, this first interpretation treats every confirmed local high as
potential resistance without discretionary importance ranking. It does not
implement a one-hour trend filter or the optional ATR-acceleration exit branch.

## Result and files

- Test interval: **2026-10-09 16:00 UTC to 2026-11-08 16:00 UTC**, exclusive end.
  New York starts October 9 at 12:00 EDT and ends November 8 at 11:00 EST.
- **2,880/2,880 complete test bars**, plus **672** preceding warmup bars.
- No missing 15-minute observations in either interval. No interpolation,
  carry-forward or invented prices were used.
- **114 completed local-breakout candidates**; **zero** passed the 2.0 minimum
  net reward/risk screen. No model position opened.
- With zero, 2 and 5 basis points of assumed friction **per side**, the highest
  candidate ratios were approximately **1.0545, 0.9936 and 0.9088** respectively.
  These are planned price-space ratios, not realized returns.
- Win rate, profitability, stop execution and the 50% exit method **cannot be
  evaluated**, because there were no entries. Zero entries is not a 0% win rate.

The results show that this particular unranked resistance definition may be
too restrictive. Do not optimize it on this month merely to create trades.
Review resistance selection against the original chart discussion, record any
revision separately and test on a new or forward interval.

Artifacts under [`reports/btc_structure_2026_11_08/`](../reports/btc_structure_2026_11_08/):

- [Spreadsheet](../reports/btc_structure_2026_11_08/BTC_30_DAY_RETEST.xlsx):
  summary, all candidates, current per-candle audit, parameters and raw bars.
- `RETEST.json`: configuration, request provenance, all candidates and full
  per-bar decisions for each of the three fixed cost cases.
- `BTCUSD_15M.csv`, `CANDIDATES.csv`, `LEDGER.csv`: auditable source and results.
- `raw/*.json`: exact public API responses, named by requested UTC bounds;
  request URLs and SHA-256 hashes are recorded in `RETEST.json`.
- `CURRENT_SNAPSHOT.json` and `current_raw/`: a separate latest-chart check,
  completed through 11:15 EST and inspected in Chrome around 11:25. This does
  not extend or change the frozen 30-day interval ending at 11:00.
- `TRADES.csv` and `FILLS.csv` are empty because no trades occurred. Their
  absence of data must not be replaced with placeholder trades.

The workbook is a **saved snapshot**, not a live market monitor. Its cost and
minimum-RR inputs recalculate the candidate screen. Structural parameter or
market-data changes require rerunning the research and rebuilding the workbook;
changing an input does not silently create new historical trades.

## Mechanical rule specification

No parameter search was performed. Values below are initial research choices,
not previously user-approved optimal settings.

| Item | Fixed interpretation |
| --- | --- |
| Timeframe | Completed Coinbase BTC-USD 15-minute bars, 24/7 |
| Pivot | Strictly lower/higher than one bar on each side; usable only after the right-hand bar closes |
| L1 | Most recent previously confirmed local low |
| H1 | Highest observed high strictly between L1 and the new L2 |
| L2 | New confirmed low greater than L1 by more than 0.10 ATR |
| Confirmation candle | The completed right-hand candle that confirms L2 |
| Trigger | A later complete candle closes above that confirmation candle's full high, including its wick |
| Expiry | Up to eight subsequent bars; crossing L2 invalidates the setup |
| Volatility | Simple mean of 14 completed true ranges; not Wilder ATR |
| Stop | L2 minus 0.25 signal-time ATR |
| Resistance | Nearest already-confirmed 15-minute pivot high above signal close, from the prior seven days, also considering H1 |
| First target | Resistance minus 0.10 signal-time ATR |
| Second target | Next distinct known pivot resistance minus the same buffer, if available; otherwise leave unavailable |
| Minimum ratio | Net potential reward / planned risk >=2.0 |
| Friction | Fixed separate runs at 0, 2 and 5 bps each way; zero commission. Not observed bid/ask data or Coinbase spot fees |
| Entry limit | Lower of signal close +0.10 ATR and the highest price still satisfying the minimum ratio |
| Entry model | Only the immediately following real bar's open may fill, if inside the cap and between stop and T1; otherwise skip |
| First sale | Model 50% of initial position at T1 after strict trade-through; touching alone is insufficient |
| Remaining sale | T2 if known, structural protection, or completed resistance-failure upper wick >=50% of full range and close below resistance |
| Trailing protection | After T1, a newly confirmed higher structural low minus 0.25 ATR; protection can only rise, effective next bar |
| Close-based exit | Earliest next real bar open after full confirmation, never at the wick high |
| Ambiguous intrabar path | Stop first when both stop and target occur; worse opening gaps respected, favorable target gaps receive no improvement |
| Missing history | Never pad; reset setup/ATR context. If a position spans a missing interval, mark unresolved and stop evaluating its outcome |

For price E, stop S, target T and per-side friction fraction q:

`net reward = T - E - q(E + T)`

`planned risk = E - S + q(E + S)`

For minimum multiple m, the highest admissible price is:

`Emax = (1-q)(T + mS) / ((1+q)(1+m))`

These are screening assumptions. Next-bar opens, limit trade-throughs and stop
prices are explicitly **model execution conventions**, not broker-confirmed
fills. OHLC cannot establish queue priority, latency or precise intrabar order.
R-normalized results, if any in a later run, would not by themselves establish a
funded, leverage-constrained portfolio return. This run has no such results.

## Current Chrome review and price references

Chrome inspection at approximately **11:12 EST on November 8** showed the
Coinbase BTCUSD 15-minute chart around $75,950. The last completed candle was
**10:45–11:00 EST**, O $75,978.36, H $75,980.47, L $75,951.58,
C **$75,966.27**. Public Coinbase data independently agreed on that completed
candle. It closed below the previous candle's **$75,996.29** high. The
11:00–11:15 candle was incomplete at inspection, so no completed signal is
claimed from its then-current high or low.

**No qualifying entry.** Previously discussed structural and teaching references:

| Reference | Value and earliest availability | Meaning |
| --- | --- | --- |
| Prior full high | $75,996.29; 10:45 EST onward | Nearby obstacle; breaking it alone does not establish a qualified trade |
| Last completed high | $75,980.47; 11:00 EST onward | Later candle comparisons may use it, but full setup still required |
| Earlier structural low | $75,891.50 from 10:15–10:30; 10:30 onward | Possible invalidation reference; not a newly qualified setup |
| Stop illustration | $75,868.95 using that low minus 0.25 of the 11:00 ATR, about $90.1871 | Arithmetic only, no submitted stop; future setups use their own L2 and ATR |
| First target illustration | $75,990, before the old $76,000 teaching resistance | Retained classroom target, not automatically recalculated resistance |
| Remaining 50% | Next credible resistance or confirmed structural protection | No new numeric target invented; no actual position in this exercise |

Using the 11:00 signal-close reference and the illustrated stop/T1 yields only
about 0.24 gross reward/risk; at the assumed 2 bps each way, net reward is
negative (about -0.052 net reward/risk). Even the favorable zero-buffer,
zero-friction bound is only about 0.32. This is not a buy setup.

The initial workbook review listed **every completed bar from 08:00–11:00 EST**. It retains
the three earlier rejected reference checks at 09:15, 09:45 and 10:45 and the
conditional **08:30** upper-wick exit case. Those manual classroom checks use
the old $76,000/$75,990 references; they are separate from V1.1's algorithmic
resistance screen and must not be merged into simulated fills.

### Latest refresh at 11:25 EST

The now-completed **11:00–11:15** bar is O **$75,966.54**, H **$75,998.00**,
L **$75,918.51**, C **$75,926.65**. Chrome and the public API agree on these
values. Although it traded above the preceding bar's $75,980.47 high, it closed
back below it. **No confirmed breakout entry.** The 11:15–11:30 candle was
still incomplete at this refresh.

The new $75,918.51 low is only a candidate L2. If the following full candle
holds above it, its right-side pivot confirmation would first be available
**at 11:30**. A subsequent full 15-minute close above the confirmation candle's
complete high could first be evaluated **at 11:45**, conditional on that actual
structure occurring. These times are possible future confirmation times, not
predictions of a signal or promises to buy.

For comparison only, retaining the earlier $75,891.50 low and using the latest
ATR of approximately $90.4679 gives an illustrated buffered stop of about
**$75,868.88**. At the new $75,926.65 close and the old $75,990 classroom target,
gross reward/risk is about 1.10 and net is about **0.37** under the assumed 2bps
each way; even no buffer and no friction gives only about **1.80**. None reaches
2.0. A future actual setup must use its own confirmed L2, contemporaneous ATR,
closest credible resistance and executable quote. The $75,990 example is not a
new live target or a recommended standing order.

The workbook includes this additional bar as the thirteenth completed current
review row, through **11:15**. Its raw thirty-day data and screening totals
remain frozen through 11:00 so the sample definition is not changed mid-report.

## Reproduce and verify

From the repository root:

```bash
python3 scripts/btc_structure_retest.py --as-of 2026-11-08T16:00:00Z --days 30 --output reports/btc_structure_2026_11_08
python3 -m pytest trading_desk/tests/test_btc_structure_retest.py -q
node scripts/build_btc_retest_workbook.mjs
```

The workbook builder uses the bundled `@oai/artifact-tool` runtime and currently
locates it through the configured local Codex dependency bundle. It recalculates
candidate ratios, independently compares each with Python output, tests a cost
input change and restores it, scans formula errors, renders all five sheets and
exports one XLSX. No dependency folders are modified. Render images stay in the
local output folder and are not market data.

The eight focused regression tests passed. Workbook formulas, export and all
five sheet previews were checked. A full Sphinx HTML build was unavailable
because Sphinx is not installed in either local Python runtime; the source
documentation and index link were checked directly.

Regression checks use archived **real Coinbase observations**, covering source
completeness, formula ceilings, prefix causality, omission without padding,
November 1 DST ambiguity and the absence of invented trades. Core exit ordering
is also checked against an actual observed candle and explicitly hypothetical
order levels; that unit check is not an empirical exit-performance result.

Source handling follows [Coinbase's candle documentation](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles):
the response order is timestamp, low, high, open, close, volume; each request
stays below the 300-candle limit. Responses are filtered to half-open requested
intervals. Missing source candles remain missing. Observe that no data is
published for intervals without ticks, so completeness is checked explicitly.

This is BTC **signal research**, not Coinbase spot-investment performance or
ETF realized return. A future ETF test needs its own quotes, session handling,
price mapping, spread and slippage. Zero ETF commission does not remove those
costs or make the Sunday BTC bars executable in an ETF.
