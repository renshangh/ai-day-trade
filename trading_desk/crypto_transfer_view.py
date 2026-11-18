"""Read-only frozen-0.2 cross-crypto comparison and audit exports."""
import copy
import json
import re
import sqlite3
import threading
from trading_desk.btc_data import read,ts
from trading_desk.crypto_transfer import STUDIES,ASSETS,MODELS


def compact(p):
    return {k:copy.deepcopy(p.get(k)) for k in ('id','symbol','model','units','status','entry_rule','entry_time','entry',
        'initial_stop','stop','t1','remaining','exit_time','net','net_r','legs','references','realized_leg_net',
        'unrealized_net_reference','normalized_10000_realized_net','normalized_10000_unrealized_net','mark_price','mark_time',
        'gap_exposed','context_partial','actual_missing_minutes_while_held','stop_history','structure_history','failed_rebound_history')}


class CryptoView:
    def __init__(self,home=STUDIES):self.home=home;self.cache={};self.lock=threading.RLock()
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-frozen02-crypto',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')

    def result(self,folder,symbol,model):
        p=folder/symbol.replace('/','_')/model/'result.json';key=str(p)
        with self.lock:
            if key not in self.cache:
                if len(self.cache)>=2:self.cache.pop(next(iter(self.cache)))
                self.cache[key]=read(p)
            return self.cache[key]

    def snapshot(self,symbol='SOL/USD',model='0.1',trade_id=None):
        if symbol not in ASSETS or model not in MODELS:raise ValueError('Choose a saved asset/model')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        summaries=[];start=ts(s['start']);end=ts(s['end'])
        for asset in ASSETS:
            q=s['source_quality'][asset];coverage=dict(status=q['status'],reason=q.get('reason'))
            if q['status']=='available':
                missing=sum(start<=t<end for t in q['missing']);coverage.update(test_expected=(end-start)//60,
                    test_observed=(end-start)//60-missing,test_missing=missing,zero_volume_minutes=q['zero_volume_minutes'])
            for m in MODELS:summaries.append(dict(symbol=asset,model=m,coverage=coverage,**copy.deepcopy(s['results'][asset][m])))
        detail=s['results'][symbol][model];r=self.result(folder,symbol,model) if detail['status']=='complete' else None
        p=None;signal=None;rows=[]
        if r and r['trades']:
            try:ident=int(trade_id) if trade_id is not None else r['trades'][0]['id']
            except (ValueError,TypeError):raise ValueError('Choose a saved trade') from None
            p=next((p for p in r['trades'] if p['id']==ident),None)
            if not p:raise ValueError('Trade unavailable')
            signal=next((x for x in r['signals'] if x['id']==p['signal_id']),None)
            first=ts(p['entry_time'])//900*900-7200;last=(ts(p.get('exit_time') or r['last_observed'])//900+1)*900+1800
            path=folder/symbol.replace('/','_')/model/'ledger.sqlite'
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                    b=json.loads(body);item={k:b.get(k) for k in ('t','time','end','open','high','low','close','observed_minutes','stop','remaining','position_id')}
                    item['events']=[e for e in b['events'] if e.get('trade_id')==p['id']];rows.append(item)
        elif trade_id is not None:raise ValueError('No saved trade')
        evidence={k:copy.deepcopy(signal.get(k)) for k in ('time_utc','interval_end','previous_bar_time','atr','references','setup_evidence')} if signal else None
        return dict(available=True,symbol=symbol,model=model,study={k:s[k] for k in ('study_id','start','end','warmup_start',
            'assets','models','policy','btc_controls_reproduced','preserved_files_verified')},summaries=summaries,
            selected=compact(p) if p else None,trades=[compact(p) for p in r['trades']] if r else [],rows=rows,
            entry_evidence=evidence,signal_counts=copy.deepcopy(r['signal_counts']) if r else {},
            unavailable_reason=detail.get('reason'),read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,symbol,model,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Study unavailable')
        if symbol=='all':
            if name not in ('SUMMARY.csv','TRADES.csv','EXITS.csv','STUDY.json'):raise ValueError('Unknown export')
            p=folder/name
        else:
            if symbol not in ASSETS or model not in MODELS:raise ValueError('Choose saved asset/model')
            if s['results'][symbol][model]['status']!='complete':raise ValueError('Saved result unavailable')
            if name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','result.json'):raise ValueError('Unknown export')
            p=folder/symbol.replace('/','_')/model/name
        if not p.is_file():raise ValueError('Export unavailable')
        return p


CRYPTO_VIEW=CryptoView()
