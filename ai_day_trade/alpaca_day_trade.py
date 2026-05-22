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
    entry_strategy: str


class AiDayTradePilot(Strategy):
    """Small Lumibot pilot for Alpaca paper day-trade execution."""

    parameters = {
        "symbol": "NVDA",
        "max_notional": 1000.0,
        "take_profit_pct": 0.005,
        "stop_loss_pct": 0.0025,
        "sleeptime": "30S",
        "entry_strategy": "vwap_higher_low",
    }

    def initialize(self) -> None:
        self.symbol = str(self.parameters["symbol"]).upper()
        self.max_notional = float(self.parameters["max_notional"])
        self.take_profit_pct = float(self.parameters["take_profit_pct"])
        self.stop_loss_pct = float(self.parameters["stop_loss_pct"])
        self.sleeptime = str(self.parameters["sleeptime"])
        self.entry_strategy = str(self.parameters["entry_strategy"])
        self.submitted_entry = False

    def on_trading_iteration(self) -> None:
        if self.submitted_entry:
            return

        price = self.get_last_price(self.symbol)
        if price is None or price <= 0:
            self.log_message(f"Skipping {self.symbol}: no usable last price.")
            return

        if self.entry_strategy != "immediate" and not self._entry_signal_is_ready(float(price)):
            return

        self._submit_bracket(float(price))

    def _entry_signal_is_ready(self, price: float) -> bool:
        if self.entry_strategy == "vwap_higher_low":
            return self._vwap_higher_low_signal(price)

        raise ValueError(f"Unsupported entry_strategy={self.entry_strategy!r}")

    def _vwap_higher_low_signal(self, price: float) -> bool:
        bars = self.get_historical_prices(self.symbol, length=60, timestep="minute")
        df = getattr(bars, "df", None)
        if df is None or df.empty:
            self.log_message(f"Waiting for {self.symbol}: no minute bars available for entry signal.")
            return False

        required_columns = {"open", "high", "low", "close", "volume"}
        missing = required_columns.difference(df.columns)
        if missing:
            self.log_message(
                f"Waiting for {self.symbol}: minute bars missing columns {sorted(missing)}."
            )
            return False

        minute_bars = df.copy()
        if not getattr(minute_bars.index, "is_monotonic_increasing", False):
            minute_bars = minute_bars.sort_index()

        minute_bars = minute_bars.tail(60)
        session_volume = minute_bars["volume"].sum()
        if session_volume <= 0:
            self.log_message(f"Waiting for {self.symbol}: minute bars have no usable volume.")
            return False

        vwap = (
            ((minute_bars["high"] + minute_bars["low"] + minute_bars["close"]) / 3)
            .mul(minute_bars["volume"])
            .sum()
            / session_volume
        )
        five_minute = (
            minute_bars.resample("5min")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
        )
        if len(five_minute.index) < 3:
            self.log_message(f"Waiting for {self.symbol}: need at least three 5-minute bars.")
            return False

        previous_bar = five_minute.iloc[-2]
        prior_bar = five_minute.iloc[-3]
        trigger_price = float(previous_bar["high"])
        higher_low = float(previous_bar["low"]) > float(prior_bar["low"])
        holding_vwap = price > float(vwap) and float(previous_bar["close"]) > float(vwap)
        breaking_prior_high = price > trigger_price

        if holding_vwap and higher_low and breaking_prior_high:
            self.log_message(
                f"{self.symbol} entry signal ready: price={price:.2f}, "
                f"vwap={vwap:.2f}, trigger={trigger_price:.2f}."
            )
            return True

        self.log_message(
            f"Waiting for {self.symbol}: price={price:.2f}, vwap={vwap:.2f}, "
            f"trigger={trigger_price:.2f}, holding_vwap={holding_vwap}, "
            f"higher_low={higher_low}, breaking_prior_high={breaking_prior_high}."
        )
        return False

    def _submit_bracket(self, price: float) -> None:
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
    parser.add_argument(
        "--entry-strategy",
        choices=["vwap_higher_low", "immediate"],
        default="vwap_higher_low",
        help="Entry gate to use before submitting the first bracket order",
    )
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
            "entry_strategy": args.entry_strategy,
        },
    )
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()


if __name__ == "__main__":
    main()
