BTC Pattern Transfer Backtest
=============================

Review the same thirty-day stock/ETF replay on the Trading Desk.

:Last Updated: 2026-11-09
:Status: Complete retrospective research; no live promotion
:Audience: Trading Desk users

Overview
--------

Open ``/pattern-backtest`` from the desk home page or Pattern Discovery. Choose
a symbol and review entry reference time/price, initial stop and effective time,
planned first target, actual exit fractions/times/prices, costs and net P/L.
The page includes all thirteen symbols, real 15-minute chronological observations,
protection history, rejected matches and CSV/JSON downloads. Zero-trade names
are shown explicitly. The page cannot run jobs or submit orders.

The fixed UTC window is October 10 through November 9 (exclusive), 2026, with
seven-day warmup. Stocks/ETFs cover twenty regular sessions, October 12–November 6.
The existing B1 similarity rule, stop, first 25% target, remainder exits and
2 bps per-side cost proxy are unchanged. No forced sale is made at window end.

Results and units
-----------------

Twelve stocks/ETFs generated three trades: TQQQ +$53.43, ASTS -$49.40 and
NBIS -$55.18 when each entry is independently normalized to $10,000. The nine
other stock/ETF names had no qualifying entry. The $10,000 scaling is a
comparison, not cash allocation or a compounded portfolio result. Actual model
units are one share per equity/ETF and one BTC for the separate reference row;
split symbols use a comparable adjusted share. Realized and unrealized figures
are separate. No position remains open in this saved window.

The unchanged fourteen-complete-consecutive-15m context requirement rejects many
morning stock candidates because ordinary overnight closures break continuity.
Across stocks/ETFs, 33 of 81 otherwise-would-open checks fail that context gate,
42 belong to an undefined family, three resemble losing lookalikes and three
are accepted. Earlier structure/risk rejections also remain available. These
restrictions were not relaxed to improve the result.

Data and interpretation
-----------------------

This is retrospective, not independent validation. BTC examples use outcomes
from this same month, and the watchlist was selected using November 9 data after
the window ends. Positive BTC replay results are not evidence of predictive
success. Current templates and the universe snapshot are saved with the run.

Equity/ETF history uses actual consolidated SIP minutes, distinct from the
forward discovery worker's IEX feed. Missing observations are never filled.
The exchange calendar defines required sessions, holidays/early closes and
New York daylight-saving times. All stocks/ETFs have complete test-session coverage. One absent AXTI minute
is in warmup, outside the tested interval. The BTC reference uses the
exact frozen source with 558 absent test minutes. Scheduled overnight closures
are distinguished from actual missing session data in trade-quality counts.

SOXX's November 5 split uses real vendor split-adjusted minutes, explicitly
labeled in the summary. A rounding-aware factor check distinguishes that event
from ordinary cent-rounding differences. The fixed $0.01 trigger is applied to
adjusted prices; raw tick/fill parity is not claimed. No share adjustment or
market price is fabricated. All twelve unaffected symbol trade paths remain
identical to the prior raw-price replay. Earlier diagnostic runs are retained.

Historical minute data is assumed available at minute end with zero extra
latency; those clocks are simulated availability, not actual receipt times or
fills. Overnight positions receive their next modeled protection check on the
next observed regular-session minute. Actual commissions, BTC trading fees,
spreads/depth, funded position sizing and broker fills are outside this model.

Frozen 0.2, P1/C records, both forward paper workers and their controls remain
unchanged. The backtest is comparison-only and submits no orders.
