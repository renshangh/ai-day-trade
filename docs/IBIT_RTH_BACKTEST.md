# BTC live models on IBIT regular session history

Exact-rule controls and a separate exchange-session clock comparison on actual ETF prices.

Last Updated: 2026-11-10  
Status: Historical research complete; no live promotion  
Audience: Trading Desk owner and maintainers

## Overview

Open `/ibit-lab` for original BTC 0.1/E1/E2 models replayed on IBIT's actual
minute prices and volume. The user selected a session-adapted comparison beside
an exact BTC-rule control and retained overnight positions. This does not
restart or alter the original `/btc-live` worker. SOL remains paused and frozen
0.2 is unchanged. There is no IBIT live worker or broker order.

The same studied month, October 10–November 9, 2026 UTC exclusive, is tested
with seven calendar days of real warmup from October 3. Twenty regular test
sessions contain 7,800 of 7,800 expected minutes; warmup plus test contains
9,750 of 9,750. Alpaca consolidated SIP raw minute observations are archived,
with original responses/hashes, actual exchange calendar and split checks.
There is no in-window split. All observed rows are genuine; missing data would
stay absent. No premarket or after-hours bar is passed to either replay.

The North Star is real-source, causal and reproducible behavior. Coverage,
entry/exit availability, overnight execution, drawdown and source/rule
preservation matter alongside P/L.

## Calendar and overnight execution

The regular-session grid comes from the actual exchange calendar: normally
09:30–16:00 America/New_York Monday–Friday, with holidays, supplied early
closes and daylight saving. Expected minutes are the half-open interval
`[open,close)`. The final included minute normally starts at 15:59; a separate
16:00 auction observation is not invented. UTC openings change from 13:30
before November 1 to 14:30 after the daylight-saving transition.

Positions carry overnight, with no forced daily close. Stops and active exits
use only observed regular-session prices. A stop gapped through at opening
uses the actual observed opening reference, not the old stop level. No
off-hours protection, intraminute crossing second or executable fill is
claimed. Overnight/wide gaps can hide adverse paths. Cash-account equity is
marked only at actual observed minute closes; no flat overnight equity rows
are generated.

The adapted continuity cursor is absent across a scheduled closure; no fake
minute or price is inserted. The calendar counts only actual missing regular
minutes between observations. Genuine gaps still flag exposure and reset
unconfirmed context. The account/CSV continuity fields distinguish closed
minutes from missing market minutes. Original fifteen-minute entry structure
continues to reset on overnight wall-clock discontinuities; a stale prior-day
bar cannot open a 09:30 buy. Original ATR incorporates actual observed price
gaps from the preceding close to the next regular session.

## Exact control and separately declared clock adaptation

The exact control uses the unmodified BTC live constructors. Each model sees
eleven breakout candidates and zero trades: none has the original continuous
multi-hour resistance target. The literal engine also counts 36,780 overnight/
weekend minutes across warmup and test as clock gaps. That diagnostic is not
actual source absence; regular-session coverage is complete.

The adapted arm was declared and hashed before its replay. It changes
scheduled-closure continuity/coverage and the higher-timeframe resistance
clock, not numerical entry/exit thresholds:

- Four complete actual RTH fifteen-minute bars form a trading-hour block.
  Sixteen form a four-trading-hour block. Blocks can span scheduled closures.
  They retain their first real source start, last real source end and all
  constituent starts. These are **trading-time blocks**, not standard
  wall-clock one-/four-hour chart candles.
- Higher-timeframe peak confirmation retains two neighbours on each side;
  hourly ATR14, prominence, zone width and merging, seven-calendar-day large-
  peak retention, original wall-clock zone lookback and target ATR buffer
  remain unchanged. A peak/zone is usable only after its right neighbours'
  final actual constituents finish. No lower-timeframe target is substituted
  to force entries, and no target is selected using later outcomes.
- Original unfiltered A/B1/B2, consumed history, aggressive B1, $0.01 trigger,
  parent-D buffer, chase ceiling, positive target space with advisory 2R,
  first 25% target and original 0.1/E1/E2 exit settings remain unchanged.
  There is no ML/P1/C gate, fitted ETF threshold or parameter search.

The calendar adaptation is explicitly a separate experiment rather than a
claim of identical behavior to a 24/7 strategy. This period was already used
to study the BTC rules, so this is retrospective transfer, not unseen testing.

## Results

| Arm / model | Illustrative cash return | Max observed drawdown | Trades | Wins / losses | Realized net per fixed $10k entry |
|---|---:|---:|---:|---:|---:|
| Exact control 0.1 | 0.00% | 0.00% | 0 | 0 / 0 | $0.00 |
| Exact control E1 | 0.00% | 0.00% | 0 | 0 / 0 | $0.00 |
| Exact control E2 | 0.00% | 0.00% | 0 | 0 / 0 | $0.00 |
| Session adapted 0.1 | +0.14% | 2.14% | 4 | 1 / 3 | +$14.93 |
| Session adapted E1 | +0.30% | 1.98% | 4 | 1 / 3 | +$31.62 |
| Session adapted E2 | +0.14% | 2.14% | 4 | 1 / 3 | +$14.93 |

Every illustrative book starts with $10,000 and buys fractional shares using
available cash, including the same 2bps/side friction proxy. Partial-sale
cash stays idle until the old position exits. The next trade reinvests only
available cash, with no borrowing or added funds. Ending E1 equity is
$10,030.49. Independent fixed-$10,000-entry trade P/L sums to $31.62; it is
not the same as reinvested account P/L.

The unchanged proxy represents spread/slippage, with no broker commission.
Actual spread/depth, market impact, fill timing, taxes and trading constraints
are unverified. Observed ETF prices already reflect the fund's expenses; the
study does not double-charge them. Drawdown uses observed minute-close
liquidation equity; off-hours and intraminute lows can be worse. All books end
flat without a forced endpoint sale. IBIT buy-and-hold with the same cash and
cost proxy returns -8.20% over the actual test-session observations. Only four
strategy trades occur, too few to establish an enduring edge.

## Every adapted E1 trade

New York local times, explicitly EDT or EST. Each listed time is a source
minute interval with completed-minute availability one minute later. Prices
are model references, not actual fills. No trade reaches its first 25% target,
so all four exit their full remaining position through an original exit rule.

| Trade | Entry | Entry price | Initial stop | First 25% target | Exit | Exit price | Net per fixed $10k entry |
|---|---|---:|---:|---:|---|---:|---:|
| #1 B1 | Oct 15 10:08 EDT | $45.6985 | $45.0581 | $47.3714 | Oct 16 09:30 EDT | $46.3550 | +$139.63 |
| #2 B1 | Oct 23 10:36 EDT | $46.1800 | $45.7739 | $47.9970 | Oct 23 15:08 EDT | $45.9900 | -$45.14 |
| #3 B1 | Oct 28 10:02 EDT | $45.6550 | $45.4134 | $48.0027 | Oct 28 12:00 EDT | $45.5262 | -$32.21 |
| #4 B2 | Nov 5 13:27 EST | $43.0699 | $42.5612 | $45.8418 | Nov 5 14:29 EST | $42.9550 | -$30.67 |

The first trade demonstrates actual overnight handling. Its confirmed failed-
rebound floor is $46.355. The next session opens at $46.37, then that actual
09:30 minute trades through the floor, producing a phase-1 $46.355 threshold
exit. This is not an execution at the opening print or an off-hours sale.
The first three exits are failed-rebound/E1 protections; #4 uses the existing
turning exit. 0.1/E2 keep #3 until 12:46 at $45.45, producing a larger loss of
$48.89 per fixed-$10,000 entry. No other model entry differs.

## Interface and reproducibility

`/ibit-lab` shows all six books, the exact no-trade controls, every original
signal rejection, initial D/stop/target, recorded exit fractions, P/L and
inspected actual fifteen-minute chronology. It reads saved results only:
there is no polling, live activation or order endpoint. CSV/JSON exports
include trades, exits, protection, signals, chronology and actual equity marks.

Input is `trading_records/ibit_structure/inputs/20261003-20261109/`. Study
`20261110T235316Z-ibit-rth` contains `PROTOCOL_BEFORE_RESULTS.json`, source/code
hashes and a source bundle, preserved original files, six complete books and
`SUMMARY.csv`. Reproduce with `python3 scripts/study_ibit.py`; it creates a
separate study rather than modifying prior outcomes. The replay reads the
archive without fetching quotes. No original study selector is changed.

Tests use actual archived RTH and extended-hours observations, verify DST
and calendar close metadata, no overnight source fabrication, true account
compounding/drawdowns, actual target confirmation times, deterministic replay,
opening-gap stop price selection, readonly exports and rejection of mutation
requests. Frozen 0.2's thirteen strategy hashes and original BTC source/UI
are checked before and after. BTC retains PID 56139/session
`20261109T175620Z`; SOL remains paused. No broker or broker-paper orders.

Session references: [Nasdaq regular hours and holidays](https://www.nasdaq.com/market-activity/stock-market-holiday-schedule),
[Alpaca market calendar](https://alpaca.markets/sdks/python/api_reference/broker/calendar.html),
[Alpaca historical bars](https://docs.alpaca.markets/us/reference/stockbars).
