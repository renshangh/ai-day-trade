# Trading Desk — Hot Sector Board

Local dashboard that screens sectors and themes over short horizons — for momentum
or for reversals — and charts the resulting movers with the standard technical
indicator set.

**Last Updated:** 2026-08-14
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
your default browser automatically. If the dashboard is already running, it just
opens it instead of starting a second copy. To stop it, close that Terminal
window or press Ctrl+C in it — the server is not left running in the background.

**Manual:**

```bash
python3 trading_desk/server.py --port 8799
```

Then open <http://localhost:8799>.

## What's on the page

| Section | What it shows |
|---|---|
| View tabs | Momentum / Reversal candidates / Earnings timing / Daily review. The first two scope the hero, ranking, movers strip and table; the last two replace them. |
| Lookback tabs | 1D–5D for momentum, 2D–5D for reversal. Scopes the whole board. |
| Hottest group | Mean, median, breadth, vs SPY, and the ETF proxy return. |
| Top reversal candidate | Prior decline, bounce, reversal breadth, vs SPY today, volume ratio. |
| Group ranking | All 14 groups as a diverging bar chart; click a row to load its leaders. |
| Top 5 | The leaders inside the selected group, with a 30-day sparkline. |
| Detail chart | Candlesticks + overlays, with volume, RSI and MACD panes on a shared crosshair. |
| Company detail | Market cap, trailing P/E, 52-week range, volatility, SEC filings, news, research links. |
| Earnings timing | Upcoming prints (including today's, before they land) with an uncertainty window, expected timing, 1-day and 1-week reaction stats, and held-position alerts. |
| Daily review | Every open lot in the journal against its own levels: P&L, nearest support/resistance in ATR as well as percent, downside to support, and the journal's own recorded gaps. |
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
| `GET /api/review` | Per-holding review: levels, downside to support, theme exposure, journal gaps. `?force=1` rebuilds. |
| `GET /api/health` | Credential and cache status. |

Board and per-symbol routes cache for 5 minutes; the review caches for 2 (it reuses
the per-symbol cache, so a rebuild is cheap and prices stay live). Only the board is persisted to `cache.json`
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
| `tests/test_reversal.py` | Reversal qualification regression tests |
| `tests/test_review.py` | Daily-review arithmetic and flag-rule tests |

## Tests

```bash
python3 trading_desk/tests/test_reversal.py       # no pytest needed
python3 trading_desk/tests/test_review.py         # daily review
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
