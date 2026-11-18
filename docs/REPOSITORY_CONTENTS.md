# AI Trading Desk Repository Contents

Find the local application, saved chart captures and separate research experiments.

Last Updated: 2026-11-18  
Status: Public source and market-research index  
Audience: Repository users and maintainers

## Overview

This repository contains the Trading Desk application as well as its underlying
LumiBot framework. GitHub displays source files and saved captures; it does not
run the local dashboard or connect to a brokerage account. A URL such as
`/btc-live` is a server route, not a folder named `btc-live`.

## Application map

| Local route | Source | Operating guide |
| --- | --- | --- |
| `/btc-live` | [BTC Live Paper](../trading_desk/btc_live.html) | [Startup and recovery](BTC_LIVE_PAPER.md) |
| `/btc-lab` | [Frozen research viewer](../trading_desk/btc_lab.html) | [Research desk](BTC_RESEARCH_DESK.md) |
| `/btc-p1` | [P1 comparison](../trading_desk/btc_p1.html) | [P1 research](BTC_P1_RESEARCH.md) |
| `/btc-parent-hl` | [Parent HL](../trading_desk/btc_parent_hl.html) | [Parent HL research](BTC_PARENT_HL_RESEARCH.md) |
| `/btc-parent-five` | [15m/5m comparison](../trading_desk/btc_parent_five.html) | [Five-minute trigger research](investigations/2026-11-15_BTC_PARENT_FIVE_COMPARISON.md) |
| `/btc-parent-memory` | [Parent memory](../trading_desk/btc_parent_memory.html) | [Memory comparison](investigations/2026-11-15_BTC_PARENT_MEMORY_COMPARISON.md) |
| `/btc-parent-filter` | [Parent filter](../trading_desk/btc_parent_filter.html) | [Filter research](BTC_PARENT_FILTER_RESEARCH.md) |
| `/sol-live` | [Separate SOL page](../trading_desk/sol_live.html) | [SOL model review](SOL_MODEL_01.md) |
| `/crypto-research` | [Saved crypto research](../trading_desk/crypto_research.html) | [BTC research](BTC_RESEARCH_DESK.md) |
| `/chart-review` | [Dated chart gallery](../trading_desk/chart_review.html) | [Trading Desk guide](../trading_desk/README.md) |

Start the viewing server from the repository root:

```bash
python3 trading_desk/server.py --port 8799
```

The extended research pages use NumPy; install the repository dependencies in
your Python environment first. Configure your own local `.env` for market data.
Opening the browser is separate from starting a worker. To inspect an existing
BTC worker without starting another process:

```bash
python3 scripts/run_btc_live.py --status
```

## Saved captures and reviews

- [BTC November 16 scenario charts and subsequent reviews](../reports/btc_elliott_wave_2026_11_16/README.md).
- [BTC Live Paper and IBIT-hours captures](../reports/btc_live_captures/README.md).
- [Native chart gallery manifest](../trading_desk/chart_review.json).
- [E3 ten-case comparison](../reports/btc_e3_draft1_2026_11_15/REPORT.md).
- [Local versus parent support](../reports/btc_e3_support_recovery_2026_11_15/AUDIT.md).
- [Failed-breakout controls](../reports/btc_e3_failure_controls_2026_11_15/AUDIT.md).

Captures are dated historical observations. Scenario dashed paths are hypotheses,
not observed future candles, confirmed forecasts or trading instructions.

## Frozen data and local records

The unchanged [BTC research 0.2 release](https://github.com/renshangh/ai-day-trade/releases/tag/btc-research-v0.2)
contains the frozen source/data bundle, integrity manifest and comparison
workbook. Follow [offline verification and installation](releases/BTC_STRUCTURE_0_2.md)
to restore its research store into a fresh checkout. Missing local studies stay
unavailable until installed or explicitly generated; the viewer never invents
replacement results. Live observations, private portfolios and machine-specific
worker state are not repository source files.

`.env`, OAuth tokens, `.secrets/`, brokerage records, the private Daily Review
archive and current account snapshots stay local. The public dashboard HTML
omits embedded account-specific holdings; the working local dashboard can retain
them. `scripts/public_dashboard_snapshot.py` creates a separate public shell
without overwriting that local view. Review the staged snapshot before pushing;
do not stage the entire working directory indiscriminately.

## Verification

The **Trading Desk Public Snapshot** GitHub workflow checks the published shell
and portable unit/render tests without credentials or private stores. It also
compares all frozen BTC rule sources with the byte-for-byte original 0.2
manifest in `docs/releases/BTC_STRUCTURE_0_2_MANIFEST.json`.

The broader local Python and browser suites include archived-study integration
tests. Install their original saved study data before running them; a fresh
checkout intentionally lacks those machine-local research stores. Tests for
historical study preservation keep engine/worker hashes strict, while permitting
the subsequently authorized BTC display-panel changes. No strategy hash or
market observation was updated to make the tests pass.
