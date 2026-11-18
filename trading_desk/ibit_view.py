"""Saved IBIT RTH research only; no live controller or order routing."""
from contextlib import closing
import json,re,sqlite3
from trading_desk.btc_data import ROOT,read,ts
from trading_desk.sol01_view import brief

HOME=ROOT/'trading_records/ibit_structure/studies'


class View:
    def __init__(self,root=HOME):self.root=root
    def current(self):
        ident=read(self.root/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-ibit-rth',ident):return None,None
        f=self.root/ident;return f,read(f/'STUDY.json')
    def snapshot(self,model='E1',arm='session_adapted',trade_id=None):
        if model not in ('0.1','E1','E2') or arm not in ('exact_control','session_adapted'):raise ValueError('Choose an IBIT model and session-clock arm')
        f,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,orders_enabled=False)
        r=read(f/arm/model/'result.json');selected=None;rows=[]
        if trade_id is not None:
            try:ident=int(trade_id)
            except (TypeError,ValueError):raise ValueError('Choose an IBIT trade') from None
            selected=next((p for p in r['trades'] if p['id']==ident),None)
            if selected is None:raise ValueError('Choose an IBIT trade')
            a=ts(selected['entry_time'])//900*900-3600;b=ts(selected.get('exit_time') or r['last_observed'])//900*900+1800
            with closing(sqlite3.connect((f/arm/model/'ledger.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
                rows=[{k:v for k,v in json.loads(raw).items() if k in ('time','end','t','open','high','low','close','observed_minutes','l1_price','l2_price','stop','remaining','events')} for raw, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(a,b))]
            selected={**brief(selected),**{k:selected[k] for k in ('stop_history','case_exit_evidence') if k in selected}}
        return dict(available=True,symbol='IBIT',model=model,arm=arm,start=s['start'],end=s['end'],policy=s['policy'],
            holding_assumption=s['holding_assumption'],summaries=s['books'],test_expected=s['test_expected'],test_observed=s['test_observed'],
            quality=s['quality'],trades=[brief(p) for p in r['trades']],selected_trade=selected,rows=rows,
            account={k:v for k,v in r['account'].items() if k!='account_trades'},signals=[{k:v for k,v in q.items() if k in ('id','route','decision','time_utc','entry_reference','initial_stop','t1','references','risk_reason','signal_reasons','trade_id')} for q in r['signals']],
            resistance_diagnostics=r['resistance_diagnostics'],target_reviews=r['target_reviews'],orders_enabled=False,live_promoted=False)
    def export(self,arm,model,name):
        f,s=self.current()
        if not s or s['status']!='complete':raise ValueError('IBIT result unavailable')
        if name in ('STUDY.json','SUMMARY.csv'):return f/name
        if arm not in ('exact_control','session_adapted') or model not in ('0.1','E1','E2') or name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','SIGNALS.csv','LEDGER.csv','EQUITY.csv','result.json'):
            raise ValueError('Choose a saved IBIT export')
        return f/arm/model/name


VIEW=View()
