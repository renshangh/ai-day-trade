"""Read-only discretionary BTC review and uncapped 12-hour model action audit.

This dashboard view is not imported by the live worker. It cannot evaluate new
entries, alter frozen rules, create benchmark fills, or submit orders.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sqlite3
import time
from pathlib import Path

from trading_desk.btc_data import iso, read
from trading_desk.btc_live import LIVE, MODELS
from trading_desk.ibit_hours import Calendar, HOME, epoch, signal_hours

REVIEW = Path(__file__).with_suffix('.json')
WINDOW = 12 * 3600
COST_PER_SIDE = .0002  # Reporting only: original normalized 1-BTC benchmark.


def action(event):
    fraction = event.get('fraction')
    return event.get('type') == 'entry' or (
        type(fraction) in (int, float) and math.isfinite(fraction) and 0 < fraction <= 1)


def grouped(rows):
    """Group identical model actions, retaining every original proposal/event ID."""
    found = {}
    for row in rows:
        key = json.dumps({k: v for k, v in row.items() if k not in ('model', 'event_id')}, sort_keys=True)
        if key not in found:
            found[key] = dict(copy.deepcopy(row), models=[], event_ids=[])
            found[key].pop('model', None)
            found[key].pop('event_id', None)
        found[key]['models'].append(row['model'])
        found[key]['event_ids'].append(row['event_id'])
    return list(found.values())


def history(state, *, now=None, root=LIVE, calendar_root=HOME):
    now = time.time() if now is None else now
    start = now - WINDOW
    result = dict(start=iso(start), end=iso(now), basis='Actual availability: later of detection and completed reference minute',
                  status='unavailable', error=None, actions=None, counts=None, recent_before_window=[],
                  net_by_model=None, orders_enabled=False, benchmark_note='Initial 1 BTC per trade, 2bps/side proxy; not IBIT returns or broker fills')
    ident = state.get('session', {}).get('id')
    if not isinstance(ident, str) or not re.fullmatch(r'[0-9TZ-]+', ident):
        result['error'] = 'Live session unavailable; no zero-trade conclusion'
        return result
    path = Path(root) / 'sessions' / ident / 'observations.sqlite'
    if not path.exists():
        result['error'] = 'Observation database unavailable; no zero-trade conclusion'
        return result
    try:
        try:
            calendar = Calendar(read(Path(calendar_root) / 'CALENDAR.json', {}), now)
        except (OSError, ValueError):
            calendar = Calendar({}, now)
        current = calendar.at(now)
        with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10) as db:
            # Unlike the live page's latest-150 list, query the complete durable
            # action history. No table/schema changes and no worker methods run.
            source = db.execute('SELECT id,model,ref,detected,body FROM events WHERE detected<=? ORDER BY detected,ref,model', (now,)).fetchall()
            first, last = db.execute('SELECT min(t),max(t) FROM minutes').fetchone()
        if first is None:
            result['error'] = 'No observed minutes; no zero-trade conclusion'
            return result
        entries, actions = {}, []
        for event_id, model, reference, detected, body in source:
            if model not in MODELS:
                continue
            event = json.loads(body)
            if not action(event):
                continue
            meta = signal_hours(event, current, calendar, now, event=True, worker_health=state.get('health'))
            available = epoch(meta['available_at'])
            if available is None or available > now:
                continue
            trade = event.get('trade_id')
            entry = event.get('type') == 'entry'
            if entry:
                entries[(model, trade)] = event
            original = entries.get((model, trade))
            fraction = None if entry else event['fraction']
            net = None
            if not entry and original is not None:
                net = fraction * (event['price'] - original['price'] - COST_PER_SIDE * (event['price'] + original['price']))
            actions.append(dict(model=model, event_id=event_id, trade_id=trade,
                action='entry' if entry else 'exit', rule=event.get('entry_rule') or (original or {}).get('entry_rule'),
                reason=event['type'], reference_time=event.get('reference_time'),
                detected_at=event.get('detected_at'), available_at=meta['available_at'],
                price=event.get('price'), fraction=fraction,
                initial_stop=(original or {}).get('stop'), first_target=(original or {}).get('target'),
                net=net, availability_session=meta['availability_session'], timing_label=meta['label']))
        inside = [r for r in actions if start <= epoch(r['available_at']) <= now]
        counts = {m: dict(entries=sum(r['model'] == m and r['action'] == 'entry' for r in inside),
                          exits=sum(r['model'] == m and r['action'] == 'exit' for r in inside)) for m in MODELS}
        nets = {m: sum(r['net'] for r in inside if r['model'] == m and r['net'] is not None) for m in MODELS}
        recent = []
        for model in MODELS:
            trades = {}
            for row in actions:
                if row['model'] != model:
                    continue
                trade = trades.setdefault(row['trade_id'], dict(model=model, trade_id=row['trade_id'], entry=None, exits=[]))
                if row['action'] == 'entry':
                    trade['entry'] = row
                else:
                    trade['exits'].append(row)
            closed = [t for t in trades.values() if t['entry'] and t['exits'] and sum(e['fraction'] for e in t['exits']) >= .999999
                      and epoch(t['exits'][-1]['available_at']) < start]
            for trade in closed[-2:]:
                entry, exits = trade['entry'], trade['exits']
                recent.append(dict(model=model, event_id=entry['event_id'], trade_id=trade['trade_id'],
                    rule=entry['rule'], entry_available=entry['available_at'], entry_reference=entry['reference_time'],
                    entry_price=entry['price'], initial_stop=entry['initial_stop'], first_target=entry['first_target'],
                    exit_available=exits[-1]['available_at'], exit_reference=exits[-1]['reference_time'],
                    exit_price=exits[-1]['price'], fraction=sum(e['fraction'] for e in exits),
                    reason=exits[-1]['reason'], net=sum(e['net'] for e in exits),
                    ibit_session=exits[-1]['availability_session'], scope='Before the 12-hour window'))
        result.update(status='available', actions=grouped(inside), counts=counts, net_by_model=nets,
                      recent_before_window=sorted(grouped(recent), key=lambda r: r['exit_available'], reverse=True),
                      first_observation=iso(first) if first is not None else None,
                      last_observation_end=iso(last + 60) if last is not None else None,
                      session_covers_window=first is not None and first <= start,
                      feed_health=state.get('health'), missing_observations_are_not_filled=True)
    except (sqlite3.Error, OSError, ValueError, TypeError, KeyError):
        result.update(error='Durable action audit unavailable; do not infer zero trades', actions=None, counts=None, net_by_model=None)
    return result


def snapshot(state, *, now=None, root=LIVE, calendar_root=HOME, review_path=REVIEW):
    now = time.time() if now is None else now
    try:
        review = read(Path(review_path), {})
    except (OSError, ValueError):
        review = {}
    return dict(as_of=iso(now), comparison_only=True, orders_enabled=False,
                review=review, history=history(state, now=now, root=root, calendar_root=calendar_root),
                quote=copy.deepcopy(state.get('quote')) if state.get('quote_fresh') else None,
                quote_age_seconds=state.get('quote_age_seconds'), worker_health=state.get('health'),
                positions=[dict(model=m['model'], holding=m.get('position') is not None,
                                closed=m.get('closed'), closed_net=m.get('closed_net')) for m in state.get('models', [])],
                completed_structure_end=state.get('rows', [{}])[-1].get('end') if state.get('rows') else None)
