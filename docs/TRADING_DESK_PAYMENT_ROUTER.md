# Trading Desk Payment Router

Specification for the private Ren-to-Anthony $10 payment prototype.

**Last Updated:** 2026-09-28
**Status:** Proposed MVP specification
**Audience:** Trading Desk, payments, security, and implementation teams

## Overview

Ren asks ChatGPT to pay Anthony **$10 using the cheapest permitted crypto he accepts**. A private Trading Desk Payment plugin calls a Payment MCP server. The server discovers Anthony's verified settlement preferences, compares executable routes, obtains approval for one immutable transaction proposal, submits it through a constrained wallet, and returns a verified receipt. Anthony's ChatGPT may help publish preferences or inspect the receipt; it is not a settlement dependency.

This document specifies interfaces and invariants. Chain, token, protocol, wallet, and fee support must be enabled only after integration and compliance review. No transaction is authorized by this document.

## MVP wallet decision

Use **MetaMask Mobile on Ren's phone** as the self-custody payer wallet. **Circle-issued native USDC on Arbitrum One is a candidate route, not a mandatory destination.** Compare it with every other route the deployed connectors can actually quote, the recipient accepts, policy permits, and Ren's wallet can fund. If it is cheapest, recommend it; if another eligible route is cheaper, recommend that one. Check each token contract against its issuer's current official registry before implementation so bridged USDC is not mistaken for native USDC. Never claim a global cheapest route when the system covers only a subset of networks or providers; state the comparison scope.

The Payment MCP server prepares and tracks the payment; it does not hold Ren's seed phrase or sign on his behalf. A Trading Desk approval page connects to MetaMask Mobile through MetaMask Connect (mobile deep link or in-app browser), displays the frozen proposal, requests the wallet transaction, and returns the transaction identifier to the server for independent verification. The ChatGPT tool response may link Ren to that page; a ChatGPT tool call by itself cannot authorize a wallet signature. The first prototype therefore requires Ren to approve each payment in MetaMask. Agent-controlled or delegated spending is a later design with a separate wallet and explicit limits.

## Trust boundaries

1. **ChatGPT/plugin authorization:** Ren may invoke discovery and quoting; write actions must be explicitly allowed by the workspace and require a user approval for the exact proposal.
2. **Router policy:** Allowlisted chains, assets, protocols, contracts, spend limits, recipient rules, quote age, and fee/slippage ceilings filter candidate routes.
3. **Wallet policy:** The signer independently enforces account, chain, recipient or contract, asset, amount, and daily limits. The MCP server cannot bypass it.
4. **Transaction policy:** A signed, expiring proposal binds payer wallet, Anthony's verified recipient address, chain, token and token contract, exact delivered amount, maximum debit, maximum fee, maximum slippage, approved contract targets and calldata hash, nonce/sequence, and expiry. Any material change requires a new quote and approval.

Secrets and private keys stay outside ChatGPT and the MCP server. The wallet signs only after verifying the approved proposal and transaction policy. An authenticated user action is required at the approval step; an LLM message alone is insufficient.

## MCP tools

| Tool | Inputs | Output | Effect |
|---|---|---|---|
| `payment.get_recipient_options` | `recipient_id` | Signed/verified options, validity, provenance | Read only |
| `payment.quote` | `recipient_id`, `delivered_amount`, `currency`, optional payer preferences | Route candidates, exclusions, all-in costs, quote expiry | Read only; no funds reserved |
| `payment.prepare` | `quote_id`, `route_id`, `idempotency_key` | Immutable proposal, human-readable approval summary, policy checks, expiry | No signing or broadcast |
| `payment.execute` | `proposal_id`, approval artifact, `idempotency_key` | Execution state and transaction identifier when submitted | Funds-moving; requires exact approval |
| `payment.get_status` | `proposal_id` | Pending/confirmed/failed state and evidence | Read only |
| `payment.get_receipt` | `proposal_id` | Verified receipt or explicit unverified status | Read only |

`execute` rejects stale quotes, changed recipients, missing approvals, modified transaction fields, duplicate submissions, and proposals whose on-chain nonce or expiry no longer matches. A repeated request with the same idempotency key returns the existing operation. Discovery data from Anthony is untrusted until authenticated and bound to his identity; a free-text ChatGPT response is never sufficient to select an address.

## Data model

Amounts are integer minor units or integer token base units. Display decimals are derived from a verified token registry. USD pricing uses a timestamped, identified source and is never represented as guaranteed settlement value.

- `RecipientOption`: `recipient_id`, `chain_id`, `asset_id`, `token_contract` (or native asset marker), `address`, `min_amount`, `max_amount`, `valid_until`, `verified_at`, `verification_method`, `preference_signature` or trusted directory record.
- `RouteQuote`: `quote_id`, `route_id`, input asset/chain/amount, output asset/chain/address/amount, ordered protocol and contract hops, source of liquidity, network fees, protocol fees, bridge fees, price impact, slippage bound, total payer debit, estimated delivered USD value, quote timestamp/expiry, and per-component provenance.
- `PolicyDecision`: policy version, allow/deny result, reason codes, evaluated route hash, limits consumed, and evaluation time.
- `PaymentProposal`: immutable canonical payload and hash, quote and route IDs, payer account, recipient option snapshot, exact or minimum delivered amount, maximum total debit, fee/slippage caps, contract allowlist, calldata hash, nonce, expiry, policy decision, and approval summary.
- `ApprovalArtifact`: authenticated approver, proposal hash, approval time, expiry, one-time approval ID, and authorization scope. It must be bound to the exact proposal, not merely to “$10.”
- `Execution`: proposal ID, idempotency key, signing result, broadcast time, chain transaction hash/signature, finality state, actual debit and receipt amounts, failure reason, and audit timestamps.
- `Receipt`: chain ID, transaction identifier, block/slot and confirmation depth, payer and recipient, asset and actual received amount, fees, explorer reference, independently queried chain evidence, and verification status.

Persist proposals, approvals, policy decisions, route inputs, transaction IDs, and state transitions in an append-only audit trail. Store only the minimum personal data needed for reconciliation; redact secrets and sensitive wallet metadata from model-visible responses.

## Route selection

1. Resolve Anthony's authenticated, unexpired recipient options. If none exist, stop and request verified settlement details.
2. Enumerate executable routes from Ren's funded, permitted payer accounts to each accepted option. Include direct transfer routes; add Circle, Uniswap, or Solana infrastructure only where the actual connector and policy support it.
3. Reject any route with an unapproved chain, asset, protocol, contract, recipient, or signer; insufficient balance; unavailable live quote; stale price or gas estimate; excessive fee/slippage; unsupported finality model; or amount outside limits. Missing cost components make a route ineligible, never zero-cost.
4. Normalize costs into the payer's funding currency using contemporaneous, attributed rates. For each route, calculate **all-in payer debit** = principal + swap spread/price impact + protocol and bridge fees + origin/destination network fees + any wallet/service fees. Require the expected net receipt to satisfy the $10 delivery target under the configured tolerance. Show both monetary cost and quote uncertainty.
5. Choose the lowest all-in eligible cost. Break near ties deterministically by lower execution risk, fewer hops, shorter expected settlement, then stable route ID. If estimates overlap materially or exceed the configured uncertainty bound, present options rather than claiming one is cheapest.
6. Tell Ren which route is cheapest among those checked, its all-in debit and expected net receipt, and at least one next-best eligible alternative when available. Distinguish a cheaper **unavailable** route (for example, unsupported wallet, insufficient funds, expired quote, or rejected protocol) from an eligible route. If no route is executable, explain why and show practical alternatives such as funding the wallet, using another accepted chain, or waiting for a fresh quote; do not offer a pay action.
7. Re-quote the chosen route immediately before preparation. If it remains available within the displayed maximum debit and transaction policy, show the exact transaction for Ren to confirm in MetaMask and then submit it. If its cost or terms change, stop and show the revised route or next-best eligible option for fresh approval. Freeze the approved route into the transaction policy; any later material change invalidates approval.

The MVP must define whether “$10” means **Anthony receives at least $10 equivalent** or **Ren spends at most $10**. This specification uses the former, with Ren shown the maximum total debit before approval. A route that cannot guarantee the minimum token amount or the policy's valuation tolerance must be rejected or shown as uncertain.

## Ren → Anthony sequence

| Step | Actor | Action and required evidence |
|---:|---|---|
| 1 | Ren → ChatGPT | “Pay Anthony $10 using the cheapest permitted crypto he accepts.” |
| 2 | Plugin → MCP server | Request verified recipient options; identify Ren's authorized payer accounts. |
| 3 | Router → recipient directory | Validate Anthony's identity, address ownership/provenance, accepted chains/assets, and expiry. |
| 4 | Router → route connectors | Obtain live quotes for supported direct, swap, or cross-chain routes; record source and expiry. |
| 5 | Router policy | Reject disallowed or incomplete routes; rank eligible routes by all-in cost and risk rules. |
| 6 | MCP server → ChatGPT → Ren | Identify the cheapest eligible route among checked routes; show comparison scope, recipient, chain, token, delivered amount, max total debit and fees, protocol/contracts, expiry, and next-best options. If none is executable, explain blockers and alternatives without a pay action. |
| 7 | Ren → Trading Desk approval page | Review the exact proposal on his phone; open MetaMask Mobile and approve the wallet transaction. The approval record binds to the proposal hash. |
| 8 | Wallet policy → MetaMask signer | Verify approval, proposal hash, nonce, expiry, limits, recipient, contract targets, and calldata; request one signature from MetaMask. |
| 9 | Executor → blockchain | Broadcast using the idempotency key; record transaction hash/signature and pending state. |
| 10 | Verifier → blockchain | Independently check finality and actual received amount; classify failure or partial settlement explicitly. |
| 11 | MCP server → Ren | Return the transaction identifier and verified receipt; if still pending, return pending status and a way to recheck. |
| 12 | Anthony | Optionally verify the receipt independently; Anthony's ChatGPT has no authority over Ren's wallet. |

## Acceptance test

Use a funded, low-value test account and a verified Anthony-controlled destination. The test passes only when: (1) at least two eligible routes are quoted when infrastructure supports them, with rejected routes and reasons visible; (2) the selected route has the lowest comparable all-in cost under the rule above, regardless of whether that is Arbitrum; (3) the user sees a next-best option or a concrete reason no alternative is executable; (4) execution cannot occur before exact authenticated approval; (5) tampering with amount, recipient, chain, token, contracts, fee, or expiry invalidates approval; (6) retries cannot double-pay; and (7) the returned transaction identifier resolves to independently verified final settlement and the intended net receipt. Also test an unavailable cheapest quote: no payment occurs on that route, and the router offers the next eligible route for new approval. If live routes cannot meet these conditions, report the missing capability rather than fabricating quotes or a receipt.

Before a real $10 payment, confirm supported chains/assets, Anthony's verified address and accepted options, Ren's wallet/provider, regional and compliance constraints, fee ceiling, finality threshold, and the valuation tolerance for “$10.”
