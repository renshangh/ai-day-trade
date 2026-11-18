BTC Bounce Entry Audit November 14 and 15
==========================================

Explain the missing entry during the actual $61,991 to $66,085 recovery.

:Last Updated: 2026-11-15
:Status: Read-only diagnostic; no trading-rule or live-worker changes
:Audience: Trading Desk owner and maintainers

Overview
---------

A causal isolated replay reproduced all 20 recorded entries and all 20 exit
legs per model through the historical cutoff. During the low-to-peak interval
all 448 minutes were available for entry, but no A/B setup became ready.
Prices crossed the preceding complete 15m high in 138 observed minutes; those
are crossing minutes, not independent trade signals. Broker hours, holding
status, chase and a mandatory 2R screen did not cause the missing trade.

A and B failures
-----------------

A requires four independently rebounding lower lows, followed by its armed
HH/HL sequence. The prior trade consumed earlier setup history. The initial
continuous decline produced one LL phase, not four, and the rising peak later
replaced that declining scope. The next pullback accumulated only three LLs.
The larger parent-wave higher-low continuation was outside frozen A's scope.

B requires a single completed bearish new-low impulse of at least two prior
ATRs. The 20:00, 20:15 and 20:30 declines were respectively about 1.366, 0.569
and 0.690 ATR. The candle containing the final low closed green. The later
02:30 decline reached 1.738 ATR. No shock chain was established, so neither
B1 stabilization nor B2 rebound/HL checks could create an entry episode.

Five-minute diagnostic
-----------------------

Five-minute bars were aggregated from genuine consecutive observations only.
The 20:50 previous-five-minute-high break was earlier but lacked a separate
completed post-D hold. By 20:58 that holding candle and a new high break were
visible; the fifteen-minute high also broke in that minute. The 03:20 five-
minute trigger preceded the fifteen-minute break by about one minute, whereas
04:00 gave the same trigger minute on both timeframes.

Speed is expressed as percent per minute and prior-ATR-normalized change,
not visual chart angles. Complete-bar speed is known only after that bar
finishes. Quote-derived/venue-volume limitations prevent claims of consolidated
buying pressure or executable fills. No speed cutoff, five-minute rule, stop,
target or hypothetical P/L is adopted from this selected successful bounce.

Evidence and preservation
--------------------------

The full 30-candle table, gate states, before/after-close LL counts, exact
worker receipts and five-minute metrics are in
``docs/investigations/2026-11-15_BTC_BOUNCE_ENTRY_AUDIT.md``.
``reports/btc_bounce_audit_2026_11_15/AUDIT.html`` is the readable table report;
``AUDIT.json`` preserves the complete trace. The scripts replay only the
original local prefix in isolated memory, without calling the mutating final
flush or any broker client. Frozen 0.2, all 13 strategy hashes, original BTC
worker PID/session, control files and registration remain unchanged.
