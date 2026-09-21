# Trading Desk Session VWAP

Consolidated intraday VWAP for the private journal's open holdings.

**Last Updated:** 2026-09-14
**Status:** Active
**Audience:** Contributors

## Overview

Daily Review includes a separate Today's VWAP panel via `GET /api/session-vwap`.
It includes all open journal symbols except SNDL, including IBIT independently of
the existing swing-review exclusions. The journal and account weights are unchanged.
This supports the desk's risk-review discipline by comparing holdings against a
clearly timestamped session benchmark; being above VWAP is not a trading signal.

## Data contract

`session_vwap.py` requests the current New York date from Alpaca's paper trading
calendar using the existing Alpaca credentials. Calendar open/close times govern
the window, including early closes. Calendar failures report unavailable; closed
days and pre-open requests never carry a previous session forward.

Each symbol requests unadjusted SIP `1Min` bars from session open until the earlier
of session close or now minus 17 minutes, rounded down to a whole minute. The end
is exclusive. This feed is independent of the board's IEX fallback. The comparison
price comes from the last returned minute bar in the same window, not a live quote.

Session VWAP is `sum(bar.vw * bar.v) / sum(bar.v)`. Bar VWAPs come from the vendor;
OHLC-derived typical prices are not substitutes. Missing minutes are not filled.
Duplicate timestamps, invalid numbers, failed or incomplete pagination, and missing
VWAP fields invalidate the symbol. Empty history reports no data. A symbol failure
does not blank the remaining symbols. This obeys RULE #1 in
`BACKTESTING_ARCHITECTURE.md`.

The response includes the New York session date, cutoff, fetch timestamp, per-symbol
last bar timestamp, volume, last price, VWAP and percent difference. Last-bar times
make inactive trading and older prices visible. It is an aggregate of returned
eligible minute bars, not a guarantee that the vendor captured every exchange print.

## Refresh and privacy

The two-minute memory cache keys on date and current symbol membership. Force
refresh bypasses it. The panel loads independently of daily research, refreshes
every two minutes while Daily Review is visible, and has its own Refresh VWAP
button. Failed requests clear old displayed figures. No account data is persisted
to the public board cache; no new credentials or environment variables are added.

## Verification

`python3 trading_desk/tests/test_session_vwap.py` covers weighted arithmetic,
window boundaries, missing/invalid data, pagination, calendar closures, early
closes, DST, exclusion, cache behavior and per-symbol failures. All fixtures are
explicit offline test inputs, never served as market data.

Public usage: `docsrc/TRADING_DESK.rst`. Existing daily chart VWAP 20 remains a
different, rolling indicator.

Verified locally on 2026-09-14: Trading Desk suite passed (235 tests plus 5
subtests), live endpoint and browser panel showed the expected six holdings,
and JavaScript syntax passed. The new public page passes a targeted Sphinx HTML
build with warnings treated as errors. Full repository documentation generation
was blocked by the existing missing `jsonpickle` dependency during autosummary.
