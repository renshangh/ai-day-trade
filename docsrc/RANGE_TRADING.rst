Range trading paper pilot
=========================

An experimental crypto range model with Alpaca paper execution.

:Last Updated: 2026-10-17
:Status: Experimental
:Audience: Strategy operators

Overview
--------

On-demand discovery
~~~~~~~~~~~~~~~~~~~

The Trading Desk home page has a **Range Discovery** section. It is also
available under **Range Trade Discovery** on the sector board at
``/board?view=range-discovery``. Select **Discover candidates** to scan fresh
Schwab stock history and Coinbase crypto history. Opening the panel shows the
latest dated scan without automatically requesting new provider data.

The **Stock range** selector offers **45 days · recent ranges** and
**2 years · long-term boxes**. Select **Discover candidates** after changing it.
Crypto remains on the same 14-day / four-hour model in both modes.

Two-year stocks use 730 calendar days of split/dividend-adjusted consolidated
SIP daily prices across a reviewed pool of 332 stocks. Every expected completed
trading session must have real data. Qualification requires at least three full
swings, including one in each annual half, boundary movement <=60%, at least
80% overall containment, at least 50% containment in each quarter, and the latest
close inside the range. Both five- and 20-session average volume must reach
$100M and 2M shares. The rounded width minimum defaults to 15%.

A full swing in the latest 126 sessions improves ranking. Missing recent swings
and start-to-end drift do not automatically disqualify long-term boxes. The
one-swing Needs review list is available only in the 45-day mode. Qualified
long-term rows include a **Review two-year price charts** section showing the
actual completed daily closes and measured bands. Temporary range breaks stay
visible. These are research matches, not automatic entry signals.

The rules below describe the existing 45-day stock and 14-day crypto modes
unless explicitly marked as two-year rules.

Select any snapshot symbol, or its mini-chart caption, to load the detailed
chart underneath. The first qualified symbol loads automatically. Stock and
crypto selections stay on the desk and retain the exact discovery interval:
daily for two-year stocks, 30-minute regular sessions for 45-day stocks, and
four-hour candles for 14-day crypto. The chart includes the measured range band,
candlesticks, volume, RSI and MACD, with the source and data cutoff labeled.
Unavailable or revised history clears the prior candles and shows an error;
it is never replaced with another symbol or timeframe. The home panel links
to this same asset-aware chart on the board.

The default discovery rule rounds the range ratio up to a whole percentage
and requires **at least 15%**. Thus DOT at 14.56% rounds to 15% and passes the
width filter only. Both values appear; exact 14% fails and exact 15% passes.
The formula is ``(resistance - support) / support * 100``. This is gross price
distance, not expected profit. Threshold and market scope can be changed before
scanning. Dollar volume is mandatory: crypto must have at
least $1M in estimated 24-hour dollar volume; stocks need at least $100M and
2M shares per completed session on average. Dollar volume is the sum of each
candle's close times its traded units. Missing or thin volume excludes a match,
even if its width passes.

Discovery uses **14 calendar days for crypto** (84 completed four-hour bars)
and **45 calendar days for stocks** (completed 30-minute regular-session bars).
Support is the observed 10th-percentile low; resistance the observed
90th-percentile high. No missing candles are filled.

The boundary-movement check compares the two halves of the full window;
the larger boundary change divided by the full range width must be <=60%.
Start-to-end movement is the absolute first-to-last close change divided by
that width, limited to <=40% for crypto and used for stock ranking.
Trend efficiency must be <=25%, containment >=80%,
with at least three midpoint crossings and two distinct visits at each edge.
Crypto retains the 3–30% width/midpoint guard and net reward/risk >=1.5 after
assumed 75 bps fees and 10 bps slippage per side. Stocks retain the 1% minimum; widths above 20% prompt a volatility advisory.

The latest **seven calendar days** must have at least 80% of closes inside
the longer box. A recent full swing is mandatory for crypto and a ranking
bonus for stocks. Two full swings are required for qualified candidates.
Stocks with exactly one full swing and all other mandatory checks passing
appear separately under **Needs review**, never as qualified trades. Zero-swing
stocks remain excluded. Start-to-end movement and unusually wide stock ranges
produce ranking penalties/advisories instead of automatic rejection.
The stock ranking score is an ordering aid, not a return forecast.
Stock dollar/share liquidity uses the latest seven days of completed sessions;
crypto liquidity continues to use the latest 24 hours. Old saved results require
a fresh scan before they can qualify under these rules.

Discovery covers a reviewed pool of 23 coins and 52 stocks, with the full lists
under scan coverage. Candidates must also have stable boundaries, limited
trend efficiency, a latest completed close inside the box, and at least two full
back-and-forth swings. Completed closes in the outer 20% zones establish visits;
consecutive visits to one edge count once. Support to resistance and back (or
its reverse) is one full swing. A single fall from a weekly high cannot qualify.

One-swing stock prospects appear separately under **Needs review**. Remaining
failures appear under **Disqualified moves — not candidates**, with counts
and reasons. Saved rows without swing evidence require a fresh scan. Fresh
spread, depth and earnings/news review remain necessary. Results show actual source
dates, provider omissions and Alpaca paper availability when verified. Discovery
does not place orders or change the NEAR/DOT paper watchlist.

Paper model
~~~~~~~~~~~

The range pilot focuses on NEAR and DOT, looking for repeated reversals inside
a measured seven-day box of 42 completed four-hour candles. Use
``--lookback-days`` and ``--symbols`` for explicit changes.
It buys near support after a rising completed close, sells below resistance,
and exits a failed range or a position held for five days. It does not average
down or assume that a past range predicts the next few days.

Start with a read-only screen::

    python3 -m ai_day_trade.alpaca_range_paper

Enable a bounded paper test::

    python3 -m ai_day_trade.alpaca_range_paper --execute-paper --cycles 2

Run a supervised paper process until interrupted::

    python3 -m ai_day_trade.alpaca_range_paper --execute-paper --cycles 0

Use the existing ``ALPACA_API_KEY``, ``ALPACA_API_SECRET``, and
``ALPACA_IS_PAPER=true`` configuration. Trading endpoints are fixed to Alpaca
paper. The command has no live mode. Both the model and the process remain
experimental; building them does not install an unattended service.

Selection and risk
------------------

Only Alpaca-supported USD crypto pairs are eligible. Four-hour candles must be
complete and contiguous, with repeated visits to support and resistance,
limited drift, stable boundaries and at least 1.5 reward/risk after modeled
fees and slippage. Missing observations are never replaced. The $1M daily
turnover filter is a venue-specific close-times-volume proxy, not aggregate
crypto liquidity. The screen can correctly return no entries.

Entry also requires fresh bid/ask and order-book observations, at most 10 bps
spread, and at least $5,000 or ten times the order value on each side within
10 bps of the best price. Missing or thin books block entry.

Defaults use a hypothetical $1,000 paper sleeve, 0.25% risk per trade, at most
20% initial allocation per symbol and two positions. A $10 daily marked-loss
entry halt prevents further entries. Stops cannot guarantee a maximum loss.
The paper cost assumption is 25 bps per side and 10 bps slippage. Crypto fees
need reconciliation with broker activities before assessing net performance.

History refreshes every 15 minutes. Exits are checked every 30 seconds.
Stops and targets are monitored in software, so they require a running process
and a working connection. They are not broker-hosted crypto bracket orders.
Pending submissions reconcile by client order ID without blind retries. An API
failure stops the process for inspection; do not leave it unattended.

Results and limits
------------------

Current results and source bars are in ``reports/range_trading/ALPACA_LATEST.json``
and ``ALPACA_LATEST_SOURCE.json``. Private order state lives in
``trading_records/range_paper_state.json``. Do not reset state while orders or
positions remain outstanding. Other strategies' holdings are not adopted.

``python3 -m ai_day_trade.range_trading --snapshot PATH`` produces a separate
historical paper account for each symbol from a dated real-data snapshot.
Replay refits daily using prior data, freezes exits after entry and resolves
ambiguous exit bars conservatively. These account returns must not be combined
as one portfolio. Short replay samples and paper fills do not prove an edge.
Coinbase and Schwab live execution are not included. A separate read-only stock
screen is available with ``python3 -m ai_day_trade.schwab_range_screen``. It
reads Schwab's 30-minute regular-session history across seven calendar days,
checks completeness against the broker calendar, and requires at least 2M
average daily shares and $100M average daily turnover proxy. Its output is
research only: earnings, news, executable spreads and broker eligibility need
review before a trade. Weekends and holidays are never filled with fake bars.
