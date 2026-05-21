from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass

from lumibot.brokers import Alpaca
from lumibot.credentials import ALPACA_CONFIG
from lumibot.entities import Order
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader


@dataclass(frozen=True)
class DayTradeSettings:
    symbol: str
    max_notional: float
    take_profit_pct: float
    stop_loss_pct: float
    sleeptime: str


class AiDayTradePilot(Strategy):
    """Small Lumibot pilot for Alpaca paper day-trade execution."""

    parameters = {
        "symbol": "NVDA",
        "max_notional": 1000.0,
        "take_profit_pct": 0.005,
        "stop_loss_pct": 0.0025,
        "sleeptime": "30S",
    }

    def initialize(self) -> None:
        self.symbol = str(self.parameters["symbol"]).upper()
        self.max_notional = float(self.parameters["max_notional"])
        self.take_profit_pct = float(self.parameters["take_profit_pct"])
        self.stop_loss_pct = float(self.parameters["stop_loss_pct"])
        self.sleeptime = str(self.parameters["sleeptime"])
        self.submitted_entry = False

    def on_trading_iteration(self) -> None:
        if self.submitted_entry:
            return

        price = self.get_last_price(self.symbol)
        if price is None or price <= 0:
            self.log_message(f"Skipping {self.symbol}: no usable last price.")
            return

        quantity = math.floor(self.max_notional / float(price))
        if quantity < 1:
            self.log_message(
                f"Skipping {self.symbol}: max_notional={self.max_notional:.2f} cannot buy one whole share."
            )
            self.submitted_entry = True
            return

        take_profit_price = round(float(price) * (1 + self.take_profit_pct), 2)
        stop_loss_price = round(float(price) * (1 - self.stop_loss_pct), 2)
        order = self.create_order(
            self.symbol,
            quantity,
            Order.OrderSide.BUY,
            secondary_limit_price=take_profit_price,
            secondary_stop_price=stop_loss_price,
            order_class=Order.OrderClass.BRACKET,
        )
        self.submit_order(order)
        self.submitted_entry = True
        self.log_message(
            f"Submitted {self.symbol} bracket: qty={quantity}, "
            f"target={take_profit_price:.2f}, stop={stop_loss_price:.2f}."
        )

    def on_abrupt_closing(self) -> None:
        self.sell_all()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m ai_day_trade.alpaca_day_trade")
    parser.add_argument("--symbol", default="NVDA", help="Ticker to paper trade")
    parser.add_argument("--max-notional", type=float, default=1000.0, help="Maximum paper notional")
    parser.add_argument("--take-profit-pct", type=float, default=0.005, help="Bracket take-profit percentage")
    parser.add_argument("--stop-loss-pct", type=float, default=0.0025, help="Bracket stop-loss percentage")
    parser.add_argument("--sleeptime", default="30S", help="Lumibot strategy loop interval")
    args = parser.parse_args()

    if not os.environ.get("ALPACA_API_KEY") or not os.environ.get("ALPACA_API_SECRET"):
        raise SystemExit("Missing ALPACA_API_KEY or ALPACA_API_SECRET in environment/.env.")
    if not ALPACA_CONFIG.get("PAPER"):
        raise SystemExit("Refusing to run: ALPACA_IS_PAPER must be true.")

    broker = Alpaca(ALPACA_CONFIG)
    strategy = AiDayTradePilot(
        broker=broker,
        parameters={
            "symbol": args.symbol,
            "max_notional": args.max_notional,
            "take_profit_pct": args.take_profit_pct,
            "stop_loss_pct": args.stop_loss_pct,
            "sleeptime": args.sleeptime,
        },
    )
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()


if __name__ == "__main__":
    main()
