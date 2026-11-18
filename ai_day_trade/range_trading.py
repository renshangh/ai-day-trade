"""Range screen and causal paper replay. No broker order submission exists here."""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import time
import urllib.parse
import urllib.request
import urllib.error
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

UNIVERSE = ('NEAR', 'DOT')
_PUBLIC_RATE_LOCK = threading.Lock()
_PUBLIC_LAST_REQUEST = 0.0


@dataclass(frozen=True)
class Config:
    lookback_days: int = 7
    fee: float = 0.0075  # Observed taker tier; both entry and exit pay fees.
    slippage: float = 0.001  # Assumption, not an observed historical spread.
    risk_fraction: float = 0.0025
    allocation_fraction: float = 0.20
    daily_loss_fraction: float = 0.01
    min_reward_risk: float = 1.5
    max_holding_days: int = 5
    min_daily_turnover: float = 1_000_000
    max_boundary_movement: float = .40

    def __post_init__(self):
        for value in (self.fee, self.slippage, self.risk_fraction,
                      self.allocation_fraction, self.daily_loss_fraction, self.max_boundary_movement):
            if not math.isfinite(value) or not 0 <= value < 1:
                raise ValueError('fractions must be finite and between zero and one')
        if (self.lookback_days < 3 or self.max_holding_days < 1 or self.min_reward_risk <= 0
                or not math.isfinite(self.min_daily_turnover) or self.min_daily_turnover < 0):
            raise ValueError('invalid lookback, holding period, or reward/risk')


def normalize(raw, seconds, asof):
    """Reject malformed observations; exclude forming bars; never fill gaps."""
    if seconds not in (3600, 14400, 21600, 86400):
        raise ValueError('unsupported candle interval')
    bars, seen = [], set()
    for row in raw:
        if isinstance(row, list):
            if len(row) != 6:
                raise ValueError('invalid Exchange candle')
            row = dict(zip(('start', 'low', 'high', 'open', 'close', 'volume'), row))
        values = {key: float(row[key]) for key in ('start', 'low', 'high', 'open', 'close', 'volume')}
        if not all(math.isfinite(v) for v in values.values()):
            raise ValueError('nonfinite candle')
        ts = values['start']
        if ts != int(ts) or ts % seconds or ts in seen:
            raise ValueError('duplicate or unaligned candle timestamp')
        seen.add(ts)
        if not (0 < values['low'] <= min(values['open'], values['close'])
                <= max(values['open'], values['close']) <= values['high']) or values['volume'] < 0:
            raise ValueError('invalid OHLCV candle')
        if ts + seconds <= asof:
            values['start'] = int(ts)
            bars.append(values)
    return sorted(bars, key=lambda b: b['start'])


def quantile(values, fraction):
    # Observed order statistic, not an interpolated market observation.
    return sorted(values)[int((len(values) - 1) * fraction)]


def touches(flags):
    return sum(flag and (i == 0 or not flags[i - 1]) for i, flag in enumerate(flags))


def assess(bars, seconds, config=Config(), *, asof=None):
    n = config.lookback_days * 86400 // seconds
    if len(bars) < n:
        return {'eligible': False, 'reasons': ['insufficient completed history']}
    b = bars[-n:]
    if any(y['start'] - x['start'] != seconds for x, y in zip(b, b[1:])):
        return {'eligible': False, 'reasons': ['missing candles; no gap filling']}
    if asof is not None and asof - (b[-1]['start'] + seconds) >= seconds:
        return {'eligible': False, 'reasons': ['stale candles']}
    c = [x['close'] for x in b]
    lower = quantile([x['low'] for x in b], .10)
    upper = quantile([x['high'] for x in b], .90)
    width = upper - lower
    if width <= 0:
        return {'eligible': False, 'reasons': ['zero range width']}
    atr = statistics.mean(max(y['high'] - y['low'], abs(y['high'] - x['close']),
                              abs(y['low'] - x['close'])) for x, y in zip(b[-15:-1], b[-14:]))
    path = sum(abs(y - x) for x, y in zip(c, c[1:]))
    efficiency = abs(c[-1] - c[0]) / path if path else 1.0
    drift = abs(c[-1] - c[0]) / width
    mid = (upper + lower) / 2
    crossings = sum((x < mid <= y) or (y < mid <= x) for x, y in zip(c, c[1:]))
    halves = (b[:n // 2], b[n // 2:])
    stability = max(abs(quantile([x[key] for x in halves[0]], q)
                        - quantile([x[key] for x in halves[1]], q)) / width
                    for key, q in (('low', .1), ('high', .9)))
    lower_touches = touches([x['low'] <= lower + .15 * width for x in b])
    upper_touches = touches([x['high'] >= upper - .15 * width for x in b])
    containment = sum(lower <= x <= upper for x in c) / n
    turnover = sum(x['close'] * x['volume'] for x in b[-86400 // seconds:])
    entry, target, stop = lower + .15 * width, upper - .15 * width, lower - .5 * atr
    cost_entry = entry * (1 + config.slippage) * (1 + config.fee)
    net_target = target * (1 - config.slippage) * (1 - config.fee)
    net_stop = stop * (1 - config.slippage) * (1 - config.fee)
    rr = (net_target - cost_entry) / (cost_entry - net_stop) if cost_entry > net_stop else 0
    checks = {
        'range width outside 3–30%': .03 <= width / mid <= .30,
        'directional drift too large': drift <= .40,
        'trend efficiency too high': efficiency <= .25,
        'range moved between halves': stability <= config.max_boundary_movement,
        'too few midpoint crossings': crossings >= 3,
        'too few independent boundary visits': min(lower_touches, upper_touches) >= 2,
        'too few closes inside range': containment >= .80,
        'latest close outside range': lower <= c[-1] <= upper,
        'reward/risk too small after costs': rr >= config.min_reward_risk and stop > 0,
        '24h turnover proxy too low': turnover >= config.min_daily_turnover,
    }
    reasons = [label for label, passed in checks.items() if not passed]
    return dict(eligible=not reasons, reasons=reasons, lower=lower, upper=upper,
                entry_ceiling=entry, target=target, stop=stop, atr=atr,
                last_close=c[-1], last_candle_start=b[-1]['start'],
                efficiency=efficiency, drift=drift, stability=stability,
                midpoint_crossings=crossings, lower_visits=lower_touches,
                upper_visits=upper_touches, containment=containment,
                daily_turnover_proxy=turnover,
                net_reward_risk=rr, net_target_return=net_target / cost_entry - 1,
                entry_signal=not reasons and lower <= c[-1] <= entry and c[-1] > c[-2],
                score=max(0, 100 * (1 - efficiency) * (1 - min(stability, 1)))
                if not reasons else 0)


def replay(bars, seconds, config=Config(), capital=10000.0):
    """Independent per-symbol paper account; signal close -> next observed open.

    Daily refits use only prior bars. Held exits never move with a refit.
    Stop wins if both exits occur in one bar. Gaps reject replay entirely.
    """
    if not math.isfinite(capital) or capital <= 0:
        raise ValueError('paper capital must be positive')
    if any(y['start'] - x['start'] != seconds for x, y in zip(bars, bars[1:])):
        return {'available': False, 'reason': 'missing candles; replay withheld'}
    cash, position, plan, day, day_equity = capital, None, None, None, capital
    peak, drawdown, cooldown, trades, curve = capital, 0.0, 0, [], []
    n = config.lookback_days * 86400 // seconds
    for i in range(n, len(bars)):
        bar, prev = bars[i], bars[i - 1]
        current_day = bar['start'] // 86400
        if day != current_day:
            day = current_day
            day_equity = cash + (position['units'] * prev['close'] if position else 0)
            plan = assess(bars[:i], seconds, config)
        # Exit before any possible entry. Never buy and sell in the same bar.
        had_position = position is not None
        if position:
            price, reason = None, None
            if bar['low'] <= position['stop']:
                price, reason = min(bar['open'], position['stop']), 'stop'
            elif bar['high'] >= position['target']:
                price, reason = position['target'], 'target'
            elif bar['start'] - position['time'] >= config.max_holding_days * 86400:
                price, reason = bar['open'], 'time_exit'
            if price is not None:
                price *= 1 - config.slippage
                proceeds = position['units'] * price * (1 - config.fee)
                cash += proceeds
                trades.append(dict(entry_time=position['time'], exit_time=bar['start'],
                                   entry=position['entry'], exit=price, units=position['units'],
                                   pnl=proceeds - position['cost'], reason=reason))
                position = None
                if reason == 'stop':
                    cooldown = (current_day + 1) * 86400
        equity_before = cash + (position['units'] * prev['close'] if position else 0)
        if (not had_position and not position and plan and plan['eligible']
                and bar['start'] >= cooldown
                and equity_before > day_equity * (1 - config.daily_loss_fraction)
                and plan['lower'] <= prev['close'] <= plan['entry_ceiling']
                and prev['close'] > bars[i - 2]['close']
                and plan['lower'] <= bar['open'] <= plan['entry_ceiling']):
            entry = bar['open'] * (1 + config.slippage)
            cost = entry * (1 + config.fee)
            risk = cost - plan['stop'] * (1 - config.slippage) * (1 - config.fee)
            reward = plan['target'] * (1 - config.slippage) * (1 - config.fee) - cost
            if risk > 0 and reward / risk >= config.min_reward_risk:
                units = min(cash * config.allocation_fraction / cost,
                            cash * config.risk_fraction / risk)
                if units > 0:
                    cash -= units * cost
                    position = dict(units=units, entry=entry, cost=units * cost,
                                    stop=plan['stop'], target=plan['target'], time=bar['start'])
                    # Entry occurs at open: its stop can trigger during this bar.
                    if bar['low'] <= position['stop']:
                        exit_price = min(bar['open'], position['stop']) * (1 - config.slippage)
                        proceeds = units * exit_price * (1 - config.fee)
                        cash += proceeds
                        trades.append(dict(entry_time=bar['start'], exit_time=bar['start'],
                                           entry=entry, exit=exit_price, units=units,
                                           pnl=proceeds - position['cost'], reason='stop'))
                        position = None
                        cooldown = (current_day + 1) * 86400
                    # No target fill on an entry bar: its timing is ambiguous.
        equity = cash + (position['units'] * bar['close'] if position else 0)
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
        curve.append({'time': bar['start'] + seconds, 'equity': equity})
    return dict(available=True, mode='historical_paper_replay', initial_capital=capital,
                ending_equity=curve[-1]['equity'] if curve else capital,
                max_drawdown=drawdown, closed_trades=len(trades), trades=trades,
                open_position=position, equity_curve=curve,
                warning='Short sample; independent symbol account; no live fills or proven edge')


def get_json(url):
    global _PUBLIC_LAST_REQUEST
    request = urllib.request.Request(url, headers={'User-Agent': 'RangeResearch/1.0'})
    for attempt in range(3):
        # One process-wide budget also covers concurrent discovery workers.
        with _PUBLIC_RATE_LOCK:
            delay = .2 - (time.monotonic() - _PUBLIC_LAST_REQUEST)
            if delay > 0:
                time.sleep(delay)
            _PUBLIC_LAST_REQUEST = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(2 ** attempt)


def fetch_snapshot(symbols, now):
    """Public Coinbase Exchange data only; no keys, no order endpoints."""
    seconds = 14400
    end = int(now) // seconds * seconds
    snapshot = dict(source='Coinbase Exchange public REST', retrieved_at=iso(now),
                    candle_seconds=seconds, products={})
    for symbol in symbols:
        product = symbol.upper() + '-USD'
        if not re.fullmatch(r'[A-Z0-9]{2,12}-USD', product):
            raise ValueError('invalid symbol')
        base = 'https://api.exchange.coinbase.com/products/' + product
        try:
            meta = get_json(base)
            if (meta.get('status') != 'online' or any(meta.get(key) is not False for key in
                    ('trading_disabled', 'cancel_only', 'post_only', 'limit_only'))):
                raise ValueError('product not verified for normal trading')
            hourly = []
            # Exchange has no native 4h interval. Aggregate ONLY four actual
            # contiguous hourly observations; missing buckets remain missing.
            for stop in (end - 280 * 3600, end):
                start = stop - 280 * 3600
                params = urllib.parse.urlencode(dict(granularity=3600, start=iso(start), end=iso(stop)))
                hourly.extend(row for row in get_json(base + '/candles?' + params)
                              if start <= row[0] < stop)
            observed = normalize(hourly, 3600, end)
            groups = {}
            for bar in observed:
                groups.setdefault(bar['start'] // seconds * seconds, []).append(bar)
            candles = []
            for stamp, group in sorted(groups.items()):
                if [x['start'] for x in group] != list(range(stamp, stamp + seconds, 3600)):
                    continue
                candles.append(dict(start=stamp, open=group[0]['open'], close=group[-1]['close'],
                                    high=max(x['high'] for x in group), low=min(x['low'] for x in group),
                                    volume=sum(x['volume'] for x in group)))
            snapshot['products'][product] = dict(candles=candles)
        except Exception as exc:
            snapshot['products'][product] = {'error': str(exc)}
    return snapshot


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def report(snapshot, config, capital):
    asof = datetime.fromisoformat(snapshot['retrieved_at'].replace('Z', '+00:00')).timestamp()
    seconds, results = snapshot['candle_seconds'], []
    for product, item in sorted(snapshot['products'].items()):
        try:
            if item.get('error'):
                raise ValueError(item['error'])
            bars = normalize(item['candles'], seconds, asof)
            results.append(dict(product=product, **assess(bars, seconds, config, asof=asof),
                                replay=replay(bars, seconds, config, capital)))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            results.append(dict(product=product, eligible=False, reasons=[str(exc)]))
    return dict(mode='research_and_paper_only', source=snapshot['source'],
                asof=snapshot['retrieved_at'], candle_seconds=seconds,
                config=asdict(config), capital_is_hypothetical=True,
                results=sorted(results, key=lambda r: r.get('score', 0), reverse=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Replay a dated real-data snapshot offline')
    parser.add_argument('--symbols', nargs='+', default=UNIVERSE)
    parser.add_argument('--lookback-days', type=int, default=7)
    parser.add_argument('--capital', type=float, default=10000, help='Hypothetical per-symbol paper capital')
    parser.add_argument('--fee-bps', type=float, default=75)
    parser.add_argument('--slippage-bps', type=float, default=10)
    parser.add_argument('--output', type=Path, default=Path('reports/range_trading/latest.json'))
    parser.add_argument('--watch-seconds', type=int, help='Repeat fresh research reports; no live/persistent fills')
    args = parser.parse_args()
    if args.watch_seconds is not None and (args.watch_seconds < 900 or args.snapshot):
        parser.error('watch needs fresh data and an interval of at least 900 seconds')
    config = Config(lookback_days=args.lookback_days, fee=args.fee_bps / 10000,
                    slippage=args.slippage_bps / 10000)
    while True:
        snapshot = json.loads(args.snapshot.read_text()) if args.snapshot else fetch_snapshot(args.symbols, time.time())
        requested = {s.upper().replace('/', '-').removesuffix('-USD') + '-USD' for s in args.symbols}
        snapshot['products'] = {p: item for p, item in snapshot['products'].items() if p in requested}
        result = report(snapshot, config, args.capital)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not args.snapshot:
            args.output.with_suffix('.source.json').write_text(json.dumps(snapshot, indent=2) + '\n')
        # Sibling temporary file + replace prevents partially written reports.
        temporary = args.output.with_suffix(args.output.suffix + '.tmp')
        temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        temporary.replace(args.output)
        for row in result['results']:
            print(row['product'], 'QUALIFIED' if row['eligible'] else 'WAIT',
                  ', '.join(row['reasons']), flush=True)
        print('Paper research report:', args.output.resolve(), flush=True)
        if not args.watch_seconds:
            break
        time.sleep(args.watch_seconds)


if __name__ == '__main__':
    main()
