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

The report editor saves dated snapshots. The AI Economy Score is an experimental equal-weight average of six analyst-entered 0–100 inputs and appears only when all six have source URLs. The other four scores are manual assessments that require a method or source note. Top 5 Changes are sourced developments entered for a report after the first baseline report. No current market values are seeded or inferred.

The Thesis Tracker contains proposed thesis statements and watch criteria. Reviewers can append dated confidence, trend, supporting evidence, contradicting evidence, and source links. The Opportunity Pipeline supports stage changes, and the Decision Log supports later outcome updates. All entries remain in this browser's local storage; they do not sync to the server. The page offers a JSON backup export. Watchlists and research themes are structural examples, not current recommendations.
