"""Sourced release schedules; never infer release dates, times, or results."""
from __future__ import annotations

import json
import html
import re
import subprocess
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
ROOT = Path(__file__).resolve().parent
LOCK = threading.Lock()
CACHE: dict = {}
_worker = None
FEEDS = {
    'BLS': 'https://www.bls.gov/schedule/news_release/bls.ics',
    'BEA': 'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics',
    'Federal Reserve': 'https://www.federalreserve.gov/json/calendar.json',
}
FRED = 'https://fred.stlouisfed.org/releases/calendar'
BLS_RELEASES = {'10': 'Consumer Price Index', '50': 'Employment Situation',
                '192': 'Job Openings and Labor Turnover', '46': 'Producer Price Index'}
LAST_GOOD = ROOT.parent / 'trading_records' / 'economic_calendar_latest.json'
IMPORTANT = re.compile(r'consumer price|producer price|employment situation|job openings|employment cost|productivity|import.*export|gross domestic product|\bgdp\b|personal income|international trade', re.I)


def fetch(url):
    def curl_text():
        result = subprocess.run(['curl', '--fail', '--silent', '--show-error',
                                 '--location', '--max-time', '12', url],
                                capture_output=True, timeout=15, check=True)
        if len(result.stdout) > 2_000_000:
            raise ValueError('Calendar response too large')
        return result.stdout.decode('utf-8-sig')
    if url.startswith(('https://www.federalreserve.gov/', 'https://fred.stlouisfed.org/')):
        return curl_text()
    request = urllib.request.Request(url, headers={'User-Agent': 'TradingDesk economic calendar'})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.read(2_000_000).decode('utf-8-sig')
    except Exception:
        # Some publisher CDNs reject urllib but accept the system TLS client.
        # No cookies, authentication, third-party proxy, or access-control bypass.
        return curl_text()


def parse_fed(text, source):
    payload = json.loads(text)
    if not isinstance(payload.get('events'), list):
        raise ValueError('Fed calendar schema changed')
    events = []
    for item in payload['events']:
        title = item.get('title', '')
        if not re.search(r'FOMC|Beige Book', title, re.I):
            continue
        month = item.get('month', '')
        if not month:
            # The publisher mixes undated archival entries into this feed.
            # They cannot be assigned a year/month and are not current events.
            continue
        if not re.fullmatch(r'\d{4}-\d{2}', month):
            raise ValueError('Fed calendar month invalid')
        days = str(item.get('days', '')).strip()
        if not re.fullmatch(r'\d{1,2}(?:\s*,\s*\d{1,2})*', days):
            raise ValueError('Fed calendar day format changed')
        raw_time = item.get('time', '').strip()
        match = re.fullmatch(r'(\d{1,2}):(\d{2})\s*([ap])\.?m\.?', raw_time, re.I)
        if raw_time and not match:
            raise ValueError('Fed calendar time format changed')
        for day in days.split(','):
            date = datetime.strptime(f'{month}-{int(day):02}', '%Y-%m-%d')
            stamp = None
            if match:
                hour, minute, meridiem = match.groups()
                stamp = date.replace(hour=int(hour) % 12 + (12 if meridiem.lower() == 'p' else 0), minute=int(minute), tzinfo=ET).isoformat()
            events.append({'title': title, 'date': date.date().isoformat(), 'at': stamp,
                           'agency': 'Federal Reserve', 'source': source})
    if not events:
        raise ValueError('Fed calendar contains no policy events')
    return events


def parse_fred_day(text, rid, date):
    """Read the release row itself; FRED times are US Central, not Eastern."""
    if 'All times are US Central Time' not in text:
        raise ValueError('FRED calendar timezone not established')
    current_date = None
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', text, re.S | re.I):
        plain = html.unescape(re.sub('<[^>]*>', ' ', row))
        heading = re.search(r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})', plain)
        if heading:
            current_date = datetime.strptime(heading.group(1), '%B %d, %Y').date().isoformat()
        link = re.search(r'<a\b[^>]*href=["\']/release\?rid=' + re.escape(rid) + r'["\'][^>]*>(.*?)</a>', row, re.S)
        if link and current_date == date:
            title = html.unescape(re.sub('<[^>]*>', '', link.group(1))).strip()
            if not IMPORTANT.search(title):
                raise ValueError('Unexpected FRED release title')
            clock = re.search(r'\b(\d{1,2}:\d{2}\s*[ap]m)\b', plain, re.I)
            stamp = None
            if clock:
                dt = datetime.strptime(date + ' ' + clock.group(1).upper(), '%Y-%m-%d %I:%M %p')
                stamp = dt.replace(tzinfo=ZoneInfo('America/Chicago')).astimezone(ET).isoformat()
            return {'title': title, 'date': date, 'at': stamp, 'agency': 'BLS',
                    'source': f'{FRED}?rid={rid}&vs={date}&ve={date}&view=day',
                    'publisher_source': FEEDS['BLS'], 'retrieved_via': 'St. Louis Fed FRED'}
    raise ValueError('FRED release row missing for requested date')


def bls_from_fred(today):
    end = today + timedelta(days=30)
    def read_release(rid):
        url = f'{FRED}?rdc=1&vs={today}&ve={end}&rid={rid}'
        payload = json.loads(fetch(url))
        if not isinstance(payload.get('events'), list):
            raise ValueError('FRED date schema changed')
        events = []
        for row in payload['events']:
            date = row.get('start', '')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
                raise ValueError('FRED release date invalid')
            if str(today) <= date <= str(end):
                events.append(parse_fred_day(fetch(f'{FRED}?rid={rid}&vs={date}&ve={date}&view=day'), rid, date))
        return events
    with ThreadPoolExecutor(max_workers=4) as pool:
        return [event for rows in pool.map(read_release, BLS_RELEASES) for event in rows]


def parse_ics(text, agency, source):
    if 'BEGIN:VCALENDAR' not in text:
        raise ValueError('Source did not return a calendar')
    text = re.sub(r'\r?\n[ \t]', '', text)
    events = []
    for block in text.split('BEGIN:VEVENT')[1:]:
        fields = {}
        for line in block.split('END:VEVENT')[0].splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                fields[key] = value
        title = fields.get('SUMMARY', '').replace('\\,', ',').replace('\\n', ' ')
        if not IMPORTANT.search(title):
            continue
        starts = [(k, v) for k, v in fields.items() if k.split(';')[0] == 'DTSTART']
        if not starts:
            continue
        key, raw = starts[0]
        # A date-only announcement is not a timed release. Never guess 08:30.
        if re.fullmatch(r'\d{8}', raw):
            date = datetime.strptime(raw, '%Y%m%d').date().isoformat()
            stamp = None
        else:
            zone = timezone.utc if raw.endswith('Z') else ET
            tzid = re.search(r'TZID=([^;:]+)', key)
            if tzid:
                zone = ZoneInfo(tzid.group(1).strip('"'))
            stamp = datetime.strptime(raw.rstrip('Z'), '%Y%m%dT%H%M%S').replace(tzinfo=zone).astimezone(ET).isoformat()
            date = stamp[:10]
        events.append({'title': title, 'date': date, 'at': stamp, 'agency': agency, 'source': source})
    return events


def snapshot(*, now=None, force=False):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(ET).date()
    # The first request on each Eastern calendar day rechecks source schedules.
    # A failed daily attempt is retried after an hour, not on every browser poll.
    with LOCK:
        if CACHE and not force and CACHE['day'] == str(today):
            age = (now - datetime.fromisoformat(CACHE['checked_at'])).total_seconds()
            if not CACHE['partial'] or age < 3600:
                return CACHE
        seed = json.loads((ROOT / 'economic_calendar_verified.json').read_text())
        try:
            saved = json.loads(LAST_GOOD.read_text())
        except (OSError, ValueError):
            saved = {}
        def read(item):
            agency, url = item
            try:
                via = None
                if agency == 'Federal Reserve':
                    events = parse_fed(fetch(url), url)
                elif agency == 'BLS':
                    try:
                        events = parse_ics(fetch(url), agency, url)
                    except Exception:
                        events = bls_from_fred(today)
                        via = 'St. Louis Fed FRED (direct BLS unavailable)'
                else:
                    events = parse_ics(fetch(url), agency, url)
                if not any(e['date'] >= str(today) for e in events):
                    raise ValueError('Calendar has no current or upcoming important releases')
                return agency, events, {'agency': agency, 'url': FRED if via else url, 'status': 'refreshed', 'via': via, 'checked_at': now.isoformat()}
            except Exception as error:
                previous = saved.get(agency)
                events = [dict(e, stale=True) for e in (previous['events'] if previous else seed['events']) if e['agency'] == agency]
                verified = previous['checked_at'] if previous else seed['verified_date'] if events else None
                return agency, events, {'agency': agency, 'url': url, 'status': 'refresh unavailable', 'detail': type(error).__name__, 'last_verified': verified}
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(read, FEEDS.items()))
        for agency, rows, status in results:
            if status['status'] == 'refreshed':
                saved[agency] = {'events': rows, 'checked_at': now.isoformat()}
        if saved:
            LAST_GOOD.parent.mkdir(parents=True, exist_ok=True)
            temporary = LAST_GOOD.with_suffix('.tmp')
            temporary.write_text(json.dumps(saved))
            temporary.replace(LAST_GOOD)
        events = [e for _, rows, _ in results for e in rows]
        sources = [status for _, _, status in results]
        end = today + timedelta(days=30)
        events = [e for e in events if str(today) <= e['date'] <= str(end)]
        for e in events:
            e['status'] = ('Scheduled' if datetime.fromisoformat(e['at']) > now else 'Scheduled time passed; results not loaded') if e['at'] else 'Time not published'
        events.sort(key=lambda e: (e['date'], e['at'] or '', e['title']))
        CACHE.clear()
        CACHE.update(day=str(today), checked_at=now.isoformat(), timezone='America/New_York', events=events, sources=sources, partial=any(s['status'] != 'refreshed' for s in sources), coverage='Selected BLS / BEA releases and Fed policy events; not a complete economic calendar. BLS fallback via FRED covers CPI, payrolls, JOLTS and PPI. No consensus or actual results are supplied.')
        return CACHE


def start_daily_refresh():
    """Refresh in the running desk, even when no browser tab is open."""
    global _worker
    if _worker and _worker.is_alive():
        return
    def run():
        pause = threading.Event()
        while True:
            try:
                snapshot()
            except Exception:
                # Endpoint still reports unavailable; background failures must
                # never prevent the rest of the desk from serving requests.
                pass
            pause.wait(300)
    _worker = threading.Thread(target=run, name='economic-calendar-refresh', daemon=True)
    _worker.start()
