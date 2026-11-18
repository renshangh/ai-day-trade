BTC Parent-Only Sequential Comparison
=====================================

:Last Updated: 2026-11-09
:Status: Separate research; improved but still negative; not promoted
:Audience: Trading Desk users and maintainers

Overview
--------

Open ``/btc-parent-filter`` for the independent full-sequence comparison of
P1+C controls against the locked parent-failure-only C filter. The original
controls reproduce exactly. The same minute stream, seven-day warmup, stops,
targets, exit methods and costs are retained. Uncertain cases remain eligible;
trigger lowering is diagnostic only. No manual #13 override is used.

The filtered 0.1/E1/E2 model nets are -$6,797.67 / -$8,866.65 / -$7,113.90,
improving their P1+C controls by $1,777.50 / $1,757.28 / $1,777.50. All remain
negative. Closed-trade drawdowns fall; these are fixed-1-BTC model outcomes,
not compounded or mark-to-market account returns. Each gap group is separate.

Full sequences permit replacement A/B/C opportunities after a rejected C.
These are not fixed-entry deletion sums: baseline adds seven trades with net
-$1,080.23 while fourteen old entries disappear. Lost winners and all actual
exit legs remain visible, with charts, chronological protection and CSVs.

Preservation
------------

``docs/BTC_PARENT_FILTER_RESEARCH.md`` documents the exact contract and results.
``scripts/retest_btc_parent_filter.py`` writes separate runs/study folders;
opening the read-only result page never starts it. Existing P1/C, frozen 0.2,
blind labels, original selectors and the Live Paper worker remain unchanged.
The research is not promoted and no broker orders are sent.
