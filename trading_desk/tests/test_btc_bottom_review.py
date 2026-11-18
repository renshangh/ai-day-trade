"""Audit actual persisted model actions; never generate market observations."""
import copy
import hashlib
import json
import sqlite3
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'trading_desk'))
from trading_desk.btc_bottom_review import history, snapshot
from trading_desk.btc_data import read, save
from trading_desk.ibit_hours import epoch

FIXTURES = Path(__file__).parent / 'fixtures'


def fixture(root):
    data = read(FIXTURES / 'btc_bottom_actions_20261114.json')
    state = copy.deepcopy(data['state'])
    folder = root / 'sessions' / state['session']['id']
    folder.mkdir(parents=True)
    path = folder / 'observations.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE events(id TEXT PRIMARY KEY,model TEXT,ref INTEGER,detected REAL,body TEXT)')
        db.execute('CREATE TABLE minutes(t INTEGER PRIMARY KEY,body TEXT,received REAL,sha TEXT)')
        for event in data['events']:
            db.execute('INSERT INTO events VALUES(?,?,?,?,?)', (event['event_id'], event['model'], event['ref'], event['detected'], json.dumps(event['body'])))
        for m in data['minutes']:
            db.execute('INSERT INTO minutes VALUES(?,?,?,?)', (m['t'], json.dumps(m['body']), m['received'], m['sha']))
    calendar = read(FIXTURES / 'ibit_calendar_2025_2027.json')
    calendar['fetched_at'] = '2026-11-15T00:00:00Z'
    save(root / 'calendar/CALENDAR.json', calendar)
    return state, path


def run(root, state, now):
    return history(state, now=epoch(now), root=root, calendar_root=root / 'calendar')


def test_empty_last12_is_distinct_from_latest_completed_trades(tmp_path):
    state, _ = fixture(tmp_path)
    result = run(tmp_path, state, '2026-11-15T14:35:00Z')
    assert result['status'] == 'available' and result['actions'] == []
    assert all(c == dict(entries=0, exits=0) for c in result['counts'].values())
    latest = result['recent_before_window']
    assert len(latest) == 2 and [r['trade_id'] for r in latest] == [20, 19]
    assert all(r['models'] == ['0.1', 'E1', 'E2'] for r in latest)
    assert abs(latest[0]['net'] - 55.6515768) < .00001
    assert abs(latest[1]['net'] + 306.7563599) < .00001
    assert all(r['ibit_session'] == 'closed' for r in latest)


def test_actions_inside_window_group_models_without_tripling_pl(tmp_path):
    state, _ = fixture(tmp_path)
    result = run(tmp_path, state, '2026-11-15T00:40:00Z')
    assert len(result['actions']) == 4
    assert all(c == dict(entries=2, exits=2) for c in result['counts'].values())
    assert all(len(r['event_ids']) == 3 for r in result['actions'])
    assert all(abs(n + 251.1047831) < .00001 for n in result['net_by_model'].values())
    assert all(r['availability_session'] == 'closed' for r in result['actions'])


def test_detection_availability_includes_older_reference_minute(tmp_path):
    state, _ = fixture(tmp_path)
    # Window starts at 16:39:30 EST: entry reference was 16:39, but was not
    # available until 16:40:10. All timestamps are from the actual archive.
    result = run(tmp_path, state, '2026-11-15T09:39:30Z')
    entry = next(r for r in result['actions'] if r['trade_id'] == 19 and r['action'] == 'entry')
    assert epoch(entry['reference_time']) < epoch(result['start']) < epoch(entry['available_at'])


def test_exact_window_boundary_and_future_events(tmp_path):
    state, _ = fixture(tmp_path)
    exact = '2026-11-14T21:40:10.433794Z'
    result = run(tmp_path, state, exact)
    assert len(result['actions']) == 1 and result['actions'][0]['trade_id'] == 19
    assert result['actions'][0]['action'] == 'entry'
    earlier = run(tmp_path, state, '2026-11-14T21:40:10Z')
    assert earlier['actions'] == []


def test_missing_database_and_empty_observations_are_not_zero_trades(tmp_path):
    state, path = fixture(tmp_path)
    other = tmp_path / 'missing'
    result = history(state, now=epoch('2026-11-15T14:35:00Z'), root=other)
    assert result['status'] == 'unavailable' and result['counts'] is None
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM minutes')  # Isolated test-only database.
    result = run(tmp_path, state, '2026-11-15T14:35:00Z')
    assert result['status'] == 'unavailable' and result['counts'] is None


def test_no_input_or_database_mutation_and_no_stale_quote_substitution(tmp_path):
    state, path = fixture(tmp_path)
    state['quote_fresh'] = False
    before = copy.deepcopy(state)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    data = snapshot(state, now=epoch('2026-11-15T14:35:00Z'), root=tmp_path, calendar_root=tmp_path / 'calendar')
    assert state == before and hashlib.sha256(path.read_bytes()).hexdigest() == digest
    assert data['quote'] is None and not data['orders_enabled'] and data['comparison_only']
    assert data['review']['prior']['status'].startswith('Invalidated')
    assert data['review']['scenario']['entry'] == 66160


def test_new_http_route_is_get_only_and_original_dto_stays_unchanged(tmp_path, monkeypatch):
    import server
    from http.server import ThreadingHTTPServer
    state, _ = fixture(tmp_path)
    expected = snapshot(state, now=epoch('2026-11-15T14:35:00Z'), root=tmp_path, calendar_root=tmp_path / 'calendar')
    monkeypatch.setattr(server.btc_live.CONTROLLER, 'status', lambda *a, **k: copy.deepcopy(state))
    monkeypatch.setattr(server.btc_bottom_review, 'snapshot', lambda s: expected)
    srv = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        base = 'http://127.0.0.1:' + str(srv.server_address[1])
        with urllib.request.urlopen(base + '/api/btc-bottom-review') as response:
            result = json.load(response)
        assert result == expected and not result['orders_enabled']
        with urllib.request.urlopen(base + '/btc_bottom_review.js') as response:
            assert response.read() == (ROOT / 'trading_desk/btc_bottom_review.js').read_bytes()
        with urllib.request.urlopen(base + '/api/btc-live') as response:
            original = json.load(response)
        original.pop('ibit_hours')
        assert original == state
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(3)
