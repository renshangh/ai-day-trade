# FRED Macro Data

Lumibot includes native Federal Reserve Economic Data (FRED) macro tools for strategies and AI agents.

Use macro data for interest rates, inflation, employment, growth, liquidity, credit spreads, and market-risk context.

## Strategy API

```python
self.macro.list_series()
self.macro.get_series("DGS10")
self.macro.get_latest("UNRATE")
self.macro.get_snapshot(["FEDFUNDS", "DGS10", "CPIAUCSL", "UNRATE"])
```

## Agent Tools

Agents receive these built-ins automatically:

- `list_fred_series`
- `get_fred_series`
- `get_fred_latest`
- `get_fred_snapshot`

You do not need to manually attach these tools. They are included with the rest of the built-in agent tool surface.

## API Key Behavior

`FRED_API_KEY` is required for the official FRED/ALFRED API path and for strict point-in-time macro backtests.

Lumibot uses the official FRED/ALFRED API and passes `realtime_start` and `realtime_end` based on the strategy datetime. This is the strict point-in-time path for macro backtests.

Lumibot does not use public CSV fallbacks for macro data. Built-in FRED agent tools are hidden during backtests unless `FRED_API_KEY` is configured. This prevents agents from accidentally using macro data without a point-in-time data contract in historical simulations.

## Backtest Date Safety

In a backtest, `as_of` defaults to `self.get_datetime()`.

Lumibot always filters observations to `observation_date <= as_of` and requests the vintage data known as of that date through the official API.

## Cache

FRED data is cached under:

```text
~/.lumibot/cache/fred
```

Override with:

```bash
export LUMIBOT_FRED_CACHE_DIR=/path/to/cache
```

Backtests should fetch each series once and reuse the local cache instead of hitting FRED on every trading iteration.

### Cache lifetime is vintage-dependent

A request's cache key includes its ALFRED vintage (`realtime_start`/`realtime_end`,
both the as-of date), which splits cached responses into two classes:

| Requested vintage | Expires | Why |
|---|---|---|
| Settled history (as-of older than yesterday) | never | The vintage is immutable. Keeps backtests at one fetch per series. |
| Current (as-of today or yesterday) | 1 hour | FRED publishes and restates intraday under an unchanged cache key. |

Constants are at the top of `lumibot/macro/fred.py`
(`CURRENT_VINTAGE_CACHE_MAX_AGE_SECONDS`, `VINTAGE_SETTLES_AFTER_DAYS`). The
settled/current boundary is decided against **wall-clock** today, not strategy
time — a backtest reading a 2024 vintage is reading settled history regardless of
its own clock. `VINTAGE_SETTLES_AFTER_DAYS` is non-zero so the boundary is not
decided by UTC-vs-local date skew or same-day late revisions.

If an expired copy cannot be refreshed (FRED down or rate limiting), the expired
copy is served with a warning rather than raising. Unparseable cache files left by
an interrupted write are discarded and re-fetched.

Before this was fixed, every FRED response cached forever. That was correct for
settled vintages but wrong for the current one: a live bot could act on a value
cached earlier in the same session. See
`docs/investigations/2026-08-28_SEC_SUBMISSIONS_CACHE_NEVER_EXPIRES.md` for the
same defect class in the SEC client.
