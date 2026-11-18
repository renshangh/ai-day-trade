# Original Unfiltered BTC and SOL: 90-Day Study

Independent original-rule replays with observed drawdown, cash-account illustrations and every losing trade.

Last Updated: 2026-11-10  
Status: Complete; historical comparison only  
Audience: Trading Desk owner and research maintainers

## Overview

North Star: causal, reproducible results from actual observations, with clear
sizing and coverage limits. Study `20261110T140721Z-unfiltered-90d` is independently
selected under `trading_records/btc_structure/unfiltered_90_studies/`.
Open `http://127.0.0.1:8799/crypto-live#unfiltered-90`.

Use the exact original frozen 0.2 constructors used by the live comparisons:
BTC 0.1/E1/E2 and SOL E1. No ML, indicator gate, P1, C, adaptive shock/weight,
new target, stop or exit policy is applied. The original absolute $0.01
trigger and all other numerical parameters remain unchanged. Both live
processes/sessions, frozen rules, archives, previous research and selectors are
preserved. No orders, broker-paper fills, real funding or new forward worker.

## Period and real source coverage

Keep the existing endpoint **November 9, 2026 00:00 UTC, exclusive**, so the new
window is **August 11 00:00 UTC–November 9 00:00 UTC**, ninety elapsed days,
with seven days of warmup from August 4. In New York it starts August 10 at
20:00 EDT and ends November 8 at 19:00 EST.

The original October 3–November 9 suffix archives remain untouched and retain
their exact hashes/observations. A newly joined archive does not overwrite them.
Earlier BTC observations are a validated read-only SELECT from the original
Alpaca cache, frozen into an independent selected-row archive/hash. Earlier SOL
observations come from approved Alpaca historical market-data GETs only, with
raw response hashes, params and timestamps. No data is written into shared
caches or either live observation store. No alternative vendor is mixed into
a gap and no missing minute is treated as a zero-volume observation.

Every requested UTC day has observations, but coverage is incomplete:

| Asset | Observed test minutes | Expected | Missing | Coverage |
|---|---:|---:|---:|---:|
| BTC | 124,731 | 129,600 | 4,869 | 96.24% |
| SOL | 101,072 | 129,600 | 28,528 | 77.99% |

Daily counts and every absence are saved. Actual zero-volume bars can be
quote-derived, as explained in [Alpaca's market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq).
Missing bars remain absent. Earlier SOL is particularly sparse. An observed-
minute backtest cannot establish what happened inside missing intervals; trade
qualifications can be missed and drawdown/fill realism is limited. Do not
present this as ninety fully observed days or a complete measure of downside.

## Reproduced controls and unchanged strategy results

Before each ninety-day replay, reproduce the original standalone thirty-day
entry, risk, target, exit and metric paths exactly from the original suffix.
All four controls pass. They are separately reset flat; a continuous ninety-day
book can carry different positions and consumed setup history into its final
month. Do not subtract the standalone thirty-day return from the ninety-day
return and call the difference a separately replayed earlier period.

The strategy still runs one initial coin per reference trade. Its original
per-coin P/L, sum of fixed-$10,000-entry normalized P/L, original closed-trade
R drawdown, 25% partial/75% remainder legs and open marks are preserved. Fixed-
notional normalized P/L is not itself an account return.

## Reporting-only illustrative cash scenario

For an additional comparable return/drawdown measure, independently rescale
each saved trade book to an illustrative $10,000 starting cash account:

- Buy fractional units with all available cash, including the original 2bps
  entry friction: `units = cash / (entry × 1.0002)`.
- Scale each original exit fraction by the initial units; sale proceeds are
  `units_sold × exit × 0.9998`. Partial-sale cash stays idle until the old
  position has fully exited. A new trade reinvests only available cash.
- Never borrow, add capital, overlap positions, change a fill reference or
  create an order. This is reporting arithmetic, not a new strategy sizing rule.
- At every actual observed minute close, liquidation-value equity is cash plus
  remaining units × observed close × 0.9998. Missing minutes get no marks.
- An open remainder is marked, not forcibly sold at the endpoint. Realized
  funded trade P/L and hypothetical liquidation marks are kept distinct.
- Maximum observed minute-close drawdown uses the running equity peak and
  includes open-position marks. Intraminute/gap lows can be worse. Peak,
  trough and observed recovery timestamps are saved. Closed-trade R drawdown
  remains a different original strategy metric.

The illustration assumes arbitrary fractional size, no market impact, no
minimum lot/venue size restrictions and unchanged proxy fills. It is not an
actual Alpaca or Schwab account. The frozen 2bps/side ETF cost proxy excludes
actual spot-crypto fees, interest, funding and taxes. These limits matter given
the sparse venue volume and numerous reference trades.

For fully closed books, ending cash independently reconciles to
`10000 × product(1 + original_trade_net / (entry × 1.0002))`. This is tested,
as are partial positions, entry cash, trade costs and all actual equity marks.

## Ninety-day results

Illustrative independent cash books, original rules and costs:

| Book | Total return | Max observed minute-close drawdown | Closed trades | Wins / losses | Longest loss streak | Profit factor, fixed-notional net |
|---|---:|---:|---:|---:|---:|---:|
| BTC/USD 0.1 | 0.12% | 5.32% | 80 | 38 / 42 | 7 | 1.016 |
| BTC/USD E1 | 1.83% | 4.75% | 80 | 38 / 42 | 7 | 1.132 |
| BTC/USD E2 | 1.00% | 5.32% | 80 | 38 / 42 | 7 | 1.073 |
| SOL/USD E1 | 14.02% | 5.37% | 44 | 22 / 22 | 5 | 2.116 |

All books end flat at the last actual mark, November 9 00:00 UTC. BTC E1's
ending equity is about $10,183.20; SOL E1's is about $11,401.79. These are
historical reference simulations, not actual returns or forecasts.

The original standalone thirty-day illustrative returns are +4.43% / +5.31% /
+5.35% for BTC 0.1/E1/E2 and +16.78% for SOL E1. Adding the older history
weakens total results; the recent favorable month does not establish strength
across this longer sample. No strategy is modified after viewing the results.

With the same starting cash, actual first observed opening, actual final mark
and friction, buy-and-hold returns +16.93% for BTC and +13.82% for SOL. Observed
buy-and-hold drawdowns are 15.57% and 31.48%, respectively. BTC's strategy gives
up substantial upside in this sample while showing lower observed drawdown.
SOL's illustrative return is close to buy-and-hold with lower observed
drawdown, but missing-data, liquidity and fee limits prevent a live superiority
claim. This is not a combined BTC/SOL allocation or account.

## Losing-trade review

Loss means a fully closed trade with net < 0; breakevens are separate. The
longer BTC book has 42 losses out of 80 and a seven-loss streak. SOL has 22
losses out of 44 and a five-loss streak. Worst fixed-$10k losses are roughly
-$94.57 for BTC E1 and -$161.30 for SOL. A final stop may follow a prior 25%
profit; final exit reason alone cannot determine full-trade profitability.

The desk lists every loser, sorted by fixed-notional loss, and can switch to
all chronological trades or open positions. Each has entry/exit references,
original D/L1 and L2, initial stop activation, target, stop raises, actual model
exit fractions/costs, per-coin/fixed-notional net, R, illustrative entry cash
and funded leg P/L, holding duration and gap flags. Entry-type and final-reason
breakdowns and longest loss streak always describe the full book.

Exposure filters affect only the trade list. Full-book equity/account returns
and drawdowns remain unchanged. A hindsight "gap-free" cohort must not be
presented as a new tradable filtered account. The 90-day BTC E1 book has 26
flagged-gap/context trades; SOL has nine. Quality partitions remain available
in original summary/exports for audit.

## Interface and reproduction

The period selector switches between the original reset thirty-day control
and the continuous ninety-day replay. It never reruns or mutates a strategy.
Daily tables show actual last observed UTC-day marks, with New York timestamps
and real observed-minute counts; they are not official session closes. Missing
observations are never carried forward. All CSV/JSON/gzipped equity exports are
allowlisted and read-only.

To reproduce in a new isolated study:

1. `python3 scripts/prepare_unfiltered_90d.py` obtains/verifies the independent
   earlier prefix; source requests are market-data GET only.
2. `python3 scripts/study_unfiltered_90d.py` reproduces the original controls,
   runs all four ninety-day books and saves exact source/code bundles, ledgers,
   original trades/losers/protection, funded account arithmetic and minute marks.

Each long job is bounded externally to twenty minutes. Preserve every old
study and selector, never delete shared caches or update live source/session
files. Original-rule hashes, protected-file hashes and both live PID/session
identities are verified before/after. No new environment variable is introduced.

Rules were developed using the overlapping recent month. This ninety-day
historical extension is not prospective or genuinely out-of-sample validation,
and its positive illustrative outcomes do not demonstrate future profitability.
