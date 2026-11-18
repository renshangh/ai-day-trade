# BTC and SOL Entry-Quality ML Research

A separate causal entry-pattern classifier, winner/loss audit and complete sequential filter test.

Last Updated: 2026-11-10  
Status: Complete; negative test result, disabled  
Audience: Trading Desk owner and research maintainers

## Overview

North Star: reproducible, causal decisions on real observations, with honest
winner harm and sequential P/L. Study `20261110T123201Z-entry-quality` is selected
independently under `trading_records/btc_structure/entry_quality_studies/`.
Open `http://127.0.0.1:8799/crypto-live#entry-quality`.

This experiment learns entry-time patterns rather than optimizing ATR or SOL
weights. Frozen 0.2, all previous studies/selectors and both live process/session
identities remain unchanged. No broker orders, new forward worker or promotion
is enabled. Stops, targets, fractions, exits and all original numerical risk
settings remain fixed. No parameter was retuned after seeing results.

## Model and feature contract

Use one pooled, strongly regularized logistic classifier. It minimizes mean
binary log loss plus `0.5 × 1.0 × sum(non-intercept coefficients²)`. The intercept
is unpenalized. Standardization uses only training means/standard deviations;
constant columns retain a scale of one, not fabricated market observations.
Newton fitting is deterministic and must converge. The acceptance cutoff is
fixed at 0.50; no feature selection, penalty search, threshold search, validation
refit or post-test adjustment occurs.

The eleven features, all fixed before outcomes are examined, are:

1. Previous completed candle's signed body/range.
2. Previous close's position within its range.
3. Reference range / pre-entry ATR.
4. Net close change across the prior four complete candles / ATR.
5. Reference close's distance above the causal D / ATR.
6. `log(1 + D age in fifteen-minute candles)`.
7. Entry-reference chase above the original trigger / ATR.
8. Pullback from the prior four-candle high / ATR.
9. SOL identity indicator.
10. A-route indicator.
11. B2-route indicator, with the original B1 convention otherwise retained.

Features require consecutive complete prior candles, confirmed D and original
pre-entry ATR. No entry-minute final H/L/close/volume, future candles, target,
exit, realized P/L, winner label or future data-quality outcome enters the
feature vector. The chase uses the original modeled entry reference, which is
max(trigger, observed minute opening), not a later closing price. Original
crossing seconds, feed receipt and actual fills remain unverified.

If context/features or a sufficiently supported model are unavailable, abstain
and pass the original signal through. Never impute features or invent a score.
Model fitting requires at least twelve labeled rows and at least four examples
of each class. Probabilities are uncalibrated model scores, not proven win odds.

References for the method:
[official leakage guidance](https://scikit-learn.org/stable/common_pitfalls)
and [regularized logistic classification](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html).
The implementation uses the project's existing NumPy dependency, with no new
package or environment variable.

## Sources, labels and chronological split

Use the original saved BTC and SOL minute archives and frozen 0.2 entries over
October 10 00:00 UTC–November 9 00:00 UTC, exclusive, with October 3 warmup.
Training is October 10–24; validation October 24–31; test October 31–November 9.
There are 558 absent BTC and 1,754 absent SOL test minutes out of 43,200 per
asset. They remain absent, never synthesized or carried forward.

Train on original E1 records only: one row per asset/entry, not duplicated
0.1/E1/E2 outcomes from the same BTC context. Label 1 means the original E1
trade's net after the frozen cost proxy is positive; label 0 includes losses
and breakeven. An open trade has no label. The label cannot become known before
its exit minute completes. Only resolved, fully observed and unflagged first-
period labels fit the model. Future-gap quality is never a prediction feature.

There are **22 unique training entries: 9 winners and 13 losses**, eleven per
asset. Training-only preprocessing and weights are saved in
`MODEL_BEFORE_VALIDATION_TEST.json` before validation/test scoring. Entries whose
labels are unresolved by a phase boundary are excluded and counted by the saved
dataset, rather than labeled using a later exit. Across the fixed E1 evaluation,
there are 22 train, 20 validation and 29 test resolved rows; other original rows
cross split boundaries. Training statistics are optimistic in-sample fit.

The same previously studied month is reused. This is a retrospective
chronological holdout, not genuinely unseen evidence. Pooled E1 learning is
also transferred to the other BTC exit variants only for separate comparison;
those variants do not add independent training examples. A new forward sample
and more history would be needed for any credible deployment decision.

## Winning versus losing patterns

The strongest training association is lower distance above D: winners average
1.0333 ATR versus losers 1.8605 ATR. Winners also have less chase (0 versus
0.00611 ATR), a lower signed reference body (-0.0688 versus +0.1818), and lower
log D age (0.4148 versus 0.9411). All eleven pooled means, coefficients and
per-asset class means/sample sizes are available on the desk.

These are small-sample descriptive associations, not causal rules. For example,
a negative B2 coefficient comes from very few training examples; it does not
establish that B2 entries are inherently bad. Correlated features and only nine
positive examples limit interpretation.

## Prediction and original-entry filter results

Unique E1 records, with the unchanged 0.50 cutoff:

| Phase | Scored / wins / losses | AUC | Brier error | Asset-frequency baseline Brier |
|---|---|---:|---:|---:|
| Training | 22 / 9 / 13 | 0.89744 | 0.19754 | 0.23991 |
| Validation | 20 / 11 / 9 | 0.66667 | 0.23916 | 0.27337 |
| Test | 29 / 17 / 12 | 0.41176 | 0.28740 | 0.26688 |

The simpler prediction baseline is each asset's training-only win frequency,
with an explicit Beta(1,1) smoothing prior. It is not an invented market value.
The ML model is worse than that baseline on test Brier error. AUC also
falls below 0.5: the problem is not only the cutoff.

On original test E1 entries, the filter rejects **16 of 17 winners** and avoids
**10 of 12 losses**. It keeps one winner and two losses. BTC rejects all eight
winners; SOL rejects eight of nine. This fixed-entry analysis retains every
original entry/exit for comparison and introduces no replacement buys.

The training win share is 9/22 (40.9%), versus 17/29 (58.6%) in the test.
This base-rate shift and the poor ranking are consistent with weak generalization;
the sample cannot isolate a single cause. A binary positive-net label also
ignores payoff size. The training strategy can earn money despite a sub-50%
win rate because profitable trades can outweigh losses. A fixed 50% win-score
cutoff is therefore not an expected-P/L objective. Do not lower the cutoff
post-test or relabel these outcomes as evidence of an improved system.

## Full sequential replay

Independently replay all four books flat from October 31, with seven days of
actual warmup. Compare the original engine with the ML gate before opening a
position. A rejection creates no position and no consumed-history reset. The
original emitted-token handling remains; other routes do not fall back in the
same minute, and later newly emitted candidates may be assessed. Preserve the
original holding/exit-minute no-reentry convention.

The table uses independent fixed-$10,000-per-entry normalized modeled net,
not account returns. The 2bps/side ETF friction proxy excludes actual spot-crypto
fees. Every retained trade has its original stop, targets and exit legs.
Closed-trade drawdown R is not portfolio or intratrade drawdown.

| Book | Sequential trades | Original → filtered net | Original test winners rejected | Original test losses avoided |
|---|---|---:|---:|---:|
| BTC/USD 0.1 | 15 → 1 | $66.02 → $-42.68 | 8 | 6 |
| BTC/USD E1 | 15 → 1 | $134.38 → $-42.68 | 8 | 6 |
| BTC/USD E2 | 15 → 1 | $118.79 → $-42.68 | 8 | 6 |
| SOL/USD E1 | 15 → 2 | $400.35 → $-9.00 | 8 | 4 |

SOL's flat-start control has fifteen trades, while the original-month fixed
entry test cohort has fourteen. The different boundary state permits a different
candidate; do not confuse fixed-entry and sequential P/L. The sequential filter
scores 34 BTC candidates and rejects 33; SOL scores 23 and rejects 21. No extra
replacement entry is accepted in this experiment. Candidates without a matching
control entry have no counterfactual outcome; none is invented.

The negative test result is decisive for this draft: keep it disabled. Any next
experiment should be independently specified and evaluate trade payoff as well
as classification quality on longer/new data. No such new model is fitted here.

## Reproducibility and delivery

Run `python3 scripts/study_entry_quality.py` for a new isolated timestamped study.
Source archives, frozen rule hashes, all prior studies/selectors, live code and
worker identities are verified. Four full-month controls reproduce exactly;
four abstention/pass-through controls reproduce the flat-start original paths.
Feature-prefix and train-only preprocessing invariants have real-data tests.

The initial run was repeated only to harden unavailable-label handling: open
outcomes stay null and cannot be forced into training. All source original
entries are closed, so labels, fit, scores and P/L remain identical. Both runs
and their exact source bundles are preserved; no model parameter was changed.

The GET-only desk/API provides pooled/per-asset patterns, fixed entries and
forecasts, lost winners, all sequential decisions including unmatched rejects,
original/filtered entry/stop/target/exit/P&L, quality partitions and downloadable
CSV/JSON. No control can train a model, change a live rule or send an order.
