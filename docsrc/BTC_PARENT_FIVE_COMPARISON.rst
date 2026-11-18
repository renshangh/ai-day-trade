15-minute parent HL and five-minute trigger
===========================================

Read the separate PH5 historical comparison on the Trading Desk.

:Last Updated: 2026-11-15
:Status: Research complete; negative experimental results; not promoted
:Audience: Trading Desk owner and maintainers

Overview
--------

Open ``/btc-parent-five``. The page reads saved research; it cannot start
a worker, fetch prices, rerun a test or submit an order. Frozen 0.2, P1 and
the original BTC Live Paper worker remain unchanged. All three original
monthly controls reproduced exactly before evaluating the experiment.

PH5 is a separate entry family. A confirmed 15-minute parent low must pass
the existing independence distances: two complete holding bars, a rebound
of at least one preceding ATR and a close at least half an ATR above D.
Higher internal lows do not replace that parent. After a confirmed rebound
and later confirmed 15-minute HL, a separate complete five-minute bar must
hold strictly above HL. Price must then exceed the immediately preceding
complete five-minute high. There is no fitted acceleration cutoff.

The original 15-minute ATR, chase ceiling, parent-D stop buffer, targets,
25% first sale, exits and two-basis-point-per-side cost proxy remain intact.
Five-minute observations are never relabeled as fifteen-minute candles.
Missing minutes clear the new setup and remain absent. An entry consumes
its setup history; fresh complete candles must rebuild it.

Read the results
----------------

The page compares original A/B, PH5 alone and A/B plus PH5 for each of the
0.1/E1/E2 exit models. Added entries may change subsequent position and
setup availability; original A/B retains simultaneous-entry priority.
The fixed test window is October 10 through November 9, 2026 UTC, with
seven days of warmup. This repeatedly studied month is in-sample.

All PH5-only and combined variants lost money. The combined 0.1 result is
-$2,295.15 versus +$3,516.46 for the original control. No parameters were
subsequently adjusted to improve those results.

The November 14/15 bounce is separate and outside the test month. PH5
enters at 23:47 EST at a $64,826.61 reference, then the unchanged failed-
rebound exit closes 100% at 00:48 for -$135.66 per initial BTC. Its planned
25% target was not reached. This definition neither catches the initial
straight-up move nor retains the consumed parent for the later rally.

Every trade includes entry, initial stop, target, first 25% sale when
present, remaining/full exit, prices and P/L. Review the selected trade's
15-minute chronological ledger and genuine five-minute entry bars. All
crossings, including rejected/held candidates, remain visible. Download
TRADES, EXITS, PROTECTION, SIGNALS and LEDGER CSVs or the result JSON.

Interpretation and limitations
------------------------------

Results use an initial one BTC per trade, not compounded account returns
or actual ETF/crypto fills. Closed-trade drawdown is shown in R, separately
from net dollar P/L; it is not minute-level account-equity drawdown.
No-flagged-gap and flagged complementary groups are separate. No flagged
gap does not certify all older resistance context is complete. Venue-only
volume and quote-derived minutes cannot establish consolidated volume,
depth or executable fills. Historical minute and receipt times are
distinct; the new strategy was not running at those historical times.

For the locked definition, exact source fingerprint and full findings see
``docs/investigations/2026-11-15_BTC_PARENT_FIVE_COMPARISON.md``.
``scripts/retest_btc_parent_five.py`` writes only its independent study
directory and selector. It verifies the frozen bundle, original worker
PID/session, P1 and existing selectors before and after replay. The full
replay is bounded to twenty minutes. No broker client is used.
