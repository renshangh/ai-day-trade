# Trading Desk RWA & Tokenization

A sourced market-value and liquidity screen for the RWA research sector.

**Last Updated:** 2026-10-12
**Status:** Active
**Audience:** Contributors and desk users

## Overview

The main desk (`/#rwa`) and sector board (`/board?view=rwa`) share a ten-coin
shortlist. This supports the existing North Star of sourced, explicit thesis
decisions by showing dated market observations instead of unsupported liquidity
claims. It is a research screen and does not submit orders.

## Selection and units

`rwa_market.py` requests the first 100 CoinGecko RWA-category markets by market
cap in USD. Its reviewed pool covers LINK, XLM, XAUT, QNT, ONDO, PAXG, ALGO, INJ,
XDC, SYRUP, RSR and PLUME. Broad infrastructure tokens have indirect RWA exposure;
category membership does not establish token-holder revenue. Restricted funds,
stablecoins and tokenized stock wrappers are outside the pool.

Both circulating market cap >= $100M and reported 24-hour USD trading volume >=
$10M are required. Invalid or missing metrics and timestamps are excluded.
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
to avoid repeated upstream requests when both desk surfaces open during an outage.
Each coin retains the provider's
`last_updated`. Source: https://www.coingecko.com/en/categories/real-world-assets-rwa.
A provider failure returns the previous observation set (or the checked-in actual
`rwa_snapshot.json` research capture) marked stale, with original timestamps and
a visible warning. Failed refreshes never rewrite timestamps or fabricate values.
The snapshot is never consumed as historical bars, an executable quote, or a
backtest input. No strategy universe or stock-sector ranking is changed.

## Verification

Offline regression tests cover dual-threshold screening, missing observations,
rank ties, duplicate records, the ten-member limit, and stale refresh behavior.
