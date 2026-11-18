Adaptive Crypto Shocks and Calibration
======================================

BTC-relative volatility scaling, an extra SOL weight, and chronological testing.

:Last Updated: 2026-11-10
:Status: Complete; research only, no promotion
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://127.0.0.1:8799/crypto-live#adaptive-shock``. Frozen 0.2, P1, earlier
studies and both live workers remain unchanged. No orders or automated strategy
promotion are enabled. This is a small parameter-calibration experiment, not a
trained neural network or a demonstrated forecasting edge.

BTC baseline and separate SOL weight
------------------------------------

Use ATR as a percentage of the previous close to compare coins at different
price levels. Statistical beta is a benchmark-relative return measure; the
adjustable weight here is an explicit strictness assumption, not measured beta.

The shock threshold in percent is:

``BTC base × BTC pre-ATR% × max(1, asset pre-ATR% / BTC pre-ATR%) × coin weight``

BTC weight is always 1.0. The initial base is two ATR, shallower than the earlier
uniform net-three-ATR draft. SOL's ATR-only weight is 1.0; the extra-weight trial
uses 1.5. If SOL is more volatile than BTC, ATR scaling alone already requires
a larger percentage drop. The additional weight makes that requirement another
50% stricter. If SOL becomes quieter, the BTC volatility floor still applies.

Both assets need fifteen consecutive complete prior fifteen-minute candles for
the existing engine's arithmetic mean of fourteen true ranges. The ATR and
previous-close denominator are known before the shock starts. Missing BTC or
asset context disables a new shock; it is never filled or carried forward.
Shock confirmation still needs a complete bearish new-low candle with enough
net close-to-close decline, then B1/B2 entry confirmation. A non-shock cannot
become an A buy without the full unchanged A/P1 structure.

For November 10's 04:00 EST impulse, BTC's net drop is 0.514660% versus its
0.483342% threshold. SOL's net drop is 0.670085% versus a 0.741447% ATR-only
threshold or 1.112171% with extra weight. Thresholds were known at 04:00;
the completed shock could only be known at 04:15. These cases are outside the
preceding monthly replay, and a passed shock is not a profitable-trade guarantee.

Chronological calibration
-------------------------

* Training: October 10–24, 2026 UTC; fourteen days.
* Validation: October 24–31 UTC; seven days.
* Test: October 31–November 9 UTC; nine days. End boundaries are exclusive.
* Search only BTC base 2, 2.5, 3 and SOL extra weights 1, 1.25, 1.5.
* Only trades completed before their phase's end have labels; unresolved trades
  are excluded and counted. Require at least three completed training and two
  validation trades, with positive net R in both phases.
* Rank by validation net R minus closed-trade drawdown R. Ties prefer the
  ATR-only base-two/weight-one settings. No eligible candidate uses an explicitly
  labeled predeclared fallback rather than claiming a learned choice.
* Save the selection before replaying the test. Reset each test book flat with
  seven days of real warmup; never invent a split-boundary liquidation fill.

Every book selected base 2 and weight 1. Thus calibration did not improve on
ATR-only scaling. The extra SOL weight did better on the later test but worse
over the full month; selecting it using that test would be leakage. These
historical dates were examined before this task, so this is a retrospective
chronological holdout rather than genuinely unseen validation. Sparse trade
counts and unresolved labels limit confidence. Fresh forward evidence is needed.

Results
-------

P/L sums independent fixed-$10,000-per-entry normalized modeled net. It is not
a funded account return. Costs use the original 2bps/side ETF proxy, excluding
actual crypto fees. The full-month and flat-start test sequences differ and
must not be combined. Closed-trade R drawdown is not portfolio drawdown.

.. list-table:: Full month versus flat-start nine-day test
   :header-rows: 1

   * - Book
     - Full ATR-only
     - Full weighted
     - Test ATR-only
     - Test weighted
     - Test calibrated
   * - BTC 0.1 / E2
     - $329.15
     - $329.15
     - $170.81
     - $170.81
     - $170.81
   * - BTC E1
     - $387.92
     - $387.92
     - $177.90
     - $177.90
     - $177.90
   * - SOL E1
     - $784.86
     - $475.66
     - $22.47
     - $57.64
     - $22.47

These full-month adaptive totals remain below the original frozen model's
$444.59 / $527.95 / $531.53 for BTC 0.1/E1/E2 and $1,581.86 for SOL E1.
Improving on the strict-three-ATR draft is not proof of improving the operating
model. No settings were retuned after seeing these outcomes.

Adjustment and evidence
-----------------------

The desk's inputs change threshold previews on actual saved context only.
Saved returns and selections remain tied to the run's settings. New isolated
comparisons accept explicit settings, for example:

``python3 scripts/study_adaptive_shock.py --btc-base-atr 2 --sol-weight 1.5``

Supported research bounds are BTC base 2–6 and SOL weight 1–3. The base minimum
retains compatibility with the unchanged shared two-ATR excursion validator.
The fixed calibration grid is disclosed separately and is not silently expanded.

Use the book, period and exposure controls to inspect all changed and unchanged
entries, thresholds known before the impulse, stops, targets, fractional exit
legs and P/L. Download the CSV/JSON evidence and selection-before-test record.
The saved API is read-only: previews do not start workers, fetch quotes, create
fills or place orders. Gaps remain absent; source hashes, earlier study files,
frozen rules and live PID/session identities are verified.
