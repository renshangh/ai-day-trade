"""Read-only IBIT manual-trading hours overlay; never controls BTC or orders."""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_desk.btc_data import ROOT, credentials, iso, read, save

NY = ZoneInfo('America/New_York')
HOME = ROOT / 'trading_records/ibit_hours'
MAX_AGE = 86400
FRESH_SIGNAL_SECONDS = 180
SOURCE = 'Alpaca exchange calendar /v2/calendar'
PROFILE = dict(
    channel='thinkorswim EXTO',
    eligibility='IBIT eligibility reported by owner on 2026-11-10; not verified through broker API',
    hours='Sunday 20:00 through Friday 20:00 Eastern, with holidays and session breaks',
    order_note='Manual LIMIT orders using EXTO; outside regular hours broker stop orders do not execute. API overnight routing is not established.',
    source='https://www.schwab.com/learn/story/ins-and-outs-245-trading',
    holiday_source='https://workplace.schwab.com/story/how-does-extended-hours-trading-work',
)
PLAN = dict(
    starts_at='2026-12-06T21:00:00-05:00', status='separate_nasdaq_plan',
    daily_pause='20:00–21:00 America/New_York',
    note='The separate planned Nasdaq 23/5 schedule does not replace current thinkorswim EXTO hours or establish API access.',
    source='https://www.nasdaq.com/23-5-trading',
)


def epoch(value):
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp.timestamp() if stamp.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


class Calendar:
    """Apply published Schwab session rules to actual sourced trading dates.

    Each exchange trading date owns the previous calendar evening from 20:00.
    This naturally excludes weekends and full holidays, including Friday
    holidays. Half days end at 17:00 per Schwab, with the actual exchange close
    still controlling its five-minute post-close break. No market bars exist
    here, and source metadata is never filled with guessed sessions.
    """
    def __init__(self, document, now):
        self.now = now
        self.sessions = {}
        self.windows = []
        self.error = None
        try:
            fetched = epoch(document['fetched_at'])
            self.start = datetime.fromisoformat(document['start']).date()
            self.end = datetime.fromisoformat(document['end']).date()
            if fetched is None or not 0 <= now - fetched <= MAX_AGE:
                raise ValueError('Stale or future calendar')
            rows = document['sessions']
            if not isinstance(rows, list) or not rows or self.start >= self.end:
                raise ValueError('Calendar unavailable')
            for row in rows:
                day = row['date']
                date = datetime.fromisoformat(day).date()
                opening = datetime.fromisoformat(day + 'T' + row['open']).replace(tzinfo=NY)
                closing = datetime.fromisoformat(day + 'T' + row['close']).replace(tzinfo=NY)
                if (day in self.sessions or not self.start <= date <= self.end
                        or date.weekday() > 4 or opening.time().isoformat() != '09:30:00'
                        or closing.hour not in (13, 16) or closing.minute or closing.second):
                    raise ValueError('Unsupported exchange calendar')
                start = (opening - timedelta(days=1)).replace(hour=20, minute=0)
                end = closing.replace(hour=17 if closing.hour == 13 else 20)
                row = dict(date=day, opening=opening.timestamp(), closing=closing.timestamp())
                self.sessions[day] = row
                # Published five-minute closures before and after RTH are
                # distinct from a reference signal's availability minute.
                points = (start.timestamp(), row['opening'] - 300,
                          row['opening'], row['closing'], row['closing'] + 300, end.timestamp())
                self.windows.extend((a, b, row) for a, b in ((points[0], points[1]),
                    (points[2], points[3]), (points[4], points[5])))
            self.windows.sort(key=lambda w: w[0])
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            self.error = 'Calendar unavailable, unsupported or stale; hours unverified'
            self.windows = []
            self.sessions = {}

    def at(self, stamp):
        unknown = dict(code='unknown', label='IBIT hours unverified', regular_open=False, trading_open=False)
        if self.error or stamp is None:
            return unknown
        try:
            local = datetime.fromtimestamp(stamp, NY)
        except (ValueError, OverflowError, OSError, TypeError):
            return unknown
        if not self.start <= local.date() <= self.end:
            return unknown
        rth = self.sessions.get(local.date().isoformat())
        regular = bool(rth and rth['opening'] <= stamp < rth['closing'])
        active = next((w for w in self.windows if w[0] <= stamp < w[1]), None)
        later = next((w for w in self.windows if w[0] > stamp), None)
        if active:
            row = active[2]
            if regular:
                code, name = 'regular', 'Regular'
            elif stamp >= row['closing']:
                code, name = 'after_hours', 'After-hours'
            elif local.date().isoformat() != row['date'] or local.hour < 7:
                code, name = 'overnight', 'Overnight'
            else:
                code, name = 'premarket', 'Pre-market'
            label = f'IBIT {name.lower()} window open · thinkorswim'
        else:
            pause = bool(rth and (rth['opening'] - 300 <= stamp < rth['opening']
                                 or rth['closing'] <= stamp < rth['closing'] + 300))
            code, name = ('break', 'Session break') if pause else ('closed', 'Closed')
            label = 'IBIT session break' if pause else 'IBIT trading window closed'
        return dict(code=code, label=label, session=name, regular_open=regular,
                    trading_open=bool(active), closes_at=iso(active[1]) if active else None,
                    next_open=iso(later[0]) if later else None,
                    next_close=iso(later[1]) if later else None,
                    regular_closes_at=iso(rth['closing']) if regular else None,
                    local_time=local.isoformat())


def signal_hours(row, current, calendar, now, *, event=False, worker_health='running'):
    reference = epoch(row.get('reference_time') if event else row.get('time_utc'))
    action = (row.get('type') == 'entry' or (isinstance(row.get('fraction'), (int, float))
              and row['fraction'] > 0)) if event else row.get('decision') == 'entry'
    detected = epoch(row.get('detected_at'))
    end = epoch(row.get('interval_end'))
    earliest = max(reference + 60, end or reference + 60) if reference is not None else None
    available = max(earliest, detected) if earliest is not None and detected is not None else None
    ref_window, window = calendar.at(reference), calendar.at(available)
    age = now - available if available is not None else None
    delay = available - earliest if available is not None else None
    historical = age is not None and (age > FRESH_SIGNAL_SECONDS or delay > FRESH_SIGNAL_SECONDS)
    session = window.get('session', 'unverified')
    if not action:
        state, label = 'info', 'Info only' if event else 'No entry'
    elif window['code'] == 'unknown' or current['code'] == 'unknown' or available is None:
        state, label = 'unknown', 'IBIT hours unverified'
    elif available > now:
        state, label = 'waiting', 'Not yet available'
    elif historical:
        state, label = 'historical', f'Historical · {session} at detection'
    elif not window['trading_open'] or not current['trading_open']:
        state, label = 'closed', 'Outside IBIT trading window'
    elif worker_health != 'running':
        state, label = 'unknown', 'BTC feed not current'
    else:
        state, label = 'review', f'Recent · IBIT {session.lower()} window'
    return dict(state=state, label=label, is_entry_or_exit=action,
                reference_time=row.get('reference_time') if event else row.get('time_utc'),
                reference_session=ref_window['code'], available_at=iso(available) if available is not None else None,
                availability_session=window['code'], age_seconds=age,
                delay_after_completed_minute_seconds=delay,
                timing_window_open=state == 'review', execution_verified=False,
                note='Hours only, for manual thinkorswim review. Check IBIT quote/spread and eligibility. Outside RTH use LIMIT/EXTO; broker stops do not execute there. BTC prices are not IBIT prices. Never backfill old signals.')


def request_calendar(start, end, folder):
    """Pinned GET-only calendar request, independent of research/order modules."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    url = 'https://paper-api.alpaca.markets/v2/calendar?' + urllib.parse.urlencode(dict(start=start, end=end))
    request = urllib.request.Request(url, headers=credentials(), method='GET')
    with urllib.request.build_opener(NoRedirect).open(request, timeout=20) as response:
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError('Oversized calendar response')
    data = json.loads(payload)
    raw = folder / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    dest = raw / (hashlib.sha256(payload).hexdigest() + '.json.gz')
    if not dest.exists():
        dest.write_bytes(gzip.compress(payload))
    return data


class Service:
    def __init__(self, root=HOME, clock=time.time):
        self.root, self.clock = Path(root), clock
        self.lock, self.thread, self.last_attempt = threading.Lock(), None, None

    def refresh(self):
        now = self.clock()
        year = datetime.fromtimestamp(now, NY).year
        start, end = f'{year-1}-01-01', f'{year+1}-12-31'
        rows = request_calendar(start, end, self.root)
        document = dict(start=start, end=end, sessions=rows, fetched_at=iso(now), source=SOURCE)
        if Calendar(document, now).error:
            raise ValueError('Invalid exchange calendar; prior cache retained')
        save(self.root / 'CALENDAR.json', document)
        return document

    def ensure_refresh(self, calendar):
        if calendar.error is None:
            return
        with self.lock:
            if (self.thread and self.thread.is_alive()) or (self.last_attempt is not None and self.clock() - self.last_attempt < 60):
                return
            self.last_attempt = self.clock()
            def work():
                try:
                    self.refresh()
                except Exception:
                    pass  # UI stays unknown, never guessed open; no credential/error payload is returned.
            self.thread = threading.Thread(target=work, daemon=True, name='ibit-hours-calendar')
            self.thread.start()

    def overlay(self, state, *, allow_refresh=True):
        now = self.clock()
        try:
            document = read(self.root / 'CALENDAR.json', {})
        except (OSError, ValueError):
            document = {}
        calendar = Calendar(document, now)
        if allow_refresh:
            self.ensure_refresh(calendar)
        current = calendar.at(now)
        return dict(symbol='IBIT', policy='thinkorswim_exto_24_5', now=iso(now), current=current,
                    calendar_error=calendar.error, calendar_fetched_at=document.get('fetched_at') if isinstance(document, dict) else None,
                    source=SOURCE, manual_profile=copy.deepcopy(PROFILE), planned_23_5=copy.deepcopy(PLAN),
                    signals=[signal_hours(s, current, calendar, now, worker_health=state.get('health')) for s in state.get('signals', [])],
                    events=[signal_hours(e, current, calendar, now, event=True, worker_health=state.get('health')) for e in state.get('events', [])],
                    orders_enabled=False, strategy_changed=False, execution_verified=False)


SERVICE = Service()
