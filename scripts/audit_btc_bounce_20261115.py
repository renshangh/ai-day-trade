"""Causal local-prefix audit of Nov 14/15 bounce; no live mutation or new rules."""
from __future__ import annotations
import copy
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path
from types import MethodType
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trading_desk.btc_live import CONTROLLER, LIVE, verify_rules
from trading_desk.btc_engine import create_replay, aggregate
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_shock_branches import ExpandedEntryDetector, expanded_shock_setup
from trading_desk.btc_entry_rules import four_wave_setup
from trading_desk.btc_data import iso, ts
from scripts.btc_structure_retest import Config

NY = ZoneInfo('America/New_York')
START = ts('2026-11-14T18:00:00-05:00')
BOTTOM = ts('2026-11-14T20:45:00-05:00')
END = ts('2026-11-15T05:15:00-05:00')
FOLDER = ROOT / 'reports/btc_bounce_audit_2026_11_15'


def compact_chain(c):
    if not c:
        return None
    return dict(impulse_time=iso(c['impulse']['t']), d=copy.deepcopy(c['d']),
                rebound_time=iso(c['rebound']['t']) if c['rebound'] else None,
                hl=copy.deepcopy(c.get('hl')), d_broken=c['d_broken'], hl_broken=c['hl_broken'])


class TraceDetector(ExpandedEntryDetector):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.trace = []

    def observe(self, bar, previous, now):
        prior_low, generation = self.lowest, self.generation
        before = compact_chain(self.shock_chain)
        super().observe(bar, previous, now)
        if not START <= bar['t'] < END:
            return
        if generation != self.generation:
            prior_low = None
        atr = bar.get('atr_before')
        downward = max(bar['open'], previous['close']) - bar['low'] if previous else None
        gates = dict(previous_present=previous is not None, atr_present=bool(atr),
                     prior_scope_low=prior_low, bearish=bar['close'] < bar['open'],
                     fresh_scope_low=prior_low is not None and bar['low'] < prior_low,
                     down_points=downward, threshold_2atr=2*atr if atr else None,
                     down_atr=downward/atr if atr and downward is not None else None,
                     passes_size=bool(atr and downward is not None and downward >= 2*atr),
                     observed_minutes=bar['observed_minutes'])
        scopes = [copy.deepcopy(a) for a in self.a_scopes]
        turns = []
        if len(self.window) == 3:
            l, m, r = self.window
            low_turn=m['low']<min(l['low'],r['low']);high_turn=m['high']>max(l['high'],r['high'])
            turns.append(dict(middle_bar=iso(m['t']),low_turn=low_turn,high_turn=high_turn,
                              skipped_outside_bar=low_turn and high_turn))
        self.trace.append(dict(bar=copy.deepcopy(bar), known_at=iso(now), gates=gates,
            chain_before=before, chain_after=compact_chain(self.shock_chain),
            selected_A=copy.deepcopy(self.a), max_A_low_count=max((len(a['lows']) for a in scopes),default=0),
            scopes=scopes, turns=turns, detector_snapshot=self.snapshot(),
            notes=self.notes[-4:], routes_after_observe=[route for route,_ in self.setups()]))


def instrument(engine):
    engine.detector = TraceDetector(independent_b1_hold=engine.b1_independent_hold)
    original_scan = engine.scan
    engine.audit_scans = []
    engine.audit_atr = {}
    def scan(self, minute, can_trade):
        if START <= minute['t'] < END:
            routes=[]
            for route, setup in self.detector.setups():
                check = four_wave_setup(setup,minute['t']) if route=='A' else expanded_shock_setup(setup,minute['t'],route)
                routes.append(dict(route=route,setup_passed=check['setup_passed'],reasons=check['reasons']))
            self.audit_scans.append(dict(t=minute['t'],can_trade=can_trade,holding=self.position is not None,
                previous_time=self.prev['t'] if self.prev else None,
                previous_high=self.prev['high'] if self.prev else None,
                previous_high_cross=bool(self.prev and minute['high']>self.prev['high']+.01),
                ready_routes=routes, selected_A=self.detector.snapshot().get('A'),
                max_A_low_count=max((len(a['lows']) for a in self.detector.a_scopes),default=0),
                shock=compact_chain(self.detector.shock_chain), atr=self.atr,
                current_low=minute['low'],current_high=minute['high']))
            self.audit_atr[minute['t']]=self.atr
        return original_scan(minute,can_trade)
    engine.scan = MethodType(scan,engine)
    return engine


def main():
    status=CONTROLLER.status();session=status['session'];hashes=verify_rules()
    protected=list(hashes)+['trading_desk/btc_live.py','scripts/run_btc_live.py',
        str(LIVE/'CONTROL.json'),str(LIVE/'SESSION.json'),
        str(Path.home()/'Library/LaunchAgents/com.renshangh.btc-live-comparison.plist')]
    before={p:hashlib.sha256((ROOT/p if not Path(p).is_absolute() else Path(p)).read_bytes()).hexdigest() for p in protected}
    source=LIVE/'sessions'/session['id']/'observations.sqlite'
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(END+60,)).fetchall()
        signals={m:[json.loads(b) for b, in db.execute('SELECT body FROM signals WHERE model=? AND ref<? ORDER BY ref',(m,END+60))] for m in ('0.1','E1','E2')}
        events={m:[json.loads(b) for b, in db.execute('SELECT body FROM events WHERE model=? AND ref<? ORDER BY ref,detected',(m,END+60))] for m in signals}
    minutes=[json.loads(b) for b,_ in records]
    engines={};results={}
    for model in signals:
        ledger=sqlite3.connect(':memory:');ledger.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
        if model=='0.1':
            engine=create_replay(session['start'],4102444800,ledger,expanded_b=True,exit_version='failed_rebound')
        else:
            engine=EarlySequentialReplay(session['start'],4102444800,ledger,Config(first_sale_fraction=.25,resistance_mode='major1h'),
                early_policy=model,expanded_b=True,consume_entry_history=True,b1_independent_hold=False)
        instrument(engine)
        for bar, (_, received) in zip(minutes, records):
            before_frames = len(engine.detector.trace)
            before_scans = len(engine.audit_scans)
            engine.minute(bar)
            for frame in engine.detector.trace[before_frames:]:
                frame['available_to_worker'] = iso(received)
                frame['triggered_by_observed_minute'] = iso(bar['t'])
            for scan in engine.audit_scans[before_scans:]:
                scan['detected_at'] = iso(received)
        # Do not call finish(): it can invent a last-period decision boundary.
        actual=[(s['trade_id'],s['route'],s['time_utc'],s['entry_reference'],s['initial_stop'],s['t1']) for s in signals[model] if s['decision']=='entry']
        replay=[(s['trade_id'],s['route'],s['time_utc'],s['entry_reference'],s['initial_stop'],s['t1']) for s in engine.signals if s['decision']=='entry']
        assert actual==replay,(model,'entry mismatch')
        exits=[(e['trade_id'],e['time_utc'],e['type'],e['price'],e['fraction']) for e in events[model] if e.get('fraction',0)>0]
        legs=sorted([(p['id'],l['time_utc'],l['reason'],l['price'],l['fraction']) for p in engine.trades for l in p['legs']],key=lambda e:e[1])
        assert exits==legs,(model,'exit mismatch')
        frames=[]
        for frame in engine.detector.trace:
            b=frame['bar'];scans=[s for s in engine.audit_scans if b['t']<=s['t']<b['t']+900]
            frame['during_bar']=dict(scan_count=len(scans),holding_minutes=sum(s['holding'] for s in scans),
                allowed_minutes=sum(s['can_trade'] for s in scans),cross_minutes=[iso(s['t']) for s in scans if s['previous_high_cross']],
                routes_seen=sorted({r['route'] for s in scans for r in s['ready_routes']}),
                first_scan=scans[0] if scans else None)
            frames.append(frame)
        results[model]=dict(recorded_entries_reproduced=len(actual),recorded_exit_legs_reproduced=len(exits),
            final_holding=engine.position,entry_history_start=iso(engine.entry_history_start) if engine.entry_history_start else None,
            entry_signals_in_bounce=[s for s in engine.signals if BOTTOM<=ts(s['time_utc'])<END],frames=frames,
            scans=engine.audit_scans)
        engines[model]=engine
    # Five-minute context is a price-structure diagnostic, not the 15m engine
    # relabelled or rerun with five observations masquerading as fifteen.
    five=[];groups={}
    received_by_minute={json.loads(body)['t']:received for body,received in records}
    for b in minutes:
        if START<=b['t']<END:groups.setdefault(b['t']//300*300,[]).append(b)
    for t,group in sorted(groups.items()):
        if [b['t'] for b in group]!=list(range(t,t+300,60)):
            five.append(dict(t=t,complete=False,observed_minutes=len(group)));continue
        bar=aggregate(group,300);bar['complete']=True
        atr=engines['0.1'].audit_atr.get(t)
        bar['known_after']=iso(t+300)
        bar['source_data_available_at']=iso(max(received_by_minute[m['t']] for m in group))
        bar['zero_volume_minutes']=sum(m['volume']==0 for m in group)
        bar['change_pct']=100*(bar['close']/bar['open']-1)
        bar['pct_per_minute']=bar['change_pct']/5
        bar['prior_15m_atr']=atr
        bar['atr_per_minute']=(bar['close']-bar['open'])/(atr*5) if atr else None
        if five and five[-1].get('complete') and five[-1]['t']+300==t:
            prev=five[-1];trigger=prev['high']+.01
            crossed=next((m for m in group if m['high']>trigger),None)
            bar['previous_5m_high']=prev['high'];bar['previous_5m_high_cross']=iso(crossed['t']) if crossed else None
            bar['cross_known_after']=iso(crossed['t']+60) if crossed else None
            bar['cross_source_received_at']=iso(received_by_minute[crossed['t']]) if crossed else None
        five.append(bar)
    out=dict(created_at=iso(time.time()),session=session['id'],pid=status['pid'],
        mode='read-only causal prefix replay; no monthly rerun, rule adjustment or live writes',
        prefix_start=iso(minutes[0]['t']),prefix_end=iso(minutes[-1]['t']+60),prefix_minutes=len(minutes),
        input_sha256=hashlib.sha256(''.join(body+'\n' for body,_ in records).encode()).hexdigest(),
        audit_start=iso(START),audit_end=iso(END),results=results,five_minute_diagnostic=five,
        source='Original persisted Alpaca observations; quote-derived and venue-only volume limitations retained',
        reference_is_not_fill=True,rules_sha256=hashes,orders_enabled=False)
    FOLDER.mkdir(parents=True,exist_ok=True)
    (FOLDER/'AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
    for name,engine in engines.items():engine.db.close()
    after=CONTROLLER.status();assert after['pid']==status['pid'] and after['session']['id']==session['id'];assert verify_rules()==hashes
    for p,h in before.items():assert hashlib.sha256((ROOT/p if not Path(p).is_absolute() else Path(p)).read_bytes()).hexdigest()==h,p
    (FOLDER/'PRESERVATION.json').write_text(json.dumps(dict(protected_files=len(before),hashes=before,
        btc_pid=after['pid'],session=after['session']['id'],health=after['health'],unchanged=True),indent=2)+'\n')
    print(json.dumps(dict(report=str(FOLDER/'AUDIT.json'),models={k:dict(entries=v['recorded_entries_reproduced'],exits=v['recorded_exit_legs_reproduced'],bounce_signals=len(v['entry_signals_in_bounce'])) for k,v in results.items()},prefix_minutes=len(minutes))))

if __name__=='__main__':main()
