# Trading Desk — Hot Sector Board

Local dashboard that ranks sectors and themes by short-horizon momentum and charts
the top movers with the standard technical indicator set.

**Last Updated:** 2026-08-09
**Status:** Active
**Audience:** Both

---

## Overview

For each lookback window (1, 2, 3, 4 and 5 trading days) the board:

1. ranks all 14 groups (11 GICS sectors + 3 themes) by the equal-weight mean
   return of their constituents,
2. surfaces the hottest group, and
3. lists that group's 5 best performers, each chartable with full indicators.

Data comes from the Alpaca market data API using the paper credentials already
in the repo-root `.env`.

**Feed:** the server prefers the **SIP consolidated tape** (all US venues) with a
16-minute-delayed request window, and falls back to **IEX** if the subscription
refuses SIP. The feed in use is shown in the page header and in `/api/health`.
IEX is real-time but is a single venue carrying only ~2.5–4% of consolidated
volume, so IEX volume understates true liquidity by roughly 25–40× (measured:
AXTI 488k shares on IEX vs 19.2M on SIP for the same session). Closes agree to
within 0.2%, so rankings are the same either way — but liquidity is not worth
being an order of magnitude wrong about. Since the board runs on daily bars, the
16-minute cutoff costs nothing.

## Run it

```bash
python3 trading_desk/server.py --port 8799
```

Then open <http://localhost:8799>.

## What's on the page

| Section | What it shows |
|---|---|
| Lookback tabs | 1D–5D. One filter row scoping the whole board. |
| Hottest group | Mean, median, breadth, vs SPY, and the ETF proxy return. |
| Group ranking | All 14 groups as a diverging bar chart; click a row to load its leaders. |
| Top 5 | The leaders inside the selected group, with a 30-day sparkline. |
| Detail chart | Candlesticks + overlays, with volume, RSI and MACD panes on a shared crosshair. |
| Company detail | Market cap, trailing P/E, 52-week range, volatility, SEC filings, news, research links. |
| Ranking table | The same board in text form — every value readable without color. |

### Company detail

Below the chart, for the selected symbol:

- **Key stats** — market cap (SEC shares outstanding × last price), trailing P/E,
  TTM diluted EPS, 52-week range with the current position marked, ATR-based
  daily volatility, and 20-day average / dollar volume.
- **Latest SEC filings** — revenue, gross profit, operating income, net income,
  EPS, R&D, assets, liabilities, equity, cash, and operating cash flow. Every
  row shows the form (10-K/10-Q), the period it covers, and the filing date.
- **Recent news** — headlines from the Alpaca News API, linked to the source.
- **Research & analyst coverage** — links out to Yahoo Finance analysis, Finviz,
  StockAnalysis, TradingView, and the company's SEC EDGAR filing index.

#### How P/E is computed

Companies do not file a Q4 10-Q, so the four most recent quarters are never all
present as quarterly XBRL rows. TTM diluted EPS is reconstructed as:

```
TTM = last full fiscal year + current year-to-date - prior-year year-to-date
```

The exact arithmetic is shown under the P/E tile, so the figure is auditable. If
that reconstruction is not possible, P/E reads `n/a` with the reason rather than
falling back to a single quarter's EPS (which would understate it ~4×). Negative
trailing earnings show `n/a` rather than a meaningless negative multiple.

Where a company has migrated XBRL revenue tags, the tag with the most recent
period wins — picking by a fixed tag order would surface a long-abandoned tag as
if it were current.

### Indicators

Overlays: SMA 20 / 50 / 200, VWAP 20 (rolling), Bollinger Bands (20, 2σ).
Panes: Volume + 20-day volume SMA, RSI 14, MACD (12, 26, 9) with histogram.
Also computed and available in the table view and tooltip: ATR 14, Stochastic
(14, 3), EMA 12 / 26, OBV.

Range selector: 3M / 6M / 1Y / 2Y.

## API

| Route | Returns |
|---|---|
| `GET /api/board` | Rankings for all five lookbacks. `?force=1` bypasses the cache. |
| `GET /api/stock?symbol=X` | ~2 years of daily bars plus every indicator series. |
| `GET /api/detail?symbol=X` | Fundamentals, price stats, news, and research links. |
| `GET /api/health` | Credential and cache status. |

Both routes cache for 5 minutes. Only the board is persisted to `cache.json`
(~60 KB); per-symbol payloads stay in memory behind a 60-entry LRU. Persisting
them meant re-serializing tens of megabytes under the global lock on every
cache-miss, and they are cheap to refetch after a restart.

## Data integrity

Per `AGENTS.md` RULE #1, nothing here fabricates market data:

- A symbol with missing or too-short history is **dropped and reported** under
  `omitted` (shown as a banner on the page), never back-filled or carried forward.
- Indicator warmup regions are `null`, not zero-filled — an undefined SMA200 on
  day 3 stays undefined.
- A flat Stochastic window (zero range) returns `null` rather than a made-up 50.
- If a live fetch fails, the server serves the **last known-good** cache and marks
  the payload `stale`, with a banner saying so. A failed fetch never overwrites
  good cached data, and the board's cache write is atomic (temp file + rename).

## Known limitations

- **Daily bars only, and SIP is 16 minutes behind.** The board is built for
  multi-day horizons. For intraday work Alpaca also serves 1Min/5Min/15Min/1Hour
  bars and tick-level trades and quotes (nanosecond timestamps) — but sub-minute
  *bars* are not offered, and real-time (undelayed) access is IEX-only on this
  subscription.
- **Group membership is hand-curated** in `universe.py`, not pulled from an index
  provider. It covers liquid names per sector, not the full index.
- **Themes have no ETF proxy**, so their `etf_return_pct` is `null` by design.
  All groups rank on constituent returns, so the comparison stays apples-to-apples.
- **Mean is outlier-sensitive.** A single name up 87% lifts its whole group. The
  median and breadth columns are shown alongside precisely so you can see when a
  group's rank rests on one name.

## Files

| File | Role |
|---|---|
| `server.py` | HTTP server, Alpaca client, ranking, caching |
| `universe.py` | Sector/theme constituents |
| `indicators.py` | Indicator math (pure stdlib) |
| `fundamentals.py` | SEC filings, TTM EPS reconstruction, news, research links |
| `index.html` / `app.js` / `style.css` | Dashboard UI |

## Dependencies

Price data, indicators, news and the UI are **stdlib only**. Fundamentals reuse
Lumibot's `SECFundamentals` (already in this repo) for SEC XBRL access, imported
lazily — if Lumibot is unavailable the panel reports fundamentals as unavailable
and everything else still works.

## Design notes

Chart colors use the validated categorical palette; the series slots were checked
with the `dataviz` skill's `validate_palette.js` against both surfaces
(dark `#12161c` passes all checks; light `#fcfcfb` passes with a contrast warning
on two slots, which is why direct endpoint labels and a table view both ship).
