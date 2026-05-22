"""
AAPL Backtest Example for Lumibot

This example buys AAPL only when the trend is positive and exits on either a
fixed take-profit or stop-loss.

Run:
    python examples/aapl_backtest.py
"""

from datetime import datetime
from lumibot.strategies import Strategy
from lumibot.backtesting import YahooDataBacktesting


class AAPLBacktestStrategy(Strategy):
    parameters = {
        "symbol": "AAPL",
        "quantity": 10,
        "take_profit_pct": 0.05,
        "stop_loss_pct": 0.02,
        "fast_ma": 10,
        "slow_ma": 20,
    }

    def initialize(self):
        self.entry_price = None
        self.position_open = False
        self.log_message(
            f"Initialized backtest for {self.parameters['symbol']} "
            f"quantity={self.parameters['quantity']} "
            f"TP={self.parameters['take_profit_pct']*100:.1f}% "
            f"SL={self.parameters['stop_loss_pct']*100:.1f}%",
            color="green",
        )

    def on_trading_iteration(self):
        symbol = self.parameters["symbol"]
        bars = self.get_historical_prices(symbol, 40, "day")
        df = bars.pandas_df

        if df is None or df.empty or len(df) < self.parameters["slow_ma"] + 1:
            self.log_message("Waiting for enough historical data before entering", color="yellow")
            return

        stop_price = float(df["close"].iloc[-1])
        current_price = float(df["close"].iloc[-1])
        fast_ma = float(df["close"].rolling(self.parameters["fast_ma"]).mean().iloc[-1])
        slow_ma = float(df["close"].rolling(self.parameters["slow_ma"]).mean().iloc[-1])

        if not self.position_open:
            if current_price > fast_ma > slow_ma:
                self.log_message(
                    f"Entry signal: price={current_price:.2f} fast_ma={fast_ma:.2f} slow_ma={slow_ma:.2f}",
                    color="green",
                )
                order = self.create_order(symbol, self.parameters["quantity"], "buy", type="market")
                self.submit_order(order)
                self.entry_price = current_price
                self.position_open = True
            else:
                self.log_message(
                    f"No entry: price={current_price:.2f} fast_ma={fast_ma:.2f} slow_ma={slow_ma:.2f}",
                    color="yellow",
                )
            return

        if self.entry_price is None:
            self.entry_price = current_price

        take_profit_price = self.entry_price * (1 + self.parameters["take_profit_pct"])
        stop_loss_price = self.entry_price * (1 - self.parameters["stop_loss_pct"])

        self.log_message(
            f"Holding position: price={current_price:.2f} entry={self.entry_price:.2f} "
            f"TP={take_profit_price:.2f} SL={stop_loss_price:.2f}",
            color="yellow",
        )

        if current_price >= take_profit_price:
            self.log_message("Take-profit target reached, exiting position", color="green")
            self.close_position(symbol)
            self.position_open = False
            self.entry_price = None
        elif current_price <= stop_loss_price:
            self.log_message("Stop-loss triggered, exiting position", color="red")
            self.close_position(symbol)
            self.position_open = False
            self.entry_price = None
        elif current_price < slow_ma:
            self.log_message("Trend turned down, closing position", color="yellow")
            self.close_position(symbol)
            self.position_open = False
            self.entry_price = None

    def on_abrupt_closing(self):
        self.log_message("Abrupt exit: closing AAPL position if still open", color="yellow")
        self.close_position(self.parameters["symbol"])


if __name__ == "__main__":
    AAPLBacktestStrategy.backtest(
        YahooDataBacktesting,
        datetime(2023, 1, 1),
        datetime(2024, 1, 1),
        quiet_logs=False,
    )
