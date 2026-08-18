"""Collect historical earnings-announcement dates for the trading-desk universe.

The announcement date is taken from **8-K filings carrying SEC item 2.02**
("Results of Operations and Financial Condition"). That is the earnings release
itself, which is what a pre-earnings study needs -- the 10-Q *filing* date is
typically days later and would mis-date every event.

`acceptanceDateTime` tells us whether a release landed before the open or after
the close, which decides where the run-up window has to stop. Getting this wrong
leaks the earnings reaction into the "pre-earnings" measurement.

Output: JSON mapping symbol -> list of {date, accepted_utc, timing}.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# trading_desk/ for `universe`, repo root for `lumibot` -- so this runs from any cwd.
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))

import universe  # noqa: E402

from lumibot.fundamentals.sec import SECFundamentals  # noqa: E402

OUT = HERE / "earnings_dates.json"

# US market hours in UTC. EDT is UTC-4, so 09:30 ET = 13:30 UTC and
# 16:00 ET = 20:00 UTC. A release accepted at/after the close is "after_close";
# one accepted before the open is "before_open"; anything in between happened
# during the session and is flagged so it can be excluded rather than guessed at.
OPEN_UTC_H, OPEN_UTC_M = 13, 30
CLOSE_UTC_H = 20


def classify(accepted: str) -> str:
    """after_close | before_open | intraday | unknown, from an ISO UTC stamp."""
    if not accepted or "T" not in accepted:
        return "unknown"
    try:
        hhmm = accepted.split("T", 1)[1][:5]
        h, m = int(hhmm[:2]), int(hhmm[3:5])
    except (ValueError, IndexError):
        return "unknown"
    if h >= CLOSE_UTC_H:
        return "after_close"
    if (h, m) < (OPEN_UTC_H, OPEN_UTC_M):
        return "before_open"
    return "intraday"


def collect(symbols: list[str]) -> dict[str, list[dict]]:
    sec = SECFundamentals()
    out: dict[str, list[dict]] = {}
    failures: list[str] = []
    for i, sym in enumerate(symbols, 1):
        try:
            recent = sec.get_submissions(sym).get("filings", {}).get("recent", {})
            forms = recent.get("form", []) or []
            dates = recent.get("filingDate", []) or []
            items = recent.get("items", []) or [""] * len(forms)
            accepted = recent.get("acceptanceDateTime", []) or [""] * len(forms)
            events = [
                {"date": d, "accepted_utc": a, "timing": classify(a)}
                for f, d, it, a in zip(forms, dates, items, accepted)
                if f == "8-K" and "2.02" in str(it)
            ]
            # Newest first, matching how SEC returns them.
            events.sort(key=lambda e: e["date"], reverse=True)
            if events:
                out[sym] = events
        except Exception as e:  # noqa: BLE001 - a missing filer must not abort the run
            failures.append(f"{sym}: {type(e).__name__}")
        if i % 25 == 0:
            print(f"  ... {i}/{len(symbols)} symbols, {len(out)} with earnings 8-Ks",
                  file=sys.stderr, flush=True)
        time.sleep(0.12)  # stay well inside SEC's request budget

    if failures:
        print(f"  [warn] {len(failures)} symbols failed: {', '.join(failures[:12])}",
              file=sys.stderr)
    return out


def main() -> None:
    symbols = universe.all_symbols()
    print(f"collecting earnings 8-Ks for {len(symbols)} symbols", file=sys.stderr)
    data = collect(symbols)
    OUT.write_text(json.dumps(data, indent=1))

    counts = [len(v) for v in data.values()]
    timings: dict[str, int] = {}
    for evs in data.values():
        for e in evs:
            timings[e["timing"]] = timings.get(e["timing"], 0) + 1
    print(f"\nwrote {OUT}")
    print(f"  symbols with events : {len(data)}/{len(symbols)}")
    print(f"  total events        : {sum(counts)}")
    if counts:
        print(f"  events per symbol   : min {min(counts)}, median "
              f"{sorted(counts)[len(counts)//2]}, max {max(counts)}")
    print(f"  release timing      : {timings}")


if __name__ == "__main__":
    main()
