Parent background and consumed entry comparison
===============================================

Review a separate PH5 lifecycle experiment without changing the live worker.

:Last Updated: 2026-11-15
:Status: Completed research; no promotion; combined variants remain negative
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``/btc-parent-memory``. This saved-only page compares original A/B,
original PH5 that clears parent context, and PH5 that keeps intact parent
background separately from consumed D/HL entry opportunities. Frozen 0.2,
original PH5 results and selector, P1 and the original BTC Live Paper worker
remain unchanged. Opening this page cannot start a replay, fetch quotes,
control a worker or submit an order.

An actual entry still consumes the current opportunity and requires a new
complete fifteen-minute HL after its entry candle. Each D/HL first crossing
is consumed once, even while holding, during warmup or when rejected. The
parent D and observed turn context survive an entry until the original
price invalidation or observation-gap rules clear them. A/B priority and
the one-position rule remain intact. Exit and risk methods are inherited,
with no changes to ATR, stop buffer, chase ceiling, targets or costs.

The nominated bounce
--------------------

Keeping the parent enables an earlier entry at November 15 01:44 EST at
$64,440.143. At 03:20 the new HL and five-minute break qualify, but the
earlier position is still held: the saved decision is ``held_position``,
not a second fill. The original 23:47 entry and 00:48 full exit remain
unchanged. Strict prefixes ending at the 03:20 minute reproduce this
decision without later price information.

The case uses the same historical cutoff, 05:16 EST, with the last actual
minute at 05:15. The 01:44 trade is still open there. Its net marked gain
of $1,088.99 per initial BTC is historical unrealized value, not a realized
profit, current quote or broker fill. The case lies outside the monthly
test window and is not counted in monthly results.

Monthly results and risk
------------------------

The month is the identical October 10 through November 9, 2026 UTC source,
with seven days of warmup. All nine original A/B and cleared-PH5 controls
reproduced before comparison. No thresholds were tuned after evaluation.

.. list-table:: Combined net model P/L per initial one BTC per entry
   :header-rows: 1

   * - Exit model
     - Original A/B
     - Cleared PH5 plus A/B
     - Retained PH5 plus A/B
   * - 0.1
     - $3,516.46
     - -$2,295.15
     - -$1,607.31
   * - E1
     - $4,159.67
     - -$1,357.93
     - -$8,897.28
   * - E2
     - $4,195.15
     - -$2,432.97
     - -$2,649.62

Only 0.1 improves against cleared PH5; all retained combinations remain
negative and below original A/B. The page also lists PH5-only sequences,
all trades and separate no-flagged-gap and flagged complementary groups.
This repeatedly studied month is an in-sample comparison.

The original two-basis-point-per-side proxy is included; results are not
compounded account returns, actual ETF returns or actual crypto fees.
Deeper retained parents can increase dollar stop distances even though the
risk formula is unchanged. A lower R drawdown may reflect a larger R
denominator. Compare the displayed dollar and R closed-trade drawdowns;
neither is minute-level account mark-to-market drawdown.

Review and exports
------------------

Select a model and one of five saved sequences. Review every entry, parent
D/HL confirmation, initial stop, planned target, 25% sale when reached,
remaining/full exits and P/L. Actual five-minute entry observations and the
full fifteen-minute parent-to-exit ledger show recorded events. Added,
removed and same-entry changed trades are compared against original PH5.
Historical reference and actual observation-receipt times are distinct.

Download TRADES, EXITS, PROTECTION, SIGNALS and LEDGER CSVs or result JSON.
No missing observations are synthesized or carried forward. Gaps clear
the new background; venue-only and quote-derived observations do not prove
consolidated volume or an achievable fill.

For engineering evidence see
``docs/investigations/2026-11-15_BTC_PARENT_MEMORY_COMPARISON.md``.
``scripts/retest_btc_parent_memory.py`` writes only its independent study
directory and selector, with a twenty-minute execution bound and protected
source/result/worker checks before and after the run.
