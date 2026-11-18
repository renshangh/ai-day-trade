BTC Parent-Flagged Winners Review
=================================

:Last Updated: 2026-11-09
:Status: Read-only adjudication; original labels and trading rules preserved
:Audience: Trading Desk owner and research maintainers

Overview
--------

The two baseline C parent-flagged winners (#5 and #69) still had valid
pre-entry evidence that the selected old parent continuation had failed.
They profited from subsequent smaller rebounds, without reclaiming the failed
parent peak. Profit does not retroactively make the original parent valid.
The #69 path also broke its near HL while holding the larger parent D, then
exited through the unchanged profit-giveback guard.

For #13, the uncertain outside hour can be examined with real one-minute
observations: its high occurred at 13:05, its low at 13:54, and that low was
broken again at 18:23, all before the 21:32 entry. The hour did not reclaim
the old failed LH/H or establish a surviving replacement base. Manual review
supports the failure evidence; the original automatic uncertain label remains
untouched. This does not resolve every outside bar or promote a new filter.

Evidence
--------

See ``docs/investigations/2026-11-09_BTC_C_PARENT_FLAG_WINNERS.md`` and the
``reports/btc_c_parent_flag_winners_2026_11_09/`` minute/candle evidence.
``scripts/audit_btc_c_parent_flag_winners.py`` reads saved inputs only.
Pre-entry evidence, later hourly confirmation timing and post-entry outcomes
are explicitly separate. Original data, blind labels, P1/C, frozen 0.2 and
the running Live Paper session are verified unchanged. No strategy replay,
new exit, stop change or broker order is created.
