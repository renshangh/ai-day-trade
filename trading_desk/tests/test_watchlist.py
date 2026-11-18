"""Saved scanner rankings for the Trading Desk."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import watchlist  # noqa: E402


def save_scan(path, timestamp, candidates, picks, **metadata):
    path.write_text(json.dumps({
        "generated_at": timestamp,
        "candidates": candidates,
        "llm_result": {"top": [{"symbol": symbol, "reason": "Saved rationale"} for symbol in picks]},
        **metadata,
    }))


def test_compare_saved_local_and_legacy_scans(tmp_path):
    local = {"model": "qwen3.5:35b", "route": "local"}
    amd = {"symbol": "AMD", "score": 52, "above_vwap": True}
    msft = {"symbol": "MSFT", "score": 34, "above_vwap": True}
    previous = tmp_path / "day_trade_candidates_dev_20261118_110000.json"
    save_scan(previous, "2026-11-18T11:00:00-05:00", [msft, {**amd, "score": 10, "above_vwap": False}], ["MSFT"])
    archive = tmp_path / "day_trade_candidates_history_20261118_170000_000001.json"
    latest = tmp_path / "day_trade_candidates_latest.json"
    save_scan(archive, "2026-11-18T17:00:00+00:00", [amd, msft], ["AMD"], reranker=local, feed="iex")
    latest.write_bytes(archive.read_bytes())
    save_scan(tmp_path / "day_trade_candidates_20261118_180000.json",
              "2026-11-18T18:00:00+00:00", [msft], ["MSFT"],
              reranker={"model": "gpt-5.4-mini", "route": "explicit"})
    save_scan(tmp_path / "day_trade_candidates_smoke.json",
              "2026-11-18T19:00:00+00:00", [msft], ["MSFT"], reranker=local)
    (tmp_path / "day_trade_candidates_20261118_200000.json").write_text("{")

    view = watchlist.compare_scans(tmp_path)

    assert view["latest"]["model"] == "qwen3.5:35b"
    assert view["latest"]["feed"] == "iex"
    assert view["previous"]["report"] == previous.name
    assert view["previous"]["model"] is None
    entered, dropped = view["rows"]
    assert entered["symbol"] == "AMD"
    assert entered["latest"]["rank"] == 1
    assert entered["previous"]["score_rank"] == 2
    assert entered["previous"]["above_vwap"] is False
    assert "rank" not in entered["previous"]
    assert dropped["symbol"] == "MSFT"
    assert "rank" not in dropped["latest"]
    assert dropped["previous"]["rank"] == 1


def test_watchlist_empty_without_comparable_reports(tmp_path):
    assert watchlist.compare_scans(tmp_path) == {"latest": None, "previous": None, "rows": []}
