"""On-demand, read-only discovery. A wide range is never an execution signal."""
from __future__ import annotations

import copy
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

from ai_day_trade.alpaca_range_paper import Client
from ai_day_trade.range_trading import Config, assess, fetch_snapshot, iso, normalize
from ai_day_trade.schwab_range_screen import ET, STOCKS, screen, session_grid
from scripts import schwab_api
from range_geometry import completed_swings, ratio
import long_range_discovery

CRYPTO_POOL = ('NEAR', 'DOT', 'BTC', 'ETH', 'SOL', 'LINK', 'AVAX', 'ADA', 'ATOM',
               'LTC', 'XLM', 'XRP', 'BCH', 'UNI', 'AAVE', 'ONDO', 'RENDER', 'FET',
               'INJ', 'ARB', 'OP', 'FIL', 'GRT')
STOCK_POOL = tuple(dict.fromkeys((*STOCKS, 'MSTR', 'MARA', 'RIOT', 'IONQ', 'ASTS',
                                'RKLB', 'OPEN', 'LCID', 'GME', 'AMC', 'SMCI', 'AXTI',
                                'COHR', 'LITE', 'FN', 'APP', 'RBLX', 'SHOP')))
REPORT_PATH = Path(__file__).resolve().parents[1] / 'reports/range_trading/DISCOVERY_LATEST.json'
QUALITY_VERSION = 7
MAX_BOUNDARY_MOVEMENT = .60
CRYPTO_DAYS = 14
STOCK_DAYS = 45
RECENT_DAYS = 7
LONG_SELECTION_RULE = 'Two-year stocks: rounded width threshold, 3 full swings, annual repeats, 60% stability, 80% overall and 50% quarterly containment, latest inside, 5/20-session liquidity; crypto unchanged'
SELECTION_RULE = 'Width and liquidity and hard range checks; >=2 full swings qualifies; stocks with exactly 1 swing need review; stock recent swings and drift rank only'



def apply_swing_requirement(row, closes):
    count, visits = completed_swings(closes, row['support'], row['resistance'])
    row.update(completed_cycles=count, alternating_boundary_visits=visits,
               qualification_version=QUALITY_VERSION)
    minimum = 1 if row['asset'] == 'stock' else 2
    if count < minimum:
        row['quality_pass'] = False
        row['warnings'] = [*row['warnings'], f'Fewer than {minimum} completed back-and-forth swings']
    return row


def apply_recent_requirement(row, bars):
    """Confirm the longer box remains active, using only recent real closes.

    Both markets require 80% recent containment. A full recent trip remains
    mandatory for crypto; stock recent trips contribute to ranking only.
    """
    closes = [x['close'] for x in bars]
    count, visits = completed_swings(closes, row['support'], row['resistance'])
    containment = sum(row['support'] <= x <= row['resistance'] for x in closes) / len(closes) if closes else 0
    passed = containment >= .8 and (row['asset'] == 'stock' or count >= 1)
    row.update(recent_range_pass=passed, recent_days=RECENT_DAYS,
               recent_completed_cycles=count, recent_containment=containment,
               recent_boundary_visits=visits)
    if row['asset'] == 'stock' and count < 1:
        row['advisories'] = [*row.get('advisories', []), 'No full swing in recent 7 days; lower ranking and wait for a fresh bounce before entry']
    if not passed:
        row['quality_pass'] = False
        reason = ('Recent 7 days need 80% of closes inside the longer range' if row['asset'] == 'stock' else
                  'Recent 7 days need at least one full swing and 80% of closes inside the longer range')
        row['warnings'] = [*row['warnings'], reason]
    return row


def passes_base(row, threshold=15):
    common = (row.get('qualification_version') == QUALITY_VERSION and
              row.get('quality_pass') is True and row.get('liquidity_pass') is True and
              isinstance(row.get('completed_cycles'), int) and
              isinstance(row.get('rounded_ratio'), int) and row['rounded_ratio'] >= threshold)
    if not common:
        return False
    if row.get('stock_mode') == 'two_year':
        annual, quarters = row.get('annual_cycles', []), row.get('quarter_containment', [])
        return (row.get('asset') == 'stock' and row.get('lookback_days') == 730 and
                len(annual) == 2 and min(annual) >= 1 and len(quarters) == 8 and min(quarters) >= .5 and
                row.get('containment', 0) >= .8 and row.get('stability', 1) <= .6 and
                row.get('support', 0) <= row.get('last_close', -1) <= row.get('resistance', -2) and
                min(row.get('volume_usd', 0), row.get('volume_usd_5', 0)) >= 100_000_000 and
                min(row.get('volume_shares', 0), row.get('volume_shares_5', 0)) >= 2_000_000)
    return row.get('recent_range_pass') is True


def qualifies(row, threshold=15):
    minimum = 3 if row.get('stock_mode') == 'two_year' else 2
    return passes_base(row, threshold) and row['completed_cycles'] >= minimum


def needs_review(row, threshold=15):
    """A one-swing short-window stock is never a qualified trade."""
    return (row.get('asset') == 'stock' and row.get('stock_mode') != 'two_year' and
            passes_base(row, threshold) and row['completed_cycles'] == 1)


def crypto_row(symbol, item, asof, paper_supported=None, days=CRYPTO_DAYS):
    if item.get('error'):
        raise ValueError('Coinbase history unavailable or market not in normal trading')
    bars = normalize(item['candles'], 14400, asof)
    measurements = assess(bars, 14400, Config(lookback_days=days, max_boundary_movement=MAX_BOUNDARY_MOVEMENT), asof=asof)
    if 'lower' not in measurements:
        raise ValueError('; '.join(measurements['reasons']))
    # No matches may be computed from a stale or incomplete requested window.
    raw, rounded = ratio(measurements['lower'], measurements['upper'])
    row = dict(symbol=symbol, asset='crypto', support=measurements['lower'],
                resistance=measurements['upper'], range_ratio=raw, rounded_ratio=rounded,
                last_close=measurements['last_close'],
                last_bar_at=iso(measurements['last_candle_start'] + 14400),
                volume_usd=measurements['daily_turnover_proxy'], volume_shares=None,
                volume_scope='Coinbase trailing 24h close × volume estimate',
                liquidity_pass=measurements['daily_turnover_proxy'] >= 1_000_000,
                quality_pass=measurements['eligible'], warnings=measurements['reasons'],
                source='Coinbase', interval='4h', lookback_days=days, paper_supported=paper_supported,
                drift=measurements['drift'], stability=measurements['stability'],
                efficiency=measurements['efficiency'], containment=measurements['containment'],
                midpoint_crossings=measurements['midpoint_crossings'],
                boundary_visits=[measurements['lower_visits'], measurements['upper_visits']],
                net_reward_risk=measurements['net_reward_risk'],
                entry_ceiling=measurements['entry_ceiling'], target=measurements['target'],
                stop_reference=measurements['stop'], execution_enabled=False)
    apply_swing_requirement(row, [x['close'] for x in bars[-days * 6:]])
    return apply_recent_requirement(row, bars[-RECENT_DAYS * 6:])


def stock_row(symbol, item, calendar, asof, days=STOCK_DAYS):
    payload = dict(source='Schwab', retrieved_at=asof, calendar=calendar, products={symbol: item})
    row = screen(payload, days, max_boundary_movement=MAX_BOUNDARY_MOVEMENT)['results'][0]
    if 'support' not in row:
        raise ValueError('; '.join(row['reasons']))
    recent = screen(payload, RECENT_DAYS)['results'][0]
    if 'average_daily_turnover_proxy' not in recent:
        raise ValueError('Recent stock liquidity unavailable: ' + '; '.join(recent['reasons']))
    raw, rounded = ratio(row['support'], row['resistance'])
    soft_reasons = {'too much directional drift', 'range width outside 1–20%'}
    hard_reasons = [x for x in row['reasons'] if not x.startswith('average daily') and x not in soft_reasons]
    width_mid = (row['resistance'] - row['support']) / ((row['resistance'] + row['support']) / 2)
    if width_mid < .01:
        hard_reasons.append('Range width below 1% of midpoint')
    advisories = ['Earnings/news not checked; fresh bounce, spread and depth required before entry']
    if row['drift'] > .4:
        advisories.append('Start-to-end movement above 40%; ranking penalty only')
    if width_mid > .2:
        advisories.append('Wide range above 20% of midpoint; review volatility and position size')
    dates = sorted(session['date'] for session in calendar
                   if datetime.fromisoformat(session['date'] + 'T' + session['close'])
                   .replace(tzinfo=ET).timestamp() <= asof)
    last_session = next(x for x in calendar if x['date'] == dates[-1])
    end = datetime.fromisoformat(last_session['date'] + 'T' + last_session['close']).replace(tzinfo=ET)
    result = dict(symbol=symbol, asset='stock', support=row['support'], resistance=row['resistance'],
                range_ratio=raw, rounded_ratio=rounded, last_close=row['regular_close'],
                last_bar_at=end.isoformat(), volume_usd=recent['average_daily_turnover_proxy'],
                volume_shares=recent['average_daily_shares'],
                volume_scope='Schwab recent 7-day average per completed session; close × volume estimate',
                liquidity_pass=recent['average_daily_shares'] >= 2_000_000 and
                recent['average_daily_turnover_proxy'] >= 100_000_000,
                quality_pass=not hard_reasons, warnings=hard_reasons, advisories=advisories,
                source='Schwab', interval='30m regular session', stock_mode='45_day', lookback_days=days, paper_supported=None,
                drift=row['drift'], stability=row['stability'], efficiency=row['efficiency'],
                containment=row['containment'], midpoint_crossings=row['midpoint_crossings'],
                boundary_visits=row['boundary_visits'],
                entry_ceiling=row['entry_ceiling'], target=row['target'],
                stop_reference=row['stop_reference'], execution_enabled=False)
    expected = set.union(*session_grid(calendar, asof, days).values())
    closes = [float(x['close']) for x in sorted(item['candles'], key=lambda x: x['datetime'])
              if x['datetime'] / 1000 in expected]
    apply_swing_requirement(result, closes)
    recent_expected = set.union(*session_grid(calendar, asof, RECENT_DAYS).values())
    recent_bars = [x for x in sorted(item['candles'], key=lambda x: x['datetime'])
                   if x['datetime'] / 1000 in recent_expected]
    apply_recent_requirement(result, recent_bars)
    # Ranking is an ordering aid, not a probability or expected-return estimate.
    result['ranking_score'] = round(20 * (result['recent_completed_cycles'] >= 1) +
        20 * result['recent_containment'] + 20 * (1 - min(result['efficiency'], 1)) +
        20 * (1 - min(result['stability'], 1)) + 20 * (1 - min(result['drift'], 1)) -
        10 * (width_mid > .2), 2)
    return result


class Discovery:
    def __init__(self, path=REPORT_PATH):
        self.path, self.lock = path, threading.Lock()
        self.chart_cache = {}
        self.state = dict(status='idle', rows=[], omitted=[], checked=0, total=0,
                          lookback_days={'crypto': CRYPTO_DAYS, 'stocks': STOCK_DAYS}, recent_days=RECENT_DAYS, threshold=15, market='both', started_at=None,
                          completed_at=None, rule=SELECTION_RULE, stock_mode='45_day',
                          crypto_pool=list(CRYPTO_POOL), stock_pool=list(STOCK_POOL))
        try:
            saved = json.loads(path.read_text())
            if (isinstance(saved, dict) and saved.get('status') in ('complete', 'failed')
                    and isinstance(saved.get('rows'), list)):
                self.state.update(saved)
        except (OSError, ValueError, TypeError):
            pass
        self.state['rule'] = LONG_SELECTION_RULE if self.state.get('stock_mode') == 'two_year' else SELECTION_RULE
        self.state['lookback_days'] = {'crypto': CRYPTO_DAYS, 'stocks': 730 if self.state.get('stock_mode') == 'two_year' else STOCK_DAYS}
        self.state['recent_days'] = RECENT_DAYS

    def get(self):
        with self.lock:
            result = copy.deepcopy(self.state)
        result['candidates'] = [r for r in result['rows'] if qualifies(r, result['threshold'])]
        result['needs_review'] = sorted([r for r in result['rows'] if needs_review(r, result['threshold'])],
                                        key=lambda r: r.get('ranking_score', 0), reverse=True)
        result['candidates'].sort(key=lambda r: r.get('ranking_score', 0), reverse=True)
        result['disqualified'] = [r for r in result['rows']
                                  if r.get('rounded_ratio', 0) >= result['threshold']
                                  and not qualifies(r, result['threshold']) and not needs_review(r, result['threshold'])]
        return result

    def chart(self, symbol, asset, scan_id=None):
        """Retrieve real candles for this dated snapshot, never substitute dates.

        Daily long-mode bars reuse the audited source. Other intervals request
        historical observations ending at the original scan cutoff and must
        reproduce the displayed boundaries before they may be charted.
        """
        with self.lock:
            current_scan = self.state.get('started_at')
            if scan_id and scan_id != current_scan:
                raise ValueError('Discovery scan changed; select the snapshot again')
            row = next((r for r in self.state['rows'] if r['symbol'] == symbol and r['asset'] == asset), None)
            if row is None or not current_scan:
                raise ValueError('Symbol is unavailable in the saved discovery scan')
            row = copy.deepcopy(row)
            key = (current_scan, asset, symbol)
            if key in self.chart_cache:
                return copy.deepcopy(self.chart_cache[key])
        asof = datetime.fromisoformat(current_scan.replace('Z', '+00:00')).timestamp()
        days = row['lookback_days']
        if asset == 'crypto':
            source = fetch_snapshot([symbol], asof)
            item = source['products'][symbol + '-USD']
            measured = crypto_row(symbol, item, asof, days=days)
            observed = normalize(item['candles'], 14400, asof)[-days * 6:]
            bars = [dict(t=iso(b['start']), o=b['open'], h=b['high'], l=b['low'], c=b['close'], v=b['volume']) for b in observed]
        elif row.get('stock_mode') == 'two_year':
            source = json.loads(long_range_discovery.SOURCE_PATH.read_text())
            source_asof = datetime.fromisoformat(source['retrieved_at']).timestamp()
            if abs(source_asof - asof) > 10:
                raise ValueError('Daily chart source does not match this scan; refresh discovery')
            observed = source['products'].get(symbol, [])
            measured = long_range_discovery.stock_row(symbol, observed, source['calendar'], source_asof, QUALITY_VERSION)
            expected = long_range_discovery.expected_sessions(source['calendar'], source_asof)
            bars = [dict(t=b['t'][:10], **{k:b[k] for k in ('o','h','l','c','v')})
                    for b in sorted(observed, key=lambda b:b['t']) if b['t'][:10] in expected]
        else:
            today = datetime.fromtimestamp(asof, ET)
            calendar = Client().request('/v2/calendar?start=' + (today - timedelta(days=days + 5)).date().isoformat()
                                        + '&end=' + today.date().isoformat())
            schwab_api.load_env(schwab_api.REPO_ROOT / '.env')
            item = schwab_api.api('/marketdata/v1/pricehistory', dict(symbol=symbol, periodType='day',
                startDate=int((asof - (days + 1) * 86400) * 1000), endDate=int(asof * 1000),
                frequencyType='minute', frequency=30, needExtendedHoursData='false'))
            measured = stock_row(symbol, item, calendar, asof, days=days)
            expected = set.union(*session_grid(calendar, asof, days).values())
            bars = [dict(t=iso(b['datetime']/1000), o=b['open'], h=b['high'], l=b['low'], c=b['close'], v=b['volume'])
                    for b in sorted(item['candles'], key=lambda b:b['datetime']) if b['datetime']/1000 in expected]
        if any(measured[k] != row[k] for k in ('support', 'resistance', 'last_close')):
            raise ValueError('Provider history changed since this snapshot; refresh discovery before charting')
        result = dict(symbol=symbol, asset_type=asset, bars=bars, feed=row['source'],
            feed_note=f"{row['source']} · {row['interval']} · saved discovery snapshot", levels=[],
            discovery={k:row[k] for k in ('support','resistance','lookback_days','interval','last_bar_at','range_ratio')},
            scan_started_at=current_scan)
        with self.lock:
            if self.state.get('started_at') != current_scan:
                raise ValueError('Discovery scan changed; select the snapshot again')
            self.chart_cache[key] = copy.deepcopy(result)
        return result

    def start(self, market='both', threshold=15, stock_mode='45_day'):
        if stock_mode not in ('45_day', 'two_year'):
            raise ValueError('stock_mode must be 45_day or two_year')
        if market not in ('both', 'crypto', 'stocks'):
            raise ValueError('market must be both, crypto, or stocks')
        if isinstance(threshold, bool) or not isinstance(threshold, int) or not 1 <= threshold <= 100:
            raise ValueError('rounded minimum must be an integer from 1 to 100')
        with self.lock:
            if self.state['status'] == 'running':
                return copy.deepcopy(self.state)
            stock_pool = long_range_discovery.stock_pool(STOCK_POOL) if stock_mode == 'two_year' else STOCK_POOL
            self.chart_cache.clear()
            self.state.update(status='running', rows=[], omitted=[], checked=0,
                              stock_mode=stock_mode, stock_pool=list(stock_pool),
                              rule=LONG_SELECTION_RULE if stock_mode == 'two_year' else SELECTION_RULE,
                              lookback_days={'crypto': CRYPTO_DAYS, 'stocks': 730 if stock_mode == 'two_year' else STOCK_DAYS},
                              total=(len(CRYPTO_POOL) if market != 'stocks' else 0) +
                              (len(stock_pool) if market != 'crypto' else 0),
                              threshold=threshold, market=market, started_at=iso(time.time()),
                              completed_at=None)
            result = copy.deepcopy(self.state)
            threading.Thread(target=self._run, args=(market,), daemon=True).start()
            return result

    def _record(self, symbol, asset, row=None, error=None):
        with self.lock:
            self.state['checked'] += 1
            if error:
                self.state['omitted'].append(dict(symbol=symbol, asset=asset, reason=error))
            elif row:
                self.state['rows'].append(row)
                self.state['rows'].sort(key=lambda r: r['range_ratio'], reverse=True)

    def _run(self, market):
        now = time.time()
        tasks = []
        stock_mode = self.state.get('stock_mode', '45_day')
        try:
            paper_symbols, calendar = None, None
            try:
                client = Client()
                assets = client.request('/v2/assets?asset_class=crypto&status=active')
                paper_symbols = {x['symbol'] for x in assets if x.get('tradable')}
                today = datetime.fromtimestamp(now, ET)
                if market != 'crypto' and stock_mode == '45_day':
                    calendar = client.request('/v2/calendar?start=' + (today - timedelta(days=STOCK_DAYS + 5)).date().isoformat()
                                              + '&end=' + today.date().isoformat())
            except Exception:
                pass  # Public crypto research remains available without Alpaca.

            def crypto(symbol):
                snapshot = fetch_snapshot([symbol], now)
                return crypto_row(symbol, snapshot['products'][symbol + '-USD'], now,
                                  symbol + '/USD' in paper_symbols if paper_symbols is not None else None)

            def stock(symbol):
                item = schwab_api.api('/marketdata/v1/pricehistory', dict(symbol=symbol, periodType='day',
                    startDate=int((now - (STOCK_DAYS + 1) * 86400) * 1000), endDate=int(now * 1000),
                    frequencyType='minute', frequency=30, needExtendedHoursData='false'))
                return stock_row(symbol, item, calendar, now)

            stock_error = None
            if market != 'crypto' and stock_mode == '45_day':
                if not calendar:
                    stock_error = 'Trading-session calendar unavailable'
                else:
                    try:
                        schwab_api.load_env(schwab_api.REPO_ROOT / '.env')
                        schwab_api.access_token()  # Refresh once before concurrent read requests.
                    except (Exception, SystemExit):
                        stock_error = 'Schwab authorization unavailable; reconnect before stock discovery'
            if market != 'stocks':
                tasks.extend((symbol, 'crypto', crypto) for symbol in CRYPTO_POOL)
            if market != 'crypto' and stock_mode == 'two_year':
                symbols = long_range_discovery.stock_pool(STOCK_POOL)
                try:
                    source = long_range_discovery.fetch_snapshot(symbols, now)
                except Exception:
                    source = None
                for symbol in symbols:
                    if source is None or symbol in source.get('batch_errors', []):
                        self._record(symbol, 'stock', error='Two-year SIP history/calendar unavailable; no volume fallback')
                        continue
                    try:
                        self._record(symbol, 'stock', row=long_range_discovery.stock_row(
                            symbol, source['products'].get(symbol, []), source['calendar'], now, QUALITY_VERSION))
                    except (ValueError, TypeError, KeyError) as exc:
                        self._record(symbol, 'stock', error=str(exc))
            if market != 'crypto' and stock_mode == '45_day':
                for symbol in STOCK_POOL:
                    if stock_error:
                        self._record(symbol, 'stock', error=stock_error)
                    else:
                        tasks.append((symbol, 'stock', stock))
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(fn, symbol): (symbol, asset) for symbol, asset, fn in tasks}
                for future in as_completed(futures):
                    symbol, asset = futures[future]
                    try:
                        self._record(symbol, asset, row=future.result())
                    except ValueError as exc:
                        self._record(symbol, asset, error=str(exc))
                    except (Exception, SystemExit):
                        self._record(symbol, asset, error='Market history unavailable, stale, incomplete, or invalid')
        except Exception:
            with self.lock:
                self.state['omitted'].append(dict(symbol='SCAN', asset='all', reason='Discovery interrupted'))
        finally:
            with self.lock:
                self.state['status'] = 'complete' if self.state['rows'] else 'failed'
                self.state['completed_at'] = iso(time.time())
                saved = copy.deepcopy(self.state)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                temp = self.path.with_suffix('.tmp')
                temp.write_text(json.dumps(saved, indent=2, allow_nan=False) + '\n')
                temp.replace(self.path)
            except OSError:
                pass  # In-memory result remains usable if disk persistence fails.


DISCOVERY = Discovery()
