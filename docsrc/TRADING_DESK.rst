Trading Desk: Today's VWAP
================================

Compare each open holding with its regular-session volume-weighted average price.

:Last Updated: 2026-10-09
:Status: Active
:Audience: Trading Desk users

AI Power — Nuclear
------------------

The AI Power section is available on the Hot Sector Board at
``/board?view=ai-power``. It is not displayed or loaded on the home page. It combines sourced company evidence with a
completed-session recovery assessment, a staged swing-trading plan, and a
whole-share risk calculator. Refresh reads market data and masked account
positions. Entry levels remain a dated analyst plan until reviewed again.

The recovery framework requires breadth, relative strength and producer
leadership over two completed sessions. Today’s New York candle is excluded
even after the close. Missing, stale or misaligned data prevents confirmation;
short-history indicators remain unavailable. These rules are unbacktested
research criteria, not probabilities or guaranteed bottom identification.

The calculator requires a valid long entry/stop/target, cash and risk budgets,
and at least 2R to the target. It does not submit orders. Daily evidence notes
are saved through the main desk’s existing local revisioned research store.

Overview
--------

Daily review now prioritizes the verified SOLT addition as a separate day-trade
sleeve. Replaced orders are not fills. The trade entry, whole-position average,
earlier holdings and other accounts remain distinct. Intraday references carry
their own timestamps; delayed VWAP is not a live execution signal. The written
before-close review does not submit orders or automatically close a position.

The October 9 AI-optical exit review remains visible, confirmed
against both linked Schwab accounts. Optical names remain on the watchlist;
prior October 6–7 allocation and price-level commentary is superseded history.
Tactical sentiment and the fundamental Cycle score are separate: an incomplete
reassessment has no overall total or status. Weekday after-close monitoring
uses completed-session relative strength, breadth and dated fundamental sources,
and does not execute trades.

The historical review includes an October 6 intraday Individual-account snapshot with
current quantities, broker marks, reported cash, concentration and measured
price levels. CCJ and BWXT each show 50 shares. CRCL shows 275 and ETHA 66;
ETHA's zero reported cost basis leaves its cost and profit unavailable.
QNT remains watch-only and SNDL excluded. No fill times or stops are inferred.
The snapshot is dated and does not refresh itself; the live combined-account
review below continues to refresh independently. Broker marks and delayed
chart references have separate timestamps.

The main **Daily review** uses current Schwab holdings when the personal API
connection is available. A filled purchase appears after refresh, with the
broker's quantity and average cost. Journal stops and entry notes are used only
when the journal quantity matches the broker. A new holding is marked
**journal gap** until the private journal is updated; the desk does not invent
an entry date or stop. If Schwab cannot be reached, the review uses the journal
and labels that source. An open order is not shown as a holding until it fills.

The paper-agent panel starts with its configured review symbols and adds every
positive-quantity holding in the linked Schwab account on each refresh, except
UNG, IBIT and watch-only QNT. QNT remains visible in account holdings but does
not receive a paper-agent trade proposal. If the account read fails, the panel explicitly reports that it is
using only the configured fallback list. It derives entry, exit, and
risk-reference bands from observed price levels and ATR. **Buy Review** and
**Sell Review** only fill the guarded order form; a Schwab preview and separate
exact confirmation are still required to place an order.

Each broker preview includes an advisory wash-sale scan. It checks executed trades
for the same ticker across all linked Schwab accounts during the prior 30 calendar
days. Proposed buys highlight recent same-symbol sales whose realized loss must be
verified. Proposed sells compare the order price with the selected account's current
average position price, highlight recent replacement buys, and remind the user that
the 30-day post-sale window remains open after a loss sale.

The scan is intentionally conservative and never certifies an order as tax-safe.
Schwab's transaction history does not provide reliable tax-lot realized gain/loss
for this purpose, and average position price can differ from the selected lot's tax
basis. Other brokers, spouse-controlled accounts, options, and different securities
that may be substantially identical are outside its visibility. Missing history or
basis is shown as unknown, not safe. The warning does not block or submit an order.
See `IRS Publication 550 <https://www.irs.gov/publications/p550>`_ and
`Schwab's wash-sale overview <https://www.schwab.com/learn/story/primer-on-wash-sales>`_.

Open **Daily review** in the local Trading Desk to see **Today's VWAP**.
The panel follows the same Schwab holdings, falling back to the private journal
when Schwab is unavailable. It includes IBIT and excludes SNDL. It displays
session VWAP, the last price in the same data window, percentage
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

Symbol charts
~~~~~~~~~~~~~

Select a stock or crypto symbol to load its chart below the sector-board review.
Main-desk symbols link directly to the selected board chart. The adjacent arrow
opens the external market page. Canton is listed as **CCCAUSD**, mapped to the
Kraken **CC/USD** crypto pair rather than the unrelated CC stock.

Kraken charts show completed UTC daily candles and token volume; today's forming
candle is excluded. The feed and latest bar date appear with the chart. Missing
or invalid data clears the previous chart and displays unavailable. Some tokens
lack a configured daily feed; their external market page remains accessible.

Crypto chart ranges use calendar months ending at the latest completed candle.
Stock charts retain their trading-session ranges. Missing dates stay missing.

Combined Schwab accounts
~~~~~~~~~~~~~~~~~~~~~~~~

Daily Review shows all linked Schwab accounts in one holdings list. Shared
symbols combine quantities and use a quantity-weighted average cost for long
holdings. Masked account contributions appear beneath each symbol.
Today's VWAP uses this same combined account scope.

The **Schwab holdings by account & guarded preview** panel has separate
**IRA** and **Individual** tables. Each displays its own account value, cash,
holdings value, open profit/loss and day profit/loss. Holdings show shares,
average cost, broker mark, cost basis, market value, account weight, open
profit/loss in dollars and percent, and day profit/loss. Weight uses only that
account's liquidation value, including cash and hidden holdings. Broker mark
is market value divided by shares, not an executable quote. Missing or zero
average cost leaves derived cost basis and profit/loss percent unavailable.
Hidden holdings remain in account totals. Each account retains its own fetch
time. The IRA label is owner-identified, with registration confirmation pending.
Choose the labeled account explicitly before requesting a guarded preview.

Missing costs remain unavailable. If one account fails to load, the combined
review is unavailable instead of displaying a partial portfolio or the journal.
Journal stops are not applied to a symbol shared across accounts because the
journal does not identify the account. Chart-derived valuations retain their
market-data dates. Trading still requires selection of one account.

AI Power — Nuclear
==================

The Hot Sector Board has an **AI Power — Nuclear** view. It groups twelve
stocks by role: power producers (CEG, VST, TLN), fuel and enrichment
(CCJ, LEU, SOLS, STDN), equipment and services (BWXT, CW, MIR, FLS), and advanced
reactors (XE). Select a ticker to open its chart, or open the nuclear
scorecard to compare measured price strength, breadth and relative performance.

The scorecard uses SPY as its default benchmark and the existing market-data
feeds. Missing bars are reported as unavailable. The watchlist is research
scope; it does not rank future profits or submit trades. Optical and crypto
views remain available.

The broker identifier ``46438R105`` is hidden by request from desk rows,
alerts, paper-agent candidates and session VWAP. Its actual broker market
value remains in account-weight calculations. Hiding it does not sell or
remove the holding from Schwab; ETHA ticker rows remain visible.

Two-account daily review
------------------------

Daily Review includes the normal taxable Individual brokerage account and the
owner-identified rollover retirement account ending 434. Schwab currently
labels the latter Individual 401(k); registration confirmation is pending.
The saved October 6 Individual review remains a dated taxable-account snapshot,
with an October 7 clarification rather than revised historical balances.

Review combined holdings for exposure, but keep each account's cash, quantities,
cost basis and tax decisions separate. Combined open profit/loss is not a taxable
gain/loss calculation. A loss inside the retirement account can be realized by
selling, but it cannot be harvested as a deductible capital loss. IBIT proceeds
may be rotated within that retirement account without current capital-gains tax;
withdrawals have separate rules. Taxable sales require their own lot review,
including purchases across accounts when checking wash sales.

The owner's roughly 20% retirement-account decline and intended COIN/CRCL adds
are dated observations and plans, not refreshed performance or executed trades.
See `Schwab's tax-smart strategies <https://www.schwab.com/taxes/tax-smart-strategies>`_
and `IRS traditional IRA guidance <https://www.irs.gov/retirement-plans/traditional-iras>`_.

RWA & Tokenization sector
-------------------------

Open ``/board?view=rwa`` or select **RWA & Tokenization** on the sector board.
This market screen is available only on the sector board; the home page does not
load its table or market-screen assets. The table selects up to ten leaders from a
reviewed pool of RWA infrastructure,
governance and gold-backed tokens in CoinGecko's RWA category. Each must have at
least $100 million circulating market cap and $10 million reported 24-hour USD
trading volume. Default order sums market-cap and volume ranks equally, breaking
ties by market-cap rank. Ranks cover all qualifying pool members; sort controls
reorder the selected shortlist without changing membership.

The table shows source timestamps and supports explicit refresh. Successful
responses cache for five minutes; failed responses cache for 30 seconds.
If market-data refresh fails, a dated snapshot can be displayed with a warning
only after a successful current Coinbase check; it does not create observations.
If Coinbase verification fails, the token list is withheld. Market cap is circulating token
value, not fully diluted value or assets under management. Dollar volume aggregates
reported markets and differs from venue candle volume. Infrastructure tokens do
not represent ownership of tokenized assets. Stablecoins, restricted funds and
tokenized stock wrappers are excluded from this research pool.

Select a coin ticker in the RWA table to show its chart below, just as stock
selection does. Modified clicks open the sector board with that coin selected.
RWA tickers always route to crypto data, including QNT. The source footer still
opens the external market-data source. Charts use Kraken's completed UTC daily
candles and token volume; the ranking table uses aggregate 24-hour USD volume.
Unavailable candles are reported without substitutes, and the previous chart
is cleared when a new coin is selected.

Coinbase tradability is required before ranking. Each coin must have an online
Coinbase Exchange USD or USDC spot market with normal trading enabled: no
trading-disabled, cancel-only, post-only, limit-only or auction mode. The table
shows the verified pair and check time. If Coinbase verification is unavailable,
tokens are withheld. Public Exchange availability does not determine account or
regional eligibility. Charts continue to use Kraken candles.

The crypto research panel below the chart provides separate CoinGecko and
CoinMarketCap links for the selected token. Each opens its asset-specific page
in a new tab. Switching tokens updates both links; they remain available when
chart candles cannot be loaded. USD feed aliases resolve to the underlying token.
