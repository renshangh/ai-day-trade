# Live A/B Entry Classification Review

Review the three original BTC live trades and two SOL cross-checks using entry-time evidence.

Last Updated: 2026-11-10  
Status: Audited; classification refinements proposed, not active  
Audience: Trading Desk owner and maintainers

## Overview

The latest BTC trade is recorded **B1**, not A. At its entry minute it also
passes the unchanged B2 validator, price trigger, support and target checks.
The engine selects B1 first. A recorded route is therefore the branch that
opened a benchmark, not proof that the chart fits only one pattern.

BTC has three completed unique trades in each of 0.1/E1/E2. Their paths and
exits match for these three; they are not nine independent observations. SOL
E1 has two completed trades. All times below are America/New_York **EST**.

The independent audit replays only the persisted live-session prefix, including
its actual warmup, through these recorded exits. It reproduces the saved entry
signals, stops, targets and exit legs exactly. It does not rerun the historical
month, change a worker, revise a saved route or alter strategy parameters.

Evidence: `reports/live_entry_review_20261110T111101Z/REVIEW.json`, individual
`BTC_TRADES.json` / `SOL_TRADES.json`, and `TRADES.csv`. Reproduce the audit with
`python3 scripts/audit_live_entry_types.py`; each audit creates a new folder.

## Three BTC trades

| Trade | Recorded route | Entry reference | Initial stop | First 25% target | Final model exit | Net per initial 1 BTC |
|---|---|---|---|---|---|---:|
| #1 | A | Nov 9 13:08, $74,772.59 | $73,541.70 | $76,039.65 | Nov 9 19:30, $74,999.95; 100% structure exit | +$197.41 |
| #2 | A | Nov 10 02:01, $74,617.9565 | $74,219.93 | $75,364.13 | Nov 10 03:01, $74,668.485; 100% giveback exit | +$20.67 |
| #3 | B1 | Nov 10 04:45, $74,369.01 | $74,012.15 | $75,361.95 | Nov 10 05:14, $74,295.87; 100% turning exit | −$102.87 |

Total +$115.20 per independent initial one-BTC benchmark trade sequence, using
the frozen 2bps/side proxy. None hit its first 25% target; none of these final
exits was a hard-stop fill. These are model references, not broker fills or
actual crypto-fee-adjusted returns. Initial risk/exit rules remain unchanged.

Reference minutes became observable no earlier than the next minute. Actual
service detection was #1 Nov 9 13:09:05.114, #2 Nov 10 02:02:15.388, and #3
Nov 10 04:46:00.841. The current 15-minute entry candles did not need to finish.

### #1: mechanically A, but only three P1-independent phases

The original lows are Nov 8 19:06 $74,387.05, Nov 9 00:36 $74,209.08,
02:29 $73,711.65 and 02:58 $73,629.551. P1 qualifies the first, second and
fourth. The 02:29 low gets only one completed post-D hold before being breached;
P1 treats it as an extension into the same decline, not a fourth independent
phase. The existing original A count nevertheless passes its one-neighbour
mechanical definition, followed by HH $75,474.433 and HL $74,446.3365.

B1 and B2 also qualify at that entry minute under a retained shock scope from
Nov 8 16:45, about 20.38 hours earlier. They use that scope's older D and thus
different risk/target references. Rejecting the A label alone would not prove
the engine could not open a B trade instead. No such counterfactual sequence
is claimed here.

### #2: mechanically A, again only three P1-independent phases

Its lows are Nov 9 19:58 $74,865.45, 20:37 $74,816.295, 21:42 $74,686.581
and 22:43 $74,266.43. The third again fails P1 after only one completed hold.
P1 retains three phases. Original A uses the later HH $74,911 and HL
$74,456.628 and crosses the previous complete candle high at 02:01.

This does not become B automatically: the entry-time detector exposes only A,
with no qualifying B episode. A stricter classification would say
**A-candidate / insufficient independent phases**, not invent a B setup.

Both #1 and #2 were profitable. Stricter A independence is a consistency
proposal, not evidence of improved profit on this sample. P1 remains research
only; it is not active in the original worker.

### #3: B1 selected, B2 also eligible

| Known event | Completed/known time | Actual reference |
|---|---|---|
| Rapid bearish impulse, 04:00–04:15 | 04:15 | Previous close $74,618.9035 to D $74,064.0845; about 3.077 pre-impulse ATR |
| D printed | 04:10; D candle complete 04:15 | $74,064.0845 |
| Rebound, 04:15–04:30 | 04:30 | High $74,394.65, low $74,185.3685, bullish close $74,369.636 |
| Red pullback, 04:30–04:45 | 04:45 | HL $74,203.272 at 04:36; remains above D |
| Local breakout | 04:45–04:46 minute; detected 04:46:00.841 | Previous complete high $74,369.00 + $0.01; entry $74,369.01 |
| Exit | 05:14–05:15 minute; detected 05:15:05.024 | 100% at $74,295.87, turning/new-high failure rule |

The full pre-priority B2 check passes, including the same target and initial
stop. But the original order is A, B1, B2; opening B1 consumes prior entry
history and stops evaluating the later branch for execution. Hence the saved
label is B1. Under stage-exclusive proposed terminology this would be **B2:
shock → rebound → completed HL retest → local breakout**. It is not A: no
qualifying new four-phase A chain is exposed at entry.

The $74,369.01 local trigger is initially below the first rebound high
$74,394.65. The entry minute subsequently reaches $74,401.9425 and closes
$74,398.816, so it would be wrong to say the rebound high was never reclaimed.
Minute OHLC does not reveal exact crossing seconds or guaranteed fill order.
Record local trigger and prior rebound high separately; do not turn every
minor high into a mandatory target or require a new global high.

The loss is gross −$73.14 and proxy friction $29.732976 = net −$102.872976.
It exited above the initial stop; this sample alone does not establish that
the initial stop was too tight or that changing labels would avoid the loss.

The owner's follow-up asked whether the 04:45 entry shows B1 weakness. The
completed 04:45–05:00 bar was actually green: open $74,328.75, high $74,451.86,
low $74,328.21, close **$74,408.43**, above the rebound high $74,394.65. The next
05:00–05:15 bar only marginally extended the high to $74,460.185, then reversed.
Its final close $74,308.292 was below the reclaimed level. That final close is
only known at 05:15, not at the model's earlier 05:14 exit. The stored last-minute
turning signal used the then-observed reference $74,295.87. This is evidence of
failed follow-through after an initially valid local/B2 breakout, not proof
that every B1 must be rejected at entry. Retain the entry-time versus subsequent
failure distinction when researching a future filter.

## SOL cross-check

| Trade | Recorded route | Entry / exit EST | Net per 1 SOL | Classification finding |
|---|---|---|---:|---|
| #1 | B1 | Nov 9 22:51 $85.6962 → Nov 10 01:01 $86.0528 | +$0.3222502 | Shock from Nov 8 16:45 persists about 30.1 hours. Its stored HL $85.0695 is only $0.00415 above D $85.06535, below the existing 0.1-ATR tolerance, so B2 fails. This is not a fresh first-stabilization episode under the proposed description. |
| #2 | B1 | Nov 10 04:45 $85.41505 → 05:30 $85.18305 | −$0.26611962 | Fresh 04:00 shock and independent post-D hold pass. No later qualifying HL is established under the original pullback definition, so B1 is the correct current stage; do not force it into B2 because BTC had a pullback at the same time. |

### New SOL #3 during this review: B1, without independent post-D hold

The initial closed-trade audit above was captured at 06:11 EST. A new SOL entry
subsequently appeared at **06:15 EST, $84.73**, detected at 06:16:05.116,
with initial stop $84.0911768 and first target $87.7639393. Its stored route is
B1. `NEW_SOL_ENTRY.json` preserves the actual saved entry and validator checks.
No later exit or hypothetical P/L is imputed to this entry-only addendum.

The shock candle was 05:30–05:45, about 2.417 pre-impulse ATR downward. The
extended D $84.19835 printed at **06:01**, in the 06:00–06:15 candle. That
same candle became the stabilization reference, high/close $84.72, and the
next minute crossed $84.72 + $0.01. The frozen aggressive validator permits
this; it does not require a separate complete post-D candle.

The already reviewed independent-hold validator **fails** at this entry:
`D candle itself cannot serve as its own post-D confirmation`. Under that
proposed B1 requirement, the earliest eligible boundary would be **06:30**,
after a separate full 06:15–06:30 candle held the same D, with a subsequent
qualifying high break and all other conditions still satisfied. This is a
conditional earliest time, not a forecast or retroactive fill. B2 also fails:
there is no completed rebound and later qualifying HL at entry.

This new case supports keeping the B1 independent-hold distinction explicit.
It does not establish whether the entry will ultimately make or lose money.

## Proposed clearer definitions, not deployed

1. **A: multi-phase reversal.** Preserve the whole parent decline. Require four
   genuinely independent LL/LH phases using the already defined P1 evidence
   (two completed holds, rebound high at least 1 pre-D ATR, a completed close
   at least 0.5 pre-D ATR), then HH and a completed HL. Enter on the approved
   intrabar break of the previous complete candle high. Failing A does not
   imply B; record which other route, if any, independently qualifies.
2. **B1: first post-shock stabilization probe.** Require a causally known
   2-ATR bearish new-low impulse and the previously reviewed independent
   complete post-D hold before a local high break. No HL is claimed. Once a
   completed rebound and qualifying HL exist, classify the stage as B2 rather
   than allowing B1 priority to conceal that evidence. This is a proposed
   semantic restriction; frozen 0.2 remains permissive.
3. **B2: shock-rebound HL retest.** Require the completed rebound, an independent
   later pullback/HL above the original D by the existing tolerance, intact
   support and the same shared local trigger checks. A green inside pause
   alone is not proof that the original pullback detector has established HL.
4. **Scope lifecycle must be explicit.** Show shock origin, D time, rebound and
   current phase. End a first-stabilization phase after its first completed
   rebound; do not call a much later recovery under an old warmup shock a
   fresh B1. No arbitrary hours/bars expiry is selected from these outcomes.
   A later local setup without fresh qualifying shock or full A evidence
   remains continuation/unclassified research rather than being forced into B.

Keep local trigger versus rebound-high reclaim as separate evidence fields.
Keep original parent-D stop, target/exits, costs and risk tolerances fixed.
These are a review protocol for a separate comparison, not optimized parameters
or a claim that the next trade will profit. Do not update the running detector
or rerun the month on the basis of these five outcomes alone.

## Page clarity and preservation

The page now explicitly displays `entry_rule` on each proposal and a recent
trade table containing the recorded route, entry/detection times, original
D/L2, stop/target, actual model exits and per-coin realized leg P/L. The legend
explains P1 is not active and route priority can make labels overlap.

Alpaca can include quote midpoints when a minute has no trades; zero volume is
not fabricated volume and is not proof of an executable trade. See the
[Alpaca market-data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq).
The audit retains the original source observations and reference-only labels.
