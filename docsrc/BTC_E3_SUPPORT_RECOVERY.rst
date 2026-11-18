E3 Support Failure and Recovery Review
======================================

This four-case historical review explains why an entry-time local higher low
can fail while the saved larger parent D remains intact. It does not change
the strategy, E3 draft one, frozen release 0.2, or the live worker.

Support levels and information timing
-------------------------------------

The local HL and larger parent D are the original references recorded at
entry. Both can come from fifteen-minute candles while belonging to different
wave levels. The audit never promotes a later small low to parent support.
The three October examples retain the October 15 parent at 79,691.8665;
the November 15 01:44 example retains the November 14 parent at 61,991.3285.

Actual observations form complete five- and fifteen-minute candles. Partial
edge candles remain marked partial and cannot confirm a pivot. The existing
strict three-candle pivot convention excludes turns that are simultaneously
strict highs and lows against both adjacent candles. A candle outside its
left neighbour alone is not automatically excluded.

An unfinished candle is never used as completed evidence. The live historical
prefix also checks exact observed delivery timestamps, retaining sub-second
precision. Candle completion, input delivery and actual strategy processing
are distinct; delivery does not establish execution or broker fills.

Findings
--------

* All four local HLs genuinely failed. All four original parent Ds remained
  intact. At E3 confirmation, the parent was approximately 6.8 to 10.1 prior
  ATRs below the signal close, so retaining that background permits substantial
  adverse movement.
* Trade 33 continued lower before recovering. A later original H-L-LH
  reference became armed, but its low was not broken afterward.
* Trade 39 recovered quickly, although its first one-minute reclaim was not
  yet a completed five- or fifteen-minute reclaim.
* Trade 40 had traded below the original HL for over five hours. Its 08:11
  confirmed low was above the 05:50 range base but below the intervening 06:42
  low, so calling it simply a higher low would mix wave levels. That early
  reclaim later failed again, and price made another low before recovering.
* The 01:44 example did not confirm its later 02:51 low until 03:15, with the
  required raw inputs arriving at 03:15:04 New York time. Its fifteen-minute
  reclaim completed at 03:30, with inputs arriving at 03:30:13.

The four selected examples all eventually recovered. They cannot establish
a separator against genuine persistent failures or justify changing E3's
thresholds. The original nine-winner comparison and every original P/L value
remain unchanged. The 01:44 baseline is still historical unrealized P/L at
the original cutoff, not a new realized profit.

Artifacts and reproduction
--------------------------

Open ``reports/btc_e3_support_recovery_2026_11_15/AUDIT.html`` for the explanation,
all observed fifteen- and five-minute candles, and minute details around the
breakdown and initial recovery. ``AUDIT.json`` retains causal snapshots and
``BAR_REVIEW.csv`` exports bar-by-bar evidence.

``python3 scripts/audit_btc_e3_support_recovery.py`` reads archived data and
saved studies only. It does not fetch prices, instantiate a replay, create
entries, alter exit references, place orders, or restart workers. The
engineering review is in
``docs/investigations/2026-11-15_BTC_E3_SUPPORT_RECOVERY.md``.

Targeted checks cover future-data exclusion, exact receipt timing, incomplete
bar handling, independent parent/local references and strict-prefix stability
in ``trading_desk/tests/test_btc_e3_support_recovery.py``.
