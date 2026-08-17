"""Does price drift up into an earnings release? A measurement, not an assumption.

The question this answers: over the N sessions ending just before an earnings
announcement, does a stock return more than it normally returns over any N
sessions?

The baseline is the whole point. Every name in this universe sits in a strong
uptrend, so *any* 15-session window shows a positive average return. Reporting
"pre-earnings return is +3%" without a control would be measuring the bull
market and calling it a pattern. So every event is scored as an **excess**
against that same symbol's own mean N-session return over non-pre-earnings
windows.

Window placement respects release timing:
  after_close  -> the announcement day's own session is still pre-earnings
  before_open  -> the announcement day IS the reaction; window ends the day before
  intraday     -> ambiguous, excluded rather than guessed

Usage:  python3 drift_study.py
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

import server  # noqa: E402  - reuse its feed resolution, pagination and backoff
import universe  # noqa: E402

WINDOWS = [5, 10, 15, 21]      # trading sessions of run-up to test
DATES_FILE = HERE / "earnings_dates.json"
OUT_FILE = HERE / "drift_results.json"
# A baseline window must not overlap a pre-earnings run-up, nor sit in the
# immediate aftermath of a release.
POST_EVENT_BUFFER = 5


def load_events() -> dict[str, list[dict]]:
    if not DATES_FILE.exists():
        sys.exit(f"missing {DATES_FILE} -- run earnings_dates.py first")
    return json.loads(DATES_FILE.read_text())


def fetch_bars() -> dict[str, list[dict]]:
    server.resolve_feed()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=760)
    symbols = universe.all_symbols()
    print(f"fetching bars for {len(symbols)} symbols (feed={server.FEED})", file=sys.stderr)
    return server.fetch_daily_bars(symbols, start, end)


def study() -> dict:
    events_by_symbol = load_events()
    bars_by_symbol = fetch_bars()

    per_window: dict[int, dict] = {w: {"excess": [], "raw": [], "baseline": [], "hits": 0}
                                   for w in WINDOWS}
    per_symbol_rows: list[dict] = []
    skipped = {"no_bars": 0, "intraday": 0, "out_of_range": 0, "short_history": 0}
    events_used = 0
    symbols_used: set[str] = set()

    for sym, events in events_by_symbol.items():
        bars = bars_by_symbol.get(sym) or []
        if len(bars) < max(WINDOWS) + 30:
            skipped["no_bars" if not bars else "short_history"] += 1
            continue
        dates = [b["t"][:10] for b in bars]
        closes = [float(b["c"]) for b in bars]
        index_of = {d: i for i, d in enumerate(dates)}
        n = len(bars)

        # --- locate the last pre-earnings session for each usable event
        event_ends: list[int] = []
        for ev in events:
            timing = ev.get("timing")
            if timing == "intraday" or timing == "unknown":
                skipped["intraday"] += 1
                continue
            d = ev["date"]
            if timing == "after_close":
                # The release follows that day's close, so that session counts.
                idx = index_of.get(d)
                if idx is None:
                    # Announcement on a non-trading day: fall back to the last
                    # session at or before it.
                    prior = [i for i, dd in enumerate(dates) if dd <= d]
                    idx = prior[-1] if prior else None
            else:  # before_open -> the session before the announcement
                prior = [i for i, dd in enumerate(dates) if dd < d]
                idx = prior[-1] if prior else None
            if idx is None:
                skipped["out_of_range"] += 1
                continue
            event_ends.append(idx)

        if not event_ends:
            continue

        for w in WINDOWS:
            # Indices whose window would overlap any event's run-up or aftermath.
            tainted: set[int] = set()
            for e in event_ends:
                for k in range(e - w, e + POST_EVENT_BUFFER + 1):
                    tainted.add(k)

            baseline_rets = [
                closes[i] / closes[i - w] - 1.0
                for i in range(w, n)
                if i not in tainted and closes[i - w] > 0
            ]
            if len(baseline_rets) < 20:
                continue
            base_mean = statistics.fmean(baseline_rets)

            for e in event_ends:
                if e - w < 0 or closes[e - w] <= 0:
                    continue
                raw = closes[e] / closes[e - w] - 1.0
                per_window[w]["raw"].append(raw * 100)
                per_window[w]["baseline"].append(base_mean * 100)
                per_window[w]["excess"].append((raw - base_mean) * 100)
                if raw > 0:
                    per_window[w]["hits"] += 1
                if w == WINDOWS[0]:
                    events_used += 1
                symbols_used.add(sym)

        per_symbol_rows.append({"symbol": sym, "events": len(event_ends)})

    # --- aggregate
    summary = {}
    for w in WINDOWS:
        ex = per_window[w]["excess"]
        raw = per_window[w]["raw"]
        base = per_window[w]["baseline"]
        if not ex:
            continue
        mean_ex = statistics.fmean(ex)
        sd_ex = statistics.pstdev(ex) if len(ex) > 1 else 0.0
        # Naive t-stat. Overlapping windows make observations correlated, so this
        # overstates significance -- reported for scale, not as a p-value.
        t = (mean_ex / (sd_ex / (len(ex) ** 0.5))) if sd_ex > 0 else 0.0
        summary[w] = {
            "n_events": len(ex),
            "mean_raw_pct": mean_ex + statistics.fmean(base),
            "mean_raw_actual_pct": statistics.fmean(raw),
            "mean_baseline_pct": statistics.fmean(base),
            "mean_excess_pct": mean_ex,
            "median_excess_pct": statistics.median(ex),
            "sd_excess_pct": sd_ex,
            "t_stat_naive": t,
            "pct_positive_raw": per_window[w]["hits"] / len(raw) * 100,
            "pct_beat_own_baseline": sum(1 for x in ex if x > 0) / len(ex) * 100,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feed": server.FEED,
        "symbols_with_events": len(symbols_used),
        "events_used_per_window": {str(w): summary.get(w, {}).get("n_events", 0) for w in WINDOWS},
        "skipped": skipped,
        "windows": {str(k): v for k, v in summary.items()},
    }


def main() -> None:
    res = study()
    OUT_FILE.write_text(json.dumps(res, indent=1))

    print()
    print("=" * 78)
    print("PRE-EARNINGS DRIFT STUDY")
    print("=" * 78)
    print(f"feed={res['feed']}  symbols={res['symbols_with_events']}  skipped={res['skipped']}")
    print()
    hdr = (f"{'win':>4} {'events':>7} {'raw ret':>9} {'baseline':>9} {'EXCESS':>8} "
           f"{'median':>8} {'>0 raw':>7} {'>base':>7} {'t':>7}")
    print(hdr)
    print("-" * len(hdr))
    for w in WINDOWS:
        s = res["windows"].get(str(w))
        if not s:
            continue
        print(f"{w:>4} {s['n_events']:>7} {s['mean_raw_actual_pct']:>8.2f}% "
              f"{s['mean_baseline_pct']:>8.2f}% {s['mean_excess_pct']:>7.2f}% "
              f"{s['median_excess_pct']:>7.2f}% {s['pct_positive_raw']:>6.1f}% "
              f"{s['pct_beat_own_baseline']:>6.1f}% {s['t_stat_naive']:>7.1f}")
    print()
    print("raw ret  = mean return over the N sessions ending just before the release")
    print("baseline = same symbol's mean N-session return over non-pre-earnings windows")
    print("EXCESS   = raw - baseline; this is the only column that isolates the effect")
    print(">base    = share of events beating that symbol's own baseline")
    print("t        = naive t-stat on excess; overlapping windows inflate it")
    print(f"\nwrote {OUT_FILE}")


if __name__ == "__main__":
    main()
