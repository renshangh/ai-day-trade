# Quick Start

Get started quickly with Lumibot using this repository.

## 1. Install locally

Create a Python virtual environment and install the repo in editable mode:

```bash
cd /Users/danielshan/Documents/Codex/github/ai-day-trade
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

This installs the `lumibot` package and makes the local code available for development.

## 2. Run the included Alpaca sample

The repository includes a sample paper trading script for Alpaca at `ai_day_trade/alpaca_day_trade.py`.

Set your Alpaca paper API credentials in the environment or `.env` file, then run:

```bash
export ALPACA_API_KEY="your-api-key"
export ALPACA_API_SECRET="your-api-secret"
python -m ai_day_trade.alpaca_day_trade --symbol NVDA --max-notional 1000
```

The sample script uses `Alpaca` in paper mode and submits a bracket order for the requested ticker.

## 3. Create a minimal custom strategy

This example is not a file in the repo yet. Create a new file called `my_strategy.py` in the repository root with this minimal Lumibot strategy:

```python
from datetime import datetime
from lumibot.strategies import Strategy
from lumibot.backtesting import YahooDataBacktesting

class MyStrategy(Strategy):
    def on_trading_iteration(self):
        if self.first_iteration:
            aapl = self.create_order("AAPL", 10, "buy")
            self.submit_order(aapl)

MyStrategy.backtest(
    YahooDataBacktesting,
    datetime(2023, 1, 1),
    datetime(2024, 1, 1),
)
```

Then run it with:

```bash
python my_strategy.py
```

This uses the built-in `YahooDataBacktesting` data source for a quick local backtest.

## 4. What this repo contains

- `lumibot/` — the main package implementing backtesting, strategy lifecycle, brokers, AI agents, and order logic.
- `ai_day_trade/alpaca_day_trade.py` — a runnable demo strategy for Alpaca paper trading.
- `docs/` — engineering and architecture docs.
- `docsrc/` — public Sphinx documentation source.
- `tests/` — pytest coverage for backtesting, brokers, strategy flows, and integrations.

## 5. Notes and tips

- The package is published as `lumibot` and the current version in this repo is `4.5.30`.
- `ThetaTerminal.jar` is optional. If present under `lumibot/resources`, the build process bundles it automatically.
- Backtesting and live trading share the same strategy abstractions.
- If you need more features, explore `lumibot.backtesting`, `lumibot.brokers`, `lumibot.traders`, and `lumibot.strategies`.

## 6. Learn more

For full documentation, examples, broker setup, and deployment guidance, see:

- `README.md`
- `docs/`
- `docsrc/`

Happy building with Lumibot!
