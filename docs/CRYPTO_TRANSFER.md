# Frozen 0.2 SOL and ETH Transfer Backtest

Replay the unchanged BTC Live Paper model variants on real native SOL/USD and ETH/USD observations.

Last Updated: 2026-11-09
Status: Complete same-window cross-asset comparison; no live promotion
Audience: Trading Desk owner and research maintainers

## Overview

Open `/crypto-transfer` from the Trading Desk home page. Compare BTC/USD,
SOL/USD and ETH/USD across the exact 0.1, E1 and E2 constructors used by
`/btc-live`. This experiment does **not** use the newer top-ten example
library, nearest-neighbor matcher, P1 A filter or parent-HL C continuation.
All thirteen frozen strategy-source hashes are verified. The original BTC
controls are replayed first and every trade path and metric matches frozen 0.2.

The existing North Star is causal, reproducible decisions from observed data.
No missing minute is filled, no actual fill is claimed, no source or parameter
is tuned after seeing SOL/ETH outcomes, and no live order is submitted.

## Fixed window and model settings

The thirty-day UTC window is `[2026-10-10T00:00Z, 2026-11-09T00:00Z)`, with
seven-day warmup from October 3 UTC. In New York it is October 9 20:00 EDT
through November 8 19:00 EST (exclusive), including the daylight-saving change.
This matches the original comparison window; it is not a separate rolling
thirty days ending at the time of the request.

Baseline 0.1 uses `create_replay(... expanded_b=True,
exit_version='failed_rebound')`. E1/E2 use `EarlySequentialReplay` with the
same Config as Live Paper. Original A/B1/B2, consumed setup history and the
aggressive B1 convention are retained. Stops, ATR tolerances, resistance/target
selection, first 25% partial, remaining exits, one-position rule and every
numeric parameter remain unchanged. That includes the absolute **$0.01**
trigger increment applied to each asset, rather than a new asset-specific tick.
Earlier E1/E2 exits can alter later opportunities through normal sequential
state; every asset/model runs its own complete sequence.

## Results and units

| Asset | Variant | Closed / open | Wins / losses | Realized per 1 coin | Fixed $10,000 entry: realized | Fixed $10,000 entry: unrealized |
|---|---|---:|---:|---:|---:|---:|
| BTC/USD | 0.1 | 38 / 0 | 19 / 19 | $3,516.4563 | $444.59 | $0.00 |
| BTC/USD | E1 | 38 / 0 | 19 / 19 | $4,159.6666 | $527.95 | $0.00 |
| BTC/USD | E2 | 38 / 0 | 19 / 19 | $4,195.1480 | $531.53 | $0.00 |
| SOL/USD | 0.1 | 35 / 0 | 18 / 17 | $12.9844 | $1,334.90 | $0.00 |
| SOL/USD | E1 | 35 / 0 | 18 / 17 | $15.3716 | $1,581.86 | $0.00 |
| SOL/USD | E2 | 35 / 0 | 18 / 17 | $12.9844 | $1,334.90 | $0.00 |
| ETH/USD | 0.1 | 46 / 1 | 19 / 27 | $17.8772 | $82.87 | $-13.28 |
| ETH/USD | E1 | 46 / 1 | 19 / 27 | $41.4774 | $183.28 | $-13.28 |
| ETH/USD | E2 | 46 / 1 | 19 / 27 | $17.8772 | $82.87 | $-13.28 |

SOL has 35 closed trades for each variant. ETH has 46 closed and one still
open at the historical cutoff for each variant. The open ETH remainder has
no fabricated final sale; its net mark is separate from realized P/L. E1 has
the highest realized modeled result on SOL and ETH in this particular sample.
No variant is promoted to the live worker as a result.

The benchmark sizes each trade at one initial coin. Per-coin dollars are not
comparable across BTC, ETH and SOL. Each trade is also independently scaled by
`10000 / entry_reference` for the fixed-$10,000 display. These sums are not
compounded or capital-constrained returns from a $10,000 funded account, and
different asset/model books must not be added as a diversified portfolio.
Open size is marked at the last real observed minute close with remaining
proxy entry/exit costs; the last-observed timestamp is shown. No forced
window-end sale is created. Closed-trade drawdown R is not intraholding
mark-to-market account drawdown.

The original **2bps per side ETF spread/slippage proxy** remains unchanged.
This is not a claim that SOL/ETH/BTC spot trading is zero-commission or costs
only that amount. Actual crypto trading fees, fresh bid/ask, depth, order
precision and broker fills can materially change the result. Native crypto
bars may contain quote midprices and zero-volume observations, so the modeled
threshold references are not guarantees of traded/executable prices.

## Real sources, gaps and timing

SOL/USD and ETH/USD use Alpaca's same US crypto historical 1-minute endpoint
as the BTC integration, HTTPS GET only, no redirect. Every raw response is
saved compressed with its SHA256, request parameters and genuine retrieval
time. Each normalized minute archive has its own checksum. Responses are
validated for finite positive valid OHLC, nonnegative real volume, duplicate
or unaligned timestamps, and pagination loops. Unavailable data remains absent.

BTC uses its exact frozen 51,961-minute stream; its original input checksum is
verified. SOL has 47,495 observed warmup/test minutes and ETH 45,731. Of the
43,200 expected test minutes, BTC has 558 missing, SOL 1,754 and ETH 2,248.
The absent intervals remain absent; no interpolation, default OHLC or
carry-forward market data is used. Source histories can be revised by the
vendor; current SOL/ETH downloads are not proof of historical receipt timing.

The page separates all trades, no flagged gap/context, and flagged gap/context
partitions, and exposes actual missing minutes while held per trade. SOL's
accepted paths have no flagged holding/initial-context exposure in this run;
ETH has one flagged closed trade per variant. No flagged exposure does not
prove that every older resistance/context observation was complete. Missing
observations may hide triggers or exits, so this remains conditional replay.

Historical minute OHLC provides model intervals, not exact crossing seconds.
E1/E2 confirmation and exact-next-minute handling are inherited unchanged;
if that observation is absent, a fill is not carried forward or invented.
Confirmed, effective and execution-reference times remain distinct in the
15-minute ledger/protection and exit records. Entry/exit costs and fractions
reconcile in the downloads. Planned targets do not become sales unless an
actual modeled exit leg exists.

## Interpretation

This is a cross-asset transfer test over the BTC strategy's development month,
not an unseen chronological/out-of-sample validation or live profitability
proof. Unlike the separate example-library experiment, no winning SOL/ETH
examples or SOL/ETH-specific thresholds were selected. Positive sample results
do not justify automatic live trading or claims of future returns, especially
with the proxy fee model and observed gaps. Frozen parameters are not adjusted
to improve the outcome.

## Desk, exports and isolation

The desk shows nine asset/model summaries; BTC control reproduction badges;
coverage, gap partitions and modeled closed drawdown; every entry, D/L1 and
L2/HL reference when required; initial stop activation, target, each actual
partial/remainder exit and cost; current/final stop and protection history;
and actual chronological fifteen-minute observations through the exit or mark.
Choose a trade/model/asset without rerunning. CSV/JSON exports are allowlisted.
GET reads saved local results only. POST to the comparison route cannot run a
job or submit an order. No new environment variable or order client is added.

Run `python3 scripts/retest_frozen_crypto.py` only for an explicitly requested
replay, with a 20-minute external timeout. Artifacts are separate under
`trading_records/btc_structure/crypto_transfer_studies/`; its own ACTIVE.json
selects this view. Frozen 0.2 archives/results, all old research selectors,
Live Paper controls/session/rules and the BTC-only discovery configuration
are hashed before and after. Both forward workers keep running unchanged.
No signal or position from this historical run enters either forward book.

Study: `20261110T030809Z-frozen02-crypto`.
