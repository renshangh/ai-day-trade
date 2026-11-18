# Trading Desk Range Trade Discovery

Generate a dated stock and crypto research shortlist on demand.

**Last Updated:** 2026-10-17
**Status:** Active research feature; no order execution
**Audience:** Trading Desk users and contributors

## Overview

Open **Range Discovery** on the Trading Desk home page, or **Range Trade
Discovery** on `/board?view=range-discovery`. Select **Discover candidates** to
request fresh measurements. Opening a page reads local status and saved results;
it does not start a provider scan. This supports the desk's North Star of
decisions backed by dated observations and explicit trade gates. The existing
crypto focus remains NEAR/DOT. Discovery never expands the paper watchlist.

## Stock window selection

**Stock range** offers **45 days · recent ranges** and **2 years · long-term
boxes**. Crypto keeps its existing 14-day/four-hour rules in either mode.
Changing the selector filters the displayed stock results; select **Discover
candidates** to fetch the selected mode. Opening the page never fetches vendor
history. The last selected scan is restored with its mode and original dates.
The 45-day mode keeps its reviewed 52-stock pool and one-swing review list.
The two-year mode covers 332 reviewed stocks from the sector/theme constituents,
the short-window pool, and additional liquid names. It is a bounded pool.

Two-year stock rules:

- 730 calendar days of completed daily bars, checked against every expected
  trading session. No missing, duplicate, malformed or stale observations.
- Observed 10th-percentile lows / 90th-percentile highs define the box. Default
  rounded-up range ratio >=15%; the existing width selector remains available.
- At least three full close-confirmed swings between the outer 20% zones,
  including at least one full swing in each chronological half of the history.
- Boundary movement between halves <=60% of full width.
- At least 80% of all daily closes inside the box; at least 50% in **each** of
  eight chronological quarters. Latest completed close must remain inside.
- Both 5-session and 20-session averages must reach $100M close-times-volume
  and 2M shares. The table shows 20-session averages plus the 5-day dollar figure.
- A full swing in the latest 126 sessions improves ranking, not qualification.
  Start-to-end drift is informational. There is no automatic maximum-width gate.
- Ranking = 100 points for a recent 126-session swing, plus 10 times the full
  swing count capped at ten, plus 20 times (1 - boundary movement capped at one).
  This is an ordering aid, never an expected return or probability.
- The one-swing review list belongs only to 45-day mode. A two-year range needs
  three full swings; incomplete evidence cannot be downgraded into review.

Long-term data uses consolidated Alpaca SIP, split/dividend adjusted. There is
no IEX-volume fallback. Daily histories are fetched in batches of 70 with at
most three workers, with bounded pagination and detection of repeated tokens.
A failed batch is surfaced as unavailable. Real source observations are saved
atomically to `reports/range_trading/LONG_RANGE_SOURCE_LATEST.json` for audit.
Qualified rows carry their actual daily closes for the **Review two-year price
charts** section. These charts preserve temporary excursions outside the box.
Prices are adjusted observations, not absolute unadjusted historical highs/lows.

This long-term mode is retrospective pattern discovery inspired by the RBLX
example, not a validated predictive model. Earnings/news, spreads, depth and a
fresh support reaction still require review; discovery does not enable orders.

## Range rule

`range_ratio = (resistance - support) / support * 100`.
The rule is **round up to a whole percentage, then require >=15%**. It is
inclusive, preserving DOT at 14.56% ->15%. Exact 14% fails; exact 15% passes.
The exact ratio (displayed to two decimals) and rounded-up value both appear.
Threshold is editable from 1 to 100 whole percentages. Decimal arithmetic avoids
binary artifacts at integer boundaries. Width is gross price distance, not an
expected return or return after fees.

## Discovery versus entry

Crypto boundaries use 14 calendar days (84 completed four-hour candles); stock
boundaries use 45 calendar days of completed regular sessions. Both use observed 10th-percentile lows and 90th-percentile highs.
Candidates must pass **all** width, liquidity and range-quality checks. Crypto
requires >=$1M over 24 hours; stocks >=$100M and >=2M shares per session.
Boundaries must be stable and the latest completed close inside the box.
Crypto retains the 40% directional-drift limit; stock drift affects ranking. Existing efficiency, containment, boundary-visit and
midpoint-crossing checks remain mandatory.

Qualified candidates require **at least two completed full back-and-forth swings**.
Stocks with exactly one full swing can appear in **Needs review**, provided
all other mandatory checks pass. Zero-swing stocks remain excluded.
Completed closes establish visits to the outer 20% zones. Consecutive closes in
one zone count as one visit. Support → resistance → support (or the reverse)
counts as one full swing; two full swings require five alternating visits.
Intrabar highs/lows cannot establish ordering and never count as full swings.
Occasional historical overshoots remain visits; separate containment and
latest-close checks guard against unstable or broken boxes.

The main table and qualified count exclude every failure. **Disqualified moves
— not candidates** shows rejected boundaries, latest close, completed swing
count and reasons. There is no switch bypassing these required checks. Old
saved rows without version-7 longer-window and recent-swing evidence fail closed until a new scan.
Backend status returns separate `candidates`, `needs_review` and `disqualified` lists; the UI
independently enforces the same evidence requirement. No row is trade-ready:
fresh spreads, depth and earnings/news still need review.

The real ASTS/MARA review shows resistance → support only, zero full swings
and each latest close below its lower boundary. Generic behavior gates reject
them; there is no ticker blacklist. Real QCOM bars provide a positive control
with five alternating visits and two full swings, while its narrow width still
fails the default 15% rule. NEAR/DOT stay on the research watchlist and receive
no exemption from the new candidate requirements.

The crypto floor was lowered from $10M to $1M at the user's request. DOT's
observed ~$2.25M passes; ATOM's ~$576K does not. A large coin count alone is not
a liquidity failure: 100,000 units at $0.01 is $1,000 notional. No minimum coin
price or maximum unit-count exclusion is imposed. Fresh spread and book-depth
checks remain necessary before paper entries. Older saved reports can contain
badges or warnings from the prior floor; the UI recomputes the volume gate from
observed dollar amounts, and a new scan regenerates the model warnings.

The bounded pool has 23 reviewed Coinbase USD coins and 52 reviewed stocks.
Complete lists appear under scan coverage. Choose both, crypto only or stocks
only. This is not a whole-market search. Schwab quotes are not account-specific
trade permission. Crypto paper availability is separately verified from Alpaca's
active assets; unavailable verification remains unknown.

## Retained checks and recent confirmation

- Range width: `(resistance - support) / support * 100`, rounded upward, >=15%.
- Boundary movement: calculate support/resistance separately in each half of
  the full window; the larger absolute boundary change divided by full width
  must be <=60%. Crypto compares two seven-day halves. Stocks split completed
  session bars into two approximately equal halves (roughly 22–23 calendar days).
- Start-to-end movement: absolute first-to-last completed close change divided
  by full width must be <=40% for crypto. For stocks this is a ranking
  factor and values above 40% produce an advisory, not rejection.
- Trend efficiency: absolute net change / sum of absolute close changes <=25%.
- At least three midpoint crossings and two distinct visits near each boundary.
- At least 80% of full-window closes inside the box; latest close inside it.
- At least two full close-confirmed swings for qualified candidates; stocks
  with exactly one full swing are review prospects, never qualified trades.
- Latest seven calendar days: at least 80% of recent closes inside the
  **long-window** box for both markets. At least one recent full swing is
  mandatory for crypto; for stocks it improves ranking but is not required.
  This operational definition of recent confirmation prevents old levels from
  qualifying solely on historical width. It does not refit a smaller box.
- Crypto keeps the existing 3–30% width/midpoint guard and modeled net reward/risk
  >=1.5 after 75 bps fee and 10 bps slippage per side. Stocks retain a 1% minimum
  width/midpoint guard; widths above 20% produce a volatility/position-size
  advisory instead of rejection. These are research assumptions, not executable quotes.
- Liquidity remains recent: crypto >=$1M trailing 24h; stocks >=$100M and >=2M
  shares per completed session averaged over the latest seven calendar days.

Rows expose `lookback_days`, `drift`, `stability`, `efficiency`, `containment`,
`boundary_visits`, `completed_cycles`, `recent_completed_cycles`,
`recent_containment` and `recent_range_pass` for review. Qualification version 7
invalidates older seven-day-only pass badges. Missing full-window observations
are omissions, never padded or replaced with a shorter window.

The goal is better paper returns after costs with controlled drawdown and
repeatable completed swings. Longer windows are hypotheses to compare with
seven-day results, not a claim of improved profitability. Daily rescans refit
research boundaries; they do not move any existing paper position's exits.

## Stock ranking and review rules

These changes apply only to stock discovery. Crypto selection and all paper
execution settings are unchanged. Stock mandatory checks remain rounded width
>=15%, >=$100M and >=2M shares per recent completed session, boundary movement
<=60%, trend efficiency <=25%, three midpoint crossings, two independent visits
near each boundary, full and recent containment >=80%, and latest close inside
the range. Full history must be complete. The one-swing list does not waive any
of these requirements. Below-support stocks cannot qualify or enter review.

Stock ranking score (ordering aid, not a probability or return forecast) equals
20 points for at least one recent full swing, plus 20 times each of recent
containment, (1 - efficiency), (1 - min(stability, 1)), and
(1 - min(drift, 1)), minus 10 for width/midpoint above 20%. Rank qualified and
review stocks separately. Advisories explain drift above 40%, unusually wide
ranges, missing recent swings, and unverified events. A fresh bounce, executable
spread/depth and earnings/news review are required before considering entry;
none is asserted verified by discovery, and no orders are enabled.

## Data and liquidity

Crypto uses 84 completed four-hour bars. Coinbase Exchange has no four-hour
buckets: four actual adjacent hourly observations are aggregated, and missing
hours are never substituted. Crypto volume is the Coinbase trailing-24-hour sum
of close times base volume, requiring >=$1M. It is a venue-specific estimate.

Stocks use completed 30-minute regular-session bars across 45 calendar days,
usually about 31–33 sessions. The calendar is requested for 50 days and Schwab
history uses explicit start/end timestamps rather than a ten-day period. Alpaca's calendar supplies holidays and early closes.
Every expected observation must exist; overnight/weekend gaps are not filled.
Average session volume over the latest seven calendar days must be >=2M shares and the close-times-volume estimate
>=$100M. Stock and crypto volume scopes are separately labeled.

Missing, duplicate, malformed, stale or insufficient histories cannot produce
a discovery ratio. Each result retains its actual data-through time; failed
observations are listed rather than replaced with prior bars. Crypto links open
Coinbase; stock links open the existing desk chart. Discovery has no order button.

## Snapshot selection and the lower chart

Select a symbol in a candidate row, one-swing review row, rejected-move row, or
long-term mini-chart caption to update the detailed chart below. Stock and crypto
links stay inside the desk; the separate market link remains available in the
chart header. The first qualified snapshot is selected automatically without
scrolling. Explicit selection scrolls to the chart. Asset-aware deep links use
`?view=range-discovery&symbol=NEAR&asset=crypto#detail-card`, preventing a coin
from being interpreted as a stock ticker. The home discovery panel links to the
same board selection.

The lower chart uses the **measured interval and window**: long-term stocks use
730-day daily OHLCV, recent stocks use their 45-day regular-session 30-minute
OHLCV, and crypto uses its 14-day four-hour OHLCV. It shows candlesticks, volume,
RSI, MACD and the snapshot's measured support/resistance band. The interval,
source and actual data-through cutoff appear beside it. No observations are
filled; indicators without enough history remain absent. The period selector
shows the saved scan window rather than labeling it as an unrelated six months.

`GET /api/range-discovery/chart?symbol=NEAR&asset=crypto&scan=<started_at>`
resolves a row from the current scan. Long-term charts reuse the audited daily
source only when its scan timestamp agrees. Other charts fetch historical real
candles ending at the saved scan cutoff, validate complete sessions/buckets, and
must reproduce support, resistance and latest close. Revisions or missing data
surface an error instead of substituting newer prices. Charts are cached per
scan, asset and symbol, and a new scan clears that cache. A changed scan ID is
rejected. This read-only chart request never starts discovery or sends orders.

Switching selection clears the previous chart and stock facts immediately.
The existing selection sequence guard prevents a slower prior response from
replacing the newly selected symbol. Failures show an explicit unavailable
message with no leftover candles. Refreshing a selected discovery chart retains
its snapshot interval and boundaries.

## API and refresh

`GET /api/range-discovery` reads status. `POST /api/range-discovery` accepts
`{"market":"both","threshold":15,"stock_mode":"two_year"}` and starts a background scan (202).
Loopback-host, local-origin, content-type and bounded-input checks apply.
`stock_mode` accepts `45_day` (the default) or `two_year`. Omitting it preserves
existing short-window API behavior. One scan runs per server process; concurrent clicks reuse its progress. Three
provider workers run at most. Coinbase public GETs share a five-request/second
budget and bounded retries for transient errors. Schwab authorization refreshes
before concurrent reads.

The browser polls local progress and retries lost connections. It displays
checked/total counts and omissions. The latest completed result is saved
atomically to `reports/range_trading/DISCOVERY_LATEST.json` and restored after
restart, retaining original dates. It is a dated research report, not a live
quote or market-bar cache. Opening it does not trigger a new scan. Persistence
failure leaves the current in-memory result usable.

## Verification

Offline tests use archived real Coinbase/Schwab observations, covering threshold
boundaries, DOT liquidity, NEAR paper availability, missing/stale data, session
context, explicit scan start, duplicate clicks, persistence and client filtering.
The first live scan checked 75 symbols and reported unavailable observations
explicitly. All matches remained research-only.

```bash
python3 -m pytest trading_desk/tests/test_range_discovery.py -q
node --test trading_desk/tests/test_range_discovery.cjs
```

Discovery uses an explicit 60% boundary-movement limit for both markets. The
separate paper runner retains its existing 40% default; this discovery setting
does not authorize or alter order execution. Start-to-end movement stays <=40% for crypto and affects ranking for stocks.
