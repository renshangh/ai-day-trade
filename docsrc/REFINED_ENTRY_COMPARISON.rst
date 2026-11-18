Refined A, B1 and B2 Comparison
===============================

The historical section at ``http://127.0.0.1:8799/crypto-live#refined-comparison``
compares the refined entry draft with original BTC 0.1/E1/E2 and SOL E1 over
the exact archived thirty-day period. Frozen release 0.2 and both live workers
remain unchanged. No broker or paper-broker orders are enabled.

Rules tested
------------

* A applies existing P1 independent-low confirmation before HH/HL and breakout.
* B1 uses the first independent post-D hold as its reference. Only the immediately
  following fifteen-minute candle may break that reference; later bars wait for B2.
* B2 requires the inherited rebound/HL retest and is evaluated before B1.
* A fresh qualifying shock starts a new B episode. A D breach after the first
  independent hold retires that attempt rather than moving D to rescue it.

The B1 first-reference window is an explicit interpretation fixed before the
test, not an optimized hour-count expiry. Original stop, target, exit, costs
and risk settings remain fixed; 2R is advisory. No result-driven retuning was
performed. No missing observation was interpolated or filled.

Results
-------

The period is October 10, 2026 00:00 UTC through November 9, 2026 00:00 UTC,
exclusive, with the original warmup. All four original controls reproduce.
Fixed-$10,000-per-entry normalized realized totals are:

.. list-table:: Original versus refined
   :header-rows: 1

   * - Book
     - Original
     - Refined
     - Difference
   * - BTC 0.1
     - $444.59
     - $351.11
     - -$93.48
   * - BTC E1
     - $527.95
     - $344.96
     - -$182.99
   * - BTC E2
     - $531.53
     - $351.11
     - -$180.42
   * - SOL E1
     - $1,581.86
     - $935.05
     - -$646.81

These sum independent normalized trades; they are not funded account returns.
The original 2bps/side ETF proxy excludes actual crypto fees. Closed-trade
drawdown also increases in all books. The draft is not promoted.

Trade review
------------

The page lists every removed, added, relabelled and retained trade with original
and refined entries, initial stop, first target, actual exit legs and P/L deltas.
Trade IDs can change after a new sequence; matching is by entry minute. Five
BTC entries per variant change labels only, without changing their P/L.

Select all observations, no flagged gap/context, or flagged gap/context. Each
sequence's partition is independent; missing history is explicit. Maximum
drawdown remains the labeled all-book value. Download full change/trade/exit
tables or each sequence's minute-sourced fifteen-minute ledger and signals.
GET/filter/export reads saved results without starting any job or changing
live comparison records.
