# AI Data Center Cycle Dashboard

Monthly check on whether the long-term AI infrastructure buildout thesis behind
the desk's optical and power positions is still intact.

**Last Updated:** 2026-09-08
**Status:** Active
**Audience:** Both

---

## Overview

The purpose of this dashboard is to monitor whether the long-term AI
infrastructure investment thesis remains intact.

The key question is:

**Are hyperscalers continuing to build AI data centers at the scale and pace
required to support continued growth in power infrastructure, networking,
optical interconnects, and related manufacturing?**

This dashboard should focus on fundamental changes in the data center buildout
cycle, not short-term stock price volatility.

## How this fits the desk

**Nothing on the page computes it.** None of the indicators below is visible in
Alpaca bars, so every score is a judgment entered by hand from primary sources:
hyperscaler earnings calls and capex guidance, the quarterly data center market
reports (CBRE, JLL, datacenterHawk), utility interconnection filings, and the
optical and electrical suppliers' own calls. Where the desk does help:

- **Earnings timing** already projects the prints where the inputs change.
  MSFT, ORCL, AMZN, GOOGL and META are all in the universe, so capex guidance
  (section 1) and AI revenue commentary (section 5) arrive on dates the
  calendar shows; AXTI, LITE, COHR, FN and POWL are there for sections 6 and 7.
  Re-score the affected row when one of those prints lands, not just at
  month-end.
- **Daily review** reports the exposure this framework maps. AXTI, LITE, COHR
  and FN sit in the `AI Optical / Interconnect` theme and POWL in
  `AI Power / Datacenter Buildout` (and Industrials), so the two equity sleeves
  in the exposure map correspond to two `universe.py` themes, and each theme's
  book weight is a row on the review's theme-exposure block (a row sums every
  reviewed holding in that theme, not only the names listed here). The crypto
  sleeve sits outside the swing book: the Bitcoin position (held as IBIT) is
  reported by the review but excluded from the risk math by `REVIEW_EXCLUDE`,
  and nothing else in that sleeve is in the journal at all. Its risks are not
  data center risks, which is why it is a separate sleeve here as well.
- **Division of labour.** The Daily review answers where each position stands
  against its own levels *today*. This dashboard answers whether the *reason*
  for owning it still holds. A position can be sitting on support with the
  thesis GREEN, or well above its levels with the thesis RED. Read the two
  together; neither replaces the other.

Scores are logged in `trading_records/cycle-score.csv`; see
[Recording the score](#recording-the-score).

## Overall Status

Use a simple three-level signal:

### GREEN — Thesis Intact
Data center demand, capital spending, construction, and capacity deployment
remain strong.

### YELLOW — Caution
Growth continues, but one or more important indicators are weakening or
projects are being delayed.

### RED — Thesis Deteriorating
Hyperscalers are materially reducing capital spending, projects are being
cancelled, utilization is weakening, or significant excess capacity is
developing.

## 1. Hyperscaler Capital Spending

Track:

- Microsoft
- Meta
- Alphabet / Google
- Amazon / AWS
- Oracle
- xAI
- CoreWeave
- Other major AI infrastructure operators

### Monitor

- Quarterly capex
- Forward capex guidance
- AI infrastructure commentary
- Data center lease commitments
- GPU / accelerator deployment plans

### GREEN
Capex guidance is maintained or raised.

### YELLOW
Capex growth slows materially or one major hyperscaler reduces guidance.

### RED
Multiple hyperscalers reduce capex plans or cancel major AI infrastructure
projects.

## 2. Data Center Construction Pipeline

Track North American data center capacity:

- Capacity under construction
- Planned capacity
- Pre-leasing percentage
- Major project announcements
- Project delays and cancellations

### GREEN
Construction pipeline continues expanding and most new capacity is pre-leased.

### YELLOW
Construction remains strong but project delays increase or pre-leasing weakens.

### RED
Construction pipeline contracts materially and project cancellations become
widespread.

## 3. Data Center Vacancy and Demand

Track:

- Vacancy rate
- Leasing activity
- Rental rates
- Large AI campus commitments
- Future capacity reservations

### GREEN
Vacancy approximately 1–3% and new capacity is absorbed quickly.

### YELLOW
Vacancy rises toward approximately 4–6%.

### RED
Vacancy rises significantly above approximately 6–8% while new supply continues
arriving.

A rising vacancy rate would be one of the clearest early signs that supply is
beginning to exceed demand.

## 4. Power Availability and Grid Bottlenecks

Track:

- Utility interconnection queues
- New generation announcements
- Transmission projects
- Transformer availability
- Switchgear lead times
- Data center power agreements
- Nuclear / gas / renewable power agreements
- Behind-the-meter generation

The key question:

**Is power limiting construction, or is actual data center demand weakening?**

These are very different situations.

### GREEN
Demand remains strong and power shortages are the main constraint.

### YELLOW
Power constraints materially delay data center deployment.

### RED
Utilities begin seeing significant data center project cancellations rather
than simple delays.

## 5. AI Monetization

Track whether AI revenue and usage are eventually supporting the infrastructure
investment.

Monitor:

- Cloud AI revenue growth
- AI inference demand
- AI service utilization
- Hyperscaler AI revenue commentary
- Return on invested capital
- Free cash flow versus capex
- Depreciation growth

### GREEN
AI revenue and usage continue growing rapidly.

### YELLOW
AI infrastructure investment grows much faster than AI-related revenue for
several quarters.

### RED
Hyperscalers explicitly reduce investment because AI infrastructure returns are
below expectations.

## 6. Networking and Optical Demand

This is especially important for:

- AXTI
- LITE
- COHR
- FN

Track:

- 800G shipments
- 1.6T adoption
- 3.2T development
- Silicon photonics adoption
- CPO deployment
- InP laser demand
- CW laser demand
- Optical module lead times
- AI network bandwidth growth

### GREEN
800G continues growing, 1.6T ramps strongly, and CPO / next-generation optical
architectures progress.

### YELLOW
Optical demand remains healthy but customer inventory or deployment delays
appear.

### RED
Major hyperscalers materially reduce AI networking deployments or optical
suppliers report broad order cancellations.

## 7. Power Infrastructure Demand

Especially relevant to:

**POWL**

Track:

- Switchgear backlog
- Electrical equipment orders
- Transformer demand
- Data center electrical infrastructure orders
- Utility investment
- Large industrial power projects

### GREEN
Backlogs and orders remain strong.

### YELLOW
Backlog growth slows but remains elevated.

### RED
Orders decline significantly and project cancellations begin appearing.

## Portfolio Exposure Map

### Digital / Crypto

- BTC
- ETH

Primary risk:

- Liquidity
- Interest rates
- Regulatory changes
- Crypto adoption
- Risk appetite

### AI Optical Infrastructure

- AXTI
- LITE
- COHR
- FN

Primary risk:

**AI data center networking deployment slows materially.**

### Power Infrastructure
POWL

Primary risk:

**Data center and utility electrical infrastructure spending slows.**

## Four Primary Warning Signals

These are the most important indicators to watch.

### 1. Hyperscaler Capex Cuts

One company reducing capex is not necessarily important.

Multiple hyperscalers cutting AI infrastructure spending simultaneously is a
major warning.

### 2. Data Center Pre-Leasing Deteriorates

If developers are constructing large amounts of capacity without committed
tenants, risk increases materially.

### 3. Vacancy Rises Rapidly

A sustained increase from approximately 1–2% toward 5%+ should receive close
attention.

### 4. Project Cancellations Replace Project Delays

This distinction is critical.

**Delay because electricity is unavailable = demand may still be strong.**

**Cancellation because the customer no longer wants the capacity = demand is
weakening.**

## Monthly Data Center Cycle Score

Score each category from 0 to 2.

| Indicator | Score |
|---|---:|
| Hyperscaler Capex | 0–2 |
| Construction Pipeline | 0–2 |
| Pre-Leasing / Vacancy | 0–2 |
| Power / Grid Demand | 0–2 |
| AI Monetization | 0–2 |
| Optical Demand | 0–2 |
| Electrical Equipment Demand | 0–2 |

Maximum score: **14**

### 11–14: GREEN
AI infrastructure cycle remains strong.

### 7–10: YELLOW
Remain invested but become more selective and preserve dry powder.

### 0–6: RED
Reassess the core AI infrastructure thesis and portfolio exposure.

## Investment Principle

Do not reduce a position simply because the stock price falls.

Reduce exposure when the **fundamental data center buildout thesis
deteriorates**.

Likewise, do not increase exposure simply because a stock becomes cheaper.

Add when:

1. The long-term infrastructure thesis remains GREEN,
2. Company fundamentals remain intact,
3. The stock has corrected without a corresponding deterioration in the
   underlying business.

## Core Question

Every monthly review should end by answering:

**If I were 100% in cash today, based on the current data center construction
outlook, would I still want to own AXTI, LITE, COHR, FN, and POWL at their
current portfolio weights?**

If the answer changes, identify exactly which underlying assumption changed.

## Recording the score

One row per monthly review in `trading_records/cycle-score.csv`. Unlike the
rest of `trading_records/`, this file is tracked in git and pushed: it holds
0-2 judgment scores and research notes, not positions or account details, so
there is nothing in it that needs to stay off the public remote. The
template it follows, `trading_records/TEMPLATE-cycle-score.csv`, is
committed too. The seven score
columns follow the table above in order, then `total`, `status`, the answer to
the core question, and what changed. The column meanings are in
`trading_records/README.md`.

The desk's **Cycle** view is the form for this file. It shows each indicator's
GREEN / YELLOW / RED criterion, read from this document, beside its score,
writes one row per save, and replaces the row for a date you save again. It
refuses to write to a file whose header differs from the template, so the log
stays readable by hand and by the page alike.

Two rules, both borrowed from how the rest of the desk treats data:

- **An indicator you did not check this month stays blank.** Copying last
  month's score forward records a judgment nobody made. Leave `total` and
  `status` blank too when any of the seven is blank; a partial total is not
  comparable to a full one.
- **`assumption_changed` is written only when the core question's answer moved.**
  Otherwise write `unchanged`. The point of the column is to force the
  sentence "X was true last month and is not true now", not to collect
  commentary.
