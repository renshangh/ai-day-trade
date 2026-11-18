"""Isolated PH5 entry research. Original A/B, exits and live factory are untouched."""
from __future__ import annotations

import copy
from collections import deque
from datetime import datetime

from trading_desk.btc_data import iso
from trading_desk.btc_engine import aggregate, partial_context, NY
from trading_desk.btc_entry_rules import Rules
from scripts.btc_structure_retest import reward_risk
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay


PH5_RULE = dict(
    name='PH5_15M_PARENT_HL_5M_HOLD_BREAK', version='research-1',
    parent='Lowest intact strict 3-candle 15m D in fresh setup history; outside turns excluded. Higher internal lows never replace D.',
    independence='Two consecutive complete post-D 15m bars strictly above D, rebound high >= D + 1 prior-D ATR, best close >= D + 0.5 prior-D ATR (existing P1 distances, no A/P1 modification).',
    rebound='Highest confirmed strict 15m peak after D and before the latest confirmed 15m HL; must exceed D by 1 prior-D ATR.',
    hl='Latest strict 3-candle 15m low after rebound, above D + 0.1 entry ATR, intact at trigger.',
    hold='One separate complete contiguous 5m bar starting at/after 15m HL confirmation; its low strictly exceeds HL.',
    trigger='Intraminute high above immediately preceding complete 5m high + $0.01; original 0.1 entry-ATR chase ceiling.',
    stop='Larger 15m parent D minus original 0.25 entry ATR; exits remain 15m/1h original models.',
    consumption='First crossing consumes each D/HL episode, including held/warmup/rejected crossings. Every entry clears parent setup history; only full 15m candles after entry may rebuild it.',
    gaps='Clear all PH5 context and 5m hold on a missing minute; never fill gaps.',
    priority='Original A/B first in combined sequence; one position, no reentry on exit minute.',
    atr='14 completed 15m true ranges; no 5m rescaling of risk or exits.',
    speed='Descriptive only; no fitted acceleration cutoff.',
    orders_enabled=False, live_promoted=False)


class ParentFiveDetector:
    def __init__(self):
        self.reset()

    def reset(self, floor=None):
        self.window = deque(maxlen=3)
        self.parent = None
        self.lows = []
        self.highs = []
        self.floor = floor
        self.now = 0

    @staticmethod
    def point(bar, kind, known):
        return dict(time=bar[kind+'_t'], bar_time=bar['t'], price=bar[kind],
                    known_at=known, broken=False, atr_before=bar.get('atr_before'))

    def observe(self, bar):
        if self.floor is not None and bar['t'] < self.floor:
            return
        if bar['observed_minutes'] != 15:
            self.reset(self.floor)
            return
        if self.window and bar['t'] != self.window[-1]['t']+900:
            self.reset(self.floor)
        now = bar['t']+900
        self.now = now
        self.window.append(copy.deepcopy(bar))
        if len(self.window) == 3:
            left, middle, right = self.window
            lo = middle['low'] < min(left['low'], right['low'])
            hi = middle['high'] > max(left['high'], right['high'])
            if lo and not hi:
                point = self.point(middle, 'low', now)
                self.lows.append(point)
                if self.parent is None or point['price'] < self.parent['price']:
                    self.parent = dict(point, holds=0, peak=point['price'],
                                       best_close=point['price'], checked_through=middle['t'],
                                       independence_at=None)
            if hi and not lo:
                self.highs.append(self.point(middle, 'high', now))
        p = self.parent
        if p and not p['broken'] and bar['t'] > p['checked_through']:
            p['checked_through'] = bar['t']
            if bar['low'] <= p['price']:
                p['broken'] = True
            else:
                p['holds'] += 1
                p['peak'] = max(p['peak'], bar['high'])
                p['best_close'] = max(p['best_close'], bar['close'])
                atr = p['atr_before']
                if (p['independence_at'] is None and atr and p['holds'] >= 2
                        and p['peak'] >= p['price']+atr
                        and p['best_close'] >= p['price']+.5*atr):
                    p['independence_at'] = now

    def invalidate(self, minute):
        if self.parent and minute['low'] <= self.parent['price']:
            self.parent['broken'] = True
        for low in self.lows:
            if minute['low'] < low['price']:
                low['broken'] = True

    def ready(self, atr):
        p = self.parent
        if not atr or not p or p['broken'] or p['independence_at'] is None or not self.lows:
            return None
        hl = self.lows[-1]
        if hl['broken'] or hl['time'] <= p['time'] or hl['price'] <= p['price']+.1*atr:
            return None
        peaks = [h for h in self.highs if p['time'] < h['time'] < hl['time']
                 and h['known_at'] <= self.now and h['price'] >= p['price']+p['atr_before']
                 and h['price'] > hl['price']]
        if not peaks:
            return None
        peak = max(peaks, key=lambda h: h['price'])
        return dict(parent=copy.deepcopy(p), rebound=copy.deepcopy(peak), hl=copy.deepcopy(hl),
                    known_at=max(p['independence_at'], hl['known_at'], peak['known_at']))


def five_signal(setup, previous_five, minute, atr, target):
    # Same arithmetic as entry_signal, with an explicit 300-second adjacency
    # check. Never alter timestamps/coverage to pass the 15m validator.
    rules = Rules()
    reasons = []
    if setup['known_at'] > minute['t']:
        reasons.append('15m structure not yet known')
    if (previous_five['observed_minutes'] != 5 or previous_five['t']+300 != minute['t']//300*300
            or previous_five['t'] < setup['known_at']):
        reasons.append('separate post-confirmation complete adjacent 5m hold unavailable')
    if previous_five['low'] <= setup['hl']['price']:
        reasons.append('5m hold does not remain strictly above confirmed HL')
    if minute['low'] < setup['hl']['price']:
        reasons.append('HL and trigger crossed in same minute; order unknown')
    if setup['hl']['broken'] or setup['hl']['price'] <= setup['parent']['price']+rules.higher_low_atr*atr:
        reasons.append('HL broken or tolerance failed')
    trigger = previous_five['high']+rules.trigger_increment
    crossed = minute['high'] > trigger
    price = max(trigger, minute['open']) if crossed else None
    if not crossed:
        reasons.append('previous complete 5m high not crossed')
    if crossed and price > trigger+rules.chase_atr*atr:
        reasons.append('entry exceeds existing 0.1 ATR chase ceiling')
    stop = setup['parent']['price']-rules.stop_buffer_atr*atr
    ratio = reward_risk(price, stop, target, rules.friction_bps) if price is not None and target is not None else None
    risk = ratio is not None and ratio > 0 and ratio >= rules.minimum_net_r
    preferred = ratio is not None and ratio >= rules.preferred_net_r
    structural = not reasons
    return dict(rule=PH5_RULE['name'], setup_passed=True, price_crossed=crossed,
        structural_price_signal=structural, signal_interval_start=minute['t'], signal_interval_end=minute['t']+60,
        trigger=trigger, entry_reference=price, initial_stop=stop, target_known=target is not None,
        net_reward_risk=ratio, risk_passed=risk, qualified_candidate=structural and risk,
        preferred_rr_met=preferred, rr_warning='below 2R; advisory only' if ratio is not None and not preferred else None,
        signal_reasons=reasons, risk_reason=None if risk else 'target unavailable or net target reward not positive',
        trigger_timeframe_seconds=300, trigger_increment=rules.trigger_increment,
        execution='research minute reference only; no orders or actual fills')


class ParentFiveMixin:
    def __init__(self, *args, ph5_mode='combined', ph5_active_from=None, ph5_trace=False, **kwargs):
        if ph5_mode not in ('combined', 'standalone'):
            raise ValueError('Choose combined or standalone PH5')
        super().__init__(*args, **kwargs)
        self.ph5_mode = ph5_mode
        self.ph5_active_from = self.start if ph5_active_from is None else ph5_active_from
        self.ph5_trace_enabled = ph5_trace
        self.ph5_trace = []
        self.ph5 = ParentFiveDetector()
        self.five_pending = []
        self.previous_five = None
        self.ph5_emitted = set()

    def minute(self, b):
        if self.last_minute is not None and b['t'] != self.last_minute+60:
            self.ph5.reset(self.entry_history_start)
            self.five_pending = []
            self.previous_five = None
        if self.five_pending and b['t']//300 != self.five_pending[0]['t']//300:
            group = self.five_pending
            self.previous_five = (aggregate(group, 300) if [m['t'] for m in group]
                == list(range(group[0]['t']//300*300, group[0]['t']//300*300+300, 60)) else None)
            self.five_pending = []
        super().minute(b)
        self.ph5.invalidate(b)
        self.five_pending.append(b)

    def complete(self):
        had = bool(self.minutes)
        super().complete()
        if had:
            self.ph5.observe(self.prev)
            if self.ph5_trace_enabled and self.prev['t'] >= self.ph5_active_from:
                self.ph5_trace.append(dict(bar=copy.deepcopy(self.prev),
                    parent=copy.deepcopy(self.ph5.parent), ready=copy.deepcopy(self.ph5.ready(self.atr)),
                    lows=copy.deepcopy(self.ph5.lows[-4:]), floor=self.ph5.floor))

    def scan(self, b, can_trade):
        setup = self.ph5.ready(self.atr)
        prev = self.previous_five
        candidate = None
        if setup and prev and self.atr:
            token = (setup['parent']['time'], setup['hl']['time'])
            if (token not in self.ph5_emitted and prev['t'] >= setup['known_at']
                    and prev['t']+300 == b['t']//300*300 and prev['low'] > setup['hl']['price']
                    and b['high'] > prev['high']+.01):
                self.ph5_emitted.add(token)
                price = max(prev['high']+.01, b['open'])
                t1, t2 = self.targets(price, dict(high=setup['rebound']['price']), b['t'], self.atr)
                candidate = five_signal(setup, prev, b, self.atr, t1)
                candidate.update(route='PH5', routes=['PH5'], time_utc=iso(b['t']),
                    time_ny=datetime.fromtimestamp(b['t'], NY).isoformat(), interval_end=iso(b['t']+60),
                    previous_bar_time=iso(prev['t']), t1=t1, t2=t2, atr=self.atr,
                    setup_evidence=copy.deepcopy(setup), hold_bar=copy.deepcopy(prev),
                    context_partial=partial_context(self.recent), quote_reference=b['volume']==0,
                    references=dict(l1={k:iso(v) if k in ('time','known_at') else v
                        for k,v in setup['parent'].items() if k in ('time','price','known_at')},
                        l2={k:iso(v) if k in ('time','known_at') else v
                        for k,v in setup['hl'].items() if k in ('time','price','known_at')},
                        h1=dict(time=iso(setup['rebound']['time']), price=setup['rebound']['price']),
                        trigger=prev['high']+.01, stop=candidate['initial_stop'], target=t1,
                        net_reward_risk=candidate['net_reward_risk']))
        if self.ph5_mode == 'combined':
            super().scan(b, can_trade)
        else:
            self.last_scanned = b['t']
        if candidate is None or b['t'] < self.ph5_active_from or b['t'] < self.start:
            return
        s = candidate
        s.update(id=len(self.signals)+1, trade_id=None)
        s['decision'] = ('entry' if s['qualified_candidate'] and can_trade and self.position is None else
            'held_position' if s['qualified_candidate'] and self.position is not None else
            'exit_minute_no_reentry' if s['qualified_candidate'] else
            'risk_rejected' if s['structural_price_signal'] else 'structure_rejected')
        self.signals.append(s)
        self.counter['candidates'] += 1
        self.counter['route_PH5'] += 1
        if s['decision'] == 'entry':
            self.open_signal(b, s)
        else:
            if not s['qualified_candidate']:
                self.counter['rejected'] += 1
            self.event('entry_skipped' if s['qualified_candidate'] else 'entry_rejected', b['t'],
                signal_id=s['id'], entry_rule='PH5', price=s['entry_reference'],
                reason='; '.join(s['signal_reasons']) or s['risk_reason'] or s['decision'])

    def open_signal(self, b, s):
        super().open_signal(b, s)
        self.ph5.reset(self.entry_history_start)
        if self.position and s['route'] == 'PH5':
            self.position['parent_five'] = dict(setup=copy.deepcopy(s['setup_evidence']),
                hold=copy.deepcopy(s['hold_bar']), trigger_known_no_earlier_than=s['interval_end'])

    def finish(self):
        r = super().finish()
        r['ph5_rule'] = copy.deepcopy(PH5_RULE)
        r['ph5_mode'] = self.ph5_mode
        r['signal_counts']['PH5'] = sum(s['route']=='PH5' for s in r['signals'])
        return r


class ParentFiveBaseline(ParentFiveMixin, FailedReboundReplay):
    pass


class ParentFiveEarly(ParentFiveMixin, EarlySequentialReplay):
    pass
