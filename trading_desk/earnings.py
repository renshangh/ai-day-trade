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
# One week of post-earnings follow-through, measured from the pre-earnings
# close so the figure includes the initial gap.
POST_EARNINGS_WEEK_SESSIONS = 5

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
        if cand >= today:
            return cand
    return None


def _snap_to_weekday(d: date, weekday: int, not_before: date | None = None) -> date:
    """Nearest date to `d` on `weekday` (0=Mon), never earlier than `not_before`.

    The floor matters: snapping a Tuesday anniversary back to a habitual Monday
    would otherwise land yesterday and get thrown out as a past date, losing a
    print that is actually due today.
    """
    best = d
    best_gap = 99
    for delta in range(-3, 4):
        cand = d + timedelta(days=delta)
        if not_before is not None and cand < not_before:
            continue
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

    # Pick the slot by *calendar* anniversary, not by 364-day stepping.
    #
    # Stepping to choose the slot reintroduced the shortfall the anniversary
    # refinement exists to remove: from a 2025-08-18 print it lands on
    # 2026-08-17, one day before a 2026-08-18 "today", then skips a whole year
    # and reported the next print as 366 days away instead of tonight.
    candidates: list[tuple[date, date]] = []  # (anniversary, source)
    for d in dates:
        ann = _calendar_anniversary(d, today)
        if ann is not None:
            candidates.append((ann, d))
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
    adjusted = (_snap_to_weekday(anniversary, habitual_weekday, not_before=today)
                if anniversary else projected)
    adjusted = _shift_off_weekend(adjusted)

    # Never emit a date in the *past* -- a stale "next earnings" is worse than
    # none, and substituting "tomorrow" would assert an imminent print on no
    # evidence, so this returns None like every other insufficient-history path.
    #
    # Today itself is allowed, and is the single most important day to show: a
    # company reporting after tonight's close is still ahead of the reader, and
    # excluding today rolled those prints forward a whole year.
    if adjusted < today:
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
    """How this name behaves after it reports -- over one session and one week.

    The reaction session depends on release timing:
      after_close  -> the *next* session reacts
      before_open  -> the announcement session itself reacts

    Both horizons are measured from the same pre-earnings close, so the 1-week
    figure *includes* the initial gap rather than starting after it. That is what
    someone holding through the print actually experiences.

    Each horizon reports two things, because they answer different questions:

    - **absolute** (median/mean/max) -- how violent the print usually is,
      regardless of direction. This is the risk number: direction is not
      predictable, magnitude is somewhat persistent.
    - **signed** median -- whether the reaction has historically leaned up or
      down for this particular name. Informative, not a forecast; FN fell on 6
      of its last 8 prints, which is worth seeing before holding through one.
    """
    if not bars or not events:
        return None
    dates = [b["t"][:10] for b in bars]
    closes = [float(b["c"]) for b in bars]
    index_of = {d: i for i, d in enumerate(dates)}

    day_moves: list[float] = []
    week_moves: list[float] = []
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
        day_moves.append((closes[react] / closes[base] - 1.0) * 100)

        # One week = POST_EARNINGS_WEEK_SESSIONS sessions on from the same
        # pre-earnings close. Skipped rather than truncated when the history
        # runs out, so a partial window is never reported as a full week.
        week_idx = base + POST_EARNINGS_WEEK_SESSIONS
        if week_idx < len(closes):
            week_moves.append((closes[week_idx] / closes[base] - 1.0) * 100)

    if not day_moves:
        return None

    abs_day = [abs(x) for x in day_moves]
    out = {
        "n": len(day_moves),
        "mean_abs_move_pct": statistics.fmean(abs_day),
        "median_abs_move_pct": statistics.median(abs_day),
        "max_abs_move_pct": max(abs_day),
        "median_signed_move_pct": statistics.median(day_moves),
        "up_count": sum(1 for x in day_moves if x > 0),
        "down_count": sum(1 for x in day_moves if x <= 0),
    }
    if week_moves:
        abs_week = [abs(x) for x in week_moves]
        out.update({
            "n_week": len(week_moves),
            "median_abs_move_1w_pct": statistics.median(abs_week),
            "mean_abs_move_1w_pct": statistics.fmean(abs_week),
            "max_abs_move_1w_pct": max(abs_week),
            "median_signed_move_1w_pct": statistics.median(week_moves),
            "up_count_1w": sum(1 for x in week_moves if x > 0),
            "down_count_1w": sum(1 for x in week_moves if x <= 0),
        })
    return out
