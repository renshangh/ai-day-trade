# BTC and SOL losses in the original ninety day test

Largest losses, winning counterexamples and the earlier sixty day performance.

Last Updated: 2026-11-10  
Status: Read-only investigation complete; no trading changes  
Audience: Trading Desk owner and maintainers

## Overview

The earlier sixty days lost money mainly because winning trades earned less
than losing trades cost. BTC E1's average winner fell to $26.01 per fixed
$10,000 entry, compared with $61.92 in the final month. SOL had both smaller
winners and larger losses, but all nine earlier SOL trades have partial
entry context. Its sparse earlier feed cannot establish a clean market-regime
conclusion.

There are at least three distinct failure types: an early reversal that fails
and keeps falling; a valid stop followed by a later recovery; and a weak,
long-held rebound with wide initial risk and incomplete observations. The
same B1 entry family also produces the largest winners. This investigation
does not identify a proven filter or change an entry, exit, stop or parameter.

## Period accounting

Use E1 for the common BTC/SOL exit policy. The original ninety-day study is
`20261110T140721Z-unfiltered-90d`. The earlier segment is August 11–October 10,
2026 00:00 UTC exclusive; the final segment is October 10–November 9 00:00 UTC
exclusive. Every book is actually flat at the split. Period returns therefore
come from saved boundary cash, not subtraction of ninety- and thirty-day
percentages. SOL's last boundary observation is one minute early, with the
account flat in cash.

| E1 book | Earlier 60 days | Final 30 days |
|---|---:|---:|
| BTC illustrative cash return | -3.31% | +5.31% |
| BTC maximum observed minute-close drawdown | 4.75% | 3.01% |
| BTC winners / closed trades | 19 / 42 | 19 / 38 |
| BTC average net winner / loser per $10,000 entry | +$26.01 / -$35.97 | +$61.92 / -$34.13 |
| SOL illustrative cash return | -2.36% | +16.78% |
| SOL maximum observed minute-close drawdown | 4.80% | 3.52% |
| SOL winners / closed trades | 4 / 9 | 18 / 35 |
| SOL average net winner / loser per $10,000 entry | +$62.93 / -$97.35 | +$127.87 / -$42.34 |

Cash returns use separate $10,000 initial accounts, available-cash reinvestment
and original partial-sale fractions. Per-trade dollars below instead normalize
each independent entry to $10,000. These measures are different. Both retain
the original 2bps per-side ETF friction proxy, excluding actual spot crypto
fees, market impact, funding, interest and taxes. These are reference
simulations, not broker fills or account profits.

BTC 0.1 and E2 each lost 4.13% in the earlier segment; their final-segment
returns were +4.43% and +5.35%, respectively. E1 already reduces some losing
exits relative to 0.1, but does not eliminate the earlier period's deficit.

## Largest BTC losses

IDs refer to the ninety-day E1 book, not the original thirty-day numbering.
All times in this section are New York local time. An entry or exit time
identifies the source minute interval; completed-minute availability is one
minute later. Neither an exact crossing second nor an actual fill is verified.

| Trade | Entry date and time | Entry | Initial stop | Final exit date and time | Exit | Net per $10,000 entry |
|---|---|---:|---:|---|---:|---:|
| BTC #47 B1 | Oct 15 09:45 | $80,655.71 | $79,925.08 | Oct 15 09:53 | $79,925.08 | -$94.57 |
| BTC #42 B1 | Oct 8 12:17 | $81,217.63 | $80,616.36 | Oct 8 13:05 | $80,616.36 | -$78.02 |
| BTC #20 B1 | Sep 15 10:00 | $76,574.17 | $76,040.95 | Sep 15 10:35 | $76,040.95 | -$73.62 |
| BTC #22 B1 | Sep 15 15:03 | $76,141.74 | $74,796.83 | Sep 15 16:30 | $75,664.62 | -$66.65 |
| BTC #65 A | Oct 30 12:15 | $77,482.40 | $76,353.01 | Oct 30 14:00 | $77,030.52 | -$62.31 |

**BTC #47 is a whipsaw, not proof that every failed entry keeps declining.**
The 09:30–09:45 candle contains D at $80,003.855 and closes at $80,625.008.
The next minute breaks its $80,655.70 high, meeting the original aggressive
B1 contract. The entry minute's high is only $80,682.245, about 0.036 initial
price-risk units above entry. D and the initial stop break in the 09:53 minute,
eight minutes after entry. Saved observations first open above entry again
at 10:09, and the following two hours contain a high of $82,561.115. That
recovery is known only later; it cannot justify ignoring the stop at 09:53.

**BTC #42 breaks out briefly and then loses its base.** D is $80,735.6295
at 12:07. The 12:00–12:15 reference closes at $80,955.698; the 12:17 minute
crosses its $81,217.615 high. Subsequent observed minute opens reach only
0.248 initial price-risk units above entry before exit. The 12:45 candle
weakens; D breaks at 13:00 and the stop at 13:05. An observed opening first
recovers entry at 14:22, after the stop. This also has a later rebound, but
the stopped position had already lost its designated structure.

**BTC #20 and #22 show persistent weak follow-through.** #20 uses a separate
09:45–10:00 stabilization candle, so merely rejecting the D candle as its
own confirmation would not exclude it. The entry's following observed minute
opens achieve only 0.030 price R, then D and the stop break at 10:35 New York.
There are no missing held minutes, although prior context is partial. #22
has wider initial price risk of 1.77% and achieves only 0.052 price R at later
minute opens. The existing failed-rebound exit closes it before the hard stop,
at a loss of 0.369 cost-inclusive R. Neither trade has a subsequent observed
opening back at entry within the next two hours.

**BTC #65 is an A failure, not another B1 failure.** Later minute opens reach
only 0.056 initial price R above entry. Its failed-rebound exit closes above
the hard stop at -0.416 cost-inclusive R. It does not recover entry in the next
two hours of observations. A contributes only two trades in each segment;
the larger early BTC drag is B1: forty earlier B1 trades total -$349.37 per
fixed-$10,000 entry, while two earlier A trades total +$16.18.

## Largest SOL losses

| Trade | Entry date and time | Entry | Initial stop | Final exit date and time | Exit | Net per $10,000 entry |
|---|---|---:|---:|---|---:|---:|
| SOL #28 B1 | Oct 29 16:31 | $99.4670 | $97.9021 | Oct 29 16:41 | $97.9021 | -$161.30 |
| SOL #5 B1 | Sep 15 15:03 | $98.3270 | $94.2408 | Sep 16 09:12 | $96.9334 | -$145.71 |
| SOL #9 B1 | Oct 8 11:45 | $109.3200 | $107.8206 | Oct 8 11:54 | $107.8206 | -$141.13 |
| SOL #14 B1 | Oct 14 22:55 | $103.3600 | $100.3369 | Oct 15 01:30 | $102.2560 | -$110.79 |
| SOL #8 B1 | Sep 30 11:05 | $119.0755 | $118.1530 | Sep 30 11:25 | $118.1505 | -$81.67 |

**SOL #28 already has a separate post-D candle, yet fails.** The 16:00–16:15
shock makes D at $98.0335. The complete 16:15–16:30 candle holds D, with a
low of $98.8002 and high of $99.457. The next candle's 16:31 minute breaks the
high plus the original $0.01 increment. Its entry-minute high is $99.4695,
only $0.0025 above entry. D and the stop fail at 16:41. In all 120 following
observed minutes, even the maximum high of $97.92935 stays below entry.
This is a failed bounce with continued weakness. A post-D hold requirement
alone cannot distinguish it from a good entry.

**SOL #5 is a wide-risk, incomplete-data hold.** Initial price risk is 4.16%,
and the first target's cost-adjusted reward/risk is 0.911. The following
observed minute opens reach only 0.044 initial price R. The original larger-D
stop starts at $94.2408; saved protection records raise it to $96.2482 at
23:00 September 15 and $96.9334 at 09:00 September 16. The latter stop
triggers at 09:12. Thus this is not a full initial-stop loss: the recorded net
is -0.347 cost-inclusive R. There are 316 absent held minutes and partial
entry context. The observations do not support an uninterrupted candle-by-
candle account of the 18-hour hold or hypothetical earlier fills.

**SOL #9 is a failed first reversal despite a high target ratio.** The
11:30–11:45 candle makes D at $108.05 and a high at $109.31. The following
minute triggers $109.32; its observed high barely crosses the trigger.
Subsequent pre-exit minute opens reach only 0.088 initial price R. D and the
stop fail at 11:54. The highest observed price in the next two hours is
$109.027, still below entry. The initial target ratio was 7.760, so a large
target ratio does not protect against immediate reversal. Prior context is
partial even though every held minute is present.

**SOL #14 fails more slowly; #8 is another whipsaw.** #14 starts with a
2.92% price-risk distance and reaches only 0.261 initial price R at subsequent
minute opens. Three completed declining 15-minute bars confirm the existing
E1 exit, executed at the 01:30 minute opening, above the original stop.
Its shock was already steep: the shock's net close decline was 3.809 prior
ATR. #8 loses its D and exits around the stop, then has an observed opening
back above entry seven minutes later at 11:32. Its one missing held minute
and partial context remain flagged. Widening all stops would mix this
whipsaw with #28 and #9, whose observed weakness persists.

## Winners that constrain possible explanations

The audit pairs every large loser with the nearest positive-net trade in the
same asset, route and early/late period, preferring matching data-exposure
status. These are descriptive comparisons selected after outcomes, not
prospective matched controls. The full pairing table includes small winners,
not just spectacular recoveries.

| Winner | Entry New York | Net per $10,000 entry | Relevant counterexample |
|---|---|---:|---|
| BTC #41 B1 | Oct 8 10:00 | +$31.42 | Same day as #42; a target ratio of 4.840 and modest later gain, not a different entry family |
| BTC #21 B1 | Sep 15 11:03 | +$34.60 | Same day as #20; partial context and newly confirmed D can still precede a winner |
| BTC #44 B1 | Oct 12 21:00 | +$268.66 | Newly confirmed D is in the immediately prior candle, like several fast losers |
| SOL #29 B1 | Oct 29 20:53 | +$323.39 | Same evening as #28; initial entry candle closes below entry and multiple subsequent candles remain weak, but D holds |
| SOL #15 B1 | Oct 15 10:06 | +$280.78 | Newly confirmed D and 1.47% initial price risk; wins after the earlier #14 rebound fails |
| SOL #18 B1 | Oct 18 16:27 | +$420.62 | Entry candle closes below entry, followed by a red 16:30 candle; later continuation produces the largest SOL winner |

BTC #44's 20:45–21:00 reference makes D at $80,942.813. The entry follows at
$81,397.246 during the 21:00 minute. The 21:00, 21:15, 21:30 and 21:45 candles
show continued upside. The original first 25% exits at $82,962.1950 at 22:57,
and the remaining 75% at $83,835.33 at 04:29 October 13. Its net is +3.842
cost-inclusive R. Excluding all entries whose immediately prior candle
contains D would also exclude this winner's original entry; no alternative
entry or P/L has been simulated here.

SOL #29 has a wider 2.90% initial price-risk distance than many losers. Entry
is $94.67, stop $91.9272, D $92.1859. Its 20:45 candle closes at $94.651,
21:00 at $94.5926 and 21:15 at $93.7314. Those prices are below entry, but
they do not break the original D. The later rebound exits at $97.77 at
01:59 October 30, without hitting the original first target. Requiring every
new trade's first candle to finish above entry would label this winner weak.
This does not prove that every D-holding pullback should be retained.

Across the earlier BTC cohort, median maximum favorable movement at observed
subsequent minute openings is 1.170 price R for winners versus 0.242 for
losers. In earlier SOL it is 1.923 versus 0.044. These outcomes describe why
the trades made or lost money; they are not features available at entry.
An exit test would need a predeclared observation window and causal structure
conditions before any separate comparison could establish its value.

## Why the earlier period loses

**Winner size matters more than a modest change in hit rate.** Earlier BTC
wins 45.2% of trades, compared with 50.0% later. However, its average net
winner is 58% smaller. Nineteen earlier winners contribute +$494.11 while
twenty-three losers consume $827.30, producing -$333.19. In the final month,
nineteen winners contribute +$1,176.46 against $648.51 of losses. The three
largest final-month BTC winners contribute +$605.57, more than that month's
entire +$527.95 fixed-notional net. This is concentrated profitability, not
uniformly better trades.

Earlier SOL has four winners totaling +$251.73 against five losses totaling
$486.76. Its average loser is 2.30 times the final month's average loser.
The median initial price-risk distance among earlier SOL losers is 1.372%,
versus 0.833% later. All nine earlier trades are B1; there is no evidence that
changing A is the primary remedy. The three biggest final-month SOL winners
contribute +$1,024.79, about 64.8% of that month's +$1,581.86 net.

**The broad trend explanation is insufficient.** The saved source prices give
same-cost earlier-segment buy-and-hold returns of +29.12% for BTC and +43.63%
for SOL. The final month's corresponding returns are -9.48% and -20.81%.
The short-term bounce entries lose during an overall rising period and win
during the later falling period. These facts describe sampled price paths,
not macroeconomic causes or a clean regime classifier. Inference: individual
bounce quality and captured payoff matter more here than a simple full-period
up/down label.

**Original costs are material but do not fully explain the losses.** Earlier
BTC gross fixed-notional P/L is -$165.22 before $167.97 in proxy costs; SOL is
-$199.07 before $35.96 in costs. Removing the cost proxy would still leave
both earlier books negative. Actual spot fees could worsen the results.

**Coverage changes the sample, especially for SOL.** Earlier BTC contains
82,089 of 86,400 expected minutes (95.01%); later BTC contains 42,642 of
43,200 (98.71%). Earlier SOL contains 59,626 minutes (69.01%), versus 41,446
(95.94%) later. All nine earlier SOL entries have partial context; there is
no unflagged earlier SOL cohort. Earlier BTC's seventeen unflagged trades
still total -$287.28, so missing-data flags alone do not explain BTC's loss.
Dropping flagged original trades is only a fixed-entry description, not a new
sequential backtest with replacement opportunities.

## What is established and what remains untested

The frozen B1 branch permits a completed off-low reference candle containing
D to serve as the first stabilization; it does not require an independent
post-D hold or an HL. Its shock measure is the downward excursion from the
larger of the opening and preceding close to the low, divided by pre-shock
ATR. The audit separately reports full range and net-close decline; these
must not be confused with the actual frozen qualification formula.

Some losers fit that aggressive design and fail. Other losers already have
a separate holding candle. The largest winners can share both designs.
Steeper shocks, wider stops, a 2R cutoff or a fast first-candle failure exit
cannot be declared improvements from these examples. SOL #9 has 7.760 target
R and still fails; an earlier SOL winner, #1, has 1.204 and earns +$129.56.
Zero-volume entry-minute references also appear in large winners, so they
must not be treated as proof of a weak signal or verified execution liquidity.

A useful next investigation would label post-entry failures into immediate
D breaks, persistent lower-high/lower-low sequences while D still holds, and
normal D-holding pullbacks. Each label needs an explicit decision time and
only then-available information. Test candidate distinctions against #44,
SOL #29 and #18 before considering another full comparison. No candidate
rule is selected, enabled, optimized or replayed by this audit.

The rules were developed using the overlapping final month, so that month's
stronger result also carries selection and development bias. The historical
sixty-day extension is informative but is not prospective validation.

## Evidence and preservation

Run `python3 scripts/audit_unfiltered_90_losses.py` to reproduce the read-only
calculations. This does not instantiate a strategy or fetch quotes. Evidence
is in `reports/unfiltered_90_losses_2026_11_10/`:

- `AUDIT.json` and `ALL_E1_TRADES.csv`: every original E1 trade, exact original
  legs, setup/exit evidence, context flags, stop references and diagnostics.
- `PERIODS.csv` and `COHORTS.csv`: boundary-equity accounting, coverage,
  win/loss, cost, route and outcome breakdowns.
- `CASES.csv` and `WINNER_PAIRS.csv`: five largest losses per asset, matched
  winners and largest winners from each segment; twenty-seven distinct cases.
- `CASE_1MIN.csv` and `CASE_15MIN.csv`: 10,997 actual minute observations
  across case windows and 785 retrospective fifteen-minute aggregates.
  Overlapping case windows repeat genuine observations under different case
  IDs. Incomplete aggregates report actual coverage; no missing bucket is
  filled. Retrospective bar highs/closes are not available before bar end.
- `PROTECTION.csv`: original initial stops, raises and other exit references.
- `BASELINE_HASHES.json`: 1,029 preserved files, including the original
  ninety-day study, prior study controls/selectors and frozen strategy files.

All thirteen frozen source hashes match. BTC worker PID 56139/session
`20261109T175620Z` and SOL worker PID 68200/session `20261110T033411Z` remain
unchanged and running. P1, frozen 0.2, original study data and outputs, both
workers, their parameters and the live dashboard are unchanged. No orders,
broker-paper orders, new market-data requests or full-month replay occur.
