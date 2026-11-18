# BTC 15-Minute Parent HL and Five-Minute Trigger Comparison

Separate locked PH5 definition, nominated bounce first, then the unchanged frozen-source month.

Last Updated: 2026-11-15  
Status: Complete; all experimental variants lose money; not promoted  
Audience: Trading Desk owner and maintainers

## Overview

Open `/btc-parent-five`. The experiment reproduces the three original controls exactly, then tests PH5 alone and A/B + PH5 as separate complete position sequences. Frozen 0.2, P1 and the original live worker are unchanged. The nominated bounce is outside the month and is not included in monthly P/L.
Study: `20261115T172851Z-PH5`. Fixed UTC window: `[2026-10-10T00:00:00Z, 2026-11-09T00:00:00Z)`, seven-day warmup, source SHA256 `6676741b2e47d6fd45e5bde450f8e308eb4546df830a54e281412a1e1fdfc05b`.
The research metric is full-sequence net P/L, closed-trade drawdown, turnover and explicit data quality, not whether one chosen bounce produces a profitable entry.

## Definition locked before monthly evaluation

- **name**: PH5_15M_PARENT_HL_5M_HOLD_BREAK
- **version**: research-1
- **parent**: Lowest intact strict 3-candle 15m D in fresh setup history; outside turns excluded. Higher internal lows never replace D.
- **independence**: Two consecutive complete post-D 15m bars strictly above D, rebound high >= D + 1 prior-D ATR, best close >= D + 0.5 prior-D ATR (existing P1 distances, no A/P1 modification).
- **rebound**: Highest confirmed strict 15m peak after D and before the latest confirmed 15m HL; must exceed D by 1 prior-D ATR.
- **hl**: Latest strict 3-candle 15m low after rebound, above D + 0.1 entry ATR, intact at trigger.
- **hold**: One separate complete contiguous 5m bar starting at/after 15m HL confirmation; its low strictly exceeds HL.
- **trigger**: Intraminute high above immediately preceding complete 5m high + $0.01; original 0.1 entry-ATR chase ceiling.
- **stop**: Larger 15m parent D minus original 0.25 entry ATR; exits remain 15m/1h original models.
- **consumption**: First crossing consumes each D/HL episode, including held/warmup/rejected crossings. Every entry clears parent setup history; only full 15m candles after entry may rebuild it.
- **gaps**: Clear all PH5 context and 5m hold on a missing minute; never fill gaps.
- **priority**: Original A/B first in combined sequence; one position, no reentry on exit minute.
- **atr**: 14 completed 15m true ranges; no 5m rescaling of risk or exits.
- **speed**: Descriptive only; no fitted acceleration cutoff.
- **orders_enabled**: False
- **live_promoted**: False

This is an operational draft, not proof of discretionary same-wave identity. The parent uses the lowest intact 15m D in fresh setup history, rather than replacing it with each higher internal low. Its independence uses existing P1 distances; original P1 source/selection and A rules are not modified. A later HL is a strict confirmed 15m turn. The separate 5m hold begins only after that HL is known. No upside velocity cutoff was fitted.
The module implements the original economic entry arithmetic with a genuine 300-second adjacency check; no five-minute bar is relabeled as a fifteen-minute observation. All exits and stop-raising methods remain inherited from the original engines.

## Bounce prefix test

Original A/B entries run from the original live-session start. PH5 entries are activated at November 14 18:00 EST, before the bottom, without assuming flat at a later desirable HL. Earlier PH5 crossings are consumed without opening positions. The source stops at November 15 05:16 EST; no finish() flush, later rally or hypothetical target fill is used. A strict entry-time prefix independently reproduces the candidate.

| Reference | Occurrence / confirmation EST | Price |
| --- | --- | ---: |
| Parent D | 11/14 20:45:00 EST / known 11/14 21:15:00 EST | $61,991.3285 |
| Confirmed rebound | 11/14 22:03:00 EST / known 11/14 22:30:00 EST | $65,553.4380 |
| Later 15m HL | 11/14 23:09:00 EST / known 11/14 23:30:00 EST | $64,620.6000 |
| Parent independence complete | 11/14 21:30:00 EST | — |
| Separate 5m holding bar | 11/14 23:40:00 EST–11/14 23:45:00 EST | Low $64,730.5750; high $64,826.6000 |
| Entry reference | 11/14 23:47:00 EST; actual observation receipt 11/14 23:48:01 EST | $64,826.6100 |
| Initial stop, effective after modeled entry | 11/14 23:47:00 EST reference, not an executable live order | $61,846.5658 |
| Planned first 25% target | Known at entry, never reached | $69,951.9321 |

| Exit model | Reference exit / observation receipt EST | Fraction / reason | Price | Gross / cost / net |
| --- | --- | --- | ---: | ---: |
| 0.1 | 11/15 00:48:00 EST / 11/15 00:49:10 EST | 100% / failed_rebound_exit_remaining | $64,716.8550 | $-109.75 / $25.91 / $-135.66 |
| E1 | 11/15 00:48:00 EST / 11/15 00:49:10 EST | 100% / failed_rebound_exit_remaining | $64,716.8550 | $-109.75 / $25.91 / $-135.66 |
| E2 | 11/15 00:48:00 EST / 11/15 00:49:10 EST | 100% / failed_rebound_exit_remaining | $64,716.8550 | $-109.75 / $25.91 / $-135.66 |

This definition does not catch the initial straight-up leg because no later confirmed 15m HL exists yet. It buys the first qualifying HL continuation at 23:47, but the unchanged failed-rebound exit closes 100% at 00:48 for -$135.66 per initial BTC; no 25% sale occurred. That entry consumes the old parent setup. At the later 03:20 rally the fresh $63,735 low is a new D rather than a later HL above the old $61,991 anchor, so no second PH5 entry occurs. Retaining that old D across an entry would be a different consumption rule, not silently added here.

## Same-month full trade sequences

Each entry starts at 1 BTC. Original 2bps per side spread/slippage proxy; zero ETF commissions assumed, but these are BTC 24/7 signals, not executed ETF returns, actual crypto fees, compounded account returns or broker fills. No positions are retrospectively marked at the bounce peak. Open trades are not invented as closed. Drawdown is closed-trade cumulative R, not account minute-level mark-to-market.

| Model | Sequence | Entries / W / L / open | Net USD | Delta vs original | Max drawdown R | PH5 entries / net |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 0.1 | control | 38 / 19 / 19 / 0 | $3,516.46 | $0.00 | 3.18 | — |
| 0.1 | standalone | 87 / 34 / 53 / 0 | $-7,265.22 | $-10,781.67 | 12.49 | 87 / $-7,265.22 |
| 0.1 | combined | 109 / 47 / 62 / 0 | $-2,295.15 | $-5,811.61 | 12.14 | 71 / $-5,706.26 |
| E1 | control | 38 / 19 / 19 / 0 | $4,159.67 | $0.00 | 2.98 | — |
| E1 | standalone | 92 / 31 / 61 / 0 | $-5,433.06 | $-9,592.72 | 10.49 | 92 / $-5,433.06 |
| E1 | combined | 115 / 44 / 71 / 0 | $-1,357.93 | $-5,517.60 | 10.78 | 76 / $-5,306.35 |
| E2 | control | 38 / 19 / 19 / 0 | $4,195.15 | $0.00 | 2.64 | — |
| E2 | standalone | 89 / 33 / 56 / 0 | $-7,571.13 | $-11,766.27 | 13.17 | 89 / $-7,571.13 |
| E2 | combined | 113 / 46 / 67 / 0 | $-2,432.97 | $-6,628.11 | 12.38 | 75 / $-6,522.76 |

## Gap groups

No-flagged-gap = no holding-path gap and 14 complete adjacent entry-context bars. The flagged complement includes holding gaps or partial entry context. It does not prove all earlier resistance context is gap-free. Missing minutes remain absent and clear PH5 setup context; no interpolation or carry-forward.

| Model / sequence | No-flagged-gap net | Flagged complement net |
| --- | ---: | ---: |
| 0.1 / control | $2,751.29 | $765.17 |
| 0.1 / standalone | $-7,758.67 | $493.45 |
| 0.1 / combined | $-3,553.77 | $1,258.62 |
| E1 / control | $2,998.96 | $1,160.71 |
| E1 / standalone | $-5,596.63 | $163.57 |
| E1 / combined | $-2,682.21 | $1,324.28 |
| E2 / control | $3,034.44 | $1,160.71 |
| E2 / standalone | $-8,064.58 | $493.45 |
| E2 / combined | $-3,717.14 | $1,284.17 |

## Sequence changes and outcome

- 0.1: 72 added entries, 1 original entries not taken; 37 matched original entry times/routes, 0 changed same-entry exits. PH5 has 71 entries and only 8 reach the first 25% sale. Final reasons: {'stop': 13, 'failed_rebound_exit_remaining': 17, 'structure_exit_remaining': 18, 'giveback_exit_remaining': 7, 'turning_exit_remaining': 10, 'wick_exit_all': 6}.
- E1: 77 added entries, 0 original entries not taken; 38 matched original entry times/routes, 0 changed same-entry exits. PH5 has 76 entries and only 7 reach the first 25% sale. Final reasons: {'e1_exit_remaining': 22, 'stop': 8, 'turning_exit_remaining': 10, 'structure_exit_remaining': 15, 'giveback_exit_remaining': 6, 'failed_rebound_exit_remaining': 8, 'wick_exit_all': 7}.
- E2: 76 added entries, 1 original entries not taken; 37 matched original entry times/routes, 0 changed same-entry exits. PH5 has 75 entries and only 8 reach the first 25% sale. Final reasons: {'stop': 14, 'e2_exit_remaining': 4, 'turning_exit_remaining': 11, 'structure_exit_remaining': 17, 'giveback_exit_remaining': 7, 'failed_rebound_exit_remaining': 16, 'wick_exit_all': 6}.

The additional candidate increases turnover and admits many losing continuations; all PH5-only and combined variants lose money, including the no-flagged-gap groups. Capturing an HL is not sufficient to improve the original system. This repeatedly studied month is in-sample, not independent validation. No threshold, target, exit, ATR weight or stop was changed after seeing results.

## Review, exports and preservation

The page lists every trade, entry/initial-stop/planned-target, first-25% and remaining/full exits with prices and net P/L, separate source-quality groups, added/removed trades, every PH5 candidate including rejected/held, and chronological 15m and actual 5m entry observations. Download TRADES, EXITS, PROTECTION, SIGNALS and LEDGER CSVs or result JSON. Opening the page only reads saved data; POST is rejected.
Saved study: `/Volumes/SanDisk Extreme/github/ai-day-trade/trading_records/btc_structure/parent_five_studies/20261115T172851Z-PH5`. Verified 132 protected files, original worker PID 56139 and session `20261109T175620Z` unchanged. All 13 frozen source hashes match. Existing research selectors/results, P1, release bundles and original live data are preserved. Only the independent PH5 ACTIVE selector is written.
Some observations are quote-derived with zero recorded venue volume. No claim of consolidated volume, depth, exact-second sequencing or achievable fill is made. A minute crossing both support and trigger is rejected as ambiguous. Broader historical feed gaps and crypto execution costs remain limitations.
