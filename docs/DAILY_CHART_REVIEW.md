# Daily Chart Review

Dated native chart comparisons and separately sourced futures evidence.

Last Updated: 2026-11-17
Status: Active research view
Audience: Trading Desk owner and contributors

## Overview

The desk's sourced-decision North Star requires each count to name its evidence,
confirmation test and precise invalidation. `/chart-review` and the embedded
Daily Review render `trading_desk/chart_review.json`; opening the page reads the
saved manifest only. It does not refresh quotes, accounts, orders or monitors.

## Intraday updates

The optional `intraday_update` in the saved manifest adds completed OHLC bars
and separately dated scenario notes to each available asset. Candle positions
follow provider timestamps, including gaps. Dashed lines mark selected levels
from the saved studies. Recovery and extension paragraphs describe conditional
tests. The original drawings and completed-session evidence remain available
with their original timestamps.

The November 18 update uses Yahoo Finance cash NDX and SPX, Coinbase Exchange
BTC-USD, and delayed Alpaca consolidated SIP bars for COIN and CRCL. Cash and
equity returns compare with the prior session close from the same intraday
feed. BTC compares with midnight Eastern. The saved notes identify the local
model used on the observations.

## Comparison records

Use the **Elliott Wave scenarios** ticker links at the top of Daily Review to
jump straight to a saved study. The compact view includes each study’s levels,
confirmation and invalidation alongside the original and updated drawings.
The full gallery's direct ticker links scroll to the study after its saved data
loads.

Each asset's optional `comparison` selects an `original_url` and `updated_url`
from its existing `charts` manifest. Both captures remain visible in compact
and full views. The renderer shows a verdict, changes, reasoning, dated evidence,
next test and limitations. Other captures stay in expandable history in either view;
the selected pair and separately shown futures image are not duplicated there.
Desktop pairs use two columns; screens below800px stack the images. Long source
notes and point tables wrap rather than forcing the comparison wider.

Keep the original image immutable. Native evening NDX/SPX captures may update
an observed final pivot without asserting a confirmed wave ending. Preserve
the prior manifest privately before changing the current review. A lower low
can defeat a fixed-bottom hypothesis while leaving an extending fifth viable.
A genuinely broken impulse rule requires a recount; CRCL's shortest-third
failure below54.87 is separate from COIN's117.32 fixed-bottom failure.

## Cash indexes and futures

`futures` is a separate optional evidence record: contract symbol, individually
timestamped quote, source/session/delay, baseline limitations, review points,
native chart URL and completed-candle observations. December `/NQZ26` and
`/ESZ26` never overwrite NDX/SPX cash quote or historical wave pivots.

November17 uses Schwab realtime-flagged December quotes and separately delayed
TradingView15m screenshots. Yahoo front-contract history retains its own series
identity. Do not assume a constant cash/futures basis or validated subwaves.
Reject missing OHLC, malformed ranges, non-aligned quote pseudo-bars and candles
that are not complete at the provider's delayed cutoff.17:00–18:00ET maintenance
rows stay absent. The inconsistent current Yahoo futures daily row after the
18:00 rollover was rejected. No data was filled, interpolated or repaired.
Schwab and Yahoo settlement/previous-close references were not reconciled, so
the panel deliberately provides no futures percentage return.

## Next-session plans

The optional `next_session_plan` appears before the chart comparisons in both
Daily Review and the full gallery. It carries an explicit session date and
evidence timestamp, three symbol-level hold/trim/invalidation cards, independent
December NQ/ES and Coinbase BTC confirmation tests, execution review rules and
the official calendar link. Publication reuses the saved research snapshot;
it does not refresh quotes or imply completed-candle confirmation. Prior chart
records and the owner's dated decisions remain unchanged below it.

After the plan date passes in America/New_York, the badge marks it historical
and requires refresh. Proposed invalidations name the specific bottom hypothesis;
they are not approved stops or broker orders. Opening-range/VWAP values for a
future session remain unknown. Public content excludes account facts. Archive
the previous manifest privately before replacing it.

## Serving and verification

Only explicit public image routes in `trading_desk/server.py` serve chart files;
never add arbitrary filesystem or private `trading_records` access. Native
browser screenshots are JPEGs and use `.jpg` plus `image/jpeg`; compatibility
aliases for the first evening export URLs retain the correct actual MIME type.

Run `node --test trading_desk/tests/test_chart_review_render.cjs`. Coverage checks
the five visible pairs, duplicate-history exclusion, cash/futures separation,
missing quotes/captures, escaping, completed actual candle boundaries and the
single saved-manifest GET. Verify visible layout and all image links separately.
The November17 validation checked all26 image routes and inspected the desktop
Daily Review. Sphinx documentation build was unavailable in this environment
because Sphinx was not installed; customer-facing source was updated in
`docsrc/TRADING_DESK.rst`.
