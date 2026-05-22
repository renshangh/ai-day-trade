# Day Trade Entry Notes

One-line description: Practical intraday entry frameworks captured during ticker research.
Last Updated: 2026-05-22
Status: Working notes
Audience: Trading research, AI agents, and contributors

## Overview

These notes record intraday entry frameworks discussed during live trading
research. They are not financial advice, trade recommendations, or guarantees.
Use them as structured checklists for risk-defined day-trade planning.

## Candidate Scanner

Read-only scanner command:

```bash
python -m ai_day_trade.find_day_trade_candidates --top 3
```

The scanner pulls real Alpaca intraday bars for a liquid watchlist, ranks
candidates by relative strength versus QQQ, VWAP state, high-of-day proximity,
gap, and volume participation, then optionally asks an OpenAI model to rerank
and explain the top candidates. It writes a JSON report to
`reports/day_trade_candidates_latest.json`.

Use `--no-llm` for deterministic scoring only:

```bash
python -m ai_day_trade.find_day_trade_candidates --top 3 --no-llm
```

The scanner does not submit orders. Use the printed `alpaca_day_trade` command
only after the symbol-specific setup is acceptable.

## NVDA Day-Trade Entry Framework

Captured on 2026-05-22.

Preferred timeframe stack:

- Daily chart: broader bias, prior high/low, earnings gap levels, extension risk.
- 15-minute chart: intraday trend and whether the trade is with or against flow.
- 5-minute chart: primary setup timeframe.
- 1-minute chart: execution timing only after the 5-minute setup is valid.

Preferred long setup:

- NVDA reclaims and holds above VWAP on the 5-minute chart.
- Price forms a higher low above VWAP.
- Entry triggers on a break of the prior 5-minute candle high.
- Stop goes below the higher low or below VWAP.
- First target is prior intraday resistance.
- Only take the setup when planned reward is at least twice planned risk.

Avoid-long or short-bias conditions:

- NVDA repeatedly rejects VWAP.
- NVDA loses the opening range low.
- NVDA shows lower highs on the 5-minute chart.
- NVDA is weak relative to QQQ.

Primary levels to mark:

- VWAP.
- Opening range high and low.
- Premarket high and low.
- Prior day high and low.
- Recent earnings gap levels.

Paper command:

```bash
python -m ai_day_trade.alpaca_day_trade --symbol NVDA --max-notional 1000 --take-profit-pct 0.006 --stop-loss-pct 0.003 --sleeptime 30S
```

This command now waits for the VWAP/higher-low entry gate by default. Use
`--entry-strategy immediate` only when an immediate paper bracket is intended.

## AAPL Day-Trade Entry Framework

Captured on 2026-05-22.

Market context at capture:

- AAPL traded near 309.83 with an intraday range of 304.73 to 309.83.
- QQQ and SPY were also positive, so AAPL long setups should be judged against
  index participation rather than isolated strength alone.
- Recent Q2 earnings were a positive catalyst, with reported revenue and EPS
  above expectations, but tariff and leadership-transition headlines remain
  relevant risk context.

Preferred timeframe stack:

- Daily chart: trend, all-time-high proximity, prior earnings reaction zone, and
  gap/support levels.
- 15-minute chart: whether AAPL is trending, basing, or mean reverting intraday.
- 5-minute chart: primary setup timeframe.
- 1-minute chart: execution timing only after the 5-minute setup is valid.

Preferred long setup:

- AAPL holds above VWAP and stays stronger than or at least in line with QQQ.
- Price forms a higher low above VWAP or above the opening range midpoint.
- Entry triggers on a break of the prior 5-minute candle high.
- Stop goes below the higher low, VWAP, or the opening range midpoint depending
  on which level defined the setup.
- First target is the intraday high or next daily resistance level.
- Only take the setup when planned reward is at least twice planned risk.

Breakout setup:

- AAPL breaks the opening range high with expanding volume.
- QQQ confirms by holding above VWAP or making a new intraday high.
- Avoid chasing if the breakout candle is already far above VWAP and leaves no
  practical stop.

Avoid-long or short-bias conditions:

- AAPL fails at VWAP while QQQ is also weakening.
- AAPL breaks the opening range low and cannot reclaim it.
- AAPL makes lower highs on the 5-minute chart after a failed high-of-day push.
- Volume expands on down candles near daily resistance.

Primary levels to mark:

- VWAP.
- Opening range high, low, and midpoint.
- Premarket high and low.
- Prior day high and low.
- Recent earnings reaction high/low.
- Round-number levels near current price.

Paper command:

```bash
python -m ai_day_trade.alpaca_day_trade --symbol AAPL --max-notional 1000 --take-profit-pct 0.004 --stop-loss-pct 0.002 --sleeptime 30S
```

This command now waits for the VWAP/higher-low entry gate by default. Use
`--entry-strategy immediate` only when an immediate paper bracket is intended.
