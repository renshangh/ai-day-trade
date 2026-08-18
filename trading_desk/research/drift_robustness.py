"""Is the pre-earnings excess broad and stable, or an artifact?

A positive average across ~2000 events means little if it comes from a handful of
names in one hot stretch. Three checks:

1. **Split-half by time** -- does the older half of the sample show it too, or
   only the recent run?
2. **Winsorised mean** -- does it survive clipping the extreme 5% tails, or is it
   carried by a few enormous moves?
3. **By group** -- is it present across sectors, or concentrated in the AI theme?

Uses the 10-session window, which the main study showed has the best
mean/median agreement (least outlier-driven).
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

import server  # noqa: E402
import universe  # noqa: E402

WINDOW = 10
POST_EVENT_BUFFER = 5


def group_of(symbol: str) -> str:
    for name, cfg in universe.all_groups().items():
        if symbol in cfg["constituents"]:
            return name
    return "(unclassified)"


def winsorised_mean(xs: list[float], pct: float = 5.0) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = int(len(s) * pct / 100)
    if k > 0:
        s = s[k:-k] if len(s) > 2 * k else s
    return statistics.fmean(s)


def main() -> None:
    events_by_symbol = json.loads((HERE / "earnings_dates.json").read_text())
    server.resolve_feed()
    end = datetime.now(timezone.utc)
    bars_by_symbol = server.fetch_daily_bars(
        universe.all_symbols(), end - timedelta(days=760), end
    )

    records: list[dict] = []
    for sym, events in events_by_symbol.items():
        bars = bars_by_symbol.get(sym) or []
        if len(bars) < WINDOW + 30:
            continue
        dates = [b["t"][:10] for b in bars]
        closes = [float(b["c"]) for b in bars]
        index_of = {d: i for i, d in enumerate(dates)}
        n = len(bars)

        ends: list[tuple[int, str]] = []
        for ev in events:
            timing = ev.get("timing")
            if timing in ("intraday", "unknown"):
                continue
            d = ev["date"]
            if timing == "after_close":
                idx = index_of.get(d)
                if idx is None:
                    prior = [i for i, dd in enumerate(dates) if dd <= d]
                    idx = prior[-1] if prior else None
            else:
                prior = [i for i, dd in enumerate(dates) if dd < d]
                idx = prior[-1] if prior else None
            if idx is not None:
                ends.append((idx, d))
        if not ends:
            continue

        tainted: set[int] = set()
        for e, _ in ends:
            tainted.update(range(e - WINDOW, e + POST_EVENT_BUFFER + 1))
        baseline = [
            closes[i] / closes[i - WINDOW] - 1.0
            for i in range(WINDOW, n)
            if i not in tainted and closes[i - WINDOW] > 0
        ]
        if len(baseline) < 20:
            continue
        base_mean = statistics.fmean(baseline)

        for e, d in ends:
            if e - WINDOW < 0 or closes[e - WINDOW] <= 0:
                continue
            raw = closes[e] / closes[e - WINDOW] - 1.0
            records.append({
                "symbol": sym,
                "group": group_of(sym),
                "date": d,
                "excess_pct": (raw - base_mean) * 100,
                "raw_pct": raw * 100,
            })

    if not records:
        sys.exit("no records")

    ex = [r["excess_pct"] for r in records]
    print("=" * 74)
    print(f"ROBUSTNESS OF THE PRE-EARNINGS EXCESS  (window = {WINDOW} sessions)")
    print("=" * 74)
    print(f"events={len(records)}  mean excess={statistics.fmean(ex):+.2f}%  "
          f"median={statistics.median(ex):+.2f}%")
    print()

    # 1. split-half by date
    records.sort(key=lambda r: r["date"])
    mid = len(records) // 2
    older, newer = records[:mid], records[mid:]
    print("1. SPLIT-HALF BY TIME")
    for label, part in (("older half", older), ("newer half", newer)):
        e = [r["excess_pct"] for r in part]
        print(f"   {label} ({part[0]['date']}..{part[-1]['date']}, n={len(part)}): "
              f"mean {statistics.fmean(e):+.2f}%  median {statistics.median(e):+.2f}%  "
              f"beat-base {sum(1 for x in e if x>0)/len(e)*100:.1f}%")
    print()

    # 2. outlier sensitivity
    print("2. OUTLIER SENSITIVITY")
    print(f"   plain mean          : {statistics.fmean(ex):+.2f}%")
    print(f"   winsorised 5%       : {winsorised_mean(ex, 5):+.2f}%")
    print(f"   winsorised 10%      : {winsorised_mean(ex, 10):+.2f}%")
    print(f"   median              : {statistics.median(ex):+.2f}%")
    print()

    # 3. by group
    print("3. BY GROUP (>=25 events)")
    by_group: dict[str, list[float]] = {}
    for r in records:
        by_group.setdefault(r["group"], []).append(r["excess_pct"])
    rows = [(g, statistics.fmean(v), statistics.median(v),
             sum(1 for x in v if x > 0) / len(v) * 100, len(v))
            for g, v in by_group.items() if len(v) >= 25]
    rows.sort(key=lambda x: x[1], reverse=True)
    print(f"   {'group':32}{'mean':>8}{'median':>9}{'beat-base':>11}{'n':>6}")
    for g, m, md, hit, n in rows:
        print(f"   {g[:32]:32}{m:>7.2f}%{md:>8.2f}%{hit:>10.1f}%{n:>6}")
    positive = sum(1 for r in rows if r[1] > 0)
    print(f"\n   groups with positive mean excess: {positive}/{len(rows)}")

    (HERE / "drift_robustness.json").write_text(json.dumps({
        "window": WINDOW,
        "n_events": len(records),
        "mean_excess_pct": statistics.fmean(ex),
        "median_excess_pct": statistics.median(ex),
        "winsorised_5_pct": winsorised_mean(ex, 5),
        "split_half": {
            "older": statistics.fmean([r["excess_pct"] for r in older]),
            "newer": statistics.fmean([r["excess_pct"] for r in newer]),
        },
        "by_group": {g: {"mean": m, "median": md, "beat_base_pct": h, "n": n}
                     for g, m, md, h, n in rows},
    }, indent=1))


if __name__ == "__main__":
    main()
