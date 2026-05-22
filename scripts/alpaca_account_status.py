import csv
import os

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest

load_dotenv()


def main() -> None:
    client = TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_API_SECRET"],
        paper=True,
    )

    orders = client.get_orders(filter=GetOrdersRequest(status="all", limit=500))
    print(f"Found {len(orders)} Alpaca orders")
    for o in orders:
        print(
            o.id,
            o.symbol,
            o.side,
            o.status,
            getattr(o, "qty", None),
            getattr(o, "filled_qty", None),
            getattr(o, "submitted_at", None),
            getattr(o, "filled_at", None),
            getattr(o, "type", None),
            getattr(o, "limit_price", None),
            getattr(o, "stop_price", None),
        )

    positions = client.get_all_positions()
    print(f"\nFound {len(positions)} Alpaca positions")
    for p in positions:
        print(p.symbol, p.qty, p.avg_entry_price, p.market_value)

    account = client.get_account()
    print("\nAccount summary:")
    print(account)

    os.makedirs("logs", exist_ok=True)
    outfile = "logs/alpaca_orders.csv"
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "symbol",
                "side",
                "status",
                "qty",
                "filled_qty",
                "submitted_at",
                "filled_at",
                "type",
                "limit_price",
                "stop_price",
            ]
        )
        for o in orders:
            writer.writerow(
                [
                    o.id,
                    o.symbol,
                    o.side,
                    o.status,
                    getattr(o, "qty", None),
                    getattr(o, "filled_qty", None),
                    getattr(o, "submitted_at", None),
                    getattr(o, "filled_at", None),
                    getattr(o, "type", None),
                    getattr(o, "limit_price", None),
                    getattr(o, "stop_price", None),
                ]
            )
    print(f"Wrote order export to {outfile}")


if __name__ == "__main__":
    main()
