Trading Desk: Today's VWAP
================================

Compare each open holding with its regular-session volume-weighted average price.

:Last Updated: 2026-09-14
:Status: Active
:Audience: Trading Desk users

Overview
--------

Open **Daily review** in the local Trading Desk to see **Today's VWAP**.
The panel shows holdings from your private journal, including IBIT and excluding
SNDL. It displays session VWAP, the last price in the same data window, percentage
above or below VWAP, traded volume, and the last available minute bar's time.

VWAP weights each traded price by volume. A price above VWAP is above the session's
volume-weighted average; this alone does not establish a buy signal or a market
bottom. Session VWAP is separate from your purchase cost and the daily chart's
rolling **VWAP 20** indicator.

Timing and refresh
------------------

The panel uses consolidated Alpaca SIP minute bars, delayed at least 17 minutes.
The displayed date, session window, fetch time and last-bar times use Eastern Time.
The window ends just before the stated cutoff; a cutoff of 11:27 includes the
completed 11:26 minute. Prices are from that same window and are not live quotes.

Use **Refresh VWAP** to request fresh data. The panel also refreshes every two
minutes while Daily review is visible. The desk's main **Refresh** button refreshes
it too. The existing Alpaca credentials are used; calendar access and delayed SIP
data access are required.

Only regular-session bars count. The market calendar handles holidays and early
closes. Before delayed session data becomes available, or on a closed day, the
panel reports that state rather than showing yesterday's VWAP. Missing or invalid
data appears as unavailable; it is never filled with estimated prices or silently
replaced with a single-exchange feed. Gaps between reported trading minutes are
not filled. Values may differ from other platforms because of session settings,
trade eligibility, data revisions or timing.

Onchain Finance Buildout
------------------------

The main desk and sector board now organize the existing crypto research into
five daily-review layers: **Digital Money**, **Onchain Markets**, **TradFi Bridge**,
**Infrastructure Rails**, and **Agentic Finance**. **COIN and CRCL** are the anchor
securities. Review USDC supply and share, tokenized-asset growth, partnerships,
regulatory changes, settlement volumes and real agent-payment adoption.
These watchlists describe research scope; they do not assert current adoption.

Choose a review date under **What changed since yesterday?**. On the main desk,
expand **Record a sourced daily entry** to save a development, evidence type,
source URL, COIN/CRCL implications and who gains or loses. Optionally record a
metric value with its unit and scope. Entries use the existing private local
research storage and appear on the sector board too. Check the main desk's sync
status to confirm saving to the local file; the JSON export includes these entries.

A day-over-day comparison appears only when there is exactly one sourced metric
for yesterday with the same layer, metric name and unit/scope. Keep the source
methodology consistent. Missing or ambiguous baselines stay unavailable; a zero
baseline has no percentage change. News and metrics require sourced manual entry;
the desk does not automatically collect them. Unreviewed layers remain labeled.

The original eight-layer infrastructure map expands below the daily review.
Market links retain ticker labels; associated tokens do not represent company
equity. Additional research and saved observations remain available.
