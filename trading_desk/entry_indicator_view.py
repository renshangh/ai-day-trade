"""Read-only saved VWAP/MA ML comparisons and matched coverage controls."""
import re
from trading_desk.btc_data import STORE,read
from trading_desk.refined_entry_view import BOOKS,GROUPS,compact
from trading_desk.entry_quality import metrics
from trading_desk.entry_indicator_ml import ARMS
STUDIES=STORE/'entry_indicator_studies'
PAIRS={'original_ml':None,'matched_ma':'original_ml','plus_ma':'matched_ma','matched_all':'original_ml','plus_ma_vwap':'matched_all'}
class IndicatorView:
    def __init__(self,home=STUDIES):self.home=home
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-entry-indicators',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')
    def snapshot(self,symbol='BTC/USD',model='E1',arm='plus_ma_vwap',phase='test',group='all'):
        if (symbol,model) not in BOOKS or arm not in ARMS or phase not in ('train','validation','test') or group not in GROUPS:raise ValueError('Choose saved book, arm, phase and data group')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        def fixed(rows):return [r for r in rows if r['phase']==phase and r['phase_label_resolved'] and (group=='all' or r['quality_group']==group)]
        def belongs(p):return bool(p and (group=='all' or bool(p['gap_exposed'] or p['context_partial'])==(group=='flagged_gap_or_context')))
        def short(p):return None if p is None else {**compact(p),'entry_quality':p.get('entry_quality')}
        summaries=[];fixed_summaries=[]
        for asset,variant in BOOKS:
            b=next(b for b in s['books'] if (b['symbol'],b['model'])==(asset,variant))
            summaries.append(dict(symbol=asset,model=variant,control=b['control'][group],arms={k:v['summary'][group] for k,v in b['arms'].items()},
                drawdown_r={k:v['summary']['max_closed_trade_drawdown_r'] for k,v in b['arms'].items()},decisions={k:v['decisions'] for k,v in b['arms'].items()}))
        book=folder/symbol.replace('/','_')/model
        for a in ARMS:fixed_summaries.append(dict(arm=a,metrics=metrics(fixed(read(book/('FIXED_'+a+'.json'))))))
        changes=[]
        for c in read(book/arm/'CHANGES.json'):
            a=c['original'] if belongs(c['original']) else None;b=c['refined'] if belongs(c['refined']) else None
            if a is None and b is None:continue
            changes.append(dict(time=c['time'],status=c['status'],original=short(a),alternative=short(b),
                delta_normalized_10000=(b['normalized_10000_realized_net'] if b else 0)-(a['normalized_10000_realized_net'] if a else 0)))
        result=read(book/arm/'result.json');models=read(folder/'MODELS_BEFORE_VALIDATION_TEST.json')
        return dict(available=True,symbol=symbol,model=model,arm=arm,phase=phase,group=group,pair=PAIRS[arm],summaries=summaries,fixed_summaries=fixed_summaries,
            fixed_entries=fixed(read(book/('FIXED_'+arm+'.json'))),changes=changes,decisions=result['indicator_decisions'],model_fits=models,
            prediction_metrics=s['prediction_metrics'],vwap_sources=s['vwap_sources'],
            study={k:s[k] for k in ('study_id','protocol','start','end','train_end','test_start','controls_reproduced','original_ml_reproduced','preserved_files')},
            read_only=True,orders_enabled=False,live_promoted=False)
    def export(self,symbol,model,arm,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Saved indicator comparison unavailable')
        if symbol=='all':
            allowed=('STUDY.json','MODELS_BEFORE_VALIDATION_TEST.json','VWAP_SOURCE_AUDIT.json','SUMMARY.csv','FIXED_ENTRIES.csv','DECISIONS.csv')+tuple('DATASET_'+a+'.json' for a in ARMS)
            if name not in allowed:raise ValueError('Unknown export')
            path=folder/name
        else:
            if (symbol,model) not in BOOKS or arm not in ARMS:raise ValueError('Choose saved book and arm')
            book=folder/symbol.replace('/','_')/model
            if name=='FIXED_ENTRIES.json':path=book/('FIXED_'+arm+'.json')
            else:
                if name not in ('CHANGES.json','result.json','TRADES.csv','EXITS.csv','SIGNALS.csv','PROTECTION.csv','LEDGER.csv'):raise ValueError('Unknown export')
                path=book/arm/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path
VIEW=IndicatorView()
