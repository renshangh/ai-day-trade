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

Data comes from the Alpaca market data API on the **IEX feed** using the paper
credentials already in the repo-root `.env`. No pip installs — stdlib only.

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
| Ranking table | The same board in text form — every value readable without color. |

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

- **IEX feed, not SIP.** This Alpaca key is not SIP-entitled, so prices reflect
  IEX volume only and can differ slightly from a consolidated-tape terminal.
  Rankings are directionally reliable; exact percentages may not match Bloomberg.
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
| `index.html` / `app.js` / `style.css` | Dashboard UI |

## Design notes

Chart colors use the validated categorical palette; the series slots were checked
with the `dataviz` skill's `validate_palette.js` against both surfaces
(dark `#12161c` passes all checks; light `#fcfcfb` passes with a contrast warning
on two slots, which is why direct endpoint labels and a table view both ship).
