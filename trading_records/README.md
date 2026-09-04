# Trading Records

Trade journal for the swing-trading workflow driven by `trading_desk/`.

**Last Updated:** 2026-08-10
**Status:** Active
**Audience:** Both

---

## Privacy — read this first

Everything in this folder except `README.md` and `TEMPLATE.csv` is **gitignored**.
Real records contain positions, fills, and account details, and this repo has a
public remote — so the actual journal never gets committed. The `.gitignore` rule
is an allowlist, not a blocklist:

```
trading_records/*
!trading_records/README.md
!trading_records/TEMPLATE.csv
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
