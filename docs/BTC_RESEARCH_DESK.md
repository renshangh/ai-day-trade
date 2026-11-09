# BTC Research Desk

Alpaca minute archive, causal signal replay and a chronological learning interface.

Last Updated: 2026-11-09  
Status: Mechanical research draft; no paper or live orders  
Audience: Trading Desk owner and maintainers

## Overview

The separate [Live Paper operating page](BTC_LIVE_PAPER.md) is available at
/btc-live. It runs newly received BTC/USD observations in three independent
comparison records, under the owner's comparison-only instruction. This is a
minute-based signal benchmark, not an Alpaca broker-paper execution path.
Detection time, market reference time, quote freshness and recovery are explicit.
The macOS login service now starts the comparison directly under launchd with
RunAtLoad and KeepAlive. Python removable-volume access was verified enabled;
the internal-disk working/log paths avoid the earlier external-directory
startup failure. No browser/dashboard dependency or broader privacy grant is
introduced. See the operating guide for installation and recovery checks.

The approved comparison is published as BTC Research Release 0.2, tag
btc-research-v0.2. See [release contents and offline installation](releases/BTC_STRUCTURE_0_2.md).
The desk labels this review 0.2 while 0.1 remains the original execution
baseline. The frozen ZIP is downloadable beside the current workbook.
The archive client reads existing paper credentials directly without importing
an order runner; its GET-only host, fields and data treatment are unchanged.

The active review now contains only release 0.1 and the separate E1/E2 full
sequential replays of the identical frozen 30-day stream. The combined workbook
has current comparison, all trades, formula-valued exit legs, sequence changes
and chronological 15m records. Previous single-case, fixed-entry and monthly
research panels/downloads are removed from the active page, while original
files remain at preserved paths with a study archive index. No release is
promoted; 0.1 remains the selected default and frozen source of truth.

The study is selected through trading_records/btc_structure/studies/ACTIVE.json.
Its STUDY.json links the exact source hash, three run IDs, summary partitions,
changed trades and freed-position windows. The opt-in EarlySequentialReplay
inherits original 0.1 behavior and adds only the unchanged E1 or E2 exit.
Signal confirmation requires complete adjacent 15m bars; execution requires
the exact following observed 1m opening. A missing opening is explicitly
skipped, never filled later or carried forward. Existing opening-time
protection wins a tie, then E1/E2, then T1; known openings precede unresolved
minute ranges. Entry history is consumed on entry exactly as before;
exiting does not resurrect an old episode.

Both sequences actually replay all minutes and entry opportunities, rather
than fixing the original trade list. Both happen to retain all 38 entries,
19 wins/19 losses, and the original 56 crossing signals. There are no new or
lost buys in the released windows (E1: 8/514/332 minutes; E2: 289/152 minutes).
E1 changes #11/#12/#32 and nets $4,159.67; E2 changes #12/#32 and nets
$4,195.15; original net is $3,516.46 per initial 1 BTC. No original winner is
reduced. Original stops, entry/target parameters and costs remain unchanged.

The page and workbook list three groups per sequence: all, no flagged gap,
and its complement (holding gap OR incomplete 14-bar entry context).
Baseline clean net is $2,751.29 on 36 trades; E1/E2 clean nets are
$2,998.96/$3,034.44 on 37. Flagged nets are $765.17 on two original trades
and $1,160.71 on one trade in either new sequence. #12 exits before its later
gap and changes groups; subgroup totals are not paired estimates of benefit.
The source still has 558 missing minutes; none is fabricated. See
[the full-sequence audit](investigations/2026-11-09_BTC_E1_E2_SEQUENTIAL_30D.md).

Open <http://127.0.0.1:8799/btc-lab>. Both the desk home and sector board link to
this page. It shows real observed 15-minute aggregates, L1/L2 references, when
references became known, minute-interval entries/exits, stop activation, rejection
reasons and per-initial-BTC model P/L. Choose a research run, New York calendar
date or trade. All candles are retained in the table unless the event filter is
explicitly selected; absent candles remain absent.

This supports the desk's existing North Star of sourced, explicit decisions.
Acceptance targets: every trade references known-at-time structure, zero invented
market minutes, zero order submissions, and visible data-quality flags for every
identified gap exposure. Win rate is a research observation, not a target to
optimize by changing rules after seeing losses.

## Historical B1 refinement: initial single-case check

The owner now requires a separate complete 15m candle after the D candle,
whose low holds the same D, before a subsequent intrabar previous-high break.
The explicit `independent_b1_setup()` validator checks this definition without
changing the monthly default or creating a run. #5's D is known at October 15
09:45 EDT; its 09:45--10:00 confirmation candle breaches D at 09:53--09:54.
Confirmation fails at 10:00. That time is only the earliest hypothetical
eligibility boundary, not a delayed entry. No trade, stop activation or P/L
is manufactured, and no old monthly result/workbook is changed. A real archived
positive control verifies the rule can pass after a separate holding candle.
See [the single-case check](investigations/2026-11-09_BTC_TRADE5_INDEPENDENT_D_HOLD.md).

## Current saved monthly policy: independent failed-rebound exit

The owner explicitly approved a separate failure exit after reviewing losses
over $500. After an observed post-entry swing H, a completed pullback L and a
confirmed lower high LH, a strict break below L exits the actual remainder.
Each swing uses the existing complete 15m left/middle/right convention. The
LH becomes usable only after its right neighbour completes. This is separate
from hard-stop trailing and has no new-high, 1R, ATR-size or dollar threshold.
The entry, original hard stop, 25% first target and costs remain unchanged.

Observed reclaim above LH invalidates that pattern. Missing/incomplete bars
clear unconfirmed construction but cannot revoke a reference confirmed before
the gap; subsequent observed triggers retain gap-exposure flags. An opening
below L uses that opening; otherwise a within-minute strict break uses L.
Unresolved break/reclaim/target ordering is risk-first and explicitly marked.
Candidate priority is hard stop, prior structural protection, failed rebound,
profit giveback, last-minute turning/wick and target at the same observation.
Known minute openings precede unresolved minute ranges.

The current factory selects `FailedReboundReplay`, draft-8. Historical
`turning_consumed_v7` preserves the prior lifecycle/exit combination; pinned
classroom audits continue to use it. The independent exit is not a downward
or premature modification of the original hard stop.

Fixed-old-entry controls for baseline `20261109T034016Z-30-ab`:

| Baseline trade | Prior net USD | New net USD | Conclusion |
| --- | ---: | ---: | --- |
| #5 | -762.75 | -762.75 | Eight-minute stop precedes a completed 15m failure pattern |
| #11 | -700.09 | -327.60 | Confirmed LH/low break exits earlier |
| #12 | -509.86 | -395.54 | Previously confirmed reference retained across a flagged data gap |
| #23 | -1,160.16 | -482.78 | Confirmed LH/low break exits earlier |
| #32 | -990.82 | -732.67 | Earlier structural exit; still exceeds $500 |

Same-source full sequence `20261109T041525Z-30-ab` retains all 38 entries,
19 wins/19 losses, net +$3,516.46 versus +$2,214.63 per initial 1 BTC, net
+6.905525R and max drawdown 3.179710R. Eight exits change, including winning
trades: #13 profit falls from $1,332.64 to $857.61. All changed paths are shown,
not just the five focus losses. #5/#32 remain over $500; $500 is a review
selector, not an approved risk cap or sizing change. The original 558 missing
minutes and every old result/workbook remain preserved. No orders or threshold
search; this remains in-sample research.

The desk and eight-sheet workbook expose all five controls, H/L/LH occurrence,
confirmation/activation times, actual break minute, gross/cost/net, chronological
observations and sequential IDs. Partial last candles show actual observation
end and minute coverage. `LARGE_LOSS_REVIEW.csv` is downloadable. See
[the focused investigation](investigations/2026-11-08_BTC_LARGE_LOSSES_FAILED_REBOUND.md).

## Previous: consume entry history, audit all losses

The owner's subsequent review identified that the old B2 trade #2 re-used
trade #1's 08:30 impulse and 09:26 D. Deduplicating `(route, D, HL)` was
insufficient: a later B2 label or new HL could re-enter an already traded
episode. The current factory consumes all A/B setup history on entry and
rebuilds from complete 15m candles beginning after the entry candle. For a
09:33 entry, fresh structure begins at 09:45. The mixed entry candle cannot
repopulate the detector when it later completes. Existing raw prices, ATR,
resistance and held-position protection references are retained.

Historical direct engines retain their old default, and explicit
`exit_version='turning_v5'` pins the pre-consumption V5 lifecycle. The public
`current` factory and monthly runner use the corrected draft-7 lifecycle.
Unfilled/rejected signals do not consume an episode. No thresholds were tuned.

All 27 original losses have been audited: 19 have pre-previous-entry structure
origins in the old sequence, and three have positive gross but negative net
after fixed friction (categories overlap). Hard stops, confirmed structure
breaks and last-minute turning exits are independently checked against real
Alpaca minutes. No earlier qualified active exit was found and ignored.

Run `20261109T034016Z-30-ab` repeats the same thirty-day source snapshot.
It has 56 signals, 38 eligible entries/closed trades, 19 wins/19 losses,
50% win rate, fixed-initial-1-BTC net **+$2,214.63**, +5.505690R and maximum
R drawdown 3.935983R. There is no open position. Twenty-one original losing
entries disappear from the sequential replay and six retain the same entry;
the new sequence also creates different trades. This is not the arithmetic
removal of 21 losses or out-of-sample evidence. All 19 corrected losses are
also audited, with no reused setup history or execution violations found.
Eighteen have less than initial 1R favourable excursion on the identifiable
minute path; boundary-minute high/low ordering remains unknown.

The eight-sheet workbook includes original 27-loss review and corrected
19-loss review, observed MFE/MAE in original price R, costs, cause, old/new IDs
and sequential disposition. UI sections and `LOSS_REVIEW.csv` show the same
audits. Old records stay immutable; a sidecar flags the old 44-trade run as
containing invalid entries and points to its replacement. The 558 absent
minutes remain absent; corrected gap-exposed trades are #12/#22. No orders.
See [the full loss audit](investigations/2026-11-08_BTC_ALL_LOSING_TRADES_REVIEW.md).

## Historical 44-trade replay: stale entries discovered

Run `20261109T030906Z-30-ab` covers October 9 20:00 EDT through November 8
19:00 EST, end exclusive. The owner explicitly authorized this monthly replay
after the nominated-case reviews. It uses the already-approved A/B1/B2 entry
branches and V5 exits, with unchanged numerical risk/cost parameters. Monthly
`run()` now opts into the expanded B branches; `create_replay()` keeps its
historical entry default for pinned case audits. No broker endpoints are used.

There are 89 signals, 79 eligible, 44 entries/closed trades, 17 wins and 27
losses. Net R is +1.638264R but fixed-initial-1-BTC net dollars are **-$1,253.88**.
These weight trades differently: each R denominator is its own initial net
risk, whereas fixed BTC assigns more dollars of risk to wider stops. Do not
describe this as a profitable fixed-size strategy. Eight trades reach T1 and
exit 25%/75%; 36 exit 100% before T1. There are 43 protection raises, with hard
stop changes and fifteen-minute structural references identified separately.

The source hash matches baseline `20261109T002127Z-30-ab`; all old result,
workbook and workbook-input hashes are preserved in `COMPARISON.json`.
The baseline is -$3,691.76 / -8.764537R with one open position. Both entries
and exits have approved changes, so their combined difference cannot be
attributed to exits alone. No parameter optimization or additional month was run.

Downloads include the seven-sheet XLSX and `SIGNALS`, `TRADES`, `EXITS`,
`PROTECTION`, `LEDGER` CSVs. Trade rows include entry/initial-stop activation,
first-25% time/price/net, actual remainder fraction/time/price/net and UTC
timestamps. A B1 without HL keeps HL blank in CSV/workbook and shows absence
in the view. The detail API supplies full-run closed net dollars separately
from the date-filtered positions, preventing a daily selection from changing
the monthly dollar headline. Old runs remain selectable and unchanged.

There are 42,642 real observed test minutes and 558 absent minutes. Gap-exposed
trades #21/#25 are conditional observed-path estimates. No bars are filled.
See [the full fixed-rule audit](investigations/2026-11-08_BTC_APPROVED_RULES_30_DAY_RETEST.md).

## Current V5: last-minute new-high failure

The public factory defaults to `TurningABReplay` (V5), retaining V4 profit,
structure and wick protection. At the last-minute opening, require a current
new wave high versus the retained completed-bar peak, a preceding complete
bullish candle, observation below that candle's full-range midpoint, current
red price below current 15m open, not above previous close, and neither body
nor observed range contained in the preceding bar. Only fourteen complete
minutes plus the observation are used. No ATR/body-size threshold is added.
This local-range 50% comparison is independent of whole-trade profit giveback.

Shared candidate priority is hard stop, structure, profit giveback, new-high
failure, wick, then targets at the same observation. Known openings still precede
unresolved intraminute ranges. T1 takes 25%; actual remainder exits once. T2
remains disabled and midpoint crossing alone remains a warning.

In the earlier nominated-case pass, evening T1 was 22:57 net +$383.02,
then October 13 04:29 / 83,835.33 exits remaining 75% net +$1,803.78, total
+$2,186.80 per initial BTC. The 04:15--04:30 candle has a 76.28% retracement of
the prior complete bullish range. The earlier 01:44 red/midpoint observation
is rejected because its current candle made no new wave high. Morning exits
and net +$218.90 remain unchanged. This is not validated ETF execution or
out-of-sample evidence.

Historical helpers explicitly request `exit_version='guarded_v4'`; V4 strategy
modules remain unchanged and retain their old 04:50 / +$1,973.40 continuation.
The version dispatcher may evolve without replacing prior results. The saved
case endpoint includes `current_exit_review` for the top panel, preserving all
V1/V2/V3/V4 JSON. That earlier case-only pass did not run a month or submit orders;
the subsequently authorized monthly run is documented above.
See [approved turning replay](investigations/2026-11-08_BTC_OCT12_APPROVED_TURNING_EXIT.md).

## Retained V4 profit guard and original checkpoint

`btc_engine.create_replay(..., entry_mode='ab')` now selects `GuardedABReplay`
with the approved 1R/50%/direction/non-inside guard and the existing V3 structure
policy. Its inherited entry detector is unchanged; expanded B1/B2 is enabled
only in the nominated-case harness, as before. Historical ABReplay/Replay and
prior study JSON remain readable and unchanged. No monthly run was executed.

The guard uses immutable initial entry-to-stop risk, completed post-entry minute
highs (entry-minute high excluded), and each real one-minute opening observation.
It requires maximum favourable excursion >= initial 1R, giveback >= 50%, current
price <= current 15m open AND <= previous complete 15m close, and neither body
nor observed full range inside that previous candle. Equality to open/previous
close is permitted. Missing complete prior/prefix observations withhold this
guard; hard protection remains active. Current minute H/L/C never informs its
opening decision. This is minute-sampled historical research, not tick replay.

A shared additional-candidate hook preserves normal event ordering: known
opening hard stop, structure, giveback, wick, then target; opening observations
precede unknown intraminute ranges. All exits close only current remainder.
T1 still sells 25%, midpoint only warns, fixed T2 is disabled; structure and
last-minute wick protections remain. R does not rebase after partial sales.

`audit_btc_oct12_profit_guard.py` uses the same public factory, restricts entry
permission to the two frozen nominated bars, and verifies all exit prices,
times, quantities and P/L against the previously selected hypothesis. Morning
T1 10:11 +$106.17 and 10:19 remainder +$112.72 total +$218.90 per initial BTC.
Evening T1 22:57 +$383.02; 75% stays open through October 13 01:45. The latter
has no remaining-position realized profit, only separate valuation.

The desk's top panel reads saved approved-case data through the existing
read-only case endpoint; historical V3 and unselected candidate comparisons
remain separately labeled. Stored monthly results/latest_run are not replaced,
and no paper/live order is routed. Approval of this implementation does not
establish out-of-sample profitability. See
[the approved code replay](investigations/2026-11-08_BTC_OCT12_APPROVED_PROFIT_GUARD.md).

## Historical giveback hypotheses, before approval

The saved `oct12_giveback_comparison` study aligns all six morning and nineteen
evening 15m candles, retaining minute-open evidence. Compare the same V3 baseline
against three declared hypotheses: first reach 1 initial R of maximum favourable
excursion, then give back half; optionally preserve trigger-time direction and
body/range-inside exemptions, or additionally restrict checks to the final
minute. The fixed 1R/50% numbers are unoptimized research assumptions, not
previously approved settings or proven optimal values.

The simple candidate exits the morning at 10:06 / 82,752.0485, net +$147.64, but
violates the inside-candle holding preference and is followed by a recovery.
Preserving direction/inside conditions waits until 10:19 / 82,754.706, after
the 10:11 25% target; combined net is +$218.90. Final-minute-only confirmation
waits to 10:44, combined net +$101.27. The 10:15 candle ultimately closes green:
an earlier profit-protection candidate is not proof of a confirmed reversal.

All evening variants take the same 22:57 25% profit and retain 75% through
01:45. After 1R activation, its maximum observed minute-opening giveback is
25.13%; even a conservative high-first/low-second intraminute envelope is only
29.50%. The latter does not assert actual H/L ordering or create fills. Later
price rows after a variant closes are comparison data, not its held P/L.

The saved-case endpoint optionally reads this study; it never runs it. JSON and
chronological CSV preserve all variants, complete-candle metrics are labeled
known only at period end, and no production/default exit rule or monthly
artifact changes. See
[the chronological comparison](investigations/2026-11-08_BTC_OCT12_GIVEBACK_COMPARISON.md).

## Latest opt-in evening case: midpoint warning and 15m structure

`StructureExitMixin` is an explicit single-case research branch; it does not
change monthly defaults or the saved morning/V1/V2 paths. The October 12 21:00
entry is reviewed only through October 13 01:45 EDT, using 285 contiguous real
minutes. Midpoint crossings warn only; fixed T2 is disabled while unchanged T1
sells the initial 25%. Original hard protection and 2bps-per-side costs remain.

For this selected 15m structure rule, a higher low must be below both complete
adjacent lows, above the retained reference, and followed by a complete bar
exceeding its pre-pullback rally high. Activate only when both confirmations
are known. A strict intrabar break of that active raw low exits the remainder;
opening gaps use observed open, not a retroactive threshold. This introduces
no new buffer or body-size parameter. Full-range or body containment blocks
shape-only wick exits, never actual structural breaks or hard protection.
The wick still uses the prior fourteen minutes and final-minute open, with
non-green/previous-close filters; final candle colour is not used early.

T1 sells 25% at 22:57 / 82,962.195014889, realized net +$383.02 per initial BTC.
The structure reference activates at 23:00 / 82,578.695; 23:45 / 82,677.245;
01:15 / 83,153.77; 01:30 / 83,285.235. The 01:40 break of 83,508.87 is only a
previous-candle break, not a confirmed swing break. Through 01:45, the remaining
75% is still open: last observed close 83,488.2935, gross unrealized +$1,568.29,
or +$1,556.08 after its allocated entry friction. Pre-deducting hypothetical
future exit friction gives +$1,543.55, not realized P/L or a sale. No forced
end-of-review liquidation is inserted.

A new holding diagnostic compares profit giveback at prior V2 checkpoints:
(known post-entry peak minus reference price) / (known peak minus entry). Morning
10:05 gives 47.55% / 0.728 initial R versus evening 22:31 at 7.57% / 0.192R.
Only complete prior minutes plus observed current opening/reference are used;
the morning peak known then is 82,950, not the unfinished 15m candle's later
83,040.768 high. Both entries are B1. This is post-entry diagnosis, not a new
entry classification, exit threshold, or evidence of predictive profitability.
Near-zero favourable excursion makes this ratio unstable.

`GET /api/btc-lab/structure-case` reads the saved single-case JSON without jobs
or orders. A separate latest-case table includes every 15m candle and distinguishes
realized legs from cutoff valuation. JSON and chronological CSV live under
`oct12_structure_exit/`. See
[the single-case audit](investigations/2026-11-08_BTC_OCT12_STRUCTURE_EXIT.md).
No month was rerun; every prior artifact and latest_run remain intact.

## Direction-filtered active exits; two cases only

Current A/B replay uses `ApprovedExitReplay` V2. Both intrabar next-bar midpoint
and last-minute upper-wick exits require observation price <= the current 15m
open AND <= the previous complete 15m close. Equal-to-open is neutral, not green;
equal-to-previous-close is allowed. Never inspect the unfinished bar's final close.
Missing true opening or complete preceding-bar data withholds active exits,
never the original protective stop. Midpoint waiting uses the newly eligible
crossing reference, not a retroactive fill at a previously rejected higher price.

Midpoints still apply only to the next bar after a complete post-entry new high;
a further intrabar high does not cancel them. Wick observation still uses only
fourteen complete minutes plus the final minute's opening observation, with
>=50%, new-high and above-entry conditions, without an integer gate.
Known minute-open observations precede unresolved H/L; ambiguous range ties
retain stop > midpoint > target priority and an explicit ambiguity flag.
Active exits close the current remaining quantity once, without same-minute
reentry. Stops, target selection, 25%/75% sizes and costs remain unchanged.

Only the October 12 fixed entries were replayed. Morning: 09:33 entry, 10:05
midpoint full exit at 82,769.94775, net +$165.53 per initial BTC. Evening: 21:00
entry, 22:29 wick rejected because 82,637.30 exceeds previous close 82,627.021;
22:30 midpoint opening also rejected, and its minute low stays above the bound.
At 22:31--22:32 the price crosses 82,655.0085, meeting all gates, full exit net
+$1,224.95. Both exit before T1; neither has partial target fills or stop raises.

The saved V2 artifact is `oct12_direction_filtered_exits/REVIEW.json`.
`exit_policy='approved_v1'` preserves V1 (+$165.53 / +$1,207.25), and `legacy`
preserves original studies. Frozen `Replay` methods, all prior case artifacts,
monthly results and latest_run remain unchanged; no monthly run or order.
`GET /api/btc-lab/cases` reads saved V2 cases only, without starting jobs, and
keeps them separate from monthly metrics. See
[the direction-filter review](investigations/2026-11-08_BTC_OCT12_DIRECTION_FILTERED_EXITS.md).

## October 12 morning exit-only review

The original parent-stop conditions do not authorize a raise during the holding
interval, and the 25% target does not automatically move protection to breakeven.
However, the already-approved manual midpoint exit triggers at 10:05 before
the 10:11 first target. A separate no-round-gate wick event is visible at 10:14;
it is conditional after the earlier full exit. The former nets +$165.53 per
initial BTC as a complete exit; retaining the original 25% leg then applying
the later wick condition would net +$286.36. Do not combine these paths.
The old -$104.11 reflects the frozen webpage implementation, which lacks midpoint
exits and blocks the wick with its historical integer gate. No engine behavior,
parameters, original case artifact or monthly result changed. See
[the six-candle review](investigations/2026-11-08_BTC_OCT12_MORNING_EXIT_REVIEW.md).

## Opt-in B1/B2 two-case preview

`ABReplay(..., expanded_b=True)` now supports continuous pre-rebound D
extensions, B1 first stabilization breakout (no invented HL), and B2 completed
rebound/HL retest. Completed-minute causality, unchanged protective/exit methods,
and explicit support/trigger ordering checks remain. Monthly defaults do not
opt in; no run registry or latest pointer was changed. The October 12 nominated
09:30/21:00 cases trigger at 09:33/21:00. The first takes 25% then stops the
remaining 75%, net -$104.11; the second reaches both targets, net +$1,833.70 per
initial BTC. Later B2 signals remain held-position annotations. Full source,
stop-effective times and exit legs are in
[the two-case audit](investigations/2026-11-08_BTC_OCT12_B1_B2_CASES.md).

## A/B integrated replay and positive-net qualification

The saved thirty-day comparison used `Alpaca-BTC-AB-entry-positive-net-draft-2` and routes
through `ABReplay`. Both entry routes are causal mechanical drafts. Confirm
15m turns with one completed neighbour each side; retain nested declining
scopes and prefer the widest structurally eligible origin. Internal HLs never
replace the retained D. This is not validated human wave-level equivalence:
November 7 is five mechanical phases versus four owner-marked larger phases.

Under the owner's latest instruction, **2R is advisory**. Known target reward
must be strictly positive after the unchanged 2bps friction each way; absent
targets remain unavailable. Do not select entries by later realized profit.
The new run has 62 deduplicated signals, 51 qualified candidates, 21 entries,
20 closed (7 wins/13 losses, -8.764537R) and one open. The test has 42,642 real
minutes and 558 absent minutes; nothing is filled. All 2,880 15m aggregates show
coverage. Old result folders, including the strict-2R comparison, remain intact.

`ABReplay` inherits the original protective/target/exit behavior. Its hooks add
entry structures, labels and stop-history records only. The historical $1,000
wick gate remains; later handbook midpoint/no-round-gate revisions are not
silently included in this entry-only experiment. Source and implementation
hashes are saved in each run.

The page provides route/qualification filters, rejected and held-position
signals, setup evidence and downloadable SIGNALS/TRADES/EXITS/LEDGER CSVs.
The current reviewed six-sheet XLSX is attached as RESEARCH.xlsx. Future runs
produce fresh CSVs; XLSX requires the existing workbook builder/QA step.
Downloads use validated run IDs and an explicit file allowlist. GET never
starts a job; no route calls a broker. See
[complete retest](investigations/2026-11-08_BTC_AB_30_DAY_RETEST.md).

## Initial standalone validators (archived strict-2R review)

The following sections preserve the pre-integration case audits, including
their historical 2R conclusions; current policy is described above.



[Entry definitions](BTC_ENTRY_RULES.md) separate A (four independent LL phases,
intervening LH, then HH/HL/local breakout) from B (completed bearish new-low
shock of at least 2 pre-shock ATR14, completed rebound, HL/local breakout).
The 2-ATR threshold is a declared unoptimized research draft. B does not wait
for four lows or a break of the first rebound peak. Both use the existing
intrabar previous-completed-high trigger and unchanged risk/cost/exit checks.

`btc_entry_rules.py` validates reviewed wave facts and their known-at times;
it does not solve automatic wave hierarchy. The November 7 21:58 A signal and
November 8 17:58 B signal pass structure/price checks but fail the original 2R
screen at 1.8068R and 1.6323R. See the separate
[November 8 source audit](investigations/2026-11-08_BTC_1745_SHOCK_ENTRY_REVIEW.md).
The fresh response has 630 real minutes from 08:00 to 18:30 exclusive; its
partial endpoint minute is excluded. Missing data is never filled.

These validators are not connected to the frozen monthly engine, UI replay
button, signal deduplication orchestration or broker. No monthly rerun or orders.

## November 8 follow-up: four-case hierarchy review

The owner rejected automatic replacement of a larger parent D by internal
pullbacks and rejected the $1,000 gate for wick exits. They confirmed that a
next-bar drop below the prior completed new-high 15-minute candle's full-range
midpoint is a full remaining-position exit. This is independent of the last-minute
wick window. New highs in this review must exceed the retained setup parent H1,
not merely a tiny post-entry local high. Preserve the earliest trigger, including
ones earlier than the owner's nominated selling candle.

Only #23/#24/#25 and November 7 21:30 were audited. The frozen draft-3 engine and
its replay button still describe the historical implementation below; new rules
have **not** been promoted to a monthly run. Case evidence flags #23's initial D
as already undercut before entry, records its 07:32 midpoint event as conditional
after an earlier 04:29 wick, and retains #25's loss rather than forcing an exit.
See [four-case review](investigations/2026-11-08_BTC_FOUR_CASE_HIERARCHY_REVIEW.md).

The owner subsequently supplied a chart and the four low intervals, correcting
our mistaken reset at child rebound peaks. Count the whole decline from November 7
04:00: 06:15, 07:30, 10:45 and 16:30. Each has completed rebound evidence, known
by 17:00. The four-low gate therefore **passes**. The short-scope diagnostic
count of two remains preserved only as evidence of the old scope error.
Coinbase and Alpaca each validate four decreasing phases independently; Alpaca's
second phase minimum occurs at 07:46 rather than in the Coinbase 07:30 candle.

The owner confirmed alternating lower lows (LL) and lower rebound highs (LH),
using 15-minute structure for now. The first three rebound peaks decrease; the
fourth rebound exceeds the preceding rebound high, so label it HH/structure
strengthening, not LH. A subsequent 21:15 HL and the 21:58 local breakout are
separate evidence. This is an annotated in-sample case, not a validated general
live detector. Thirty-minute/hourly comparisons are deferred, without changing
this case's timeframe or running a new monthly test.

The November 7 21:45 bar has a price breakout at 21:58. Four-wave evidence passes;
the original net-2R gate independently remains below threshold. The frozen engine
also incorrectly requires a fresh L2 on the immediately preceding bar, silently
losing a later breakout of an otherwise unbroken L2. The case corrections do not
change the frozen monthly replay button or its results.

The separately requested November 7 21:45 holding-path audit assumes entry at
21:58 at 75,655.545 while preserving the failed net-2R gate as a qualification
limitation. Initial protection is 75,444.876375 and never rises before the first
exit: at the 22:59 minute's opening provider observation, a 70.55% upper wick at
a new high closes the hypothetical full position at 75,779.12. Per initial BTC,
gross is $123.575 and net after the unchanged 2bps each way is $93.288067.
No target partial occurs and later stop upgrades do not belong to this closed
path. The new high is just $0.866 above the prior peak; no minimum-breakout filter
was silently added. See [unified timeline](investigations/2026-11-08_BTC_2145_ENTRY_TIMELINE.md).
The original engine, run pointer and monthly artifacts remain unchanged.

## Source and archive

`trading_desk/btc_data.py` requests only Alpaca's official US crypto bars GET
endpoint, BTC/USD, 1Min. Existing paper credentials are read locally and never
returned to the page. The paper account was read-only checked ACTIVE, unblocked,
and BTC/USD tradable; no orders were submitted. Credential presence or paper
readiness does not make historical prices executable.

Frozen download cutoff: **2026-11-08 19:15 UTC**. Observed coverage:
**2021-01-01 06:00 UTC–2026-11-08 19:14 UTC**, **2,741,551 records**.
The request began in 2016; the earliest *returned* observation is 2021, not a
claim that every earlier venue/feed is unavailable. The archive span contains
**336,524 missing minutes** and **1,160,610 zero-volume observations**. Alpaca
crypto bars may incorporate quote midprices; zero volume must not be presented
as an actual trade. See [Alpaca data semantics](https://docs.alpaca.markets/us/v1.1/docs/historical-crypto-data-1)
and [historical bars endpoint](https://docs.alpaca.markets/us/reference/cryptobars-1).

The ignored local folder `trading_records/btc_structure/` stores SQLite minutes,
raw gzip responses, SHA256/source manifests, resumable pagination states and
immutable dated research runs. No interpolation, default bars or carry-forward
prices are permitted. Conflicting overlap observations fail without overwriting
the cache. A download lock prevents simultaneous writers. Update recent history
or extend all history using the explicit buttons; opening the page makes no
market-data requests and starts no job.

## Mechanical draft and limits

This is an explicit first programmatic draft, **not proven equivalence to the
owner's discretionary examples**. The existing frozen Coinbase month and
October/November teaching audits are unchanged. Providers can differ in exact
OHLC prices, and mechanically selecting the latest confirmed D can differ from
the owner selecting a particular earlier D. Review that difference before
interpreting the backtest as a test of the complete manual.

- Previous-D L1: a completed hourly pivot low, below its adjacent completed hours;
  the right hour must finish before confirmation. L2 is the previous completed
  15-minute pullback bar and requires all fifteen real minute observations.
- Enter intrabar on the next observed minute crossing the previous 15-minute full
  high plus $0.01. Require a higher L2, the existing 0.10 ATR chase cap and net
  first-target reward/risk of at least 2. Initial protection uses L1 less the
  existing 0.25 pre-entry ATR. ATR is simple fourteen completed 15-minute true
  ranges. L2 is still the eligibility starting point for later new parent lows.
- Target: a causally confirmed 4-hour high (two completed bars each side), within
  a confirmed major hourly resistance zone, above formation H1, with the existing
  0.10 ATR buffer. This is a declared mechanical hierarchy, not optimized.
- Same-level protection can rise only after a higher hourly pivot low and a break
  of a preceding confirmed parent peak. Both facts must be known. Breakout ATR
  must precede that breakout. Stop changes take effect at the next 15-minute
  boundary; the ledger explicitly labels the state after the row's end.
- Ordinary targets sell 25% then 75%. A stop exits all currently remaining shares.
  A last-minute upper-wick rejection also exits all remaining shares. The automated
  watch-level proxy is the nearest lower **$1,000** level of the prior completed
  15-minute close. It requires a new high, return below the level, upper wick at
  least 50%, and a level above entry. This proxy for a manually drawn resistance
  line is **a research choice needing review**, not an owner-approved universal
  resistance rule.
- At the last minute's first observation, use only the preceding fourteen completed
  minutes and that minute's open. Do not use its final H/L/C or the next minute's
  open. This cannot detect triggers first occurring later in that minute; finer
  data would be required. Ordinary intraminute stop/target ordering is unknown;
  adverse-first is used, entry-minute stop ambiguity is flagged, and a minute
  cannot host a second entry after an existing position closes.

Study BTC signals 24/7, as requested. Cost assumption: ETF zero commission plus
**2bps each way** spread/slippage. This is **not actual ETF execution or return**;
no ETF trading-hour filter or BTC-to-ETF tracking model is asserted. Each trade
is normalized to one initial BTC. Net R totals are a noncompounded sequence, not
an account percentage or portfolio backtest. No capital or buying power is used.

## Quality handling

Aggregates contain only observed prices and show observed-minute counts. Partial
context is visible; missing intervals are never populated. Holding-period gaps
mark trades `gap_exposed`; incomplete entry ATR windows mark `context_partial`.
Such P/L is conditional on the observed path; an unobserved trigger may have
occurred during a gap. Both overall and **no-flagged-gap subset** metrics are
shown. The subset checks the preceding fourteen 15-minute bars and holding path,
not every older source bar used by all resistance/parent context. It does not
certify full historical completeness. Source zero-volume observations remain
quote references even in the subset.

## Frozen initial results

| Run | Closed | Wins / losses | Net R | No-flagged-gap subset |
| --- | ---: | ---: | ---: | --- |
| `20261108T195603Z-30` · 30 days | 25 | 5 / 20 | -10.0017R | 21 trades, -8.9770R |
| `20261108T195604Z-all` · all after 7-day warmup | 1,060 | 287 / 773 | -104.6770R | 535 trades, -155.7423R |

Both are negative under this draft. The subset is not a controlled matched
comparison, and removing gap-exposed trades changes the sample. No profitable
strategy or exact manual equivalence is claimed. The preliminary local run
`20261108T144224-30` is retained as superseded following event-ordering review;
it is omitted from the active page. Draft 3 additionally flags wholly absent 15-minute buckets in the entry context;
older draft-2 runs remain preserved as superseded. These integrity fixes did not
change trade paths or overall metrics. No parameter search was performed.

## Interface and maintenance

GET `/api/btc-lab` reads source/job/run summaries. GET `/api/btc-lab/run` accepts
validated `run_id`, New York `day`, optional `trade_id`; day responses are capped
at 101 observed candles (including a 25-hour DST day). SQLite day indexes keep
all-history review bounded. POST `/api/btc-lab` permits only `sync_recent`,
`sync_all`, `backtest` and periods 30/90/365/all. It requires JSON and rejects a
foreign Origin, under the existing loopback Host guard. The module has no order
operation. A single background research job is allowed; previous successful
results remain available after a failure. Downloads can resume after interruption;
backtests create new run folders and do not resume a half-written run.

Relevant modules: `btc_data.py`, `btc_engine.py`, `btc_lab.py`, `btc_lab.html/js/css`.
Tests exercise real preserved minute observations, missing-data propagation,
open-time wick precedence, full remaining-position stops, no same-minute re-entry,
source normalization and the read-only HTTP contract.

## External drive location

The six repositories formerly under `/Users/danielshan/github` now reside under
`/Volumes/SanDisk Extreme/github`. The original path is a compatibility symlink.
The migration verified all 78,896 regular files by SHA256, all 19 symlinks and
six repository Git states before cutover. Audit:
`/Volumes/SanDisk Extreme/GITHUB_MIGRATION_AUDIT.json`.
The desk was restarted from the physical external path on port 8799. Keep the
volume connected while using the repositories or the running desk.

## Release 0.1 and independent B1 monthly rollout (November 9)

The BTC model has its own immutable local release 0.1, separate from LumiBot's
package version: original 38 trades, net +$3,516.46. Its manifest, actual minute
stream, shipped sources and original workbook independently reproduce all fills
and metrics. The run selector and download endpoint expose the frozen bundle.
No GitHub publication is implied. See `docs/releases/BTC_STRUCTURE_0_1.md`.

Current `create_replay(..., exit_version='current', expanded_b=True)` uses draft-9
B1 independent post-D confirmation. Historical `failed_rebound` pins draft-8.
A separate complete 15m bar (15 observed minutes) must hold the same D after
D known_at. A lower completed D restarts the wait; rejected waiting crossings
have separate dedup tokens so they cannot consume a later valid signal. No
risk thresholds, costs or exit policies changed. `window_end` explicitly pins
the prior data cutoff for fair comparisons. No new environment variable.

Same-source run `20261109T122648Z-30-ab`: 36 closed trades, 18/18 wins/losses,
net +$2,805.01 (below 0.1), +2.169071R. All 33 B1 entries pass causal confirmation
checks; 26 waiting crossings remain inspectable, not counted as trades. The
comparison CSV and eighth workbook tab track all 38 baseline entry timestamps.
`B1_CONFIRMATION_REVIEW.json` keeps original #5's detailed audit separately.
Missing-data policy and source hash remain unchanged.

## Active baseline retained: Release 0.1

On November 9 the owner retained Release 0.1 after the independent-B1 month
underperformed. `releases/ACTIVE.json` selects 0.1 separately from
`latest_run.json`; latest continues to identify the newest experimental result.
`Lab.status().default_run` drives the initial view. Manual selection of other
records remains available; no original result or workbook is overwritten.

New `btc_engine.run()` jobs default to `research_policy='release_0_1'`, selecting
the pinned draft-8 `failed_rebound` factory with original aggressive B1.
The desk explicitly passes that policy. The independent-B1 audit runner
explicitly passes `research_policy='independent_b1'`; the low-level `current`
factory remains the draft-9 research variant for historical experiment tests.
No change to frozen release source, numerical parameters or exit logic.

`investigate_btc_release01_performance.py` reads all 38 baseline trades and
real observed minutes only; it does not replay a strategy or use order APIs.
It checks all 19 losing exits and ranks loss/profit-retention review cases.
18/19 losses never observed the original price-risk 1R activation. One (#3)
passed 1R but body-inside protection delayed its exit. #5 and #32 are the two
largest losses. Hindsight best-open liquidation values are diagnostic, not
causal exit signals or recoverable profits.

One unpromoted fixed-entry probe tests a complete red, <= prior close,
non-inside 15m candle losing the original breakout trigger, with liquidation
at the following observed minute open. Across all 38 original entries it
changes 15 exits (9 improve, 6 worsen), net delta -$325.53. #32 improves by
$521.32 while #30 worsens by $1,500.51. This is not sequential monthly P/L and
is not adopted. `investigations/RELEASE_0_1_PERFORMANCE.json` and the matching
November 9 investigation document retain the full comparison. The baseline
view exposes it without editing the release workbook or ZIP.

## Three-case pullback review: release 0.1 remains unchanged

The read-only `audit_btc_release01_pullbacks.py` reviews #5, #32 and #30 from
the frozen run. It reads 1,095 actual minutes and validates all 73 complete
15m aggregates against the original ledger. It never creates an engine or
calls replay/order APIs. `investigations/RELEASE_0_1_PULLBACK_CASES.json`
adds a separate baseline-only detail field and three expandable view tables;
the original result, workbook, release ZIP, latest pointer and active selection
remain unchanged. Every candle has its completion/known time; terminal candles
which complete after exit are explicitly comparison-only. Entry/exit minute
ranges are not assumed to reveal within-minute fill ordering.

#5 loses D and its original hard stop before its first post-entry 15m candle
can complete. #32's 12:15 weakness is a warning, not a confirmed H-L-LH low-break;
its first 14:15 anchor is invalidated by a reclaim, and the 14:30 bar recovers
the original entry trigger. The final LH confirms at 17:45, breaks L at 17:47.
#30's 09:15 candle (known 09:30) is red/below trigger but has higher high and
higher low, while the 08:15 effective HL 78,026.42 remains intact. T1 at 09:40
and the later 14:05 failure exit are future observations, not reasons available
to the 09:30 decision. Numeric thresholds and existing exemptions are unchanged.

## #32 early exits versus #30: E1 / E2 research only

`audit_btc_release01_early_failure.py` reads only frozen cases and does not
instantiate an engine. `RELEASE_0_1_EARLY_FAILURE.json` is a baseline-only
read-only detail field and view panel. All run/result/workbook files, release
files, latest and active pointers are verified unchanged; no monthly replay.

E1 uses two consecutive adjacent complete 15m lower-high/lower-low comparisons
(three candles, not independent parent swings), a close below the original
entry trigger, red/<= previous close, and neither body nor full-range inside.
It values liquidation at the following real minute opening. E2 uses that
weakness as background, then a complete reclaim, complete failed reclaim and
immediate following lower-high/lower-low direction/non-inside confirmation.
These are explicit, unpromoted research assumptions; in particular they sample
direction at completed signal closes rather than release 0.1 intrabar guards.
No numerical stop, target or cost parameter changes, no missing-data filling.

On November 5 #32, E1 confirms 12:15 EST: observed opening 76,079.9285,
net -$211.35, +$521.32 versus the original. E2 confirms 15:15: observed opening
75,961.01, net -$330.24, +$402.42. The alternatives close 100% independently,
not two cumulative legs. #30 triggers neither and retains its original staged
net +$1,454.49. Prefix-only replay of the arithmetic (not a strategy replay)
verifies no early signal depends on later candles; absent execution minutes
produce null price/P&L. Post-candidate trace rows are labeled original-path
comparison only. Two in-sample cases do not establish monthly improvement.

## E1/E2 overlays on all 38 fixed release entries

`audit_btc_release01_early_failure_all.py` reuses the unchanged E1/E2 functions
and the actual minute stream packaged in frozen release 0.1. The stream SHA256
matches the original run. No engine or replay is instantiated: all 38 original
entries, original risk/target/cost parameters and earlier partial exits remain
fixed. Only strictly earlier confirmed exits may override the original final
exit; identical final-exit minutes retain baseline. Original target exits in the
candidate opening minute are excluded under the documented opening-risk-first
valuation assumption, not claimed as verified tick ordering.

E1 changes #11/#12/#32: fixed-entry net $4,159.67, delta +$643.21. E2 changes
#12/#32: $4,195.15, delta +$678.69. All 19 original profitable trades retain
identical legs; both overlays remain 19 wins/19 losses. #12's original holding
path has seven missing minutes, all later than either alternative exit, so its
improvement still compares with a conditional gap-exposed original outcome.
The 36-trade no-original-holding-gap subset has delta +$585.90 E1 / +$402.42 E2.
This is exit attribution, not a new sequential monthly strategy return.

The baseline-only API field `early_failure_fixed38` reads
`investigations/RELEASE_0_1_E1_E2_FIXED38.json`. The view displays all 38 rows,
all altered trades and the original 19 profitable controls. Its separate
`E1_E2_FIXED38.xlsx` contains a formula-reconciled 38-trade comparison and all
132 original/alternative exit legs. Export is a single allowlisted analysis
path available only for release 0.1, never a write into the frozen run folder.
All original workbooks, two-case study, source snapshots and active/latest
pointers are preserved. Neither candidate is promoted.
