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
