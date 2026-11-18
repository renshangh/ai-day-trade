"""Saved-only parent-memory research. No worker, quote or order operations."""
from __future__ import annotations
import copy
import json
import re
import sqlite3

from trading_desk.btc_data import read,ts
from trading_desk.btc_parent_five_view import ParentFiveView

SEQUENCES=('original','cleared_combined','retained_combined','cleared_standalone','retained_standalone')


def dollar_drawdown(trades):
    balance=peak=dd=0.0
    for p in trades:
        if p['status']!='closed':continue
        balance+=p['net'];peak=max(peak,balance);dd=max(dd,peak-balance)
    return dd


class ParentMemoryView(ParentFiveView):
    def __init__(self,store=None):
        if store is None:super().__init__()
        else:super().__init__(store)
        self.dd_cache={}

    def current(self):
        ident=read(self.store/'parent_memory_studies/ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-PH5-memory',ident):return None,None
        folder=self.store/'parent_memory_studies'/ident
        return folder,read(folder/'STUDY.json')

    def selection(self,model,sequence):
        if model not in ('0.1','E1','E2') or sequence not in SEQUENCES:
            raise ValueError('Choose a saved memory-comparison model/sequence')
        folder,s=self.current()
        if not s or s.get('status')!='complete':return folder,s,None
        p=folder/model/sequence/'result.json'
        with self.lock:
            if str(p) not in self.cache:
                if len(self.cache)>=3:self.cache.pop(next(iter(self.cache)))
                self.cache[str(p)]=read(p)
            result=self.cache[str(p)]
        return folder,s,result

    @staticmethod
    def case_compact(case):
        r=copy.deepcopy(case)
        r['trades']=[ParentFiveView.compact(p)|{k:copy.deepcopy(p[k]) for k in (
            'entry_received_at','mark_time','mark_price','realized_leg_net','unrealized_net','marked_net') if k in p}
            for p in case['trades']]
        r.pop('bars',None)
        return r

    def snapshot(self,model='0.1',sequence='retained_combined',trade_id=None):
        folder,s,r=self.selection(model,sequence)
        if r is None:return dict(available=False,read_only=True,orders_enabled=False)
        trades=r['trades']
        try:
            ident=int(trade_id) if trade_id is not None else next(
                (p['id'] for p in trades if p['entry_rule']=='PH5'),trades[0]['id'] if trades else None)
        except (TypeError,ValueError):raise ValueError('Choose a saved trade') from None
        p=next((p for p in trades if p['id']==ident),None)
        if trade_id is not None and p is None:raise ValueError('Trade not found')
        rows=[];five=[]
        if p:
            first=ts(p['entry_time'])//900*900-3600
            if p.get('parent_five'):first=min(first,p['parent_five']['setup']['parent']['bar_time']-900)
            last=(ts(p.get('exit_time') or r['end'])//900+2)*900
            path=folder/model/sequence/'ledger.sqlite'
            with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
                for body, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(first,last)):
                    row=json.loads(body)
                    rows.append(dict(t=row['t'],end=row['end'],open=row['open'],high=row['high'],
                        low=row['low'],close=row['close'],observed_minutes=row['observed_minutes'],
                        stop=row.get('stop') if row.get('position_id')==p['id'] else None,
                        events=[e for e in row['events'] if e.get('trade_id')==p['id']]))
            five=self.five_bars(ts(p['entry_time'])//900*900-1800,ts(p['entry_time'])//900*900+1800)
        c=read(folder/'CASE.json')['models'][model]
        case=dict(cleared=self.case_compact(c['cleared']),retained=self.case_compact(c['retained']),
            reentry=c['reentry'],position_at_0320=c['position_at_0320'],
            prefix_verified=c['prefix_verified'],first_exit_unchanged=c['first_exit_unchanged'])
        public={k:v for k,v in s.items() if k not in ('changes',)}
        # Dollar drawdown must accompany R: retaining a deeper D changes the R
        # denominator even though the risk formula/thresholds were not changed.
        with self.lock:
            if s['study_id'] not in self.dd_cache:
                dd={}
                for m in ('0.1','E1','E2'):
                    dd[m]={}
                    for mode in SEQUENCES:
                        _,_,result=self.selection(m,mode)
                        dd[m][mode]=dollar_drawdown(result['trades'])
                self.dd_cache={s['study_id']:dd}
            dd=self.dd_cache[s['study_id']]
        prior=next((q for q in reversed(trades) if p and ts(q['entry_time'])<ts(p['entry_time'])),None)
        return dict(available=True,read_only=True,orders_enabled=False,live_promoted=False,
            model=model,sequence=sequence,study=public,dollar_drawdowns=dd,
            trades=[self.compact(p) for p in trades],selected=self.compact(p) if p else None,
            previous_trade=self.compact(prior) if prior else None,rows=rows,five=five,
            signals=[s for s in r['signals'] if s['route']=='PH5'],case=case,
            changes=s['changes'][model].get(sequence))


PARENT_MEMORY_VIEW=ParentMemoryView()
