#!/usr/bin/env python3
"""Weekday morning check-in on the core sector, run locally via launchd.

This exists because the cloud-routine version of this check (see
research/ for the abandoned attempt) cannot work at all: Anthropic's cloud
sandboxes block outbound access to data.alpaca.markets at the network-proxy
level, before any request reaches Alpaca. That is a fixed platform boundary,
not a credentials problem, and there is no environment setting that lifts it.
Running locally sidesteps it entirely -- this machine already talks to Alpaca
every time the dashboard itself runs.

What this reports, in order:
  1. The core sector ("AI Optical / Interconnect", CORE_GROUP below) --
     momentum across every lookback, and whether it currently qualifies as a
     reversal candidate.
  2. A rotation flag if a *different* group is #1 at the 1-day or 5-day
     lookback -- surfaced, not buried, since that is the one fact that
     contradicts "stay anchored on this sector".
  3. Earnings landing within EARNINGS_WINDOW_DAYS for the core group's own
     constituents (not portfolio-aware -- this has no access to any trade
     journal, and does not need one).

Per this repo's Rule #1 (AGENTS.md / CLAUDE.md-adjacent convention
established throughout trading_desk/): a failed fetch is reported as a
failure, never papered over with fabricated numbers. See the `except`
block in main() -- it writes and notifies the failure itself, not a guess.
"""

from __future__ import annotations

import subprocess
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRADING_DESK = HERE.parent
sys.path.insert(0, str(TRADING_DESK))

import earnings  # noqa: E402
import server  # noqa: E402
import universe  # noqa: E402

CORE_GROUP = "AI Optical / Interconnect"
EARNINGS_WINDOW_DAYS = 3
OUT_DIR = TRADING_DESK / "research" / "morning-checkin"
LATEST_PATH = OUT_DIR / "latest.txt"


def _applescript_quote(s: str) -> str:
    """Double-quoted AppleScript string literal.

    Python's repr() produces single-quoted output, which is not a valid
    AppleScript string -- that shipped as the first version of this function
    and broke every notification with a syntax error. AppleScript only
    escapes backslash and double-quote inside a "..." literal.
    """
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title: str, message: str) -> None:
    """macOS banner notification. Best-effort -- a failure here must never
    take down the check-in itself, so any error is swallowed after being
    written to stderr (the launchd log still captures it)."""
    try:
        # osascript, not a third-party notifier: works on any Mac with no
        # install step, which matters for a script that has to survive
        # unattended for months.
        script = (
            f"display notification {_applescript_quote(message)} "
            f"with title {_applescript_quote(title)}"
        )
        subprocess.run(["osascript", "-e", script], check=False, timeout=10)
    except Exception as e:  # noqa: BLE001 - notification is a nice-to-have
        print(f"[warn] notification failed: {e}", file=sys.stderr)


def fmt_pct(v: float | None) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.2f}%"


def group_row(rankings: list[dict], name: str) -> tuple[dict | None, int | None]:
    """A group's own ranking row, plus its 1-indexed rank in that lookback."""
    for i, g in enumerate(rankings, start=1):
        if g["group"] == name:
            return g, i
    return None, None


def build_report(today: date) -> str:
    server.resolve_feed()
    board = server.build_board()

    lines: list[str] = []
    lines.append(f"Trading desk morning check-in -- {today.isoformat()}")
    lines.append(f"Core sector: {CORE_GROUP}")
    lines.append(f"Feed: {board.get('feed', '?')}" + (" (STALE)" if board.get("stale") else ""))
    lines.append("")

    # --- 1. core sector across every lookback -----------------------------
    lines.append(f"== {CORE_GROUP} ==")
    core_row_5d = None
    for lb in ("1", "2", "3", "4", "5"):
        slice_ = board["lookbacks"].get(lb)
        if not slice_:
            continue
        row, rank = group_row(slice_["rankings"], CORE_GROUP)
        if row is None:
            lines.append(f"  {lb}D: not priced today (omitted -- see board's own omitted list)")
            continue
        if lb == "5":
            core_row_5d = {**row, "_rank": rank}
        rev_flag = ""
        reversal = slice_.get("reversal")
        if reversal:
            rev_row, _ = group_row(reversal.get("rankings", []), CORE_GROUP)
            if rev_row:
                rev_flag = (
                    f"  [REVERSAL CANDIDATE: {rev_row['breadth_pct']:.0f}% of members reversed, "
                    f"avg bounce {fmt_pct(rev_row['avg_trigger_return_pct'])}]"
                )
        lines.append(
            f"  {lb}D: mean {fmt_pct(row['mean_return_pct'])}  median {fmt_pct(row['median_return_pct'])}  "
            f"breadth {row['breadth_pct']:.0f}%  rank #{rank}/14{rev_flag}"
        )
    lines.append("")

    # --- 2. rotation flag ---------------------------------------------------
    lines.append("== Rotation check ==")
    for lb, label in (("1", "1-day"), ("5", "5-day")):
        slice_ = board["lookbacks"].get(lb)
        if not slice_ or not slice_.get("rankings"):
            continue
        leader = slice_["rankings"][0]
        if leader["group"] == CORE_GROUP:
            lines.append(f"  {label}: core sector IS the #1 group ({fmt_pct(leader['mean_return_pct'])}).")
        else:
            lines.append(
                f"  {label}: ROTATION -- #1 is '{leader['group']}' "
                f"({fmt_pct(leader['mean_return_pct'])}), not the core sector."
            )
    lines.append("")

    # --- 3. earnings within the window, core group's constituents only -----
    lines.append(f"== Earnings within {EARNINGS_WINDOW_DAYS}d ({CORE_GROUP} only) ==")
    constituents = universe.all_groups()[CORE_GROUP]["constituents"]
    events_by_symbol = earnings.load_event_file()
    missing = [s for s in constituents if s not in events_by_symbol]
    if missing:
        # Cache miss (a new name added to the group, or the cache predates
        # it) -- fetch just the gap rather than the whole 271-symbol universe.
        sys.path.insert(0, str(TRADING_DESK / "research"))
        import earnings_dates as ed  # noqa: E402

        fresh = ed.collect(missing)
        events_by_symbol.update(fresh)

    flagged = []
    for sym in constituents:
        proj = earnings.project_next(events_by_symbol.get(sym, []), today)
        if proj and proj["days_until"] <= EARNINGS_WINDOW_DAYS:
            flagged.append((sym, proj))
    if flagged:
        for sym, proj in sorted(flagged, key=lambda t: t[1]["days_until"]):
            timing = proj.get("expected_timing", "unknown")
            lines.append(f"  {sym}: {proj['projected_date']} (in {proj['days_until']}d, {timing})")
    else:
        lines.append(f"  none in the next {EARNINGS_WINDOW_DAYS} days")
    lines.append("")

    return "\n".join(lines), core_row_5d


def notification_summary(core_row_5d: dict | None, flagged_count: int) -> str:
    if core_row_5d is None:
        return "No 5D data for the core sector today -- see latest.txt."
    parts = [f"5D {fmt_pct(core_row_5d['mean_return_pct'])}, rank #{core_row_5d.get('_rank', '?')}"]
    if flagged_count:
        parts.append(f"{flagged_count} earnings within {EARNINGS_WINDOW_DAYS}d")
    return " | ".join(parts)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).astimezone().date()

    try:
        report, core_row_5d = build_report(today)
    except Exception as e:  # noqa: BLE001 - report the failure, never guess data
        report = (
            f"Trading desk morning check-in -- {today.isoformat()}\n"
            f"FAILED: could not build today's report.\n\n"
            f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}"
        )
        LATEST_PATH.write_text(report)
        (OUT_DIR / f"{today.isoformat()}.txt").write_text(report)
        notify("Trading Desk check-in FAILED", f"{type(e).__name__}: {e}")
        print(report, file=sys.stderr)
        return 1

    LATEST_PATH.write_text(report)
    (OUT_DIR / f"{today.isoformat()}.txt").write_text(report)
    print(report)

    flagged_count = report.count("(in ")  # cheap count of earnings rows above
    notify("Trading Desk morning check-in", notification_summary(core_row_5d, flagged_count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
