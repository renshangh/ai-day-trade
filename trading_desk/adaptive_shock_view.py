"""Saved adaptive-shock/chronological-calibration research, GET-only."""
import re
from pathlib import Path
from trading_desk.btc_data import STORE,ROOT,read
from trading_desk.refined_entry_view import BOOKS,GROUPS,compact
from scripts.retest_refined_entries import compare
STUDIES=STORE/'adaptive_shock_studies'

class AdaptiveView:
    def __init__(self,home=STUDIES):self.home=home
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-adaptive-shock',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')
    def snapshot(self,symbol='BTC/USD',model='E1',phase='test',group='all'):
        if (symbol,model) not in BOOKS or phase not in ('full','test') or group not in GROUPS:raise ValueError('Choose saved book, full/test phase and exposure group')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        book=folder/symbol.replace('/','_')/model;prefix='' if phase=='full' else 'test_';name='weighted' if phase=='full' else 'selected'
        old=read(book/(prefix+'atr_only')/'result.json');new=read(book/(prefix+name)/'result.json')
        def belongs(p):
            flag=bool(p and (p['gap_exposed'] or p['context_partial']))
            return bool(p and (group=='all' or flag==(group=='flagged_gap_or_context')))
        changes=[]
        def saved_trade(p):
            if p is None:return None
            return {**compact(p),'adaptive_shock':p.get('adaptive_shock')}
        for c in compare(old,new):
            a=c['original'] if belongs(c['original']) else None;b=c['refined'] if belongs(c['refined']) else None
            if a is None and b is None:continue
            changes.append(dict(time=c['time'],status=c['status'],original=saved_trade(a),alternative=saved_trade(b),
                delta_normalized_10000=(b['normalized_10000_realized_net'] if b else 0)-(a['normalized_10000_realized_net'] if a else 0)))
        summaries=[]
        for b in s['books']:
            summaries.append(dict(symbol=b['symbol'],model=b['model'],sequences={n:v[group] for n,v in b[phase].items()},
                closed_drawdown_r={n:v['max_closed_trade_drawdown_r'] for n,v in b[phase].items()},selection=b['selection']))
        source=(ROOT/s['source_study']).resolve()
        if not source.is_relative_to((STORE/'crypto_transfer_studies').resolve()):raise ValueError('Invalid saved source')
        frozen=[]
        for asset,variant in BOOKS:
            ref=read(source/asset.replace('/','_')/variant/'result.json')
            frozen.append(dict(symbol=asset,model=variant,normalized_10000_realized=ref['summary']['all']['normalized_10000_realized']))
        return dict(available=True,symbol=symbol,model=model,phase=phase,group=group,comparison=name,changes=changes,summaries=summaries,frozen_references=frozen,
            calibration=read(book/'CALIBRATION.json'),cases=[{k:v for k,v in c.items() if k!='source_minutes'} for c in s['cases']],
            study={k:s[k] for k in ('study_id','settings','start','end','train_end','test_start','protocol','ml_protocol','controls_reproduced','preserved_files')},
            read_only=True,orders_enabled=False,live_promoted=False)
    def export(self,symbol,model,sequence,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Saved comparison unavailable')
        if symbol=='all':
            if name not in ('STUDY.json','SUMMARY.csv','WEIGHT_CHANGES.csv','CALIBRATION.json','BTC_USD_CASE.json','SOL_USD_CASE.json'):raise ValueError('Unknown export')
            path=folder/name
        else:
            if (symbol,model) not in BOOKS:raise ValueError('Choose saved book')
            book=folder/symbol.replace('/','_')/model
            if name in ('WEIGHT_CHANGES.json','CALIBRATION.json','SELECTION_BEFORE_TEST.json'):path=book/name
            else:
                if sequence not in ('uniform3','atr_only','weighted','test_uniform3','test_atr_only','test_weighted','test_selected') or name not in ('result.json','TRADES.csv','EXITS.csv','SIGNALS.csv','PROTECTION.csv','LEDGER.csv'):raise ValueError('Unknown export')
                path=book/sequence/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path
VIEW=AdaptiveView()
