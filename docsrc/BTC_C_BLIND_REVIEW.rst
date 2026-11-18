BTC C Blinded Structure Review
==============================

:Last Updated: 2026-11-09
:Status: Fixed-entry diagnostic only; no filter promoted
:Audience: Trading Desk owner and research maintainers

Overview
--------

The locked protocol classifies twenty new baseline C entries using only
pre-entry observations, with exit/P&L fields withheld. The sample is stratified
ten wins/ten losses by a fixed SHA256 selection. This is procedural input
blinding in the same historical window, not independent human or out-of-sample
validation. Labels are saved before outcomes are joined.

Seven clear flags include five losing and two winning original trades. The
unchanged classifier then annotates 368 saved model rows / 149 unique entry
contexts, without replaying any strategy or changing trade paths. On baseline
C, the parent-failure flag marks 8 losses/2 wins; the trigger-lowering flag
marks 8 losses/10 wins whose original net is positive $1,619.16. This does not
support promoting trigger lowering to a hard filter. Unknown outside/gap
contexts remain manual review, including the known #13 control.

The complete Chinese report is in
``docs/investigations/2026-11-09_BTC_C_BLIND_REVIEW.md``. Tables and stage hashes
are in ``reports/btc_c_blind_review_2026_11_09/``. Original P1/C, frozen 0.2,
entries, exits, costs and the running Live Paper session remain unchanged.
No replacement opportunities, new monthly returns or broker orders are created.

Reproduction
------------

``scripts/audit_btc_c_blind_review.py`` has separate prepare, classify, reveal
and fixed-entry-all phases. The protocol and classifier hashes are locked
before labels. Prepare refuses to overwrite the existing study. Read the saved
artifacts for review rather than rerunning or altering the locked investigation.
