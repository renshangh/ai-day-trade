BTC live models on IBIT regular session history
===============================================

Exact-rule controls and a separate exchange-session clock comparison on actual ETF prices.

:Last Updated: 2026-11-10
:Status: Historical research complete; no live promotion
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``http://localhost:8799/ibit-lab``. Original BTC live 0.1/E1/E2 models
are tested on IBIT's own consolidated SIP raw minute prices, alongside exact
controls. The selected holding policy carries positions overnight. The
running BTC worker/session and frozen 0.2 remain unchanged; SOL stays paused.
There is no IBIT live worker or broker order.

Sessions and data
-----------------

The studied month is October 10–November 9, 2026 UTC exclusive, with seven
calendar days of real warmup. Expected minutes follow the actual exchange
calendar, normally 09:30–16:00 America/New_York weekdays, accounting for
holidays, early closes and DST. Twenty test sessions contain all 7,800
expected minutes; warmup plus test contains all 9,750. Extended hours are
excluded. There is no in-window split or substituted/filled observation.

No daily liquidation is imposed. Stop/exit references can act only on real
regular-session observations. A stop gapped through at opening uses the
observed opening reference. No overnight protection or auction fill is
assumed. Equity marks are recorded only for actual observed minute closes.

Calendar adaptation and controls
--------------------------------

The exact BTC constructors find eleven candidates but zero trades, because
their continuous multi-hour resistance structures cannot form on this tape.
Their legacy clock-gap count is not an actual source-coverage failure.

The separate adapted arm excludes closed intervals from missing-minute
counts. Higher-timeframe resistance uses four actual complete RTH fifteen-
minute bars per trading-hour block and sixteen per four-trading-hour block.
These blocks may span closures, retaining all real constituent timestamps.
They are not ordinary wall-clock hourly chart candles. A block becomes known
only when its final actual constituent ends.

Original peak confirmation, prominence, zone width/merging, target buffer,
lookback settings, A/B1/B2 entries, aggressive B1, consumed history, parent-D
stops, advisory 2R, 25% first target and 0.1/E1/E2 exit settings remain
unchanged. Original fifteen-minute entry structures still reset at overnight
wall-clock discontinuities; stale prior-day bars do not cause opening buys.
There is no fitted threshold, ML filter or parameter search.

Results
-------

.. list-table:: Historical illustrative accounts
   :header-rows: 1

   * - Arm and model
     - Return
     - Observed drawdown
     - Trades
   * - Exact controls, all three models
     - 0.00%
     - 0.00%
     - 0
   * - Session adapted 0.1
     - +0.14%
     - 2.14%
     - 4
   * - Session adapted E1
     - +0.30%
     - 1.98%
     - 4
   * - Session adapted E2
     - +0.14%
     - 2.14%
     - 4

Every adapted model has one winner and three losers. E1 ending equity is
$10,030.49 from a separate $10,000 all-cash, available-funds reinvestment
illustration. Its sum of fixed-$10,000-entry net P/L is $31.62, a different
measure. Costs retain the 2bps/side ETF spread/slippage proxy; actual spreads,
impact, taxes and fills are unverified. Observed minute-close drawdown can
miss worse intraminute or off-hours paths. This previously studied month
and four trades cannot establish an enduring predictive edge.

The overnight winner enters October 15 at 10:08 EDT and exits during the
next session's 09:30 minute. Its failed-rebound floor is $46.355; the actual
opening is $46.37, followed by an intraminute floor break. The reference exit
is $46.355, not the opening print. Exact crossing seconds and actual fills
remain unverified. All books end flat without forced endpoint sales.

Review and reproducibility
--------------------------

The page lists all six books, each actual entry/stop/target/exit and P/L,
inspected fifteen-minute chronology, and rejected candidates. CSV/JSON
downloads retain original reference times, stop raises and actual equity.
No page request starts a worker or submits an order.

See ``docs/IBIT_RTH_BACKTEST.md`` for each trade and calendar assumptions.
Study ``20261110T235316Z-ibit-rth`` contains pinned protocols, source hashes,
six books and summary exports. ``python3 scripts/study_ibit.py`` reproduces
into a separate study from the saved archive without fetching new quotes.
