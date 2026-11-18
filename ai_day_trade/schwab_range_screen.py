"""Read-only stock range research using Schwab bars and the Alpaca calendar.

Seven calendar days of completed regular sessions; no stock order submission.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .alpaca_range_paper import Client
from .range_trading import iso, quantile, touches
from scripts import schwab_api

ET = ZoneInfo('America/New_York')
STOCKS = ('AAPL', 'MSFT', 'AMZN', 'GOOGL', 'META', 'NVDA', 'AMD', 'TSLA',
          'PLTR', 'SOFI', 'UBER', 'HOOD', 'COIN', 'CRCL', 'INTC', 'MU', 'QCOM',
          'PYPL', 'JPM', 'BAC', 'C', 'WFC', 'XOM', 'CVX', 'F', 'GM', 'T',
          'PFE', 'KO', 'DIS', 'NKE', 'NIO', 'SNAP', 'RIVN')


def session_grid(calendar, asof, days):
    expected = {}
    for session in calendar:
        start = datetime.fromisoformat(session['date'] + 'T' + session['open']).replace(tzinfo=ET).timestamp()
        end = datetime.fromisoformat(session['date'] + 'T' + session['close']).replace(tzinfo=ET).timestamp()
        if start >= asof - days * 86400 and end <= asof:
            if end <= start or (end - start) % 1800:
                raise ValueError('invalid session hours')
            expected[session['date']] = set(range(int(start), int(end), 1800))
    return expected


def screen(snapshot, days=7, *, max_boundary_movement=.40):
    if days < 3 or days > 45:
        raise ValueError('stock research window must be 3–45 calendar days')
    expected = session_grid(snapshot['calendar'], snapshot['retrieved_at'], days)
    if len(expected) < max(3, days // 2):
        raise ValueError('insufficient completed stock sessions for requested window')
    stamps = set.union(*expected.values())
    rows = []
    for symbol, item in snapshot['products'].items():
        try:
            if item.get('error') or item.get('empty'):
                raise ValueError(item.get('error', 'no Schwab history'))
            bars, seen = [], set()
            for bar in sorted(item.get('candles', []), key=lambda x: x['datetime']):
                raw_time = float(bar['datetime']) / 1000
                ts = int(raw_time)
                if ts not in stamps:
                    continue
                if raw_time != ts or ts in seen:
                    raise ValueError('duplicate or unaligned bar')
                seen.add(ts)
                values = [float(bar[k]) for k in ('open', 'high', 'low', 'close', 'volume')]
                op, hi, lo, cl, vol = values
                if (not all(math.isfinite(v) for v in values)
                        or not 0 < lo <= min(op, cl) <= max(op, cl) <= hi or vol < 0):
                    raise ValueError('invalid stock OHLCV')
                bars.append(bar)
            if seen != stamps:
                raise ValueError('incomplete regular-session history; no gap filling')
            lower = quantile([x['low'] for x in bars], .1)
            upper = quantile([x['high'] for x in bars], .9)
            width, mid = upper - lower, (upper + lower) / 2
            if width <= 0:
                raise ValueError('zero range')
            closes = [x['close'] for x in bars]
            path = sum(abs(y - x) for x, y in zip(closes, closes[1:]))
            efficiency = abs(closes[-1] - closes[0]) / path if path else 1
            drift = abs(closes[-1] - closes[0]) / width
            half = len(bars) // 2
            stability = max(abs(quantile([x[k] for x in bars[:half]], q)
                                - quantile([x[k] for x in bars[half:]], q)) / width
                            for k, q in (('low', .1), ('high', .9)))
            crossings = sum((x < mid <= y) or (y < mid <= x) for x, y in zip(closes, closes[1:]))
            visits = [touches([x['low'] <= lower + .15 * width for x in bars]),
                      touches([x['high'] >= upper - .15 * width for x in bars])]
            avg_volume = sum(x['volume'] for x in bars) / len(expected)
            avg_turnover = sum(x['volume'] * x['close'] for x in bars) / len(expected)
            containment = sum(lower <= x <= upper for x in closes) / len(bars)
            checks = {
                'average daily volume below 2M shares': avg_volume >= 2_000_000,
                'average daily turnover proxy below $100M': avg_turnover >= 100_000_000,
                'range width outside 1–20%': .01 <= width / mid <= .20,
                'too much directional drift': drift <= .4,
                'too much trend efficiency': efficiency <= .25,
                'unstable boundaries': stability <= max_boundary_movement,
                'too few midpoint crossings': crossings >= 3,
                'too few boundary visits': min(visits) >= 2,
                'too few closes inside range': containment >= .8,
                'latest close outside range': lower <= closes[-1] <= upper,
            }
            reasons = [label for label, passed in checks.items() if not passed]
            atr = statistics.mean(max(y['high'] - y['low'], abs(y['high'] - x['close']),
                                      abs(y['low'] - x['close'])) for x, y in zip(bars[-15:-1], bars[-14:]))
            rows.append(dict(symbol=symbol, range_qualified=not reasons, reasons=reasons,
                             support=lower, resistance=upper, regular_close=closes[-1],
                             entry_ceiling=lower + .15 * width, target=upper - .15 * width,
                             stop_reference=lower - .5 * atr, average_daily_shares=avg_volume,
                             average_daily_turnover_proxy=avg_turnover,
                             drift=drift, efficiency=efficiency, stability=stability,
                             midpoint_crossings=crossings, boundary_visits=visits,
                             containment=containment, bars=len(bars),
                             score=100 * (1 - efficiency) * (1 - min(stability, 1)) if not reasons else 0,
                             entry_authorized=False, earnings_status='not verified; review before entry'))
        except (ValueError, KeyError, TypeError) as exc:
            rows.append(dict(symbol=symbol, range_qualified=False, reasons=[str(exc)]))
    return dict(mode='read_only_stock_research', source=snapshot['source'],
                asof=iso(snapshot['retrieved_at']), calendar_days=days,
                session_dates=sorted(expected), interval='30 minute regular session',
                warning='Range fit only; earnings, news, spreads and broker eligibility need review',
                results=sorted(rows, key=lambda x: x.get('score', 0), reverse=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+', default=STOCKS)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--output', type=Path, default=Path('reports/range_trading/SCHWAB_STOCKS.json'))
    args = parser.parse_args()
    if args.snapshot:
        source = json.loads(args.snapshot.read_text())
    else:
        schwab_api.load_env(schwab_api.REPO_ROOT / '.env')
        now = time.time()
        today = datetime.fromtimestamp(now, ET)
        calendar = Client().request('/v2/calendar?start=' + (today - timedelta(days=10)).date().isoformat()
                                    + '&end=' + today.date().isoformat())
        products = {}
        for symbol in args.symbols:
            if not symbol.isalpha() or len(symbol) > 6:
                raise ValueError('invalid stock ticker')
            try:
                products[symbol] = schwab_api.api('/marketdata/v1/pricehistory', dict(
                    symbol=symbol, periodType='day', period=10, frequencyType='minute',
                    frequency=30, needExtendedHoursData='false'))
            except schwab_api.SchwabError as exc:
                products[symbol] = {'error': 'Schwab HTTP ' + str(exc.status)}
        source = dict(source='Schwab market data API', retrieved_at=now,
                      calendar_source='Alpaca trading calendar', calendar=calendar, products=products)
    result = screen(source, args.days)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.source.json').write_text(json.dumps(source, indent=2) + '\n')
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for row in result['results']:
        if row['range_qualified']:
            print(row['symbol'], 'range', round(row['support'], 2), round(row['resistance'], 2),
                  'avg daily shares', round(row['average_daily_shares']), flush=True)
    print('Read-only report:', args.output.resolve())


if __name__ == '__main__':
    main()
