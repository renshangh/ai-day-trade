# ai-day-trade

This fork keeps day-trading experiments separate from `ai-8888`.

- `ai-8888`: weekly investment research, policy, memos, and long-term allocation.
- `ai-day-trade`: Lumibot-based intraday paper trading and backtesting.

## First Goal

Replace the custom `ai-8888 daytrade` execution loop with a Lumibot strategy that can use the same rules for backtests and Alpaca paper execution.

The first pilot is intentionally conservative:

- Alpaca paper only.
- Long-only US equities.
- Whole-share entries.
- Explicit stop and take-profit bracket.
- No live trading credentials.
- No automatic strategy expansion until paper logs show stable behavior.

## Local Setup

```bash
cd /Users/danielshan/Documents/Codex/github/ai-day-trade
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
cp .env.example .env
```

The local `.env` should contain the separate Alpaca day-trading paper account keys:

```text
ALPACA_IS_PAPER=true
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
```

## Pilot Run

Find the top three same-day candidates from a liquid watchlist:

```bash
python -m ai_day_trade.find_day_trade_candidates --top 3
```

The candidate scanner is read-only. It pulls real Alpaca intraday bars, scores
relative strength versus QQQ, VWAP state, high-of-day proximity, gap, and volume
participation, then optionally asks an OpenAI model to rerank and explain the
watchlist. If `OPENAI_API_KEY` is unavailable or the model call fails, the
scanner falls back to deterministic scoring. It writes the full report to
`reports/day_trade_candidates_latest.json`.

Start with a one-symbol paper pilot:

```bash
python -m ai_day_trade.alpaca_day_trade --symbol NVDA --max-notional 1000
```

By default, the pilot waits for a simple intraday entry gate before submitting
the bracket order:

- price is above VWAP,
- the prior 5-minute bar closed above VWAP,
- the prior 5-minute bar made a higher low versus the bar before it,
- current price breaks the prior 5-minute bar high.

To intentionally submit immediately after launch, pass
`--entry-strategy immediate`.

This uses Lumibot's Alpaca broker integration. Keep it paper-only until we have:

- A replayable backtest for the same rules.
- A paper ledger with fills, stop/target outcomes, time in trade, MFE/MAE, and slippage.
- Daily risk controls: max daily loss, max trades, cooldown after loss, and end-of-day flat check.
