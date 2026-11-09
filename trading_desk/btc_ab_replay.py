"""A/B entries with approved active exits and explicit legacy compatibility."""
import copy
import hashlib
import inspect
import json

from trading_desk.btc_engine import Replay, partial_context, NY
from trading_desk.btc_data import iso
from trading_desk.btc_entry_detector import EntryDetector
from trading_desk.btc_entry_rules import four_wave_setup, shock_setup, entry_signal
from trading_desk.btc_approved_exits import ApprovedExitReplay
from datetime import datetime


class ABReplay(ApprovedExitReplay):
    def __init__(self, *args, expanded_b=False, consume_entry_history=False,b1_independent_hold=False, **kwargs):
        super().__init__(*args, **kwargs)
        if expanded_b:
            from trading_desk.btc_shock_branches import ExpandedEntryDetector
            self.detector=ExpandedEntryDetector(independent_b1_hold=b1_independent_hold)
        else:
            self.detector = EntryDetector()
        self.signals = []
        self.emitted = set()
        self.last_scanned = None
        self.consume_entry_history=consume_entry_history
        self.entry_history_start=None
        self.b1_independent_hold=bool(expanded_b and b1_independent_hold)

    def event(self,kind,t,**values):
        super().event(kind,t,**values)
        if kind=='stop_raised' and self.position:
            self.position.setdefault('stop_history',[]).append(dict(time_utc=iso(t),**values))

    def complete(self):
        previous = self.prev
        had_minutes = bool(self.minutes)
        super().complete()
        if not had_minutes:
            return
        bar = self.prev
        # A consumed setup cannot seed a later trade under another route/HL.
        # The entry candle itself mixes pre/post-entry minutes, so only fresh
        # complete candles starting after the entry interval may rebuild A/B.
        floor=self.entry_history_start
        if floor is None or bar['t']>=floor:
            eligible_previous=previous if floor is None or (previous and previous['t']>=floor) else None
            self.detector.observe(bar, eligible_previous, bar['t']+900)
        if bar['t'] >= self.start:
            row = json.loads(self.db.execute('SELECT body FROM ledger WHERE t=?', (bar['t'],)).fetchone()[0])
            row['entry_setups'] = self.detector.snapshot()
            if floor is not None:row['entry_history_start']=iso(floor)
            self.db.execute('UPDATE ledger SET body=? WHERE t=?', (json.dumps(row, ensure_ascii=False), bar['t']))

    def minute(self, b):
        super().minute(b)
        # Base Replay intentionally skips entry on held/exit minutes. Still
        # retain their A/B signals for review, without opening another trade.
        if self.last_scanned != b['t']:
            self.scan(b, can_trade=False)
        self.detector.invalidate(b)

    def entry(self, b):
        self.scan(b, can_trade=True)

    def scan(self, b, can_trade):
        self.last_scanned = b['t']
        if b['t'] < self.start or self.prev is None or self.atr is None:
            return
        found = []
        for route, setup in self.detector.setups():
            if route=='A':state=four_wave_setup(setup,b['t'])
            elif route=='B':state=shock_setup(setup,b['t'])
            else:
                from trading_desk.btc_shock_branches import expanded_shock_setup
                if route=='B1' and self.b1_independent_hold:
                    from trading_desk.btc_shock_branches import independent_b1_setup
                    state=independent_b1_setup(setup,b['t'],self.prev,d_intact=not setup['d_broken'])
                else:state=expanded_shock_setup(setup,b['t'],route)
            waiting_b1=route=='B1' and self.b1_independent_hold and not state['setup_passed']
            if not state['setup_passed'] and not waiting_b1:
                continue
            d_time = setup['lows'][-1]['time'] if route == 'A' else setup['d']['time'] if route in ('B1','B2') else setup['impulse']['low_t']
            active_hl=None if route=='B1' else setup['hl']
            token = (route, d_time, active_hl['time'] if active_hl else None)
            if waiting_b1:
                # A blocked D-candle breakout must not consume the later valid
                # independent-confirmation signal for this same D.
                token=('B1_WAIT',d_time,self.prev['t'])
            if token in self.emitted:
                continue
            trigger = self.prev['high']+.01
            if b['high'] <= trigger:
                continue
            entry = max(trigger,b['open'])
            h = setup['hh'] if route == 'A' else dict(price=self.prev['high'],time=self.prev['high_t']) if route=='B1' else dict(price=setup['rebound']['high'],time=setup['rebound']['high_t'])
            t1,t2 = self.targets(entry,dict(high=h['price']),b['t'],self.atr)
            # Every target was constructed exclusively from already observed
            # peaks/zones; keep its complete evidence instead of later prices.
            context = dict(previous_bar=self.prev,minute=b,atr_before_entry=self.atr,
                atr_known_at=b['t']//900*900,hl_unbroken_before_trigger=not setup['d_broken'] if route=='B1' else not setup['hl_broken'],
                target=dict(price=t1,known_at=b['t']) if t1 is not None else None)
            signal = entry_signal(state,context)
            if not signal['price_crossed']:
                continue
            # A current minute crossing HL has unknown within-minute order.
            if b['low'] < (active_hl['price'] if active_hl else state['d']):
                signal['structural_price_signal'] = signal['qualified_candidate'] = False
                signal['signal_reasons'].append('support and trigger both crossed within minute; order unknown')
            self.emitted.add(token)
            refs = dict(l1=dict(time=iso(d_time),price=state['d'],known_at=iso(
                setup['lows'][-1]['known_at'] if route=='A' else setup['d']['known_at'] if route in ('B1','B2') else setup['impulse']['t']+900)),
                h1=dict(time=iso(h['time']),price=h['price']),
                l2=dict(time=iso(active_hl['time']),price=active_hl['price'],known_at=iso(active_hl['known_at'])) if active_hl else None,
                trigger=trigger,stop=signal['initial_stop'],target=t1,net_reward_risk=signal['net_reward_risk'])
            confirmation=None
            if route=='B1' and self.b1_independent_hold:
                confirmation=dict(required=True,time=iso(self.prev['t']),
                    known_at=iso(self.prev['t']+900),low=self.prev['low'],high=self.prev['high'],observed_minutes=self.prev['observed_minutes'],
                    independent=self.prev['t']>=setup['d']['known_at'],passed=state['setup_passed'],
                    entry_not_before=iso(state['entry_not_before']))
            found.append(dict(route=route,routes=[route],**signal,
                time_utc=iso(b['t']),time_ny=datetime.fromtimestamp(b['t'],NY).isoformat(),
                interval_end=iso(b['t']+60),previous_bar_time=iso(self.prev['t']),
                t1=t1,t2=t2,atr=self.atr,references=refs,setup_evidence=copy.deepcopy(setup),
                context_partial=partial_context(self.recent),quote_reference=b['volume']==0,
                b1_confirmation=confirmation))
        # Exact same D/HL/trigger on A and B is one signal with two labels.
        merged = {}
        for s in found:
            key=(s['references']['l1']['time'],s['references']['l2']['time'] if s['references']['l2'] else None,s['trigger'],s['initial_stop'],s['t1'],s['t2'])
            if key in merged:
                merged[key]['routes'].extend(s['routes'])
                merged[key]['route']='+'.join(merged[key]['routes'])
                merged[key]['also_setup_evidence']=s['setup_evidence']
            else:
                merged[key]=s
        for s in merged.values():
            s['id']=len(self.signals)+1
            eligible=s['qualified_candidate']
            s['decision']=('entry' if eligible and can_trade and self.position is None else
                'held_position' if eligible and self.position is not None else
                'exit_minute_no_reentry' if eligible else
                'risk_rejected' if s['structural_price_signal'] else 'structure_rejected')
            s['trade_id']=None
            self.signals.append(s)
            self.counter['candidates']+=1
            for route in s['routes']:
                self.counter['route_'+route]+=1
            if not eligible:
                self.counter['rejected']+=1
            if s['decision']=='entry':
                self.open_signal(b,s)
                if self.consume_entry_history:
                    # Other found routes were calculated before this fill and
                    # belong to the history just consumed, not fresh setups.
                    break
            else:
                self.event('entry_rejected' if not eligible else 'entry_skipped',b['t'],
                    reason='; '.join(s['signal_reasons']) or s['risk_reason'] or s['decision'],
                    signal_id=s['id'],entry_rule=s['route'],price=s['entry_reference'],**s['references'])

    def open_signal(self,b,s):
        self.position_id+=1
        s['trade_id']=self.position_id
        entry=s['entry_reference'];stop=s['initial_stop']
        self.position=dict(id=self.position_id,status='open',entry=entry,entry_time=iso(b['t']),
            entry_interval_end=iso(b['t']+60),initial_stop=stop,stop=stop,t1=s['t1'],t2=s['t2'],remaining=1.0,
            initial_risk=entry-stop+(entry+stop)*.0002,legs=[],references=s['references'],
            protected_t=self.prev['t'],protected_low=self.prev['low'],pending_lows=[],
            peak=b['high'],peak_before_period=b['high'],entry_period=b['t']//900*900,
            gap_exposed=False,context_partial=s['context_partial'],quote_reference_entry=b['volume']==0,
            entry_rule=s['route'],signal_id=s['id'])
        self.event('entry',b['t'],price=entry,trade_id=self.position_id,
            entry_rule=s['route'],signal_id=s['id'],**s['references'])
        if self.consume_entry_history:
            self.entry_history_start=(b['t']//900+1)*900
            self.detector.reset('entry consumed all prior A/B setup history')
            self.event('entry_history_consumed',b['t'],trade_id=self.position_id,
                entry_rule=s['route'],fresh_bars_from=iso(self.entry_history_start),
                reason='prior setup bars excluded from new A/B entries; price/ATR/resistance and held-position protection retained')
        if b['low']<=stop:
            self.position['entry_minute_ambiguity']=True
            self.close_part(b,stop,1.0,'stop_entry_minute_ambiguous')

    def finish(self):
        result=super().finish()
        result['signals']=self.signals
        result['consume_entry_history']=self.consume_entry_history
        result['b1_independent_hold']=self.b1_independent_hold
        result['signal_counts']={
            'all':len(self.signals),
            'structural':sum(s['structural_price_signal'] for s in self.signals),
            'risk_passed':sum(s['qualified_candidate'] for s in self.signals),
            'risk_rejected':sum(s['structural_price_signal'] and not s['risk_passed'] for s in self.signals),
            'below_2r':sum(s['structural_price_signal'] and s['net_reward_risk'] is not None and s['net_reward_risk']<2 for s in self.signals),
            'target_missing':sum(s['structural_price_signal'] and s['t1'] is None for s in self.signals),
            'positive_below_2r':sum(s['structural_price_signal'] and s['net_reward_risk'] is not None and 0<s['net_reward_risk']<2 for s in self.signals),
            'nonpositive_target':sum(s['structural_price_signal'] and s['net_reward_risk'] is not None and s['net_reward_risk']<=0 for s in self.signals),
            'traded':sum(s['trade_id'] is not None for s in self.signals),
            'A':sum('A' in s['routes'] for s in self.signals),
            'B':sum(any(x.startswith('B') for x in s['routes']) for s in self.signals)}
        legacy={name:hashlib.sha256(inspect.getsource(getattr(Replay,name)).encode()).hexdigest()
            for name in ('minute','complete','close_part','targets')}
        result['legacy_exit_reference_sha256']=legacy
        if self.exit_policy=='legacy':result['unchanged_exit_contract']=legacy
        result['exit_policy']=self.policy
        return result
