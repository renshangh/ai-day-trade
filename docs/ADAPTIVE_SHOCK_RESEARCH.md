# Adaptive Crypto Shocks and Chronological Calibration

BTC-relative volatility scaling, a separate SOL weight, and a small time-ordered calibration experiment.

Last Updated: 2026-11-10  
Status: Complete; research only, no promotion  
Audience: Trading Desk owner and maintainers

## Overview

The North Star remains reproducible decisions on actual observations, not a
better-looking result from repeatedly fitting the same month. Study
`20261110T121223Z-adaptive-shock` lives independently under
`trading_records/btc_structure/adaptive_shock_studies/`. View it at
`http://127.0.0.1:8799/crypto-live#adaptive-shock`.

Frozen 0.2, P1, earlier studies/selectors and both live PID/session identities
are preserved. There are no broker orders, new live workers, automated
promotions, F1/F2 exit changes or trained neural-network claims.

## Volatility and the additional weight

ATR is a range measure; ATR% normalizes that range by price. Statistical beta
measures returns relative to a benchmark and includes correlation, so the SOL
weight here must not be described as measured beta. References:
[Fidelity ATRP glossary](https://www.fidelity.com/webcontent/ap010098-etf-content/16.06/help/research/learn_er_glossary_1.shtml)
and [Nasdaq beta definition](https://www.nasdaq.com/glossary/r/beta).

A common ATR multiple already scales a percentage threshold upward for a more
volatile coin. Avoid silently applying the volatility ratio twice. The explicit
extra weight is an additional owner-requested strictness penalty, not a second
estimate of ATR or beta:

`threshold_pct = K × BTC_pre_ATR_pct × max(1, asset_pre_ATR_pct / BTC_pre_ATR_pct) × W`

- BTC weight W is always 1.0; default BTC base K is 2.0, shallower than the
  prior uniform net-3-ATR draft.
- ATR-only SOL uses W=1.0. The separately declared weighted trial uses W=1.5.
  When SOL ATR% exceeds BTC ATR%, this means 2 SOL ATR versus 3 SOL ATR.
- If SOL becomes quieter than BTC, the BTC volatility floor still applies.
  Do not hard-code an assertion that SOL is always more volatile.
- A shock still requires a complete bearish fifteen-minute candle, adjacent
  complete prior candle, a new scope low and a net close-to-close decline at
  least the threshold. It is not itself an entry: B1/B2 confirmation is required.
- A non-shock is only an A candidate and must pass all original A/P1 checks.

The existing engine uses the arithmetic mean of fourteen true ranges, not
Wilder smoothing. Each pre-shock ATR context requires fifteen consecutive
complete prior fifteen-minute candles: fourteen ranges and their preceding
close. Divide by the immediately prior close, so the entire threshold is known
before the shock starts. Missing BTC or asset context means no new B shock;
no stale, synthetic or carried-forward benchmark data is substituted.

The strict prior-context requirement is shared by ATR-only and weighted runs,
so their difference isolates the extra weight. Relative to the uniform-3 control,
changing K and enforcing this context are both disclosed changes. Existing
entry lifecycle, larger-D stop/buffer, A/P1 thresholds, targets, exit variants,
position fractions and cost/risk settings remain fixed.

## November 10 case check

For the 04:00–04:15 EST impulse underlying the 04:45 examples, thresholds were
known at 04:00 and the shock could only be confirmed at 04:15:

| Asset | Pre-shock ATR% | ATR% relative to BTC | Actual net drop | ATR-only threshold | Extra-weight threshold |
|---|---:|---:|---:|---:|---:|
| BTC | 0.241671% | 1.000 | 0.514660% | 0.483342% | 0.483342% |
| SOL | 0.370724% | 1.534 | 0.670085% | 0.741447% | 1.112171% |

BTC passes the new shallow shock threshold even though that historical trade
later lost. SOL fails both. This is not a claim that either future trade is
profitable. The cases do not belong to the preceding monthly replay.

## ML principles and split

Use low-complexity chronological parameter calibration, not a flexible model
on a tiny sample. The exact grids and eligibility rules were saved before
examining this experiment's outcomes:

- Training: October 10–24, 2026 UTC, fourteen days.
- Validation: October 24–31 UTC, seven days.
- Test: October 31–November 9 UTC, nine days. All boundaries exclusive at the end.
- Candidate BTC base K: 2.0, 2.5, 3.0. Candidate SOL weights: 1.0, 1.25, 1.5.
  BTC's extra weight remains 1.0. E1/E2/0.1 exit policies are not searched.
- Development replays stop before the test boundary. Training/validation labels
  include only entries from their own phase completed before its boundary;
  unresolved labels are explicitly excluded and counted, never labeled using
  later exits. Eligibility requires at least three completed training and two
  completed validation trades, positive net R in both.
- Rank eligible candidates by validation net R minus closed-trade drawdown R.
  Ties prefer fewer parameter departures from ATR-only K=2, W=1. If none qualify,
  fall back explicitly to that baseline without claiming a learned choice.
- Write `SELECTION_BEFORE_TEST.json` before running test books. Each test book
  restarts flat with seven days of real warmup; no development position is
  inherited and no forced liquidation fill is invented at the split.

All four books select K=2, W=1 from earlier data. Thus calibration adds no
performance over the ATR-only baseline. It cannot be relabeled after seeing
that a heavier SOL weight did better on the test. These dates were studied
before this task; the split is a **retrospective chronological holdout**, not
genuinely unseen evidence. A new forward sample is still necessary. Closed-trade
R drawdown is not portfolio or intratrade drawdown. Sparse labels and unresolved
positions limit confidence; the three correlated BTC variants are not three
independent market samples.

## Results

All full-month books use October 10 00:00 UTC–November 9 00:00 UTC, with the
same October 3 warmup and actual archived observations. BTC has 558 absent test
minutes; SOL has 1,754 out of 43,200 per asset. No new data download or filled
bar is used. Tables separate unflagged versus flagged-gap/context cohorts.

Below, P/L sums independent fixed-$10,000-per-entry normalized modeled net,
not funded account returns. Costs retain the 2bps/side ETF proxy and exclude
actual spot crypto fees. Full-month and flat-start nine-day results differ in
entry state and must not be added or treated as the same sequence.

| Book | Full ATR-only net / trades | Full weighted net / trades | Test ATR-only net | Test weighted net | Test calibrated net |
|---|---:|---:|---:|---:|---:|
| BTC/USD 0.1 | $329.15 / 16 | $329.15 / 16 | $170.81 | $170.81 | $170.81 |
| BTC/USD E1 | $387.92 / 16 | $387.92 / 16 | $177.90 | $177.90 | $177.90 |
| BTC/USD E2 | $329.15 / 16 | $329.15 / 16 | $170.81 | $170.81 | $170.81 |
| SOL/USD E1 | $784.86 / 17 | $475.66 / 6 | $22.47 | $57.64 | $22.47 |

The shallower BTC draft improves on the strict uniform-3 draft, but full-month
adaptive totals remain below the original frozen baseline: $444.59 / $527.95 /
$531.53 for BTC 0.1/E1/E2, and $1,581.86 for SOL E1. Do not claim an improvement
on the original operating model. SOL's extra weight removes eleven full-month
entries and adds none; it trades less, earns less in the full month and has
lower closed-trade drawdown. Its final-nine-day result is better than weight 1,
but selecting it now using that result would contaminate the test. No parameter
was changed after viewing these outcomes.

## Adjustment and reproduction

`Settings(base_btc_atr=2.0, sol_weight=1.5)` is separate research configuration.
Supported bounds are BTC base 2–6 and SOL weight 1–3. The lower K bound preserves
the inherited shared validator's minimum 2-ATR excursion gate. Changing that
lower bound without changing/isolating the shared validator would be misleading.
No new environment variables are introduced.

The desk's inputs preview thresholds on actual saved context only; they do not
silently rerun returns, change the saved settings or apply live rules. A new
comparison can be explicitly run with:

`python3 scripts/study_adaptive_shock.py --btc-base-atr 2 --sol-weight 1.5`

Every invocation creates a new independent timestamped study and preserves its
control/source hashes. The fixed ML grid is independent of the manually selected
weighted trial, disclosed in the protocol, and never silently expanded.

The GET-only API exposes all sequence differences, stops, targets, exit-leg
fractions/P&L, per-trade pre-known thresholds, candidate sample sizes, selected
settings, flat-start test results and CSV/JSON evidence. No POST action is enabled.
Tests use real archived minutes, verify context-prefix invariance and missing
benchmark behavior, reproduce every uniform-3 control, reconcile partitions and
leg costs, preserve every protected file and prove selection ignores test scores.
