BTC Parent-Wave HL Identity
===========================

:Last Updated: 2026-11-09
:Status: Definition proposal; read-only entry-time evidence
:Audience: Trading Desk owner and research maintainers

Overview
--------

``docs/investigations/2026-11-09_BTC_PARENT_WAVE_HL_DEFINITION.md`` distinguishes
an intact ancestor support price from the currently active parent-wave
continuation. A confirmed H-L-LH and break of L invalidates that continuation
attempt; retaining an older lower D does not itself rebuild the failed branch.
Internal fifteen-minute lower lows can occur during a larger pullback, so a
local LL does not automatically disqualify a parent-level HL candidate.

The October 14 C #13 had a known hourly failure chain and an already confirmed
post-HL local high. Its original trigger was not crossed and the next trigger
was lowered. The November 9 03:17 and October 28 C #90 references crossed in
the first new candle after their local low confirmation, without this same
intervening hourly failure evidence. The November 9 setup remains an early
support-retest candidate, not a fully confirmed parent uptrend.

The normal-pullback #90 control is retained as a structural candidate despite
its later loss. Requiring every peak to have hourly confirmation would exclude
its original entry; that requirement is not introduced here. Three examples
do not validate a universal automated wave hierarchy or an improved return.

Reproduction
------------

``scripts/audit_btc_parent_wave_identity.py`` creates three structure-only
snapshots from observations strictly before the original entry minute, with
original price references separate. No later P/L is included. Prefix-only
equivalence and preservation checks accompany the evidence in
``reports/btc_parent_wave_identity_2026_11_09/``.

No trading rule, monthly replay, stop adjustment or order is added. P1, C,
frozen 0.2, saved results and the running Live Paper session remain unchanged.
