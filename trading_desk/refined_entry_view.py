"""Read-only saved entry experiment; independent of all live worker imports."""
import copy
import re
import threading
from trading_desk.btc_data import STORE,read,ts

STUDIES=STORE/'refined_entry_studies'
BOOKS=(('BTC/USD','0.1'),('BTC/USD','E1'),('BTC/USD','E2'),('SOL/USD','E1'))
GROUPS=('all','no_flagged_gap','flagged_gap_or_context')


def compact(p):
    if p is None:return None
    return {k:copy.deepcopy(p.get(k)) for k in ('id','status','entry_time','entry_rule','entry','initial_stop','stop','t1',
        'exit_time','remaining','legs','net','references','gap_exposed','context_partial','realized_leg_net',
        'unrealized_net_reference','normalized_10000_realized_net','normalized_10000_unrealized_net','entry_refinement','p1')}


class RefinedView:
    def __init__(self,home=STUDIES):self.home=home;self.cache={};self.lock=threading.RLock()
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-refined-AB',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')

    def changes(self,folder,symbol,model):
        path=folder/symbol.replace('/','_')/model/'CHANGES.json';key=str(path)
        with self.lock:
            if key not in self.cache:
                if len(self.cache)>=2:self.cache.pop(next(iter(self.cache)))
                self.cache[key]=read(path)
            return self.cache[key]

    def snapshot(self,symbol='BTC/USD',model='E1',group='all'):
        if (symbol,model) not in BOOKS or group not in GROUPS:raise ValueError('Choose saved BTC 0.1/E1/E2 or SOL E1 and a gap group')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        def belongs(p):
            flagged=bool(p and (p['gap_exposed'] or p['context_partial']))
            return bool(p and (group=='all' or flagged==(group=='flagged_gap_or_context')))
        rows=[]
        for index,c in enumerate(self.changes(folder,symbol,model)):
            a=c['original'] if belongs(c['original']) else None;b=c['refined'] if belongs(c['refined']) else None
            if a is None and b is None:continue
            rows.append(dict(index=index,time=c['time'],status=c['status'],original=compact(a),refined=compact(b),
                delta_realized=(b['realized_leg_net'] if b else 0)-(a['realized_leg_net'] if a else 0),
                delta_normalized_10000=(b['normalized_10000_realized_net'] if b else 0)-(a['normalized_10000_realized_net'] if a else 0),
                group_note='One side excluded by data-exposure partition' if (a is None and c['original'] is not None) or (b is None and c['refined'] is not None) else None,
                original_entry_review=copy.deepcopy(c['original_entry_review'])))
        summaries=[]
        for book in s['books']:
            a=book['original'][group];b=book['refined'][group]
            summaries.append(dict(symbol=book['symbol'],model=book['model'],original=a,refined=b,
                delta_realized=b['realized_net']-a['realized_net'],
                delta_normalized_10000=b['normalized_10000_realized']-a['normalized_10000_realized'],
                original_max_dd_r=book['original']['max_closed_trade_drawdown_r'],refined_max_dd_r=book['refined']['max_closed_trade_drawdown_r'],
                all_group_change_counts=book['change_counts']))
        source=read(folder/symbol.replace('/','_')/model/'original/result.json')['source_quality']
        missing=sum(ts(s['start'])<=t<ts(s['end']) for t in source['missing'])
        return dict(available=True,symbol=symbol,model=model,group=group,changes=rows,summaries=summaries,
            study={k:s[k] for k in ('study_id','start','end','warmup_start','protocol','controls_reproduced','sizing','costs','gaps','preserved_files')},
            coverage=dict(missing_test_minutes=missing,expected_test_minutes=(ts(s['end'])-ts(s['start']))//60),
            read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,symbol,model,sequence,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Saved study unavailable')
        if symbol=='all':
            if name not in ('STUDY.json','SUMMARY.csv','CHANGES.csv','TRADES.csv','EXITS.csv'):raise ValueError('Unknown export')
            path=folder/name
        else:
            if (symbol,model) not in BOOKS:raise ValueError('Choose a saved book')
            if name in ('CHANGES.csv','CHANGES.json'):path=folder/symbol.replace('/','_')/model/name
            else:
                if sequence not in ('original','refined') or name not in ('result.json','TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv'):raise ValueError('Unknown export')
                path=folder/symbol.replace('/','_')/model/sequence/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path


VIEW=RefinedView()
