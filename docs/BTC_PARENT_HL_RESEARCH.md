# BTC Parent-Wave HL Continuation Research

Separate C-entry comparison, preserving P1, frozen 0.2 and Live Paper.

Last Updated: 2026-11-09
Status: Research only; monthly results deteriorate; not promoted
Audience: Trading-desk owner and contributors

## Overview

Open `/btc-parent-hl` for the saved comparison. This experiment addresses the
wider-wave reading of November 9 at 03:17 EST. It adds C candidates to the
P1-filtered A/B sequence, with original A/B priority, exits and risk arithmetic.
Opening the page never starts a replay, changes a worker or submits an order.
Evaluation measures full-sequence net P/L, drawdown, turnover and data quality;
catching the nominated example alone does not establish an improvement.

## Fixed operational definition

- Parent D: strict low among three adjacent complete one-hour candles,
  confirmed when the right candle completes. Exclude a candle simultaneously
  qualifying as the local high and low. Hours require four complete observed
  fifteen-minute candles.
- HL: strict low among three adjacent complete fifteen-minute candles, with
  the same outside-turn exclusion. The latest confirmed HL must remain intact
  and exceed parent D by the inherited 0.1 entry-ATR tolerance.
- Choose the most recent intact confirmed hourly parent below HL, without
  searching older parents for better reward/risk. Rebound is the highest
  confirmed fifteen-minute peak after D and before HL.
- Cross the previous complete fifteen-minute high plus $0.01 intrabar. Shared
  entry checks, 0.1-ATR chase ceiling, targets, advisory 2R, 25% first sale,
  exits and costs remain inherited.
- Initial stop uses **the larger parent D minus 0.25 entry ATR**, as explicitly
  chosen by the owner. A nearer-HL break is diagnostic, not a new exit rule.
- First crossing consumes an HL episode even during warmup or while holding.
  Every actual entry consumes prior actionable history; a subsequent HL candle
  must begin after that entry's candle. Larger parent context is retained.
- A missing minute clears C structural context rather than assuming a parent
  survived an unseen price path. No absent bars are synthesized or filled.
- Original P1 A/B entries retain priority. Holding/exit minutes cannot add a
  position. All C candidates, including held/rejected ones, are saved.

These are explicit research definitions, not proof that every discretionary
same-level wave is classified correctly. No tuning followed monthly results.

## November 9 prefix test

Two isolated replays use only persisted Alpaca observations before 03:18 EST
and reproduce the same signal without the subsequent 04:02 high. This case
assumes flat at its 03:15 activation, not throughout the entire earlier day.

| Reference | Price | Occurrence EST | Confirmed / available EST |
|---|---:|---|---|
| Larger parent D | $73,530.0885 | Nov 8 16:55 | Nov 8 18:00 |
| HL | $73,629.551 | Nov 9 02:58 | Nov 9 03:15 |
| C crossing | $73,867.005 | Nov 9 03:17 minute | No earlier than 03:18 plus delivery |
| Initial stop | $73,456.6322 | After hypothetical entry | Parent D less 0.25 entry ATR |
| First 25% target | $76,045.4052 | Known at entry | Planned, not an actual exit |

An existing B route enters at the same minute and retains priority. Qualified
C is recorded `held_position`, not an extra fill. No case P/L is invented.
The minute identifies a historical interval, not exact-second execution.
Live Paper activated later at 12:57 EST; this is not a retroactive live fill.

Separately, the actual 13:08 live trade broke its nearer $74,446.3365 HL at
13:22, inside the 13:15 candle. Its recorded $73,629.551 D and $73,541.6979
hard stop were not breached in that candle. This changes no live protection.

## Same thirty-day sequence

Study `20261109T220635Z-parent-HL` uses the exact frozen 0.2 source, seven-day
warmup and window `[2026-10-10T00:00Z, 2026-11-09T00:00Z)`. There are 42,642
observed test minutes out of 43,200; 558 missing minutes remain absent.
Source minute SHA256:
`6676741b2e47d6fd45e5bde450f8e308eb4546df830a54e281412a1e1fdfc05b`.

All three P1 controls reproduce exactly before comparison. Results normalize
each entry to initial 1 BTC, with the original two basis points per side cost
proxy. These are not compounded returns, broker fills or actual crypto fees.

| Model | P1 net / trades | P1 + C net / trades | C entries | C net alone |
|---|---:|---:|---:|---:|
| 0.1 | $3,965.02 / 36 | -$8,575.17 / 143 | 109 | -$11,309.69 |
| E1 | $4,608.23 / 36 | -$10,623.94 / 181 | 146 | -$15,206.05 |
| E2 | $4,643.71 / 36 | -$8,891.40 / 147 | 113 | -$12,304.61 |

C admits many losing continuations. Turnover also raises costs, but gross
results are negative too. All-observation, no-flagged-gap and gap/partial
groups are listed separately. Removing flagged trades does not make these
variants profitable. A clean holding-path flag does not certify all earlier
target context was gap-free. C remains unpromoted; no post-result tuning.

## Review, exports and preservation

The page provides frozen/P1/P1+C sequences for 0.1/E1/E2, entry-time and route
matching, full entry/exit charts, parent/HL confirmation times, chronological
protection/events, all C candidates, and TRADES/EXITS/PROTECTION/LEDGER/SIGNALS
CSVs plus result JSON. Charts fit available width and mark all actual exits.

`scripts/retest_btc_parent_hl.py` writes new runs and its independent
`parent_hl_studies/ACTIVE.json`. Protected P1 sources, study/run artifacts,
live control/session and frozen files are hashed before/after; all thirteen
frozen engine hashes are verified separately. The live worker is not restarted.
Frozen archives/tag, live activation, P1 selector and original research selector
remain unchanged.

Regression tests in `trading_desk/tests/test_btc_parent_hl*.py` and
`test_btc_parent_hl_render.cjs` cover causal confirmation, parent-D stops,
consumed episodes, missing observations, B priority, saved gap groups,
allowlisted exports, responsive chart bounds and no HTTP trading action.
