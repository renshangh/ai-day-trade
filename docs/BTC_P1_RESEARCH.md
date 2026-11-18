# BTC P1 A-Entry Research

Operate the independent same-source P1 comparison without changing frozen 0.2 or Live Paper.

Last Updated: 2026-11-09  
Status: Research only; complete sequential replay; not promoted to live  
Audience: Trading Desk owner and maintainers

## Overview

Open `/btc-p1`. Select 0.1, E1 or E2, then Frozen 0.2 or P1 research. Every
sequence includes the full trade list, original entry/exit reference times and
prices, each exit fraction and net P/L, data-quality flags, and chronological
15-minute rows. The selected trade chart fits its container and marks the full
holding interval, entry and every actual recorded model exit. A planned target
is never displayed as an exit. CSV and result JSON exports remain downloadable.

The North Star is reproducible, causal decisions from observed data. Missing
minutes remain missing. Price references and model P/L do not imply fills.

## Fixed research contract

P1 affects A only. For each original candidate D, use ATR14 known before its
15-minute candle starts. Require at least two consecutive complete post-D
candles with lows strictly above D, a completed-bar high at least D + 1 ATR,
and at least one completed post-D close at or above D + 0.5 ATR. Qualification
uses completed observations only, matching the preceding fixed-trade audit.
If D is undercut first, that low phase extends into the later lower D. Missing
confirmation bars are unavailable evidence and are never filled. Historical
qualified phases remain qualified; a subsequent break begins the next phase.

Retain confirmed original lower-high ordering and the decline origin. After
merging internal lows, retain the highest intervening original LH. The later
HH must exceed that retained high; do not pick a smaller internal resistance
to qualify. Choose the earliest originating P1-eligible ready scope. All shared
HH/HL/breakout, ATR buffers, target selection, chase limits and cost checks still
run through the original validators. P1 rejection does not consume the episode;
a later complete confirmation can become eligible. An accepted entry consumes
prior A/B setup history exactly as in frozen 0.2.

B1/B2 objects and validation paths pass through unchanged. The adapter inherits
all original exit and risk methods. The frozen aggressive B1 remains in use;
the separate experimental independent-B1 rule is not enabled.

## Window and results

The UTC window is `[2026-10-10 00:00, 2026-11-09 00:00)`, with the same seven-day
warmup and 51,961 observed source minutes. The test window has 558 absent
minutes. Per-trade initial size is 1 BTC and friction is 2 bps per side; it is
the frozen ETF-cost proxy, not actual crypto-fee-adjusted or account returns.

| Model | Frozen trades / net USD | P1 trades / net USD | Difference |
| --- | --- | --- | --- |
| 0.1 | 38 / 3,516.46 | 36 / 3,965.02 | +448.56 |
| E1 | 38 / 4,159.67 | 36 / 4,608.23 | +448.56 |
| E2 | 38 / 4,195.15 | 36 / 4,643.71 | +448.56 |

Each P1 sequence has 18 winners and 18 losers. Original A #23 (-482.78) and #26
(+34.22) are removed. The other 36 entries, stops, targets and exit legs match
their own original model exactly; no replacement entries appear. Max drawdown R
and win rate do not improve. The sample loses all existing A entries, so this
result does not establish general usefulness of P1.

The page also shows all/no-flagged-gap/flagged partitions. Baseline P1 clean net
is 3,199.85 on 34 trades; E1/E2 P1 clean nets are 3,447.52 / 3,483.00 on 35.
Flagged groups remain conditional on the observed path, not assurance that no
trigger occurred inside missing minutes.

## Isolation and reproducibility

Run `python3 scripts/retest_btc_p1_30d.py` only for an explicitly authorized
replay. It verifies the frozen manifest and thirteen pinned strategy hashes,
loads the exact frozen stream, reproduces each original sequence, and runs
each P1 variant through every observed minute. All outputs get new run IDs.
Only `p1_studies/ACTIVE.json` selects this separate research page. Original
study/release/latest pointers, source bars, frozen artifacts and live session,
control and service files are not changed. GET requests read saved results;
they never start a replay or contact a broker. No new environment variable or
order endpoint is introduced. The CLI has no broker client.

`STUDY.json` stores source and adapter hashes, baseline verification, summaries
and entry-time/route sequence comparisons. Run folders retain all observed
ledger rows, CSVs, signals and P1-blocked price crossings. Blocked crossings
are labeled before shared risk validation; they are not invented lost trades.

## November 9 annotation review

The user's marked LL4 at 02:58, 73,629.55, is an HL relative to the earlier
November 8 16:55 base of 73,530.09. It remains an LL relative to the local
73,711.65 low. The 03:15–03:30 candle first crosses the prior full high plus
0.01 at 03:17, reference 73,867.005; not at the 03:15 opening. Later confirmed
peaks/lows form the HH/HL continuation, but cannot be used before confirmation.
The separate saved case lists all reference and known-at times.

This case is outside the fixed 30-day window and before live activation at
12:57 EST. It is not retroactively entered into Live Paper or this monthly
study. At 03:17 only one post-D holding candle is complete; P1's two-bar filter
first passes at 03:30 and only three lows remain. A separate B/continuation
entry proposal must be reviewed independently; it is not added to this rerun.
