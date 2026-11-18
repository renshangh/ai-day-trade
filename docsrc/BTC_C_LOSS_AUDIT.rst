BTC C Continuation Loss Audit
=============================

:Last Updated: 2026-11-09
:Status: Read-only investigation; no rule change or monthly replay
:Audience: Trading Desk owner and research maintainers

Overview
--------

The investigation in
``docs/investigations/2026-11-09_BTC_C_PARENT_HL_LOSSES.md`` examines the four
largest baseline C losses and the distinct largest E1 loss against the
November 9 03:17 prefix case. Original entries, exits and net P/L are retained.

C can attach a local fifteen-minute low to an older intact hourly D after
nearer parents have broken or failed the inherited HL-distance check. This
does not establish that they are independent lows of the same wave level.
The October 16 and October 14 cases expose this scope fallback. October 28
also shows that a reasonable HL continuation can simply fail afterwards.

The nominated 03:17 case itself remains a local lower low compared with the
preceding fifteen-minute low; it is an HL only relative to the larger parent.
Later appreciation cannot validate the classification retroactively. No new
filter, forced 2R, nearer stop, changed exit or improved monthly return is
claimed in this audit.

Evidence
--------

``scripts/audit_btc_parent_hl_losses.py`` reads saved research results and
observed source minutes without constructing a strategy or replay. Its
``reports/btc_parent_hl_loss_audit_2026_11_09/`` outputs include full real
fifteen-minute, hourly and minute CSVs, raw audit JSON, and a preservation
manifest. Partial observations remain explicitly partial. Candles after entry
are labelled retrospective evidence, never pre-entry knowledge.

P1, C rules and saved comparisons, frozen 0.2 and Live Paper remain unchanged;
the worker continues in the same session with no broker orders.
