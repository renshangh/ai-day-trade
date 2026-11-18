# Pattern Discovery and Independent Paper Lab

The separate same-window stock/ETF replay is available at `/pattern-backtest`;
see `PATTERN_BACKTEST.md` for results, source coverage and retrospective-selection limits.

Build a reference library from reviewed trades, find entry-time analogues, and track new local simulations.

Last Updated: 2026-11-09
Status: Draft 2; forward local paper comparison; unvalidated pattern transfer
Audience: Trading Desk owner and maintainers

## Overview

Open `/pattern-discovery`. The separate discovery worker scans BTC/USD and the
configured stock/ETF list. It records a normalized local paper position when a
fresh qualified pattern passes, then tracks the inherited 0.1 protection and
partial exits. This is **not** an Alpaca paper-account order or a live order.
There is no broker order client, funded portfolio, cash balance, margin borrowing,
position allocation, or combined cross-symbol investment return.

The existing North Star is causal, reproducible decisions on observed evidence.
For this experiment track forward matches, skipped reasons, data coverage,
winner/loser lookalike margins, net R after the declared cost proxy, missed valid
setups and false positives. Zero future-outcome features, invented bars,
duplicate positions or broker submissions are required. Ten winners are reference
material, not evidence that this method predicts future winners.

## Reference selection and definition

The immutable draft-2 library selects the ten highest net-dollar **distinct
completed trades** across all 38 original frozen **0.2 baseline** trades in
the same thirty-day window, each originally sized at 1 BTC. It retains data-gap
flags in the ranking and does not pick whichever exit model won for each entry.
The P1 baseline has the same ten winning entries. The October 29 22:15 trade
ranks third at a conditional $1,160.71, but is disabled for matching until its
data evidence is verified. Nine unflagged ranked examples enable matching.
The earlier clean-only draft and its input/config records are archived; no
forward paper trade had occurred before the explicitly corrected session. All ten are B1, so the library defines **one pattern
family using ten examples**, rather than claiming ten independent strategies.
All seventeen clean losing B1 trades from the original baseline are included as
counterexamples. Source result and market-data SHA256 hashes are retained.

Each card contains original trade ID, D/trigger/reference known-at times,
entry/initial stop/first target, setup evidence, actual modeled exit legs, net
USD and R. Outcomes are selection/review labels, kept separate from features.
This is retrospective winner selection with substantial selection bias.

B1 remains the existing aggressive first-stabilization definition: a complete
bearish new-low impulse of at least 2 pre-impulse ATR, an intact extended D and
a complete off-low stabilization reference, followed by a first crossing of
the previous complete 15-minute high plus $0.01, within the 0.10 ATR chase bound.
No HL is invented for B1. The initial stop is D minus 0.25 entry ATR. A/B2/C
families have no approved template in this first library and cannot open here.
P1, original C, the frozen release and existing BTC forward worker are untouched.

Entry-only features are: impulse/ATR, additional D extension/ATR,
reference-candle range/ATR, signed body/range, reference close distance from
low/range and elapsed 15-minute periods since D became known. Positive ATR
ratios and age use `log1p`; the two candle fractions remain raw. Distance is
unweighted mean absolute feature difference. No volume, current-minute close,
future high/low, exit, profit or chosen outcome enters this vector.

The radius is the maximum leave-one-out nearest-positive distance among the
nine unflagged ranked winners. A new B1 must be within this radius and strictly closer
to a positive example than any negative one. Ties reject. This is a declared
research hypothesis, not a calibrated probability or a validated improvement.
Do not change the library/radius in response to forward outcomes without a new
explicit experiment/session. Existing sessions refuse a changed library hash.

SPX is an index reference, not a stock/ETF order symbol in this experiment.
SPY and QQQ remain benchmark references. The separate completed-session screen
now measures consolidated liquidity, beta and ATR to select more active scan
names. Fresh executable spread/depth remain unverified; IEX minute volume is
never substituted for consolidated daily liquidity.

## Candidate data and paper entry

The initial example list (BTC/USD, FN, AXTI, COHR, LITE, CRCL, SPY, QQQ) was
replaced on November 9 by the measured mover selection described below. The
current editable list is a research universe, not an account-holdings sync. The list is bounded to 24 including
BTC/USD. Symbols with open local positions cannot be removed. The scan page
changes only this independent worker's config, never any brokerage watchlist.

The source pins HTTPS GET requests to Alpaca's data host, blocks redirects,
saves compressed raw responses/hashes and explicit retrieval parameters, checks
pagination, and normalizes only returned valid observations. BTC uses US crypto
minute bars; stocks/ETFs explicitly use **IEX single-venue raw minutes**, filtered
to 09:30–16:00 New York weekdays. This filter is a session scope, not an exchange
holiday calendar. No IEX-volume-as-consolidated-liquidity assumption is made.
Trading halts, thin venue coverage and unavailable data can prevent a signal.
Missing minutes remain absent. The frozen BTC engine resets incomplete entry
structure, and this adapter additionally rejects partial recent entry context.

BTC retains the original larger-hourly-resistance target calculation. A US
regular session does not offer fourteen uninterrupted BTC-style hourly bars.
The independent **stock/ETF transfer experiment** therefore uses confirmed
15-minute peaks with two complete neighboring bars each side and at least
one current-entry ATR of prominence on each side. Peaks must be above both the
entry and trigger reference; target is the nearest peak minus 0.10 ATR. This
is disclosed separately, not called equivalent to the BTC target rule, and has
now been replayed retrospectively on the equities list at `/pattern-backtest`;
this is not independent predictive validation. Missing/negative net target space
still rejects; 2R remains advisory. Targets/protection are model references.

Only full one-minute observations are fetched. Availability is minute end;
actual receipt/detection time is recorded separately. New model entries require
receipt delay of 0–180 seconds and complete context. Catch-up signals are saved
as skipped, never backdated paper entries. Exact intraminute crossing seconds
and executable fills are unknown. Warmup is eight calendar days; activation is
the next full minute after setup, after the reference training window ends.

Each accepted symbol can hold one normalized unit. Original first-25% target,
75% structural/protection exits and hard-stop full-remainder behavior are
inherited. Cost is the same 2 bps per side **ETF proxy**; BTC trading fees,
real spreads/slippage, stock execution and capital limits are not modeled as
broker facts. Unrealized reference P/L uses the last observed close and its
timestamp, potentially stale. No cross-symbol aggregate account result is shown.

## High-volume, high-beta, high-ATR universe

`python3 scripts/screen_pattern_universe.py` screens the bounded 309-name pool
(existing sector/theme stocks plus explicit active-name and ETF research lists).
It is not an entire-market search. `--apply` updates only the independent paper
scan list and retains any symbol with an open local position. Running without
that flag saves a reviewable screen first. Current results/source files are
under `reports/pattern_discovery/`; the page reads `UNIVERSE_SCREEN.json`.
This one-time screen is not an installed recurring refresh service.

Use 180 calendar days of real consolidated SIP split/dividend-adjusted daily
bars, with the most recent 64 **exact** completed exchange-calendar sessions.
The 16-minute end delay prevents inclusion of unavailable real-time SIP bars;
calendar close/early-close times determine completed sessions. Missing sessions,
new listings with insufficient history and failed batches remain unavailable.
Raw pages are compressed and hashed; original per-symbol bars are retained.

Fixed initial screen (unoptimized research universe settings):

- Both 5- and 20-session average close-times-volume >=$500 million/day.
- Both 5- and 20-session average shares >=5 million/day.
- Positive beta >=1.25, from the covariance of 63 aligned daily simple returns
  with SPY divided by SPY return variance. Not annualized or vendor 5-year beta.
- Wilder ATR14 >=3% of latest completed close. Seed with the mean first fourteen
  measured true ranges, then update `(13*ATR+TR)/14` across the observed window.
- Sort passing names by ATR% descending, then consolidated dollar volume.
  Select up to eight stocks and four positive-beta ETFs, plus BTC/USD. Inverse
  ETF rows are shown for review and do not enter this positive-beta selection.

The November 9 completed-session screen measures 301 of 309 names, omits eight,
and qualifies 58. Selected equities: CIFR, AXTI, IREN, LITE, CRDO, CRWV, ASTS,
NBIS; selected ETFs: SOXL, TQQQ, SOXX, SMH. SPY/QQQ remain visible benchmarks
but their 1.48%/2.38% ATR is below this active-mover cutoff. Other qualified
names, including NVDA, AMD, TSLA, COIN, MSTR and HOOD, remain inspectable in
**All qualified names**. FN fails the current dollar/share liquidity minimum.

SOXL/TQQQ and other leveraged funds are explicitly marked with their daily
leverage target. Beta is a measured sample estimate, not the stated daily
leverage multiple or an expected gain. ATR% is normalized movement, not a return
forecast; current depressed price/regime can raise it sharply. The selection
contains correlated exposures and is not diversified portfolio allocation.
Current spreads/depth, cash/risk sizing and actual broker fills are outside this
historical candidate screen. Manual additions to the list do not automatically
inherit a passing liquidity assessment. No entry/exit/stop rule changed.

## Operation and recovery

The new independent worker is separate from the original login-managed BTC
worker. Closing the trading desk does not stop a running discovery process.
This draft has **not** installed another login service; after a restart, run
the worker separately. Existing BTC login startup is unchanged.

```sh
python3 scripts/run_pattern_discovery.py --library
python3 scripts/run_pattern_discovery.py --worker
python3 scripts/run_pattern_discovery.py --status
```

`--once` performs a single scan/recovery pass while holding the same process
lock. A second worker refuses the lifetime lock. Config saves refuse while a
cycle owns its lock, preventing removal of a concurrently opened position.
Pausing preserves existing records and stops all model processing, including
model exits; resume reconstructs the same book. These are local controls only.

State is under `trading_records/pattern_discovery/`: immutable `LIBRARY.json`,
`CONFIG.json` (library and frozen engine pins), `OBSERVATIONS.sqlite` (actual
minute plus original receipt), compressed raw pages, source journal, `STATUS.json`
and log. Startup reconstructs each engine from its persisted actual input and
receipt clocks. A rolled-back batch discards its engine before recovery.
No finalization method is called on running positions. Missing/failing symbols
surface unavailable/stale, retaining explicitly saved prior observations.

GET `/api/pattern-discovery` and `/api/pattern-discovery/library` read saved
state only. Local same-origin POST accepts only `watchlist` and `enabled`;
order, strategy, risk or account settings are rejected. The library is reviewed
through the desk, not mutated through the page. Future live broker execution
would require a separately defined sizing/risk/approval workflow.

Provider references: [stock historical bars](https://docs.alpaca.markets/us/reference/stockbars),
[market-data venue and crypto methodology](https://docs.alpaca.markets/us/docs/market-data-faq).
