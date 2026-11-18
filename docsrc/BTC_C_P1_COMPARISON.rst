BTC C and P1 Confirmation Comparison
====================================

:Last Updated: 2026-11-09
:Status: Six-case read-only comparison, no rule promotion
:Audience: Trading Desk owner and research maintainers

Overview
--------

The C route seeks a local fifteen-minute breakout after a higher pullback low
relative to an intact confirmed hourly parent D. It retains the larger-D stop,
original exits and A/B priority. It does not require A's four independent lows.

``docs/investigations/2026-11-09_BTC_C_P1_CONFIRMATION.md`` applies the original
P1 low-confirmation function separately to each parent D and entry HL in the
five selected C losses and the November 9 03:17 case. This is a diagnostic,
not a new C rule and not the full A setup validator.

All six parent Ds pass. On the nearer HL, four losing original entry times
are blocked, but the November 9 03:17 opportunity is blocked too. Only the
October 14 #13 loss passes at its original entry. P1 postpones confirmation;
it does not establish same-level parent-wave ownership.

Later qualification times are reported separately, not treated as new fills
or revised P/L. No monthly replay, parameter change or hypothetical improved
return is claimed. Original P1/C code, saved sequences, frozen 0.2 and the
running Live Paper session remain unchanged.

Reproduction
------------

``scripts/audit_btc_c_p1_confirmation.py`` reads archived observations and
saved case references, calls only the unchanged P1 low checker, verifies ATR
against original ledger values and confirms prefix-only equivalence. Evidence
and preservation hashes are in
``reports/btc_c_p1_confirmation_2026_11_09/``. Missing observations are not filled.
