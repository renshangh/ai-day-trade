"""Verified USD venue pairs for the onchain research map; no invented bars."""

from datetime import datetime, timezone
import math

# Kraken AssetPairs verified 2026-10-06. CCCAUSD is the desk/TradingView label;
# it maps to Canton CC/USD, never to Chemours' unrelated stock ticker CC.
PAIRS = {
    "CCCAUSD": "CCUSD", "USDT": "USDTZUSD", "PYUSD": "PYUSDUSD",
    "XRP": "XXRPZUSD", "ONDO": "ONDOUSD", "UNI": "UNIUSD",
    "AAVE": "AAVEUSD", "ETH": "XETHZUSD", "SOL": "SOLUSD",
    "AVAX": "AVAXUSD", "XLM": "XXLMZUSD", "NEAR": "NEARUSD",
    "ADA": "ADAUSD", "LINK": "LINKUSD", "VIRTUAL": "VIRTUALUSD",
    "FET": "FETUSD", "ARB": "ARBUSD", "USDC": "USDCUSD",
}


def load(symbol, fetch, now=None):
    """Return completed daily candles as supplied by Kraken, including volume."""
    pair = PAIRS[symbol]
    payload = fetch(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440")
    if payload.get("error"):
        raise ValueError("Kraken: " + ", ".join(payload["error"]))
    rows = (payload.get("result") or {}).get(pair) or []
    today = (now or datetime.now(timezone.utc)).date()
    bars = []
    seen = set()
    # Kraken always includes a final, uncommitted interval. Do not expose it as
    # a completed daily bar even if the user's clock differs from venue time.
    for row in rows[:-1]:
        if len(row) != 8:
            raise ValueError("Incomplete Kraken candle")
        timestamp = float(row[0])
        if not math.isfinite(timestamp) or timestamp % 86400:
            raise ValueError("Invalid Kraken daily timestamp")
        day = datetime.fromtimestamp(timestamp, timezone.utc).date()
        if day >= today:
            continue
        o, h, l, c, v = (float(row[i]) for i in (1, 2, 3, 4, 6))
        if not all(math.isfinite(x) for x in (o, h, l, c, v)) or min(o, h, l, c) <= 0 or v < 0 or not l <= min(o, c) <= max(o, c) <= h or day in seen:
            raise ValueError("Invalid or duplicate Kraken candle")
        seen.add(day)
        bars.append({"t": day.isoformat(), "o": o, "h": h, "l": l, "c": c, "v": v})
    bars.sort(key=lambda bar: bar["t"])
    return bars
