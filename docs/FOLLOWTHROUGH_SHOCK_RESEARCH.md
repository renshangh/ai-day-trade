# Failed Follow-through and Steeper Shock Research

Two isolated experiments explaining the November 10 04:45 BTC and SOL failures.

Last Updated: 2026-11-10  
Status: Complete; comparison only, not promoted  
Audience: Trading Desk owner and maintainers

## Overview

North Star: causal, reproducible decisions on sourced observations. Study
`20261110T115246Z-followthrough-shock` is independently selected under
`trading_records/btc_structure/followthrough_shock_studies/`. View it at
`http://127.0.0.1:8799/crypto-live#followthrough-comparison`.

Keep frozen 0.2, P1, prior studies/selectors and both live workers unchanged.
The two experiments are deliberately not combined. No broker or paper-broker
order, new chat automation, or parameter search is enabled.

## Locked exit experiment

Keep the original BTC 0.1/E1/E2 and SOL E1 entries, initial stops, targets and
existing exit paths fixed. The original local breakout trigger is the failure
level, not the entry price when the entry gapped higher. Arm only after a full
post-entry fifteen-minute candle closes above that level.

- **F1:** two adjacent completed one-minute closes below the level, after arming.
  At the next exact observed minute's opening, require price still below level;
  the current fifteen-minute prefix must be non-green, no higher than the
  previous completed close, and neither range-inside nor body-inside that bar.
- **F2:** a later complete fifteen-minute candle closes below level, non-green,
  no higher than the prior close and neither range-inside nor body-inside. Use
  the exact next observed minute's opening only if still below level.
- Original earlier exits and same-minute legs win. Keep prior 25% realized legs;
  replace only a strictly later exit of the remaining fraction. No replacement
  entries are introduced. Original hard stops remain. Missing observations
  reset arming; no interpolation, carry-forward or retrospective fills.

Only prior completed observations and the reference minute's opening are used.
No reference-minute high/low/close or future fifteen-minute close is consulted.
An opening is an optimistic historical reference boundary, not proof that a
live system receiving the preceding bar could execute there. Receipt latency,
spread and executable quote data are unavailable. Provider zero-volume bars may
be quote-derived rather than trade prints. Both F1 and F2 allow a doji under the
owner's non-green constraint. No 1R or round-number gate was added.

## The actual 04:45 cases

All times November 10, 2026 EST; one initial coin, original 2bps/side ETF proxy.
Neither trade reached its first 25% target; each comparison exits 100%.

| Case | Entry | Original exit / net | F1 reference / net | F2 reference / net |
|---|---|---|---|---|
| BTC #3 | 04:45 at 74,369.01 | 05:14 at 74,295.87 / -$102.87 | 05:05 at 74,336.7845 / -$61.97 | Original exit retained / -$102.87 |
| SOL #2 | 04:45 at 85.41505 | 05:30 at 85.18305 / -$0.266120 | 05:05 at 85.2745 / -$0.174688 | 05:15 at 85.2678 / -$0.181387 |

The 04:45–05:00 candles close above their original triggers at 05:00. The
05:03 and 05:04 minute closes are then below the triggers, known by 05:05;
current prefixes also pass the direction/inside guards. BTC's original
05:14 exit already precedes F2's potential 05:15 confirmation, so F2 cannot
claim a better earlier result. SOL's completed 05:00–05:15 failure permits F2.
The original BTC label was B1 even though B2 also qualified under its priority;
SOL was an actual first-break B1 without a qualifying HL at entry.

## Same-month winner and loser check

Use the unchanged archived October 10 00:00 UTC–November 9 00:00 UTC window,
exclusive, with October 3 warmup. This ends before the live examples. There are
558 missing BTC test minutes and 1,754 SOL, out of 43,200 each. Full-context and
flagged-gap/context groups are shown separately. Exit partitions retain the
original trade's exposure; new shock sequences calculate their own exposure.

The following sums independent fixed-$10,000-per-entry normalized net results;
these are not funded account returns or actual spot-crypto fee-adjusted profits.

| Book | Original | F1 | F2 | F1 losers improved / worsened | Winners cut F1 / F2 |
|---|---:|---:|---:|---:|---:|
| BTC 0.1 | $444.59 | $338.92 | $410.75 | 7 / 1 | 3 / 1 |
| BTC E1 | $527.95 | $338.92 | $410.75 | 7 / 1 | 3 / 1 |
| BTC E2 | $531.53 | $338.92 | $410.75 | 7 / 1 | 3 / 1 |
| SOL E1 | $1,581.86 | $1,781.05 | $1,705.01 | 9 / 1 | 0 / 0 |

All cut BTC winners become net losses. F2 improves 5/4/5 BTC losers and 6 SOL
losers, worsening none. Do not count the three correlated BTC model books as
three independent market samples. SOL's apparent improvement is in-sample.

**BTC #30 is the key counterexample:** entry November 4 07:31 EST at
78,239.91, parent stop 77,857.281241. F1 would exit 08:53 at 78,206.4435 for
-$64.76; F2 09:30 at 78,225.185 for -$46.02. The original path first sells
25% at 09:40, exits the balance at 14:05 and nets +$1,454.49 per BTC.
F1's current-prefix low 78,205.655 still holds the preceding candle's
78,205.61 low; its high exceeds the prior high by only about $1.01. It fails
the inside guard mechanically but has not broken parent support. Losing the
entry trigger therefore does not establish a larger structural failure.
The same exit predicate cannot reliably distinguish this normal retest from
the 04:45 failures. No extra rule was fitted after seeing this counterexample.

Other controls: original BTC #32's baseline exit moves from November 5 17:47
EST (-$732.67) to 12:02 (-$170.65) with F1, or 12:15 (-$211.35) with F2.
Its E1 path already exits at 12:15, so F2 makes no further improvement. Original
#5 still stops eight minutes after entry, before any post-entry fifteen-minute
close can arm the overlay; neither test claims to solve that rapid initial
failure. F1 also harms winners #15 and #17, turning +$138.06 / +$428.99 into
-$83.02 / -$172.79 per BTC. F2 preserves those two winners, but still harms #30.

## Separate steeper shock experiment

Use the prior refined-entry draft as the control, not the frozen-entry exit
overlay. Reproduce all four saved control paths and metrics exactly first.
The new draft requires a **net close-to-close decline ≥3 pre-candle ATR within
one completed fifteen-minute candle**, adjacent complete context, bearish body
and a new scope low. This is a normalized fixed-time drop, not a screen angle.
The earlier refined criterion used ≥2 ATR excursion to the low. This research
changes both the net metric and threshold as a single disclosed steeper-shock
draft; it does not attribute its results solely to raising 2 to 3.

Non-shocks must go through unchanged A/P1 structural checks: four independent
LL/LH phases, HH/HL and shared risk validation. They cannot automatically become
A buys. Both 04:45 impulses fail: BTC net decline 2.13 ATR (old excursion 3.08),
SOL net 1.81 ATR (old excursion 2.87). No qualified A was exposed in their
original entry-time audit. Watch rather than force a trade.

| Book | Prior refined trades → steeper | Prior refined $10k net | Steeper $10k net | Closed drawdown R, prior → steeper |
|---|---|---:|---:|---|
| BTC 0.1 | 29 → 6 | $351.11 | $45.35 | 3.33 → 0.85 |
| BTC E1 | 29 → 6 | $344.96 | $66.69 | 3.26 → 0.95 |
| BTC E2 | 29 → 6 | $351.11 | $45.35 | 3.33 → 0.85 |
| SOL E1 | 30 → 6 | $935.05 | $475.66 | 1.70 → 0.37 |

Lower trade counts and drawdown do not offset the lost total return by
themselves. No live promotion is justified by this same-window result.
A future candidate needs forward evidence and explicit deployment approval;
none is enabled here.

## Reproducibility and delivery

Run `python3 scripts/study_followthrough_shock.py` to create a new independent
study, never overwrite an old run. Code hashes were pinned before viewing the
04:45 outcomes or monthly replay. Source archive hashes, all protected files,
worker PID/session identities and thirteen frozen rule-file hashes are checked.
The read-only view/API supplies all original trades, earlier exit evidence,
all shock removals/additions and CSV/JSON exports. No research module is
imported by either worker. The dashboard reads saved files only, without new
quotes or research polling. Tests use actual saved minutes, enforce causal
access, reconcile legs/partitions and retain harmful winner #30.
