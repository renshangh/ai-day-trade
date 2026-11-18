# Refined A, B1 and B2 Historical Comparison

An isolated full-sequence test of the entry refinements, with original risk and exits fixed.

Last Updated: 2026-11-10  
Status: Complete; lower returns, not promoted  
Audience: Trading Desk owner and maintainers

## Overview

The owner requested a separate same-thirty-day comparison after the live-entry
classification audit. This experiment applies P1 to A, requires a separate
post-D hold for B1, limits B1 to its first stabilization breakout, and evaluates
B2 before B1. It uses BTC 0.1/E1/E2 and SOL E1, matching the two live services'
books. It does not enable ETH or alter either running worker.

The existing North Star is causal, reproducible decisions on real observations.
The locked protocol and code hashes were saved before the replay. All four
original controls reproduce their saved entry/risk/exit paths and metrics before
the refined sequence runs. No parameter is adjusted after inspecting results.

## Fixed interpretation of the draft

The earlier prose did not specify exactly how long a first-stabilization B1
remains eligible. Before the test, this run fixed the following interpretation:

- **A:** use existing P1 independence: at least four LL/LH phases, each with two
  completed post-D holds, a rebound high at least one pre-D ATR above its low,
  and a completed close at least half an ATR above it; then inherited HH/HL and
  shared trigger checks.
- **B1:** the first independent complete off-low post-D candle that holds D is
  the reference. Only its immediately following 15-minute candle can trigger
  B1. A later rolling stabilization reference cannot revive this first probe.
- **B2:** inherited completed rebound and later qualifying HL, intact support,
  shared trigger/risk checks. Evaluate B2 before B1. After B1's first window
  ends, wait for a valid B2 rather than falling back to a stale B1.
- **Episode lifecycle:** a new causally qualifying 2-ATR bearish new-low impulse
  starts a fresh B episode without resetting A. D may extend before an
  independent hold. After the first hold, a D breach retires that attempt;
  rolling D down cannot rescue it. A new qualifying shock may begin another.

This is a disclosed operational interpretation of the draft, not the unique
possible definition of B1. No hours-based expiry was optimized. The one-reference
breakout phase is fixed before results. Do not silently reinterpret it after
seeing which winners it misses.

Parent-D stop/buffer, HL tolerance, target selection, 25% first sale and inherited
exit variants, cost proxy, risk screening and consumed-entry history remain
fixed. 2R remains advisory. Original observation gaps are never filled.

## Source and period

Study: `20261110T112940Z-refined-AB`, stored under
`trading_records/btc_structure/refined_entry_studies/` with its own ACTIVE selector.
Original crypto transfer/P1/C/release selectors remain unchanged.

Use exactly the archived period **2026-10-10 00:00 UTC through 2026-11-09 00:00
UTC, exclusive**, with warmup from October 3. New York boundaries are October 9
20:00 EDT through November 8 19:00 EST. The BTC stream is the exact frozen 0.2
source; SOL is the same saved Alpaca US crypto minute stream from the prior
transfer comparison. There are 558 absent BTC test minutes and 1,754 absent
SOL test minutes, out of 43,200 expected per asset. No new download, synthetic
bar, interpolation or carry-forward is used.

## Full sequential results

Each entry starts with one coin, independently; columns labeled $10k normalize
each entry to $10,000 and sum its actual modeled exit-leg P/L. This is not a
funded portfolio return, compounding simulation or actual spot-crypto return.
All books finish flat. The frozen 2bps/side ETF friction proxy excludes actual
spot crypto fees and executable bid/ask/queue effects.

| Book | Trades old → refined | Net per coin old → refined | Per-coin difference | Fixed $10k entry old → refined | $10k difference | All-book max closed DD, R |
|---|---|---|---:|---|---:|---|
| BTC 0.1 | 38 → 29 | $3,516.46 → $2,686.90 | −$829.56 | $444.59 → $351.11 | −$93.48 | 3.18 → 3.33 |
| BTC E1 | 38 → 29 | $4,159.67 → $2,635.80 | −$1,523.86 | $527.95 → $344.96 | −$182.99 | 2.98 → 3.26 |
| BTC E2 | 38 → 29 | $4,195.15 → $2,686.90 | −$1,508.25 | $531.53 → $351.11 | −$180.42 | 2.64 → 3.33 |
| SOL E1 | 35 → 30 | $15.371588 → $9.160567 | −$6.211021 | $1,581.86 → $935.05 | −$646.81 | 1.16 → 1.70 |

Return falls and closed-trade drawdown increases in every book. Do not promote
this draft to either worker from these results. This is the same development
month, not unseen chronological validation; the draft was motivated by later
live examples. A changed route label alone is not an economic improvement.

## Which trades changed

Entries match by asset/model and exact reference minute, not renumbered trade
ID or route label. If prices, risk, targets and all exits match but A/B labels
differ, classify `relabelled_only` with zero P/L change. Other categories are
unchanged, changed at the same minute, removed and added. A later replacement
entry appears separately; do not claim a one-to-one counterfactual pairing.

Every BTC variant has **10 unchanged, 5 label-only, 23 removed and 14 added**;
SOL E1 has **14 unchanged, 4 label-only, 17 removed and 12 added**. No same-minute
economic-path changes occurred in this run. Added entries are full sequential
replacements after different earlier entries/reset history; original entries
are not artificially held fixed.

Examples from BTC E1, fixed-$10k-entry normalization:

- Original #2 at Oct 12 21:00 EDT disappears: losing its +$268.66 contribution.
- Original #30 at Nov 4 07:31 EST disappears (−$185.90 contribution change);
  a new #23 enters at 07:48 and contributes +$185.52. These are separate
  sequence events, not a rule tuned to recover that winner.
- Original #5 at Oct 15 09:45 EDT disappears, avoiding its −$94.57 contribution.
  Removing that loss does not establish improved month-level performance.

BTC E1 removes 11 winning and 12 nonpositive original trades, whose combined
normalized net was +$317.76; fourteen new trades contribute +$134.77, giving
−$182.99 overall. SOL removes 8 winning and 9 nonpositive trades (+$837.32 net),
while twelve additions contribute +$190.51, giving −$646.81 overall.

## Data-exposure partitions

The page exposes all, no-flagged-gap/context and flagged-gap/context partitions.
This flags recorded entry/holding exposure, not a claim that every older context
is complete. Each sequence is partitioned independently. If a same-minute old
and new trade has different exposure, the table explicitly notes that one side
is excluded by the partition; delta sums still reconcile to its summaries.
The displayed maximum drawdown is always the all-book value, labeled as such.

BTC E1 no-flagged-gap net drops from $2,998.96 to $1,475.09 per initial BTC. Its
flagged contribution stays $1,160.71. SOL has no flagged trades in either
sequence, despite the underlying source gaps. Empty partitions show no trades,
not fabricated zero-price entries.

## Review on crypto-live

Open `/crypto-live#refined-comparison`. This is a separately labeled historical
section, not a fourth live worker. Select book, exposure partition and whether
to show only changed trades. Inspect each original/refined entry, initial stop,
first target, every 25%/remaining exit leg and P/L, original-entry-time causal
state, and the change delta. Full original/refined CSV/JSON and 15m ledgers are
downloadable. Opening/filtering/exporting never starts a replay or order.

Use `python3 scripts/retest_refined_entries.py` only for an explicitly requested
new saved study. The script is time-bounded externally in the local run log at
`outputs/refined_entries_30d/REPLAY.log`; current results are preserved. Thirteen
frozen strategy hashes, immutable source archives, prior selectors and both
live PID/session identities are checked before and after the replay.
