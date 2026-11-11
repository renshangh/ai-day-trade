IBIT trading hours on BTC Live Paper
=====================================

Display-only manual thinkorswim session and availability badges.

:Last Updated: 2026-11-10
:Status: Manual EXTO 24/5 timing; no execution or strategy change
:Audience: Trading Desk owner and maintainers

Overview
---------

On ``/btc-live``, a separate IBIT panel identifies scheduled regular,
pre-market, after-hours and overnight windows. The original BTC 0.1/E1/E2
strategies run 24/7. Frozen 0.2, worker source, PID/session, controls and
registration stay unchanged. No order, fill or signal filtering occurs.

Manual channel and hours
-------------------------

The owner reported IBIT overnight eligibility on November 10, 2026. This is
recorded as owner-reported, not broker-API verification. The indicator uses
Schwab's current thinkorswim EXTO schedule: Sunday 20:00 through Friday
20:00 Eastern, excluding holidays and five-minute breaks before/after the
regular session. Regular hours remain separately identified. Half days
close extended trading at 17:00, with a 13:00–13:05 post-close break.
Full holidays suspend the preceding evening's session and resume at 20:00
on the holiday, subject to weekends. Times follow New York EDT/EST.

Outside regular hours use manual LIMIT / EXTO orders. Broker stop orders
do not execute in extended hours. BTC reference prices and benchmark stops
are not IBIT prices or protective orders. Current bid/ask/spread, permissions,
market halts, liquidity and execution are not verified by a schedule.
Overnight availability on thinkorswim does not establish Schwab API support.

Reading the badges
-------------------

* **Recent · IBIT [session] window**: a recent model entry or positive-fraction
  exit became available while scheduled trading was open, it remains open,
  and BTC reports running. Human review only; execution is unverified.
* **Historical · [session] at detection**: older than 180 seconds or detected
  more than 180 seconds after the reference minute completed. No revival at
  reopening, backdated fill or queued order.
* **Outside IBIT trading window**: availability or now falls in a closure
  or session break.
* **No entry / Info only**: rejected/held setup checks, stop raises and
  informational events do not become entry or exit actions.
* **Unverified / Not yet available**: calendar/timestamp missing, stale,
  unsupported or future-dated. No open session is assumed.

The later of actual detection and completed-minute availability controls the
badge. A 15:59 BTC minute detected at 16:00:06 is in the post-close break.
The panel shows the next transition; failed page refreshes invalidate badges.

Calendar, preservation and separate Nasdaq plan
------------------------------------------------

An independent cache uses real Alpaca exchange-calendar dates and supplied
open/close times. Published Schwab hours are applied to those dates without
creating price observations. Missing/stale metadata refreshes nonblockingly
in the dashboard through a pinned GET with redirects disabled, a bounded
response and no more than one attempt per minute. Errors stay unverified.
Fresh checks make no remote request. No AI polling or extra worker is added.

The ``ibit_hours`` sidecar preserves every original BTC response field and
record. No metadata is written to worker records. Portable tests cover calendar,
transport, refresh, availability, display and non-mutation behavior.

Current thinkorswim 24/5 access is separate from Nasdaq's planned December 6,
2026 23/5 expansion. That plan does not replace the broker schedule or enable
API overnight execution. See ``docs/IBIT_HOURS_INDICATOR.md`` for source links.
