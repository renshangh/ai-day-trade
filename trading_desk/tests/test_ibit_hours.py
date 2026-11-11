"""Real calendar metadata and schedule boundaries; no synthetic market bars."""
import copy
import hashlib
import json
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'trading_desk'))
from trading_desk.btc_data import read, save
from trading_desk.ibit_hours import Calendar, Service, epoch, request_calendar, signal_hours

FIXTURES = Path(__file__).parent / 'fixtures'


def document(now):
    # Actual sourced dates/times, with only the retrieval clock controlled.
    doc = copy.deepcopy(read(FIXTURES / 'ibit_calendar_2025_2027.json'))
    doc['fetched_at'] = now
    return doc


def calendar(now='2026-11-10T17:00:00Z'):
    return Calendar(document(now), epoch(now))


def sample(now, reference, detected, **extra):
    n = epoch(now)
    c = calendar(now)
    row = dict(time_utc=reference, detected_at=detected, decision='entry', **extra)
    return signal_hours(row, c.at(n), c, n)


def status():
    entry = copy.deepcopy(read(FIXTURES / 'ibit_hours_reference.json')['signal'])
    entry['detected_at'] = entry['interval_end']
    return dict(health='running', signals=[entry], events=[])


@pytest.mark.parametrize('stamp,code,regular', [
    ('2026-11-09T00:59:59Z', 'closed', False),  # Sunday 19:59:59 EST
    ('2026-11-09T01:00:00Z', 'overnight', False),
    ('2026-11-10T13:00:00Z', 'premarket', False),
    ('2026-11-10T14:24:59Z', 'premarket', False),
    ('2026-11-10T14:25:00Z', 'break', False),
    ('2026-11-10T14:30:00Z', 'regular', True),
    ('2026-11-10T21:00:00Z', 'break', False),
    ('2026-11-10T21:05:00Z', 'after_hours', False),
    ('2026-11-11T01:00:00Z', 'overnight', False),
    ('2026-11-14T00:59:59Z', 'after_hours', False),  # Friday 19:59:59
    ('2026-11-14T01:00:00Z', 'closed', False),
    ('2026-11-14T17:00:00Z', 'closed', False),
])
def test_actual_schedule_week_open_close_and_session_breaks(stamp, code, regular):
    window = calendar().at(epoch(stamp))
    assert window['code'] == code
    assert window['regular_open'] == regular
    assert window['trading_open'] == (code not in ('closed', 'break'))


def test_full_holiday_early_close_and_dst():
    c = calendar()
    # Thanksgiving closes Wed 20:00, reopens Thu 20:00, Fri half day ends 17:00.
    assert c.at(epoch('2026-11-26T00:59:59Z'))['trading_open']
    assert c.at(epoch('2026-11-26T01:00:00Z'))['code'] == 'closed'
    assert c.at(epoch('2026-11-26T17:00:00Z'))['code'] == 'closed'
    assert c.at(epoch('2026-11-27T01:00:00Z'))['code'] == 'overnight'
    assert c.at(epoch('2026-11-27T18:00:00Z'))['code'] == 'break'
    assert c.at(epoch('2026-11-27T18:05:00Z'))['code'] == 'after_hours'
    assert c.at(epoch('2026-11-27T21:59:59Z'))['trading_open']
    assert c.at(epoch('2026-11-27T22:00:00Z'))['code'] == 'closed'
    # Christmas Friday: do not reopen Thursday evening, only Sunday evening.
    x = c.at(epoch('2026-12-25T01:00:00Z'))
    assert x['code'] == 'closed' and x['next_open'] == '2026-12-28T01:00:00Z'
    assert c.at(epoch('2026-10-30T13:30:00Z'))['regular_open']
    assert not c.at(epoch('2026-11-02T13:30:00Z'))['regular_open']
    assert c.at(epoch('2026-11-02T14:30:00Z'))['regular_open']
    weekend = c.at(epoch('2026-11-07T17:00:00Z'))
    assert weekend['next_open'] == '2026-11-09T01:00:00Z'


def test_availability_not_reference_controls_the_window():
    opening = sample('2026-11-10T14:30:10Z', '2026-11-10T14:29:00Z', '2026-11-10T14:30:06Z')
    assert opening['reference_session'] == 'break' and opening['availability_session'] == 'regular'
    assert opening['timing_window_open']
    closing = sample('2026-11-10T21:00:10Z', '2026-11-10T20:59:00Z', '2026-11-10T21:00:06Z')
    assert closing['reference_session'] == 'regular' and closing['availability_session'] == 'break'
    assert not closing['timing_window_open']
    overnight = sample('2026-11-11T02:00:10Z', '2026-11-11T01:59:00Z', '2026-11-11T02:00:06Z')
    assert overnight['timing_window_open'] and 'overnight' in overnight['label']
    assert not overnight['execution_verified']


def test_old_delayed_future_and_invalid_signals_never_revive():
    old = sample('2026-11-10T16:00:00Z', '2026-11-09T16:00:00Z', '2026-11-09T16:01:01Z')
    assert old['state'] == 'historical' and not old['timing_window_open']
    delayed = sample('2026-11-10T16:00:10Z', '2026-11-09T23:00:00Z', '2026-11-10T16:00:01Z')
    assert delayed['state'] == 'historical' and delayed['delay_after_completed_minute_seconds'] > 180
    waiting = sample('2026-11-10T16:00:00Z', '2026-11-10T16:01:00Z', '2026-11-10T16:02:00Z')
    assert waiting['state'] == 'waiting'
    for value in (None, 'invalid', '2026-11-10T16:00:00'):
        row = sample('2026-11-10T16:00:10Z', '2026-11-10T15:59:00Z', value)
        assert row['state'] == 'unknown' and not row['execution_verified']


def test_entry_exit_rejection_and_information_are_separate():
    now = '2026-11-10T16:00:10Z'
    n, c = epoch(now), calendar(now)
    event = dict(type='stop', fraction=1., reference_time='2026-11-10T15:59:00Z', detected_at='2026-11-10T16:00:01Z')
    assert signal_hours(event, c.at(n), c, n, event=True)['timing_window_open']
    event.pop('fraction')
    event['type'] = 'stop_raised'
    assert signal_hours(event, c.at(n), c, n, event=True)['state'] == 'info'
    row = dict(decision='held_position', time_utc='2026-11-10T15:59:00Z', detected_at='2026-11-10T16:00:01Z')
    assert signal_hours(row, c.at(n), c, n)['state'] == 'info'
    row['decision'] = 'entry'
    assert signal_hours(row, c.at(n), c, n, worker_health='stale')['state'] == 'unknown'


def test_missing_stale_malformed_and_outside_calendar_fail_unknown(tmp_path):
    n = epoch('2026-12-07T03:00:00Z')
    service = Service(tmp_path, lambda: n)
    for doc in ({}, [], {'sessions': []}, document('2026-12-05T03:00:00Z')):
        save(tmp_path / 'CALENDAR.json', doc)
        assert service.overlay({}, allow_refresh=False)['current']['code'] == 'unknown'
    doc = document('2026-12-07T03:00:00Z')
    doc['sessions'].append(copy.deepcopy(doc['sessions'][0]))
    assert Calendar(doc, n).error
    doc = document('2026-12-07T03:00:00Z')
    doc['sessions'][0]['open'] = '08:00'
    assert Calendar(doc, n).error
    save(tmp_path / 'CALENDAR.json', document('2026-12-07T03:00:00Z'))
    d = service.overlay({}, allow_refresh=False)
    assert d['current']['code'] == 'overnight' and d['policy'] == 'thinkorswim_exto_24_5'
    assert d['planned_23_5']['status'] == 'separate_nasdaq_plan'
    assert calendar().at(epoch('2030-11-10T16:00:00Z'))['code'] == 'unknown'


def test_overlay_does_not_mutate_source_or_fetch_on_fresh_calendar(tmp_path, monkeypatch):
    now = '2026-11-10T16:00:10Z'
    save(tmp_path / 'CALENDAR.json', document(now))
    service = Service(tmp_path, lambda: epoch(now))
    monkeypatch.setattr(service, 'refresh', lambda: pytest.fail('Fresh cache must not fetch'))
    state = status()
    before = copy.deepcopy(state)
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ('trading_desk/btc_live.py', 'scripts/run_btc_live.py')}
    metadata = service.overlay(state)
    assert state == before
    assert hashes == {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in hashes}
    assert len(metadata['signals']) == len(state['signals'])
    assert not metadata['orders_enabled'] and not metadata['strategy_changed']


def test_refresh_is_single_bounded_job_and_failure_preserves_cache(tmp_path, monkeypatch):
    import trading_desk.ibit_hours as hours
    now = '2026-11-10T16:00:10Z'
    save(tmp_path / 'CALENDAR.json', document(now))
    service = Service(tmp_path, lambda: epoch(now))
    before = (tmp_path / 'CALENDAR.json').read_bytes()
    calls, entered, release = [], threading.Event(), threading.Event()
    def unavailable(*args):
        calls.append(args)
        entered.set()
        assert release.wait(3)
        raise ValueError('Calendar offline')
    monkeypatch.setattr(hours, 'request_calendar', unavailable)
    missing = Calendar({}, epoch(now))
    try:
        for _ in range(5):
            service.ensure_refresh(missing)
        assert entered.wait(3) and len(calls) == 1
    finally:
        release.set()
        service.thread.join(3)
    service.ensure_refresh(missing)
    assert len(calls) == 1 and (tmp_path / 'CALENDAR.json').read_bytes() == before
    monkeypatch.setattr(hours, 'request_calendar', lambda *args: [])
    with pytest.raises(ValueError):
        service.refresh()
    assert (tmp_path / 'CALENDAR.json').read_bytes() == before


def test_transport_is_pinned_get_no_redirect_and_archives_calendar_only(tmp_path, monkeypatch):
    import trading_desk.ibit_hours as hours
    payload = json.dumps(document('2026-11-10T16:00:10Z')['sessions']).encode()
    seen = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit): return payload[:limit]
    class Opener:
        def open(self, request, timeout):
            assert request.get_method() == 'GET'
            assert request.full_url.startswith('https://paper-api.alpaca.markets/v2/calendar?')
            assert timeout == 20
            seen.append(request.full_url)
            return Response()
    def build(handler):
        assert handler().redirect_request(None, None, None, None, None, None) is None
        return Opener()
    monkeypatch.setattr(hours, 'credentials', lambda: {})
    monkeypatch.setattr(hours.urllib.request, 'build_opener', build)
    assert len(request_calendar('2025-01-01', '2027-12-31', tmp_path)) == 752
    assert len(seen) == 1 and len(list((tmp_path / 'raw').glob('*.json.gz'))) == 1


def test_http_status_adds_only_a_display_sidecar(tmp_path, monkeypatch):
    import server
    from http.server import ThreadingHTTPServer
    original = status()
    service = Service(tmp_path, lambda: epoch('2026-11-10T16:00:10Z'))
    save(tmp_path / 'CALENDAR.json', document('2026-11-10T16:00:10Z'))
    monkeypatch.setattr(server.btc_live.CONTROLLER, 'status', lambda *a, **kw: copy.deepcopy(original))
    monkeypatch.setattr(server.ibit_hours, 'SERVICE', service)
    srv = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen('http://127.0.0.1:' + str(srv.server_address[1]) + '/api/btc-live') as r:
            data = json.load(r)
        metadata = data.pop('ibit_hours')
        assert data == original and metadata['symbol'] == 'IBIT'
        assert not metadata['orders_enabled'] and not metadata['execution_verified']
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(3)
