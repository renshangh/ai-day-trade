Frozen 0.2 SOL and ETH Backtest
========================================

Inspect the unchanged BTC model variants on native SOL/USD and ETH/USD history.

:Last Updated: 2026-11-09
:Status: Complete comparison-only cross-asset replay
:Audience: Trading Desk users

Overview
--------

Open ``/crypto-transfer`` from the desk home page. It shows frozen 0.2's
original 0.1, E1 and E2 variants on SOL/USD and ETH/USD, plus exactly reproduced
BTC controls. No P1, C or top-ten-library filter is used. All frozen entry,
stop, target and exit settings remain unchanged, including the absolute $0.01
trigger increment and first 25% partial sale. No result is promoted to live.

The fixed UTC window is October 10 through November 9 (exclusive), 2026, with
seven-day warmup. In New York: October 9 20:00 EDT to November 8 19:00 EST.
This matches the original thirty-day window, not a newly rolling window ending
at the request time. This is a cross-asset test on the BTC development month,
not unseen chronological validation or a prediction of future returns.

Results
-------

SOL has 35 closed trades in each variant. Realized net at fixed $10,000 entry
notional per independent trade is +$1,334.90 for 0.1, +$1,581.86 for E1 and
+$1,334.90 for E2. ETH has 46 closed and one still open per variant, with
realized +$82.87 / +$183.28 / +$82.87 and open net mark -$13.28 for each.
These are benchmark model sums, not returns on a shared $10,000 account.
E1 leads the realized sample, without any tuning or live-policy change.

The page also shows per-one-coin results; BTC/ETH/SOL unit P/L should not be
compared directly. Open remainders stay open at the cutoff; unrealized marks
are shown separately with the last observed timestamp. Closed-trade R
drawdown does not include intraholding mark-to-market account drawdown.

Costs and data
--------------

The frozen cost remains 2 bps per side as an ETF spread/slippage proxy. It is
not an actual spot-crypto fee assumption or a guarantee of execution. Actual
fees/spreads/depth may materially change the result. Alpaca US crypto minute
bars can include quote midprices and zero-volume observations.

All returned real observations are retained with raw-response/request hashes;
missing minutes are never filled. The test has 558 absent BTC minutes, 1,754
SOL and 2,248 ETH out of 43,200 expected. BTC reuses the exact archived source;
SOL/ETH are current historical downloads. No actual historical receipt clock
or exact crossing second is claimed. Same-window source revisions or gaps can
affect comparisons. All/no-flagged/flagged partitions remain separately visible.
No flagged trade exposure guarantees complete older resistance context.

Review and operation
--------------------

Select asset, variant and trade. The page lists entries, confirmed reference
lows, initial stop/effective time, planned 25% target, each actual exit fraction,
time, price, cost and P/L. Open ETH trades have no invented final sale. Stop
and structure history plus observed 15-minute chronology are included. Safe
CSV/JSON downloads cover summaries, all trades, exit legs and per-model
signals/protection/ledger. Opening the page never fetches data or starts a job.

Both forward workers, BTC-only scope, frozen release files and existing
research selectors remain unchanged. No previews, orders, account changes or
live SOL/ETH trading are enabled.
