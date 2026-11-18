Trading Desk Repository Contents
================================

The repository front page links the local Trading Desk source and saved chart
captures. ``/btc-live`` is a server route implemented by
``trading_desk/btc_live.html`` and its associated Python/JavaScript files;
GitHub does not run the interactive page. See ``docs/REPOSITORY_CONTENTS.md``
for the complete route-to-source map and local viewing instructions.

The extended research views require the repository's Python dependencies,
including NumPy. Missing private or research stores remain unavailable.
The unchanged ``btc-research-v0.2`` GitHub release supplies the frozen data,
verification manifest and workbook for installing the baseline in a fresh clone.

Historical BTC scenario captures live in
``reports/btc_elliott_wave_2026_11_16``. Dated BTC Live Paper and IBIT-hours
captures are indexed under ``reports/btc_live_captures``. Screenshots do not
advance their own evidence dates and dashed paths remain illustrative.

Credentials, OAuth state, brokerage records and current account snapshots are
local only. The public dashboard shell omits embedded account holdings.
``scripts/public_dashboard_snapshot.py`` writes a separate public HTML copy
without overwriting the local private view. Publication changes no frozen
trading rule, worker control or order behavior.

The Trading Desk Public Snapshot workflow verifies portable Python and browser
checks without credentials or private stores, and compares every frozen BTC
rule source with the original published 0.2 manifest. Broader archived-study
integration tests require their original saved inputs and do not fabricate
substitutes when those inputs are absent.
