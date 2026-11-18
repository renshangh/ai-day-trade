Pattern Discovery and Paper Lab
================================

Find entry-time analogues of ten reference trades and track local simulations.

:Last Updated: 2026-11-09
:Status: Draft 2; experimental forward local paper comparison
:Audience: Trading Desk users

Overview
--------

Open ``/pattern-discovery``. Ten winning BTC examples and seventeen losing B1
lookalikes come from the original frozen 0.2 baseline. The ranking covers all
38 completed trades, including flagged results. The third-ranked October 29
22:15 trade has conditional P/L due to data gaps and remains visible with
matching disabled; nine unflagged examples enable matching. P1 has the same
ten winning entries. The previous clean-only draft is archived. All ten winners belong to the
same B1 first-stabilization family. This is retrospective example selection,
not proof of future profitability or ten separately validated strategies.

The independent worker scans BTC/USD and an editable stock/ETF list. A fresh
qualified B1 can start a **local normalized paper position**, followed by
the inherited first-25% target and remaining-75% protection/structural exits.
It never sends Alpaca paper-account orders or live brokerage orders. Frozen
0.2, P1, original C and the running original BTC comparison remain unchanged.

Matching and evidence
---------------------

The scanner uses only evidence known before or at the modeled entry: impulse
size/ATR, D extension/ATR, stabilization range/ATR, body/range, close position
within that range and time since D confirmation. Outcomes and future bars are
excluded. Log-transformed positive ratios/age and raw candle fractions use
unweighted mean absolute distance. The nearest winning example must be closer
than the nearest losing example and inside the library's maximum leave-one-out
nearest-positive radius. Ties reject. These draft choices are not a probability.

The page shows ten complete reference cards, scan coverage, decision/detection
times, nearest examples, skipped reasons, local positions and actual modeled
exit legs. It also exposes the source-pinned reference JSON. Training ends at
the original saved window; activation is a later future full minute. Delayed
catch-up signals cannot become backdated paper entries.

Data and limits
---------------

BTC uses Alpaca US crypto minutes. Stocks/ETFs use explicitly labeled IEX
single-venue raw minutes in regular weekday hours. Missing minutes are never
filled, and insufficient context or stale observations prevent entries. The
default list is BTC/USD, FN, AXTI, COHR, LITE, CRCL, SPY and QQQ; this is not an
account-holdings synchronization. Up to 24 symbols may be configured. Symbols
with open local paper positions must remain listed for continued processing.

BTC retains its existing target method. The separate unvalidated equity
transfer draft selects a known prominent 15-minute peak with two complete
neighbors on each side and at least one entry ATR prominence, minus 0.10 ATR.
This is explicitly different from BTC hourly target construction. Missing or
nonpositive net target space rejects. The 2R threshold remains advisory.

One normalized unit per position and the original 2 bps per-side ETF cost proxy
are comparison conventions. They are not an allocated account, actual crypto
fees or executable stock fills. No combined cross-symbol account return is
claimed. Unrealized figures use the displayed last observation and can be stale.

Selecting liquid movers
-------------------------

Run ``python3 scripts/screen_pattern_universe.py`` to review a new screen;
``--apply`` updates the independent paper scan list, preserving symbols with
open local positions. This is a bounded 309-name research pool, not the whole
market and not an installed daily refresh service. Saved source/omission details
are retained. The page offers selected movers, all qualified reserves and all
measured names, including explicit rejection reasons and SPY/QQQ benchmarks.

The screen requires exact last-64 completed exchange-calendar sessions from
consolidated SIP daily adjusted bars. It computes beta from 63 daily returns
against SPY, and Wilder ATR14 divided by the last close. Both 5/20-session
averages must exceed $500M/day and 5M shares/day; beta must be at least 1.25 and
ATR at least 3% of price. Missing sessions are never filled. Passing rows rank
by ATR%, then dollar volume; select up to eight stocks and four positive-beta
ETFs, plus BTC/USD. These are explicit research settings, not optimized returns.

November 9 results: 58 qualify, eight of 309 are unavailable. Selected stocks:
CIFR, AXTI, IREN, LITE, CRDO, CRWV, ASTS, NBIS. Selected ETFs: SOXL, TQQQ, SOXX,
SMH. Other passing names remain reviewable. SPY/QQQ are below the ATR cutoff.
Leveraged/inverse funds have visible daily-target labels; inverse ETFs remain
review-only in this positive-beta selection. Measured beta does not equal a
fund's leverage multiple. High ATR is not predicted profit, and overlapping
semiconductor/AI exposures do not create independent portfolio opportunities.
Manual watchlist additions do not imply a passing screen. Stops/exits unchanged.

Running the independent worker
------------------------------

From the checkout::

    python3 scripts/run_pattern_discovery.py --library
    python3 scripts/run_pattern_discovery.py --worker
    python3 scripts/run_pattern_discovery.py --status

The worker polls every minute and continues with the page closed. It saves real
observations and original receipt times, reconstructs the same local book after
restart, and refuses another process or a changed reference library. This draft
does not install a new login service; start the discovery worker separately
after restarting. The existing BTC login service remains independent.

``Process new observations`` pauses or resumes this independent model only.
Pausing stops model entries and exits while retaining saved records. Saving a
scan list during a running scan asks you to retry after that cycle finishes.
The page accepts no account, broker order or strategy/risk parameter changes.
