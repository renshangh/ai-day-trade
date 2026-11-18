# Same-Window BTC Pattern Transfer Backtest

Replay the current stock/ETF mover list using the fixed draft-2 BTC pattern library.

Last Updated: 2026-11-09
Status: Complete retrospective research; not out-of-sample; no promotion
Audience: Trading Desk owner and research maintainers

## Overview

Open `/pattern-backtest`, also linked from Pattern Discovery and the trading
home page. The same thirty-day UTC interval is `[2026-10-10T00:00Z,
2026-11-09T00:00Z)`, with the original seven-day warmup. In New York that is
October 9 20:00 EDT through November 8 19:00 EST (exclusive). Equities have
twenty tested regular sessions, October 12 through November 6. The current
13-name list and draft-2 library are snapshotted independently of live state.

All twelve stocks/ETFs were tested. They generated three trades: one TQQQ
winner, one ASTS loser and one NBIS loser. Nine names had zero accepted entries.
No thresholds, similarity gate, stop, target or exit parameters were retuned in
response. The sum of the three separate $10,000-per-entry modeled profits is
-$51.16; this is not a funded portfolio or an account return. No positions are
open at this window's end. BTC is a reference row and is never mixed into a
stock/ETF account total.

## Per-symbol results

| Symbol | Trades | Wins/losses | Realized net per 1 unit | Sum at fixed $10,000 per entry |
|---|---:|---:|---:|---:|
| BTC/USD | 10 | 10/0 | $7,488.0782 | $940.37 |
| CIFR | 0 | 0/0 | $0.0000 | $0.00 |
| AXTI | 0 | 0/0 | $0.0000 | $0.00 |
| IREN | 0 | 0/0 | $0.0000 | $0.00 |
| LITE | 0 | 0/0 | $0.0000 | $0.00 |
| CRDO | 0 | 0/0 | $0.0000 | $0.00 |
| CRWV | 0 | 0/0 | $0.0000 | $0.00 |
| ASTS | 1 | 0/1 | $-0.1954 | $-49.40 |
| NBIS | 1 | 0/1 | $-0.8681 | $-55.18 |
| SOXL | 0 | 0/0 | $0.0000 | $0.00 |
| TQQQ | 1 | 1/0 | $0.3868 | $53.43 |
| SOXX | 0 | 0/0 | $0.0000 | $0.00 |
| SMH | 0 | 0/0 | $0.0000 | $0.00 |

An equity/ETF unit means one share (a comparable adjusted share for split
symbols); the BTC unit is 1 BTC. The normalization multiplies each trade's
actual modeled legs by `10000 / entry_reference`. It does not change decisions,
introduce a cash budget, compound capital or net simultaneous exposures.
Existing 2 bps per-side spread/slippage proxy is retained; actual commissions,
crypto fees and executable fills are not claimed. Open remaining size would
stay open, marked at the last actual observed price, with unrealized net
separate; the engine never creates a forced final-window sale.

## Selection bias and interpretation

This is explicitly **retrospective**. The BTC winning/losing reference library
was selected using this same month's outcomes, and the high-volume/beta/ATR
universe uses November 9 completed data after the test window ends. These
choices are future information relative to early historical decisions. The
minute-by-minute market features remain causal within the replay, but that
does not make the overall experiment out-of-sample. The ten BTC winners and
positive BTC reference result cannot be used as evidence of predictive power.

The existing library enables nine unflagged winning examples and seventeen
losing lookalikes. The flagged third-ranked winner remains visible in the
library but does not enable matching. B1 is the only defined entry family;
A/B2/C cannot open this experiment. Targets use the existing PatternReplay
stock/ETF prominent-15m-pivot policy and the original BTC hourly policy.

Across stocks/ETFs there were 81 otherwise-would-open checks: 33 rejected for
incomplete **continuous BTC-style** context, 42 for a route outside the B1
library, three for nearer losing lookalikes, and three accepted. Earlier
structure/risk/held-position rejections remain in SIGNALS.csv and diagnostics.
The context gate requires fourteen full consecutive 15-minute bars, so a normal
overnight closure blocks morning stock entries even if every regular-session
minute exists. This restriction was preserved, not silently relaxed.

## Source observations and corporate actions

Stocks/ETFs use actual Alpaca consolidated SIP minute OHLCV, raw price basis
unless an in-window split requires an explicitly labeled vendor split-adjusted
series. Every request is HTTPS GET with pinned data/calendar hosts and no
redirects/order client. Compressed raw pages, hashes, normalized observed-only
minute archives and the exchange calendar are saved with the study. Missing
minutes remain absent. The forward paper worker still uses IEX; this historical
SIP result is not a forward-feed or live broker fill-parity claim.

There are 7,800 expected test minutes per stock/ETF, excluding nights, holidays
and weekends using real calendar open/close times including daylight saving.
All selected stocks/ETFs have complete test-session coverage. One absent AXTI
minute lies in warmup, outside the tested interval.
BTC reuses the exact frozen 51,961-minute source and its source SHA, with 558
absent minutes in the test period. No missing price or volume is substituted.

SOXX's observed daily raw/split factors establish a 3:1 basis change on
November 5. The first diagnostic check was too sensitive to cent-rounding and
incorrectly marked many dates. A regression now intersects half-cent price
rounding bounds, identifying only the genuine factor change. Earlier studies
are retained. The final SOXX replay uses real provider `adjustment=split`
minute observations for a constant comparable-share basis, not locally invented
prices or share transactions. Its unchanged $0.01 trigger applies to adjusted
prices; raw historical tick/fill equivalence is not claimed. Missing adjusted
data would make the symbol unavailable. SOXX generated zero trades.

The other twelve symbol trade paths match the preceding raw-price replay
exactly, including every entry, stop, target, exit leg and P/L. The data-check
repair did not change their trading behavior.

## Timing, overnight risk and audit exports

Historical complete minute OHLC is assumed delivered at its minute end with
zero extra latency. The model's `detected_at` field is explicitly a simulated
availability clock, never an actual historical network receipt or fill time.
Entry/exit records retain minute intervals and unknown exact crossing seconds.
All decisions require the setup and previous complete candle to be known.

Stock positions can remain held over regular-session closures; protection is
processed only when the next real regular-session minute arrives. A gap through
a stop uses the observed opening price under the inherited adverse-first logic.
The inherited BTC engine flags scheduled closures as gaps. The page separately
counts **actual missing required session minutes while held**, so ASTS's normal
weekend closure is not falsely presented as missing stock data. Its first 25%
profit and remaining 75% stop loss are both visible. Planned targets are never
shown as actual sale prices unless an exit leg exists.

The page provides all thirteen summaries, full per-symbol trade tables,
entry/stop effective times, first 25% and remainder exit legs, nearest pattern
labels, costs, per-unit and normalized P/L, protection history, actual 15-minute
chronology, rejection reasons and safe CSV/JSON downloads. Zero-trade names
retain coverage and diagnostic reasons. GET never fetches data or runs a job;
POST to the backtest route is refused.

## Isolation and reproducibility

`python3 scripts/retest_pattern_watchlist.py` performs a separate saved replay
with a 20-minute external timeout recommended. Results live under
`trading_records/pattern_discovery/backtests/`; only its independent ACTIVE.json
selects this view. Each study pins library/source/code hashes and preservation
checks. Frozen 0.2, prior P1/C studies, main research selectors, forward discovery
config/library and the original Live Paper worker/control/session stay unchanged.
This is comparison-only: no previews, broker paper orders or live submissions.

Study: `20261110T021026Z-patterns-30d`.
