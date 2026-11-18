Original Unfiltered BTC/SOL: 90 Days
====================================

Historical returns, observed drawdowns, losing trades and cash-account illustrations.

:Last Updated: 2026-11-10
:Status: Complete; historical comparison only
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://127.0.0.1:8799/crypto-live#unfiltered-90``. Replay original BTC
0.1/E1/E2 and SOL E1 constructors with no ML, indicator gate, P1, C, adaptive
shock or new exit filter. Frozen 0.2, previous studies/selectors and both live
workers remain unchanged. No orders, real funding or broker-paper fills occur.

Period and coverage
-------------------

The ninety-day window is August 11, 2026 00:00 UTC–November 9 00:00 UTC,
exclusive, with seven days of warmup from August 4. New York boundaries are
August 10 at 20:00 EDT through November 8 at 19:00 EST. This keeps the original
study endpoint rather than changing dates while extending the lookback.

Keep the original October 3–November 9 suffix unchanged. Earlier BTC is a
validated read-only SELECT from the original Alpaca cache; earlier SOL comes
from independently archived approved market-data GETs. Source/raw hashes and
selected actual observations are saved. No shared cache or live store is changed.
No alternative vendor, synthetic observation, interpolation or carry-forward
fills a missing minute.

.. list-table:: Actual test coverage
   :header-rows: 1

   * - Asset
     - Observed minutes
     - Expected
     - Missing
     - Coverage
   * - BTC
     - 124,731
     - 129,600
     - 4,869
     - 96.24%
   * - SOL
     - 101,072
     - 129,600
     - 28,528
     - 77.99%

Every requested day has observations, but SOL is particularly sparse. Actual
zero-volume quote bars remain observations, while missing bars remain absent.
Drawdowns and fills inside gaps cannot be established. Do not present this as
ninety fully observed days or a complete downside measurement.

Cash-account illustration and original metrics
----------------------------------------------

The original reference strategy retains one initial coin per trade, all risk
parameters including the $0.01 trigger, 25%/remainder exit fractions and the
same 2bps/side ETF friction proxy. Original per-coin P/L, fixed-$10k-entry
normalized P/L and closed-trade R drawdown remain available.

A separate reporting-only account starts each book with $10,000. Buy fractional
units with available cash including entry friction; partial-sale proceeds stay
in cash until the old position closes, then reinvest. Never borrow, add capital,
overlap positions, change a fill reference or place an order. The illustration
assumes no size restrictions or market impact. Actual crypto fees, interest,
funding and taxes are excluded.

At each actual observed minute close, liquidation-value equity is cash plus
remaining units at the actual close less hypothetical exit friction. No marks
are created in missing minutes and no open remainder is forcibly sold. Maximum
observed minute-close peak-to-trough drawdown includes open positions, but can
miss intraminute and gap lows. It differs from original closed-trade R drawdown.

Fixed-$10,000-per-entry normalized P/L sums independent trades; it is not the
reinvested account return. Each strategy has separate illustrative capital,
not a combined BTC/SOL portfolio.

Results
-------

.. list-table:: Ninety-day illustrative cash accounts
   :header-rows: 1

   * - Book
     - Return
     - Max observed drawdown
     - Closed
     - Wins / losses
     - Longest loss streak
   * - BTC 0.1
     - +0.12%
     - 5.32%
     - 80
     - 38 / 42
     - 7
   * - BTC E1
     - +1.83%
     - 4.75%
     - 80
     - 38 / 42
     - 7
   * - BTC E2
     - +1.00%
     - 5.32%
     - 80
     - 38 / 42
     - 7
   * - SOL E1
     - +14.02%
     - 5.37%
     - 44
     - 22 / 22
     - 5

All books end flat at the final actual mark. With the same initial cash,
friction and observed endpoints, buy-and-hold returns +16.93% for BTC and
+13.82% for SOL, with observed drawdowns of 15.57% and 31.48% respectively.
These are historical reference simulations, not forecasts or actual returns.

All four standalone thirty-day controls reproduce exactly. Their illustrative
returns are +4.43% / +5.31% / +5.35% for BTC 0.1/E1/E2 and +16.78% for SOL E1.
The longer sample is weaker. A continuous ninety-day book can carry different
history/positions into the final month, so its trailing period cannot be
assumed identical to a thirty-day flat-start reset or subtracted as if it were.

Losing trades and interface
---------------------------

Review every net-negative closed trade with entry/exit references, initial
stop activation, D/L1 and L2, targets, stop raises, partial/remainder prices and
costs, original per-coin/fixed-notional net and R, illustrative funded entry cash
and leg P/L, holding duration and data-gap flags. Losses sort by fixed-notional
severity; all trades can be viewed chronologically or filtered to open positions.
A final stop can follow a profitable 25% partial, so final exit reason alone
does not determine whole-trade profitability.

Exposure/trade-list controls only filter records. Full-book equity, return,
drawdown, entry-type/reason breakdowns and longest loss streak remain unchanged.
Do not present a hindsight gap-free cohort as a tradable filtered account.
Daily tables use UTC dates with the last actual observed mark shown in New York
time, not official closes or filled prices. Download full minute equity,
account arithmetic, losers, original trades, exits and protection CSV/JSON.

Reproduction and limits
-----------------------

Run ``python3 scripts/prepare_unfiltered_90d.py`` to obtain/verify the independent
earlier prefix, then ``python3 scripts/study_unfiltered_90d.py`` for a new isolated
study. Long jobs are externally bounded to twenty minutes. Earlier results,
selectors, shared caches and both live workers are preserved. Source/code
bundles, frozen hashes and live PID/session identities are verified.

Real-data tests reconcile fractional cash compounding, partial/open positions,
every actual equity mark and drawdown, trade fractions and losses, source
coverage and read-only exports. No new environment variables or order client
are introduced.

Rules were developed on the overlapping recent month. This historical extension
is not prospective or genuinely out-of-sample validation. Sparse observations,
quote-based prices, unverified execution and the proxy fee model limit any
profitability or risk claim.
