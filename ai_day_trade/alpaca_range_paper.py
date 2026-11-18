"""Alpaca-only crypto range pilot. Hosts are pinned to paper and market data.

Stops are monitored in software every cycle; keep the runner online. No live
endpoint, crypto bracket, shorting, averaging down, or automatic POST retry.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import shlex
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

from .range_trading import Config, UNIVERSE, assess, iso, normalize, report

ROOT = Path(__file__).resolve().parents[1]
PAPER = 'https://paper-api.alpaca.markets'
DATA = 'https://data.alpaca.markets'
TERMINAL = {'filled', 'canceled', 'expired', 'rejected'}


def credentials():
    for line in (ROOT / '.env').read_text().splitlines() if (ROOT / '.env').exists() else []:
        key, sep, value = line.partition('=')
        if sep and key.strip() in ('ALPACA_API_KEY', 'ALPACA_API_SECRET', 'ALPACA_IS_PAPER'):
            parts = shlex.split(value, comments=True)
            if parts:
                os.environ.setdefault(key.strip(), parts[0])
    if os.environ.get('ALPACA_IS_PAPER', '').lower() != 'true':
        raise ValueError('ALPACA_IS_PAPER must be true')
    if not all(os.environ.get(k) for k in ('ALPACA_API_KEY', 'ALPACA_API_SECRET')):
        raise ValueError('Alpaca paper credentials are missing')
    return {'APCA-API-KEY-ID': os.environ['ALPACA_API_KEY'],
            'APCA-API-SECRET-KEY': os.environ['ALPACA_API_SECRET']}


class Client:
    def __init__(self):
        self.headers = credentials()

    def request(self, path, *, data=False, body=None):
        if not path.startswith('/') or '://' in path:
            raise ValueError('relative API path required')
        if body is not None and (data or path != '/v2/orders'):
            raise ValueError('only paper orders may be submitted')
        req = urllib.request.Request((DATA if data else PAPER) + path,
                                     headers={**self.headers, 'Content-Type': 'application/json'},
                                     data=json.dumps(body).encode() if body is not None else None)
        # No redirects: credentials must never follow a changed host.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with urllib.request.build_opener(NoRedirect).open(req, timeout=20) as response:
            return json.load(response)


def snapshot(client, symbols, now):
    assets = client.request('/v2/assets?asset_class=crypto&status=active')
    allowed = {x['symbol']: x for x in assets if x.get('tradable') and x['symbol'].endswith('/USD')}
    result = dict(source='Alpaca US crypto historical bars', retrieved_at=iso(now),
                  candle_seconds=14400, products={})
    for symbol in symbols:
        pair = symbol.upper() + '/USD'
        if pair not in allowed:
            result['products'][pair] = {'error': 'not tradable on Alpaca paper'}
            continue
        rows, token, seen = [], None, set()
        while True:
            params = dict(symbols=pair, timeframe='4Hour', start=iso(now - 45 * 86400),
                          end=iso(now), limit=10000, sort='asc')
            if token:
                params['page_token'] = token
            page = client.request('/v1beta3/crypto/us/bars?' + urllib.parse.urlencode(params), data=True)
            rows.extend(page.get('bars', {}).get(pair, []))
            token = page.get('next_page_token')
            if not token:
                break
            if token in seen:
                raise ValueError('repeated Alpaca pagination token')
            seen.add(token)
        result['products'][pair] = {'candles': [dict(
            start=int(datetime.fromisoformat(x['t'].replace('Z', '+00:00')).timestamp()),
            open=x['o'], high=x['h'], low=x['l'], close=x['c'], volume=x['v']) for x in rows]}
    return result, allowed


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2, allow_nan=False) + '\n')
    os.chmod(temp, 0o600)
    temp.replace(path)


def rounded(value, increment):
    inc = Decimal(str(increment))
    if not inc.is_finite() or inc <= 0 or not math.isfinite(value) or value < 0:
        raise ValueError('invalid order precision or amount')
    return format((Decimal(str(value)) / inc).to_integral_value(rounding=ROUND_DOWN) * inc, 'f')


def quote(client, pair, now):
    q = client.request('/v1beta3/crypto/us/latest/quotes?' +
                       urllib.parse.urlencode({'symbols': pair}), data=True)['quotes'][pair]
    timestamp = datetime.fromisoformat(q['t'].replace('Z', '+00:00')).timestamp()
    bid, ask = float(q['bp']), float(q['ap'])
    if not all(math.isfinite(x) for x in (bid, ask)) or not 0 < bid <= ask:
        raise ValueError('invalid bid/ask')
    if not -5 <= now - timestamp <= 60:
        raise ValueError('quote is stale or future dated')
    return bid, ask


def entry_liquidity(client, pair, now, notional):
    """Require two-sided observed depth, not just a quoted price."""
    book = client.request('/v1beta3/crypto/us/latest/orderbooks?' +
                          urllib.parse.urlencode({'symbols': pair}), data=True)['orderbooks'][pair]
    timestamp = datetime.fromisoformat(book['t'].replace('Z', '+00:00')).timestamp()
    if not -5 <= now - timestamp <= 60:
        return False
    asks, bids = book.get('a', []), book.get('b', [])
    if not asks or not bids:
        return False
    for level in asks + bids:
        if not all(math.isfinite(float(level[k])) and float(level[k]) > 0 for k in ('p', 's')):
            return False
    ask, bid = min(float(x['p']) for x in asks), max(float(x['p']) for x in bids)
    if not 0 < bid <= ask or (ask - bid) / ask > .001:
        return False
    buy_depth = sum(float(x['p']) * float(x['s']) for x in asks if float(x['p']) <= ask * 1.001)
    sell_depth = sum(float(x['p']) * float(x['s']) for x in bids if float(x['p']) >= bid * .999)
    return min(buy_depth, sell_depth) >= max(5000, notional * 10)


def reconcile(client, state):
    pending = state.get('pending')
    if not pending:
        return
    # An ambiguous POST is looked up by its stable ID, never blindly retried.
    order = client.request('/v2/orders:by_client_order_id?' + urllib.parse.urlencode(
        {'client_order_id': pending['client_order_id']}))
    if order['status'] not in TERMINAL:
        return
    qty, price = float(order.get('filled_qty') or 0), float(order.get('filled_avg_price') or 0)
    if qty:
        if pending['side'] == 'buy':
            positions = client.request('/v2/positions')
            position = next((x for x in positions if x['symbol'].replace('/', '') ==
                             pending['symbol'].replace('/', '')), None)
            if position is None:
                raise ValueError('filled buy not yet visible in paper positions')
            # Crypto buy fees can be deducted in coins. Track broker net units.
            net_qty = min(qty, float(position['qty']))
            state['positions'][pending['symbol']] = dict(
                **pending['plan'], qty=net_qty, entry=price, entry_time=pending['created_at'])
            state['cash'] -= qty * price
        else:
            holding = state['positions'][pending['symbol']]
            state['cash'] += qty * price * (1 - state['fee'])
            holding['qty'] -= qty
            if holding['qty'] < max(1e-10, float(pending.get('min_order_size', 0))):
                state.setdefault('dust', {})[pending['symbol']] = max(0, holding['qty'])
                del state['positions'][pending['symbol']]
            if pending.get('reason') == 'stop':
                state['cooldown'][pending['symbol']] = (int(pending['created_at']) // 86400 + 1) * 86400
    state['journal'].append(dict(**pending, status=order['status'], filled_qty=qty, filled_avg_price=price))
    state['pending'] = None


def submit(client, state, path, pair, side, qty, now, *, plan=None, reason=None, candle=None,
           min_order_size=None):
    key = f'{pair}:{side}:{candle if candle is not None else now}'
    client_id = 'range-paper-' + hashlib.sha256(key.encode()).hexdigest()[:30]
    state['pending'] = dict(client_order_id=client_id, symbol=pair, side=side, qty=qty,
                            created_at=now, plan=plan, reason=reason, min_order_size=min_order_size)
    # Write intent before sending: crashes/timeouts cannot duplicate submissions.
    if candle is not None:
        state['last_signal'][pair] = candle
    save(path, state)
    client.request('/v2/orders', body=dict(symbol=pair, qty=qty, side=side,
                                          type='market', time_in_force='ioc', client_order_id=client_id))


def cycle(client, state, path, candidates, assets, config, now):
    account = client.request('/v2/account')
    if account.get('status') != 'ACTIVE' or account.get('trading_blocked') or account.get('account_blocked'):
        raise ValueError('paper account is blocked or inactive')
    reconcile(client, state)
    save(path, state)
    if state.get('pending'):
        return 'waiting for paper order reconciliation'
    broker_positions = {x['symbol'].replace('/', ''): x for x in client.request('/v2/positions')}
    open_orders = client.request('/v2/orders?status=open&limit=500')
    occupied = {x['symbol'].replace('/', '') for x in open_orders}
    marked = state['cash']
    for pair, holding in list(state['positions'].items()):
        p = broker_positions.get(pair.replace('/', ''))
        if not p:
            raise ValueError('tracked paper position missing at broker; reconcile manually')
        available = min(holding['qty'], float(p.get('qty_available', p['qty'])))
        bid, ask = quote(client, pair, now)
        marked += available * bid * (1 - config.fee)
        reason = ('stop' if bid <= holding['stop'] else 'target' if bid >= holding['target']
                  else 'time_exit' if now - holding['entry_time'] >= config.max_holding_days * 86400 else None)
        if reason and pair.replace('/', '') not in occupied:
            qty = rounded(available, assets[pair]['min_trade_increment'])
            if Decimal(qty) < Decimal(assets[pair]['min_order_size']):
                raise ValueError('position below minimum exit size; reconcile paper dust')
            submit(client, state, path, pair, 'sell', qty, now, reason=reason,
                   min_order_size=assets[pair]['min_order_size'])
            return f'{pair}: paper {reason} submitted'
    day = int(now) // 86400
    if state.get('day') != day:
        state.update(day=day, day_equity=marked)
    if marked <= state['day_equity'] - state['capital'] * config.daily_loss_fraction:
        state['halt_day'] = day
    save(path, state)
    if state.get('halt_day') == day or len(state['positions']) >= 2:
        return 'new entries paused by risk limit'
    spendable = min(state['cash'], float(account['cash']), float(account['non_marginable_buying_power']))
    if not math.isfinite(spendable) or spendable <= 0:
        return 'no paper cash available'
    for row in candidates['results']:
        pair = row['product']
        if not row.get('entry_signal') or pair in state['positions']:
            continue
        if pair.replace('/', '') in broker_positions or pair.replace('/', '') in occupied:
            continue  # Never adopt or interfere with another strategy's holding.
        candle = row['last_candle_start']
        if state['last_signal'].get(pair) == candle or now < state['cooldown'].get(pair, 0):
            continue
        bid, ask = quote(client, pair, now)
        if (ask - bid) / ask > .001 or not row['lower'] <= ask <= row['entry_ceiling']:
            continue
        risk = ask * (1 + config.fee + config.slippage) - row['stop'] * (1 - config.fee - config.slippage)
        reward = row['target'] * (1 - config.fee - config.slippage) - ask * (1 + config.fee + config.slippage)
        if risk <= 0 or reward / risk < config.min_reward_risk:
            continue
        units = min(state['capital'] * config.risk_fraction / risk,
                    state['capital'] * config.allocation_fraction / ask,
                    spendable / (ask * (1 + config.fee + config.slippage)))
        qty = rounded(units, assets[pair]['min_trade_increment'])
        if Decimal(qty) < Decimal(assets[pair]['min_order_size']):
            continue
        if not entry_liquidity(client, pair, time.time(), float(qty) * ask):
            continue
        submit(client, state, path, pair, 'buy', qty, now, candle=candle,
               plan={k: row[k] for k in ('stop', 'target', 'lower', 'upper')})
        return f'{pair}: paper entry submitted'
    return 'waiting for a qualified range entry'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+', default=UNIVERSE)
    parser.add_argument('--lookback-days', type=int, default=7)
    parser.add_argument('--capital', type=float, default=1000, help='Dedicated hypothetical paper sleeve')
    parser.add_argument('--execute-paper', action='store_true', help='Enable Alpaca paper orders')
    parser.add_argument('--cycles', type=int, default=1, help='0 runs continuously')
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--state', type=Path, default=ROOT / 'trading_records/range_paper_state.json')
    args = parser.parse_args()
    if args.interval < 10 or args.cycles < 0 or not math.isfinite(args.capital) or args.capital <= 0:
        parser.error('invalid interval, cycle count, or capital')
    client, config = Client(), Config(lookback_days=args.lookback_days, fee=.0025)
    folder = ROOT / 'reports/range_trading'
    folder.mkdir(parents=True, exist_ok=True)
    args.state.parent.mkdir(parents=True, exist_ok=True)
    lock = args.state.with_suffix('.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = json.loads(args.state.read_text()) if args.state.exists() else dict(
        capital=args.capital, cash=args.capital, fee=config.fee, positions={},
        pending=None, last_signal={}, cooldown={}, journal=[])
    if state['capital'] != args.capital or state['fee'] != config.fee:
        raise ValueError('existing paper ledger budget or fees differ')
    count, refreshed, candidates, assets = 0, 0, None, None
    while args.cycles == 0 or count < args.cycles:
        now = time.time()
        # Price/exit checks run every cycle; history refreshes only every 15m.
        if candidates is None or now - refreshed >= 900:
            snap, assets = snapshot(client, args.symbols, now)
            candidates = report(snap, config, args.capital)
            save(folder / 'ALPACA_LATEST_SOURCE.json', snap)
            save(folder / 'ALPACA_LATEST.json', candidates)
            refreshed = now
        if args.execute_paper:
            print(cycle(client, state, args.state, candidates, assets, config, now), flush=True)
        else:
            for row in candidates['results']:
                print(row['product'], 'QUALIFIED' if row['eligible'] else 'WAIT',
                      ', '.join(row['reasons']), flush=True)
        count += 1
        if args.cycles == 0 or count < args.cycles:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
