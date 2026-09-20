# SCHWAB_API.md

> How to get your own Charles Schwab developer app approved and make your first real API calls, using `scripts/schwab_api.py`.

**Last Updated:** 2026-09-11
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

The skill calls `scripts/schwab_trade.py`; it does not add trading controls to the
Trading Desk. Its order scope is deliberately small:

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
