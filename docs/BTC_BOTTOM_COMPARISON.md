# BTC Bottom Comparison Review

Dated discretionary setup and read-only twelve-hour model-action audit on BTC-live.

Last Updated: 2026-11-15
Status: Comparison only; no promotion into frozen rules or order execution
Audience: Trading Desk owner and maintainers

## Overview

The `/btc-live#bottom-review` panel separates a discretionary chart discussion
from the original BTC 0.1/E1/E2 forward model records. This supports sourced,
causal review without changing frozen 0.2, the worker, its session or any model
position. This feature does not generate signals, fills, orders or approvals.

## Dated setup and supersession

`trading_desk/btc_bottom_review.json` preserves the November 14 15:30 EST
assessment: a $64,988.1045 base and a hypothetical $66,160 entry after a new
higher low near $65,950, $65,880 conditional stop and $66,830–$66,920 first
resistance/25% exit-review zone. These numbers never constituted an active
model signal or order.

At the actual 15:54 EST reference minute the base broke; that completed minute
was not knowable before 15:55. The discussed breakout had not occurred. The
setup is therefore marked invalidated/untriggered, not a stopped-out trade.
The subsequent observed low near $61,991 and recovery near $66,085 are recorded
with actual minute boundaries. Newer review references have their own dated
source intervals; they are not automatically upgraded into confirmed HLs.

The future conditional example is displayed separately. A new independent HL
must actually form after the recovery-zone reclaim before the near stop has
any structural basis. Otherwise that example remains inactive. Keeping the
larger parent D implies a much wider stop and different reward/risk. The ratio
is descriptive, not a new hard 2R gate. A planned first 25% sale and structural
exit for the remainder are discussion only, not edits to the frozen exits.

The review is dated and must be reassessed as price evolves. A current quote
is displayed separately with source, exact quote time and age; stale quotes
are omitted rather than replaced with an old close. There is no automatic
news assessment or entry-rule evaluation in this view.

## Complete twelve-hour action audit

`/api/btc-bottom-review` uses the existing read-only controller status and opens
that session's observation database with SQLite `mode=ro`. It queries all
persisted events through the review time, not the main page's latest-150 cap.
Only actual model entries and positive-fraction exit legs count as trades;
stop raises, warnings and setup checks do not.

The exact rolling twelve hours use actual availability: the later of original
detection and completion of the reference minute. Old references detected
within the window are included with both timestamps intact. Future-available
events are excluded. Identical actions are grouped across models, while every
original event ID is retained. Counts and exit-leg benchmark net remain per
model, never tripled into one investment account.

If entry context is known, exit-leg net uses the original normalized initial
1 BTC and 2bps/side cost proxy. It is reporting arithmetic, not a simulated
IBIT fill. Entry-before-window exits remain visible in the window. The two most
recent completed trades wholly before the window are separated as historical
context. Missing database/observations or audit errors return unavailable,
not fabricated zero trades. Session coverage and observed-through time are
shown so partial or stale coverage is explicit. Missing minutes remain absent.

IBIT session labels reuse the sourced calendar and manual EXTO display policy.
Weekend BTC signals can exist while IBIT is closed. The audit does not verify
IBIT prices, fills, broker eligibility or overnight API access.

## Refresh and preservation

`trading_desk/btc_bottom_review.py` is imported by the dashboard only, never
by the worker. The existing `/api/btc-live` response is unchanged. The new
route accepts GET only, and its own page script reads once on load and on
**Refresh review data**. No recurring timer, chat automation, price fetch or
second worker is introduced. The button refreshes quotes/audit data; it does
not rewrite the dated discretionary assessment.

Tests use original persisted public BTC action and minute metadata, without
private accounts or invented bars. They cover grouping, P/L, exact availability
boundaries, older references, future events, empty versus unavailable data,
no database/input mutation, stale quote withholding and the GET-only view.
Engineering/public docs and the changelog accompany the UI change. Verify the
13 frozen rule hashes plus worker script/control/session/registration hashes
and original PID/session before and after dashboard reload.
