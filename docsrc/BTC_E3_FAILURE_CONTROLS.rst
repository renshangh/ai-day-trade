E3 Failed Breakout Control Review
=================================

This observational study compares four saved losing PH5 trades with the
previous four recovery cases. It changes no entry, exit, risk setting, frozen
release, study selector, or live worker. No new exit price or P/L is simulated.

Selection and observation boundary
----------------------------------

The controls are the four largest original net losses among the 62 PH5 losses
without holding-gap or incomplete-entry-context flags in the same saved
``0.1 retained_combined`` study: trades 22, 111, 75 and 2. Selection deliberately
uses outcomes for diagnosis, so it is not a prospective filter or a validation
of E3 performance.

Each path ends at its original exit, with the exit minute's complete OHLC
separately labeled as later information. The November 15 01:44 case retains
its original 05:16 New York cutoff and unrealized, marked P/L. A losing exit
does not establish that price never recovered afterward.

Eight cases use common checkpoints: first completed five-minute and
fifteen-minute closes below the original entry HL. Later minima, reclaims and
complete exit-minute ranges cannot enter those earlier snapshots. Partial
candles and actual input delivery remain explicit.

Findings
--------

* All eight parent Ds were intact at the first completed five-minute HL
  failure checkpoint. That early condition did not separate these outcomes.
* Trades 22 and 111 lost while their larger parent D remained intact. Trade
  22 briefly regained the HL on a completed five-minute candle but never
  regained it on a completed fifteen-minute candle before its original exit.
* Trades 75 and 2 pierced parent D intraminute and recovered it within the
  same minute. Neither had a complete one-, five- or fifteen-minute close
  below parent D before the original exit minute. Original hard stops still
  applied; waiting for a completed structural close would not replace them.
* Recovery trade 40 had twenty consecutive completed fifteen-minute closes
  below its HL, longer than these selected failures, and its initial reclaim
  failed again before its eventual winning exit. Duration or one failed
  reclaim alone cannot safely label persistent failure.

The comparison highlights sequences of confirmed lows, failed rebounds and
sustained reclaims, without defining a new threshold, score or exit rule.
Original P/L values, E3 draft one and previous results remain unchanged.

Artifacts
---------

Open ``reports/btc_e3_failure_controls_2026_11_15/AUDIT.html`` for the eight-case
comparison and all observed fifteen-, five- and one-minute records.
``AUDIT.json`` retains original metadata and causal snapshots;
``BAR_REVIEW.csv`` exports the aggregate evidence. ``COHORT.json`` records
selection and observation scope.

``python3 scripts/audit_btc_e3_failure_controls.py`` reads local archived data
and saved results only. It does not fetch quotes, instantiate a strategy
replay, change model state, create orders or restart workers. Engineering
notes are in
``docs/investigations/2026-11-15_BTC_E3_FAILURE_CONTROLS.md``.

Regression checks use actual archived losing-trade observations to verify
prefix stability, support-level separation, five- versus fifteen-minute
reclaim differences and exit-minute knowledge boundaries. Existing studies,
frozen 0.2 and the running BTC worker/session remain protected by hashes.
