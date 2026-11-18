"""Two-year stock range research on real, complete consolidated daily bars."""
from __future__ import annotations

import math
import statistics
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import json

from ai_day_trade.alpaca_range_paper import Client
from ai_day_trade.range_trading import quantile
from range_geometry import completed_swings, ratio
from universe import all_groups

ET = ZoneInfo('America/New_York')
DAYS = 730
EXTRA = 'BABA JD BIDU TME BTI KHC CAG WU AAL DAL UAL JBLU CCL NCLH DKNG UAA UA BB NOK FMC CF MOS CLF AA NUE FCX VALE GGB KGC TEVA VTRS RKT PENN CZR MGM WYNN LYFT W PTON PATH ETSY DOW DD IP'.split()
SOURCE_PATH = Path(__file__).resolve().parents[1] / 'reports/range_trading/LONG_RANGE_SOURCE_LATEST.json'


def stock_pool(short_pool):
    return tuple(sorted({s for g in all_groups().values() for s in g['constituents']} | set(short_pool) | set(EXTRA)))


def window_start(asof):
    return (datetime.fromtimestamp(asof, timezone.utc) - timedelta(days=DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)


def expected_sessions(calendar, asof):
    start = window_start(asof).date().isoformat()
    sessions = {}
    for session in calendar:
        end = datetime.fromisoformat(session['date'] + 'T' + session['close']).replace(tzinfo=ET)
        if session['date'] >= start and end.timestamp() <= asof:
            sessions[session['date']] = end
    if len(sessions) < 480 or asof - max(x.timestamp() for x in sessions.values()) > 7 * 86400:
        raise ValueError('Complete two-year trading calendar unavailable or stale')
    return sessions


def stock_row(symbol, raw, calendar, asof, version):
    sessions = expected_sessions(calendar, asof)
    bars, seen = [], set()
    for bar in sorted(raw, key=lambda x: x['t']):
        date = datetime.fromisoformat(bar['t'].replace('Z', '+00:00')).date().isoformat()
        if date not in sessions:
            continue
        if date in seen:
            raise ValueError('Duplicate daily observations')
        seen.add(date)
        op, hi, lo, cl, vol = [float(bar[k]) for k in ('o', 'h', 'l', 'c', 'v')]
        if not all(math.isfinite(x) for x in (op, hi, lo, cl, vol)) or not 0 < lo <= min(op, cl) <= max(op, cl) <= hi or vol < 0:
            raise ValueError('Invalid daily OHLCV')
        bars.append(bar)
    if seen != set(sessions):
        raise ValueError('Incomplete two-year daily history; no gap filling')
    lower = quantile([x['l'] for x in bars], .1)
    upper = quantile([x['h'] for x in bars], .9)
    raw_ratio, rounded = ratio(lower, upper)
    width = upper - lower
    closes = [x['c'] for x in bars]
    half = len(bars) // 2
    count, visits = completed_swings(closes, lower, upper)
    annual = [completed_swings(c, lower, upper)[0] for c in (closes[:half], closes[half:])]
    recent, _ = completed_swings(closes[-126:], lower, upper)
    stability = max(abs(quantile([x[k] for x in bars[:half]], q) - quantile([x[k] for x in bars[half:]], q)) / width
                    for k, q in (('l', .1), ('h', .9)))
    quarters = [bars[i * len(bars) // 8:(i + 1) * len(bars) // 8] for i in range(8)]
    quarterly = [sum(lower <= x['c'] <= upper for x in q) / len(q) for q in quarters]
    containment = sum(lower <= x <= upper for x in closes) / len(closes)
    dollar20 = statistics.mean(x['c'] * x['v'] for x in bars[-20:])
    dollar5 = statistics.mean(x['c'] * x['v'] for x in bars[-5:])
    shares20 = statistics.mean(x['v'] for x in bars[-20:])
    shares5 = statistics.mean(x['v'] for x in bars[-5:])
    checks = {
        'Fewer than three full swings over two years': count >= 3,
        'No completed full swing in one annual half': min(annual) >= 1,
        'Boundary movement above 60%': stability <= .6,
        'Fewer than 80% of daily closes inside range': containment >= .8,
        'A quarter has fewer than 50% of closes inside range': min(quarterly) >= .5,
        'Latest completed close outside range': lower <= closes[-1] <= upper,
    }
    liquid = min(dollar20, dollar5) >= 100_000_000 and min(shares20, shares5) >= 2_000_000
    advisories = ['Earnings/news, fresh support reaction, spread and depth require review before entry']
    if recent == 0:
        advisories.append('No full swing in the latest 126 sessions; lower priority')
    row = dict(symbol=symbol, asset='stock', stock_mode='two_year', lookback_days=DAYS,
        qualification_version=version, quality_pass=all(checks.values()), liquidity_pass=liquid,
        support=lower, resistance=upper, range_ratio=raw_ratio, rounded_ratio=rounded,
        last_close=closes[-1], last_bar_at=sessions[max(sessions)].isoformat(),
        source='Alpaca SIP · split/dividend adjusted', interval='1d regular session',
        volume_usd=dollar20, volume_shares=shares20, volume_usd_5=dollar5, volume_shares_5=shares5,
        volume_scope='Both 5- and 20-session averages must pass; table shows 20-session average',
        completed_cycles=count, alternating_boundary_visits=visits, annual_cycles=annual,
        recent_six_month_cycles=recent, quarter_containment=quarterly, containment=containment,
        stability=stability, drift=abs(closes[-1] - closes[0]) / width,
        ranking_score=round(100 * (recent >= 1) + 10 * min(count, 10) + 20 * (1 - min(stability, 1)), 2),
        warnings=[reason for reason, passed in checks.items() if not passed], advisories=advisories,
        paper_supported=None, execution_enabled=False)
    # Only viable rows carry prices to keep repeated local status polling small.
    if row['quality_pass'] and liquid:
        row['daily_closes'] = [[x['t'][:10], x['c']] for x in bars]
    return row


def fetch_snapshot(symbols, asof):
    """No IEX-volume fallback; a failed batch remains explicitly unavailable."""
    client = Client()
    start = window_start(asof)
    end = datetime.fromtimestamp(asof, timezone.utc) - timedelta(minutes=16)
    calendar = client.request('/v2/calendar?' + urllib.parse.urlencode(dict(start=start.date().isoformat(), end=end.date().isoformat())))
    expected_sessions(calendar, asof)

    def fetch(chunk):
        products, token, seen = {}, None, set()
        while True:
            params = dict(symbols=','.join(chunk), timeframe='1Day', start=start.isoformat(), end=end.isoformat(),
                          adjustment='all', sort='asc', limit=10000, feed='sip')
            if token:
                params['page_token'] = token
            page = client.request('/v2/stocks/bars?' + urllib.parse.urlencode(params), data=True)
            for symbol, bars in (page.get('bars') or {}).items():
                products.setdefault(symbol, []).extend(bars)
            token = page.get('next_page_token')
            if not token:
                return products
            if token in seen:
                raise ValueError('Repeated history pagination token')
            seen.add(token)

    products, errors = {}, []
    with ThreadPoolExecutor(max_workers=3) as pool:
        tasks = {pool.submit(fetch, symbols[i:i + 70]): symbols[i:i + 70] for i in range(0, len(symbols), 70)}
        for future in as_completed(tasks):
            try:
                products.update(future.result())
            except Exception:
                errors.extend(tasks[future])
    result = dict(source='Alpaca consolidated SIP daily bars', adjustment='all (split and dividend adjusted)',
                  retrieved_at=datetime.fromtimestamp(asof, timezone.utc).isoformat(), start=start.isoformat(),
                  calendar=calendar, symbols=list(symbols), products=products, batch_errors=errors)
    try:
        SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = SOURCE_PATH.with_suffix('.tmp')
        temp.write_text(json.dumps(result, separators=(',', ':')) + '\n')
        temp.replace(SOURCE_PATH)
    except OSError:
        pass  # A persistence problem never authorizes replacement observations.
    return result
