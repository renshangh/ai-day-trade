"""GET-only PH5 saved research; importing or reading cannot run a replay."""
from __future__ import annotations

import copy
import gzip
import json
import re
import sqlite3
from collections import defaultdict
from threading import RLock

from trading_desk.btc_data import STORE, read, ts
from trading_desk.btc_engine import aggregate


class ParentFiveView:
    def __init__(self, store=STORE):
        self.store = store
        self.lock = RLock()
        self.cache = {}
        self.minutes = None

    def current(self):
        ident = read(self.store/'parent_five_studies/ACTIVE.json', {}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-PH5',ident):
            return None, None
        folder = self.store/'parent_five_studies'/ident
        study = read(folder/'STUDY.json')
        return folder, study

    def selection(self, model, sequence):
        if model not in ('0.1','E1','E2') or sequence not in ('control','standalone','combined'):
            raise ValueError('Choose a saved model and sequence')
        folder, study = self.current()
        if not study or study.get('status') != 'complete':
            return folder, study, None
        p = folder/model/sequence/'result.json'
        with self.lock:
            if str(p) not in self.cache:
                if len(self.cache) >= 3:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[str(p)] = read(p)
            result = self.cache[str(p)]
        return folder, study, result

    @staticmethod
    def compact(p):
        keys = ('id','status','entry_rule','entry_time','entry_interval_end','entry','initial_stop','stop',
                't1','t2','remaining','exit_time','legs','net','net_r','references','parent_five',
                'gap_exposed','context_partial','stop_history','initial_risk')
        return {k:copy.deepcopy(p.get(k)) for k in keys}

    def five_bars(self, first, last):
        with self.lock:
            if self.minutes is None:
                with gzip.open(self.store/'releases/0.2/data/MINUTES.jsonl.gz','rt') as f:
                    self.minutes = [json.loads(line) for line in f]
            rows = self.minutes
        groups = defaultdict(list)
        for t,o,h,l,c,v,n,_ in rows:
            if first <= t < last:
                groups[t//300*300].append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
        bars = []
        for t,group in sorted(groups.items()):
            b = aggregate(group,300)
            b['complete'] = [x['t'] for x in group] == list(range(t,t+300,60))
            bars.append(b)
        return bars

    def snapshot(self, model='0.1', sequence='combined', trade_id=None):
        folder, study, r = self.selection(model, sequence)
        if r is None:
            return dict(available=False,read_only=True,orders_enabled=False)
        trades = r['trades']
        try:
            ident = int(trade_id) if trade_id is not None else next(
                (p['id'] for p in trades if p['entry_rule']=='PH5'), trades[0]['id'] if trades else None)
        except (TypeError,ValueError):
            raise ValueError('Choose a saved trade') from None
        p = next((p for p in trades if p['id']==ident),None)
        if trade_id is not None and p is None:
            raise ValueError('Trade not found')
        rows = []
        five = []
        if p:
            first = ts(p['entry_time'])//900*900-3600
            if p.get('parent_five'):
                first = min(first,p['parent_five']['setup']['parent']['bar_time']-900)
            last = (ts(p.get('exit_time') or r['end'])//900+2)*900
            path = folder/model/sequence/'ledger.sqlite'
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                    row=json.loads(body)
                    rows.append(dict(t=row['t'],end=row['end'],open=row['open'],high=row['high'],low=row['low'],
                        close=row['close'],observed_minutes=row['observed_minutes'],
                        stop=row.get('stop') if row.get('position_id')==p['id'] else None,
                        events=[e for e in row['events'] if e.get('trade_id')==p['id']]))
            five=self.five_bars(ts(p['entry_time'])//900*900-1800,ts(p['entry_time'])//900*900+1800)
        case=read(folder/'CASE.json')['models'][model]
        case=dict(trades=[self.compact(p)|{k:p[k] for k in ('entry_received_at','marked_net','mark_time') if k in p}
                           for p in case['trades']],signals=case['signals'],trace=case['trace'],note=case['note'])
        return dict(available=True,read_only=True,orders_enabled=False,live_promoted=False,
            study=study,model=model,sequence=sequence,trades=[self.compact(p) for p in trades],
            selected=self.compact(p) if p else None,rows=rows,five=five,
            signals=[s for s in r['signals'] if s['route']=='PH5'],case=case,
            changes=study['changes'][model].get(sequence))

    def export(self, model, sequence, name):
        if name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','SIGNALS.csv','LEDGER.csv','result.json'):
            raise ValueError('Unknown saved export')
        folder, _, r = self.selection(model,sequence)
        if r is None:
            raise ValueError('Saved study unavailable')
        p = folder/model/sequence/name
        if not p.is_file():
            raise ValueError('Saved export unavailable')
        return p


PARENT_FIVE_VIEW=ParentFiveView()
