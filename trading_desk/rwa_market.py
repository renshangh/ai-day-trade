"""RWA research rankings from reported CoinGecko USD market observations."""
import json
import math
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE = 'https://www.coingecko.com/en/categories/real-world-assets-rwa'
COINBASE_PRODUCTS_API = 'https://api.exchange.coinbase.com/products'
API = ('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd'
       '&category=real-world-assets-rwa&order=market_cap_desc&per_page=100&page=1')
# A reviewed research pool distinguishes tokens from restricted funds and stock
# wrappers. Category membership alone is not proof of token-holder cash flows.
ROLES = {
    'chainlink': 'Oracle / interoperability',
    'stellar': 'Tokenization / settlement network',
    'tether-gold': 'Gold-backed asset',
    'quant-network': 'Interoperability infrastructure',
    'ondo-finance': 'Tokenization protocol / governance',
    'pax-gold': 'Gold-backed asset',
    'algorand': 'Tokenization / settlement network',
    'injective-protocol': 'Onchain financial markets',
    'xdce-crowd-sale': 'Trade finance / settlement network',
    'syrup': 'Onchain lending protocol',
    'reserve-rights-token': 'Reserve ecosystem / governance',
    'plume': 'RWA network',
}
MIN_CAP = 100_000_000
MIN_VOLUME = 10_000_000
_lock = threading.Lock()
_cached = None
_cached_at = 0


def positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def active_products(products):
    if not isinstance(products, list):
        raise ValueError('Coinbase did not return a product list')
    active = {}
    for product in products:
        if not isinstance(product, dict):
            continue
        symbol, quote = product.get('base_currency'), product.get('quote_currency')
        if not isinstance(symbol, str) or quote not in ('USD', 'USDC'):
            continue
        if product.get('id') != f'{symbol}-{quote}' or product.get('status') != 'online':
            continue
        # Missing status flags cannot stand in for verified normal trading.
        if not all(product.get(flag) is False for flag in
                   ('trading_disabled', 'cancel_only', 'post_only', 'limit_only', 'auction_mode')):
            continue
        if symbol not in active or quote == 'USD':
            active[symbol] = product['id']
    return active


def build(rows, products):
    if not isinstance(rows, list):
        raise ValueError('CoinGecko did not return a market list')
    tradable = active_products(products)
    coins = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        coin_id = row.get('id')
        cap, volume = row.get('market_cap'), row.get('total_volume')
        if coin_id not in ROLES or coin_id in seen:
            continue
        if not positive(cap) or not positive(volume) or cap < MIN_CAP or volume < MIN_VOLUME:
            continue
        # Missing source timestamps cannot silently become current observations.
        stamp = row.get('last_updated')
        try:
            observed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if observed.tzinfo is None:
                continue
        except (AttributeError, TypeError, ValueError):
            continue
        if not isinstance(row.get('symbol'), str) or not row['symbol'].strip() or not isinstance(row.get('name'), str):
            continue
        symbol = row['symbol'].upper()
        if symbol not in tradable:
            continue
        seen.add(coin_id)
        coins.append({'id': coin_id, 'symbol': row['symbol'].upper(), 'name': row['name'],
                      'role': ROLES[coin_id], 'market_cap': cap, 'volume_24h': volume,
                      'price': row.get('current_price') if positive(row.get('current_price')) else None,
                      'updated_at': stamp, 'coinbase_product': tradable[symbol], 'url': f'https://www.coingecko.com/en/coins/{"ondo" if coin_id == "ondo-finance" else coin_id}'})
    for field, rank in [('market_cap', 'cap_rank'), ('volume_24h', 'volume_rank')]:
        for index, coin in enumerate(sorted(coins, key=lambda c: (-c[field], c['id'])), 1):
            coin[rank] = index
    coins.sort(key=lambda c: (c['cap_rank'] + c['volume_rank'], c['cap_rank'], c['id']))
    checked_at = datetime.now(timezone.utc).isoformat()
    return {'coinbase_source': COINBASE_PRODUCTS_API, 'coinbase_checked_at': checked_at, 'coins': coins[:10], 'eligible_count': len(coins), 'source': SOURCE,
            'fetched_at': datetime.now(timezone.utc).isoformat(), 'stale': False}


def fetch_market():
    request = urllib.request.Request(API, headers={'Accept': 'application/json', 'User-Agent': 'TradingDesk/1.0'})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)


def fetch_coinbase_products():
    request = urllib.request.Request(COINBASE_PRODUCTS_API, headers={'Accept': 'application/json', 'User-Agent': 'TradingDesk/1.0'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def get_market(force=False, fetch=fetch_market):
    global _cached, _cached_at
    with _lock:
        # Briefly cache failed refreshes too, so opening both desk surfaces
        # during a provider outage does not repeatedly hit the upstream API.
        ttl = 30 if _cached and _cached.get('stale') else 300
        if _cached is not None and not force and time.monotonic() - _cached_at < ttl:
            return _cached
        products = None
        try:
            products = fetch_coinbase_products()
            active_products(products)
            result = build(fetch(), products)
            if not result['coins']:
                raise ValueError('No reviewed tokens have usable market cap and volume above the screen thresholds')
            _cached, _cached_at = result, time.monotonic()
            return result
        except Exception:
            # This dated research snapshot is never a quote or a strategy bar.
            fallback = _cached
            if fallback is None:
                try:
                    fallback = json.loads(Path(__file__).with_name('rwa_snapshot.json').read_text())
                except (OSError, ValueError):
                    fallback = {'coins': [], 'source': SOURCE, 'fetched_at': None}
            if products is None:
                result = {'coins': [], 'eligible_count': 0, 'source': SOURCE,
                          'coinbase_checked_at': None, 'fetched_at': None, 'stale': True,
                          'warning': 'Coinbase tradability could not be verified. The token list is withheld until verification succeeds.'}
            else:
                try:
                    rows = [{'id': c['id'], 'symbol': c['symbol'], 'name': c['name'],
                             'market_cap': c['market_cap'], 'total_volume': c['volume_24h'],
                             'current_price': c.get('price'), 'last_updated': c['updated_at']}
                            for c in fallback.get('coins', [])]
                    result = build(rows, products)
                    result.update(fetched_at=fallback.get('fetched_at'), stale=True,
                                  warning='Market refresh unavailable. Showing dated market observations for currently verified Coinbase markets.')
                except (ValueError, TypeError, KeyError):
                    result = {'coins': [], 'eligible_count': 0, 'source': SOURCE, 'fetched_at': None,
                              'coinbase_checked_at': None, 'stale': True,
                              'warning': 'Coinbase tradability could not be verified. The token list is withheld until verification succeeds.'}
            _cached, _cached_at = result, time.monotonic()
            return result
