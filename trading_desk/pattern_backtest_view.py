"""Read-only saved cross-asset research, no provider or broker requests."""
import copy
import json
import re
import sqlite3
import threading
from trading_desk.btc_data import read,ts
from trading_desk.pattern_backtest import BACKTESTS,grid


def compact(p):
    keys=('id','symbol','status','entry_time','entry','initial_stop','stop','t1','remaining','exit_time','net','net_r',
        'legs','references','entry_rule','pattern_match','realized_leg_net','unrealized_net_reference',
        'normalized_10000_realized_net','normalized_10000_unrealized_net','actual_missing_minutes_while_held',
        'gap_exposed','context_partial','mark_time','mark_price','stop_history','structure_history','failed_rebound_history')
    return {k:copy.deepcopy(p.get(k)) for k in keys}


class BacktestView:
    def __init__(self,home=BACKTESTS):self.home=home;self.cache={};self.lock=threading.RLock()

    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-patterns-30d',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')

    def result(self,folder,symbol):
        path=folder/symbol.replace('/','_')/'result.json';key=str(path)
        with self.lock:
            if key not in self.cache:
                if len(self.cache)>=2:self.cache.pop(next(iter(self.cache)))
                self.cache[key]=read(path)
            return self.cache[key]

    def snapshot(self,symbol=None,trade_id=None):
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        symbol=symbol or next((x for x in s['symbols'] if x!='BTC/USD' and
            s['results'][x]['status']=='complete' and s['results'][x]['summary']['trades']),
            next((x for x in s['symbols'] if x!='BTC/USD'),'BTC/USD'))
        if symbol not in s['symbols']:raise ValueError('Choose a saved study symbol')
        calendar=read(folder/'data/CALENDAR.json');rows=[];summaries=[];start=ts(s['start']);end=ts(s['end'])
        expected_stock=len(grid(calendar,start,end))
        for name in s['symbols']:
            item=copy.deepcopy(s['results'][name]);q=s['source_quality'][name]
            coverage=dict(status=q['status'],reason=q.get('reason'),price_basis=q.get('price_basis','frozen BTC source'),
                split_events=q.get('split_events',[]),adjustment_note=q.get('adjustment_note'))
            if q['status']=='available':
                expected=(end-start)//60 if name=='BTC/USD' else expected_stock
                missing=sum(start<=t<end for t in q['missing'])
                coverage.update(test_expected=expected,test_observed=expected-missing,test_missing=missing,
                    warmup_and_test_observed=q['observed'],split_check=q.get('split_check'))
            summaries.append(dict(symbol=name,**item,coverage=coverage))
        detail=s['results'][symbol]
        r=self.result(folder,symbol) if detail['status']=='complete' else None
        p=None;signal=None
        if r and r['trades']:
            try:ident=int(trade_id) if trade_id is not None else r['trades'][0]['id']
            except (ValueError,TypeError):raise ValueError('Choose a saved trade') from None
            p=next((p for p in r['trades'] if p['id']==ident),None)
            if not p:raise ValueError('Trade unavailable for this symbol')
            signal=next((x for x in r['signals'] if x['id']==p['signal_id']),None)
            first=ts(p['entry_time'])//900*900-7200;last=(ts(p.get('exit_time') or r['last_observed'])//900+1)*900+1800
            dbpath=folder/symbol.replace('/','_')/'ledger.sqlite'
            with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
                for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                    b=json.loads(body);item={k:b.get(k) for k in ('t','time','end','open','high','low','close','observed_minutes','stop','remaining','position_id')}
                    item['events']=[e for e in b['events'] if e.get('trade_id')==p['id']];rows.append(item)
        elif trade_id is not None:raise ValueError('No saved trade for this symbol')
        selected_signal={k:copy.deepcopy(signal.get(k)) for k in ('time_utc','interval_end','previous_bar_time','atr','references','setup_evidence')} if signal else None
        return dict(available=True,study={k:s[k] for k in ('study_id','start','end','warmup_start','symbols','policy',
            'library_sha256','watchlist_selection_asof','preserved_files_verified')},summaries=summaries,symbol=symbol,
            trades=[compact(p) for p in r['trades']] if r else [],selected=compact(p) if p else None,
            entry_evidence=selected_signal,rows=rows,decisions=copy.deepcopy(r['pattern_decisions']) if r else [],
            signal_counts=copy.deepcopy(r['signal_counts']) if r else {},unavailable_reason=detail.get('reason'),
            read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,symbol,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Study unavailable')
        if symbol=='all':
            if name not in ('SUMMARY.csv','TRADES.csv','EXITS.csv','STUDY.json','LIBRARY.json'):raise ValueError('Unknown combined export')
            path=folder/name
        else:
            if symbol not in s['symbols'] or s['results'][symbol]['status']!='complete':raise ValueError('Symbol unavailable')
            if name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv','PATTERN_DECISIONS.csv','result.json'):
                raise ValueError('Unknown symbol export')
            path=folder/symbol.replace('/','_')/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path


BACKTEST_VIEW=BacktestView()
