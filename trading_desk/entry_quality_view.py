"""Read-only original-entry labels, ML diagnostics and sequential comparison."""
import copy,re
from trading_desk.btc_data import STORE,read
from trading_desk.refined_entry_view import BOOKS,GROUPS,compact
from trading_desk.entry_quality import metrics
STUDIES=STORE/'entry_quality_studies'
class QualityView:
    def __init__(self,home=STUDIES):self.home=home
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-entry-quality',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')
    def snapshot(self,symbol='BTC/USD',model='E1',phase='test',group='all'):
        if (symbol,model) not in BOOKS or phase not in ('train','validation','test') or group not in GROUPS:raise ValueError('Choose a saved book, phase and exposure group')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        def belongs(p):return bool(p and (group=='all' or bool(p['gap_exposed'] or p['context_partial'])==(group=='flagged_gap_or_context')))
        def fixed(rows):return [r for r in rows if r['phase']==phase and r['phase_label_resolved'] and (group=='all' or r['quality_group']==group)]
        def short(p):
            if not p:return None
            return {**compact(p),'entry_quality':copy.deepcopy(p.get('entry_quality'))}
        summaries=[]
        for asset,variant in BOOKS:
            b=next(b for b in s['books'] if (b['symbol'],b['model'])==(asset,variant));rows=fixed(read(folder/asset.replace('/','_')/variant/'FIXED_ENTRIES.json'))
            summaries.append(dict(symbol=asset,model=variant,fixed=metrics(rows),control=b['control'][group],filtered=b['filtered'][group],
                original_closed_dd_r=b['control']['max_closed_trade_drawdown_r'],filtered_closed_dd_r=b['filtered']['max_closed_trade_drawdown_r'],decisions=b['decisions']))
        book=folder/symbol.replace('/','_')/model;rows=fixed(read(book/'FIXED_ENTRIES.json'));changes=[]
        for c in read(book/'SEQUENTIAL_CHANGES.json'):
            a=c['original'] if belongs(c['original']) else None;b=c['refined'] if belongs(c['refined']) else None
            if a is None and b is None:continue
            changes.append(dict(time=c['time'],status=c['status'],original=short(a),filtered=short(b),
                delta_normalized_10000=(b['normalized_10000_realized_net'] if b else 0)-(a['normalized_10000_realized_net'] if a else 0)))
        seq=read(book/'test_filtered/result.json');base=read(book/'test_control/result.json');base_by_time={p['entry_time']:p for p in base['trades']}
        decisions=[]
        for p in seq['entry_quality_decisions']:
            old=base_by_time.get(p['time_utc']);d=copy.deepcopy(p)
            d['unfiltered_trade_reference']=short(old) if old else None
            d['outcome_note']='Original control result is a comparison reference, not a filled rejected trade' if old else 'No matching control entry; no counterfactual outcome invented'
            decisions.append(d)
        dataset=read(folder/'DATASET.json')
        coverage={phase:dict(total=sum(r['phase']==phase for r in dataset),unresolved=sum(r['phase']==phase and not r['phase_label_resolved'] for r in dataset)) for phase in ('train','validation','test')}
        return dict(available=True,symbol=symbol,model=model,phase=phase,group=group,summaries=summaries,fixed_entries=rows,changes=changes,label_coverage=coverage,
            decisions=decisions,patterns=read(folder/'PATTERNS.json'),model_fit=read(folder/'MODEL_BEFORE_VALIDATION_TEST.json'),
            prediction_metrics=s['prediction_metrics'],study={k:s[k] for k in ('study_id','protocol','start','end','train_end','test_start','controls_reproduced','abstention_controls_reproduced','preserved_files')},
            read_only=True,orders_enabled=False,live_promoted=False)
    def export(self,symbol,model,sequence,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Saved entry-quality study unavailable')
        if symbol=='all':
            if name not in ('STUDY.json','MODEL_BEFORE_VALIDATION_TEST.json','DATASET.json','PATTERNS.json','SUMMARY.csv','FIXED_ENTRIES.csv','DECISIONS.csv'):raise ValueError('Unknown export')
            path=folder/name
        else:
            if (symbol,model) not in BOOKS:raise ValueError('Choose a saved book')
            book=folder/symbol.replace('/','_')/model
            if name in ('FIXED_ENTRIES.json','SEQUENTIAL_CHANGES.json','DECISIONS.csv'):path=book/name
            else:
                if sequence not in ('full_control','test_control','test_filtered') or name not in ('result.json','TRADES.csv','EXITS.csv','PROTECTION.csv','SIGNALS.csv','LEDGER.csv'):raise ValueError('Unknown export')
                path=book/sequence/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path
VIEW=QualityView()
