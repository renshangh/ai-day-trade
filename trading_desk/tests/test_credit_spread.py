from datetime import date

import pytest

from trading_desk.credit_spread import summarize


def test_published_close_and_calendar_week():
    csv_text = """observation_date,BAMLH0A0HYM2
2026-11-11,3.30
2026-11-12,3.20
2026-11-18,3.47
2026-11-19,.
"""
    result = summarize(csv_text, date(2026, 11, 19))
    assert result == {
        "date": "2026-11-18",
        "spread_pct": 3.47,
        "weekly_base_date": "2026-11-11",
        "weekly_change_bp": 17,
        "alert": "none",
        "stale": False,
    }


def test_watch_boundary_and_strict_high_alert():
    rows = "observation_date,BAMLH0A0HYM2\n2026-11-11,4.00\n2026-11-18,"
    today = date(2026, 11, 19)
    assert summarize(rows + "4.49", today)["alert"] == "none"
    assert summarize(rows + "4.50", today)["alert"] == "rapid_widening"
    assert summarize(rows + "6.00", today)["alert"] == "rapid_widening"
    assert summarize(rows + "6.01", today)["alert"] == "above_six"


def test_missing_baseline_and_stale_source():
    rows = "observation_date,BAMLH0A0HYM2\n2026-11-06,4.00\n2026-11-18,5.00"
    result = summarize(rows, date(2026, 11, 23))
    assert result["weekly_change_bp"] is None
    assert result["alert"] == "unavailable"
    assert result["stale"] is True


def test_weekly_comparison_can_use_prior_published_close():
    rows = "observation_date,BAMLH0A0HYM2\n2026-11-09,4.00\n2026-11-18,4.60"
    result = summarize(rows, date(2026, 11, 19))
    assert result["weekly_base_date"] == "2026-11-09"
    assert result["weekly_change_bp"] == 60


@pytest.mark.parametrize("bad_row", ["2026-11-18,NaN", "2026-11-18", "2026-11-18,6.01,extra"])
def test_malformed_latest_row_does_not_silently_reuse_older_value(bad_row):
    rows = "observation_date,BAMLH0A0HYM2\n2026-11-17,3.43\n" + bad_row
    with pytest.raises(ValueError):
        summarize(rows, date(2026, 11, 19))
