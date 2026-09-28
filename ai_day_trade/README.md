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

## Top AI Coins — Crypto Trade Watchlist

For a crypto-focused version of the watchlist, start with these five AI-related
projects. This is a research universe, not a live market-cap ranking or a buy
recommendation. Crypto liquidity, exchange availability, token names, and the
AI narrative can change quickly, so verify current data before every trade.

| Rank | Project | Symbol | Community | How the token is used |
| --- | --- | --- | --- | --- |
| 1 | NEAR Protocol | `NEAR` | Developers building dapps, wallets, and autonomous agents | Pays for network transactions and supports applications and agents on NEAR |
| 2 | Bittensor | `TAO` | Subnet teams, miners, validators, and machine-intelligence users | Coordinates incentives; miners provide work and validators assess quality |
| 3 | Render Network | `RENDER` | Artists, studios, developers, and GPU operators | Pays for distributed GPU jobs and rewards node operators |
| 4 | Artificial Superintelligence Alliance | `FET` | Agent developers, data scientists, and open-AI users | Supports access, coordination, and incentives across participating services |
| 5 | Akash Network | `AKT` | Cloud providers, GPU operators, developers, and workload owners | Prices and settles compute leases and rewards providers |

The Trading Desk shows both the community and token-use explanations on each
watchlist card. These describe intended network roles, not proof of current
activity or adoption; verify usage metrics and venue support before trading.

### A conservative crypto trade workflow

1. Pull real bars and quotes for the exact exchange and symbol. If data is
   missing, skip the symbol—never fill the gap with synthetic or carried-forward
   market data.
2. Rank candidates using liquidity, spread, relative strength, volume
   participation, and trend state. Treat the AI theme as context, not as an
   entry signal by itself.
3. Confirm the venue supports the exact symbol and market type (`spot` or
   `perpetual`) before creating an order.
4. Apply smaller position limits than the equity pilot, define a hard stop,
   account for fees and funding, and keep leverage at zero until the paper
   results justify changing it.
5. Paper trade and log fills, slippage, funding, time in trade, MFE/MAE, and
   stop/target outcomes before enabling any live route.

For implementation, use Lumibot's documented CCXT crypto paths and set the
market to `24/7`. The scanner should remain read-only until the crypto-specific
paper ledger and risk controls are in place. The category framing is informed by
[CoinGecko's AI category](https://www.coingecko.com/en/categories/artificial-intelligence)
and the project descriptions from [Bittensor](https://www.bittensor.com/),
[Render](https://rendernetwork.com/), [NEAR](https://near.org/), and
[Akash](https://akash.network/).

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
