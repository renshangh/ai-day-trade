# BTC Live Paper Comparison

Operate the frozen 0.2 strategies on newly received Alpaca BTC/USD observations.

Last Updated: 2026-11-10
Status: Comparison only; no broker orders or broker paper fills  
Audience: Trading Desk owner and maintainers

## Overview

Open /btc-live. The owner selected comparison-only operation using BTC/USD;
IBIT and ETF execution are excluded. The three independent records are original
0.1, E1 and E2. Thirteen strategy-source hashes must match frozen release 0.2
before the worker starts or recovers. No frozen engine, parameter, original
release artifact or historic result is changed.

The North Star remains sourced, explicit decisions: every signal has its actual
observation and detection time; no invented minutes, duplicate signal records,
backdated fills or broker requests. This forward sample is separate from the
already reviewed historical month.

The page also has a separate IBIT manual thinkorswim 24/5 display overlay. It shows
current session hours and per-entry/exit availability/freshness without
changing or filtering any BTC model record. IBIT execution remains manual
and unverified; owner-reported EXTO eligibility does not establish API access. See
`docs/IBIT_HOURS_INDICATOR.md`.

## Observation and timing contract

The worker polls Alpaca's pinned US crypto market-data endpoint every 15 seconds
for completed 1-minute bars. It preserves raw response hashes and observed
OHLCV only, builds the same 15-minute structures, and obtains a separate current
BTC/USD bid/ask quote. No broker or order client is imported.

This is minute-based forward comparison, not tick-by-tick execution. A historical
breakout reference at 10:15 cannot become observable before its underlying
minute is delivered, commonly after 10:16. The dashboard distinguishes:

- Rule market-reference minute and full-minute availability boundary.
- Actual received/detected timestamp and delay.
- Current quote timestamp, freshness, bid/ask, and explicit reference-only label.
- Model entry/exit prices and hypothetical fractions, never actual fills.

The inherited engine confirms completed 15m state when a following minute is
processed. This may add a further minute of observation latency to a completed
bar signal. The worker does not synthesize a next-minute opening to avoid that
delay or call the mutating finish() method while running.

The benchmark retains initial 1 BTC per trade and the original 2bps per side
ETF-cost proxy. It is not actual BTC fee-adjusted profit, an Alpaca paper-account
trade, or an ETF return. No dollar budget or broker position is implied.

## Durable state and recovery

State is separate from the frozen archive, under
trading_records/btc_structure/live:

- CONTROL.json records start/pause intent; no order settings are accepted.
- SESSION.json pins activation at the next full minute, a seven-day warmup,
  and the approved strategy-source hashes.
- Each session's observations.sqlite owns actual received minutes, separate
  model signals/events and chronological 15m rows.
- Raw compressed provider pages and SOURCES.jsonl retain data provenance.
- STATUS.json records heartbeat, freshness, model state and sanitized errors.

Warmup cannot open positions before activation. Restart reconstructs all three
engines from the same persisted actual observations. Stable event keys preserve
the original detection timestamp and prevent duplicate events. No software
broker order is regenerated or replayed because no such client exists.

Already used observations are immutable. Conflicting data or an earlier
late-arriving minute pauses the comparison for review; it is never inserted
behind the engine's processed cursor. A missing minute remains missing.
An exception rolls back the batch and discards in-memory engine state before
recovery, preventing a partially processed batch from advancing only one model.

After pause or outage, observed catch-up events may be late. They stay labeled
as comparison references rather than current executable signals. Current quotes
older than 60 seconds or dated in the future are unavailable for fresh use.
Minute data older than 180 seconds marks the running comparison stale.
The page distinguishes running, recovery, warmup, stale, paused, error and offline.

## Daily operation

The installed macOS login worker already runs independently of the dashboard.
Keep the SanDisk connected and log in normally. To review it, open
http://127.0.0.1:8799/btc-live, check Running and fresh data, then choose 0.1,
E1 or E2. Pause comparison stops processing; Start / resume comparison continues
the same session. Closing the page does not stop the worker. These controls
never submit broker orders.

From the repository, inspect status without starting another worker:

    python3 scripts/run_btc_live.py --status

To install/enable login startup or resume enabled comparison intent:

    python3 scripts/run_btc_live.py --install-agent --enable

The dashboard server is only needed to view/control the page; the worker does
not depend on it. If the page is unavailable, start the server from the checkout:

    python3 trading_desk/server.py --port 8799

## Start and supervision

For an alternative manual supervisor when the login service is not running:

    python3 scripts/run_btc_live.py --enable --supervise

The supervisor restarts a failed worker. File locks allow one supervisor and
one writer. The CLI --status reads state without starting or fetching data.
The page's start/resume and pause controls persist intent; opening the page
does not start a process or make a provider/broker request.

On macOS, --install-agent registers the worker with launchd for login/restart
supervision. Its working directory and logs are on the internal home disk;
the absolute script path, data and existing credentials remain in the
external-drive checkout. Registration includes RunAtLoad, KeepAlive and a
15-second restart throttle. The internal --launchd-worker entry point requires
launchd as parent; it records service ownership only after acquiring the
exclusive worker lock. A competing process cannot overwrite supervision state.

On November 9, Python's Files & Folders / Removable Volumes permission was
confirmed enabled. No Full Disk Access or broader permission was granted.
The previously disabled registration was enabled and the exact earlier
registration was migrated with a backup. The local-session supervisor was
retired after checking both process identities, and launchd recovered the same
session directly. Ownership reports parent PID 1 and fresh actual observations.
This verifies launchd activation/recovery; it does not claim a logout or reboot
test was performed.

The live worker was then terminated deliberately while the dashboard HTTP server
was stopped. KeepAlive restarted it without a manual kickstart, new source
observations/quotes arrived while the server remained down, and the same session
and all previously detected signal/event records were retained. The dashboard
was restored afterward for review. The owner can leave the page closed.

Run the installer again after intentional setup changes:

    python3 scripts/run_btc_live.py --install-agent

Reinstallation is idempotent. It migrates only the exact known earlier plist,
preserves its backup and refuses unrelated registrations. The page can pause
and resume the comparison independently of login supervision. Leaving enabled
intent in CONTROL.json lets the worker resume after login without the page.
No browser or dashboard server is needed by the worker.

Host sleep, external-drive availability and network access affect observation
continuity. A paused/offline software comparison provides no broker protection.

## Interface

GET /api/btc-live accepts model=0.1/E1/E2 and an optional New York date.
It reports no more than 100 signals, 150 events and 100 selected-day 15m rows.
POST accepts only operation=start or pause, with JSON and local-origin checks.
Quantity, ticker, account, submit and other order arguments are rejected.

The page provides separate positions/P&L, parent D/L2, initial/current stop,
first 25% target, actual remaining fraction, target/protection/exit events and
chronological observed candles. Scanned current L1/L2 are not replacements
for a held trade's recorded original parent D.

## Verification

Regression coverage uses actual frozen BTC minutes to check unchanged model
outcomes, missing observations, rejection of late backfill, receipt-time
attribution, idempotent recovery, freshness and the HTTP no-order boundary.
The existing release tests continue to verify immutable archive hashes.

Review fixes keep a rejected batch's in-memory state out of the published
snapshot, bound selected-day queries to New York calendar boundaries (including
25-hour days), discard late responses after a model/date switch, and terminate
the manual supervisor's child on both SIGTERM and Ctrl-C. The existing source
JSONL was checked and remains valid; no historical provenance was rewritten.
