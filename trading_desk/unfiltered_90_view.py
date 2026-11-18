"""Read-only original 30/90-day books, losing trades and observed cash marks."""
import copy,re
from trading_desk.btc_data import STORE,read,ts
from trading_desk.refined_entry_view import BOOKS,GROUPS
STUDIES=STORE/'unfiltered_90_studies'
PERIODS=('unfiltered90','original30')
class UnfilteredView:
    def __init__(self,home=STUDIES):self.home=home
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-unfiltered-90d',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')
    def snapshot(self,symbol='BTC/USD',model='E1',period='unfiltered90',group='all',kind='losses'):
        if (symbol,model) not in BOOKS or period not in PERIODS or group not in GROUPS or kind not in ('losses','all','open'):raise ValueError('Choose saved book, period, exposure and trade filter')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        summaries=[]
        for b in s['books']:
            p=b['periods'][period];summaries.append(dict(symbol=b['symbol'],model=b['model'],**copy.deepcopy(p)))
        book=folder/symbol.replace('/','_')/model/period;r=read(book/'result.json');rows=[]
        for p in r['trades']:
            flag=p['gap_exposed'] or p['context_partial']
            if group!='all' and flag!=(group=='flagged_gap_or_context'):continue
            if kind=='losses' and not(p['status']=='closed' and p['net']<0):continue
            if kind=='open' and not p['remaining']:continue
            rows.append(copy.deepcopy(p))
        if kind=='losses':rows.sort(key=lambda p:p['normalized_10000_realized_net'])
        else:rows.sort(key=lambda p:p['entry_time'])
        quality=r['source_quality'];start=ts(r['start']);end=ts(r['end']);expected=(end-start)//60;missing=sum(start<=t<end for t in quality['missing'])
        coverage=dict(expected=expected,observed=expected-missing,missing=missing,coverage_pct=100*(expected-missing)/expected,
            daily=[q for q in s['source_quality'][symbol]['daily'] if r['start'][:10]<=q['date_utc']<r['end'][:10]],
            zero_volume_minutes_with_warmup=quality['zero_volume_minutes'])
        return dict(available=True,symbol=symbol,model=model,period=period,group=group,kind=kind,summaries=summaries,trades=rows,
            full_book_loss_analysis=r['loss_analysis'],account=r['cash_scenario'],daily_equity=read(book/'DAILY_EQUITY.json'),coverage=coverage,
            study={k:s[k] for k in ('study_id','protocol','start','end','warmup_start','original_start','controls_reproduced','preserved_files')},
            read_only=True,orders_enabled=False,live_promoted=False)
    def export(self,symbol,model,period,name):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Saved unfiltered study unavailable')
        if symbol=='all':
            if name not in ('STUDY.json','SUMMARY.csv'):raise ValueError('Unknown export')
            path=folder/name
        else:
            if (symbol,model) not in BOOKS or period not in PERIODS:raise ValueError('Choose a saved book and period')
            allowed=('result.json','TRADES.csv','LOSSES.csv','EXITS.csv','PROTECTION.csv','SIGNALS.csv','LEDGER.csv','EQUITY.csv','EQUITY.jsonl.gz','ACCOUNT_TRADES.csv','ACCOUNT_TRADES.json','DAILY_EQUITY.json')
            if name not in allowed:raise ValueError('Unknown export')
            path=folder/symbol.replace('/','_')/model/period/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path
VIEW=UnfilteredView()
