"""Saved P1 research comparison reads; opening the page never starts a replay."""
from __future__ import annotations
import copy
import json
import re
import sqlite3
from trading_desk.btc_data import STORE,read,ts


class P1View:
    def __init__(self,store=STORE):
        self.store=store
        self.cache={}

    def current(self):
        ident=read(self.store/'p1_studies/ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-P1-A-sequential',ident):return None
        return read(self.store/'p1_studies'/ident/'STUDY.json')

    def selection(self,model,sequence):
        if model not in ('0.1','E1','E2') or sequence not in ('p1','frozen'):
            raise ValueError('Choose 0.1/E1/E2 and p1/frozen')
        study=self.current()
        if not study or study['status']!='complete':return study,None,None
        ident=study['run_ids' if sequence=='p1' else 'baseline_run_ids'][model]
        if not re.fullmatch(r'\d{8}T\d{6}Z-30-ab',ident):raise ValueError('Invalid saved run')
        folder=(self.store/'runs'/ident if sequence=='p1' else
            self.store/'releases/0.2/results'/ident)
        p=folder/'result.json';stamp=p.stat().st_mtime_ns
        key=(model,sequence,str(folder))
        if key not in self.cache or self.cache[key][0]!=stamp:self.cache[key]=(stamp,read(p))
        return study,folder,self.cache[key][1]

    @staticmethod
    def compact(p):
        return {k:copy.deepcopy(p.get(k)) for k in ('id','status','entry_time','entry_rule','entry',
            'initial_stop','stop','t1','remaining','exit_time','legs','net','net_r','references',
            'p1','gap_exposed','context_partial')}

    def snapshot(self,model='0.1',sequence='p1',trade_id=None):
        study,folder,result=self.selection(model,sequence)
        if not result:return dict(available=False,read_only=True,orders_enabled=False)
        try:ident=int(trade_id) if trade_id is not None else result['trades'][0]['id']
        except (ValueError,TypeError,IndexError):raise ValueError('Choose a saved trade') from None
        p=next((p for p in result['trades'] if p['id']==ident),None)
        if not p:raise ValueError('Trade not found in this sequence')
        first=ts(p['entry_time'])//900*900-7200
        last=(ts(p.get('exit_time') or result['end'])//900+1)*900+1800
        fields=('t','time','end','open','high','low','close','observed_minutes',
            'l1_price','l1_time','l1_known_at','l2_price','l2_time','stop','remaining','position_id')
        with sqlite3.connect((folder/'ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
            rows=[]
            for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                row=json.loads(body)
                item={k:row.get(k) for k in fields}
                item['events']=[e for e in row['events'] if e.get('trade_id')==ident]
                rows.append(item)
        selected=self.compact(p)
        audit=p.get('p1')
        if not audit and sequence=='frozen' and 'A' in p.get('entry_rule',''):
            _,_,candidate=self.selection(model,'p1')
            rejection=next((r for r in candidate.get('p1_rejections',[]) if r['time_utc']==p['entry_time']),None)
            audit=rejection and rejection['p1']
        return dict(available=True,study={k:study[k] for k in ('study_id','start','end','warmup_start',
            'source_minute_sha256','source_quality','summaries','baseline_reproduced','p1_rule')},
            changes=study['changes'][model],model=model,sequence=sequence,
            trades=[self.compact(p) for p in result['trades']],selected=selected,rows=rows,
            p1_audit=audit,rejection_count=len(result.get('p1_rejections',[])),
            early_case=read(self.store/'p1_studies'/study['study_id']/'CASE_NOV09.json'),
            read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,model,sequence,name):
        if name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','result.json'):
            raise ValueError('Unknown research file')
        _,folder,result=self.selection(model,sequence)
        if not result or not (folder/name).is_file():raise ValueError('Research export not ready')
        return folder/name


P1_VIEW=P1View()
