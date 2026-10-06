"""Combine sanitized Schwab account snapshots without inventing missing values."""
from decimal import Decimal, InvalidOperation


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def total(rows, field):
    values = [number(row.get(field)) for row in rows]
    return float(sum(values)) if all(value is not None for value in values) else None


def combine(snapshots):
    if not snapshots or any(not snapshot.get('ok') for snapshot in snapshots):
        raise ValueError('Every linked account must load before combining holdings')
    groups = {}
    accounts = []
    for snapshot in snapshots:
        accounts.append({'label': snapshot['account'], 'account_type': snapshot.get('account_type'),
                         'balances': snapshot.get('balances', {})})
        for position in snapshot['positions']:
            symbol = position['symbol']
            groups.setdefault(symbol, []).append({**position, 'account': snapshot['account']})
    positions = []
    for symbol, rows in sorted(groups.items()):
        kinds = {row.get('asset_type') for row in rows}
        if len(kinds) != 1:
            raise ValueError('Cannot combine different security types under one symbol')
        qty = total(rows, 'quantity')
        weights = [number(row.get('quantity')) for row in rows]
        costs = [number(row.get('average_price')) for row in rows]
        # A missing cost remains missing. Long and short costs cannot be netted
        # into a meaningful long-position average; keep their account details.
        average = None
        if qty is not None and qty > 0 and all(q is not None and q >= 0 for q in weights) and all(number(row.get('short_quantity')) == 0 for row in rows) and all(c is not None and c >= 0 for c in costs):
            average = float(sum(q * c for q, c in zip(weights, costs)) / sum(weights))
        positions.append({'symbol': symbol, 'asset_type': rows[0].get('asset_type'),
                          **{field: total(rows, field) for field in ['quantity', 'long_quantity', 'short_quantity', 'market_value', 'open_profit_loss', 'current_day_profit_loss']},
                          'average_price': average, 'account_positions': rows})
    return {'ok': True, 'combined': True, 'account': 'All linked accounts',
            'accounts': accounts, 'account_count': len(accounts), 'positions': positions,
            'balances': {field: total([s.get('balances', {}) for s in snapshots], field) for field in ['liquidation_value', 'cash_balance']},
            'as_of': max(s['as_of'] for s in snapshots)}
