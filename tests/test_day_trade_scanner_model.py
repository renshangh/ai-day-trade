import json
import sys
from pathlib import Path
from unittest.mock import Mock

import openai
import pytest

from ai_day_trade import find_day_trade_candidates as scanner


@pytest.mark.parametrize("mode", ["default", "explicit", "local_failure", "disabled"])
def test_scanner_model_routing(mode, monkeypatch, tmp_path):
    fixture = Path(scanner.__file__).parents[1] / "reports" / "day_trade_candidates_llm_smoke.json"
    saved = json.loads(fixture.read_text())
    candidates = [scanner.Candidate(**row) for row in saved["candidates"]]
    result = {"top": [], "summary": "Model response"}
    client = Mock()
    create = client.chat.completions.create
    create.return_value.choices = [Mock(message=Mock(content=json.dumps(result)))]
    if mode == "local_failure":
        create.side_effect = TimeoutError("Local model timed out")
    openai_constructor = Mock(return_value=client)
    monkeypatch.setattr(openai, "OpenAI", openai_constructor)
    monkeypatch.setattr(scanner, "rank_candidates", Mock(return_value=candidates))
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "cloud-test-key")

    report_path = tmp_path / "report.json"
    args = ["scanner", "--report", str(report_path)]
    if mode == "explicit":
        args.extend(["--model", "gpt-5.4-mini"])
    elif mode == "disabled":
        args.append("--no-llm")
    monkeypatch.setattr(sys, "argv", args)

    scanner.main()

    actual = json.loads(report_path.read_text())
    assert actual["candidates"] == saved["candidates"]
    if mode in {"default", "local_failure"}:
        openai_constructor.assert_called_once_with(
            base_url="http://127.0.0.1:11436/v1",
            api_key="ollama",
            timeout=180.0,
            max_retries=0,
        )
        assert create.call_args.kwargs["model"] == "qwen3.5:35b"
    elif mode == "explicit":
        openai_constructor.assert_called_once_with()
        assert create.call_args.kwargs["model"] == "gpt-5.4-mini"
    else:
        openai_constructor.assert_not_called()
    assert actual["llm_result"] == (result if mode in {"default", "explicit"} else None)



def test_default_scan_report_is_archived_with_provenance(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for _ in range(2):
        scanner._write_report(
            scanner.DEFAULT_REPORT, candidates=[], top=3, llm_result={"top": []}, model=None, feed="iex",
        )

    snapshots = sorted(Path("reports").glob("day_trade_candidates_history_*.json"))
    assert len(snapshots) == 2
    assert snapshots[-1].read_bytes() == scanner.DEFAULT_REPORT.read_bytes()
    latest = json.loads(scanner.DEFAULT_REPORT.read_text())
    assert latest["reranker"] == {"model": "qwen3.5:35b", "route": "local"}
    assert latest["feed"] == "iex"
