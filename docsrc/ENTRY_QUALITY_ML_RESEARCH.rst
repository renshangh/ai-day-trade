BTC and SOL Entry-Quality ML
============================

A separate causal classifier and sequential filter comparison on real entries.

:Last Updated: 2026-11-10
:Status: Complete; negative result, disabled
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://127.0.0.1:8799/crypto-live#entry-quality``. This experiment learns
winning/losing entry patterns rather than tuning ATR or SOL weights. Frozen
0.2, previous studies, both live worker/session identities and all original
entry/exit/risk settings remain unchanged. No orders or live promotion occur.

Model and inputs
----------------

A single deterministic ridge-logistic model uses eleven entry-time features:
completed reference candle body/range, close position, range/ATR, prior-four-
candle net move/ATR, distance above D/ATR, log D age, breakout chase/ATR,
pullback from the prior four-candle high/ATR, SOL identity, A route and B2 route.
Features exclude future candles, entry-minute final OHLCV, targets, exits and
P/L. Missing context or an unavailable model causes abstention and passes the
original signal through; no features, scores or bars are invented.

Training-only standardization and a fixed L2 penalty of 1.0 are used. The
intercept is unpenalized and the cutoff is fixed at 0.50. There is no feature,
penalty or cutoff search and no refit after validation. Scores are uncalibrated
research outputs, not validated win odds. The project's existing NumPy
dependency is sufficient; no new packages or environment variables are added.

Chronology and labels
---------------------

Use original E1 trades, one BTC/SOL record per entry. Other BTC exit variants
do not duplicate the training sample. A positive original E1 net after the
fixed cost proxy is a win label; an open trade has no label. A completed
outcome cannot be known before its exit minute ends. Training labels must be
resolved and unflagged before the cutoff; later outcomes never fit the model.

The original archived thirty days run October 10 00:00 UTC–November 9 00:00 UTC,
exclusive, with October 3 warmup. Train on the first fourteen days, validate
on the next seven, test on the last nine. Only 22 unique training entries
qualify: nine wins and thirteen losses. Validation has 20 resolved original
entries and the test has 29. Entries crossing phase boundaries are excluded
and counted. Missing minutes remain absent: 558 BTC and 1,754 SOL out of
43,200 per asset.

This is a retrospective chronological holdout of dates studied previously,
not genuinely unseen evidence. Sparse data and correlated features limit
interpretation. The same E1-trained classifier is transferred to BTC 0.1/E2
only for separate comparison.

Patterns and prediction quality
-------------------------------

In the training sample, winning entries are closer to D (1.0333 ATR versus
1.8605), have less chase, less positive reference candle bodies and younger D
references. The page shows all pooled and per-asset class means/sample sizes
and standardized coefficients. These are descriptive associations, not causal
trading rules. There are no A training examples and only two B2 losses; the
model cannot claim a learned A-versus-B comparison. Later A scores extrapolate
from other features.

.. list-table:: Unique E1 prediction diagnostics
   :header-rows: 1

   * - Phase
     - Scored / wins / losses
     - AUC
     - Brier error
     - Asset-frequency baseline Brier
   * - Training, optimistic fit
     - 22 / 9 / 13
     - 0.89744
     - 0.19754
     - 0.23991
   * - Validation
     - 20 / 11 / 9
     - 0.66667
     - 0.23916
     - 0.27337
   * - Test
     - 29 / 17 / 12
     - 0.41176
     - 0.28740
     - 0.26688

The baseline predicts each asset's training-only win frequency with explicit
Beta(1,1) smoothing. The ML filter performs worse on test Brier error and has
AUC below 0.5. At its fixed cutoff, it rejects 16 of 17 original test winners
while avoiding 10 of 12 losses. It keeps one winner and two losses.

A binary win label ignores payoff magnitude. A strategy can be profitable
with fewer than half of its trades winning, so a 50% win-score gate is not an
expected-P/L objective. Training win share is 40.9%, versus 58.6% in the test.
Do not lower the cutoff after inspecting this result or assume a single cause
for the weak generalization.

Sequential trading effect
-------------------------

Start every test book flat on October 31 with seven days of actual warmup.
A rejected emitted candidate creates no position and does not reset consumed
entry history. Later new candidates can be scored, using unchanged emitted-
token and exit-minute handling. No replacement route is bought in the same
minute. Four full controls and four abstention controls reproduce exactly.

.. list-table:: Final-nine-day full sequence, fixed-$10k-entry normalized net
   :header-rows: 1

   * - Book
     - Trades original to filtered
     - Original net
     - Filtered net
   * - BTC 0.1
     - 15 to 1
     - $66.02
     - -$42.68
   * - BTC E1
     - 15 to 1
     - $134.38
     - -$42.68
   * - BTC E2
     - 15 to 1
     - $118.79
     - -$42.68
   * - SOL E1
     - 15 to 2
     - $400.35
     - -$9.00

These sums normalize each independent entry to $10,000; they are not funded
account returns. Costs retain the 2bps/side ETF proxy and exclude actual crypto
fees. Original/filtered stops, targets, fractions and exit legs are available.
Closed-trade drawdown R is not portfolio or intratrade drawdown. Open marks
are separate and no forced final sale is invented.

The fixed-entry and sequential comparisons have different boundary states;
SOL has fourteen original-month test entries versus fifteen flat-start control
entries. A new rejected candidate without a matching control entry has no known
counterfactual outcome. The page preserves that absence explicitly.

Use and reproduction
--------------------

Keep this filter disabled. Any further payoff-aware learning experiment needs
its own predeclared protocol and longer/new evidence; none is silently fitted.

Run ``python3 scripts/study_entry_quality.py`` to create a new isolated study.
Feature contracts, actual archive hashes, source bundles, training keys,
preprocessing, fitted weights and model-before-validation/test artifacts are
saved. Data-prefix invariance, missing context, label availability, train-only
preprocessing, control reproduction, preserved files, trade fractions and
P/L partitions have real-data tests.

The read-only page/API provides all original-entry forecasts, training
patterns, rejected winners, complete sequential differences, every new
candidate decision and CSV/JSON downloads. No control can train a model,
change a worker or submit an order.
