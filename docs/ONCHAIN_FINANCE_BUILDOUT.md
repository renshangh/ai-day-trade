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
