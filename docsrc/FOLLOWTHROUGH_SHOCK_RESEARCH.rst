Failed Follow-through and Steeper Shocks
=========================================

Read-only comparisons of failed-reclaim exits and steeper net-drop entries.

:Last Updated: 2026-11-10
:Status: Complete; comparison only, not promoted
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://127.0.0.1:8799/crypto-live#followthrough-comparison`` for two
separate saved experiments. Frozen 0.2, P1 and both live workers are unchanged.
No broker or paper-broker orders are enabled.

Exit tests
----------

Keep original frozen entries fixed. After a complete post-entry fifteen-minute
close above the local breakout trigger, F1 waits for two complete one-minute
closes below it. F2 instead waits for a later completed fifteen-minute failure.
Both require a non-green failure at or below the prior completed close, neither
range-inside nor body-inside. The next exact observed minute's opening must
remain below the trigger. Original earlier exits and same-minute legs win;
previous 25% profits remain realized. No replacement entries are introduced.

November 10's 04:45 EST BTC and SOL examples would both exit under F1 at
05:05. BTC's modeled net improves from -$102.87 to -$61.97 per initial BTC;
SOL's improves from -$0.266120 to -$0.174688 per initial SOL. BTC's original
05:14 exit precedes F2 confirmation, so F2 retains it; SOL F2 exits at 05:15.

These examples do not establish general superiority. Across the archived
thirty days, F1 converts three BTC winners to losses and F2 converts one.
BTC #30 is harmed by both: losing the local trigger does not necessarily
break parent support. Neither variant cuts any SOL winner in this sample,
but the SOL improvement is in-sample, with no out-of-sample validation.

.. list-table:: Fixed-$10,000-per-entry normalized net, original entries fixed
   :header-rows: 1

   * - Book
     - Original
     - F1
     - F2
   * - BTC 0.1
     - $444.59
     - $338.92
     - $410.75
   * - BTC E1
     - $527.95
     - $338.92
     - $410.75
   * - BTC E2
     - $531.53
     - $338.92
     - $410.75
   * - SOL E1
     - $1,581.86
     - $1,781.05
     - $1,705.01

Separate shock draft
--------------------

The new draft defines steepness as a net close-to-close decline of at least
three ATR in one complete fifteen-minute candle, using pre-candle ATR, adjacent
complete observations, bearish direction and a new scope low. The prior refined
criterion used two ATR of excursion to the low. This changes the measurement
and threshold together; it is not a threshold-only attribution test.

A non-shock becomes an A candidate only: it still needs P1's four independent
LL/LH phases, HH/HL and shared risk checks. Otherwise wait. BTC's 04:00 impulse
has a 2.13-ATR net drop and SOL's 1.81, so neither qualifies as a new shock.
No qualifying A was exposed in their original entry-time audit.

The full sequence reproduces all four prior refined-entry controls exactly
before testing the draft. Trades fall from 29 to 6 for each BTC book and from
30 to 6 for SOL E1. Fixed-$10k-entry normalized net falls from $351.11 to
$45.35 for BTC 0.1/E2, $344.96 to $66.69 for BTC E1, and $935.05 to $475.66
for SOL E1. Drawdown also falls; this alone does not justify promotion.
Exit overlays are not combined with this entry experiment.

Time, coverage and interpretation
---------------------------------

The monthly test uses October 10, 2026 00:00 UTC through November 9 00:00 UTC,
exclusive, with the original October 3 warmup. November 10 cases are separate.
There are 558 missing BTC and 1,754 missing SOL test minutes out of 43,200 per
asset. Missing observations are never synthesized, filled or carried forward.
The page separates flagged-gap/context and unflagged cohorts. Exit cohorts
retain the original trade's exposure; new shock sequences use their own flags.

P/L is per initial coin or sums independent fixed-$10k-entry normalizations,
not funded account returns. Costs retain the frozen 2bps/side ETF proxy and
exclude actual spot-crypto fees. Next-minute openings are historical references;
actual receipt latency, spread and executable fills are unverified. Some source
bars are quote-derived. No future minute range or unfinished candle close is
used. No thresholds were tuned after inspecting these outcomes.

Use the book, F1/F2 and exposure controls to inspect all unchanged, improved
and harmed trades, original and research exit legs, and exact known evidence.
CSV and JSON downloads include the cases and full shock sequence. The saved
research page does not start workers, fetch quotes or place orders.
