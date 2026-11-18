# VWAP and Moving-Average Entry-Quality ML

A separate real-indicator feature ablation with matched training and availability controls.

Last Updated: 2026-11-10  
Status: Complete; mixed result, not promoted  
Audience: Trading Desk owner and research maintainers

## Overview

North Star: causal, reproducible decisions with honest P/L, winner harm and
missing-data attribution. Study `20261110T130937Z-entry-indicators` is independently
selected under `trading_records/btc_structure/entry_indicator_studies/`.
Open `http://127.0.0.1:8799/crypto-live#entry-indicators`.

The owner requested real VWAP and moving-average inputs for the existing entry-
quality ML. The old 11-feature classifier, all prior selectors/results, frozen
0.2, both live workers and their PID/session identities are preserved. No orders,
new forward worker or live promotion occur. Original stops, targets, fractional
sales, exits, ATR/risk settings, regularization and 0.50 cutoff remain fixed.

## Indicator definitions fixed before replay

Use completed fifteen-minute closes and pre-entry ATR:

- `(last close - SMA20) / ATR`.
- `(SMA20 - SMA50) / ATR`.
- `(SMA20 now - SMA20 three candles earlier) / ATR`.
- `(last close - UTC-day VWAP) / ATR`.
- `(UTC-day VWAP now - VWAP three candles earlier) / ATR`.

SMA20/SMA50 mean twenty/fifty fifteen-minute bars, not trading days. All fifty
bars must be consecutive and complete; slope uses the corresponding prior
completed windows. No gap is filled and the entry candle's unfinished values
are excluded. The price reference is the last completed close, not a future
entry-candle close.

VWAP resets at **00:00 UTC** for these 24/7 crypto observations. Compute
`sum(native minute VWAP × actual positive volume) / sum(actual positive volume)`
through the prior completed fifteen-minute candle. The slope uses the same UTC
session forty-five minutes earlier. Both points require real positive volume;
very early session entries or incomplete sessions abstain. This is Alpaca-
venue-specific volume, not consolidated global-crypto VWAP and not necessarily
the VWAP on another chart venue.

Original OHLCV transfer files omit the native VWAP field. Recover it without
changing prices from the original frozen BTC tuple archive and retained SOL raw
provider response pages. Verify compressed-source hashes, raw response hashes
and exact time/OHLCV/trade-count agreement. Do not use HLC/3 or any approximate
price in place of native VWAP.

- BTC: 51,961 archived observations matched; 17,856 positive-volume minutes and
  34,105 zero-volume minutes.
- SOL: 47,495 matched; 4,837 positive-volume minutes and 42,658 zero-volume minutes.
- No positive-volume minute lacks its native VWAP. Source coverage includes warmup.

Actual zero-volume quote bars count as observed time but contribute zero VWAP
weight. This is indicator arithmetic, not a carried-forward synthetic bar.
A missing minute invalidates that session calculation; it is never treated as
zero volume or replaced by a prior price. Alpaca explicitly documents quote-
midpoint bars with zero volume in its
[crypto data documentation](https://docs.alpaca.markets/us/docs/real-time-crypto-pricing-data)
and [market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq).

## Fixed feature ablations and matched controls

Five predeclared arms, with no period, feature, penalty or cutoff search:

| Arm | Input features | Training sample |
|---|---|---|
| Previous ML | Original 11 features | 22: 9 wins / 13 losses |
| MA coverage control | Original 11; require available MA context | 19: 8 / 11 |
| Add MA | Original 11 + 3 MA features | Same 19 |
| Combined coverage control | Original 11; require both indicator contexts | 17: 7 / 10 |
| Add MA + VWAP | Original 11 + all 5 new features | Same 17 |

Each added-feature/control pair has identical training keys and inference
indicator-availability requirements. This separates indicator information from
sample selection and abstention effects. A missing feature/model passes the
original signal through; scored, abstained and rejected counts are explicit.
Complete sequential paths can still expose different later candidate times.

The combined arm tests a five-feature bundle against its matched original-
feature control. It does **not** isolate VWAP's marginal contribution beyond
MAs; that would require another independently specified same-cohort ablation.
Do not compare MA-only versus combined as though only VWAP changed, because
coverage and training rows also differ.

All classifiers keep the same ridge penalty 1.0, unpenalized intercept, train-
only standardization and fixed 0.50 cutoff. No model is chosen from the later
test. Model source and settings are pinned before replay; all five fits are
saved before validation/test scoring. The previous model and its four sequential
paths reproduce exactly, as do the original full/test controls.

## Data and split

Use the same original October 10 00:00 UTC–November 9 00:00 UTC, exclusive,
thirty-day source, with October 3 warmup. Train on fourteen days, validate on
seven and test on the final nine. Fit unique BTC E1 + SOL E1 labels only;
other BTC variants do not duplicate the training data. Labels become available
only after the exit minute completes. Unresolved labels remain excluded. The
original first-period availability/quality rules are retained.

The same 558 missing BTC and 1,754 missing SOL test minutes remain absent.
No downloads, vendor revisions, interpolation or synthetic observations are
introduced. Raw VWAP recovery uses only the same archived observations.

These dates were studied before: this is a retrospective chronological ablation,
not genuinely unseen validation. With only seventeen combined-arm training
samples for sixteen features, regularization cannot establish reliable
predictive performance. No A training examples are available; type effects
cannot be claimed as a learned A/B comparison. More independent data and fresh
forward validation remain necessary.

## Full sequential nine-day test results

All test books restart flat with seven days of real warmup. Original candidate
lifecycle, emitted-token handling, no reentry on exit minute, hard stops,
resistance targets and exit legs remain unchanged. No forced boundary fill or
counterfactual outcome is invented.

The table sums fixed-$10,000-per-entry normalized modeled net, not funded
account returns. It keeps the original 2bps/side ETF friction proxy and excludes
actual spot crypto fees. All these test books end flat; open marks are still
reported separately in artifacts. Closed-trade drawdown R is not portfolio
or intratrade drawdown.

| Book | Unfiltered | Previous ML | MA coverage control | Add MA | Combined coverage control | Add MA + VWAP |
|---|---:|---:|---:|---:|---:|---:|
| BTC/USD 0.1 | $66.02 | $-42.68 | $-42.68 | $-138.75 | $-30.86 | $-126.93 |
| BTC/USD E1 | $134.38 | $-42.68 | $-42.68 | $-70.39 | $-61.19 | $-88.90 |
| BTC/USD E2 | $118.79 | $-42.68 | $-42.68 | $-85.98 | $-30.86 | $-74.17 |
| SOL/USD E1 | $400.35 | $-9.00 | $26.75 | $19.54 | $74.59 | $377.69 |

For SOL E1 the combined bundle gains **$303.10** over its matched control,
so the gain is not merely availability-based pass-through. It also recovers
most of the return lost by the prior ML filter, but still trails the unfiltered
$400.35. It takes eight trades versus fifteen unfiltered; all-book closed-trade
drawdown is about 0.726R versus 0.894R. These are limited sample trade-offs,
not proof of deployment superiority.

For BTC E1 combined features worsen net to -$88.90 versus -$61.19 for the
matched control and +$134.38 unfiltered. MA-only also trails its matched
control for BTC and SOL. There is no universal BTC/SOL enhancement.

## Prediction quality and mechanism

The combined model retains more scored SOL test winners than its matched
control: four of seven versus two. It also keeps more losses. Its fixed-entry
normalized SOL net is $396.19 versus $93.09 matched; this differs from sequential
$377.69/$74.59 because fixed original entries and flat-start sequences have
different boundary states and later opportunities.

This P/L improvement does not imply better win-probability ranking. On all
unique scored test E1 entries, combined AUC is about 0.412 versus 0.442 matched,
and Brier error is 0.27894 versus 0.27739 matched (lower is better). SOL alone
also has weaker ranking/Brier than its matched control. A few retained large
winners matter more than the binary win/loss label. Scores remain uncalibrated.

In the combined training sample, winners are farther below SMA20 (about -1.91
ATR versus -1.16), but less far below VWAP (-0.62 versus -1.19). These are sparse
countertrend/recovery associations in an already dip-oriented entry strategy,
not validated causal rules or a reason to buy whenever an indicator is crossed.
All training means and standardized coefficients are shown on the desk.

No threshold or period is adjusted after these results. Keep all indicator
arms disabled for live trading; any future improvement needs a new predeclared
experiment and fresh evidence.

## Reproduction and interface

Run `python3 scripts/study_entry_indicators.py` for a new isolated timestamped
study. Saved artifacts include source/code hashes and source bundle, genuine
VWAP source audit, five model fits, per-arm data/forecasts, all fixed entries,
all sequential decisions, full protection/exit chronology, gap partitions and
CSV/JSON exports. Never overwrite earlier research or modify worker files.

The GET-only desk supports book, feature arm, fixed-entry phase and exposure
group. Sequential results always refer to the final nine-day flat-start test.
The matched-control P/L difference is explicit. No page control trains/refits,
starts a worker, sends an order or silently changes a saved return.

Tests verify native VWAP arithmetic from positive-volume actual minutes,
SMA/slope arithmetic, prefix invariance, zero-volume handling, unavailable native
VWAP, matched training/inference masks, old-model and frozen-control parity,
all protected files, trade fractions, net P/L and partition reconciliation.
