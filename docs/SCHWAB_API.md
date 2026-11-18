# SCHWAB_API.md

> How to get your own Charles Schwab developer app approved and make your first real API calls, using `scripts/schwab_api.py`.

**Last Updated:** 2026-10-12
**Status:** Active
**Audience:** Developers, AI Agents

---

## Overview

Schwab retired the TD Ameritrade API after the acquisition and replaced it with the
**Schwab Trader API** at [developer.schwab.com](https://developer.schwab.com). It is
free, covers the accounts you already hold at Schwab, and splits into two products:

| Product | Base path | What it gives you |
|---|---|---|
| Accounts and Trading | `/trader/v1` | accounts, balances, positions, orders, transactions |
| Market Data | `/marketdata/v1` | real-time quotes, price history, option chains, movers |

`scripts/schwab_api.py` is a read-only, stdlib-only client for both. It exists so you
can try the API without installing anything and without going through the vendored
`lumibot` Schwab broker — see [Relationship to the lumibot broker](#relationship-to-the-lumibot-broker).

**That script never places, replaces, or cancels an order.** Chat-driven order
placement uses the separate guarded helper described below.

---

## Step 1 — Register an app (you must do this yourself)

Account creation and app registration happen on Schwab's site under your own login.

1. Go to [developer.schwab.com](https://developer.schwab.com), create a developer
   account, and log in. The developer account is separate from your brokerage login,
   but you link your brokerage accounts during the OAuth step later.
2. **Dashboard → Create App**, and fill in:

   | Field | Value | Why |
   |---|---|---|
   | API Product | **Accounts and Trading Production** | Grants both trading *and* market data. Picking only "Market Data" locks you out of accounts. |
   | Order Limit | `120` | Orders per minute. Irrelevant while read-only, and there is no benefit to setting it lower. |
   | App Name / Description | something descriptive | A human at Schwab reads this during approval. |
   | Callback URL | `https://127.0.0.1:8182` | **No trailing slash.** Must be HTTPS even though it is localhost. |

3. Submit. The app shows **Approved - Pending**, which does *not* mean usable.
   Wait until it reads **Ready For Use** — this takes a few days.
4. Once ready, open the app and copy the **App Key** and **App Secret**.

### About the callback URL

The callback is where Schwab sends the authorization code after you log in. Nothing
needs to actually listen there: the login flow in this script has you copy the
redirected URL out of the address bar, so the browser's "can't connect" or
certificate error on `https://127.0.0.1:8182` is expected and harmless.

The value must match **byte for byte** between the developer portal and the script.
A trailing slash, `localhost` instead of `127.0.0.1`, or a different port all produce
an opaque security error at login. Changing it later requires re-approval (days).

---

## Step 2 — Configure credentials

Add to `.env` at the repo root (git-ignored):

```
SCHWAB_APP_KEY=your_app_key
SCHWAB_APP_SECRET=your_app_secret
```

Optional, both defaulted:

```
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
SCHWAB_TOKEN_PATH=.secrets/schwab_token.json
```

`SCHWAB_APP_KEY` and `SCHWAB_APP_SECRET` are the same names `lumibot/credentials.py`
reads, so a working `.env` here also feeds the lumibot broker later.

---

## Step 3 — Log in

```bash
python3 scripts/schwab_api.py login
```

It prints an authorization URL and opens it. Log in with your **brokerage**
credentials, pick which accounts to expose, and approve. Schwab redirects to
`https://127.0.0.1:8182/?code=...&session=...`; the browser errors out, which is fine.
Copy the entire URL from the address bar and paste it at the prompt.

The token lands at `.secrets/schwab_token.json`, mode 600, already covered by
`.gitignore`. It grants full access to your brokerage accounts — treat it exactly
like a password.

---

## Step 4 — Verify

```bash
python3 scripts/schwab_api.py check
```

Prints token age, your accounts, balances, and one SPY quote — enough to confirm both
API products respond. Then:

```bash
python3 scripts/schwab_api.py positions
python3 scripts/schwab_api.py transactions --days 30
python3 scripts/schwab_api.py quote NVDA AXTI COHR
python3 scripts/schwab_api.py raw /trader/v1/userPreference
```

`raw` takes any GET path, which is the fastest way to explore endpoints the other
subcommands do not wrap:

```bash
python3 scripts/schwab_api.py raw /marketdata/v1/pricehistory \
  --param symbol=NVDA --param periodType=month --param frequencyType=daily
```

## Chat-invoked Schwab trader

The personal Codex skill `schwab-trader` turns an explicit request in this chat into
a guarded Schwab order workflow. Invoke it naturally or by name, for example:

> Use `$schwab-trader` to preview buying 10 shares of AXTI with a $30.50 limit.

The skill and the Trading Desk's preview form both call
`scripts/schwab_trade.py`. Their order scope is deliberately small:

- stocks and ETFs only;
- whole shares only;
- BUY and SELL only (no shorts);
- MARKET/DAY or LIMIT with DAY/GTC, normal session only.

A request produces a Schwab preview, not a live order. The preview is saved under
`.secrets/schwab_order_previews/` with owner-only permissions, expires after ten
minutes, and returns a one-time token plus an exact confirmation phrase. A live
submission can happen only in a later chat turn when you type that complete phrase.
“Yes” or “confirm” is not sufficient. The agent never retries an ambiguous live
submission; it tells you to inspect Schwab open orders and order history instead.

For sells, the helper verifies that the account owns enough long shares both before
preview and immediately before submission. Missing position data blocks the order.
Schwab acceptance means the broker received the order; it does not mean the order
filled.

Useful direct checks are:

```bash
python3 scripts/schwab_trade.py status
python3 scripts/schwab_trade.py previews
```

The Trading Desk Daily Review calls the same sanitized boundaries to show readiness,
read live positions, and request a broker-side preview. It does not receive
credentials, OAuth tokens, account hashes, or full account numbers, and the dashboard
has no order-placement endpoint. Its **Copy confirmation** button only copies the
preview's exact confirmation phrase; it does not call Schwab. Loading, refreshing,
previewing, or pressing that button therefore cannot place an order. Sending the
exact phrase in a later chat turn triggers the guarded submission agent described
above.

Every Trading Desk preview also runs an advisory wash-sale scan before displaying
the broker result. The scan reads executed trades for the same ticker across all
linked Schwab accounts during the prior 30 calendar days. For a proposed sell, it
compares the requested limit (or current broker mark for a market order) with the
selected account's current average position price and highlights earlier replacement
buys. For a proposed buy, it highlights earlier same-symbol sales whose realized
gain or loss must be verified. A potential loss sale always carries a reminder that
another purchase during the 30 calendar days after the fill may create a wash sale.

This is a conservative alert, not a tax calculation. Schwab's transaction API does
not provide reliable tax-lot realized gain/loss for this purpose, and average
position price is not necessarily the selected lot's basis. The scan cannot see
other brokers, spouse-controlled accounts, options, or different securities that
may be substantially identical. An unavailable history or basis is displayed as
unknown rather than safe. The alert never blocks or submits an order. Its sanitized
read-only command is:

```bash
python3 scripts/schwab_trade.py wash-sale-check \
  --account-last4 3652 --side buy --symbol LITE --quantity 10 \
  --order-type limit --limit-price 982.00 --duration day
```

The IRS describes the rule as a loss sale paired with an acquisition of the same or
substantially identical security within 30 calendar days before or after the sale;
the rule can cross accounts, including IRA or Roth IRA acquisitions. See
[IRS Publication 550](https://www.irs.gov/publications/p550) and
[Schwab's wash-sale overview](https://www.schwab.com/learn/story/primer-on-wash-sales).

The main Daily Review now reconciles against the same live Schwab positions on
each review request. Schwab quantity and average cost determine which holdings
appear and their exposure; a new filled buy can appear without editing the
private journal. The journal still supplies entry dates, stops, and thesis
notes only when its share count matches Schwab. A mismatch is flagged as a
journal gap, and the desk does not apply an old lot stop to newly bought shares.
When the combined account read fails, the daily review reports unavailable rather than substituting journal holdings.
An accepted but unfilled order is not a holding and will not appear there.

Until the developer app reads **Ready For Use**, `status` will explain the remaining
setup step and no order can be previewed or placed.

## Token lifetimes (the part that bites)

| Token | Lifetime | Handling |
|---|---|---|
| Access token | 30 minutes | Refreshed automatically; you never see this. |
| Refresh token | **7 days, hard** | Re-run `login` by hand. |

The 7-day clock starts at the *original authorization* and refreshing does **not**
restart it. There is no way around the weekly re-login — Schwab requires a human at
the browser. `check` reports hours remaining and warns past 6.5 days. Anything built
on this API needs to tolerate a weekly manual step; running `login` every Sunday
before the week opens is the usual pattern.

---

## Rate limits

About **120 requests/minute** as an aggregate budget across all endpoints — market
data and account reads draw from the same pool — with order placement separately
capped by the Order Limit you set at registration. Going over returns **HTTP 429**
(`429-001` sustained, `429-005` burst); back off ~60s rather than retrying tightly.

Quotes accept batched symbols (`?symbols=A,B,C`), so ask for many symbols in one call
rather than looping — that single change is usually the difference between comfortably
under the limit and hitting 429s.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Login fails with a security/`unsupported_response_type` error | Callback URL mismatch. Compare against the portal character by character, trailing slash included. |
| `App Registration Error` status, or portal rejects a valid HTTPS callback | Known Schwab console bug. Delete the app, recreate it; mail `traderapi@schwab.com` if it persists. |
| `401` on every call right after approval | App is still `Approved - Pending`, not `Ready For Use`. |
| Refresh rejected with `400`/`401` | 7-day refresh token expired. Re-run `login`. |
| `404` on a `/trader/v1/accounts/{hash}` path | Use the `hashValue` from `/accounts/accountNumbers`, never the plain account number. |

---

## Relationship to the lumibot broker

The vendored fork already ships `lumibot/brokers/schwab.py`, built on
[`schwab-py`](https://schwab-py.readthedocs.io) and defaulting to Lumiwealth's hosted
OAuth callback (`api.botspot.trade/broker_oauth/schwab`) with their app key. That path
is for BotSpot users, and it routes authorization through a third-party backend.

Use `scripts/schwab_api.py` when you want **your own** app key, no dependencies, and
read-only access. Use the lumibot broker when you want a strategy to trade through
Schwab; it needs `pip install schwab-py` and its own `SCHWAB_*` config, and it can
point at your own app rather than BotSpot's.

For direct `schwab-py` use, `easy_client()` handles the whole login flow including a
local HTTPS listener, so it captures the callback without the copy-paste step.

---

## Related

- `scripts/schwab_api.py` — the client this doc describes
- `scripts/schwab_trade.py` — guarded preview/confirmation order boundary used by the chat skill
- `trading_records/SOURCE-NOTES.md` — the manual capture process this API could replace
- `lumibot/brokers/schwab.py`, `lumibot/tools/schwab_helper.py` — BotSpot-oriented path

## Combined Daily Review

As of October 28, the default review shows the current dated trading plan and
always-visible per-account holdings. Expired authentication clears current
holdings and displays a reconnect notice instead of stale data.
Historical summaries live in `trading_desk/DAILY_REVIEW_ARCHIVE.html` and are
linked from the plan. Live account widgets remain available in a collapsed
disclosure; archiving does not alter broker records, permissions or orders.


Daily Review reads all authorized Schwab accounts together using
`python3 scripts/schwab_trade.py positions --all-accounts`. The main exposure review combines shared symbols with weighted cost.
The **Schwab holdings by account & guarded preview** panel instead shows
separate Individual (***3652) and owner-identified IRA (***6434) tables. Each
account has its own liquidation value, cash, holdings value, open and day P/L.
Each holding shows quantity, average cost, derived broker mark, cost basis,
market value, weight against that account's liquidation value, open P/L in
dollars and percent, and day P/L. Broker mark is market value divided by shares,
not an executable quote. Cost basis and P/L percent are unavailable when average
cost is missing or zero, or the position is not long-only. Weights include cash
and hidden holdings in their denominator. Hidden holdings remain in account
totals. Account-specific fetch timestamps are preserved. The IRA label follows
the owner's identification; broker registration confirmation remains pending.
Preview account selection uses these same labels and requires an explicit choice.
Empty accounts
still count as linked. Missing costs and balances remain unavailable, and a
failed account prevents partial holdings from being presented as the whole book.

The same combined account scope supplies Today's VWAP. Journal stops are not
applied to a shared symbol across accounts because the journal has no account
provenance. The chart-derived valuation is dated and can differ from Schwab's
reported market value. Combined balances do not imply transferable buying power.
Order previews and trades still require one explicit account when multiple
accounts are linked; review aggregation does not choose a trading account.

## Two-account review context (October 7, 2026)

The owner reviews two accounts: normal taxable Individual brokerage ***3652
and rollover retirement ending 434. The owner identifies the latter as an IRA
rollover; Schwab's Positions page displays Individual 401(k). A secure inquiry
was sent October 7 to confirm the registration and rollover status; confirmation
is pending. Do not infer retirement registration from an API CASH/MARGIN value.

The owner reports the retirement account is about 20% down. This is an owner
observation, not a refreshed return calculation. Selling a losing retirement
holding is allowed but creates no deductible capital loss. IBIT can be sold if
needed and proceeds reinvested within that account without current capital-gains
tax; distributions have separate rules. Taxable brokerage sales require that
account's own lots and basis, with wash-sale review across accounts. Combined
P&L measures exposure and must not be used as a tax netting calculation.

The October 6 saved Individual snapshot remains dated and scoped to ***3652.
Its October 7 addendum and the persistent Daily Review account-context panel
record the clarification without rewriting historical holdings. The planned
COIN/CRCL additions remain intent, with no inferred account, quantity or fill.
This supports the desk's North Star of sourced, explicit thesis decisions:
account identity and the evidence date must accompany every rotation decision.

Sources: [Schwab tax-smart strategies](https://www.schwab.com/taxes/tax-smart-strategies),
[IRS traditional IRAs](https://www.irs.gov/retirement-plans/traditional-iras).

## Day-trade review reconciliation

For an owner-designated tactical addition, retrieve the individual submitted
order and the symbol's orders for the session before recording an entry.
`REPLACED` with zero filled shares is not an execution. Use actual `FILL`
execution legs from the final filled order for quantity, price and time.
Keep sanitized evidence in private `trading_records/` snapshots and append only
the verified addition to the private journal; do not invent older missing lots.

Review the addition separately from pre-existing shares and other accounts.
Whole-position average cost and broker current-day P&L are not the new trade's
entry or P&L. Label current bid/ask separately from delayed session VWAP, and
leave unapproved stops, targets and exit executions blank. A written time-exit
plan is advisory: a DAY order expires if unfilled, but does not sell a position
that has filled. This workflow supports the sourced-decision North Star.

## SOLT recovery-exit planner

The Daily Review SOLT planner is read-only and account-specific. It requests the
selected account's live position, then combines its quantity and average cost
with real SOLT daily bars and completed Kraken SOL daily candles. The latest
common session prevents an unfinished SOLT bar from being compared with a later
or earlier SOL close. Missing aligned closes, ATR, or position basis makes the
plan unavailable; values are never filled forward.

The first review zone starts at average cost and extends 0.25 SOLT ATR. A second
zone spans 0.5–1.0 ATR above average cost. Each is 25% of whole shares, rounded
down, while the remainder is a runner managed with fresh 30-minute structure and
session VWAP. The SOL cross-check estimates an observed short-window beta and
reports only a single-session equivalent. It is not a multi-day forecast because
SOLT resets leverage daily. Measured support is a thesis-review reference, not a
submitted stop or permission to realize a loss. The endpoint creates no preview
and has no placement path.


## Multi-account cash-percentage buys

Owner-approved project workflow, November 10, 2026; applies to other chats in this
project. Submission remains a chat workflow using the existing guarded order helper.
The read-only cash sizing page below does not add batch submission.

A request supplies symbol, selected accounts, limit price, duration, and one of
25%, 50%, 75%, or 100%. A percentage applies independently to each selected
account, never to pooled account cash. Do not assume that earlier accounts or
an earlier symbol remain selected. Normalize an unambiguous account suffix
(e.g. 071 to linked 0071), and show masked account labels.

1. Refresh authorized linked-account balances and outstanding buy orders using
   read-only APIs. Verify cash available for this purchase without margin,
   accounting for cash holds, existing buy commitments and applicable costs.
   Do not double-subtract commitments already included in the available figure.
   `cashBalance` alone is not proof of spendable cash; `availableFunds` and
   `buyingPower` can include margin. If the response cannot establish cash-only
   availability or outstanding-order coverage is incomplete, leave sizing for
   that account unavailable and explain the gap; do not guess or substitute a
   historical balance. A broker preview approving an order does not prove that
   the funding is cash-only.
2. Use decimal arithmetic: budget = verified uncommitted cash * percentage / 100;
   shares = floor((budget - applicable cost reserve) / limit price), clamped to
   zero. Cost reserves must be justified, not invented fees. Reject nonpositive
   prices and unsupported percentages. Whole shares only; never round up.
   At 100%, residual cash smaller than the cost of one share is expected.
   Market orders cannot guarantee this budget, so obtain an explicit limit
   price before using this workflow.
3. Display each account's balance source/time, verified cash, percentage, budget,
   whole-share quantity, estimated cost, and estimated cash remaining. Skip
   accounts with zero affordable shares. Estimations are not fill guarantees.
4. A sizing/recommendation request does not authorize previews or submission.
   An explicit complete placement request authorizes processing calculated orders
   through the existing Schwab skill in the same turn, subject to its validations.
   Refresh sizing inputs when stale or after another order changes commitments;
   never reuse an expired sizing table as a standing instruction.
5. Validate and submit each exact account order through the existing helper;
   preserve its account checks, single-use preview records and exact confirmation
   matching. Never bypass warnings/rejections or retry uncertain submissions.
   An account-specific rejection does not authorize changing quantity, percentage,
   accounts, price, duration, or funding source. Report per-account outcomes and
   order IDs; distinguish acceptance from fills. Multiple account orders are
   separate and not atomic; partial success is possible. Do not roll back accepted
   orders or cancel existing orders without explicit instruction.

Example instruction: "Buy GLXY at $13.00 limit, DAY, using 25% of verified
available cash in accounts 0071, 3652 and 6434." This example is not an order.
No default allocation, account selection, new orders, or automated trading is
authorized by saving this workflow. No margin-funded additions.


## Taxable account 3652 wash-sale protection

Owner instruction November 10, 2026: avoid wash sales affecting taxable
Individual account ***3652. Other linked accounts are owner-identified retirement
accounts. This preference persists across project chats and multi-account buys.

Before broker preview or submission:

- Review buys in every selected account for conflicts with ***3652 sales; review
  sells only when the selling account is ***3652. Other accounts' sells do not
  require wash-sale review (owner clarification November 13, 2026). Use the
  read-only scan and inspect relevant transactions, including retirement purchases.
  A scan failure, missing tax-lot evidence, or possible conflict is not clearance.
- For a buy in any account, check for taxable ***3652 loss sales of the same or
  substantially identical securities in the preceding 30 calendar days. Where
  realized lot-level profit/loss is unavailable, treat relevant taxable sales as
  unresolved and stop the affected buy until evidence resolves the risk.
- For a sale in ***3652, verify the selected tax lots and check replacement
  acquisitions in the preceding 30 calendar days across covered accounts.
  Average position cost is not selected-lot basis. Check open buy orders,
  reinvestments and other substantially identical securities; do not assume a
  same-symbol scan captures every possible replacement.
- After a confirmed taxable loss sale, record its date/security and the 30-day
  forward replacement-purchase restriction privately. Future project-chat buys
  must recheck this history. Do not imply that this prevents the owner, other
  systems, dividend reinvestment, spouse accounts or outside brokers from creating
  a subsequent conflict; flag missing external coverage when relevant.
- IRA/Roth IRA purchases can disallow losses on taxable sales; retirement status
  does not remove cross-account risk. Other retirement-plan applicability must
  not be assumed identical without verification. Consult the tax guidance for
  unresolved substantially-identical or retirement-plan questions.
- If a possible conflict or required-data gap exists, do not preview/submit that
  affected order under this workflow. Explain the conflict or missing evidence.
  Do not silently change symbols, accounts, tax lots, price or timing, or cancel
  existing orders. Do not claim "no wash sales guaranteed" from incomplete data.

The existing `wash-sale-check` is advisory, same-symbol, and lacks reliable
lot-level realized P/L. These agent instructions add a stop rule; they do not
change the helper into a tax engine or automatically monitor future outside
trades. No order is authorized by this preference.

Primary reference checked November 10, 2026:
https://www.irs.gov/publications/p550 (Wash Sales). The window includes 30 days
before and 30 days after the loss sale. IRA/Roth replacement purchases can cause
loss disallowance without the usual replacement-share basis increase.


## Fast multi-account cash sizing

Added November 10, 2026 after the owner reported more than two minutes to size
an intraday multi-account purchase. Use the existing v3 **Order Drafts** link
(`/cash-ticket`) for calculations, rather than round trips through chat for each
price change. This page is read-only: it never previews, sends, replaces or
cancels orders. The 3652 wash-sale guard above remains mandatory.

The fresh snapshot makes one combined balance request and parallel per-account
order requests, after one OAuth warm-up. Order coverage starts at UTC midnight
180 days earlier, covering Schwab's maximum 180-calendar-day GTC duration.
The source is Schwab's current account/order API, not cached chart data. Missing
accounts, truncated order lists, unknown statuses and unbounded buy commitments
cannot silently become available cash. Active contingent child buys are
conservatively reserved too. The page displays timestamps and measured elapsed
time. It never uses `availableFunds` or `buyingPower` as cash.

A CASH account can use `cashAvailableForTrading`, capped by cash balance less
remaining buy commitments. Taking the minimum avoids subtracting commitments
again from a figure already net of those commitments. For accounts without a
verified cash-only field, cash balance is only a ceiling: the owner must enter
just-verified net cash without borrowing, after holds, commitments and applicable
costs. Ordinary refresh preserves entered amounts only as unconfirmed drafts;
it does not renew an old attestation. The explicit **Refresh & calculate**
action means the owner has just rechecked those entered net-cash amounts. It
fetches a fresh snapshot, renews that explicit confirmation for at most 30 seconds,
and checks each amount against the new cash ceiling. Never use this button as
a substitute for actually rechecking cash. Other costs are not estimated by
this calculator. Explicit account selections survive a refresh of
the same open ticket, but a new page starts with none selected.

Cash expires after 30 seconds and must also be refreshed after any order, fill,
cancellation, transfer or new commitment. Price and percentage changes on a
fresh ticket use exact integer-cent calculations locally, with whole shares
rounded down. The copy button produces exact **BUY/SELL order drafts for review**, including
account, whole shares, LIMIT price, DAY/GTC and NORMAL session. Drafts are not
submitted orders or authorization to place them. Tax clearance and broker validations are not included in the
calculation latency. No promise of execution speed or fills is made.

The same read-only fast path is available to every project chat:

```bash
python3 scripts/schwab_cash.py snapshot
python3 scripts/schwab_cash.py size --accounts 0071 3652 --price 57.50 --percentage 50
```

The `size` command uses the latest private snapshot only while it is fresh. It
does no network calls. If the API cannot verify cash, leave that account
unavailable unless the owner has supplied a current net cash amount; pass that
explicit amount with `--confirmed-cash LAST4=NET_CASH`. Never invent a
confirmation from historical cash or the cash ceiling. Store no credentials,
full account numbers or hashes in sizing output. The latest sanitized snapshot
lives in gitignored `trading_records/schwab_cash_snapshot.json` with owner-only
permissions; there is no standing trade instruction.

Operational metrics: aim for a fresh five-account balance/order snapshot under
10 seconds on a healthy connection and price/percentage recalculation under
100ms, while maintaining zero oversize-from-rounding, zero margin substitutions
and zero stale-snapshot sizing. These are targets, not broker service guarantees.
Record elapsed time from live read-only checks privately; review slow requests
and blocked cash sources before broadening automation. On November 10 a live
combined balance read took 1.23 seconds and the complete snapshot took 6.53
seconds. These are individual measurements, not percentile benchmarks.

Schwab duration reference checked November 10, 2026:
https://www.schwab.com/content/how-to-place-trade-using-good-till-canceled-on-schwab-mobile


### Calculator input and copy feedback (November 11, 2026)

Selected accounts stay listed in step 2 even when the price, percentage or cash
confirmation is missing or the snapshot expires. Each row explains its next
step. A percentage click cannot calculate shares without a limit price. The
**Refresh & calculate** action lets the owner prepare the inputs first and
explicitly reconfirm just-checked net cash while obtaining a new snapshot.
The 30-second freshness limit is unchanged.

A fresh, complete symbol/price/percentage selection can copy order drafts when
at least one selected account supports a nonzero quantity. Blocked/zero
accounts remain visible in the results table but are omitted from the draft
box and clipboard. Copy contains only complete eligible BUY/SELL lines, with
no header, footer or account-error messages. When all accounts are blocked or
zero, Copy stays disabled and the table explains why. Copying is not submission.
Copy explains any blocking inputs, and clipboard failure exposes a read-only
text box for manual copying. No sizing or execution guards are weakened.


### BUY and SELL order drafts (November 11, 2026)

Choose **BUY** or **SELL**, DAY/GTC, the symbol and limit price, explicit
accounts, then 25/50/75/100%. The visible draft box and **Copy order drafts to
chat** show one exact leg per eligible account, omitting blocked/zero accounts
and explanatory boilerplate from the copied text. Copying never previews or sends
orders. A separate explicit placement instruction and all existing execution
checks are required. There is no new order endpoint.

BUY uses verified net cash as above. SELL uses freshly read stock/ETF long
quantities less all potentially active sell commitments for the same symbol,
including contingent and OCO children conservatively. Partial fills reserve
remaining quantity. Fractional shares are rounded down after percentage sizing.
Cash is not required to close verified long shares; unknown/missing holdings,
short exposure, unknown order states, malformed sell legs or incomplete order
coverage block sell drafts. No position is inferred from earlier snapshots.
Prices are user-entered limits, not live quotes. Estimated proceeds exclude
fees/taxes and do not guarantee a fill or settlement availability.

100% SELL means all available long shares; 50% sells half, rounded down. The
ticket does not enforce owner core/tactical allocations: follow the approved
holding plan before choosing a percentage. Selected tax lots, owner-approved
allocations and taxable/cross-account wash-sale clearance remain mandatory
before any execution. A draft alone does not clear them.

The same shared read-only helper supports sells:

```bash
python3 scripts/schwab_cash.py snapshot
python3 scripts/schwab_cash.py size --side sell --symbol HUT --accounts 0071 3652 1638 --price 60.00 --percentage 50
```

This is a calculation example, not a price recommendation or trade instruction.
The snapshot exposes only masked account suffixes and sanitized equity
quantities. Missing positions or orders remain unavailable. BUY and SELL both
expire after 30 seconds; refresh after any change in commitments.

### Cash-ticket wash-sale scope (November 13, 2026)

The page now runs a read-only 3652 same-symbol scan automatically once accounts,
symbol and limit price are entered. BUY in any selected account checks sales in
***3652 during the preceding 30 calendar days; retirement-account sales do not
trigger this guard. Because realized lot-level profit/loss is unavailable, a
matching taxable sale remains unresolved and blocks the affected buy drafts.

SELL runs this check only when ***3652 is selected. It reads that account's
position cost and replacement purchases across all linked accounts. A potential
loss, unknown basis or incomplete check blocks the 3652 sell draft; other
accounts' sell drafts remain eligible without a wash-sale check. Sizing stays
visible for blocked rows, but their lines are omitted from the draft and copy.

The GET-only `/api/schwab/cash-wash-check` uses
`scripts/schwab_trade.py cash-ticket-wash-check` and cannot preview or submit an
order. BUY history is scoped to 3652; SELL history covers linked accounts.
Missing 3652 linkage/history is unavailable, never an empty successful scan.
Results expire after 30 seconds and must match side, symbol and limit price.
Changing those inputs invalidates the result; late responses cannot approve a
changed ticket. **Refresh & calculate** retries failed/expired checks. Changing
only percentage or selected buy destinations can reuse the same fresh scan.

A successful scan is not tax clearance. Selected lots can differ from average
cost; substantially identical securities, open replacement orders, reinvestment,
outside accounts and future activity still require the execution review above.
This supports the desk's sourced-decision North Star without permitting trades.
