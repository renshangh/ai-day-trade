E3 draft one fixed entry review
===============================

Quantified rapid-drop exit research on one open case and nine saved winners.

:Last Updated: 2026-11-15
:Status: Ten-case review complete; not promoted or installed in a live model
:Audience: Trading Desk owner and maintainers

Overview
--------

The independent report at
``reports/btc_e3_draft1_2026_11_15/REPORT.html`` contains ten fixed-entry
comparisons and 888 chronological five-minute-pair rows. Frozen 0.2, the
original live worker, PH5 and retained-parent study results/selectors are
unchanged. No month was rerun and no new entries or reentries were added.

Definition locked before evaluation
-----------------------------------

H is the entry-time confirmed fifteen-minute HL, fixed for the trade.
A and B are adjacent complete five-minute bars starting after the entry's
five-minute interval. The draft requires all of the following:

* A.open minus B.close is at least one ATR. Use the original fifteen-minute
  ATR known before A starts and freeze it for the entire ten-minute pair.
* A closes strictly below H.
* B's entire high and close remain strictly below H, so the following
  five-minute candle never reclaims support, even by its wick.
* B closes red, no higher than A's close, and neither its range nor body
  is inside A.

After B completes, the hypothetical exit waits sixty seconds and uses the
exact observed one-minute opening at that time. It sells only the then
remaining position. Original earlier/same-minute exits retain priority;
earlier 25% legs remain. Missing pairs or execution observations are not
filled, carried forward or moved to a later price. A later fresh window
can qualify independently. Stop/target formulas and the original two-bps
per-side cost proxy remain unchanged.

For the live-prefix case, actual input receipts must precede the selected
execution reference. Monthly observations lack contemporaneous delivery
timestamps, so the sixty-second wait is a model assumption rather than
verified historical latency. Reference prices are not broker fills.

Results
-------

The November 15 01:44 EST case confirms E3 at 02:45, with a 02:46 modeled
exit reference of $63,836.8905. Its hypothetical net is -$628.91 per initial
BTC. The original position remains open at the historical 05:16 cutoff;
its last observed 05:15 mark is +$1,088.99 net unrealized value. The
same-cutoff marked difference is -$1,717.90, not a comparison with realized
original profit.

Among the nine previously identified winners, E3 triggers on retained-parent
0.1 trades 33, 39 and 40 and changes each to a loss. Their nine-trade saved
net total falls from $4,087.83 to $354.92, a difference of -$3,732.91.
The other six do not trigger under available observations; trade 114 retains
its original gap/partial-context flag. This deliberately selected winner
cohort cannot estimate overall E3 win rate or monthly profitability.

The thresholds were not adjusted after seeing these results. Fixed entries
exclude potential new buys after an earlier exit, including any hypothetical
03:20 reentry. Do not treat the sample difference as a full-sequence result.

Artifacts and checks
--------------------

``LOCKED_RULE.json`` preserves the initial definition and sample IDs.
``COMPARISON.csv`` lists every signal, execution reference and P/L change;
``BAR_TRACE.csv`` and ``RESULT.json`` retain all completed/incomplete windows
and failed gates. Post-E3 rows describe the original holding path for review,
not additional E3 sales. ``ACTUAL_INPUTS.json.gz`` contains the real archived
observations needed to reproduce the sample check.

Engineering notes are in
``docs/investigations/2026-11-15_BTC_E3_DRAFT1_TEN_CASE_REVIEW.md``.
Regression checks cover strict prefixes, frozen pre-window ATR, delayed
receipts, missing execution minutes, original-exit priority, real winners
cut to losses and unchanged partial-sale paths. No broker API is loaded.
