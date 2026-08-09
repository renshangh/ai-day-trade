"""Company detail: SEC fundamentals, news headlines, and research links.

Fundamentals come from SEC XBRL filings via Lumibot's `SECFundamentals`, so every
figure is something the company actually filed, carrying its period, form type and
filing date. News comes from the Alpaca News API.

RULE #1 applies here as much as to price bars: a number we cannot derive honestly
is reported as unavailable, with the reason, rather than approximated. In
particular P/E is only computed when a genuine trailing-twelve-month EPS can be
reconstructed, and never from a single quarter's EPS.

Lumibot is imported lazily: if it is unavailable the rest of the panel (news,
links, price-derived stats) still works.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.parse
import urllib.request
from typing import Any

_sec: Any = None
_sec_error: str | None = None


def _get_sec() -> Any:
    """Lazily construct the SEC client; cache the failure if it can't load."""
    global _sec, _sec_error
    if _sec is not None or _sec_error is not None:
        return _sec
    try:
        from lumibot.fundamentals.sec import SECFundamentals

        _sec = SECFundamentals()
    except Exception as e:  # noqa: BLE001 - optional dependency
        _sec_error = f"SEC fundamentals unavailable: {e}"
    return _sec


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _span_days(row: dict) -> int | None:
    try:
        return (_d(row["end"]) - _d(row["start"])).days
    except Exception:  # noqa: BLE001
        return None


def _deduped_rows(raw: dict, concept: str, unit: str) -> list[dict]:
    """Rows for one XBRL concept, deduped by period keeping the latest filing.

    The same period is restated across filings; the most recently filed value is
    the current one.
    """
    rows = (
        raw.get("facts", {})
        .get("us-gaap", {})
        .get(concept, {})
        .get("units", {})
        .get(unit, [])
    )
    best: dict[tuple[str, str], dict] = {}
    for r in rows:
        if not r.get("start") or r.get("val") is None:
            continue
        key = (r["start"], r["end"])
        if key not in best or r.get("filed", "") > best[key].get("filed", ""):
            best[key] = r
    return sorted(best.values(), key=lambda r: (r["end"], r["start"]))


def ttm_diluted_eps(raw: dict) -> tuple[float | None, str]:
    """Trailing-twelve-month diluted EPS, or (None, reason).

    Companies do not file a Q4 10-Q, so the four most recent quarters are never
    all present as quarterly rows. The standard reconstruction is:

        TTM = last full fiscal year + current YTD - prior-year YTD of equal length

    If an annual row already ends on the latest reported date, that row *is* the
    trailing year and is used directly.
    """
    rows = _deduped_rows(raw, "EarningsPerShareDiluted", "USD/shares")
    if not rows:
        return None, "no diluted EPS reported"

    annual = [r for r in rows if (s := _span_days(r)) and 350 <= s <= 380]
    if not annual:
        return None, "no annual EPS row"

    latest_end = rows[-1]["end"]
    for r in reversed(annual):
        if r["end"] == latest_end:
            return r["val"], f"annual filing {r['start']} to {r['end']} ({r.get('form', '')})"

    fy = annual[-1]
    ytd = [
        r for r in rows
        if _d(r["end"]) > _d(fy["end"]) and (s := _span_days(r)) and 60 < s < 350
    ]
    if not ytd:
        return None, f"no year-to-date row after fiscal year ending {fy['end']}"
    cur = max(ytd, key=lambda r: _d(r["end"]))
    cur_len = _span_days(cur) or 0

    prior = [
        r for r in rows
        if (s := _span_days(r)) and abs(s - cur_len) <= 8
        and abs((_d(cur["end"]) - _d(r["end"])).days - 365) <= 10
    ]
    if not prior:
        return None, f"no prior-year period matching the {cur_len}-day year-to-date"

    p = prior[-1]
    value = fy["val"] + cur["val"] - p["val"]
    note = (
        f"FY to {fy['end']} ({fy['val']}) + YTD {cur['start']} to {cur['end']} "
        f"({cur['val']}) - prior-year YTD ({p['val']})"
    )
    return value, note


def shares_outstanding(raw: dict) -> tuple[float | None, str | None, str | None]:
    """Latest reported common shares outstanding: (shares, as_of, filed)."""
    units = (
        raw.get("facts", {})
        .get("dei", {})
        .get("EntityCommonStockSharesOutstanding", {})
        .get("units", {})
        .get("shares", [])
    )
    if not units:
        return None, None, None
    latest = max(units, key=lambda r: (r.get("end", ""), r.get("filed", "")))
    return latest.get("val"), latest.get("end"), latest.get("filed")


# Companies migrate between revenue tags (COHR stopped using `Revenues` in 2018),
# so these alternates are resolved by recency rather than by list order --
# otherwise a long-abandoned tag renders as if it were the current figure.
REVENUE_CONCEPTS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                    "SalesRevenueNet")

# Facts worth showing, in display order.
FACT_LABELS: list[tuple[str, str]] = [
    ("__revenue__", "Revenue"),
    ("GrossProfit", "Gross profit"),
    ("OperatingIncomeLoss", "Operating income"),
    ("NetIncomeLoss", "Net income"),
    ("EarningsPerShareDiluted", "EPS (diluted, period)"),
    ("ResearchAndDevelopmentExpense", "R&D expense"),
    ("Assets", "Total assets"),
    ("Liabilities", "Total liabilities"),
    ("StockholdersEquity", "Shareholders' equity"),
    ("CashAndCashEquivalentsAtCarryingValue", "Cash & equivalents"),
    ("NetCashProvidedByUsedInOperatingActivities", "Operating cash flow"),
]


def key_facts(compact: dict) -> list[dict]:
    """Latest filed value for each display fact, with its period and provenance."""
    facts = compact.get("facts", compact) or {}
    out: list[dict] = []
    for concept, label in FACT_LABELS:
        if concept == "__revenue__":
            candidates = [
                facts[c] for c in REVENUE_CONCEPTS
                if isinstance(facts.get(c), dict) and facts[c].get("value") is not None
            ]
            if not candidates:
                continue
            row = max(candidates, key=lambda r: (r.get("end") or "", r.get("filed") or ""))
        else:
            row = facts.get(concept)
        if not isinstance(row, dict) or row.get("value") is None:
            continue
        out.append({
            "label": label,
            "value": row.get("value"),
            "unit": row.get("unit"),
            "form": row.get("form"),
            "fy": row.get("fy"),
            "fp": row.get("fp"),
            "start": row.get("start"),
            "end": row.get("end"),
            "filed": row.get("filed"),
        })
    return out


def get_fundamentals(symbol: str, last_price: float | None) -> dict:
    """SEC-derived fundamentals for one symbol."""
    sec = _get_sec()
    if sec is None:
        return {"available": False, "reason": _sec_error or "SEC client unavailable"}
    try:
        raw = sec.get_company_facts(symbol, raw=True)
        compact = sec.get_company_facts(symbol)
    except Exception as e:  # noqa: BLE001 - surface the absence, don't guess
        return {"available": False, "reason": f"SEC lookup failed: {e}"}

    eps, eps_note = ttm_diluted_eps(raw)
    shares, shares_as_of, shares_filed = shares_outstanding(raw)

    market_cap = shares * last_price if (shares and last_price) else None
    if eps is None:
        pe, pe_note = None, eps_note
    elif eps <= 0:
        pe, pe_note = None, "negative trailing earnings - P/E is not meaningful"
    elif last_price is None:
        pe, pe_note = None, "no current price"
    else:
        pe, pe_note = last_price / eps, eps_note

    entity = raw.get("entityName")
    return {
        "available": True,
        "entity_name": entity,
        "cik": raw.get("cik"),
        "market_cap": market_cap,
        "shares_outstanding": shares,
        "shares_as_of": shares_as_of,
        "shares_filed": shares_filed,
        "ttm_eps": eps,
        "ttm_eps_note": eps_note,
        "pe_ratio": pe,
        "pe_note": pe_note,
        "facts": key_facts(compact),
    }


def get_news(symbol: str, api_key: str, api_secret: str, limit: int = 12) -> list[dict]:
    """Recent headlines for a symbol from the Alpaca News API."""
    params = {"symbols": symbol, "limit": limit, "sort": "desc"}
    url = "https://data.alpaca.markets/v1beta1/news?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret,
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    out = []
    for a in data.get("news", []):
        url_ = a.get("url") or ""
        # Only pass through http(s); the frontend links these out.
        if url_ and not url_.startswith(("http://", "https://")):
            url_ = ""
        out.append({
            "headline": a.get("headline", ""),
            "source": a.get("source", ""),
            "author": a.get("author", ""),
            "url": url_,
            "created_at": a.get("created_at", ""),
            "symbols": a.get("symbols", []),
        })
    return out


def research_links(symbol: str, cik: Any = None) -> list[dict]:
    """External research destinations. Plain URL construction - nothing fetched."""
    s = urllib.parse.quote(symbol)
    links = [
        {"label": "Yahoo — Analysis", "url": f"https://finance.yahoo.com/quote/{s}/analysis",
         "note": "Analyst estimates, ratings, price targets"},
        {"label": "Yahoo — Profile", "url": f"https://finance.yahoo.com/quote/{s}/profile",
         "note": "Company profile, sector, executives"},
        {"label": "Finviz", "url": f"https://finviz.com/quote.ashx?t={s}",
         "note": "Valuation ratios, ownership, analyst ratings"},
        {"label": "StockAnalysis", "url": f"https://stockanalysis.com/stocks/{s}/",
         "note": "Financial statements and ratios"},
        {"label": "TradingView", "url": f"https://www.tradingview.com/symbols/{s}/",
         "note": "Charting and technical ideas"},
    ]
    if cik:
        try:
            cik_num = int(str(cik).lstrip("0") or "0")
            links.append({
                "label": "SEC EDGAR filings",
                "url": ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                        f"&CIK={cik_num:010d}&type=10-&dateb=&owner=include&count=40"),
                "note": "Primary source 10-K / 10-Q filings",
            })
        except (TypeError, ValueError):
            pass
    return links
