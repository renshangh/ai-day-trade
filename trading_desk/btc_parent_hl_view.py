"""Read-only saved C continuation studies; independent of P1/live selections."""
import copy
import json
import re
import sqlite3
import threading
from trading_desk.btc_data import STORE,read,ts
from trading_desk.btc_p1_view import P1View


class ContinuationView:
    def __init__(self,store=STORE):
        self.store=store;self.cache={};self.lock=threading.RLock()

    def current(self):
        ident=read(self.store/'parent_hl_studies/ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-parent-HL',ident):return None
        return read(self.store/'parent_hl_studies'/ident/'STUDY.json')

    def selection(self,model,sequence):
        if model not in ('0.1','E1','E2') or sequence not in ('variant','control','frozen'):
            raise ValueError('Choose a saved model and sequence')
        s=self.current()
        if not s or s['status']!='complete':return s,None,None
        if sequence=='frozen':
            rid=read(self.store/'releases/0.2/REGISTRY.json')['0.2']['run_ids'][model]
            folder=self.store/'releases/0.2/results'/rid
        else:
            rid=s['run_ids' if sequence=='variant' else 'control_run_ids'][model]
            folder=self.store/'runs'/rid
        if not re.fullmatch(r'\d{8}T\d{6}Z-30-ab',rid):raise ValueError('Invalid saved research run')
        p=folder/'result.json';key=str(p);stamp=p.stat().st_mtime_ns
        # Parallel model requests may evict another selection. Capture its
        # result under the lock rather than looking up an evictable key later.
        with self.lock:
            if key not in self.cache or self.cache[key][0]!=stamp:
                if len(self.cache)>=2:self.cache.pop(next(iter(self.cache)))
                self.cache[key]=(stamp,read(p))
            result=self.cache[key][1]
        return s,folder,result

    @staticmethod
    def compact(p):
        return dict(P1View.compact(p),continuation=copy.deepcopy(p.get('continuation')))

    def snapshot(self,model='0.1',sequence='variant',trade_id=None):
        s,folder,r=self.selection(model,sequence)
        if r is None:return dict(available=False,read_only=True,orders_enabled=False)
        try:
            ident=int(trade_id) if trade_id is not None else next((p['id'] for p in r['trades'] if p['entry_rule']=='C'),r['trades'][0]['id'])
        except (ValueError,TypeError,IndexError):raise ValueError('Choose a saved trade') from None
        p=next((p for p in r['trades'] if p['id']==ident),None)
        if p is None:raise ValueError('Trade not found in this sequence')
        first=ts(p['entry_time'])//900*900-7200
        last=(ts(p.get('exit_time') or r['end'])//900+1)*900+1800
        fields=('t','time','end','open','high','low','close','observed_minutes',
            'l1_price','l2_price','stop','remaining','position_id')
        with sqlite3.connect((folder/'ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            rows=[]
            for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                row=json.loads(body);item={k:row.get(k) for k in fields}
                item['events']=[e for e in row['events'] if e.get('trade_id')==ident];rows.append(item)
        case=read(self.store/'parent_hl_studies'/s['study_id']/'CASE_NOV09.json')
        c_trades=[p for p in r['trades'] if p['entry_rule']=='C']
        return dict(available=True,model=model,sequence=sequence,selected=self.compact(p),
            study={k:s[k] for k in ('study_id','start','end','warmup_start','source_minute_sha256',
                'source_quality','summaries','controls_reproduced','continuation_rule')},
            trades=[self.compact(p) for p in r['trades']],rows=rows,
            changes=[dict(status=c['status'],original=c['control'],p1=c['variant'],delta=c['delta']) for c in s['changes'][model]],
            c_signals=[x for x in r.get('signals',[]) if x['route']=='C'],
            c_diagnostics=dict(entries=len(c_trades),wins=sum(p['net']>0 for p in c_trades if p['net'] is not None),
                losses=sum(p['net']<=0 for p in c_trades if p['net'] is not None),
                net=sum(p['net'] for p in c_trades if p['net'] is not None),
                total_cost=sum(l['cost'] for p in r['trades'] for l in p['legs'])),
            case=case,read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,model,sequence,name):
        if name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','result.json'):
            raise ValueError('Unknown research file')
        _,folder,r=self.selection(model,sequence)
        if r is None or not(folder/name).is_file():raise ValueError('Research export unavailable')
        return folder/name


CONTINUATION_VIEW=ContinuationView()
