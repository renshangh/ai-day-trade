# BTC Structure Research Release 0.2

Freeze and publish the same-source 0.1/E1/E2 full-sequence comparison.

Last Updated: 2026-11-09  
Status: Approved research release  
Audience: Trading Desk users and research maintainers

## Overview

This is a BTC research release, independent of the parent LumiBot package
version. Tag: **btc-research-v0.2**. It preserves the original 0.1 baseline
and packages E1/E2 as separate alternatives; no single alternative is selected
merely because its in-sample result is higher. No order routing is enabled.

| Model | All trades / net USD | No flagged gap / net USD | Flagged gap / net USD |
| --- | ---: | ---: | ---: |
| 0.1 | 38 / +3,516.46 | 36 / +2,751.29 | 2 / +765.17 |
| E1 | 38 / +4,159.67 | 37 / +2,998.96 | 1 / +1,160.71 |
| E2 | 38 / +4,195.15 | 37 / +3,034.44 | 1 / +1,160.71 |

Each model has 19 wins / 19 losses. E1 reduces losses by $643.21, E2 by
$678.69. Neither creates new entries after an earlier exit or reduces an
original winner. Entry, stop, partial target, protection and cost parameters
remain unchanged. E1 changes #11/#12/#32; E2 changes #12/#32.

The window is October 10 to November 9, 2026 UTC, exclusive end, with seven
warmup days. There are 42,642 observed test minutes and 558 absent minutes.
Missing observations remain absent. The no-flagged-gap subset requires no
observed holding gap and a complete adjacent 14-bar entry context; the flagged
subset is its complement. #12 changes groups after exiting before a later gap.
Group totals therefore do not measure matched-trade improvement.

## Published artifacts

- BTC_STRUCTURE_RELEASE_0.2.zip: source snapshot, actual observed minutes,
  three result/ledger sets, integrity manifest, offline replay/installer,
  five-sheet workbook and the unchanged original 0.1 ZIP.
- E1_E2_SEQUENTIAL_30D.xlsx: current-only comparison, all 114 trade rows,
  132 exit legs and 8,640 chronological 15m rows across three models.

The [GitHub release](https://github.com/renshangh/ai-day-trade/releases/tag/btc-research-v0.2)
owns these assets. Historical research files stay preserved; earlier
single-case/monthly studies are removed from the active desk and new workbook.
The original 0.1 archive hash is
8c4d569c87a102c78a633938ad5c2bb2010eed6a5ceb336c345a86cf96026f8b.

## Verification and installation

Extract the ZIP and run Python 3.10+ with only the standard library:

    python3 REPRODUCE.py

This verifies every packaged file and source stream, then replays the full
three sequences and compares every signal, entry, initial stop, target,
exit leg, gap flag and metric. No credentials, network or broker are needed.

To install into a fresh checkout after successful verification:

    python3 REPRODUCE.py --install-store "/path/to/ai-day-trade/trading_records/btc_structure"

The installer refuses conflicting research files, preserves an existing
minute database and creates an observed-only one when absent. It installs
the three current review records while retaining 0.1 as the execution baseline.
Open /btc-lab using the normal Trading Desk server.

The release includes the read-only BTC archive client without importing the
unrelated Alpaca paper-order runner. Existing paper credential names and the
pinned market-data host remain unchanged.

## Limits

Every trade is normalized to initial 1 BTC, using ETF zero commission plus
2bps per side for spread/slippage. These are repeatedly reviewed in-sample
observed-path model results, not actual ETF executions, independent
out-of-sample validation or a claim of future profitability.
