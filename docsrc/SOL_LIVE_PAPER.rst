SOL E1 and BTC Live Paper Comparison
====================================

Current operation: ``/crypto-live`` is stopped, ``/btc-live`` continues
independently, and ``/sol-live`` contains separate SOL model 0.1 research.
The old SOL E1 worker is paused with automatic restart disabled. Historical
comparisons are at ``/crypto-research``. See :doc:`SOL_MODEL_01`. The original
E1 startup command below does not activate the new candidate.

Previously, ``http://127.0.0.1:8799/crypto-live`` displayed the original BTC 0.1/E1/E2
records beside a separate SOL/USD E1 worker. Frozen release 0.2, the BTC worker
and its session remain unchanged. ETH is not enabled.

Operation
---------

The SOL worker uses real Alpaca US crypto completed one-minute observations,
seven days of warmup and the unchanged frozen E1 strategy settings. It starts
forward signals at the next full minute after activation. Missing observations
stay missing; restarts reconstruct the same independent session.

Enable automatic login startup from the repository::

    python3 scripts/run_sol_live.py --enable --install-agent

Inspect status without starting another worker::

    python3 scripts/run_sol_live.py --status

The SOL login service is separate from BTC and keeps running with the browser
closed. The host must remain awake, online and logged in with the external
drive connected. The dashboard provides SOL pause/resume controls. Registration
does not claim a completed reboot or logout test.

Human review
------------

New BTC and SOL entry/exit model events appear at the top of the page. Each review
contains a stable proposal ID, asset/model, reference and detection times,
reference price, fraction, initial stop and first target when available.
Alerts exclude earlier events before alert activation. Delayed references are
identified explicitly. The page refreshes local data every five seconds without
AI calls. The recurring chat automation has been deleted to avoid token usage.

New alerts are highlighted and counted in the browser tab title. ``Mark
displayed alerts seen`` saves seen status in this browser, separately from
approval. Use ``Approve paper review`` or ``Reject`` to save a human decision.
When the page is closed the worker continues saving alerts; reopening shows
them. Page-only mode does not send chat or closed-page push notifications.

Model comparisons continue automatically. Approving a proposal records a
**paper-review decision only**: it does not submit an order, create a fill or
rewrite model positions/P&L. Later exits can supersede unreviewed entries.
Delivery acknowledgment is separate from approval. No broker order client is
loaded, including Alpaca paper-account execution.

Costs and units
---------------

The recent-trade table shows recorded A/B1/B2 labels, entry/detection times,
D/L2, stop/target, saved exits and per-coin realized leg P/L. It displays BTC
0.1 and SOL E1, at most three per asset; other BTC variants can have different
exits. The frozen detector tries A, then B1, then B2, so B1 may be recorded even
when B2 also qualifies. P1 independence filtering is not active in live paper.
Proposed classification refinements remain separate from the running workers.

BTC P/L is per initial one BTC; SOL P/L is per initial one SOL, not comparable
capital allocations or account returns. Both retain the frozen 2bps-per-side
ETF cost proxy, excluding actual spot-crypto fees. Quotes and minute-bar
references are not fills. Source gaps, stale data and delayed observations
remain visible on the desk.
