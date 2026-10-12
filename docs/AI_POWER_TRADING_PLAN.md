# AI Power — Nuclear Trading Plan

A sourced market assessment and conditional swing-trading framework for nuclear equities.

**Last Updated:** 2026-10-09
**Status:** Active research; proposed orders only
**Audience:** Trading Desk owner and contributors

## Overview

The objective is repeatable risk-adjusted returns with sourced decisions and
explicit invalidation. Weekly leading indicators: rule adherence, recorded
initial risk, maximum drawdown and unplanned event exposure. Targets: every
entry has a stop thesis and at least 2R to its first defensible target; no adds
through invalidation. Realized R is only recorded when actual entry risk exists.

**Assessment:** selective recovery among operating producers; the broad nuclear
bottom is not confirmed. The October 8 completed-session snapshot contains all
12 watchlist members with enough data for 50-session comparisons. Six are above
their 50-day averages. Equal-weight 5-session return is +4.58%, but 21-session
return is -6.05%, versus SPY +1.30%/+1.76% and QQQ +0.75%/+4.47% respectively.
NLR (-16.73% over 21 sessions) and URA (-17.71%) remain weak cross-checks.
These funds differ in composition; neither is an exact replica of this basket.

CEG/VST/TLN are above their 50-day averages. BWXT is near its 20-day but below
its 50-day; CCJ is below its 20-, 50- and 200-day averages. CEG's October 8 close
of $285.07 lost the October 6 event-day low of $291. The catalyst rally needs a
successful retest before it deserves larger capital. All price calculations use
actual Alpaca SIP observations from the existing desk endpoint, excluding October
9's unfinished candle. Frozen real observations accompany the regression tests.

## Fundamental evidence

- [CEG / Google, October 6](https://www.constellationenergy.com/news/2026/10/google-and-constellation-announce-landmark-agreement-to-bring-890-mw-of-new-nuclear-capacity-to-pjm-grid.html):
  890 MW of uprates under a 20-year PPA, first output expected 2028; a separate
  2,700 MW, 15-year existing-generation agreement. $4.3B is planned investment,
  not disclosed contract revenue. Reconcile overlap before adding prior PPA MW.
- [CEG Q2, August 6](https://investors.constellationenergy.com/news-releases/news-release-details/constellation-reports-second-quarter-2026-results):
  adjusted EPS $2.55 and annual guidance $11.50–$12.50. The 920 MW of contracts
  start in 2029–2032. The October 9 transcript is an older call republished.
- [VST Q2, August 7](https://investor.vistracorp.com/2026-08-07-Vistra-Reports-Second-Quarter-2026-Results):
  ongoing adjusted EBITDA $1.767B; annual guidance reaffirmed. Most near-term
  generation is hedged; spot power prices do not flow immediately into earnings.
- [BWXT Q2, August 3](https://www.bwxt.com/bwx-technologies-reports-second-quarter-2026-results/):
  commercial manufacturing and PCG support growth. Require actual supplier
  awards; no specific BWXT award is inferred from CEG's Google deal.
- [CCJ Q2, July 31](https://www.cameco.com/media/news/cameco-reports-2026-second-quarter-results):
  uranium contracting, fuel services and Westinghouse support the longer thesis.
  Deliveries and project timing can dominate quarterly results.
- [DOE UPRISE](https://www.energy.gov/ne/articles/nations-nuclear-reactor-fleet-rise)
  favors uprates, restarts and stalled-project completion.
- [FERC large-load proceeding](https://ferc.gov/news-events/news/e-7-commissioner-lacertes-concurrence-pjm-interconnection-llc-docket-no-el26-67)
  is evidence of regulatory work, not a blanket completed approval.

Risks: capital cost overruns, outage performance, load delays, cost allocation,
customer concentration, interest rates, hedging, valuation and shared AI risk.
The catalysts support existing generation more immediately than speculative new
reactor development. Good company evidence alone does not establish a stock bottom.

## Allocation and execution

Proposed additional cash cap: $18,000, subject to cash and a 12% total nuclear
allocation cap in the selected account. Existing holdings count toward the cap.
POWL is adjacent power exposure; review it separately in aggregate theme risk.

| Name | Additional ceiling | Conditional setup, October 9 references |
| --- | ---: | --- |
| CEG | $8,000 | Stabilization at $280–286; proposed stop $278, first target $309.80. Alternative breakout needs a new retest and recalculated reward. |
| VST | $4,000 | Stabilization at $151.50–156; proposed stop $149, target $168.75; cap entry at $155.58 to preserve 2R. |
| BWXT | $3,000 | Close above $147 then successful $146–147 retest; proposed stop $141.50, target $158. |
| CCJ | $3,000 | Close above $90–91 then retest near $90; proposed stop $87.80, target $94.57. Entry above $90.06 fails 2R. |
| TLN | $0 | Alternate producer candidate instead of VST; no extra funded allocation. |

Reference targets are prior observed highs/nearby resistance, not price forecasts.
Proposed stops are discretionary invalidations, not observed fills or broker orders.
Prices require a fresh check before any order. The narrow CCJ and BWXT entries can
be skipped if spreads/slippage remove the 2R margin. Existing shares require their
own lot/stop decision; a new-add setup is not automatically their stop.

Tranches per symbol: 25% of budget on a qualifying setup, 35% after two closes
above the 50-day and a successful retest with >=60% breadth, final 40% after all
broad recovery conditions hold for two completed sessions and positions work.
Unused allocations stay cash. No automatic replenishment after a losing trade.

Risk per new position <=0.15% of account equity; total added open risk <=0.5%.
Count pending orders, existing position risk and correlated exposure before adding.
Quantity is floor(min(risk / (entry-stop), tranche cash / entry)). Require >=2R
before costs, with additional room for costs in execution. Planned loss is not a
maximum loss in gaps. No leverage is used in this plan.

At +2R consider taking one-third off and trailing the rest under a confirmed
higher low. Do not widen stops. Review after five stagnant sessions; exit by ten
if follow-through never arrives. Avoid new entries within two sessions of an
issuer-confirmed earnings date unless explicitly trading the event. After two
failed entries in a name, pause three sessions and require a new base.

## Dashboard implementation and verification

`trading_desk/ai_power.js` / `.css` render only on the Hot Sector Board at
`/board?view=ai-power`. The home page does not load the AI Power assets or
mount the research desk. Chart links on the board use the existing
chart-selection path.

Market reads use the existing `/api/stock` endpoint in four concurrent workers.
Today in New York is excluded even after the close; its bar becomes eligible the
next calendar day. Each 50-session window must align to SPY's sessions. No rows
are interpolated or carried forward; stale/invalid inputs block confirmation.
Unavailable 200-day averages remain blank for newer listings. A reading older
than four calendar days cannot confirm recovery. This conservative calendar-age
rule may temporarily block a valid reading after an unusually long closure.

Five criteria must hold now and on the preceding completed session: >=60% above
50-day; equal-weight 5- and 21-session returns each beat SPY and QQQ; >=2/3
producers above 50-day; >=60% have a higher minimum low over the last five sessions
than the previous five. This low-window comparison is a proxy, not a confirmed
swing-pivot pattern. The rubric is discretionary and unbacktested.

The page labels source dates and keeps static analyst interpretation separate
from refreshable readings. Refreshing data does not update the dated trade plan.
Private positions are loaded read-only. Sourced daily notes share the existing
revision-checked v3 store. No timer or automatic order action is created.

Run `node --test trading_desk/tests/test_ai_power.cjs`. Tests cover actual sourced
observations, incomplete-day exclusion, missing/stale/invalid data, insufficient
history, risk limits and source validation. UI checks cover both surfaces,
chart selection, calculator and narrow-width layout.
