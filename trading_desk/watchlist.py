"""The Trading Desk view of saved intraday scanner reports."""

import json
import math
import re
from datetime import datetime
from pathlib import Path

REPORT_NAME = re.compile(r"day_trade_candidates_(?:latest|(?:[a-z0-9-]+_)?\d{8}_\d{6}(?:_\d{6})?)\.json")
METRICS = (
    "score", "above_vwap", "relative_strength_pct", "return_from_open_pct",
    "near_high_of_day_pct", "volume_vs_avg_daily_pct",
)


def _read_scan(path: Path) -> tuple[datetime, dict] | None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        timestamp = datetime.fromisoformat(report["generated_at"])
        if timestamp.utcoffset() is None:
            return None

        reranker = report.get("reranker")
        legacy = "reranker" not in report
        if not legacy and (
            not isinstance(reranker, dict)
            or reranker.get("route") != "local"
            or not str(reranker.get("model", "")).startswith("qwen")
        ):
            return None

        candidates = {}
        for index, row in enumerate(report["candidates"], start=1):
            metrics = {"score_rank": index}
            for key in METRICS:
                value = row.get(key)
                if key == "above_vwap":
                    metrics[key] = value if isinstance(value, bool) else None
                else:
                    metrics[key] = value if type(value) in {float, int} and math.isfinite(value) else None
            candidates[row["symbol"]] = metrics

        ranked = {}
        for index, row in enumerate(report["llm_result"]["top"], start=1):
            symbol = row["symbol"]
            if symbol in ranked or symbol not in candidates:
                return None
            ranked[symbol] = {
                "rank": index,
                "reason": str(row.get("reason") or ""),
            }
        if not ranked:
            return None
        return timestamp, {
            "generated_at": timestamp.isoformat(),
            "report": path.name,
            "model": None if legacy else reranker["model"],
            "feed": report.get("feed"),
            "top": len(ranked),
            "ranked": ranked,
            "candidates": candidates,
        }
    except (AttributeError, KeyError, OSError, OverflowError, TypeError, ValueError):
        return None


def compare_scans(directory: Path) -> dict:
    """Select the latest saved local rankings and the last comparable scan."""
    scans = {}
    for path in sorted(directory.glob("day_trade_candidates_*.json")):
        if not REPORT_NAME.fullmatch(path.name) or path.is_symlink():
            continue
        read = _read_scan(path)
        if read is not None:
            timestamp, scan = read
            scans.setdefault(timestamp, scan)
    ordered = [scans[timestamp] for timestamp in sorted(scans, reverse=True)]
    if not ordered:
        return {"latest": None, "previous": None, "rows": []}

    latest, *history = ordered
    previous = history[0] if history else None
    symbols = list(latest["ranked"])
    if previous:
        symbols.extend(symbol for symbol in previous["ranked"] if symbol not in latest["ranked"])

    def projection(scan: dict | None, symbol: str) -> dict | None:
        if not scan or symbol not in scan["candidates"]:
            return None
        return {**scan["candidates"][symbol], **scan["ranked"].get(symbol, {})}

    return {
        "latest": {key: latest[key] for key in ("generated_at", "report", "model", "feed", "top")},
        "previous": (
            {key: previous[key] for key in ("generated_at", "report", "model", "feed", "top")}
            if previous else None
        ),
        "rows": [
            {"symbol": symbol, "latest": projection(latest, symbol), "previous": projection(previous, symbol)}
            for symbol in symbols
        ],
    }
