SOL model 0.1 candidate
=======================

SOL-only tape review and independent thirty-day model comparisons.

:Last Updated: 2026-11-10
:Status: Research candidate; not installed or running
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://localhost:8799/sol-live`` for SOL/USD only. The combined
``/crypto-live`` page is stopped and has no polling; historical comparisons
remain at ``/crypto-research``. The independent ``/btc-live`` worker continues
in its original session. SOL stays paused with automatic restart disabled.

Model 0.1 is an offline research candidate, not the old SOL E1 live session.
It uses no other asset's observations, ATR or weight. No live activation,
broker or broker-paper order occurs.

Candidate rules
---------------

Two declared entry changes replace the original shock/B1 qualification:

* A complete bearish new-scope-low fifteen-minute candle must have a net
  previous-close to close decline of at least 2.0 SOL ATR14. ATR is known
  before the shock starts and requires fifteen consecutive complete prior
  fifteen-minute candles. Missing context withholds the shock.
* B1 must wait for an independent complete post-D holding candle before a
  later breakout above the previous completed candle's high. D's own candle
  cannot confirm itself.

Original A/B2 structures, route priority, consumed history, larger-D stop,
ATR buffer, target construction, advisory 2R, E1 exits and 25%/75% sales keep
their settings. New entry times can produce different actual risk references.
There is no fitted ML, cross-asset input, threshold search or result-based
selection. The combined candidate was declared before replay.

Results and limitations
-----------------------

The saved thirty days are October 10–November 9, 2026 UTC exclusive, with
seven days of real warmup. Original SOL E1's thirty-five trades reproduce
exactly. Actual test coverage is 41,446 of 43,200 minutes (95.94%); missing
minutes remain absent. Full sequential comparisons:

.. list-table:: Illustrative cash accounts and observed drawdowns
   :header-rows: 1

   * - Arm
     - Return
     - Observed drawdown
     - Trades
   * - Original SOL E1
     - +16.78%
     - 3.52%
     - 35
   * - SOL net shock only
     - +13.44%
     - 2.63%
     - 20
   * - Independent hold only
     - +13.20%
     - 3.52%
     - 34
   * - Combined SOL 0.1
     - +12.20%
     - 2.55%
     - 19

The candidate reduces drawdown and activity, but lowers returns. It is not an
overall improvement and stays disabled. Retrospective separately flat-start
first14/next7/final9-day diagnostic returns are +5.25%/+3.33%/+3.25%, versus
the original +8.82%/+3.24%/+4.03%. These dates were already studied, so they
are not untouched validation. Open phase-boundary positions are marked rather
than forcibly closed.

Each cash account starts with $10,000 and reinvests available cash after a
position closes. Fixed-$10,000-entry net P/L is a separate independent-trade
sum. The 2bps/side ETF friction proxy excludes actual spot-crypto fees,
funding, taxes and market impact. Drawdown uses actual observed minute-close
liquidation equity; unobserved and intraminute lows may be worse.

The candidate retains fourteen exact original entries/exits, removes
twenty-one original entry timestamps and adds five later entries. Removed
original winners can have later replacements: original #3 becomes a smaller
delayed winner, whereas #26 becomes a larger delayed winner. Original #6's
large winner is lost, while large winners #9 and #20 are retained exactly.
Avoiding a loser alone does not establish an improved model.

Review and operation
--------------------

The SOL page has its own status, model/period selectors, every trade with
entry/stop/target/partial sales/P&L, original tape review, changed-entry
comparison, and inspected actual fifteen-minute chronology. It calls only
SOL status and saved SOL research endpoints. It has no activation or order
controls while this candidate is under review.

``trading_records/sol_structure/releases/0.1`` holds the candidate specification,
source hashes and snapshots. Study ``20261110T161551Z-sol01`` contains all
sixteen books, original-control reproduction, tape and trade differences.
See ``docs/SOL_MODEL_01.md`` for detailed cases and reproduction limits.
The original E1 install command does not activate model 0.1.
