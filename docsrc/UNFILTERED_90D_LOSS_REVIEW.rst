BTC and SOL ninety day loss review
==================================

Largest losses, winning counterexamples and the earlier sixty day performance.

:Last Updated: 2026-11-10
:Status: Read-only investigation complete; no strategy changes
:Audience: Trading Desk owner and maintainers

Overview
--------

This audit reads the saved original ninety-day study and actual minute bars.
It does not rerun strategies, fetch data or change frozen 0.2, P1, either live
worker, existing research results or the dashboard. No orders are sent.

E1 provides a common exit policy for BTC and SOL. The earlier sixty days are
August 11–October 10, 2026 00:00 UTC exclusive; the final thirty days are
October 10–November 9 00:00 UTC exclusive. The accounts really are flat at
the split, so period returns use saved boundary cash. They are not obtained
by subtracting ninety-day and thirty-day percentages.

.. list-table:: E1 period comparison
   :header-rows: 1

   * - Measure
     - Earlier 60 days
     - Final 30 days
   * - BTC illustrative cash return
     - -3.31%
     - +5.31%
   * - BTC winners / trades
     - 19 / 42
     - 19 / 38
   * - BTC average net winner / loser, fixed $10k entry
     - +$26.01 / -$35.97
     - +$61.92 / -$34.13
   * - SOL illustrative cash return
     - -2.36%
     - +16.78%
   * - SOL winners / trades
     - 4 / 9
     - 18 / 35
   * - SOL average net winner / loser, fixed $10k entry
     - +$62.93 / -$97.35
     - +$127.87 / -$42.34

Returns use an illustrative $10,000 cash account with available-cash
reinvestment and original partial sales. Individual trade dollars instead
normalize each entry independently to $10,000. The original ETF proxy cost
is 2bps per side; actual spot-crypto fees and market impact are excluded.

Losses and winning counterexamples
----------------------------------

The five largest E1 losses per asset are reviewed, together with nearest
same-asset, same-route, same-period winners and large winners from each
segment. Matching is descriptive and uses known outcomes; it is not a causal
experiment or proposed trading filter. IDs refer to the ninety-day book.

* BTC #47 loses $94.57 per $10,000 entry in eight minutes, but an observed
  minute opening recovers entry sixteen minutes after its stop. BTC #42
  also recovers later. These are stopped trades followed by later recoveries.
* BTC #20 and #22 have little observed upside after entry and do not recover
  entry within two hours after exit. #22 exits through the existing failed-
  rebound rule before its original hard stop.
* SOL #28 loses $161.30 after ten minutes despite an independent complete
  post-D holding candle. The following two hours' observed highs all stay
  below entry. A separate holding candle alone does not eliminate failure.
* SOL #5 starts with a 4.16% price-risk distance. Its original stop is raised
  twice before exit, so the $145.71 loss is not a full initial-stop loss.
  Partial context and 316 missing held minutes limit path conclusions.
* SOL #9 loses $141.13 after nine minutes despite a 7.760 initial target
  reward/risk ratio. SOL #14 also fails despite a steep 3.809-ATR net shock.
* BTC winner #44 has newly confirmed D in the immediately preceding candle,
  like several fast losers, yet makes $268.66. SOL winner #29 remains below
  entry through several early candles while D holds, then makes $323.39.
  SOL winner #18 also has an early red candle and earns $420.62.

Those dollar figures are simulated net reference outcomes, not broker profits.
All detailed times in the investigation are New York minute intervals; the
completed-minute observations become available one minute later. Retrospective
fifteen-minute highs and closes are not known before the candle ends.

Why the earlier results are weaker
----------------------------------

Earlier BTC winners are 58% smaller on average, with only a modest hit-rate
decline. Nineteen earlier winners contribute $494.11, versus $827.30 of losses.
The earlier forty B1 trades total -$349.37; the two A trades total +$16.18.
Earlier SOL has both smaller winners and larger losers. The three largest
final-month winners contribute more than the month's entire BTC net, and
about 64.8% of SOL's net, so profitability is concentrated.

The saved earlier-period buy-and-hold price paths rise 29.12% for BTC and
43.63% for SOL, while the bounce strategies lose money. A broad downtrend
alone therefore cannot explain these results. Costs matter, but both earlier
books are already negative before the original friction proxy.

Earlier minute coverage is 95.01% for BTC and 69.01% for SOL, compared with
98.71% and 95.94% later. All nine earlier SOL entries have partial context;
there is no unflagged early SOL cohort. Earlier BTC's seventeen unflagged
trades still lose $287.28, so data flags alone do not explain its loss.
Missing observations remain absent; drawdown and excursion estimates cannot
see unknown gap moves. Zero-volume entry references occur in winners too.

The recently developed rules overlap the favorable final month. This
historical extension is informative but not prospective validation. No new
entry or exit filter is established by comparing these examples.

Detailed evidence
-----------------

See ``docs/investigations/2026-11-10_UNFILTERED_90D_LOSSES.md`` for the ten
loss reviews, exact entry/stop/exit prices, stop raises and winning examples.
Reproduce the saved-trade calculations with::

    python3 scripts/audit_unfiltered_90_losses.py

The output directory ``reports/unfiltered_90_losses_2026_11_10/`` contains
``AUDIT.json``, ``PERIODS.csv``, ``COHORTS.csv``, ``ALL_E1_TRADES.csv``,
``CASES.csv``, ``WINNER_PAIRS.csv``, ``PROTECTION.csv``, ``CASE_1MIN.csv`` and
``CASE_15MIN.csv``. The twenty-seven selected cases contain 10,997 actual
minute rows and 785 aggregates. Overlapping windows repeat actual rows under
different case IDs; missing bars are never generated. Original study and
strategy hashes plus both worker identities are checked before and after.
