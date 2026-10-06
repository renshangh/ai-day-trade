# Onchain Finance Buildout

Daily evidence review for the Trading Desk's onchain finance thesis.

**Last Updated:** 2026-10-06
**Status:** Active
**Audience:** Trading Desk contributors and users

## Overview

The existing Crypto Finance Infra section is now Onchain Finance Buildout.
Its five layers are Digital Money, Onchain Markets, TradFi Bridge,
Infrastructure Rails, and Agentic Finance. COIN and CRCL anchor the review.
The original eight-layer map and earlier research remain expandable.

## Review and data contract

`crypto_infra.js` shares the taxonomy, renderer and entry validation between
the main desk and sector board. Main-desk entries append to the existing
revisioned `observations` array with theme `Onchain Finance Buildout`.
No storage migration, new endpoint, secret or environment variable is needed.
The board reads `/api/v3/state`; writing and JSON backup remain on the main desk.
Revision conflicts retain the existing browser recovery behavior.

Each entry records its date, layer, development, source, evidence type,
adoption details and COIN/CRCL implications including winners and losers.
Metrics are optional manual observations, not automatically verified facts.
The review defaults to the New York calendar date and allows earlier dates.

Deltas require one matching sourced observation on yesterday's calendar date,
with identical layer, metric and unit/scope. Keep source methodology consistent.
Gaps and duplicate baselines are unavailable; zero baselines have no percent
change. An unreviewed layer does not assert no change. Never seed news or metrics
with examples. Test fixtures remain offline and must not enter research storage.

## Proposed metrics and OKRs

North Star: share of daily thesis decisions supported by dated adoption evidence
and an explicit COIN/CRCL implication. Weekly targets: cover all five layers on
review days, source every development, distinguish announcements from live
usage, and capture supporting as well as contradicting evidence. These are
proposed process targets; no measured performance is claimed.

## Verification

`node --test trading_desk/tests/test_crypto_infra.cjs trading_desk/tests/test_v3_logic.cjs`
covers taxonomy, empty states, validation, escaping and calendar comparisons.
Existing v3 store/API tests cover private revisioned persistence.
Public instructions live in `docsrc/TRADING_DESK.rst`; UI details in
`trading_desk/V3.md`. Existing `#coins` and `ai-crypto` links remain compatible.


## Symbol charts and Canton

Every listed stock/token in the five-layer watchlists and original map has a
chart link. On the sector board, selecting it loads the existing chart below;
on the main desk it opens the board with that symbol selected. The separate
arrow retains the external market link. Unlisted companies stay unlinked.

Canton uses the desk label `CCCAUSD`, mapped to Kraken `CCUSD` (CC/USD), not the
unrelated Chemours stock `CC`. Verified Kraken USD pairs use completed daily
UTC OHLC and base-token volumes. The last forming interval is excluded; gaps
stay gaps, and malformed/duplicate candles are rejected. Missing feeds clear
previous candles and show unavailable. Tokens without a configured daily feed
still have their external market link. Public-provider requests receive no
Alpaca credentials. No orders, secrets or environment variables are added.

Pair and candle contract: `onchain_crypto.py`. Regression coverage:
`tests/test_onchain_crypto.py` and `tests/test_crypto_infra.cjs` under
`trading_desk/`. The North Star remains sourced, explicit thesis decisions;
charts supply dated market context without substituting for adoption evidence.
