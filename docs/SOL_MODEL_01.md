# SOL model 0.1 candidate

SOL-only tape review, declared entry changes and independent thirty-day comparisons.

Last Updated: 2026-11-10  
Status: Research candidate complete; not installed or running  
Audience: Trading Desk owner and maintainers

## Overview

Open `/sol-live` for SOL model 0.1. It uses SOL/USD observations only, with no
other asset's price, ATR or weight. Original SOL E1 is its benchmark. The first
candidate reduces observed drawdown and trade count, but earns less than the
benchmark, so it is not an overall improvement and is not promoted.

`/crypto-live` is a static stopped page with no scripts or polling. `/btc-live`
continues in its original worker/session. Saved multi-asset historical research
is retained at `/crypto-research`; it does not poll live status or control a
worker. SOL's old E1 worker is paused, unloaded from launchd, and disabled for
automatic login restart. Its existing observations and model history are kept.

The North Star remains sourced, causal and reproducible decisions. Review real
bar coverage, retained winners, avoided losers, changed full sequences and
drawdown alongside returns. A higher historical return alone is not evidence
of a deployable improvement.

## SOL tape and declared model

The tape is the unchanged original October 10, 2026 00:00 UTC–November 9
00:00 UTC month, with seven days of actual warmup. All thirty-five original
SOL E1 trades are reviewed in `TAPE.json` and `TAPE.csv`, including D/L2,
entry/stop/target, every exit leg, net P/L, prior SOL shock context, confirmation
and coverage. IDs on this page are standalone thirty-day IDs, not ninety-day
IDs. Source test coverage is 41,446 of 43,200 minutes (95.94%); 1,754 minutes
remain absent. No market observation or account mark is filled or synthesized.

Two entry changes define the combined candidate, fixed before its replay:

1. A shock must be a complete bearish fifteen-minute new-scope-low candle
   whose previous-close to close decline is at least **2.0 SOL ATR14**. ATR
   comes from fourteen true ranges of fifteen consecutive fully observed
   prior fifteen-minute candles, known before the shock begins. Missing
   context withholds a new shock. This replaces the old wick/downward-
   excursion measure, not the stop's risk convention.
2. B1 requires an independent complete fifteen-minute candle starting at or
   after D confirmation, holding that D, before the later previous-high
   breakout. The candle that makes D cannot confirm its own hold.

Original A/B2 definitions, A/B1/B2 route priority, consumed entry history,
larger-D stop and buffer, target construction, positive target-space test,
advisory 2R, E1 exits and the first 25%/remaining 75% sales are unchanged.
All numerical exit and risk settings stay unchanged. Actual stop prices can
differ when a new entry occurs later with different then-known ATR. No P1,
C, fitted ML gate, cross-asset dependency or BTC volatility weight is added.

The implementation reuses generic frozen candle/entry/exit mechanics and a
complete-bar ATR context helper. Reusing code does not read another asset's
observations. Only the original SOL archive is passed to the candidate.

## Four comparisons without selection after results

`PROTOCOL_BEFORE_RESULTS.json` and source hashes precede every replay. Arms:
original SOL E1, net shock only, independent hold only, combined SOL 0.1. The
combined candidate remains model 0.1 regardless of which result is largest.
There is no parameter grid, threshold search or post-result adjustment.

| Full thirty-day book | Illustrative cash return | Max observed drawdown | Trades | Wins / losses | Net per fixed $10k entry |
|---|---:|---:|---:|---:|---:|
| Original SOL E1 | +16.78% | 3.52% | 35 | 18 / 17 | +$1,581.86 |
| SOL net shock only | +13.44% | 2.63% | 20 | 11 / 9 | +$1,284.22 |
| Independent hold only | +13.20% | 3.52% | 34 | 17 / 17 | +$1,267.66 |
| Combined SOL 0.1 candidate | +12.20% | 2.55% | 19 | 10 / 9 | +$1,174.32 |

Each illustrative cash account starts with $10,000, uses available cash with
fractional units, keeps partial-sale proceeds idle, and reinvests after the
old position closes. Drawdown uses actual observed minute-close hypothetical
liquidation equity, including open marks. Missing intervals and intraminute
lows may hide deeper declines. Fixed-$10,000-entry P/L sums independent trades
and differs from the reinvested cash return. Both retain the old 2bps/side ETF
friction proxy, excluding actual spot-crypto fees, funding, interest, taxes,
market impact and execution constraints. References are not broker fills.

The same arms also restart flat for the first fourteen, next seven and final
nine days, each with seven days of actual warmup. These are previously studied
dates and retrospective diagnostics, not untouched validation. Their separately
reset sequences need not sum to the continuous month.

| Phase | Original SOL E1 return | SOL 0.1 return | Original / candidate observed drawdown |
|---|---:|---:|---:|
| First fourteen days | +8.82% | +5.25% | 2.19% / 2.09% |
| Next seven days | +3.24% | +3.33% | 3.52% / 2.39% |
| Final nine days | +4.03% | +3.25% | 2.29% / 1.74% |

Open remainders at phase boundaries are marked, not forcibly closed. Return
includes their hypothetical liquidation mark; realized P/L and open units
remain separate in the exports and interface.

## What the tape explains

The full candidate retains fourteen exact original entries and exits, removes
twenty-one original entry timestamps, and adds five later opportunities. Of
the removed original entries, eleven were winners totaling $1,328.76 and ten
were losers totaling -$459.34 per fixed-$10,000 entry. Some removed entries
have later replacements, so these counts are not simply missed whole trades.

- Original #19 (ninety-day #28) loses $161.30. Its net shock is only 1.762
  SOL ATR despite a strong-looking downward wick. The candidate excludes that
  original entry. It later records a new 21:15 UTC entry earning $9.50.
- Original #6 earns $280.78, but its net shock is only 0.998 SOL ATR and its
  original entry follows D's own candle. That original profitable opportunity
  is lost. A larger wick is not equivalent to a steep net close decline.
- Original #3 earns $274.28 at 01:03 UTC October 13. Independent confirmation
  delays the candidate to 01:16; the replacement earns $238.24. It is a
  delayed, smaller winner, not a wholly absent winner.
- Original #26 earns $269.39 at 12:31 UTC November 4. The candidate instead
  enters at 13:26 and earns $288.79. Delay can help too; it is not always harm.
- Large winners #9 and #20 retain their exact entries/exits and earn $420.62
  and $323.39. #20's normal post-entry weakness is not cut by an added fast
  failure exit; the existing exits are unchanged.
- Original #5 has a genuinely steep 3.809-ATR net shock and still loses.
  Stronger shock qualification cannot by itself guarantee follow-through.

All times above are UTC minute references, with completed-minute availability
one minute later. The page displays New York time with explicit daylight/
standard zone labels. Later candles and P/L are review evidence, not entry
inputs. Prefix-only actual-data tests check the shock ATR and confirmation
timestamps, as well as both avoided failures and retained/delayed winners.

## Independent page and research bundle

`/sol-live` reads only `/api/sol-live` for original SOL service health and
`/api/sol01` for saved candidate research. It never calls a BTC status endpoint,
submits a review or starts a worker. Period/model/list controls select saved
results. Inspect shows initial D/stop/target, original stop raises, exit legs,
exit evidence and actual fifteen-minute chronology. All original tape records,
changed entries, equity marks and protection exports are available.

The old SOL E1 session is not relabeled as SOL 0.1. Candidate history is an
offline backtest, not live positions. A future explicit activation requires
separate candidate installation and a clear new session; the old E1 install
command must not be presented as starting SOL 0.1.

Research source: `trading_desk/sol_model01.py`. Reproduce with
`python3 scripts/study_sol01.py` into a new study; the script refuses to
overwrite an existing 0.1 candidate bundle. The immutable recorded candidate
is under `trading_records/sol_structure/releases/0.1/`, with `MODEL.json`,
source snapshots and an ATR dependency snapshot. Study
`20261110T161551Z-sol01` contains sixteen full sequential books, a reproduced
original control, every trade/exit/protection/ledger/equity export, original
tape review and changed-entry comparison. Reproduction of a recorded bundle
requires a fresh version/destination rather than overwriting it.

Frozen 0.2's thirteen strategy hashes, the BTC source/UI and BTC worker PID
56139/session `20261109T175620Z` remain unchanged. No original study selector,
data archive or output is replaced. SOL is not started and no orders occur.
