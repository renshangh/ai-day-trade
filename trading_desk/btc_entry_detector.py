"""Causal 15m entry structure draft; no orders, interpolation or owner overrides.

An independent turn uses one completed neighbour on each side (the existing
15m research convention). Its known_at is the right bar's end. This mechanical
scope is intentionally auditable, not a claim of human wave-level equivalence.
"""
from collections import deque


def point(bar, kind, known_at):
    return dict(time=bar[f'{kind}_t'], price=bar[kind], known_at=known_at)


class EntryDetector:
    def __init__(self):
        self.window = deque(maxlen=3)
        self.history = deque(maxlen=1000)
        self.peaks = deque(maxlen=1000)
        self.a = None
        self.a_scopes = []
        self.b = None
        self.last_peak = None
        self.lowest = None
        self.generation = 0
        self.notes = []

    def reset(self, reason):
        self.a = self.b = self.last_peak = self.lowest = None
        self.a_scopes = []
        self.window.clear()
        self.history.clear()
        self.peaks.clear()
        self.generation += 1
        self.notes.append(reason)

    def invalidate(self, minute):
        # Only future signals are invalidated; already emitted signals survive.
        for route in self.a_scopes + [self.b]:
            if route is None:
                continue
            if 'lows' in route and not route['lows']:
                continue
            d = route['lows'][-1]['price'] if 'lows' in route else route['impulse']['low']
            if minute['low'] <= d:
                route['d_broken'] = True
            if route.get('hl') and minute['low'] < route['hl']['price']:
                route['hl_broken'] = True

    def observe(self, bar, previous, now):
        if bar['observed_minutes'] != 15 or (self.window and bar['t'] != self.window[-1]['t'] + 900):
            self.reset('incomplete or absent 15m context; entry structure reset, no bars filled')
            if bar['observed_minutes'] != 15:
                return
        self.window.append(bar)
        self.history.append(bar)
        prior_low = self.lowest
        self.lowest = min(self.lowest, bar['low']) if self.lowest is not None else bar['low']

        # B: a new impulse replaces only the B setup, never the A wave count.
        atr = bar.get('atr_before')
        if (previous and atr and prior_low is not None and bar['close'] < bar['open']
                and bar['low'] < prior_low
                and max(bar['open'], previous['close']) - bar['low'] >= 2 * atr):
            self.b = dict(impulse=dict(bar), rebound=None, hl=None,
                atr_before_impulse=atr, atr_before_impulse_known_at=bar['t'],
                previous_close=previous['close'], lowest_before_impulse=prior_low,
                d_broken=False, hl_broken=False)
        b = self.b
        if b and not b['d_broken'] and bar['t'] > b['impulse']['t']:
            if b['rebound'] is None:
                if bar['close'] > bar['open'] and bar['low'] > b['impulse']['low']:
                    b['rebound'] = dict(bar)
            elif bar['t'] >= b['rebound']['t'] + 900:
                # The completed pullback low can persist through later bars;
                # entry need not follow a freshly lower previous-bar low.
                is_pullback = (previous and bar['low'] < previous['low']) or bar['close'] < bar['open']
                if is_pullback and (b['hl'] is None or bar['low'] < b['hl']['price']):
                    b['hl'] = point(bar, 'low', now)
                    b['hl_broken'] = False

        # A: confirmed turns, retaining the whole current declining chain.
        if len(self.window) == 3:
            left, middle, right = self.window
            low_turn = middle['low'] < min(left['low'], right['low'])
            high_turn = middle['high'] > max(left['high'], right['high'])
            if low_turn and high_turn:
                self.notes.append('outside-bar high/low order unknown; no turn inferred')
            elif high_turn:
                self.last_peak = point(middle, 'high', now)
                self.peaks.append(self.last_peak)
                # Keep nested declines separately. An internal new peak must
                # neither overwrite an outer D nor trap all future counting
                # under a stale, deeper low from days earlier.
                self.a_scopes = [a for a in self.a_scopes
                    if self.last_peak['price'] <= a['origin']['price']]
                self._start_a(self.last_peak)
                # A B-setup new low is relative to the latest causally known
                # 15m swing-high scope, not the minimum of the entire month.
                self.lowest = min(middle['low'], right['low'])
            elif low_turn and self.last_peak and self.last_peak['time'] < middle['low_t']:
                low = point(middle, 'low', now)
                for a in self.a_scopes:
                    if a['origin']['time'] >= low['time'] or a.get('chain_broken'):
                        continue
                    if not a['lows']:
                        a['lows'].append(low)
                        continue
                    if low['price'] >= a['lows'][-1]['price']:
                        continue
                    intervening = [x for x in self.peaks
                        if a['lows'][-1]['time'] < x['time'] < low['time']]
                    rebound = max(intervening, key=lambda x:x['price']) if intervening else None
                    previous_high = a['intervening_highs'][-1] if a['intervening_highs'] else a['origin']
                    if rebound and a['lows'][-1]['time'] < rebound['time'] < low['time']:
                        if rebound['price'] < previous_high['price']:
                            a['intervening_highs'].append(rebound)
                            a['lows'].append(low)
                            a.update(hh=None, hl=None, pending_high=None, d_broken=False, hl_broken=False)
                        else:
                            # A genuine intervening HH ends a strictly LH chain.
                            # Do not count an internal HL as another lower low.
                            a['chain_broken'] = True
                    else:
                        # No independently confirmed rebound: this is a lower
                        # extension of the SAME phase, not an additional LL.
                        a['lows'][-1] = low
                        a.update(hh=None,hl=None,pending_high=None,d_broken=False,hl_broken=False)

        self.a_scopes = [a for a in self.a_scopes if not a.get('chain_broken')]
        for a in self.a_scopes:
            if not a['lows'] or bar['high_t'] <= a['lows'][-1]['time']:
                continue
            peak = point(bar, 'high', now)
            if a['pending_high'] is None or peak['price'] > a['pending_high']['price']:
                a['pending_high'] = peak
            if len(a['lows']) >= 4 and not a['d_broken']:
                threshold = a['intervening_highs'][-1]['price']
                if bar['high'] > threshold:
                    if a['hh'] is None or bar['high'] > a['hh']['price']:
                        a['hh'] = peak
                        a['hl'] = None
                        a['hl_broken'] = False
                if a['hh'] and bar['t'] >= a['hh']['time']//900*900 + 900:
                    if a['hl'] is None or bar['low'] < a['hl']['price']:
                        a['hl'] = point(bar, 'low', now)
                        a['hl_broken'] = False

        ready = [a for a in self.a_scopes if a['lows'] and not a['d_broken']
            and not a['hl_broken'] and a['hh'] and a['hl']]
        # Select by structural scope alone, never by realized return or RR.
        self.a = min(ready,key=lambda a:a['origin']['time']) if ready else next(
            (a for a in reversed(self.a_scopes) if a['lows']),None)

    def _start_a(self, origin):
        self.a_scopes.append(dict(origin=origin, lows=[], intervening_highs=[], hh=None,
            hl=None, pending_high=None, d_broken=False, hl_broken=False,
            scope='nested causal 15m strict LL/LH chain; widest eligible origin; one complete left/right neighbour'))

    def setups(self):
        result = []
        if self.a and not self.a['d_broken'] and not self.a['hl_broken'] and self.a['hh'] and self.a['hl']:
            result.append(('A', self.a))
        if self.b and not self.b['d_broken'] and not self.b['hl_broken'] and self.b['rebound'] and self.b['hl']:
            result.append(('B', self.b))
        return result

    def snapshot(self):
        out = {}
        for name, state in (('A', self.a), ('B', self.b)):
            if not state:
                continue
            d = state['lows'][-1] if name == 'A' else point(state['impulse'], 'low', state['impulse']['t'] + 900)
            out[name] = dict(d=d, hl=state.get('hl'),
                lower_low_count=len(state['lows']) if name == 'A' else None,
                hh=state.get('hh'), rebound=state.get('rebound'),
                invalid=bool(state['d_broken'] or state['hl_broken']))
        return out
