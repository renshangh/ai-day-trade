BTC Bottom Comparison Review
=============================

Dated discretionary setup and a complete read-only twelve-hour model audit.

:Last Updated: 2026-11-15
:Status: Comparison only; no rule or order changes
:Audience: Trading Desk owner and maintainers

Overview
---------

Open ``/btc-live#bottom-review`` for the separately dated bottom-confirmation
study, current source/time-labeled BTC quote, conditional entry/stop/targets,
and recorded model entries and exit legs. Frozen 0.2, the original BTC worker,
its session and benchmark records remain unchanged. No orders are sent.

Dated setup versus model trades
--------------------------------

The November 14 base broke before the proposed entry triggered. The panel
preserves that history as invalidated/untriggered, then lists updated actual
wave references. A future conditional entry near $66,160 and stop near $65,880
requires a new independent HL near $65,950 after reclaiming the recovery zone.
That HL and entry are not assumed. The proposed first 25% exit-review zone is
$66,830–$66,920; the remainder follows structural weakness or its applicable
stop, with no fixed second target. These are comparison examples, not changes
to the frozen model or active IBIT orders.

Read the assessment timestamp: current quotes refresh separately and cannot
make an old analysis current. A stale quote is unavailable; a previous close
is never substituted. The review-data button does not rewrite the assessment.

Twelve-hour audit
------------------

The panel queries all durable model events in a read-only database, instead
of relying on the latest-150 display limit. It counts only true entries and
positive-fraction exits. Actual availability, which is no earlier than the
completed reference minute and actual detection, defines the exact window.
References and availability times are both shown in New York EDT/EST.

Identical actions across 0.1/E1/E2 are grouped while retaining original IDs.
Counts and normalized benchmark P/L stay per model. Trades preceding the
window are separated as context, and unavailable records do not become zero
trades. Observed-through time, worker health and session coverage are explicit.
IBIT timing does not establish an executable quote or fill. Weekend BTC
signals may occur while IBIT is closed.

Operation
----------

The view reads on load or when **Refresh review data** is selected. There is
no new recurring monitor, price fetch, worker, approval or order route.
The existing BTC live API remains unchanged. See
``docs/BTC_BOTTOM_COMPARISON.md`` for implementation and preservation checks.
