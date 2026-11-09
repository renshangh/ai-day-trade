# BTC Structure Research Release 0.1

Freeze the original 38-trade research model as an independently reproducible local release.

Last Updated: 2026-11-09  
Status: Frozen local release; not a GitHub publication  
Audience: Trading Desk users and research maintainers

## Overview

Version 0.1 applies to the BTC research model, not the parent LumiBot package.
Reference run: `20261109T041525Z-30-ab`; 38 closed trades, 19 wins / 19 losses,
model net +$3,516.46 per initial 1 BTC, +6.905525R. No orders or real ETF returns.
The historical B1 permits its D candle as stabilization; the newer independent
post-D confirmation belongs to a separate research run, not this release.

## Contents and verification

`trading_records/btc_structure/releases/0.1/` contains `MANIFEST.json`, `README.md`,
`REPRODUCE.py`, frozen source, actual observed minute stream and original results
including `results/RESEARCH.xlsx`. `BTC_STRUCTURE_RELEASE_0.1.zip` packages them.
Unzip and run `python3 REPRODUCE.py` without credentials, downloads or brokers.
The exact packaged sources replay all entries, initial stops, targets, exit legs
and metrics identically; source/file SHA256 hashes are validated.

The same 30-day window ends November 9 00:00 UTC exclusive; 558 test minutes
are absent. Zero commission plus 2bps per side is an ETF cost proxy. Results
remain in-sample observed-path research, not verified live profitability.

## Trading Desk

Choose `Release 0.1 · 冻结` in `/btc-lab`; download the release ZIP or preserved
original workbook. The independent-B1 experiment is retained separately as run
`20261109T122648Z-30-ab`, net +$2,805.01, without replacing 0.1.
See [monthly comparison](../investigations/2026-11-09_BTC_B1_MONTHLY_CONFIRMATION.md).

On November 9 the owner retained this release as the desk default and the
policy for new replay jobs. The latest experiment remains available without
replacing the selected baseline. No frozen release files were changed.
