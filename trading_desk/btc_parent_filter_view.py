"""Read-only saved parent-filter experiment, independent of every live selector."""
import copy
import json
import re
import sqlite3
import threading
from trading_desk.btc_data import STORE,read,ts
from trading_desk.btc_p1_view import P1View


class ParentFilterView:
    def __init__(self,store=STORE):
        self.store=store;self.cache={};self.lock=threading.RLock()

    def current(self):
        ident=read(self.store/'parent_filter_studies/ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-parent-filter-sequential',ident):return None
        return read(self.store/'parent_filter_studies'/ident/'STUDY.json')

    def selection(self,model,sequence):
        if model not in ('0.1','E1','E2') or sequence not in ('variant','control'):
            raise ValueError('Choose a saved model and sequence')
        s=self.current()
        if not s or s['status']!='complete':return s,None,None
        if sequence=='variant':
            rid=s['run_ids'][model]
            if not re.fullmatch(r'\d{8}T\d{6}Z-30-ab',rid):raise ValueError('Invalid saved run')
            folder=self.store/'runs'/rid
        else:folder=self.store/'parent_filter_studies'/s['study_id']/('control-'+model)
        p=folder/'result.json';key=str(p);stamp=p.stat().st_mtime_ns
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
        added=next((c['p1']['id'] for c in s['changes'][model] if c['status']=='added'),None)
        default=added if sequence=='variant' and added else next((p['id'] for p in r['trades'] if p['entry_rule']=='C'),r['trades'][0]['id'])
        try:ident=int(trade_id) if trade_id is not None else default
        except (ValueError,TypeError):raise ValueError('Choose a saved trade') from None
        p=next((p for p in r['trades'] if p['id']==ident),None)
        if p is None:raise ValueError('Trade not found')
        first=ts(p['entry_time'])//900*900-7200
        last=(ts(p.get('exit_time') or r['end'])//900+1)*900+1800
        fields=('t','time','end','open','high','low','close','observed_minutes','l1_price','l2_price','stop','remaining','position_id')
        with sqlite3.connect((folder/'ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            rows=[]
            for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                row=json.loads(body);item={k:row.get(k) for k in fields}
                item['events']=[e for e in row['events'] if e.get('trade_id')==ident];rows.append(item)
        return dict(available=True,model=model,sequence=sequence,selected=self.compact(p),rows=rows,
            study={k:s[k] for k in ('study_id','start','end','warmup_start','source_minute_sha256','source_quality',
                'policy','summaries','controls_reproduced','filter_counts')},
            trades=[self.compact(p) for p in r['trades']],changes=copy.deepcopy(s['changes'][model]),
            attribution=copy.deepcopy(s['attribution'][model]),
            parent_decisions=copy.deepcopy(r['parent_filter_audits']),read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,model,sequence,name):
        if name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','result.json','PARENT_DECISIONS.csv','CHANGES.csv'):
            raise ValueError('Unknown research file')
        s,folder,r=self.selection(model,sequence)
        if r is None:raise ValueError('Study unavailable')
        target=self.store/'parent_filter_studies'/s['study_id']/f'CHANGES_{model}.csv' if name=='CHANGES.csv' else folder/name
        if not target.is_file():raise ValueError('Export unavailable')
        return target


PARENT_FILTER_VIEW=ParentFilterView()
