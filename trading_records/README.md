# Trading Records

Trade journal for the swing-trading workflow driven by `trading_desk/`.

**Last Updated:** 2026-09-08
**Status:** Active
**Audience:** Both

---

## Privacy — read this first

Everything in this folder except `README.md`, the two templates
(`TEMPLATE.csv`, `TEMPLATE-cycle-score.csv`) and `cycle-score.csv` is
**gitignored**. `cycle-score.csv` is the one exception to "real records stay
private": it holds monthly 0-2 judgment scores and research notes, not
positions, fills, or account details, so it is tracked and pushed on
purpose, the same as the AI data center cycle research it logs. Keep it
that way -- if a note ever needs an account-linked figure, that note
belongs in the untracked journal instead, not in this file.
Real records contain positions, fills, and account details, and this repo has a
public remote — so the actual journal never gets committed. The `.gitignore` rule
is an allowlist, not a blocklist:

```
trading_records/*
!trading_records/README.md
!trading_records/TEMPLATE.csv
!trading_records/TEMPLATE-cycle-score.csv
!trading_records/cycle-score.csv
```

Adding a new file here keeps it private by default. If you ever *want* something
committed, add an explicit negation — don't loosen the wildcard.

Never put an account number in these files. The `account` distinction, if you need
one, belongs in the filename (`trades-schwab.csv`), not in a column.

## Files

| File | Role |
|---|---|
| `TEMPLATE.csv` | Column schema with one example row. Copy it to start a journal. |
| `trades.csv` | Your live journal (gitignored). |
| `TEMPLATE-cycle-score.csv` | Column schema for the monthly AI data center cycle score, with one example row. |
| `cycle-score.csv` | Your monthly cycle-score log. Tracked in git and pushed, unlike the rest of this folder -- see Privacy above. Written by the dashboard's Cycle view, or by hand. |

Start one with:

```bash
cp trading_records/TEMPLATE.csv trading_records/trades.csv
```

Then delete the example row.

## Schema

Execution facts and the reasoning are deliberately in one row. A record of only
fills tells you what happened but not whether the *decision* was sound, which is
the part worth reviewing.

| Column | Meaning |
|---|---|
| `trade_id` | Sequential. Stable handle for a trade across edits. |
| `status` | `open` or `closed`. |
| `setup` | `momentum` or `reversal` — which dashboard screen sourced the idea. |
| `group` | Sector/theme from the board (e.g. `Energy`, `AI Optical / Interconnect`). |
| `symbol` / `side` / `qty` | Instrument and position. `long` or `short`. |
| `entry_date` / `entry_price` | Fill date and average fill price. |
| `stop` / `target` | Levels set **at entry**. Recording them after the fact defeats the purpose. |
| `stop_current` | A stop for managing the position **from now**, not the entry stop. Separate column on purpose — see below. |
| `stop_current_set` | Date `stop_current` was decided. |
| `stop_current_basis` | How it was derived, e.g. `1 ATR14 (7.91) below 60.74`, so the number is auditable later. |
| `exit_date` / `exit_price` | Blank while open. |
| `gross_pnl` / `fees` / `net_pnl` | Keep fees separate; they matter at swing-trade size. |
| `pnl_pct` | Net P&L as a percent of cost basis. |
| `r_multiple` | Net P&L ÷ initial risk per share × qty. See below. |
| `atr_pct_at_entry` | ATR% from the dashboard's company panel at entry. |
| `thesis` | Why you took it, in one sentence, written *before* the outcome is known. |
| `exit_reason` | `target`, `stop`, `time`, `thesis_invalidated`, `discretionary`. |
| `lesson` | Written after closing. Blank is fine; a wrong lesson is worse than none. |

### R-multiple

```
initial_risk_per_share = |entry_price - stop|
r_multiple             = net_pnl / (initial_risk_per_share × qty)
```

`+1R` means you made exactly what you risked. This is the number worth tracking
over time — raw P&L conflates decision quality with position size, so a run of
sloppy entries in large size can look better than disciplined ones in small size.

An `r_multiple` is only meaningful if `stop` was set at entry. If you didn't set
one, leave both blank rather than back-filling a plausible number.

Direction matters: for a long the stop sits below and the **highest** of a
symbol's lot stops is the tightest; for a short it sits above and the **lowest**
is. The `side` column drives that, and `risk_to_stop` is signed so "through the
stop" is negative either way. A cell that will not parse (`n/a`, `$94.00`) is
collected in `stop_current_unparsed` rather than raising — that parsing runs past
the review's market-data guard, so an uncaught error would blank the entire
review over one typo.

`stop_current_set` is reported only when every open lot of the symbol agrees on
it. Different dates describe different decisions, and showing one as though it
covered the whole position asserts a provenance that is wrong for part of it.

### Why `stop_current` is a separate column

A stop decided today is a real risk decision, but it is **not** the entry stop,
and the two must not share a column.

`r_multiple` divides by `|entry_price - stop|`. Back-filling `stop` with a level
chosen after the fact measures risk from a price the trade never actually risked
— and because a stop picked once a position is already underwater sits closer to
the current price than an honest entry stop would have, the resulting R is
*flattering*. A losing trade can be made to look like it only cost 0.4R.

So `stop` stays blank when none was set at entry, `r_multiple` stays blank with
it, and that history is simply lost. `stop_current` records what to manage from
here without rewriting what the decision actually was.

The daily review's `no_stop` flag deliberately keys off `stop`, not
`stop_current`, because it is tracking entry discipline — the number the section
above says should trend to zero. Filling `stop_current` will not silence it, and
should not.

## Filling it in

`trading_desk/` supplies most of the numeric fields at entry time:

- `group` and `setup` — from the board's View tabs and group ranking.
- `atr_pct_at_entry` — the company detail panel's volatility stat.
- `stop` / `target` candidates — the support/resistance levels on the chart, which
  report how many times price actually turned at each.

Order-level facts (fill price, fees, timestamps) come from the broker's own
confirmations. Take them from the broker, not from the dashboard: the board runs
on the SIP tape delayed ~16 minutes and on daily bars, so its closing price is not
your fill.

## Reviewing

Worth looking at periodically:

- **Expectancy** — mean `r_multiple` across closed trades. Positive is the bar.
- **By `setup`** — momentum vs reversal, separately. They are different edges and
  averaging them hides which one is working.
- **`exit_reason` mix** — a high `stop` share with negative expectancy usually
  means entries are too extended, not that stops are too tight.
- **Trades with no `stop`** — count them. That number should trend to zero.

## Monthly cycle score

`trading_desk/AI_DATA_CENTER_CYCLE_DASHBOARD.md` scores seven indicators of the
AI data center buildout from 0 to 2 once a month and asks whether, starting from
cash, you would still own the same names at the same weights. Log each review
as one row. The dashboard's **Cycle** view is a form over this file: it
creates it on the first save, writes one row per review, and replaces the row
whose date you save again. To start the log by hand instead:

```bash
cp trading_records/TEMPLATE-cycle-score.csv trading_records/cycle-score.csv
```

Then delete the example row (the view flags it until you do).

| Column | Meaning |
|---|---|
| `review_date` | Date the scores were decided, `YYYY-MM-DD`. |
| `capex` … `electrical` | The seven indicator scores, 0–2, in the dashboard's order: capex, construction, vacancy, power, monetization, optical, electrical. |
| `total` | Sum of the seven. Fill it only when all seven are scored. |
| `status` | `GREEN` (11–14), `YELLOW` (7–10) or `RED` (0–6). Blank when `total` is blank. |
| `core_question` | Starting from cash, would you own the same names at the same weights? `yes`, or the names you would not. |
| `assumption_changed` | Only when the answer moved from last month: which underlying assumption changed. Otherwise `unchanged`. |
| `notes` | Sources checked, and anything that did not fit a cell. |

An indicator you did not check this month stays **blank** rather than
carrying last month's score forward; the dashboard's "Recording the score"
section says why. The view enforces this: a new date starts every score blank,
and a review with a blank is saved with `total` and `status` empty.

Hand edits are fine, with two rules: keep the file UTF-8 (a spreadsheet's
default "CSV" export often is not), and keep the header exactly as the template
has it. The view still reads a file with a changed header, warning on the page
and showing what it can, but it will not write to one: the form stays on screen
and every save fails with that reason until the extra column is removed. A
stored `total` or `status` that disagrees with its row's scores is reported on
the page, not corrected.
