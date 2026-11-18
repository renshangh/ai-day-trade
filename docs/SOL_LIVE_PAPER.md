# SOL E1 Live Paper and BTC Comparison

Independent live SOL/USD E1 benchmark with a shared human-review outbox.

Last Updated: 2026-11-10  
Status: Original SOL E1 paused; separate SOL 0.1 candidate under review  
Audience: Trading Desk owner and maintainers

## Overview

Current routing: `/crypto-live` is stopped, `/btc-live` continues independently,
and `/sol-live` now contains SOL-only model 0.1 research. Historical comparisons
have moved to `/crypto-research`. The SOL E1 worker is paused, unloaded and
disabled for automatic login restart. Its history remains intact. See
`docs/SOL_MODEL_01.md`; the candidate is not installed or enabled. The command
below describes the original E1 worker, not activation of SOL 0.1.

Previously, `/crypto-live` displayed both comparisons. Original `/btc-live` remains the
unaltered three-model BTC page. SOL uses E1 only, independently, with the exact
frozen 0.2 constructors and numerical entry, exit, stop, risk and 25% first-sale
settings. P1, C and the top-ten matcher do not participate. ETH is not enabled.

The existing North Star is sourced, causal, reproducible decisions. Track fresh
observations, missing minutes, receipt-to-signal delay, pending/delivered reviews
and duplicate-free recovery. No synthetic observations or retrospective fills.

## Independent observation and supervision

`trading_desk/sol_live.py` reuses the original durable observation protocol by
subclassing its comparison and worker without editing their source. Only E1 is
constructed for SOL. Seven days of real Alpaca US crypto minute bars establish
warmup; entries are eligible from the next full minute after activation. Raw
provider pages, hashes, request parameters and actual receipt times are saved.
No missing bar is interpolated, filled or carried forward. Revisions/late
backfill pause this store for review. Restart replays immutable observations
and preserves first detection timestamps. The worker does not call `finish()`.

State is separate under `trading_records/sol_live`, including control/session,
status, session observation databases, raw source pages, worker lock, review
database and preservation checks. Original BTC state is opened read-only for
notifications. Its control, process, session and registration are not changed.

Install independent login supervision from the repository:

    python3 scripts/run_sol_live.py --enable --install-agent

Read both without starting a worker or fetching market data:

    python3 scripts/run_sol_live.py --status

The SOL service is `com.renshangh.sol-e1-live-comparison`, with internal-home
working directory/logs and the external-drive script/data paths. RunAtLoad and
KeepAlive make it independent of the browser and dashboard. The original BTC
registration is untouched. The machine must remain awake, online and logged
in, with the external drive accessible. Login registration is not a claimed
logout/reboot test. This task adds no new environment variable or permission.

## Comparison versus human approval

Both frozen benchmarks automatically record hypothetical reference entries and
exits. A human-review outbox watches new actual `entry` and positive-fraction
exit events from BTC 0.1/E1/E2 and SOL E1. Stable IDs combine symbol, session and
source event identity. No prior event before alert activation is resent.

Each request includes asset/model/trade, action, fraction, market-reference
minute, earliest completed-minute availability, actual detection time, price,
initial stop, first target and available original D/L2 references. A source
model already holding before activation can still generate a new exit review.
BTC model variants remain separate proposals on the page.

Approval **acknowledges a paper review only**. It creates neither an actual nor
a hypothetical execution fill and does not pause, alter or backdate the frozen
benchmark. Pending, approved, rejected and superseded states are explicit.
A later model exit supersedes an unreviewed entry; a remainder exit supersedes
an unreviewed partial sale. This is not a broker approval or protective order.

The owner replaced chat polling with page-only alerts on November 9 to avoid
recurring model usage. The `btc-and-sol-paper-approval-alerts` automation was
deleted; do not recreate it without a new instruction. `/crypto-live` reads the
local saved outbox every five seconds with no model call. The alert panel is
above the model cards, with pending/new counts, highlighted entries/exits and
a new-alert tab title. Worker/outbox failures also appear there. A proposal
older than 180 seconds is labeled delayed, never a fresh execution opportunity.

`Mark displayed alerts seen` stores seen IDs in this browser's local storage.
Seen is separate from approval and does not change model state or the historical
chat-delivery acknowledgment. `Approve paper review` and `Reject` save only the
explicit human decision in the existing outbox. Superseded/decided proposals
do not offer review buttons. The worker keeps saving events with the page closed;
saved alerts appear on reopening. There are no closed-page or chat push alerts.
Provider delivery, 15-second worker polling and five-second page refresh add
latency. This page is not a broker execution or protective-order system.

Inspect undelivered requests without changing delivery state:

    python3 scripts/run_sol_live.py --alerts

Historical/manual chat-delivery acknowledgment remains available, only after
a message has actually been presented to the owner:

    python3 scripts/run_sol_live.py --notified PROPOSAL_ID

After the owner explicitly approves or rejects that exact paper proposal:

    python3 scripts/run_sol_live.py --decision PROPOSAL_ID --approve
    python3 scripts/run_sol_live.py --decision PROPOSAL_ID --reject

POST `/api/crypto-live/review` accepts exactly a known 24-hex-character `id` and
`decision=approved` or `rejected`, with JSON/local-origin checks. Extra arguments,
order actions and cross-origin writes are rejected. The response explicitly
states no fill and no orders. POST `/api/sol-live` still accepts only
`operation=start` or `pause`. GET `/api/crypto-live` reads both independent
states and the review outbox; GET `/api/sol-live` reads SOL E1 detail. No HTTP
request starts a worker or fetches market data. No broker client is imported.

## Units and limitations

The recent-trade table explicitly shows the latest three recorded BTC 0.1 and
SOL E1 trades, entry route, reference/detection times, D/L2, stop/target and
saved model exits with per-coin realized leg net. BTC E1/E2 exits may differ;
inspect them on the original BTC page rather than interpreting this table as
all three books. History is read from the complete persisted source event
database for those entries, not reconstructed from the capped latest-150-events
display. Missing history is reported unavailable. Alert rows also display
their recorded entry type.

The frozen route order is A, B1, B2. It may select B1 even when B2 also passes;
a recorded route is not an exclusive chart classification. P1 is not active.
See `docs/investigations/2026-11-10_LIVE_A_B_ENTRY_REVIEW.md` for the first three
BTC trades, prefix-only P1/B2 checks and proposed stage-exclusive definitions.
Those refinements are not deployed to either worker.

The separate same-thirty-day experiment is now visible at
`/crypto-live#refined-comparison`; see `docs/REFINED_ENTRY_COMPARISON.md`.
It reproduces all four original controls before full refined sequential runs.
All four refined returns are lower and closed-trade drawdowns higher. The page
shows original/refined trades, label-only changes, additions/removals, gap
partitions and exports. This research section does not add or change a worker.

BTC results use one initial BTC per trade; SOL uses one SOL. Dollar P/L between
those units is not a capital-normalized performance ranking or account return.
Both retain the frozen 2bps-per-side ETF spread/slippage proxy and exclude
actual spot crypto fees. Alpaca crypto observations may include zero-volume
quote-midpoint bars; reference prices are not executable fills. Missing source
minutes, stale quotes, delayed receipt and suspended host operation stay visible.

## Verification

Use actual archived SOL minutes through its first E1 exit to check exact entry,
stop, partial sale and net P/L, replay/recovery idempotence and receipt clocks.
Real archived BTC observations test all three separate BTC proposal variants
without source writes. Check missing/incomplete bars, no historical alert replay,
delivery/decision separation, supersession, frozen hashes, independent launchd
registration and HTTP rejection of order arguments and cross-origin controls.
Test the separate paper-review HTTP route against an actual archived SOL entry,
proving approval changes only its decision and not model positions, events,
observations or P/L. Interface tests cover new/seen persistence, actual saved
reference prices, no fabricated trades and paper-review request boundaries.
Keep original BTC PID/session and preserved source/artifact hashes unchanged.

Deployment verification on November 9 confirmed both workers running with
fresh observations and quotes. Only the SOL worker was deliberately terminated:
launchd restarted it under parent PID 1, recovered the same session and advanced
its observed-minute count. Original BTC PID/session stayed unchanged. Targeted
Python and interface regressions passed; the documentation build passed.
