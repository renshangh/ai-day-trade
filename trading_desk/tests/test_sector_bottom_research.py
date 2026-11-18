"""Recovery-study integrity using real dated HUT closes and archived SIP bars."""
from pathlib import Path
import json
import pytest
from scripts import study_sector_bottoms as study

# Actual completed HUT sessions from the November11 SIP archive. Only close is
# needed for these arithmetic tests; no invented OHLCV fields or placeholder bars.
OBSERVED = [
    {"t":"2026-11-05T05:00:00Z","c":45.95},
    {"t":"2026-11-06T05:00:00Z","c":52.65},
    {"t":"2026-11-09T05:00:00Z","c":57.02},
    {"t":"2026-11-10T05:00:00Z","c":56.77},
]


def test_missing_session_splits_windows_instead_of_joining_returns():
    rows = study.keyed(OBSERVED)
    calendar = sorted(rows)
    del rows['2026-11-06']
    assert study.complete_runs(['HUT'],{'HUT':rows},calendar) == [
        ['2026-11-05'],['2026-11-09','2026-11-10']]


def test_forward_horizon_needs_all_sessions_and_uses_real_closes():
    dates = [r['t'][:10] for r in OBSERVED]
    values = [r['c'] for r in OBSERVED]
    assert study.path_outcome(values,dates,0,4) is None
    result = study.path_outcome(values,dates,0,3)
    assert result['return_percent'] == pytest.approx((56.77/45.95-1)*100)
    assert result['max_closing_peak_to_trough_percent'] == pytest.approx((56.77/57.02-1)*100)
    assert result['worst_close_from_signal_percent'] == 0


def test_duplicate_observation_fails_instead_of_silently_overwriting():
    with pytest.raises(ValueError,match='Duplicate'):
        study.keyed(OBSERVED + [OBSERVED[-1]])


def test_main_requires_a_session_calendar_not_an_observed_bar_calendar(monkeypatch,tmp_path):
    # Actual November5 QQQ close; missing calendar must fail before analysis.
    raw={'last_completed_session':'2026-11-10','source':'Actual archived SIP close',
         'bars':{'QQQ':[{'t':'2026-11-05T05:00:00Z','c':647.05}]}}
    (tmp_path/'2026-11-11_SECTOR_BOTTOM_DAILY_RAW.json').write_text(json.dumps(raw))
    monkeypatch.setattr(study,'RECORDS',tmp_path)
    with pytest.raises(ValueError,match='session calendar missing'):
        study.main()


def test_signal_prefix_invariance_and_incomplete_forward_outcomes():
    path = study.RECORDS/'2026-11-11_SECTOR_BOTTOM_DAILY_RAW.json'
    if not path.exists():
        pytest.skip('Private real SIP study archive is not shipped with the repository')
    raw = json.loads(path.read_text())['bars']
    symbols = study.GROUPS['neocloud_context']
    book = {s:study.keyed(raw[s]) for s in symbols}
    calendar = sorted(study.keyed(raw['QQQ']))
    full = study.events(symbols,book,calendar)['events']
    cutoff = '2026-09-30'
    earlier = study.events(symbols,book,[d for d in calendar if d<=cutoff])['events']
    assert [x['date'] for x in earlier] == [x['date'] for x in full if x['date']<=cutoff]
    for event in earlier:
        original = next(x for x in full if x['date']==event['date'])
        assert event['signal_daily_return_percent'] == original['signal_daily_return_percent']
        for horizon,result in event['horizons'].items():
            if result is not None: assert result == original['horizons'][horizon]
    latest = full[-1]
    assert latest['date']=='2026-10-27'
    assert latest['horizons']['21'] is None
