BTC Structure Retest
====================

A read-only thirty-day BTCUSD signal experiment and spreadsheet.

:Last Updated: 2026-11-09
:Status: Mechanical research draft; conditional observed-path results, no orders
:Audience: Trading Desk users and research maintainers

Overview
--------

Research release 0.2
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The approved comparison is frozen under the independent GitHub tag
``btc-research-v0.2``. The parent LumiBot version is unchanged. The desk labels
the review 0.2 and offers its ZIP alongside the current workbook; 0.1 remains
the execution baseline and E1/E2 stay separate alternatives.

Extract the release ZIP and run ``python3 REPRODUCE.py`` with Python 3.10+
and the standard library. No credentials or network are needed. File and
source hashes, every signal, entry, stop, target, exit leg and metric are
verified across the complete three sequences. The unchanged 0.1 ZIP is bundled.
Optional ``--install-store /path/to/ai-day-trade/trading_records/btc_structure``
installs verified research for a fresh desk, refusing conflicting files.
The live archive client loads existing paper credentials directly without
importing the unrelated paper-order runner; its market-data-only host is
unchanged. No order capability is added.

Current: independent E1 / E2 full sequential replay
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The current page contains only frozen release 0.1 and the E1/E2 sequential
replays of the identical October 10--November 9 UTC window (exclusive end).
Each strategy processes the full real minute stream and permits later entries
after an early exit. Original entry, hard-stop, risk, target fractions,
protection and 2bps-per-side cost parameters are unchanged; 0.1 remains the
selected baseline. Neither E1 nor E2 is promoted.

Both replays retain all 38 entries and 19 wins / 19 losses; no new buys or
omitted original buys occur. Every freed position window contains zero new
crossing signals. E1 changes exits #11/#12/#32 and nets $4,159.67; E2 changes
#12/#32 and nets $4,195.15 versus original $3,516.46, per initial 1 BTC.
These totals happen to equal the earlier fixed-entry study; they are now
independently verified full-sequence results. All original winners retain
their exits.

Gap partitions are mutually exclusive. The no-flagged-gap group requires
no observed holding gap and a complete adjacent 14-bar entry context; the
flagged group is its complement. Baseline clean/flagged totals are
$2,751.29 (36 trades) / $765.17 (2); E1 totals are $2,998.96 (37) /
$1,160.71 (1); E2 totals are $3,034.44 (37) / $1,160.71 (1).
Trade #12 exits before a later gap and changes groups, so subgroup differences
are not matched-trade improvements. Missing source minutes remain absent.

E1/E2 use the original complete-bar definitions and the exact following
observed minute opening. Missing execution openings are skipped, never
backfilled. Existing opening-time protections retain priority. A single new
workbook provides current summaries, every trade and exit-leg P/L, changed
holding windows and chronological 15m records. Previous studies and workbooks
are removed from active display/downloads; their original files and the frozen
0.1 release are preserved with an archive index.

Archived: all 38 fixed entries, unchanged E1 / E2 exit comparison
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The baseline view now applies the same E1/E2 definitions independently to all
38 original release 0.1 entries. It reads the frozen real minute stream and
verifies the original source hash. No strategy engine or monthly replay runs.
Original entry, stop, target, cost and earlier partial-exit terms remain fixed;
only an earlier candidate confirmation may replace the original final exit.

E1 changes #11, #12 and #32: fixed-entry net $4,159.67, difference +$643.21.
E2 changes #12 and #32: $4,195.15, difference +$678.69. All 19 original winners
retain identical exits and P/L; neither overlay reduces a profitable trade or
turns a winner into a loss. Both retain 19 wins / 19 losses; gains are loss
reductions, not an improved win rate.

#12's original holding path contains seven missing minutes, after both
candidate exits. Its improvement still compares with a conditional original
outcome. In the 36-trade subset without original holding gaps, differences
are +$585.90 E1 and +$402.42 E2. This subset reverses the aggregate ranking;
neither candidate is adopted based solely on the full-sample total.

The desk exposes all 38 exit confirmations, times, prices and P/L differences,
plus a separate workbook with 132 formula-valued exit legs. The analysis export
is allowlisted only for release 0.1 and stored outside its immutable run and
release folders. Original results, workbook, earlier two-case study and
active/latest pointers are unchanged. These fixed-entry sums are not new
sequential monthly performance or actual ETF fills.

Earlier #32 exits: E1 / E2 versus profitable #30
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The read-only release 0.1 detail now includes two alternative early-exit
hypotheses, applied identically to frozen #32 and #30 without a monthly replay.
E1 requires two consecutive adjacent complete 15m lower-high/lower-low
comparisons (three candles), red/<= prior close, neither body nor range inside,
and a close below the original entry trigger. E2 first requires that weak
background, then a complete reclaim, failed reclaim and immediately following
complete downward confirmation. These are research assumptions, not adopted
rules or replacements for the original D/hard stop. Their direction filters
use complete signal bars, distinct from release 0.1 intrabar protection.

#32 E1 confirms November 5 12:15 EST: next observed minute opening 76,079.9285,
model net -$211.35 versus original -$732.67. E2 confirms 15:15 EST at 75,961.01,
model net -$330.24. Both precede the original 17:47 exit. They independently
close 100% before T1; they are not combined. Missing execution observations
leave price and P/L blank. ETF zero commission plus 2bps each way is unchanged.

#30 has no qualifying weak background at its 09:30 pullback, so neither early
exit occurs. It retains the original 25%/75% legs and net +$1,454.49. Later
original-path rows are clearly comparison-only after a hypothetical exit.
All release/result/workbook files and active/latest pointers remain intact.
These two repeatedly reviewed cases cannot establish whole-month improvement.

Three-case review: pullback versus failed breakout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The release 0.1 view now separately exposes #5, #32 and profitable control #30:
73 complete fifteen-minute candles and all 1,095 observed minute records.
Each candle shows when its full OHLC becomes known. Candles completed after
the original exit and terminal-minute price ranges are clearly marked; they
cannot supply an earlier exit. No strategy replay, release change, workbook
rewrite or monthly rerun occurs.

A close below the entry trigger is a warning, not by itself structural failure.
#5 breaks D/hard protection in eight minutes, before a post-entry 15m candle
can finish. #32's 12:15 warning precedes its first complete failure anchor at
14:15, which is invalidated by a reclaim; the final LH is known at 17:45 and L
breaks at 17:47. #30's 09:15 red candle (known at 09:30) raises both high and
low and holds the already effective 78,026.42 HL. Its later T1 and profit exit
cannot be used as hindsight justification for the earlier hold decision.

All times above are New York local times on the respective trade dates. The
view keeps original D, hard stop, confirmed 15m structure and independent
failure-exit references separate. No new failure rule has been adopted.

Active baseline: Release 0.1 retained
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After the same-source comparison, the owner retained Release 0.1 as the desk
default. The newer independent-B1 run remains selectable as an experiment;
it does not replace the release. Source, results, original workbook and ZIP
are unchanged. New replay jobs use ``research_policy='release_0_1'`` by
default. Independent-B1 research must explicitly select ``independent_b1``.
The low-level ``current`` factory remains draft-9 for that explicit research
path; the active monthly default selects pinned draft-8 instead.

The first performance investigation found 18 of 19 losing trades never
observed the existing price-risk 1R activation. A fixed-entry exit probe based
on a complete red, non-inside candle losing the original breakout trigger
changed 15 exits: nine improved, six worsened, net difference -$325.53. The
probe helped #32 but exited profitable #30 prematurely; it is not adopted.
These are fixed-entry comparisons, not new sequential monthly returns. The
release view displays the loss/profit-retention investigation separately.

Release 0.1 and same-source B1 comparison
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

BTC research Release 0.1 freezes run ``20261109T041525Z-30-ab``: 38 closed
trades, 19 wins/19 losses, net +$3,516.46 per initial 1 BTC. This is a local
research release, not the parent LumiBot version or a GitHub publication.
The frozen ZIP includes source, actual minute observations, results, original
workbook and ``REPRODUCE.py``. Run it after extraction without broker access.
All entry/stop/target/exit-leg and metric comparisons reproduce identically.

Select ``Release 0.1`` in the Trading Desk to download the original workbook
or frozen ZIP. The retained experimental run ``20261109T122648Z-30-ab`` changes only
B1: an independent complete fifteen-minute candle after D must hold that D
before a subsequent intrabar previous-high break. Lower D restarts the wait;
a rejected early crossing cannot consume the later valid trigger.

The same thirty-day input yields 36 closed trades, 18 wins/18 losses, net
+$2,805.01, +2.169071R. This is $711.44 lower than 0.1; no threshold was tuned
to improve it. All 33 B1 entries pass causal confirmation, and 26 unconfirmed
crossings remain reviewable. All 38 baseline entry timestamps are compared
in the B1 audit panel, CSV and eighth workbook sheet. Other risk parameters,
exit rules, target split and 2bps-per-side cost model remain unchanged.

The window ends November 9 00:00 UTC exclusive, with 42,642 observed test
minutes and 558 absent minutes. Missing observations stay absent. These are
in-sample BTC signals with ETF execution-cost assumptions, not real ETF P/L.



Approved B1 post-D hold: monthly rollout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The owner now requires an independent complete fifteen-minute candle after
the D candle, whose low does not breach that same D, before a subsequent
intrabar break of the latest completed candle high. The original $0.01
increment and numerical risk/cost/exit settings remain. A recovery close
above D does not erase an observed intrabar breach while waiting.

The independent-B1 experiment uses independent post-D confirmation.
Historical release 0.1 retains the original aggressive B1 definition.
D at 80,003.855 becomes known on October 15 at 09:45 EDT. The 09:45--10:00
candle must first complete, so the old 09:45 entry is prohibited. It breaches
D during 09:53--09:54 and ultimately has low 79,691.8665. Thus confirmation
fails at 10:00 even though its close recovers above D. There is no actual new
entry time, executable trigger or stop activation. 10:00 is only the earliest
hypothetical eligibility boundary if confirmation had passed.

No monthly replay, order, default switch or historical result/workbook change
was performed. No-trade P/L stays unavailable rather than becoming a zero-dollar
trade or an arithmetic improvement to the old month. See
``docs/investigations/2026-11-09_BTC_TRADE5_INDEPENDENT_D_HOLD.md``.

Read-only trade #5 B1 audit
~~~~~~~~~~~~~~~~~~~~~~~~~~~

On October 15, the 09:30--09:45 EDT candle makes a fresh D at 80,003.855
and recovers to 95.29% of its range. The historical B1 definition permits that
same completed candle to supply both D and the first-stabilization reference;
09:45--09:46 crosses its high and conditionally buys at 80,655.71. Mechanical
B1 passes; no independent fifteen-minute HL is present, so B2 fails. Genuine
one-minute HLs at 09:36/09:41 are confirmed at 09:38/09:43 and remain internal
to that single fifteen-minute candle.

The breakout minute closes below the trigger; its completed rejection is
known at 09:46. The 09:52 low still holds D by about 1.14. The 09:53 minute
first breaks D and the original 79,925.0756 stop, producing model net -$762.75.
Later 09:55 lows and the 10:00-known full fifteen-minute close cannot be used
to alter earlier execution. The eight-minute label is a difference between
minute interval starts; exact seconds are not verified. The 0.25-ATR buffer
is about $78.78 of the $730.63 price risk; most distance is from D to entry.

The read-only audit preserves seven complete fifteen-minute aggregates and
all 105 real one-minute rows, distinct occurrence/confirmation times, and an
independent ATR check from 300 earlier real minutes. No strategy, numerical
parameter, latest pointer, monthly result or workbook was changed. See
``docs/investigations/2026-11-08_BTC_TRADE5_B1_BAR_AUDIT.md``.

Current: independent failed-rebound exit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The owner explicitly approved an independent exit after reviewing the five
losses exceeding $500 in ``20261109T034016Z-30-ab``. A post-entry 15m swing
H, confirmed pullback L and confirmed lower high LH activate a strict
break-below-L exit of the actual remainder. Existing complete left/right
neighbours confirm each turn. LH is not actionable before its right neighbour
finishes. No new-high, initial-1R, dollar or ATR-size gate is added. This is
separate from hard-stop trailing; entry, initial stop, T1 25% and costs remain.

Reclaim above LH invalidates the combination. Incomplete/missing observations
clear unconfirmed construction. A reference fully confirmed before a gap
remains usable on subsequent observed prices with an explicit unknown-gap-path
flag; no missing price is filled. Opening breaks use the observed open;
otherwise strict within-minute breaks use L with ordering uncertainty flagged.
At the same observation, hard stop and existing structural protection precede
failed rebound, then other active exits and target. Known openings precede
unresolved intraminute ranges.

The factory now uses ``FailedReboundReplay`` / draft-8. Explicit
``turning_consumed_v7`` preserves the prior lifecycle and V5 exits for historical
audits. Fixed-entry controls change losses #11 from -$700.09 to -$327.60,
#12 from -$509.86 to -$395.54 (gap exposed), #23 from -$1,160.16 to -$482.78,
and #32 from -$990.82 to -$732.67. #5 remains -$762.75 because it stops in eight
minutes before a complete failure pattern. $500 is a review filter, not a
new risk limit or sizing change.

Same-source run ``20261109T041525Z-30-ab`` retains 38 entries, 19 wins and
19 losses. Net P/L per initial 1 BTC is +$3,516.46 versus +$2,214.63, net
+6.905525R and maximum R drawdown 3.179710R. All eight changed exits are shown,
including profitable #13 reducing from +$1,332.64 to +$857.61. #5/#32 remain
over $500. No threshold search, actual orders or independent profitability claim.

The desk and eight-sheet workbook include fixed-old-entry controls separately
from sequential results, H/L/LH occurrence, confirmation and activation times,
break references and gross/cost/net. Chronological partial candles show actual
observation end and minute coverage. ``LARGE_LOSS_REVIEW.csv`` is downloadable.
All older result/workbook hashes remain preserved. See
``docs/investigations/2026-11-08_BTC_LARGE_LOSSES_FAILED_REBOUND.md``.

Current: consumed entry history and complete loss audit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The original B2 trade #2 reused trade #1's 08:30 shock and 09:26 D after the
first trade had closed. Deduplication by route/D/HL allowed the same episode
to buy again under a different branch or HL. The current factory now consumes
all A/B setup history after each entry, rebuilding only from complete candles
starting after the entry candle. A 09:33 entry starts fresh structure at 09:45;
the mixed 09:30 candle cannot be reintroduced. Actual price history, ATR,
resistance and existing position protection remain intact. Unfilled signals
do not consume structure. Explicit ``turning_v5`` retains the historical
pre-consumption lifecycle; ``current`` uses draft-7.

All 27 original losses were checked against real minute data. Nineteen have
old-sequence structure origins preceding the previous entry's fresh-history
boundary. Three have positive gross P/L turned negative by real model costs;
the categories overlap. Their stop, structure and last-minute turning exits
pass independent observation checks, with no earlier qualified active exit
found and ignored. Numeric stop, target, exit and cost parameters are unchanged.

Run ``20261109T034016Z-30-ab`` uses the identical source hash and date window:
56 signals, 38 closed trades, 19 wins/19 losses, 50% win rate, fixed-1-BTC
net **+$2,214.63**, net +5.505690R, maximum R drawdown 3.935983R, no open
positions. Twenty-one original losing entries disappear and six retain their
entry. The changed sequence also introduces different trades; do not simply
add back avoided losses. All 19 corrected losses are audited as well, without
stale history or exit violations. Eighteen show less than initial 1R maximum
favourable excursion on the identifiable completed-minute path, excluding
uncertain execution-minute high/low ordering.

The desk and eight-sheet workbook show old/new IDs and per-loss causes,
gross/cost/net, observed MFE/MAE, exit evidence and sequential disposition.
``LOSS_REVIEW.csv`` is downloadable. Old results/workbooks are preserved and
the old 44-trade record is flagged as containing invalid entries. Gap-exposed
corrected trades are #12/#22; all 558 missing minutes remain missing. This
is an in-sample correction, not independently validated profitability. No
broker orders. See ``docs/investigations/2026-11-08_BTC_ALL_LOSING_TRADES_REVIEW.md``.

Approved thirty-day replay
~~~~~~~~~~~~~~~~~~~~~~~~~~

The historical pre-consumption replay, subsequently found to contain stale
entries, remains preserved for comparison. Run
``20261109T030906Z-30-ab`` covers October 9 20:00 EDT through November 8
19:00 EST (exclusive), using the approved A/B1/B2 entries and V5 exits.
Numerical parameters are unchanged. B1 buys the first stabilization breakout
after a rapid decline; B2 requires rebound and HL. Missing B1 HL remains blank.
The monthly runner now opts into these branches; pinned historical case
factories keep their original entry default.

The same real source snapshot has 89 signals, 79 eligible candidates and 44
closed trades: 17 wins, 27 losses, 38.6% win rate. Fixed-initial-1-BTC net P/L
is **-$1,253.88** after unchanged 2bps friction each side. Net R is +1.638264R
and maximum R-sequence drawdown 3.592053R. These metrics weight different
initial risks differently; positive total R does not make fixed-size dollars
profitable. There are no open positions at the cutoff.

Eight trades reach the first target and exit 25%/75%; 36 exit 100% before T1.
Forty-three protection raises distinguish larger hard stops from confirmed
fifteen-minute structural references. All initial stops activate at the
assumed entry, not before it. No fixed second target is active.

The seven-sheet workbook lists entry, initial stop/effectiveness, first-25%
time/price/net and actual-remainder fraction/time/price/net together. Protection
changes and all fifteen-minute observations remain separately auditable.
``PROTECTION.csv`` joins the existing signal, trade, exit and ledger exports.
UTC columns accompany New York dates across the daylight-saving transition.
The UI shows full-run dollar P/L alongside R and a saved baseline comparison.

All old result/workbook/input hashes are preserved in ``COMPARISON.json``.
Baseline ``20261109T002127Z-30-ab`` remains -$3,691.76 / -8.764537R with one
open position. Both entry branches and exits have previously approved changes;
do not attribute the combined difference only to exits. The 558 absent
minutes remain absent, and gap-exposed trades #21/#25 are conditional estimates.
No live or paper order was submitted. See
``docs/investigations/2026-11-08_BTC_APPROVED_RULES_30_DAY_RETEST.md``.

Retained V5: new-high-failure exit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The pinned V5 replay uses TurningABReplay. At the final minute's
opening observation, the current candle must have made a new wave high, the
previous complete candle must be bullish, current price must be below its
full-range midpoint and below the current open (red), not above previous close,
and neither current body nor observed range may be inside that previous bar.
Only fourteen completed minutes plus current opening are used. No current
minute H/L/C or eventual fifteen-minute close is read early.

This retracement of the prior bullish candle's range is distinct from the
retained initial-1R/50%-of-total-profit guard. Hard protection, confirmed
structure and wick exits remain; T1 still sells 25%, T2 is disabled and midpoint
crossing alone only warns. At the same opening observation, priority is hard
stop, structure, profit guard, new-high failure, wick, then target.

The nominated evening position keeps the 22:57 first target (+$383.02 net),
then exits remaining 75% at October 13 04:29 / 83,835.33 (+$1,803.78 net), total
+$2,186.80 per initial BTC after original costs. This is the 04:15--04:30 candle,
not a sale at its 04:15 high. Its local retracement at observation is 76.28%.
The earlier 01:44 observation is rejected because that current candle did not
make a new wave high. The fixed morning regression remains +$218.90.

Historical audits explicitly select guarded_v4; their strategy modules and
04:50 continuation result remain unchanged. Current results are saved separately
and shown by the saved-case endpoint. That earlier case-only pass did not
rerun a month, overwrite the latest pointer or submit orders; the subsequent
authorized month is documented above. See
``docs/investigations/2026-11-08_BTC_OCT12_APPROVED_TURNING_EXIT.md``.

Retained V4 profit protection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The historical V4 factory explicitly selects GuardedABReplay. Maximum favourable
excursion must reach the original initial 1R, profit giveback must be >= 50%,
current price must be <= current fifteen-minute open AND <= preceding complete
close, and neither current body nor observed full range may be inside that
previous candle. All conditions must pass at an actual one-minute opening
observation. Equal-to-open is non-green; equal-to-previous-close is permitted.
Current minute H/L/C and final fifteen-minute colour are not used early.

Initial R remains entry minus initial stop; partial sales and protective raises
do not rebase it. Peaks use completed post-entry minutes, excluding entry-minute
high due to unresolved pre/post-entry ordering. Missing complete previous or
prefix minutes withhold the guard, never original hard protection. This is
minute-sampled research, not exact tick timing or verified ETF fills.

T1 retains its 25% sale, midpoint crossings only warn, and fixed T2 is disabled.
Confirmed 15m structure, last-minute wick and hard protection remain active.
Shared candidate ordering preserves known opening events before unresolved
minute ranges and closes only remaining quantity. An early protective exit
before T1 closes 100%; after T1 it closes 75%, without inventing a target leg.

Only the two October 12 nominated entries were replayed using this shared
factory. Morning: 25% at 10:11 / 83,029.163077857, then 75% at 10:19 /
82,754.706, combined net +$218.90 per initial BTC. Evening: 25% at 22:57 /
82,962.195014889, realized net +$383.02; 75% remains open through October 13
01:45 EDT. Remaining unrealized P/L is separately labeled, without cutoff
liquidation. Costs and original entry/stop/T1 parameters are unchanged.

The latest saved-case panel shows the approved policy; prior V1/V2/V3 and
hypothesis studies remain historical comparisons. Future explicitly started
A/B studies use the current policy, but no month was rerun here and no stored
month/latest pointer was replaced. No paper/live order was submitted. See
``docs/investigations/2026-11-08_BTC_OCT12_APPROVED_PROFIT_GUARD.md``.

Historical giveback hypotheses before approval
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A new saved comparison aligns the October 12 morning and evening cases candle
by candle. It tests one declared, unoptimized numeric pair: maximum favourable
excursion >= 1 initial R, followed by half-profit giveback. Initial R is the
original entry-to-stop distance times initial quantity, not a risk measure
rebased after partial sales. Optional direction/inside conditions and final-minute
sampling are compared explicitly, without searching threshold values.

The simple minute-open candidate exits morning at 10:06 / 82,752.0485, net
+$147.64, but overrides the inside-candle preference and is followed by recovery.
Preserving direction and inside exemptions gives 10:19 / 82,754.706 on remaining
75%, after the unchanged 10:11 target; combined net +$218.90. Checking those
same conditions only in the last minute exits at 10:44, net +$101.27. The 10:15
candle later closes green, so an intrabar protection event cannot be described
as proof of a final bearish candle or trend reversal.

Every evening variant retains 75% through October 13 01:45 after its original
25% target. Its maximum activated minute-opening giveback is 25.13%; a
conservative intraminute H/L envelope is 29.50%, with ordering explicitly
unknown and no fills invented from that envelope. Existing case results,
monthly defaults and run pointers remain intact. The desk reads saved JSON
only; chronological CSV/Markdown include all twenty-five candles and the
confirmation tradeoffs. No month was rerun and no orders were generated.
See ``docs/investigations/2026-11-08_BTC_OCT12_GIVEBACK_COMPARISON.md``.

Latest single-case revision: warning and structural remainder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The October 12 evening case now has an explicit opt-in research branch:
midpoint crossings warn only; unchanged T1 takes 25%, while fixed T2 is disabled.
The remainder exits on a confirmed fifteen-minute structure break. A candidate
higher low must lie below both complete adjacent lows and above the retained
reference; a later complete bar must exceed the rally high before that pullback.
Only then can the reference activate. Its strict intrabar break exits the
current remainder. Original hard-stop and cost parameters are unchanged.

Full-range or body-contained candles do not independently trigger a shape exit;
containment never overrides a genuine structure break or hard stop. Last-minute
wicks retain trigger-time non-green and previous-close direction filters. No
new small-body threshold or stop buffer is introduced, and final candle colours
are not read before their availability.

Only this entry was reviewed through October 13 01:45 EDT. T1 sells 25% at
22:57 / 82,962.195014889, realized net +$383.02 per initial BTC. Structure
references activate at 23:00 / 82,578.695, 23:45 / 82,677.245, 01:15 / 83,153.77,
and 01:30 / 83,285.235. The 01:40 break of the preceding candle's 83,508.87 low
is not a confirmed swing break. Remaining 75% stays open at the review cutoff.
Its last observed close is 83,488.2935: gross unrealized +$1,568.29, or +$1,556.08
after allocated entry friction. Hypothetical two-sided-cost valuation is
+$1,543.55 on that remainder; none of it is realized sale proceeds.

A read-only profit-giveback diagnostic uses (known peak minus reference price)
/ (known peak minus entry), with no new exit threshold. At prior V2 checkpoints,
morning 10:05 gives 47.55% / 0.728 initial R versus evening 22:31 at 7.57% /
0.192R. Morning peak known then is only 82,950; do not use the unfinished 15m
candle's later 83,040.768 high. Both entries remain B1; later holding behaviour
cannot retroactively classify their entry. This ratio is unstable with very
small favourable excursion and does not establish predictive profitability.

The latest-case panel reads ``GET /api/btc-lab/structure-case``; chronological
JSON/CSV are saved separately. No cutoff liquidation, new month, broker order,
or change to monthly defaults is performed. V1/V2, morning and monthly results
remain historical records. See
``docs/investigations/2026-11-08_BTC_OCT12_STRUCTURE_EXIT.md``.

Historical V2: direction filters on both active exits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Current A/B replay uses V2: intrabar midpoint and last-minute upper-wick exits
both require observation price <= current fifteen-minute open AND <= previous
complete fifteen-minute close. Equality is allowed: equal to open is neutral,
not green. Neither waits for the current candle's final close. Missing true
opening or complete previous-bar data withholds active exits, never the
protective stop. If the midpoint was crossed before direction gates pass, wait
and use the newly eligible reference price, never the earlier higher midpoint.

Midpoints still arm only for the next bar after a completed post-entry new high.
Wicks still use fourteen completed minutes plus the last minute's opening
observation, with >=50%, new-high and above-entry gates, without an integer gate.
Known openings precede unresolved H/L; ambiguous range ties retain stop >
midpoint > target risk priority and explicit flags. Current remainder exits
once, without same-minute reentry. Protective stops, targets, 25%/75% sizes,
entry parameters and costs are unchanged.

Only two fixed October 12 entries were replayed, New York EDT. Morning 09:33
entry exits fully at 10:05--10:06 / 82,769.94775, net +$165.53 per initial BTC.
Evening 21:00 entry does not exit on the 22:29 wick: 82,637.30 is below its
15m open but above previous close 82,627.021. The 22:30 opening is also above
the preceding close, and that minute does not reach it. At 22:31--22:32, crossing
82,655.0085 meets all gates; full-exit net is +$1,224.95. Both exits precede T1;
there are no partial target legs or stop raises. Final candle color cannot
retroactively veto a valid non-green observation earlier in that candle.

The desk's read-only saved-case panel shows V2 and compares V1 and original
historical paths. V1 remains available through ``exit_policy='approved_v1'``;
``legacy`` and the frozen Replay preserve original studies. No old case,
monthly result or latest_run is overwritten; no month or order was run. See
``docs/investigations/2026-11-08_BTC_OCT12_DIRECTION_FILTERED_EXITS.md``.

October 12 morning protective and active-exit audit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The original parent-low rule permits no stop raise during the morning holding
interval; selling 25% does not automatically move the stop to breakeven.
The approved manual midpoint exit nevertheless occurs at 10:05, before the
first target at 10:11. It conditionally closes 100% at 82,769.94775, netting
+$165.53 per initial BTC after unchanged costs. A later 10:14 upper wick of
54.18% is a conditional event after that earlier full exit. Combining the
original 25% target leg with a remaining-75% wick exit would instead net
+$286.36; these are independent paths, not additive returns.

The frozen webpage lacks midpoint exits and rejects the 10:14 wick through
its historical integer gate, explaining its original -$104.11. No engine,
parameters, existing case or monthly result is changed by this audit. See
``docs/investigations/2026-11-08_BTC_OCT12_MORNING_EXIT_REVIEW.md``.

B1/B2 opt-in two-case preview
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The explicit ``expanded_b=True`` research option separates first stabilization
breakouts (B1, no HL claimed) from completed rebound/HL retests (B2). Before the
first completed bullish rebound holds D, completed lower-low bars may extend
that same impulse's D without each needing another 2-ATR decline. Unknown
current-bar lows cannot be used. An already-open stop never moves down with
these preparation references. After that full rebound, a broken D invalidates
the episode. The monthly default and saved result pointer remain unchanged.

Only the nominated October 12 09:30/21:00 examples were reviewed: entries occur
at 09:33/21:00. The morning 25% target followed by a 75% stop nets -$104.11;
the evening 25%/75% targets net +$1,833.70 per initial BTC after unchanged
friction. Neither position has a qualified stop raise. Subsequent B2 signals
at 10:31/22:53 do not add exposure to the held B1 positions. No month rerun or
orders. See ``docs/investigations/2026-11-08_BTC_OCT12_B1_B2_CASES.md``.

Historical entry-only A/B replay
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The retained baseline runs ``Alpaca-BTC-AB-entry-positive-net-draft-2``. Route A counts
four or more independent declining LL/LH phases, then HH/HL and local breakout.
Route B uses the completed bearish new-low impulse at least twice pre-drop
ATR14, a complete rebound, HL and local breakout. Both trigger intrabar above
the prior complete fifteen-minute full high. The new mechanical detector uses
one completed left/right neighbour, retains nested scopes and selects the
widest structurally eligible origin. It is not yet validated as equivalent to
human wave ranking: November 7 has five mechanical phases versus four larger
owner-marked phases.

The owner's latest policy makes **2R advisory**, requiring strictly positive
known net target reward after the unchanged 2bps friction each way. Unknown
targets still withhold qualification. Later realized winners are never used
to select earlier entries. Stop buffers, target selection and exit methods
inherit the existing webpage draft-3 behavior, including its historical $1,000
wick gate. The later manual midpoint/no-round-gate exits are not included in
this entry-only replay.

The 30-day run contains 62 deduplicated signals, 51 qualified candidates,
21 entries, 20 closed (7 wins/13 losses, -8.764537R) and one open position.
It retains 37 below-2R warnings, nine missing targets and two failed structure/
price checks. The test has 42,642 observed minutes, 558 absent minutes and
2,880 aggregates with visible coverage. Source hashes are retained; nothing is
interpolated. The page filters routes and qualification, shows setup evidence,
and exports all signals, trades, exits and bars as CSV. The reviewed six-sheet
workbook is downloadable as XLSX. Existing runs remain independently viewable;
there is no broker or order execution. See
``docs/investigations/2026-11-08_BTC_AB_30_DAY_RETEST.md``.

Archived standalone case audits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following historical reviews predate integration and preserve their original
strict-2R judgments. They do not describe the current qualification policy.

Two independent research entry routes are now defined in
``docs/BTC_ENTRY_RULES.md``. Route A requires four independent lower-low phases
with intervening lower highs, then a higher high, a higher low and a local
breakout. Route B instead requires a completed bearish new-low fifteen-minute
impulse with downward excursion ``max(open, previous close) - low`` at least
twice the prior fourteen completed bars' ATR, a completed bullish rebound,
and a higher pullback low. The 2-ATR shock threshold is an explicit unoptimized
draft. Route B does not require four lows or an initial rebound-peak reclaim.

Both trigger intrabar above the previous completed fifteen-minute candle's
full high and retain the original parent-D stop, ATR buffers, chase ceiling,
2bps friction each way, net-2R screen and exit rules. Structure/price signals
are separate from qualified candidates. The November 7 21:58 A signal and
November 8 17:58 B signal pass structure/price but independently fail net 2R
at about 1.8068R and 1.6323R. The latter's shock is in 16:45--17:00, not 16:15;
its 17:45 candle closes below the trigger despite its actual intrabar breakout.

The independent validators consume reviewed structure facts and causal
known-at times, not a validated automatic wave-ranking detector. They do not
update the frozen monthly engine, webpage replay button or broker. No full
month was rerun. The November 8 case uses 630 real Alpaca minutes, excluding
the endpoint partial minute, with raw responses and hashes retained separately
from shared caches. See
``docs/investigations/2026-11-08_BTC_1745_SHOCK_ENTRY_REVIEW.md``.

The November 8 follow-up reviews only trades #23/#24/#25 and November 7 21:30.
The owner rejected replacing a larger parent D with an internal pullback and
rejected the automatic $1,000 wick gate. A next-bar price below the previous
completed new-high candle's full-range midpoint is now a separately approved
full remaining-position exit. It is not restricted to the last-minute window.
In this review a new high must exceed the retained setup parent H1, so tiny
internal highs do not qualify. Later signals are explicitly conditional after
any earlier exit; #23's nominated 07:30 candle crosses the midpoint at 07:32,
but a shape-only wick exit is already visible at 04:29. Trade #24 has a 04:02
midpoint event before its 04:14 wick. Trade #25 still stops, and the 21:30
candidate still lacks an own-feed breakout and 2R. Trade #23's initial D was
already undercut before entry, so exit examples do not prove full entry eligibility.

These changes are audited cases, not an updated production/replay-button engine
or a new monthly result. The frozen draft-3 implementation below is retained
for comparison. See
``docs/investigations/2026-11-08_BTC_FOUR_CASE_HIERARCHY_REVIEW.md``.

The owner's subsequent chart annotation corrects our mistaken count reset at
internal rebound peaks. The full decline starts at November 7 04:00 and contains
four independent low phases at 06:15, 07:30, 10:45 and 16:30. Both providers have
completed rebound evidence known by 17:00; the four-low gate passes. Alpaca's
second phase minimum is in the 07:45 candle, while Coinbase's is in the annotated
07:30 candle. These are one phase per provider, not extra or missing waves.

The owner confirmed lower lows and lower rebound highs on the fifteen-minute
frame. The first three rebound highs decrease, but the fourth exceeds the prior
rebound high, so label it HH/structure strengthening. Do not force it into an LH
label or confuse it with breaking the whole decline's initial high. A later HL
and price breakout are separate entry evidence. Thirty-minute/hourly comparisons
remain future research, not a timeframe change to obtain a desired signal.

The 21:45 bar contains the price breakout at 21:58, which the frozen
immediate-fresh-L2 test loses. The four-wave condition now passes; the unchanged
net-2R screen independently fails. The earlier count-of-two conclusion is
superseded because it used the wrong cycle scope. These are annotated cases,
not a general automated detector, monthly rerun or engine rollout.

A subsequent single-position timeline assumes the November 7 21:58 entry at
75,655.545 solely for a holding-path exercise; the net-2R qualification failure
is retained. Initial protection is 75,444.876375 with no qualified stop raises
before exit. A causal 22:59 opening observation shows a 70.55% upper wick and
closes all remaining exposure at the 75,779.12 reference. Per initial BTC, gross
P/L is $123.575 and net after 2bps each way is $93.288067. The first target was
not touched, so there are no 25%/75% target legs. The tiny $0.866 new high is
counted under the existing rule, not filtered retrospectively. Later protection
changes do not belong to this already closed path. This is a conditional audit,
not a qualified strategy trade, actual fill or monthly rerun. See
``docs/investigations/2026-11-08_BTC_2145_ENTRY_TIMELINE.md``.

The local desk now includes ``/btc-lab``: a chronological fifteen-minute ledger,
real-data chart, known-at-time L1/L2 references, minute-interval entry/exit events,
stop activation times, rejection reasons and per-initial-BTC P/L. The homepage and
sector board both link to it. Explicit buttons update history and start separate
30/90/365-day or all-history studies; opening the page starts no network job.

The frozen Alpaca US BTC/USD archive contains 2,741,551 real source records from
January 1, 2021 06:00 UTC through November 8, 2026 19:14 UTC, with 336,524 absent
minutes across its span and 1,160,610 zero-volume records. Provider crypto bars
may use quote midprices. Missing minutes remain absent, aggregates show coverage,
and exposed trades are flagged. No-flagged-gap subset metrics do not certify all
earlier resistance context. The mechanical draft's 30-day sequence is 25 trades,
5 wins/20 losses, -10.0017R; all-history after warmup is 1,060 trades, -104.6770R.
These negative conditional observations remain visible, not optimized away.

Mechanical previous-D/parent-low and confirmed four-hour target selection are
explicit research approximations, not proven equivalence to the manual examples.
The nearest lower $1,000 watch level is a declared proxy for a manually drawn
resistance, needing review. Study BTC signals around the clock with the owner's
ETF zero-commission plus 2bps each-way spread/slippage assumption. These are not
ETF actual returns or broker fills. Normal targets retain 25%/75%, protective and
last-minute rejection exits close all remaining shares. See
``docs/BTC_RESEARCH_DESK.md`` for exact algorithms, gaps, source provenance and
run IDs. The frozen Coinbase month and teaching examples remain unchanged.

The latest handbook revision consolidates the November 7 trade into one dated
timeline. The owner confirmed the initial support anchor is the previous D,
the November 7 16:30--16:45 low of $75,452.88. With the unchanged pre-entry ATR
and 0.25 buffer, the illustrative initial stop is $75,436.62 rather than
$75,529.08. Entry remains within November 7 21:30--21:45 New York time at the
$75,650 arithmetic reference. Keeping the entry L2 as the starting point for
later new-low qualification retains the reviewed 03:00 and 07:00 upgrades to
$75,640.70 and $75,674.10. The wider initial risk gives about 1.80 net R at the
unchanged fixed target and friction, below the existing 2R entry gate.

Ordinary target profits remain staged 25%/75%, but a near-end intrabar
upper-wick rejection now exits all remaining shares immediately rather than
waiting for the fifteen-minute close. The owner fixed that window to the last
minute, 08:29:00--08:30:00 exclusive. Fifteen real Coinbase one-minute candles
reproduce the archived parent OHLCV exactly. At the 08:29 minute's first trade
of $75,955.04, the prior fourteen completed minutes already establish a 52.84%
upper wick and a price below $76,000. The current minute's final H/L/C and the
next minute's open are not used. Per initial BTC, the full-exit model grosses
$305.04 and nets $274.72 after the unchanged 2bps each way. The minute timestamp
does not establish the precise trade second or an actual order fill.
See ``docs/investigations/2026-11-08_BTC_LAST_MINUTE_REVIEW.md`` and the current
unified table in ``docs/TRADING_LEARNING_MANUAL.md``. The owner prefers Alpaca
data and paper execution for subsequent studies; read-only readiness is verified,
but no orders were submitted. Crypto fees and ETF cost assumptions remain separate.
Earlier cases below remain historical comparisons, and the Coinbase month is unchanged.

The owner's subsequent learning-rule revision takes 25% of the initial position
at the first target and retains 75%. A partial profit does not move the initial
stop: only a new high permits recalculating structural protection, which must
never be lowered. For the October 11 teaching example the initial stop remains
$82,865. In this single-case audit, a new high is an intrabar break of the
previous wave peak, starting with the first-target candle high of $83,904.73.
Use the lowest completed candle between that peak candle and the next breakout
candle, minus the existing 0.25 ATR buffer; ATR must be known at breakout-bar
start. Changed protection takes effect next candle, avoiding assumed intrabar
ordering. This is a declared audit convention, not parameter optimization.

The first-target interval remains 11:45--12:00 New York time. New highs during
12:30--12:45 and 13:30--13:45 permit using pullback lows $83,630 and $83,658.11.
Stops become $83,594.76 at 12:45 and $83,613.65 at 13:45. There is no further new
high, so the small 14:00 pullback cannot raise the stop. The remaining 75%
conditionally exits during 14:45--15:00 at the $83,613.65 model reference,
with actual fills and exact seconds unverified. This independently reproduces
the old exit interval but uses a different stop and fraction. It still does not
pass the unchanged net-2R entry screen. This revision has not been applied to
the monthly workbook. See
``docs/investigations/2026-11-08_BTC_OCT11_STRUCTURE_CLARIFICATION.md``.

The November 7 example is now audited separately with the same larger-wave
target selection, explicitly chosen by the owner instead of the earlier
$75,990 classroom target. The 16:30 L1 is $75,452.88; the 21:15 candidate L2
is $75,545.34. An intrabar break during 21:30--21:45 gives an arithmetic entry
reference of $75,650 and an initial stop reference of $75,529.08.
The owner clarified two distinct rules: profit-taking remains 25%/75%, while
a protective exit closes all shares still held at once (100% before the first
profit, 75% afterward). New-wave-high trailing starts after entry and does not
require a prior target sale. The temporary interpretations of target-gated
trailing or full-position target sales are superseded.

The known larger zone yields T1 $76,118.18, which is not reached during this
trade. The 22:00 new high proposes a lower stop, which is rejected. The 23:15
new high uses the completed 22:30 pullback low $75,704.58 and pre-breakout ATR
70.5028571; protection becomes $75,686.95429 at 23:30. During November 8
01:00--01:15, that stop closes the whole 100% before the first target.
Per one initial BTC, conditional gross P/L is $36.95; assumed round-trip
friction of two basis points each way is $30.27, leaving $6.69 net. It is one
protective exit, not separate 25% and 75% fills. Later chart highs are outside
this closed trade. These are model references, not observed ETF fills.
All 74 real candles, timestamps and distinctions are recorded in
``docs/investigations/2026-11-08_BTC_NOV07_STRUCTURE_CLARIFICATION.md``.
The October example, old source audit and monthly workbook remain unchanged;
the new entry-time trailing clarification is not retroactively replayed there.

A further, separate November 7 review applies the owner's same-level hourly
pivot definition. A replacement low must have a completed right-hand hour,
exceed the protected low, and be followed by an observed intrabar break of the
preceding confirmed hourly peak. Both confirmations must be available before
the stop changes. The existing 0.25 fifteen-minute ATR buffer and two-basis-point
friction each way are unchanged. Stops become $75,640.70 at 03:00 and $75,674.10
at 07:00. This stop-only case never reaches $76,118.18 or its active stop before
the archive ends at 11:00, so it remains open rather than producing staged exits.

The 08:15--08:30 upper-wick rejection is evaluated as an additional, explicitly
new early-exit candidate at the manual's $76,000 watch level. A prior close
above the level, a new high, at least 50% upper wick and a close back below
the level trim 25% next actual open ($75,956.20 at 08:30). An intrabar break of
that completed signal candle's low exits the remaining 75% ($75,944.77 model
reference during 08:30--08:45). The signal is not fully known at 08:15, and
neither price is a verified fill. The two modeled legs net $68.97 and $198.34
per initial BTC. The $267.31 total is in-sample and includes both the parent-stop
change and the additional early-exit clause; it cannot be attributed to the stop
change alone or mixed with the old full-position wick-failure convention.
Detailed comparison, all 54 active-window bars and timing provenance are in
``docs/investigations/2026-11-08_BTC_NOV07_PARENT_SWING_REVIEW.md``. Earlier audits
and the monthly workbook are preserved, and no real orders are routed.

The primary workbook now includes the owner's requested V1.2 important-swing
revision. It uses completed hourly peaks, two hours of confirmation on each
side, at least one hourly ATR of rise and decline, and merged zones of
plus/minus 0.15 hourly ATR. All other entry, stop and 2R requirements remain
unchanged. The original V1.1 result described below is retained as history.

Across the same 114 original signals, 14 pass the revised 2bps price screen.
With one position at a time, ten model trades close: one win and nine losses,
for -6.719R in total. Four independent passes occur during an existing position.
These results remain in-sample and do not validate profitability. The XLSX
preserves old and new targets and adds trade-by-trade exit legs. No real orders
are created. Reproduce this update with:

.. code-block:: bash

   python3 scripts/retest_btc_major_resistance.py
   python3 -m pytest trading_desk/tests/test_btc_structure_retest.py -q
   node scripts/update_btc_major_workbook.mjs

The November 8 study uses completed Coinbase BTC-USD fifteen-minute bars around
the clock, as requested by the owner. It records 2,880 complete test bars from
October 9 at 16:00 UTC through November 8 at 16:00 UTC (exclusive), plus seven
warmup days. No missing bars were interpolated or carried forward.

V1.1 quantifies the learning manual's unfinished higher-low, buffer, expiration
and resistance choices. It is a mechanical interpretation, not validation of
the complete discretionary method. In particular, treating every confirmed
local high over seven days as resistance may be overly restrictive; no one-hour
trend filter or optional acceleration exit is tested.

All 114 completed breakout candidates fail the two-times net reward/risk screen
at zero, two or five basis points of assumed friction per side. There are no
entries. Win rate, trading profit and the staged exit method cannot be evaluated
from this run. It is not ETF realized performance and creates no orders.

Review and reproduction
-----------------------

The repository's ``docs/BTC_STRUCTURE_RETEST.md`` contains the exact rule,
causal timing, execution assumptions, current-chart references and limitations.
The spreadsheet and request provenance are stored under
``reports/btc_structure_2026_11_08/``. Its five sheets cover the summary,
candidates, current candle audit, parameters and original observations.

Editable spreadsheet costs and minimum reward/risk recalculate screening, but
do not rerun structural identification or create historical fills. The workbook
is a dated snapshot, not an automatic refresh or trading agent.

.. code-block:: bash

   python3 scripts/btc_structure_retest.py --as-of 2026-11-08T16:00:00Z --days 30 --output reports/btc_structure_2026_11_08
   python3 -m pytest trading_desk/tests/test_btc_structure_retest.py -q
   node scripts/build_btc_retest_workbook.mjs

The scripts never import broker order clients. Missing source observations are
reported, never synthesized. A real ETF study must separately model its own
quotes, market hours and spread/slippage despite applicable zero commissions.
