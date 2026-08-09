"""Sector / theme universe for the trading desk board.

Every group is a real, hand-curated list of liquid US-listed tickers. Nothing here
is generated or inferred at runtime -- if a symbol stops returning bars we drop it
and report the omission rather than substituting anything (see AGENTS.md RULE #1).

`etf` is a reference proxy only. Group ranking uses the equal-weight mean of the
constituents' own returns, so themes without a clean ETF rank on the same basis as
GICS sectors.
"""

from __future__ import annotations

# GICS sector groups keyed by their SPDR sector ETF.
SECTORS: dict[str, dict] = {
    "Technology": {
        "etf": "XLK",
        "constituents": [
            "AAPL", "MSFT", "NVDA", "AVGO", "AMD", "CRM", "ORCL", "ADBE",
            "INTC", "QCOM", "TXN", "MU", "AMAT", "LRCX", "KLAC", "ANET",
            "NOW", "PANW", "CRWD", "SNPS", "CDNS", "INTU", "ACN", "IBM",
            "DELL", "SMCI", "MRVL", "ON", "NXPI", "ADI", "APH", "GLW",
        ],
    },
    "Consumer Discretionary": {
        "etf": "XLY",
        "constituents": [
            "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG",
            "TJX", "ORLY", "CMG", "ABNB", "MAR", "GM", "F", "RCL",
            "DHI", "LEN", "AZO", "ROST", "YUM", "LVS", "EBAY", "DRI", "ULTA",
        ],
    },
    "Communication Services": {
        "etf": "XLC",
        "constituents": [
            "GOOGL", "META", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS",
            "CHTR", "EA", "TTWO", "WBD", "OMC", "LYV", "PINS", "SNAP",
            "ROKU", "SPOT",
        ],
    },
    "Financials": {
        "etf": "XLF",
        "constituents": [
            "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "BLK",
            "SPGI", "AXP", "CB", "PGR", "MMC", "AON", "USB", "PNC",
            "TFC", "COF", "MET", "PRU", "AIG", "ICE", "CME", "V", "MA",
        ],
    },
    "Health Care": {
        "etf": "XLV",
        "constituents": [
            "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT",
            "DHR", "BMY", "AMGN", "GILD", "CVS", "CI", "ELV", "ISRG",
            "SYK", "BSX", "MDT", "VRTX", "REGN", "ZTS", "HCA", "MCK",
        ],
    },
    "Industrials": {
        "etf": "XLI",
        "constituents": [
            "CAT", "BA", "HON", "UNP", "GE", "RTX", "LMT", "DE",
            "UPS", "ADP", "ETN", "ITW", "EMR", "NOC", "GD", "CSX",
            "NSC", "FDX", "WM", "PH", "CMI", "PCAR", "ROK", "PWR",
            "POWL", "AME",
        ],
    },
    "Energy": {
        "etf": "XLE",
        "constituents": [
            "XOM", "CVX", "COP", "EOG", "SLB", "PSX", "MPC", "VLO",
            "OXY", "WMB", "KMI", "OKE", "HAL", "DVN", "FANG", "HES",
            "BKR", "TRGP",
        ],
    },
    "Consumer Staples": {
        "etf": "XLP",
        "constituents": [
            "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "MDLZ",
            "CL", "GIS", "KMB", "SYY", "KR", "STZ", "HSY", "CHD",
            "MKC", "TGT",
        ],
    },
    "Utilities": {
        "etf": "XLU",
        "constituents": [
            "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL",
            "ED", "PEG", "WEC", "ES", "AEE", "DTE", "PPL", "FE",
            "CEG", "VST", "NRG",
        ],
    },
    "Materials": {
        "etf": "XLB",
        "constituents": [
            "LIN", "APD", "SHW", "ECL", "NEM", "FCX", "DOW", "DD",
            "PPG", "NUE", "VMC", "MLM", "ALB", "IFF", "CTVA", "STLD",
        ],
    },
    "Real Estate": {
        "etf": "XLRE",
        "constituents": [
            "PLD", "AMT", "EQIX", "CCI", "PSA", "SPG", "O", "WELL",
            "DLR", "VICI", "AVB", "EQR", "EXR", "SBAC", "ARE", "INVH",
        ],
    },
}

# Non-GICS thematic groups. These cut across sectors, so they have no single ETF
# proxy; `etf` is None and ranking uses constituents only.
THEMES: dict[str, dict] = {
    "AI Optical / Interconnect": {
        "etf": None,
        "constituents": [
            "LITE", "COHR", "AXTI", "MTSI", "FN", "CRDO",
            "ANET", "ALAB", "CIEN", "MRVL", "AVGO", "APH", "GLW",
        ],
    },
    "AI Power / Datacenter Buildout": {
        "etf": None,
        "constituents": [
            "VRT", "ETN", "POWL", "CEG", "VST", "NRG", "GEV",
            "PWR", "NVT", "AMSC", "TLN",
        ],
    },
    "Semiconductors": {
        "etf": "SMH",
        "constituents": [
            "NVDA", "AVGO", "AMD", "TSM", "MU", "AMAT", "LRCX", "KLAC",
            "QCOM", "TXN", "ADI", "NXPI", "ON", "MRVL", "INTC", "MCHP",
            "SWKS", "TER", "ASML", "ARM",
        ],
    },
}

# Benchmarks shown for context; never ranked as a "sector".
BENCHMARKS: list[str] = ["SPY", "QQQ", "IWM"]


def all_groups() -> dict[str, dict]:
    """Sectors + themes in one mapping, tagged with their kind."""
    out: dict[str, dict] = {}
    for name, cfg in SECTORS.items():
        out[name] = {**cfg, "kind": "sector"}
    for name, cfg in THEMES.items():
        out[name] = {**cfg, "kind": "theme"}
    return out


def all_symbols() -> list[str]:
    """Every distinct symbol the board needs for ranking."""
    syms: set[str] = set(BENCHMARKS)
    for cfg in all_groups().values():
        if cfg.get("etf"):
            syms.add(cfg["etf"])
        syms.update(cfg["constituents"])
    return sorted(syms)
