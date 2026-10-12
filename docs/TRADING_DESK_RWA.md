# Trading Desk RWA & Tokenization

A sourced market-value and liquidity screen for the RWA research sector.

**Last Updated:** 2026-10-12
**Status:** Active
**Audience:** Contributors and desk users

## Overview

The sector board (`/board?view=rwa`) displays up to ten Coinbase-qualified coins.
Select **RWA & Tokenization** from the board's view tabs. The home page has no
RWA ranking section and does not load its market-screen assets. This supports
the existing North Star of sourced, explicit thesis
decisions by showing dated market observations instead of unsupported liquidity
claims. It is a research screen and does not submit orders.

## Selection and units

`rwa_market.py` requests the first 100 CoinGecko RWA-category markets by market
cap in USD. Its reviewed pool covers LINK, XLM, XAUT, QNT, ONDO, PAXG, ALGO, INJ,
XDC, SYRUP, RSR and PLUME. Broad infrastructure tokens have indirect RWA exposure;
category membership does not establish token-holder revenue. Restricted funds,
stablecoins and tokenized stock wrappers are outside the pool.

An active Coinbase Exchange USD or USDC spot market in normal trading is required
before ranking: status online, with trading_disabled, cancel_only, post_only,
limit_only and auction_mode explicitly false. Missing status fields do not
qualify. USD is preferred when both USD and USDC pairs qualify. Circulating market
cap >= $100M and reported 24-hour USD trading volume >= $10M are also required. Invalid or missing metrics and timestamps are excluded.
Rank the qualifying pool independently by market cap and volume descending, then
select the ten smallest rank sums, breaking ties by cap rank. UI sorting changes
the selected shortlist's order only. This is a reviewed category pool, not a claim
to exhaust every tokenization project. Review membership as classifications evolve.

Market cap is circulating token value, not FDV or assets under management.
Reported volume is an aggregate dollar measure, not Kraken token volume or proof
of executable depth. Gold-backed tokens differ from governance/infrastructure.

## Refresh and data integrity

`GET /api/rwa-market` caches successful responses in memory for five minutes.
`?force=1` explicitly requests a refresh. Failed responses cache for 30 seconds
to avoid repeated upstream requests when several board views open during an outage.
Each coin retains the provider's
`last_updated`. Source: https://www.coingecko.com/en/categories/real-world-assets-rwa.
If Coinbase verification fails, the list is withheld, including previously
displayed tokens. If only market-data refresh fails, dated cached observations
may be displayed after filtering and reranking against currently verified Coinbase
markets. Original market timestamps are preserved. The checked-in snapshot records
real observations and is never used as historical bars or an executable quote.
The table shows the Coinbase pair and verification timestamp. This is public
Exchange market eligibility; a user's account or region can impose restrictions.

## Verification

Offline regression tests cover dual-threshold screening, missing observations,
rank ties, duplicate records, the ten-member limit, and stale refresh behavior.

## Coin charts

Select any coin ticker to load its chart below the RWA table, using the board's
existing crypto selection path. Normal clicks stay on the board and scroll to
the chart; modified clicks open a board link with the coin preselected. RWA
selections always use crypto data, including QNT, whose ticker can also identify
a stock elsewhere. The market-source footer remains an external source link.

All twelve pool tokens have verified Kraken USD pairs. Charts use actual completed
UTC daily OHLCV candles with token volume. Today's forming candle is excluded.
Missing candles remain missing; absent data clears the previous chart and displays
unavailable. Kraken candle volume differs from the table's aggregated USD volume.

The crypto research panel below the chart provides separate CoinGecko and
CoinMarketCap links for the selected token. Each opens its asset-specific page
in a new tab. Switching tokens updates both links; they remain available when
chart candles cannot be loaded. USD feed aliases resolve to the underlying token.
