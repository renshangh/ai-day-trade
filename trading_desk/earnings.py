"""Project when a company next reports, and how violently it usually moves.

This is a **timing-awareness** tool, not a signal. The measured pre-earnings
drift (see `research/`) was +0.82% excess with 9x that in noise -- far too thin
to trade on directly at a 1-2 position cadence. What *is* reliably useful is
knowing a print is coming, so a swing position is never held through one by
accident.

Projection method
-----------------
Dates come from historical 8-K item 2.02 announcements
(`research/earnings_dates.json`). A 52-week step picks *which* fiscal slot comes
next; the date itself is then the **calendar anniversary** of that slot, snapped
to the weekday the company habitually reports on.

Two earlier approaches were measured and rejected:

1. **Median inter-quarter gap.** Gaps drift (89/91/92/93 days) and chaining
   medians forward from the last known date compounds the error.
2. **Plain +364-day stepping.** It preserves the weekday but is 1.25 days short
   of a year, so it creeps earlier every cycle: 1217 projections early against 92
   late, modal error exactly -7 days. Trying to correct it with a measured
   year-over-year drift failed too, because matching "nearest announcement to a
   364-day step" is circular and reports ~0 drift by construction.

Switching to calendar anniversaries cut median error from 7 days to 2.

Every projection is an **estimate** and is returned with an empirical uncertainty
band, never as a confirmed date. Confirm from the company's IR page before acting
on any of it.
"""

from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta
from pathlib import Path

# 52 weeks: used only to pick which fiscal slot comes next, not to date it.
YEAR_STEP_DAYS = 364
# A same-slot anniversary must sit within this tolerance to join a slot chain.
SLOT_MATCH_TOLERANCE_DAYS = 21

# Measured accuracy, from a 1437-projection no-lookahead backtest (each made 20
# days before the real announcement) -- see research/README.md:
#   median |error| 2 days, p75 7 days, p90 8 days, 97.6% within 14 days.
#
# No available feature predicted *which* projections would be wrong: neither the
# number of corroborating years nor the length of filing history discriminated
# (within-7-days ran 79-92% across every bucket, with no monotonic trend). So
# rather than ship a three-tier confidence label that looked informative and
# wasn't, every projection carries the same empirical band.
PROJECTION_MEDIAN_ERROR_DAYS = 2
PROJECTION_P90_ERROR_DAYS = 8


def load_event_file() -> dict[str, list[dict]]:
    """Historical announcements collected by research/earnings_dates.py.

    Returns {} when the file is absent so callers can degrade with a message
    rather than crash -- the collector is a separate, occasional job.
    """
    path = Path(__file__).resolve().parent / "research" / "earnings_dates.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _parse(d: str) -> date | None:
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _shift_off_weekend(d: date) -> date:
    """Nudge a weekend projection to the adjacent weekday.

    Companies do not report on Saturdays. Saturday leans back to Friday, Sunday
    forward to Monday -- whichever is closer to the projected day.
    """
    if d.weekday() == 5:      # Saturday
        return d - timedelta(days=1)
    if d.weekday() == 6:      # Sunday
        return d + timedelta(days=1)
    return d


def _slot_chain(dates: list[date], anchor: date) -> list[date]:
    """The same fiscal slot as `anchor`, traced back year by year, oldest first.

    Walks backwards in 52-week steps and keeps the nearest real announcement at
    each step, so drift is measured along one slot rather than across all four.
    """
    chain = [anchor]
    cursor = anchor
    for _ in range(6):
        target = cursor - timedelta(days=YEAR_STEP_DAYS)
        near = [d for d in dates if abs((d - target).days) <= SLOT_MATCH_TOLERANCE_DAYS]
        if not near:
            break
        cursor = min(near, key=lambda d: abs((d - target).days))
        chain.append(cursor)
    chain.reverse()
    return chain


def _calendar_anniversary(source: date, today: date) -> date | None:
    """Same month/day as `source`, in the first year that lands after `today`."""
    for add_years in range(0, 8):
        year = source.year + add_years
        try:
            cand = date(year, source.month, source.day)
        except ValueError:          # Feb 29 in a non-leap year
            cand = date(year, source.month, 28)
        if cand > today:
            return cand
    return None


def _snap_to_weekday(d: date, weekday: int) -> date:
    """Nearest date to `d` falling on `weekday` (0=Mon). Ties go later."""
    best = d
    best_gap = 99
    for delta in range(-3, 4):
        cand = d + timedelta(days=delta)
        if cand.weekday() == weekday and abs(delta) < best_gap:
            best, best_gap = cand, abs(delta)
    return best


def project_next(events: list[dict], today: date) -> dict | None:
    """Next expected announcement, or None when history can't support a guess.

    `events` are the raw records from earnings_dates.json (newest first).
    """
    parsed = sorted(
        [(_parse(e.get("date", "")), e.get("timing", "unknown")) for e in events],
        key=lambda t: (t[0] or date.min),
    )
    parsed = [(d, t) for d, t in parsed if d is not None]
    if not parsed:
        return None

    dates = [d for d, _ in parsed]
    last_seen = dates[-1]

    # Candidate projections: every past announcement stepped forward a year at a
    # time until it lands in the future. Stepping repeatedly (rather than once)
    # lets a symbol with a long gap in coverage still produce a candidate.
    candidates: list[tuple[date, date]] = []  # (projected, source)
    for d in dates:
        p = d
        guard = 0
        while p <= today and guard < 6:
            p = p + timedelta(days=YEAR_STEP_DAYS)
            guard += 1
        if p > today:
            candidates.append((p, d))
    if not candidates:
        return None

    projected, source = min(candidates, key=lambda t: t[0])

    # Refine to a *calendar* anniversary, then snap to the habitual weekday.
    #
    # Stepping 52 weeks preserves the weekday but is 1.25 days short of a year,
    # so it creeps earlier every cycle. Backtest showed the damage plainly: 1217
    # projections early against 92 late, with the modal error exactly -7 days.
    # Correcting it with a measured drift did not work either, because matching
    # "nearest announcement to a 364-day step" is circular -- it finds whatever
    # sits closest to 364 and reports ~0 drift.
    #
    # So anchor on the same month/day one or more years on (no accumulating
    # shortfall), then move to the nearest day matching the weekday this company
    # habitually reports on.
    chain = _slot_chain(dates, source)
    weekdays = [d.weekday() for d in chain]
    habitual_weekday = max(set(weekdays), key=weekdays.count) if weekdays else source.weekday()

    anniversary = _calendar_anniversary(source, today)
    adjusted = _snap_to_weekday(anniversary, habitual_weekday) if anniversary else projected
    adjusted = _shift_off_weekend(adjusted)

    # Never emit a date in the past -- the whole point is forward warning, and a
    # stale "next earnings" is worse than none. The weekday snap can move the
    # anniversary back by up to 3 days, so this is reachable. Returning None is
    # the honest answer: substituting "tomorrow" would assert an imminent print
    # on no evidence, and every other insufficient-history path here returns None.
    if adjusted <= today:
        return None

    # Expected release timing: what this company usually does, from the last few
    # announcements where it is known.
    known = [t for _, t in parsed[-6:] if t in ("before_open", "after_close")]
    timing = max(set(known), key=known.count) if known else "unknown"

    # The band is what a caller should actually plan against: a point estimate
    # implies precision the backtest does not support.
    band = PROJECTION_P90_ERROR_DAYS
    window_start = adjusted - timedelta(days=band)
    window_end = adjusted + timedelta(days=band)

    return {
        "projected_date": adjusted.isoformat(),
        "days_until": (adjusted - today).days,
        # Conservative edge: if anything, assume the print lands early.
        "earliest_plausible": window_start.isoformat(),
        "latest_plausible": window_end.isoformat(),
        "days_until_earliest": (window_start - today).days,
        "uncertainty_days": band,
        "median_error_days": PROJECTION_MEDIAN_ERROR_DAYS,
        "expected_timing": timing,
        "based_on": source.isoformat(),
        "last_reported": last_seen.isoformat(),
        "history_count": len(dates),
        "slot_years": len(chain),
        "estimated": True,
    }


def earnings_move_stats(events: list[dict], bars: list[dict]) -> dict | None:
    """How much this name typically moves on its earnings reaction.

    The reaction session depends on release timing:
      after_close  -> the *next* session reacts
      before_open  -> the announcement session itself reacts

    Returns absolute-move statistics, which is what matters for timing risk --
    direction is not predictable, magnitude is somewhat persistent.
    """
    if not bars or not events:
        return None
    dates = [b["t"][:10] for b in bars]
    closes = [float(b["c"]) for b in bars]
    index_of = {d: i for i, d in enumerate(dates)}

    moves: list[float] = []
    for e in events:
        timing = e.get("timing")
        d = e.get("date", "")[:10]
        if timing not in ("before_open", "after_close"):
            continue
        if timing == "after_close":
            base = index_of.get(d)
            if base is None:
                prior = [i for i, dd in enumerate(dates) if dd <= d]
                base = prior[-1] if prior else None
            react = base + 1 if base is not None else None
        else:
            react = index_of.get(d)
            base = react - 1 if react is not None else None
        if base is None or react is None:
            continue
        if not (0 <= base < len(closes) and 0 <= react < len(closes)):
            continue
        if closes[base] <= 0:
            continue
        moves.append(abs(closes[react] / closes[base] - 1.0) * 100)

    if not moves:
        return None
    # statistics.median, not moves_sorted[n // 2]: the hand-rolled version takes
    # the upper-middle element for even n, and even n is the normal case here
    # (two years of quarters). On [4.76, 5.0, 10.0, 20.0] it returned 10.0 where
    # the median is 7.5 -- a 33% overstatement of the risk figure the table shows.
    return {
        "n": len(moves),
        "mean_abs_move_pct": statistics.fmean(moves),
        "median_abs_move_pct": statistics.median(moves),
        "max_abs_move_pct": max(moves),
    }
