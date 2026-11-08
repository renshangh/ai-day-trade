BTC Structure Retest
====================

A read-only thirty-day BTCUSD signal experiment and spreadsheet.

:Last Updated: 2026-11-08
:Status: Research; no qualified entries or empirical exit validation
:Audience: Trading Desk users and research maintainers

Overview
--------

The primary workbook now includes the owner's requested V1.2 important-swing
revision. It uses completed hourly peaks, two hours of confirmation on each
side, at least one hourly ATR of rise and decline, and merged zones of
plus/minus 0.15 hourly ATR. All other entry, stop and 2R requirements remain
unchanged. The original V1.1 result described below is retained as history.

Across the same 114 original signals, 14 pass the revised 2bps price screen.
With one position at a time, ten model trades close: one win and nine losses,
for -6.719R in total. Four independent passes occur during an existing position.
These results remain in-sample and do not validate profitability. The XLSX
preserves old and new targets and adds trade-by-trade exit legs. No real orders
are created. Reproduce this update with:

.. code-block:: bash

   python3 scripts/retest_btc_major_resistance.py
   python3 -m pytest trading_desk/tests/test_btc_structure_retest.py -q
   node scripts/update_btc_major_workbook.mjs

The November 8 study uses completed Coinbase BTC-USD fifteen-minute bars around
the clock, as requested by the owner. It records 2,880 complete test bars from
October 9 at 16:00 UTC through November 8 at 16:00 UTC (exclusive), plus seven
warmup days. No missing bars were interpolated or carried forward.

V1.1 quantifies the learning manual's unfinished higher-low, buffer, expiration
and resistance choices. It is a mechanical interpretation, not validation of
the complete discretionary method. In particular, treating every confirmed
local high over seven days as resistance may be overly restrictive; no one-hour
trend filter or optional acceleration exit is tested.

All 114 completed breakout candidates fail the two-times net reward/risk screen
at zero, two or five basis points of assumed friction per side. There are no
entries. Win rate, trading profit and the staged exit method cannot be evaluated
from this run. It is not ETF realized performance and creates no orders.

Review and reproduction
-----------------------

The repository's ``docs/BTC_STRUCTURE_RETEST.md`` contains the exact rule,
causal timing, execution assumptions, current-chart references and limitations.
The spreadsheet and request provenance are stored under
``reports/btc_structure_2026_11_08/``. Its five sheets cover the summary,
candidates, current candle audit, parameters and original observations.

Editable spreadsheet costs and minimum reward/risk recalculate screening, but
do not rerun structural identification or create historical fills. The workbook
is a dated snapshot, not an automatic refresh or trading agent.

.. code-block:: bash

   python3 scripts/btc_structure_retest.py --as-of 2026-11-08T16:00:00Z --days 30 --output reports/btc_structure_2026_11_08
   python3 -m pytest trading_desk/tests/test_btc_structure_retest.py -q
   node scripts/build_btc_retest_workbook.mjs

The scripts never import broker order clients. Missing source observations are
reported, never synthesized. A real ETF study must separately model its own
quotes, market hours and spread/slippage despite applicable zero commissions.
