"""Calendar integrity: real source times, DST, partial failures and daily renewal."""
from datetime import datetime, timezone

from trading_desk import economic_calendar as c


def test_ics_unfolding_timezone_and_unknown_time():
    text = '''BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Gross Domestic Product\\, advance
 estimate
DTSTART:20261125T133000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Consumer Price Index
DTSTART;TZID=America/New_York:20260714T083000
END:VEVENT
BEGIN:VEVENT
SUMMARY:Employment Situation
DTSTART;VALUE=DATE:20261204
END:VEVENT
END:VCALENDAR'''
    rows = c.parse_ics(text, 'Test', 'https://example.com')
    assert rows[0]['at'] == '2026-11-25T08:30:00-05:00'
    assert rows[0]['title'] == 'Gross Domestic Product, advanceestimate'
    assert rows[1]['at'] == '2026-07-14T08:30:00-04:00'
    assert rows[2]['at'] is None
    assert rows[2]['date'] == '2026-12-04'


def test_partial_failures_do_not_claim_freshness_and_day_rolls(monkeypatch, tmp_path):
    c.CACHE.clear()
    monkeypatch.setattr(c, "LAST_GOOD", tmp_path / "last.json")
    monkeypatch.setattr(c, "bls_from_fred", lambda today: (_ for _ in ()).throw(OSError("blocked")))
    calls = []
    def fail(url):
        calls.append(url)
        raise OSError('blocked')
    monkeypatch.setattr(c, 'fetch', fail)
    try:
        first = dict(c.snapshot(now=datetime(2026, 11, 10, 12, tzinfo=timezone.utc)))
        assert first['partial']
        assert any(e['title'].startswith('Consumer Price') for e in first['events'])
        assert all(s['status'] != 'refreshed' for s in first['sources'])
        c.snapshot(now=datetime(2026, 11, 10, 12, 5, tzinfo=timezone.utc))
        assert len(calls) == 3
        second = c.snapshot(now=datetime(2026, 11, 11, 6, tzinfo=timezone.utc))
        assert len(calls) == 6
        assert all(e.get('stale') for e in second['events'])
        assert not any(e['date'] == '2026-11-10' for e in second['events'])
    finally:
        c.CACHE.clear()


def test_fred_converts_central_and_preserves_missing_times():
    text = '<p>All times are US Central Time</p><table><tr><td>Tuesday November 10, 2026</td></tr><tr><td>7:30 am</td><td><a href="/release?rid=10">Consumer Price Index</a></td></tr></table>'
    event = c.parse_fred_day(text, '10', '2026-11-10')
    assert event['at'] == '2026-11-10T08:30:00-05:00'
    assert event['retrieved_via'] == 'St. Louis Fed FRED'
    assert c.parse_fred_day(text.replace('7:30 am', ''), '10', '2026-11-10')['at'] is None


def test_fed_fomc_published_time_and_no_guessed_time():
    import json
    rows = c.parse_fed(json.dumps({'events': [
        {'title': 'FOMC Meeting', 'month': '2026-12', 'days': '9', 'time': '2:00 p.m.'},
        {'title': 'FOMC Minutes', 'month': '2027-03', 'days': '31', 'time': '2:00 p.m.'},
        {'title': 'Beige Book', 'month': '2026-11', 'days': '25'},
        {'title': 'Unrelated release', 'month': '2026-11', 'days': '1'},
        {'title': 'FOMC Meeting', 'month': '', 'days': '9', 'time': '2:00 p.m.'},
    ]}), c.FEEDS['Federal Reserve'])
    assert len(rows) == 3
    assert rows[0]['at'] == '2026-12-09T14:00:00-05:00'
    assert rows[1]['at'] == '2027-03-31T14:00:00-04:00'
    assert rows[2]['at'] is None


def test_successful_fallback_and_fed_daily_refresh(monkeypatch, tmp_path):
    import json
    c.CACHE.clear()
    monkeypatch.setattr(c, 'LAST_GOOD', tmp_path / 'last.json')
    calls = []
    def fetch(url):
        calls.append(url)
        if url == c.FEEDS['BLS']:
            raise OSError('direct BLS blocked')
        if url == c.FEEDS['Federal Reserve']:
            return json.dumps({'events':[{'title':'FOMC Meeting','month':'2026-12','days':'9','time':'2:00 p.m.'}]})
        return 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Gross Domestic Product\nDTSTART:20261125T133000Z\nEND:VEVENT\nEND:VCALENDAR'
    monkeypatch.setattr(c, 'fetch', fetch)
    monkeypatch.setattr(c, 'bls_from_fred', lambda today: [{'title':'Employment Situation','date':'2026-12-04','at':'2026-12-04T08:30:00-05:00','agency':'BLS','source':c.FRED}])
    try:
        result = c.snapshot(now=datetime(2026,11,10,12,tzinfo=timezone.utc))
        assert not result['partial']
        assert 'FRED' in result['sources'][0]['via']
        assert any(e['title'] == 'FOMC Meeting' for e in result['events'])
        c.snapshot(now=datetime(2026,11,11,12,tzinfo=timezone.utc))
        assert len(calls) == 6
        saved = json.loads(c.LAST_GOOD.read_text())
        assert set(saved) == {'BLS', 'BEA', 'Federal Reserve'}
    finally:
        c.CACHE.clear()


def test_failed_refresh_keeps_last_success_and_labels_stale(monkeypatch, tmp_path):
    import json
    c.CACHE.clear()
    path = tmp_path / 'last.json'
    event = {'title':'FOMC Meeting','date':'2026-12-09','at':'2026-12-09T14:00:00-05:00','agency':'Federal Reserve','source':c.FEEDS['Federal Reserve']}
    path.write_text(json.dumps({'Federal Reserve':{'checked_at':'2026-11-09T12:00:00+00:00','events':[event]}}))
    monkeypatch.setattr(c, 'LAST_GOOD', path)
    monkeypatch.setattr(c, 'fetch', lambda url: (_ for _ in ()).throw(OSError('offline')))
    monkeypatch.setattr(c, 'bls_from_fred', lambda today: (_ for _ in ()).throw(OSError('offline')))
    try:
        r = c.snapshot(now=datetime(2026,11,10,12,tzinfo=timezone.utc))
        assert r['partial']
        assert any(e['title'] == 'FOMC Meeting' and e['stale'] for e in r['events'])
        assert json.loads(path.read_text())['Federal Reserve']['checked_at'] == '2026-11-09T12:00:00+00:00'
    finally:
        c.CACHE.clear()
