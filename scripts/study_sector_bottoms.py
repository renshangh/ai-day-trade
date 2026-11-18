#!/usr/bin/env python3
"""Descriptive sector recovery study using archived real observations, no fills."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "trading_records"
GROUPS = {
    "neocloud_context": ["CRWV", "NBIS", "IREN", "CORZ", "GLXY", "HUT", "RIOT"],
    "cloud_compute": ["CRWV", "NBIS", "IREN"],
    "infrastructure_owners": ["CORZ", "GLXY", "HUT", "RIOT"],
    # Existing desk universe retained for aggregate analysis only. Excluded
    # individual names are never promoted into personal trading coverage.
    "optical_context": ["ALAB", "ANET", "APH", "AVGO", "AXTI", "CIEN", "COHR", "CRDO", "FN", "GLW", "LITE", "MRVL", "MTSI"],
    "SOXX_analog": ["SOXX"],
    "IGV_analog": ["IGV"],
}


def keyed(rows):
    out = {}
    for row in rows:
        day = row["t"][:10]
        if day in out:
            raise ValueError(f"Duplicate observation for {day}")
        if row["c"] <= 0:
            raise ValueError(f"Invalid close for {day}")
        out[day] = row
    return out


def complete_runs(symbols, book, calendar):
    """Gaps split return windows. No missing date is converted to a one-day return."""
    runs, run = [], []
    for day in calendar:
        if all(day in book.get(symbol, {}) for symbol in symbols):
            run.append(day)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    return runs


def return_pct(a, b):
    return (b / a - 1) * 100


def path_outcome(values, dates, i, horizon):
    if i + horizon >= len(values):
        return None
    entry = values[i]
    path = values[i:i + horizon + 1]
    peak = entry
    drawdown = 0
    for value in path:
        peak = max(peak, value)
        drawdown = min(drawdown, return_pct(peak, value))
    return {
        "end_date": dates[i + horizon],
        "return_percent": return_pct(entry, path[-1]),
        "worst_close_from_signal_percent": min(return_pct(entry, v) for v in path),
        "max_closing_peak_to_trough_percent": drawdown,
    }


def events(symbols, book, calendar):
    results, skipped = [], 0
    for run in complete_runs(symbols, book, calendar):
        if len(run) < 65:
            skipped += 1
            continue
        index, daily_returns, advance = [100.0], [None], [None]
        for i in range(1, len(run)):
            changes = [book[s][run[i]]["c"] / book[s][run[i - 1]]["c"] - 1 for s in symbols]
            daily_returns.append(mean(changes))
            advance.append(sum(v > 0 for v in changes) / len(changes))
            index.append(index[-1] * (1 + mean(changes)))
        next_eligible = 63
        for i in range(63, len(run)):
            prior_peak = max(index[i - 63:i])
            prior_drawdown = return_pct(prior_peak, index[i - 1])
            if i < next_eligible or prior_drawdown > -20 or daily_returns[i] < .03 or advance[i] < .70:
                continue
            next_eligible = i + 21
            horizons = {str(h): path_outcome(index, run, i, h) for h in (5, 10, 21)}
            diagnostic = None
            if horizons["21"] is not None:
                first = next((j for j in range(i + 1, i + 22) if index[j] >= index[i] * 1.10), None)
                if first is not None:
                    later = index[first + 1:i + 22]
                    diagnostic = {
                        "first_plus10_close_date": run[first],
                        "actual_gain_at_that_close_percent": return_pct(index[i], index[first]),
                        "later5percent_pullback_before_session21": any(v <= index[first] * .95 for v in later),
                        "minimum_later_close_vs_that_close_percent": min((return_pct(index[first], v) for v in later), default=None),
                        "subsequent_sessions_observed": len(later),
                        "signal_to_session21_return_percent": return_pct(index[i], index[i + 21]),
                        "note": "Observed closing path only; no assumption of selling or buying at these prices.",
                    }
            members = {}
            for s in symbols:
                members[s] = {str(h): return_pct(book[s][run[i]]["c"], book[s][run[i + h]]["c"])
                              if i + h < len(run) else None for h in (5, 10, 21)}
            results.append({"date": run[i], "prior63_closing_drawdown_percent": prior_drawdown,
                            "signal_daily_return_percent": daily_returns[i] * 100,
                            "advancing_percent": advance[i] * 100, "horizons": horizons,
                            "closing_path_diagnostic": diagnostic, "member_forward_returns_percent": members})
    summary = {}
    for h in (5, 10, 21):
        known = [e["horizons"][str(h)] for e in results if e["horizons"][str(h)] is not None]
        returns = [x["return_percent"] for x in known]
        summary[str(h)] = {"completed_events": len(known), "positive_events": sum(x > 0 for x in returns),
                           "median_return_percent": median(returns) if returns else None,
                           "min_return_percent": min(returns) if returns else None,
                           "max_return_percent": max(returns) if returns else None,
                           "worst_closing_loss_from_signal_percent": min((x["worst_close_from_signal_percent"] for x in known), default=None)}
    return {"events": results, "summary": summary, "short_coverage_runs_skipped": skipped}


def symbol_metrics(symbol, book, calendar, date):
    if date not in book.get(symbol, {}):
        return {"symbol": symbol, "date": date, "unavailable": True}
    i = calendar.index(date)
    current = book[symbol][date]
    def window(n):
        dates = calendar[max(0, i - n + 1):i + 1]
        return [book[symbol][d] for d in dates] if len(dates) == n and all(d in book[symbol] for d in dates) else None
    result = {"symbol": symbol, "date": date, "close": current["c"]}
    for n in (20, 50, 200):
        data = window(n)
        result[f"sma{n}"] = mean(r["c"] for r in data) if data else None
    for n in (5, 21):
        data = window(n + 1)
        result[f"return{n}_percent"] = return_pct(data[0]["c"], current["c"]) if data else None
    data = window(21)
    result["volume_vs_prior20"] = current["v"] / mean(r["v"] for r in data[:-1]) if data and mean(r["v"] for r in data[:-1]) > 0 else None
    recent = window(63)
    result["close_drawdown63_percent"] = return_pct(max(r["c"] for r in recent), current["c"]) if recent else None
    lows = window(21)
    result["new20session_intraday_low"] = current["l"] < min(r["l"] for r in lows[:-1]) if lows else None
    return result


def main():
    raw = json.loads((RECORDS / "2026-11-11_SECTOR_BOTTOM_DAILY_RAW.json").read_text())
    cutoff = raw["last_completed_session"]
    book = {s: keyed([r for r in rows if r["t"][:10] <= cutoff]) for s, rows in raw["bars"].items()}
    if not raw.get("calendar"):
        raise ValueError("Authoritative session calendar missing; do not infer sessions from returned bars")
    calendar = sorted(day["date"] for day in raw["calendar"] if day["date"] <= cutoff)
    latest = calendar[-1]
    metrics = {s: symbol_metrics(s, book, calendar, latest) for s in book}
    groups = {}
    for name, symbols in GROUPS.items():
        runs = complete_runs(symbols, book, calendar)
        valid = [run for run in runs if len(run) >= 65]
        rows = [metrics[s] for s in symbols]
        breadth = {}
        for n in (20, 50, 200):
            eligible = [r for r in rows if r[f"sma{n}"] is not None]
            breadth[str(n)] = {"above": sum(r["close"] > r[f"sma{n}"] for r in eligible), "eligible": len(eligible),
                               "percent": sum(r["close"] > r[f"sma{n}"] for r in eligible) / len(eligible) * 100 if eligible else None}
        relative = {}
        for n in (5,21):
            values = [r[f"return{n}_percent"] for r in rows]
            avg = mean(values) if all(v is not None for v in values) else None
            relative[str(n)] = {"equal_start_weight_member_mean_return_percent": avg,
                               "excess_QQQ_pp": avg - metrics["QQQ"][f"return{n}_percent"] if avg is not None else None,
                               "excess_SPY_pp": avg - metrics["SPY"][f"return{n}_percent"] if avg is not None else None}
        groups[name] = {"symbols": symbols, "current_breadth": breadth, "current_relative_strength": relative,
                        "coverage_runs": [{"start":run[0],"end":run[-1],"sessions":len(run)} for run in valid],
                        **events(symbols, book, calendar)}
    output = {"as_of_completed_session": latest, "source": raw["source"], "metrics": metrics,
              "groups": groups, "protocol": "2026-11-11_SECTOR_BOTTOM_PROTOCOL.json",
              "notices": ["Descriptive research, not an executable backtest, predictive success rate or investment product.",
                          "Group index is a calculated return measure, not fabricated observed OHLCV or a tradable security.",
                          "Current-selected cohort, short common history and small samples; analog sectors differ.",
                          "No forward fills, future bars, assumed fills, costs or tax outcomes."]}
    target = RECORDS / "2026-11-11_SECTOR_BOTTOM_STUDY.json"
    target.write_text(json.dumps(output, indent=2) + "\n")
    with (RECORDS / "2026-11-11_SECTOR_BOTTOM_EVENTS.csv").open("w") as handle:
        fields = ["group", "date", "prior63_closing_drawdown_percent", "signal_daily_return_percent", "advancing_percent", "forward5", "forward10", "forward21", "worst_close21", "max_closing_drawdown21", "first_plus10_close_date", "subsequent_pullback5"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for name, group in groups.items():
            for event in group["events"]:
                row = {k:event[k] for k in fields if k in event}; row["group"] = name
                for n in (5,10,21): row[f"forward{n}"] = event["horizons"][str(n)]["return_percent"] if event["horizons"][str(n)] else None
                h = event["horizons"]["21"]
                row["worst_close21"] = h["worst_close_from_signal_percent"] if h else None
                row["max_closing_drawdown21"] = h["max_closing_peak_to_trough_percent"] if h else None
                diagnostic = event["closing_path_diagnostic"]
                row["first_plus10_close_date"] = diagnostic["first_plus10_close_date"] if diagnostic else None
                row["subsequent_pullback5"] = diagnostic["later5percent_pullback_before_session21"] if diagnostic else None
                writer.writerow(row)
    print("Saved", target)
    for name,g in groups.items():
        print(name,"coverage",g["coverage_runs"],"breadth",g["current_breadth"],"relative",g["current_relative_strength"])
        print("summary",g["summary"])
        for event in g["events"]:
            print("event",event["date"],"day",round(event["signal_daily_return_percent"],2),
                  "fwd",{n:round(v["return_percent"],2) if v else None for n,v in event["horizons"].items()},
                  "path",event["closing_path_diagnostic"])


if __name__ == "__main__":
    main()
