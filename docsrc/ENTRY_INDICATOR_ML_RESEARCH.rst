VWAP and Moving-Average ML Features
===================================

A separate indicator-feature ablation with genuine prices and matched controls.

:Last Updated: 2026-11-10
:Status: Complete; mixed result, not promoted
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://127.0.0.1:8799/crypto-live#entry-indicators``. Frozen 0.2, earlier
research/selectors and both live workers remain unchanged. No orders, new
forward worker or automatic promotion are enabled. This tests added ML inputs,
not new stops, exits, coin weights or indicator-period optimization.

New completed-candle features
-----------------------------

* Reference close minus SMA20, divided by pre-entry ATR.
* SMA20 minus SMA50, divided by ATR.
* SMA20's change over three completed fifteen-minute candles, divided by ATR.
* Reference close minus UTC-day VWAP, divided by ATR.
* UTC-day VWAP's change over three completed candles, divided by ATR.

SMA20/50 refer to twenty/fifty fifteen-minute bars, not days. Fifty consecutive
complete prior bars are required. No entry-candle final values or future prices
enter the features. UTC-day VWAP resets at 00:00 UTC and ends before the entry
candle. It is the sum of actual minute volume times native minute VWAP, divided
by actual volume. The slope uses the same UTC session forty-five minutes earlier.
Both points require genuine positive volume and complete actual minute coverage.

The original transfer files omit native minute VWAP. Recover it from the
original frozen BTC tuple archive and retained SOL raw responses; verify source
hashes and exact timestamp/OHLCV/trade-count agreement. Never approximate it
with typical prices, fill gaps, substitute prior prices or create traded volume.
Actual zero-volume quote bars contribute zero weight. This is venue-specific
Alpaca VWAP, not consolidated global-crypto VWAP.

Source matching recovers all 51,961 BTC and 47,495 SOL archived observations,
including warmup. No positive-volume minute lacks native VWAP. Many observations
are actual quote-only bars: 34,105 BTC and 42,658 SOL. A missing observation,
insufficient same-session slope or no positive volume makes VWAP unavailable.

Matched comparisons and ML controls
-----------------------------------

.. list-table:: Five fixed arms
   :header-rows: 1

   * - Arm
     - Features
     - Training rows / wins / losses
   * - Previous ML
     - Original 11
     - 22 / 9 / 13
   * - MA coverage control
     - Original 11, require MA availability
     - 19 / 8 / 11
   * - Add MA
     - Original 11 plus 3 MA features
     - Same 19
   * - Combined coverage control
     - Original 11, require MA and VWAP availability
     - 17 / 7 / 10
   * - Add MA + VWAP
     - Original 11 plus all 5 indicator features
     - Same 17

Each added-feature/control pair has identical training keys and inference
availability requirements. Missing features/model cause abstention and pass the
original signal through. Counts are visible, so pass-through gains cannot be
silently attributed to learned indicator information. The combined arm tests
a bundle; it does not isolate VWAP's marginal contribution beyond MAs.

Retain penalty 1.0, fixed 0.50 cutoff, training-only preprocessing and no refit.
No indicator period, penalty, threshold or winning arm is chosen using test
results. The old classifier and all original strategy controls reproduce exactly.

Data and validation
-------------------

Use the same October 10 00:00 UTC–November 9 00:00 UTC thirty-day archive,
exclusive, with October 3 warmup. Train on fourteen days, validate on seven and
test on the final nine. Labels use unique original BTC/SOL E1 entries only;
other BTC exit variants are separate evaluations, not duplicate training data.
Only outcomes available after their exit minute completes can be training labels.

The original 558 missing BTC and 1,754 missing SOL test minutes remain absent.
No downloads, vendor revisions or synthetic observations are introduced. This
previously studied window is a retrospective chronological ablation, not unseen
validation. Seventeen combined training examples for sixteen features is very
little evidence, even with regularization. There are no A training examples;
the classifier cannot claim a learned A/B quality comparison.

Sequential final-nine-day results
---------------------------------

Each test book restarts flat with seven days of actual warmup. Original stops,
targets, exit fractions, exits, risk settings and candidate-history handling are
unchanged. No forced boundary sale or counterfactual fill is invented.

.. list-table:: Fixed-$10k-entry normalized modeled net
   :header-rows: 1

   * - Book
     - Unfiltered
     - Previous ML
     - MA control
     - Add MA
     - Combined control
     - Add MA + VWAP
   * - BTC 0.1
     - $66.02
     - -$42.68
     - -$42.68
     - -$138.75
     - -$30.86
     - -$126.93
   * - BTC E1
     - $134.38
     - -$42.68
     - -$42.68
     - -$70.39
     - -$61.19
     - -$88.90
   * - BTC E2
     - $118.79
     - -$42.68
     - -$42.68
     - -$85.98
     - -$30.86
     - -$74.17
   * - SOL E1
     - $400.35
     - -$9.00
     - $26.75
     - $19.54
     - $74.59
     - $377.69

These sum independent $10,000-per-entry normalizations, not funded account
returns. Costs retain the original 2bps/side ETF proxy and exclude actual crypto
fees. Open marks remain separate. Closed-trade drawdown R is not portfolio or
intratrade drawdown.

SOL's combined arm improves by $303.10 over its matched control, so that gain
is not merely missing-data pass-through. It takes eight trades versus fifteen
unfiltered, and all-book closed-trade drawdown is about 0.726R versus 0.894R.
It still trails unfiltered SOL return. BTC worsens; MA-only trails its matched
control for both assets. Keep all arms out of live trading.

Prediction quality and limits
-----------------------------

The combined model retains more scored SOL test winners than its matched
control, but also retains more losses. It does not improve prediction ranking:
pooled test AUC is about 0.412 versus 0.442 matched, and Brier error is 0.27894
versus 0.27739 (lower is better). SOL-only ranking/Brier also weaken. A few
large retained winners dominate the P/L change; uncalibrated win scores are
not expected-return estimates.

The training mean for winners is farther below SMA20 but closer to VWAP than
for losers. These are tiny-sample descriptive associations in a dip-oriented
strategy, not validated causal crossover rules. No settings are adjusted after
seeing these outcomes. Fresh forward evidence and a new predeclared experiment
would be required before any promotion.

Use and reproduction
--------------------

Run ``python3 scripts/study_entry_indicators.py`` for a new independent study.
Saved evidence includes native source audit/hashes, source bundle, all five
fits, scored original entries, every sequential decision, stops/targets/fractional
exit P/L, gap partitions and CSV/JSON downloads.

The GET-only desk supports book, arm, original-entry phase and exposure group.
The sequential table always shows the final-nine-day flat-start test. Matched
control deltas, scored/abstained counts and all lost winners remain visible.
No UI control retrains, changes live settings, creates fills or sends orders.
