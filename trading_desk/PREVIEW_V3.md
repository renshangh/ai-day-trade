# AI Trading Desk v3 Preview
One-page experimental report structure for review.
Last Updated: 2026-09-27
Status: Preview
Audience: Trading Desk reviewers

## Overview

Run `python3 trading_desk/server.py --port 8801` from this worktree and open `http://127.0.0.1:8801/preview-v3` when the Trading Desk's Alpaca credentials are configured.
For a layout-only review without credentials, run `python3 -m http.server 8801 --directory trading_desk` and open `http://127.0.0.1:8801/preview_v3.html`.
The existing dashboard remains at `/`. This preview is confined to branch `preview/ai-trading-desk-v3`.

The preview contains a CIO Brief, score framework, expanded AI Coins panels, the ten proposed Trading Desk report sections, Research Lab, Thesis Tracker, Opportunity Pipeline, and Decision Log. New components are visibly labeled `[PREVIEW]`.

Scores and market changes stay blank until sourced inputs and a scoring methodology are implemented. Watchlists and research themes are structural examples, not current recommendations. Opportunity and decision entries are saved only to this browser's local storage; they do not sync to the server. The Thesis Tracker currently contains proposed thesis statements and watch criteria, with evidence and review history empty.
