# Trading Desk — Hot Sector Board

Local dashboard that screens sectors and themes over short horizons — for momentum
or for reversals — and charts the resulting movers with the standard technical
indicator set.

**Last Updated:** 2026-09-10
**Status:** Active
**Audience:** Both

---

## Overview

Two screens share the same universe, lookback tabs, chart and company panel. A
**View** toggle switches between them.

**Momentum** — for each lookback window (1, 2, 3, 4 and 5 trading days):

1. ranks all 14 groups (11 GICS sectors + 3 themes) by the equal-weight mean
   return of their constituents,
2. surfaces the hottest group, and
3. lists that group's 5 best performers, each chartable with full indicators.

**Reversal candidates** — the opposite setup, for windows of 2–5 days: groups that
were *down* over the prior period and turned positive on the most recent session,
ranked by how many members reversed. See
[Reversal candidates](#reversal-candidates) for the qualification rules.

Data comes from the Alpaca market data API using the paper credentials already
in the repo-root `.env`.

**Feed:** the server prefers the **SIP consolidated tape** (all US venues) with a
16-minute-delayed request window, and falls back to **IEX** if the subscription
refuses SIP. The feed in use is shown in the page header and in `/api/health`.
IEX is real-time but is a single venue carrying only ~2.5–4% of consolidated
volume, so IEX volume understates true liquidity by roughly 25–40× (measured:
AXTI 488k shares on IEX vs 19.2M on SIP for the same session). Closes agree to
within 0.2%, so rankings are the same either way — but liquidity is not worth
being an order of magnitude wrong about. Since the board runs on daily bars, the
16-minute cutoff costs nothing.

## Run it

**One click (macOS):** double-click **`Launch Trading Desk.command`** in Finder.
It starts the server, waits for it to become healthy, and opens the dashboard in
your default browser automatically. If a healthy dashboard is already running on
this branch's port, it just opens that instead of starting a second copy; if the
port is occupied by something that is *not* a healthy dashboard, it says so and
stops rather than starting somewhere unexpected. To stop it, close that Terminal
window or press Ctrl+C in it — the server is not left running in the background.

**Manual:**

```bash
python3 trading_desk/server.py
```

No `--port` needed: the server binds the port its **branch** owns.

### One fixed port per branch

| Branch | Port | URL |
|---|---|---|
| `main` | **8800** | <http://localhost:8800> |
| `dev` and every topic branch | **8799** | <http://localhost:8799> |

The branch is read from `.git/HEAD` (one file read, no subprocess, works when
git is not on PATH, follows the `gitdir:` pointer used by worktrees, and degrades
to "unknown" on a corrupted HEAD rather than refusing to start).

`BRANCH_PORTS` in `server.py` is the single source of truth. The shell launcher
does not restate it — it asks:

```bash
python3 trading_desk/server.py --print-port   # prints this branch's port, exits
```

That matters beyond tidiness: the launcher used to detect the branch with
`git rev-parse`, a second mechanism that disagrees with the server's whenever git
is missing from PATH — the exact case `.git/HEAD` parsing exists to handle.
`.claude/launch.json` still names its ports (the preview needs the URL up front)
and `tests/test_ports.py` asserts they match, including that no config
reintroduces `autoPort` and that the launcher has not gone back to scanning.

Precedence, most explicit first: `--port`, then the `PORT` env var (set by the
preview launcher), then the branch's port.

**Why pin, and why fail instead of falling back.** Three things used to pick a
port independently — the preview launcher's `autoPort`, this launcher scanning
8799-8803, and `PORT` — so the dashboard turned up somewhere different most times
it started. The real damage was subtler than the inconvenience: a stale server
from an earlier session kept answering on the port you expected while serving old
code, which reads as "my change did nothing". So an occupied port is now a hard
error naming the port and how to find the process, not a quiet hop to the next
one:

```
ERROR: cannot bind 127.0.0.1:8799 (branch default) -- [Errno 48] Address already in use
       Something is already using it. Find it with:
         lsof -nP -iTCP:8799 -sTCP:LISTEN
       then stop that process, or pass --port to use another.
```

A topic branch shares dev's port on purpose. Giving each one its own would
recreate exactly the drift this removes.

### "Already running" is not the same as "running your code"

Pinning the port stops a *new* server landing somewhere unexpected. It does
nothing about an **old** server already holding the right port — and a stale
server answers `/api/health` perfectly well, which is precisely how a build from
before a change kept serving the URL you were refreshing.

So `/api/health` reports the branch the process was started from:

```json
{ "ok": true, "branch": "dev", "port": 8799, "feed": "sip", ... }
```

and the launcher compares that against the checked-out branch. Same branch, it
opens it. Different branch, it stops and tells you which one is running and how
to kill it, rather than opening a dashboard that does not match your code.

This does not catch a server started from the *same* branch before a commit — for
that, restart after touching `server.py`. Python routes load once at startup.

**Running `main` and `dev` at the same time** needs two working trees, since one
checkout is on one branch at a time:

```bash
git worktree add ../ai-day-trade-main main
python3 ../ai-day-trade-main/trading_desk/server.py   # binds 8800
python3 trading_desk/server.py                        # binds 8799
```

Python routes load once at startup, so **restart after changing `server.py`**;
`app.js`, `index.html` and `style.css` are read from disk per request and only
need a browser reload.

## What's on the page

| Section | What it shows |
|---|---|
| View tabs | Momentum / Reversal candidates / Earnings timing / Daily review / Cycle / Sector. The first two scope the hero, ranking, movers strip and table; the last four replace them. |
| Lookback tabs | 1D–5D for momentum, 2D–5D for reversal. Scopes the whole board. |
| Hottest group | Mean, median, breadth, vs SPY, and the ETF proxy return. |
| Top reversal candidate | Prior decline, bounce, reversal breadth, vs SPY today, volume ratio. |
| Group ranking | All 14 groups as a diverging bar chart; click a row to load its leaders. |
| Top 5 | The leaders inside the selected group, with a 30-day sparkline. |
| Detail chart | Candlesticks + overlays, with volume, RSI and MACD panes on a shared crosshair. |
| Company detail | Market cap, trailing P/E, 52-week range, volatility, SEC filings, news, research links. |
| Earnings timing | Upcoming prints (including today's, before they land) with an uncertainty window, expected timing, 1-day and 1-week reaction stats, and held-position alerts. |
| Daily review | Every open lot in the journal against its own levels: P&L, nearest support/resistance in ATR as well as percent, downside to support, and the journal's own recorded gaps. |
| Cycle | The monthly AI data center cycle score: the latest GREEN / YELLOW / RED reading and total, the eight indicator scores against the criteria they were scored on, a trend of past reviews, the history table, and the form that writes the next review to the log. |
| Sector | A scorecard of measured facts about one universe.py group's own recent price/volume history -- relative strength vs its benchmark (and whether that excess is widening or narrowing), breadth above its own moving averages, new highs/lows, participation, volatility, dispersion, and how many constituents sit near a level. Any group is selectable; nothing here is scored, banded, or turned into a call. See Sector scorecard below. |
| Ranking table | The same board in text form — every value readable without color. |

### Company detail

Below the chart, for the selected symbol:

- **Key stats** — market cap (SEC shares outstanding × last price), trailing P/E,
  TTM diluted EPS, 52-week range with the current position marked, ATR-based
  daily volatility, TDR(14) (see below), and 20-day average / dollar volume.
- **Latest SEC filings** — revenue, gross profit, operating income, net income,
  EPS, R&D, assets, liabilities, equity, cash, and operating cash flow. Every
  row shows the form (10-K/10-Q), the period it covers, and the filing date.
- **Recent news** — headlines from the Alpaca News API, linked to the source.
- **Research & analyst coverage** — links out to Yahoo Finance analysis, Finviz,
  StockAnalysis, TradingView, and the company's SEC EDGAR filing index.

#### TDR (14) — and why it sits next to ATR

**TDR(14)** is the 14-session mean of the intraday range, `high - low`, in dollars.
It is shown as a dollar figure, as a percentage of price, and with the shortfall
against ATR.

It is deliberately *not* ATR, and the pair is more useful than either alone:

| | Range measure | Smoothing | Gaps |
|---|---|---|---|
| **ATR(14)** | true range — `max(H-L, \|H-prevC\|, \|L-prevC\|)` | Wilder | **counted** |
| **TDR(14)** | `H - L` | simple mean | **ignored** |

So `(ATR - TDR) / ATR` is the share of average daily range that arrives as an
**overnight gap** rather than as intraday movement — reported on the tile as
"N% of ATR is gap, not intraday".

That distinction has a practical consequence: an intraday stop can only protect
against the TDR part. Range that shows up as a gap jumps straight past a stop at
the open. Two names with the same ATR are not equally stoppable if one gets there
by gapping. Measured on the current universe, the spread is real — AXTI sits near
1% gap share (its large ATR is almost entirely intraday) while MU is around 13%.

Both are computed over the same 14 sessions so the comparison is apples-to-apples,
and the warmup region is `null` rather than zero-filled.

#### How P/E is computed

Companies do not file a Q4 10-Q, so the four most recent quarters are never all
present as quarterly XBRL rows. TTM diluted EPS is reconstructed as:

```
TTM = last full fiscal year + current year-to-date - prior-year year-to-date
```

The exact arithmetic is shown under the P/E tile, so the figure is auditable. If
that reconstruction is not possible, P/E reads `n/a` with the reason rather than
falling back to a single quarter's EPS (which would understate it ~4×). Negative
trailing earnings show `n/a` rather than a meaningless negative multiple.

Where a company has migrated XBRL revenue tags, the tag with the most recent
period wins — picking by a fixed tag order would surface a long-abandoned tag as
if it were current.

### Earnings timing

Projected dates come from each company's own 8-K item 2.02 history; see
`earnings.py` for the method and its measured accuracy (**median error 2 days,
p90 7 days**, 90.9% within a week, 97.1% within two, measured over 1437
no-lookahead projections). Every date is an **estimate**, never a confirmed
announcement.

Only the **last 8 prints** define the reporting cadence. Anniversarying all of
history let a stale slot win -- a company that once reported Aug 2 but now
reports mid-August projected two weeks early -- which cost median accuracy 2d ->
5d and p90 8d -> 13d while the page still advertised +-8. Depth was picked by
measurement across 4/6/8/12/16/unbounded; 8 (two years of quarters) was best.

**Today counts.** A company reporting after tonight's close is still ahead of
you, so today is a valid projection. This needed several fixes: the guard
demanded a strictly future date; slot selection stepped 364 days, landing one day
*before* today and skipping a full year; and the weekend shift leaned a Saturday
anniversary back to Friday, which fell before today, tripped the never-past guard
and removed the symbol from the calendar entirely -- then projected ~362 days out
the next day.

Now the anniversary picks the slot, the weekday snap and weekend shift are both
floored at today (Saturday moves forward to Monday when Friday is out of range),
and a slot that has genuinely passed advances **one quarter, not one year**. No
symbol is left unprojectable.

**Reaction stats cover two horizons**, because they answer different questions:

| Column | Meaning |
|---|---|
| `Typ \|1d\|` | median **absolute** 1-session reaction -- how violent the print usually is |
| `Worst \|1d\|` | largest absolute 1-session reaction on record -- the tail, not the middle |
| `Lean 1d` | median **signed** 1-session reaction -- which way it has historically gone |
| `Typ \|1w\|` | median absolute move over 5 sessions |
| `Lean 1w` | median signed move over 5 sessions |
| `Up/Dn` | historical up/down split of the 1-session reaction |
| `n` | number of past prints behind the figures -- distrust a small sample |

Both horizons are measured from the **same pre-earnings close**, so the 1-week
figure *includes* the initial gap rather than starting after it -- that is what
holding through the print actually delivers. A partial week is skipped rather
than truncated, so a 3-day window is never reported as a week.

The two horizons genuinely disagree, which is the point of showing both: LITE
runs +2.8% on day one but +15.6% over the week (the move arrives after the
print), while NVDA is -2.5% then -5.9% (it keeps going the other way).

### Reversal candidates

A name qualifies when it was down over the **prior period** and closed **up** on
the **trigger day** (the most recent session). The window splits as `lb - 1` prior
sessions plus the trigger day, so a 5D window means "down over four sessions, up
on the fifth".

Qualification is deliberately stricter than "yesterday red, today green", because
one green day after a slide can be a dead-cat bounce that resumes falling:

- **The decline threshold scales per session** (`-0.75%` × prior sessions). A flat
  threshold would let a window with three do-nothing days and one red hair rank
  alongside a genuine four-day slide.
- **Trigger-day volume is reported as a ratio** against the prior period's average
  volume, per name and per group. A bounce on below-average volume is weaker
  evidence that the selling is finished — worth seeing rather than inferring from
  the price move alone. Where a prior session had zero volume the ratio is `null`,
  not a substituted number.
- **A strictly positive trigger day is required** — an unchanged close is not a
  reversal.
- **Groups with no qualifying members are omitted entirely**, rather than listed
  with a zeroed row.
- **There is no 1D screen.** A single-session window has no prior period to
  reverse from, so the server returns `reversal: null` there and the lookback tabs
  become 2D–5D. Switching views clamps an out-of-range lookback rather than
  landing on an undefined slice.

Groups rank by **reversal breadth** (share of priced members that reversed), then
average bounce. The bar encodes breadth on a fixed 0–100% scale — the same
quantity the list is sorted by, so a full-width bar means "every member reversed"
rather than "the most of whatever is on screen". Encoding the bounce while sorting
by breadth drew longer bars on lower-ranked rows and made the sort key invisible.

Both figures are shown per row (`76% · +4.22%`), and the group's average volume
ratio sits in the hero and the table, so a broad-but-unconfirmed bounce is
distinguishable from a narrow-but-heavy one.

### Earnings timing

The third view. **A timing tool, not a signal** -- the distinction is the whole
point, and it came out of measuring the idea first.

#### What the drift study found

A pre-earnings run-up does exist. Measured over 2012 announcements across 242
symbols (dated from SEC 8-K item 2.02, not 10-Q filing dates, which land days
later and would mis-date every event), scored as excess over **each symbol's own**
mean return for the same window:

| Window | Raw | Baseline | Excess | Beat own baseline |
|---:|---:|---:|---:|---:|
| 5 | 0.67% | 0.44% | 0.23% | 51.4% |
| **10** | 1.63% | 0.82% | **0.82%** | 54.6% |
| 15 | 2.20% | 1.29% | 0.92% | 54.2% |
| 21 | 2.66% | 1.99% | 0.67% | 50.4% |

The baseline is the finding: **half the apparent move is just this universe's
uptrend**. It survives robustness checks (stable across both sample halves,
+0.73% winsorised at 10%, positive in 12 of 14 groups) -- but per-event SD is
7.26% against a 0.82% mean, so **noise is 9x the edge** and P(two trades both
beat baseline) is 29.8%. That is a portfolio tilt, not something harvestable in
one or two positions, which is why this ships as a calendar rather than a screen.

Treat the AI Optical / Interconnect row (+4.85% excess) with suspicion: those
constituents were picked in 2026 *because* the theme had already run, so it is
selection bias. Reproduce any of this with `research/drift_study.py` and
`research/drift_robustness.py`.

#### Projection accuracy

Dates are **estimates**, never confirmed announcements. Measured on 1437
no-lookahead projections, each made 20 days before the real print: **median error
2 days**, mean 3.7, 88% within a week, 97.6% within two. Rows therefore carry a
window (+-8 days, the p90) and the UI warns on the **earliest** edge.

There is deliberately **no confidence label**. Nothing available predicted which
projections would be wrong -- within-7-days ran 79-92% across every bucket of
corroborating years and history length, with no trend -- so a three-tier badge
would have looked informative and been noise.

#### Reading the columns

- **Typical |move| / Worst |move|** are *absolute*, so they say how far the stock
  moves, not which way. Direction is not predictable; magnitude partly is.
- **n** is the sample size behind that median. Under about 6 events, distrust it.
- **5D rank** is the *group's* momentum rank (1 = hottest of 14), i.e. whether the
  print lands in a group that is already running.
- **Timing** is before-open vs after-close, taken from the company's own history.
  It decides which session reacts, and the universe splits close to 50/50.

#### Held positions

Open positions in `trading_records/trades-schwab.csv` are flagged, aggregated
across lots (two lots of one symbol report the combined size and average cost --
reporting a single lot would understate the exposure), and **never filtered out by
the horizon**. Listing a held name as "no date known" when it reports in 92 days
states the opposite of the truth.

Refresh the calendar with the header Refresh button; the server caches it for an
hour, and failures are not cached so re-running the collector takes effect at once.

Regenerate the underlying history with:

```bash
python3 trading_desk/research/earnings_dates.py
```

### Split events (research only)

Nothing on the page uses this yet; it is a measurement kept next to the drift
study so the next person does not redo it. `research/split_study.py` pulls two
years of forward and reverse splits from Alpaca's corporate-actions feed, tags
each as listed stock / ETF / OTC, and measures the close-to-close change over
the 1, 2, 3 and 5 sessions ending on the last pre-split close, plus the 1, 2, 3,
5 and 10 sessions starting on the first post-split close (raw bars throughout,
so neither window is ever contaminated by the split itself; mis-dated vendor
bars are skipped, never patched).

Headline from the 2024-09 to 2026-09 run: listed **stocks** see about **37
forward splits a year** and **470-620 reverse splits a year**; ETFs add another
30-60 forward and 70-180 reverse; OTC names are counted but have no Alpaca bars.

Forward splits (2:1 or larger, n=57) show **no pre-split drift** and no
post-split drift either -- every median from 1 to 10 sessions out sits within
about 1% of flat, roughly half positive either direction.

Reverse splits (n=1074 stock events) fall hard into the event and **keep
falling after it**:

| | median | % positive |
|---|---|---|
| T-2 to T-1 (last 2 pre-split sessions) | -12% | 19% |
| ex-date session alone | -1% | 46% |
| ex-date to +2 sessions | -6% | 30% |
| ex-date to +5 sessions | -9% | 31% |
| ex-date to +10 sessions | -11% | 32% |

So the announcement drop (T-2) is not a one-day event that then stabilizes;
roughly 70% of these names are still lower ten sessions after the split than
they closed on the split's first day. The mean is much noisier than the median
here -- occasional 100%+ bounces pull the post-10-day mean to only -3% against
a -11% median -- so read the median and hit rate, not the mean. This is a raw
continuation number, not baselined against the population's own normal
volatility: these are sub-$1 names (median pre-split close $0.30) that were
already declining before the split, so "down after the split" and "this
population is generally down" are not separated here. Nasdaq requires public
notice at least two business days before a reverse split takes effect, which
is why the T-2 session (not T-1) carries most of the announcement reaction.

```bash
python3 trading_desk/research/split_study.py
```

Writes `research/split_events.csv` (one row per event) and
`research/split_study.json` (counts and return tables).

### Daily review

A per-position screen for the one question the ranking board cannot answer:
*where does what I already own actually stand?* Positions come from
`trading_records/trades-schwab.csv` (gitignored, optional) via the same
`open_positions()` reader the earnings alerts use, so the review and the
earnings flags can never disagree about what is held.

It reuses `get_stock`, which means a review opened after browsing the board is
nearly free, and the levels shown are the identical levels the chart draws —
there is no second, subtly different calculation to reconcile.

#### Reading it

| Column | Meaning |
|---|---|
| `Last` | Latest close, with the day's change beneath it. |
| `Avg entry` | Cost basis across all open lots in that symbol. |
| `Unrealised` | Dollars and percent against that basis. |
| `% book` | Share of the reviewed book **plus** excluded holdings, at market value. Cash is not included, so this is position weight, not account weight. |
| `Resistance above` / `Support below` | Nearest level on each side, with distance in percent **and in ATR**. |
| `To support` | Dollars between today's price and the nearest support. |
| `Earnings` | Days to the next projected print. Red inside the 21-day swing window. |

Rows sort by **distance to support in ATR**, closest first — that is the
position whose level a stop would key off soonest. A name with no support at all
below it sorts to the very top: having nothing to lean on is more notable than
sitting near something.

Distance is reported in ATR as well as percent because percent alone is not
comparable across the book. AXTI at 14% ATR and POWL at 6% are not equally close
to a level 5% away; in ATR terms the first is a third of a day's move and the
second is nearly a full one.

#### Downside to support is not risk taken

`To support` is measured from **today's price**, not from entry. For an
underwater position the difference has already been spent, so this is the risk
that remains to that level — not the risk originally accepted. Conflating the
two would flatter every losing position on the page.

#### Flags are observations, not signals

Each flag states something measurable: a lot with no recorded stop, a price
within half an ATR of a level, a print inside the swing horizon, a close below
all three moving averages. None of them says what to do, and
`test_flags_never_tell_the_reader_what_to_do` asserts that no flag string
contains an imperative. The measured pre-earnings drift documented above
(+0.82% excess against 9x that in noise) is the standing reminder of why this
view does not pretend to an edge: it surfaces facts and stops there.

#### Held but not reviewed

`REVIEW_EXCLUDE` in `server.py` lists holdings kept out of the risk math and the
flags by instruction. They are still reported, in their own section with their
book weight — silently dropping a position would make the concentration figures
actively misleading, which is worse than showing something the owner has asked
not to be advised on.

It is a mapping, not a set, so the reason travels with the symbol and renders on
the page. "Excluded" covers two different cases and a bare set would flatten
them:

| Symbol | Reason |
|---|---|
| `IBIT` | Bitcoin position, held by choice — not part of the swing book. Over half the book by weight, so omitting it entirely would be misleading. |
| `SNDL` | Residual position, too small to act on. Sorted near the top on ATR distance despite being 0.0% of the book, pushing real positions down the page. |

Every entry must carry a non-empty reason; `test_excluded_symbols_are_reported_but_carry_no_risk_math`
asserts it, because an unexplained exclusion is indistinguishable from a bug.

#### Theme exposure

Reviewed positions summed by the `universe.py` groups they belong to. A symbol in
two groups counts in both (POWL is in Industrials *and* AI Power / Datacenter
Buildout), so the percentages deliberately do not sum to 100%. The excluded
holdings are left out entirely rather than filed under `(ungrouped)`, since
inventing a theme for them would be worse than omitting them.

#### Thesis strip

The latest hand-entered score from the Cycle view, read back from
`trading_records/cycle-score.csv` and shown at the top of the review. Nothing on
the review computes it. It is here because the two halves answer different
questions and are meant to be read together: the rest of the page says where each
position sits against its levels *today*, and this says whether the reason for
holding it still stands. A position can sit on support with the thesis GREEN, or
run well above its levels with the thesis RED.

A score older than `CYCLE_STALE_DAYS` (35) is marked overdue, since the dashboard
describes itself as a monthly check. An unscored thesis reports "not scored"
rather than defaulting to a passing grade —
`test_cycle_status_says_so_when_nothing_is_logged` asserts there is no `status`
key at all in that case, because a default GREEN would be a fabricated judgment.

#### Sizing worksheet

A calculator, not a suggestion. You pick the symbol, the dollar amount, and the
risk budget as a percent of book; it works out:

| Row | Meaning |
|---|---|
| Shares / actual cost | `floor(amount ÷ last)`, and what those shares cost |
| Risk per share to stop | `last − stop_current` for that position |
| Dollars at risk | shares × risk per share |
| That is % of book | the same figure against `book_market_value` |
| Your budget | `risk % × book`, from the number you typed |
| Shares that fit the budget | the inverse: `floor(budget ÷ risk per share)` |
| Weight after / theme after | concentration if the trade were done |

**It deliberately does not rank the symbols, mark any of them preferable, or
propose an amount.** The select is in table order, which is proximity to support,
not desirability. Choosing what to trade and how much is the desk owner's
decision; this converts that decision into risk and concentration terms so it can
be made with the numbers in view. Nothing here is investment advice, and the
standing disclaimer under the review says so on the page itself.

If a position has no `stop_current`, dollars at risk reports an em dash and the
worksheet says why, rather than silently substituting ATR — a risk number
measured against a level nobody set would be worse than no number.

#### Recent headlines

Up to three per reviewed position, straight from the Alpaca news feed, newest
first, linked out, with source and date.

**Not scored, ranked, or summarised.** A sentiment number here would be a guess
wearing the clothes of a signal — the same reason the cycle dashboard is
hand-entered rather than computed.
`test_headlines_are_passed_through_unscored` asserts no `sentiment` or `score`
key ever appears on a headline. Excluded holdings get no headlines, since the
page deliberately does not comment on them.

Cached for `REVIEW_NEWS_TTL` (120s), shorter than `REVIEW_TTL` — a print at 09:05
matters at 09:06, and daily bars do not move that fast. The block degrades on its
own: a dead feed shows "news unavailable" on that column and leaves the rest of
the review intact.

### Cycle

The fifth view, and the only one with nothing to compute. The Daily review asks
where each position stands against its levels today;
[`AI_DATA_CENTER_CYCLE_DASHBOARD.md`](AI_DATA_CENTER_CYCLE_DASHBOARD.md) asks
the slower question underneath it: does the reason for owning the optical and
power names still hold? It scores eight indicators of the hyperscaler buildout
from 0 to 2 once a month, sums them to a GREEN / YELLOW / RED reading out of 16,
and ends on one question: starting from cash, would you still own AXTI, LITE,
COHR, FN and POWL at their current weights? The document's "How this fits the
desk" section says what the rest of the desk supplies to that judgment: the
Earnings timing view already projects the hyperscaler prints where capex
guidance changes, and the Daily review's theme exposure is the two equity
sleeves the framework maps.

The view is the front end for that document's monthly log,
`trading_records/cycle-score.csv` -- tracked in git and pushed, unlike the
trade journal, since it holds judgment scores and research notes rather
than positions or account details:

- the latest review's status and total, its answer to the core question and
  what assumption changed, with the move since the previous review;
- one tile per indicator: the score, the level it meets, and the criterion
  that level is defined by, taken from the document;
- a trend of every logged total, and the history table, whose column headers
  are the CSV's own column names so it doubles as a key to the file;
- a form that writes the next review. Each indicator shows its three criteria
  beside the score select, with the chosen one marked, and the document's
  "what to track" list folded away beneath.

None of it is market data, and the page says so on every render. What
`cycle.py` does is read and write the log and parse the document:

- **The criteria come from the document, not from code.** `rubric()` reads the
  eight numbered sections, their `### GREEN / YELLOW / RED` paragraphs and the
  core question out of the markdown. `tests/test_cycle.py` asserts the parse
  succeeds and that the document's score table, its bands and the CSV template
  agree with `cycle.INDICATORS`, `cycle.BANDS` and `cycle.COLUMNS`. Editing the
  framework changes the page; restructuring it fails a test rather than
  quietly blanking a rubric.
- **Blank is blank.** A skipped indicator is written as an empty cell and is
  never pre-filled from last month: switching the form's date to one without a
  review starts from nothing. A review with any blank has no total and no
  status, both cells stay empty in the file, and the page reads
  "Incomplete · 7 of 8 scored" rather than a number.
- **Reads are tolerant, writes are strict.** A hand-edited file is read with
  warnings on the page: a bad cell reads as blank, a stored total that
  disagrees with its scores is reported and the scores win, an extra column is
  ignored, a file that is not UTF-8 is named as such. But the view will not
  *write* to a file whose header differs from `TEMPLATE-cycle-score.csv`, which
  has a row with the wrong number of cells, or which it cannot decode. It
  refuses with the reason rather than rewriting a layout it did not produce,
  and rows it did not write are preserved verbatim, wrong stored total included.
  Dates are held to one spelling, `YYYY-MM-DD`, because `20260831` would sort
  after every hyphenated date and never match a later save of the same day.
- **One row per date.** Saving with a date that already has a review replaces
  that row, and the form says so before you save; if what the form shows
  differs from the logged row it says that too and offers to load it. Any
  other date appends. Rows are kept oldest first; saves take a lock, since the
  server is threaded and a save is a read-modify-write of the whole file; and
  the write is atomic (a private temp file, then rename), the same as the board
  cache.
- **Changing the date never touches what is typed.** A date input fires its
  change event on every keyboard step, so rebuilding the form on change would
  wipe eight scores per arrow key. The form only re-reads the log for the new
  date when it is empty; otherwise the banner offers to load the logged review.
  A new date in a month that already has a review gets a nudge toward that
  review's date, because the framework's mid-month re-score after a print means
  editing the month's row, not adding a second one; where two reviews do share
  a month, the trend labels them by day instead of by month.
- **`POST /api/cycle` is the server's only write route.** It accepts JSON
  only, which is also the CSRF guard for a loopback server: a form on some
  other page cannot send `application/json` without a preflight this server
  never answers. The body is capped at 64 KB. A validation error comes back as
  400 carrying the message the form shows.

### Sector scorecard

Cycle asks a hand-scored monthly question about the whole buildout thesis.
Sector answers a different, faster one from data the desk already has: is
whatever group you point it at actually leading or lagging right now, measured
against its own recent history and a benchmark -- not against a target price
or a rating.

Every metric on the view is a `sector_signals.py` function over plain daily
bars, computed live on every load (subject to the same `STOCK_TTL` cache as a
single stock, keyed by group *and* benchmark so flipping between two
benchmarks for one group cannot serve one's numbers back under the other's
label):

- **Relative strength** -- equal-weighted group return minus the benchmark's,
  at 5/21/63 sessions, plus whether the 5-session excess is widening or
  narrowing versus the 5 sessions before it. The trend is the point: a group
  outperforming by a shrinking margin is a different fact than one
  outperforming by a growing one, and the level alone does not distinguish
  them.
- **Breadth** -- the share of constituents above their own 20/50/200-day
  average. Narrow breadth under a rising benchmark is the classic divergence;
  this reports the number, not the divergence story.
- **New highs / lows** -- constituents at a new 20-session extreme. Twenty
  sessions, not 52 weeks: a 52-week extreme is rare enough that a 4-13 name
  group would show zero on most days, which is not useful for something meant
  to move with the tape.
- **Participation** -- aggregate dollar volume, trailing 5 sessions against
  trailing 20. Dollar volume, not share count, so one high-price low-share-count
  name cannot be swamped by a cheap, heavily-traded one in the sum.
- **Volatility** -- average ATR% now against 20 sessions ago. Expansion
  precedes a resolution without saying which way it resolves.
- **Dispersion** -- how much constituents moved together *today* versus their
  own trailing-20-session norm, not against a fixed universal threshold. A
  ratio under 1 means today was driven by something shared across the whole
  group -- a rate move, a sector-wide print -- rather than any one name's own
  news; a ratio near or above 1 means the day was closer to normal, name-by-name
  dispersion. This is the computed, generic version of a question that comes up
  by hand in the Daily review whenever every held position moves the same way
  on the same day.
- **At a level** -- constituents currently within `LEVEL_PROXIMITY_ATR` of a
  support or resistance, the same proximity the Daily review's `at_support` /
  `at_resistance` flags use, applied across the whole group instead of one
  position.

Every group `universe.py` knows is selectable from the dropdown, sector or
theme alike -- nothing here is written for one sector specifically. The
benchmark resolves in order: an explicit `?benchmark=` query param, then the
group's own `etf` field (`SMH` for Semiconductors, `XLK` for Technology), then
`SPY` for a theme group with no ETF of its own (`AI Optical / Interconnect`,
`AI Power / Datacenter Buildout`). `DEFAULT_SECTOR_GROUP` in `server.py` is
which group loads before a client picks one -- currently the one this view was
built to look at, and a plain constant to update by hand on the rare occasion
the desk's answer to "which theme matters most" actually changes, rather than
anything the server tries to detect on its own.

As with every other flag on this desk: **these are facts about the group's own
history, not a score, a rank, or a call on direction.** A dashboard that
combined relative strength, breadth, and dispersion into one number would be
manufacturing a composite edge none of these measurements individually claims
to have.

#### Cycle stage -- the one exception, and why it is handled differently

Below the tiles is a panel classifying each constituent into one of six cycle
stages, in the order the wheel turns:

```
Local Peak -> Correction -> Bottoming -> Recovery -> Extended/Uptrend -> Local Euphoria/Peak -> (back to Local Peak)
```

This **is** a classification, not a raw measurement -- it turns several numbers
into one label. That is a real departure from every other number on this view,
so it earns different treatment rather than being dressed up as another fact
tile.

**The thresholds are the published ones, not numbers this desk invented.** An
earlier version of this classifier used moving-average positions (price vs
SMA50/SMA200, whether SMA50 was rising) with hand-picked cutoffs. It produced
a genuinely wrong read -- `GLW`, sitting 36% below the high it set three months
earlier, was labelled a "Peak" -- and the cutoffs behind it were defensible-
sounding but arbitrary. The rule now rests on the definitions these words
already have in the industry:

| Threshold | Meaning | Source |
|---|---|---|
| **10%** off the peak | Below this is noise; 10-20% is a **correction** | The 10/20 split traces to Alan Shaw at Smith Barney; still the definition used by [Morningstar](https://www.morningstar.com/markets/whats-difference-between-bear-market-correction), [Schwab](https://www.schwab.com/learn/story/market-correction-what-does-it-mean), and [Fisher](https://www.fisherinvestments.com/en-us/resource-library/market-cycles/bear-markets) |
| **20%** off the peak | Past this is a **bear market** | Same convention |
| **+20%** off the trough | What starts a **new bull market** | The other half of the same convention ([U.S. Bank](https://www.usbank.com/financialiq/invest-your-money/market-perspectives/bull-market-to-bear-market.html)) |

The rule, in order, over four numbers taken straight off closing prices
(drawdown from the name's own peak, rally off its own trough, which extreme
came last, and its return over the last month):

| Condition | Stage |
|---|---|
| Within 10% of its peak, at a fresh peak, up 15%+ in a month | `Local Euphoria/Peak` |
| Within 10% of its peak, advance stalled | `Local Peak` |
| Within 10% of its peak, still advancing | `Extended/Uptrend` |
| 10-20% off its peak | `Correction` |
| Past 20% off its peak, but +20% off a **newer** trough | `Recovery` |
| Past 20% off its peak, still falling hard | `Correction` |
| Past 20% off its peak, no longer falling | `Bottoming` |

Design notes worth keeping:

- **No moving averages, no oscillators, no benchmark.** Only closing prices
  against a name's own peak and trough. `test_stage_rule_uses_no_moving_averages_or_oscillators`
  asserts this by inspecting the rule's own source, so an indicator cannot
  quietly reappear in it.
- **Which extreme came last matters.** A name 40% below a peak set last month
  is falling; the same 40% gap with the trough more recent means it already
  bottomed and is climbing. The drawdown alone cannot tell those apart, so
  `Recovery` additionally requires the trough to be the newer extreme --
  without that, `GLW`, up 120% off a year-old low while 36% below its peak,
  would read as "Recovery".
- **"Still falling" beats "near the low".** A name down 45% and still dropping
  29% in a month is mid-decline, not a base forming, however close to its low
  it sits. This is the split the moving-average version got wrong for `FN`.
- **Two numbers have no published standard**, and are labelled as such in the
  code: what counts as a stalled advance near a peak (`STALL_MOVE_PCT`) and
  what counts as still falling (`STILL_FALLING_PCT`). The literature describes
  the distribution phase only qualitatively -- "sideways and range-bound after
  an extended uptrend" -- so these are this desk's operationalization of that
  sentence rather than a convention anyone else shares.
- **The group label is the most common stage, and a tie is reported as a tie.**
  Six stages have no numeric mean; forcing a winner out of 4 `Correction` and 4
  `Bottoming` would assert a consensus that does not exist.
- **A name needs enough history to classify** (`RECENT_MOVE_WINDOW_SESSIONS + 1`
  sessions) and is otherwise reported unclassified, never guessed. The window
  the peak and trough come from is reported per name, so a name without a full
  52 weeks does not silently claim one.
- **Still not a forecast.** `Bottoming` says a name is well off its peak and no
  longer falling -- where it is, not that it turns up from here.


### Indicators

Overlays: SMA 20 / 50 / 200, VWAP 20 (rolling), Bollinger Bands (20, 2σ),
support & resistance levels.
Panes: Volume + 20-day volume SMA, RSI 14, MACD (12, 26, 9) with histogram.
Also computed and available in the table view and tooltip: ATR 14, Stochastic
(14, 3), EMA 12 / 26, OBV. TDR 14 is computed alongside them and surfaced in the
[Company detail](#tdr-14--and-why-it-sits-next-to-atr) panel rather than on the
chart, since it reads as a position-sizing input rather than something to overlay.

Range selector: 3M / 6M / 1Y / 2Y.

#### Support & resistance

Swing pivot highs and lows (extremes over a ±5-bar window, with a strict
neighbour test so a flat plateau doesn't emit a pivot per bar) are clustered by
price. A cluster price turned at more than once becomes a level. Every level is
a price the market actually reversed at — nothing is drawn at a round number or
projected forward. Each level reports how many pivots formed it (`n×`), how many
bars tested it, and when it was first and last touched, so a live level can be
told from a stale one.

Two things are derived from ATR rather than fixed, because a fixed band is wrong
at both ends of the volatility range:

- **Cluster width** (`0.6 × ATR%`, clamped 1–8%). A flat 1.5% band suits NVDA
  (ATR ~3%) but finds *nothing* on AXTI (ATR ~12%), where every genuine retest
  falls outside it.
- **How far out to look** (`8 × ATR%`, clamped 15–60%).

Selection is anchored to the last close and balanced across both sides — up to
four levels above and four below, **nearest first**. Ranking by touch count
instead buries the level 4% away under ones 13–24% away that happened to be hit
more often, and on a stock that ran from \$2 to \$88 it returns nothing but
clusters down at \$2. A name at record highs correctly reports no resistance.

## API

| Route | Returns |
|---|---|
| `GET /api/board` | Momentum rankings for all five lookbacks, each with a `reversal` block (`null` on 1D). `?force=1` bypasses the cache. |
| `GET /api/stock?symbol=X` | ~2 years of daily bars plus every indicator series. |
| `GET /api/detail?symbol=X` | Fundamentals, price stats, news, and research links. |
| `GET /api/earnings?horizon=N` | Projected prints within N days (1-400, default 30), nearest first, with held-position flags. |
| `GET /api/review` | Per-holding review: levels, downside to support, risk to the managed stop, theme exposure, journal gaps, up to three headlines per reviewed holding, and the latest hand-entered cycle score. `?force=1` rebuilds. |
| `GET /api/cycle` | The cycle log (every review, oldest first, totals derived from the scores), the rubric parsed from the framework document, the bands, and any file warnings. Never cached. |
| `POST /api/cycle` | Write one review (JSON: `review_date`, `scores`, `core_question`, `assumption_changed`, `notes`), replacing a row with the same date. Returns the rebuilt payload, or 400 with the reason. |
| `GET /api/sector?group=X&benchmark=Y` | Leading-indicator scorecard for one universe.py group (`X` defaults to `DEFAULT_SECTOR_GROUP`; `benchmark` defaults to the group's own `etf`, then `SPY`). Cached like `/api/stock`; `?force=1` bypasses it. Unknown group returns `error` plus `available_groups`. |
| — | The same response also carries `cycle_stages`: per-name cycle stage, each name's drawdown from its own peak, rally off its own trough, which extreme came last, and recent move (`context`), a count per stage, and the group's majority label (ties reported as ties). See Sector scorecard → Cycle stage. |
| `GET /api/health` | Credential and cache status. |

Board and per-symbol routes cache for 5 minutes; the review caches for 2 (it reuses
the per-symbol cache, so a rebuild is cheap and prices stay live), and headlines for 2
minutes on their own shorter timer (`REVIEW_NEWS_TTL`), since a print matters within the
minute and daily bars do not. Only the board is persisted to `cache.json`
(~60 KB); per-symbol payloads stay in memory behind a 60-entry LRU. Persisting
them meant re-serializing tens of megabytes under the global lock on every
cache-miss, and they are cheap to refetch after a restart.

## Data integrity

Per `AGENTS.md` RULE #1, nothing here fabricates market data:

- A symbol with missing or too-short history is **dropped and reported** under
  `omitted` (shown as a banner on the page), never back-filled or carried forward.
- Indicator warmup regions are `null`, not zero-filled — an undefined SMA200 on
  day 3 stays undefined.
- A flat Stochastic window (zero range) returns `null` rather than a made-up 50.
- A reversal volume ratio against a zero-volume prior session is `null`, not a
  substituted or clamped multiple.
- If a live fetch fails, the server serves the **last known-good** cache and marks
  the payload `stale`, with a banner saying so. A failed fetch never overwrites
  good cached data, and the board's cache write is atomic (temp file + rename).

## Known limitations

- **Daily bars only, and SIP is 16 minutes behind.** The board is built for
  multi-day horizons. For intraday work Alpaca also serves 1Min/5Min/15Min/1Hour
  bars and tick-level trades and quotes (nanosecond timestamps) — but sub-minute
  *bars* are not offered, and real-time (undelayed) access is IEX-only on this
  subscription.
- **Group membership is hand-curated** in `universe.py`, not pulled from an index
  provider. It covers liquid names per sector, not the full index.
- **Themes have no ETF proxy**, so their `etf_return_pct` is `null` by design.
  All groups rank on constituent returns, so the comparison stays apples-to-apples.
- **Mean is outlier-sensitive.** A single name up 87% lifts its whole group. The
  median and breadth columns are shown alongside precisely so you can see when a
  group's rank rests on one name.

## Files

| File | Role |
|---|---|
| `server.py` | HTTP server, Alpaca client, momentum + reversal ranking, caching |
| `universe.py` | Sector/theme constituents |
| `indicators.py` | Indicator math (pure stdlib) |
| `fundamentals.py` | SEC filings, TTM EPS reconstruction, news, research links |
| `index.html` / `app.js` / `style.css` | Dashboard UI |
| `research/split_study.py` | Split-event counts and pre-split return study (see Split events) |
| `sector_signals.py` | Sector scorecard math: relative strength, breadth, new highs/lows, participation, volatility, dispersion, level proximity, six-stage cycle classification. Pure functions over bars, no I/O |
| `cycle.py` | Cycle score log: read, validate and write `cycle-score.csv`; parse the framework document for the rubric |
| `AI_DATA_CENTER_CYCLE_DASHBOARD.md` | The framework the Cycle view scores against: eight 0-2 indicators, GREEN/YELLOW/RED bands, the core question |
| `tests/test_reversal.py` | Reversal qualification regression tests |
| `tests/test_review.py` | Daily-review arithmetic and flag-rule tests |
| `tests/test_cycle.py` | Cycle log rules (blank stays blank, strict writes, tolerant reads), document/template/code agreement, POST validation |
| `tests/test_sector_signals.py` | Sector scorecard math on synthetic bars: relative strength, breadth, new highs/lows, participation, volatility, dispersion, level proximity |
| `tests/test_sector_route.py` | `/api/sector` benchmark resolution (own etf, fallback, override), missing-constituent handling, cache keying and TTL, error-not-raised |
| `tests/test_ports.py` | Per-branch port mapping, HEAD parsing, launcher agreement, stale-server detection |

## Tests

```bash
python3 trading_desk/tests/test_reversal.py       # no pytest needed
python3 trading_desk/tests/test_review.py         # daily review
python3 trading_desk/tests/test_cycle.py          # cycle score log and rubric
python3 trading_desk/tests/test_sector_signals.py # sector scorecard math
python3 trading_desk/tests/test_sector_route.py   # sector scorecard route
python3 trading_desk/tests/test_ports.py          # port pinning
python3 -m pytest trading_desk/tests/             # or under pytest
```

Synthetic bars only, no network, so the qualification rules stay pinned
independently of the current session. Kept out of the repo-root `tests/` tree on
purpose: that suite's `conftest.py` pulls in dotenv/APScheduler/Lumibot fixtures
this stdlib-only sub-project does not need.

## Dependencies

Price data, indicators, news and the UI are **stdlib only**. Fundamentals reuse
Lumibot's `SECFundamentals` (already in this repo) for SEC XBRL access, imported
lazily — if Lumibot is unavailable the panel reports fundamentals as unavailable
and everything else still works.

## Design notes

Chart colors use the validated categorical palette; the series slots were checked
with the `dataviz` skill's `validate_palette.js` against both surfaces
(dark `#12161c` passes all checks; light `#fcfcfb` passes with a contrast warning
on two slots, which is why direct endpoint labels and a table view both ship).
