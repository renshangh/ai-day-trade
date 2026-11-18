# BTC Bounce Entry Audit November 14 and 15

Causal A/B entry-gate diagnosis for the $61,991 to $66,085 recovery, with separate five-minute timing evidence.

Last Updated: 2026-11-15
Status: Read-only diagnostic; frozen 0.2 and original worker unchanged
Audience: Trading Desk owner and maintainers

## Overview

The frozen strategy did not admit a setup during this bounce. A never reached four independent LL phases; B had no active 2-ATR bearish new-low shock episode. A prior-candle high break alone cannot open a position. The missing trade is a strategy-coverage gap for this case, not a broker-hours block or a late high-break trigger.

All times below are New York EST. The $61,991.3285 low occurred November 14 at 20:45; the $66,085.424 high occurred November 15 at 04:12. This was two strong advances separated by a substantial pullback, not one uninterrupted vertical move.

## Exact reproduction and causal boundaries

The isolated replay read 18,258 actual persisted one-minute observations from the original warmup through November 15 05:16 EST. It reproduced all 20 entries and all 20 exit legs per model for 0.1/E1/E2 through that cutoff. It did not call finish(), run a month, fetch prices, write to the live database, change strategy source, or restart a worker. One earlier prefix gap remains absent; every 15m candle shown here has 15 observed minutes and every 5m diagnostic candle has five.

During the low-to-peak interval all 448 observed minutes were flat/available for model entry. In 138 minutes price exceeded the preceding complete 15m candle high plus $0.01. These are crossing minutes, not 138 independent trade opportunities. No A/B route reached the downstream entry screen. Chase, target availability, costs and 2R therefore were not the reason these entries were blocked; 2R remains advisory.

A candle's after-close state cannot be used at its opening. The tables distinguish the state entering the candle from its after-close count. The worker completes a 15m aggregate on processing the next observed minute, usually about another minute after the nominal close; the JSON retains exact receipt times.

## Why A failed

The prior B1 trade #20 entered at the November 14 18:19 reference minute, detected 18:20:13. Its entry consumed prior A/B setup history. Only fresh complete candles from 18:30 could rebuild an entry. This reset happens at entry, not at the later 19:29 exit. Reusing earlier lower lows would contradict the frozen consumed-history rule.

The decline to $61,991 was mostly continuous: several successively lower candles were extensions of one phase, not four independently rebounding wave lows. The bottom's 20:45 candle became the first independent LL only after the 21:00–21:15 right-hand candle completed; the worker knew this at 21:16:04.

The rebound also broke above the old $64,543.885 decline origin. When the $65,553.438 peak in the 22:00 candle became confirmed by the 22:15–22:30 right-hand candle (worker receipt 22:31:01), that older declining A scope was removed. This is why the $61,991 parent D did not carry forward as an A continuation anchor.

The subsequent wider decline had only these three independent lows, confirmed at 23:30, 01:30 and 03:15 respectively: $64,620.60 at 23:09; $64,137.90 at 01:10; $63,735.105 at 02:51. Intermediate rebound peaks were lower highs. The final 03:00 confirmation reached the worker at 03:16:05. At the next upside break A still had three, not four, lows. Price itself did make higher highs; the A validator deliberately does not arm its own HH/HL stage until four LLs are established.

The larger chart sequence $61,991 → $65,553 → $63,735 → $66,085 is reasonably read as a parent-wave HL continuation. That is a different structure from the frozen four-LL reversal. The separate parent-wave continuation research was not promoted into this live worker.

## Why B1 and B2 failed

B requires one complete red 15m candle making a new scope low with max(open, previous close) minus low at least twice the ATR known before that candle. It does not accumulate several moderate red candles into one shock. Recent volatility had already elevated ATR. The decisive examples are:
| 15m candle start | Direction | Downward excursion | Prior ATR | Required 2×ATR | Actual multiple | New B episode |
| --- | --- | --- | --- | --- | --- | --- |
| 11/14 20:00 | red | 857.60 | 627.95 | 1,255.90 | 1.366× | No: below 2×ATR |
| 11/14 20:15 | red | 371.41 | 652.61 | 1,305.22 | 0.569× | No: below 2×ATR |
| 11/14 20:30 | red | 448.32 | 649.79 | 1,299.57 | 0.690× | No: below 2×ATR |
| 11/14 20:45 | green | 86.30 | 600.91 | 1,201.81 | 0.144× | No: green candle |
| 11/15 02:30 | red | 480.04 | 276.19 | 552.38 | 1.738× | No: below 2×ATR |

The 20:45 bottom candle closed green, so it could not originate a bearish shock. The 02:30 second-leg decline was red and made a fresh scope low, but reached only 1.738×ATR. No shock chain was seeded. B1 could not use a stabilization/high-break without that chain; B2 could not attach the later rebound and HL to a nonexistent valid shock episode. Rebound speed does not override either prerequisite.

## Every completed 15m candle through the recovery peak

A count is the maximum across all eligible declining scopes, not just the selected internal scope. Every row had no ready A/B route while it was being processed. The B column describes whether the completed candle could seed a new episode; it is not a claim that its final values were known intrabar.

| 15m candle start EST | Low | High | Close | A LL open → after close | B episode failed because | After-close state received EST |
| --- | --- | --- | --- | --- | --- | --- |
| 11/14 20:45 | 61,991.33 | 62,758.46 | 62,578.61 | 0 → 0 | green | 11/14 21:01:10 |
| 11/14 21:00 | 62,457.86 | 64,120.65 | 63,817.57 | 0 → 1 | green | 11/14 21:16:04 |
| 11/14 21:15 | 63,721.88 | 64,597.99 | 64,458.00 | 1 → 1 | green | 11/14 21:31:13 |
| 11/14 21:30 | 64,388.90 | 64,929.16 | 64,794.30 | 1 → 1 | green | 11/14 21:46:07 |
| 11/14 21:45 | 64,573.35 | 65,018.46 | 64,869.05 | 1 → 1 | green | 11/14 22:01:01 |
| 11/14 22:00 | 64,823.72 | 65,553.44 | 65,168.11 | 1 → 1 | green | 11/14 22:16:10 |
| 11/14 22:15 | 64,955.80 | 65,315.39 | 64,963.70 | 1 → 0 | no new scope low | 11/14 22:31:01 |
| 11/14 22:30 | 64,757.15 | 65,142.50 | 65,116.81 | 0 → 0 | green | 11/14 22:46:10 |
| 11/14 22:45 | 64,705.96 | 65,135.86 | 64,788.49 | 0 → 0 | 0.607×ATR < 2 | 11/14 23:01:02 |
| 11/14 23:00 | 64,620.60 | 64,902.79 | 64,871.83 | 0 → 0 | green | 11/14 23:16:11 |
| 11/14 23:15 | 64,753.06 | 64,961.70 | 64,896.71 | 0 → 1 | green | 11/14 23:31:05 |
| 11/14 23:30 | 64,708.46 | 65,008.05 | 64,793.84 | 1 → 1 | no new scope low | 11/14 23:46:14 |
| 11/14 23:45 | 64,741.88 | 65,132.25 | 64,904.72 | 1 → 1 | green | 11/15 00:01:08 |
| 11/15 00:00 | 64,716.86 | 64,933.40 | 64,887.35 | 1 → 1 | no new scope low | 11/15 00:16:03 |
| 11/15 00:15 | 64,790.31 | 65,001.74 | 64,834.15 | 1 → 1 | no new scope low | 11/15 00:31:12 |
| 11/15 00:30 | 64,744.00 | 64,905.10 | 64,796.39 | 1 → 1 | no new scope low | 11/15 00:46:05 |
| 11/15 00:45 | 64,424.47 | 64,808.68 | 64,469.00 | 1 → 1 | 0.943×ATR < 2 | 11/15 01:01:15 |
| 11/15 01:00 | 64,137.90 | 64,501.46 | 64,227.97 | 1 → 1 | 0.944×ATR < 2 | 11/15 01:16:10 |
| 11/15 01:15 | 64,203.01 | 64,608.82 | 64,511.10 | 1 → 2 | green | 11/15 01:31:03 |
| 11/15 01:30 | 64,301.94 | 64,532.00 | 64,500.50 | 2 → 2 | no new scope low | 11/15 01:46:12 |
| 11/15 01:45 | 64,314.00 | 64,507.03 | 64,429.09 | 2 → 2 | no new scope low | 11/15 02:01:06 |
| 11/15 02:00 | 64,200.10 | 64,479.18 | 64,402.60 | 2 → 2 | 0.775×ATR < 2 | 11/15 02:16:15 |
| 11/15 02:15 | 64,278.03 | 64,519.06 | 64,320.69 | 2 → 2 | no new scope low | 11/15 02:31:09 |
| 11/15 02:30 | 63,847.21 | 64,361.14 | 63,864.13 | 2 → 2 | 1.738×ATR < 2 | 11/15 02:46:02 |
| 11/15 02:45 | 63,735.11 | 64,052.08 | 63,974.79 | 2 → 2 | green | 11/15 03:01:11 |
| 11/15 03:00 | 63,845.57 | 64,127.09 | 63,857.20 | 2 → 3 | no new scope low | 11/15 03:16:05 |
| 11/15 03:15 | 63,834.15 | 64,654.14 | 64,469.47 | 3 → 3 | green | 11/15 03:31:14 |
| 11/15 03:30 | 64,464.38 | 64,842.71 | 64,694.80 | 3 → 3 | green | 11/15 03:46:12 |
| 11/15 03:45 | 64,624.19 | 65,211.99 | 65,184.87 | 3 → 3 | green | 11/15 04:01:06 |
| 11/15 04:00 | 65,075.55 | 66,085.42 | 65,884.91 | 3 → 3 | green | 11/15 04:16:01 |

B2 was unavailable in every row because there was no valid B shock chain. A had no armed qualifying four-LL → HH → HL sequence. The first previous-15m-high crossing occurred at 20:58; the worker received that complete minute at 20:59:07, yet no route was ready.

## Five-minute timing and velocity diagnostic

Five-minute OHLC is aggregated only from real contiguous observed minutes. This is not the frozen 15m model rerun under new labels. A high break is a price observation, not a qualified A/B entry or a retrospective fill.

- **20:50:** price first crossed the completed 20:45–20:50 five-minute high of $62,327.46. That minute arrived at 20:51:09. This was earlier but more aggressive: no separate full post-D holding bar had completed yet.
- **20:58:** after the separate 20:50–20:55 five-minute candle held above D, price crossed its $62,557.72 high. That minute arrived at 20:59:07. The frozen 15m previous-high threshold ($62,650.22) was also crossed in that same minute. A/B setup eligibility, not trigger speed, was the blocker.
- **03:20:** price crossed the preceding five-minute high $63,948.505; received 03:21:14. The preceding 15m high $64,127.0925 was crossed at 03:21; received 03:22:00. Five-minute timing was approximately one minute earlier, while A still had only three lows and B still had no shock.
- **04:00:** both preceding 5m and 15m highs were $65,211.988. Both were crossed in the same observed minute; shortening the trigger timeframe added no lead here.

Use percentage change per minute or ATR-normalized speed rather than a visual 45°/85° angle, which changes with chart scaling. The following whole-bar measures become available only after the five-minute candle ends, not at its opening. The prior-hour comparison is descriptive, not a fitted trigger:

| 5m candle start EST | Open-to-close gain | Gain per minute | Prior 15m ATR per minute | Vs prior hour median absolute speed | Whole 5m data received EST |
| --- | --- | --- | --- | --- | --- |
| 11/14 21:05 | 1.326% | 0.265% | 0.283 | 4.4× | 11/14 21:10:10 |
| 11/15 03:20 | 0.642% | 0.128% | 0.274 | 5.0× | 11/15 03:25:05 |
| 11/15 04:00 | 0.921% | 0.184% | 0.326 | 6.8× | 11/15 04:05:13 |

Some breakout minutes were quote-derived with zero recorded venue volume, including the 03:21 15m breakout minute. This feed cannot establish consolidated buying volume, depth, an IBIT price, or an achievable fill. Full five-minute bars and first-cross receipts are retained in AUDIT.json.

## Interpretation and next comparison

This case supports studying a separate fast-recovery/parent-HL entry family. Five minutes can help locate a local hold and trigger, but merely shortening the clock leaves the frozen four-low/shock requirements unresolved. A potential comparison should retain the parent-wave context and structural stop, use five-minute stabilization/high-break evidence as a trigger, and measure speed causally in percent/ATR terms. It must then be tested against failed bounces and normal pullbacks, not selected on this successful bounce alone. No new speed cutoff, entry rule, stop, target or parameter is adopted here, and no hypothetical profit is credited.

The worker remains on its original PID/session with all 13 frozen source hashes, worker scripts, control/session and launch registration unchanged. Detailed original inputs, model reproduction, every after-close scope, every minute's gate state and receipt timestamps are in the adjacent AUDIT.json; PRESERVATION.json records the checks.
