import os
import time
from datetime import datetime, timezone

import pytest
import requests

import lumibot.fundamentals.sec as sec_module
from lumibot.fundamentals import SECFundamentals


class _Response:
    def __init__(self, *, payload=None, text=""):
        self._payload = payload
        self.text = text
        self.content = text.encode()

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_sec_fundamentals_are_point_in_time_gated_and_cached(monkeypatch, tmp_path):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if url.endswith("company_tickers.json"):
            return _Response(payload={"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}})
        if "companyfacts" in url:
            return _Response(
                payload={
                    "facts": {
                        "us-gaap": {
                            "Revenues": {
                                "units": {
                                    "USD": [
                                        {"val": 100, "filed": "2024-01-01", "form": "10-K", "fy": 2023, "fp": "FY", "accn": "old"},
                                        {"val": 200, "filed": "2026-01-01", "form": "10-K", "fy": 2025, "fp": "FY", "accn": "future"},
                                    ]
                                }
                            },
                            "NetIncomeLoss": {
                                "units": {
                                    "USD": [
                                        {"val": 10, "filed": "2024-01-01", "form": "10-K", "fy": 2023, "fp": "FY", "accn": "old"}
                                    ]
                                }
                            },
                        }
                    }
                }
            )
        raise AssertionError(url)

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", fake_get)
    sec = SECFundamentals(cache_dir=tmp_path, min_request_interval_seconds=0)

    result = sec.get_income_statement("AAPL", as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert result["values"]["revenue"]["value"] == 100
    assert result["values"]["net_income"]["value"] == 10

    result_again = sec.get_income_statement("AAPL", as_of=datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert result_again["values"]["revenue"]["value"] == 100
    assert len(calls) == 2


def test_sec_filings_and_keyword_search(monkeypatch, tmp_path):
    def fake_get(url, **kwargs):
        if url.endswith("company_tickers.json"):
            return _Response(payload={"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}})
        if "submissions" in url:
            return _Response(
                payload={
                    "cik": "0000320193",
                    "filings": {
                        "recent": {
                            "form": ["10-K", "10-Q"],
                            "accessionNumber": ["0000320193-24-000001", "0000320193-26-000001"],
                            "filingDate": ["2024-11-01", "2026-01-01"],
                            "reportDate": ["2024-09-30", "2025-12-31"],
                            "acceptanceDateTime": ["2024-11-01T12:00:00.000Z", "2026-01-01T12:00:00.000Z"],
                            "primaryDocument": ["aapl-20240930.htm", "aapl-20251231.htm"],
                            "primaryDocDescription": ["10-K", "10-Q"],
                        }
                    },
                }
            )
        if "Archives/edgar/data" in url:
            return _Response(text="<html><body>Revenue recognition changed. Customer concentration risk is low.</body></html>")
        raise AssertionError(url)

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", fake_get)
    sec = SECFundamentals(cache_dir=tmp_path, min_request_interval_seconds=0)

    filings = sec.get_filings("AAPL", as_of="2025-01-01T00:00:00+00:00", limit=10)
    assert len(filings["filings"]) == 1
    assert filings["filings"][0]["form"] == "10-K"

    matches = sec.search_filing(
        "AAPL",
        accession_number="0000320193-24-000001",
        primary_document="aapl-20240930.htm",
        query="customer concentration",
    )
    assert matches["match_count"] >= 1
    assert "Customer concentration" in matches["matches"][0]["context"]


def test_company_facts_are_compact_by_default(monkeypatch, tmp_path):
    def fake_get(url, **kwargs):
        if url.endswith("company_tickers.json"):
            return _Response(payload={"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}})
        if "companyfacts" in url:
            facts = {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [{"val": 100, "filed": "2024-01-01", "form": "10-K"}]}
                }
            }
            for index in range(10):
                facts[f"CustomFact{index}"] = {
                    "units": {"USD": [{"val": index, "filed": "2024-01-01", "form": "10-K"}]}
                }
            return _Response(payload={"facts": {"us-gaap": facts}})
        raise AssertionError(url)

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", fake_get)
    sec = SECFundamentals(cache_dir=tmp_path, min_request_interval_seconds=0)

    compact = sec.get_company_facts("AAPL", as_of="2025-01-01", max_facts=3)
    assert compact["fact_count"] == 3
    assert compact["truncated"] is True
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in compact["facts"]

    full = sec.get_company_facts("AAPL", as_of="2025-01-01", max_facts=None)
    assert full["fact_count"] == 11
    assert full["truncated"] is False


# --- Cache expiry ------------------------------------------------------------
#
# Regression coverage for a shipped defect: `_get_json` cached SEC responses
# permanently, including the `submissions` index that grows with every filing.
# Re-running the earnings collector silently returned its own stale input and
# reported success, hiding a real earnings print. See
# docs/investigations/2026-08-28_SEC_SUBMISSIONS_CACHE_NEVER_EXPIRES.md.


def _tickers_response():
    return _Response(payload={"0": {"ticker": "AAPL", "cik_str": 320193, "title": "Apple Inc."}})


def _submissions_payload(*, form, filing_date, accession, document):
    return {
        "cik": "0000320193",
        "filings": {
            "recent": {
                "form": [form],
                "accessionNumber": [accession],
                "filingDate": [filing_date],
                "reportDate": [filing_date],
                "acceptanceDateTime": [f"{filing_date}T12:00:00.000Z"],
                "primaryDocument": [document],
                "primaryDocDescription": [form],
            }
        },
    }


def _backdate(path, seconds):
    """Age a cached file by `seconds` so TTL logic sees it as stale."""
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def _submissions_cache_path(tmp_path):
    return tmp_path / "submissions" / "CIK0000320193.json"


def _sec_with_versioned_submissions(monkeypatch, tmp_path, state):
    """Client whose submissions endpoint returns state['version'] on each call."""

    def fake_get(url, **kwargs):
        if url.endswith("company_tickers.json"):
            return _Response(payload=_tickers_response().json())
        if "submissions" in url:
            state["submission_calls"] += 1
            if state["version"] == 1:
                return _Response(payload=_submissions_payload(
                    form="10-Q", filing_date="2026-05-04",
                    accession="0000320193-26-000001", document="a-20260504.htm"))
            return _Response(payload=_submissions_payload(
                form="8-K", filing_date="2026-08-17",
                accession="0000320193-26-000002", document="a-20260817.htm"))
        raise AssertionError(url)

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", fake_get)
    return SECFundamentals(cache_dir=tmp_path, min_request_interval_seconds=0)


def test_submissions_cache_is_served_from_disk_within_ttl(monkeypatch, tmp_path):
    state = {"version": 1, "submission_calls": 0}
    sec = _sec_with_versioned_submissions(monkeypatch, tmp_path, state)

    sec.get_submissions("AAPL")
    sec.get_submissions("AAPL")

    # Second call is inside the TTL, so no second network hit.
    assert state["submission_calls"] == 1


def test_submissions_cache_expires_and_sees_new_filings(monkeypatch, tmp_path):
    state = {"version": 1, "submission_calls": 0}
    sec = _sec_with_versioned_submissions(monkeypatch, tmp_path, state)

    first = sec.get_submissions("AAPL")
    assert first["filings"]["recent"]["filingDate"] == ["2026-05-04"]

    # Company files an 8-K, and the cached copy ages past its TTL.
    state["version"] = 2
    _backdate(_submissions_cache_path(tmp_path), sec_module.SUBMISSIONS_CACHE_MAX_AGE_SECONDS + 60)

    second = sec.get_submissions("AAPL")

    assert state["submission_calls"] == 2
    # This is the assertion that would have caught the original bug.
    assert second["filings"]["recent"]["form"] == ["8-K"]
    assert second["filings"]["recent"]["filingDate"] == ["2026-08-17"]


def test_expired_submissions_cache_falls_back_when_sec_unreachable(monkeypatch, tmp_path):
    state = {"version": 1, "submission_calls": 0}
    sec = _sec_with_versioned_submissions(monkeypatch, tmp_path, state)
    sec.get_submissions("AAPL")

    cache_path = _submissions_cache_path(tmp_path)
    assert cache_path.exists()
    _backdate(cache_path, sec_module.SUBMISSIONS_CACHE_MAX_AGE_SECONDS + 60)

    def failing_get(url, **kwargs):
        raise requests.ConnectionError("SEC unreachable")

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", failing_get)

    # Stale beats nothing: an outage must not break a run that worked offline.
    result = sec.get_submissions("AAPL")
    assert result["filings"]["recent"]["filingDate"] == ["2026-05-04"]


def test_missing_cache_still_raises_when_sec_unreachable(monkeypatch, tmp_path):
    def failing_get(url, **kwargs):
        raise requests.ConnectionError("SEC unreachable")

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", failing_get)
    sec = SECFundamentals(cache_dir=tmp_path, min_request_interval_seconds=0)

    # No cached copy to fall back to, so the failure must surface.
    with pytest.raises(requests.ConnectionError):
        sec.get_submissions("AAPL")


def test_corrupt_json_cache_is_discarded_and_refetched(monkeypatch, tmp_path):
    state = {"version": 1, "submission_calls": 0}
    sec = _sec_with_versioned_submissions(monkeypatch, tmp_path, state)
    sec.get_submissions("AAPL")

    # Simulate an interrupted write leaving a truncated file.
    cache_path = _submissions_cache_path(tmp_path)
    cache_path.write_text('{"filings": {"recent": ', encoding="utf-8")

    result = sec.get_submissions("AAPL")

    assert state["submission_calls"] == 2
    assert result["filings"]["recent"]["filingDate"] == ["2026-05-04"]


def test_filing_documents_are_cached_permanently(monkeypatch, tmp_path):
    """A filed document is immutable, so age must never trigger a re-fetch."""
    archive_calls = []

    def fake_get(url, **kwargs):
        if url.endswith("company_tickers.json"):
            return _Response(payload=_tickers_response().json())
        if "submissions" in url:
            return _Response(payload=_submissions_payload(
                form="10-K", filing_date="2024-11-01",
                accession="0000320193-24-000001", document="aapl-20240930.htm"))
        if "Archives/edgar/data" in url:
            archive_calls.append(url)
            return _Response(text="<html><body>Customer concentration risk is low.</body></html>")
        raise AssertionError(url)

    monkeypatch.setattr("lumibot.fundamentals.sec.requests.get", fake_get)
    sec = SECFundamentals(cache_dir=tmp_path, min_request_interval_seconds=0)

    kwargs = dict(accession_number="0000320193-24-000001",
                  primary_document="aapl-20240930.htm", query="customer concentration")
    assert sec.search_filing("AAPL", **kwargs)["match_count"] >= 1

    # Age the document cache far beyond any index TTL.
    doc_cache = next(p for p in (tmp_path / "filings").rglob("*") if p.is_file())
    _backdate(doc_cache, 365 * 24 * 60 * 60)

    assert sec.search_filing("AAPL", **kwargs)["match_count"] >= 1
    assert len(archive_calls) == 1
