# Range Trading Paper Pilot

A measured range screen, causal replay, and guarded Alpaca crypto paper runner.

**Last Updated:** 2026-10-17
**Status:** Experimental; no demonstrated trading edge
**Audience:** Contributors and strategy operator

## Overview

The pilot supports the desk's North Star of sourced, explicit trading decisions.
Its proposed performance metric is out-of-sample return after fees at a bounded
drawdown, rather than the number of orders. Weekly review should track net P&L,
drawdown, completed round trips, breakout losses, turnover, modeled versus broker
fees, rejected orders, missing data, and unprotected-position time. No performance
target has been achieved or inferred from this short sample.

`ai_day_trade/range_trading.py` screens real OHLCV and replays each symbol as a
separate hypothetical account. `ai_day_trade/alpaca_range_paper.py` connects the
same range measurements to Alpaca's paper API. It never calls a live trading
host. Existing stock day-trade code and the Trading Desk UI are unchanged.

## Range hypothesis

The current focus is NEAR and DOT, using seven calendar days of completed
four-hour candles (42 observations). Other coins require explicit ``--symbols``.
Both research and Alpaca paper commands accept ``--lookback-days`` for deliberate
comparisons. Support and resistance are
the observed 10th-percentile low and 90th-percentile high (order statistics).
Require 3–30% width, directional displacement <=40% of width, path efficiency
<=0.25, first/second-half boundary displacement <=40% of width, >=3 midpoint
crossings, >=2 separate visits to each boundary, >=80% of closes inside the box,
and the latest close inside it. A daily turnover proxy (sum of close times
base volume for the last 24 hours) must meet $1M, the user's current crypto floor.
The initial $10M setting was superseded. It is venue-specific and
is neither actual traded dollar turnover nor aggregate market volume.

Enter in the lower 15% of the range only after a rising completed close.
Target is 15% below resistance; stop is half a 14-bar ATR below support.
Require >=1.5 net reward/risk after assumed fees and slippage. Default exit on
a failed range is sell, never keep adding or convert to an indefinite holding.
These are unoptimized hypotheses, not probabilities that a box will persist.

## Replay and data invariants

Daily UTC refits use only prior observations; entries use the next observed
open. Stops and targets freeze at entry. A stop wins when both exits occur in
one bar, gap-down stops use the worse open, and entry-bar targets are withheld
because their timing is ambiguous. Entry-bar stops remain active. Time exit is
five days. Default risk is 0.25% and allocation at most 20% of the hypothetical
account. A stop prevents same-day reentry. The daily entry gate uses marked
equity; no claim is made that a gap loss can be capped at the sizing budget.

Only completed real bars are used. Duplicate, malformed, nonfinite and unaligned
data are rejected. Gaps reject replay and any affected range window. Missing
products remain unavailable. Nothing is filled forward. Snapshots and replay
results live under `reports/range_trading/`; account state lives under ignored
`trading_records/`. Fixture provenance is retained in the dated Coinbase source
snapshot. Tests never create synthetic market bars.

The original Oct 17 Coinbase snapshot contains about 30 days. The original
14-day study left only about 16 days after warm-up; switching to seven days
does not retroactively validate the model. It cannot establish profitability. Selection today is not a
historical trading result. Per-symbol replay balances must never be summed as
a shared portfolio result. End equity marks open positions without a forced
liquidation; closing fees/slippage would reduce it.

## Alpaca operation

Use existing `ALPACA_API_KEY`, `ALPACA_API_SECRET`, and `ALPACA_IS_PAPER=true`
from runtime or the repository `.env`. No new environment variables are added.
The client pins trading requests to `https://paper-api.alpaca.markets`, disables
redirects, and uses Alpaca US bars and quotes for paper decisions. Tradability
comes from Alpaca assets, not a Coinbase list. NEAR, ATOM and XLM were unavailable
in the checked paper account on Oct 17; DOT was supported.

The dedicated paper sleeve defaults to $1,000 of hypothetical capital, $2.50
modeled risk per trade, $200 maximum initial allocation per symbol, two open
positions, and a $10 daily marked-loss entry halt. Crypto buying power uses cash
and non-marginable buying power. Other strategies' positions and orders are
excluded. Fee assumption is Alpaca's published tier-one 25 bps taker rate per
side, with 10 bps assumed slippage. Coinbase replay defaults to the connected
account's observed 75 bps taker rate; maker rates are not assumed for market fills.

Fresh quotes must be <=60 seconds old, with spread <=10 bps. Before entry,
both sides of the live book must show at least the larger of $5,000 or ten
times the proposed order within 10 bps of their best price. Missing, stale or
thin books block entries. Exit orders remain available when this entry filter
fails. Buys and exits use
IOC market orders. Fractional units respect broker increments and minimum sizes.
Positions use actual broker net quantities after coin-denominated buy fees.
The cash ledger estimates sell fees and needs comparison with broker fee
activities; paper results do not establish realistic live execution quality.

The runner refreshes the screen every 15 minutes and checks exits every 30 seconds.
Measured levels can change when another completed four-hour candle arrives;
held exits stay fixed. Stops/targets are **software monitored**, not native
crypto brackets. The process and network must stay up; gaps, interruptions and
slippage can exceed planned losses. A market-data or API error stops the
process and requires inspection/restart. Do not treat it as unattended live-ready.

A local lock prevents overlapping runners on the same state file. A persisted
client-order intent precedes submission. Unknown outcomes reconcile by client
order ID; POSTs are never blindly retried. A 404 after an ambiguous submission
requires operator inspection. Pending/partial orders block new entries until
terminal reconciliation; partial fills become managed broker positions after
that reconciliation. Subminimum residuals are recorded as dust. Do not delete a
state file or change its capital while positions/orders are outstanding.

```bash
# Read-only account/data check and current screen:
python3 -m ai_day_trade.alpaca_range_paper

# Enable paper orders and run continuously in a supervised terminal:
python3 -m ai_day_trade.alpaca_range_paper --execute-paper --cycles 0

# Bounded two-cycle paper smoke:
python3 -m ai_day_trade.alpaca_range_paper --execute-paper --cycles 2

# Reproduce the Coinbase screen and independent replay:
python3 -m ai_day_trade.range_trading \
  --snapshot reports/range_trading/COINBASE_2026_10_17.json

python3 -m unittest discover -s ai_day_trade/tests -v
```

Continuous operation must be explicitly launched; building the model creates
no scheduler or service. Coinbase and Schwab live routing are future integrations,
not implemented by this pilot. Stock signals need session-aware history and
earnings/event guards before adding equities to this crypto model.

## Oct 17 liquidity review

The user confirmed the original example was NEAR cryptocurrency, not NIO stock.
Coinbase completed four-hour bars ending at 20:00 UTC imply a trailing-24-hour
close-times-volume proxy of approximately $26.68M for NEAR, $2.25M for DOT, and
$0.576M for ATOM. These are dated single-venue proxies. The initial range-shape
shortlist was withdrawn after liquidity checks; ATOM and DOT fail the tightened
$10M gate, while NEAR fails range-stability checks. No symbol in the initial
13-pair universe passes every entry condition. Alpaca's own venue volumes are
much smaller than Coinbase's; they must not be labeled as global crypto volume.

Fifteen focused offline tests passed. The bounded Alpaca paper smoke completed
two cycles with zero orders and zero managed positions. This is evidence that
the system withheld entries, not evidence of profitable fills. No continuous
runner or scheduler was installed. Public documentation build was attempted but
the local environment lacks `sphinx-build`.

## Seven-day revision and stock research

At the user's request, the active default is seven days with NEAR and DOT only.
Historical 14-day regression cases explicitly retain that setting; their
expected market measurements are not rewritten to match the new default.
Coinbase public REST has no four-hour granularity: the scanner fetches actual
hourly observations in bounded pages and aggregates a four-hour bar only when
all four hours exist. It never substitutes for a missing hour.

`python3 -m ai_day_trade.schwab_range_screen` reads Schwab's 30-minute regular
session history. It uses Alpaca's trading calendar to validate every expected
bar across completed sessions in the preceding seven calendar days. Weekends,
overnights and holidays are excluded by the calendar, without manufactured bars.
This stock screen requires average daily shares >=2M and close-times-volume
turnover >=$100M, 1–20% range width and the same repetition/drift/stability
criteria. It qualifies range geometry only, and cannot submit stock orders.
Schwab history is proof of quoted market data, not account-specific trade approval.

The Oct 17 screen covers Oct 12–16 (five completed sessions, 65 bars per stock).
AAPL, QCOM and WFC pass. UBER and CRCL lack repeated independent support visits;
their attractive-looking boundaries alone do not qualify. Earnings verification,
current-session spreads, news and broker eligibility remain entry prerequisites.
WFC reported Oct 13, inside this window, so its box crosses an earnings event;
require post-event stability before treating it as a reusable range.

Reproduce the archived stock screen:

```bash
python3 -m ai_day_trade.schwab_range_screen \
  --snapshot reports/range_trading/SCHWAB_STOCKS_SOURCE.json
```

The stock output is separate from crypto and paper positions. Crypto ranges
remain based on four-hour candles; stocks use 30-minute session candles to
avoid comparing partial US-session four-hour buckets with 24/7 crypto bars.

The fresh 20:57 UTC Coinbase aggregation reproduces the connector's seven-day
boundaries exactly: NEAR $4.7621–$5.8430 and DOT $1.1016–$1.2620. Neither passes
all range/liquidity gates. Twenty focused tests pass after the seven-day change
and the stock-session screen, including missing/duplicate stock bars and the
42-candle crypto lookback.

## Reference links

- [Alpaca crypto orders, fees and buying power](https://docs.alpaca.markets/us/docs/crypto-trading)
- [Alpaca historical bars and pagination](https://docs.alpaca.markets/us/reference/cryptobars-1)
- [Alpaca paper execution limitations](https://docs.alpaca.markets/us/docs/paper-trading)
- [Coinbase candle intervals and missing history](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
