# IBIT trading hours on BTC Live Paper

Display-only manual thinkorswim session and availability badges beside unchanged BTC benchmark records.

Last Updated: 2026-11-10
Status: Manual thinkorswim EXTO 24/5 timing; no execution
Audience: Trading Desk owner and maintainers

## Overview

`/btc-live` retains its original 24/7 BTC/USD 0.1/E1/E2 strategy and live worker.
The separate IBIT panel and row badges identify scheduled windows for manual
IBIT review. They never filter, delay, fill, suppress or change BTC signals,
positions or exits. Frozen 0.2, worker source, PID/session, controls and launch
registration remain unchanged. No broker or paper-broker order is submitted.

This supports the North Star of sourced, causal and reproducible decisions:
actual receipt/availability is separate from historical candle references
and execution assumptions.

## Manual channel and schedule

The owner reported IBIT's thinkorswim overnight eligibility on November 10,
2026. That provenance is explicit in the display metadata; the calendar does
not independently verify account or symbol permissions. The display uses
Schwab's existing **thinkorswim EXTO 24/5** schedule, not Schwab API routing:

- Sunday 20:00 to Friday 20:00, America/New_York (EDT/EST).
- Regular hours 09:30–16:00 on full sessions remain separately identified.
- Five-minute closures 09:25–09:30 and 16:00–16:05 on full sessions.
- Full holidays close from the preceding calendar day at 20:00 until the
  holiday at 20:00, subject to weekends. A Friday holiday resumes Sunday.
- For a 13:00 half-day close, the post-close break is 13:00–13:05 and extended
  trading ends at 17:00, following Schwab's published holiday policy.

A sourced exchange trading date owns a manual overnight/extended window from
20:00 on the preceding calendar date to 20:00 on that date (17:00 for a half
day). The actual exchange open/close supplies the two five-minute breaks.
Windows are half-open `[start,end)`. Unknown or unsupported calendar metadata
fails to unverified; no price bars or substitute sessions are generated.

For extended/overnight manual execution, use appropriate **LIMIT / EXTO**
orders. Broker stop orders do not execute outside regular hours. BTC benchmark
stops are not protective IBIT orders. Check current IBIT bid/ask/spread,
account eligibility and trading status; this overlay verifies none of these.

## Reading the display

The top panel shows regular, pre-market, after-hours, overnight, session break
or closed, the next transition, and check time. All times include EDT/EST.

- **Recent · IBIT [session] window:** a true model entry or positive-fraction
  exit is recent, both availability and current time are in scheduled trading
  windows, and the BTC worker reports running. Human review only, never a fill.
- **Historical · [session] at detection:** older than 180 seconds, or detected
  more than 180 seconds after the completed reference minute. Reopening cannot
  make it fresh; never queue or backfill old signals.
- **Outside IBIT trading window:** availability or current time is closed or
  in a session break.
- **No entry / Info only:** held/rejected setups, stop raises, confirmations
  and warnings are not promoted into entry or sell actions.
- **Unverified / Not yet available:** missing/stale calendar, missing or
  timezone-free timestamps, unsupported coverage, or future availability.

Availability is the later of actual detection and completed-minute
availability. Completion is the later of reference plus 60 seconds and any
provided interval end. A 09:29 BTC minute detected at 09:30:06 can be reviewed
in regular hours. A 15:59 minute detected at 16:00:06 is in the session break.
Every badge retains `execution_verified=false`. BTC prices are not IBIT prices.
A failed dashboard refresh invalidates hours badges.

## Independent calendar cache and implementation

`trading_desk/ibit_hours.py` reads `trading_records/ibit_hours/CALENDAR.json`.
It uses a pinned, redirect-disabled GET to Alpaca's paper `/v2/calendar` for
previous/current/next years, with existing paper credentials and a bounded
response. Raw responses are archived under that independent directory.
No research-module dependency, price request or broker order path is added.

A calendar older than 24 hours is unverified. The dashboard refreshes missing
or stale metadata with one nonblocking thread and at most one attempt per
minute. Failures preserve the previous cache and leave badges unverified.
Fresh-cache page checks make no remote requests. There is no new environment
variable, AI polling, automation or live worker.

The server appends only an `ibit_hours` sidecar to `/api/btc-live`. Source
fields and arrays remain intact, and parallel badge arrays follow the selected
model's displayed order. No observation/event database writes occur.

## Separate Nasdaq plan

Current thinkorswim 24/5 access is independent of Nasdaq's planned December 6,
2026 21:00 Eastern 23/5 launch and 20:00–21:00 daily pause. That plan does not
replace this broker schedule, activate a new routing channel or establish
Schwab API overnight access.

Sources:
- [Schwab 24/5 schedule](https://www.schwab.com/learn/story/ins-and-outs-245-trading)
- [Schwab session breaks, order types and channel restrictions](https://www.schwab.com/stocks/extended-hours-trading)
- [Schwab holiday policy](https://workplace.schwab.com/story/how-does-extended-hours-trading-work)
- [Alpaca market calendar](https://alpaca.markets/sdks/python/api_reference/broker/calendar.html)
- [Separate Nasdaq plan](https://www.nasdaq.com/23-5-trading)

## Review and verification

Portable tests use committed actual sourced calendar metadata and a minimal
archived public BTC reference, without private accounts, local research bundles
or invented OHLC/P&L. Coverage includes week/session boundaries, full holidays,
early closes, DST, malformed/stale calendars, late/future detection, informational
events, no source mutation, bounded refresh failure and pinned GET/no redirects.
The HTTP regression removes the sidecar and checks the exact original DTO.
Worker/rule hashes and original PID/session are separately verified on the host.
Only the dashboard is reloaded to activate display changes.
