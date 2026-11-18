"""Saved SOL-only model research and real chronology; no worker side effects."""
from contextlib import closing
import json,re,sqlite3
from trading_desk.btc_data import ROOT,read,ts
from scripts.retest_refined_entries import compare

HOME=ROOT/'trading_records/sol_structure/studies'
ARMS=('original_e1','sol_net_shock','independent_hold','sol_01')
PHASES=('full30','first14','next7','final9')
TRADE_FIELDS=('id','status','entry','entry_time','entry_interval_end','initial_stop','stop','t1','remaining','initial_risk',
    'entry_rule','references','legs','exit_time','net','net_r','realized_leg_net','normalized_10000_realized_net',
    'normalized_10000_unrealized_net','gap_exposed','context_partial','actual_missing_minutes_while_held')


def brief(p):
    return {k:p[k] for k in TRADE_FIELDS if k in p} if p else None


class View:
    def __init__(self,root=HOME):self.root=root
    def current(self):
        ident=read(self.root/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-sol01',ident):return None,None
        folder=self.root/ident;return folder,read(folder/'STUDY.json')
    def snapshot(self,arm='sol_01',phase='full30',trade_id=None):
        if arm not in ARMS or phase not in PHASES:raise ValueError('Choose a saved SOL arm and phase')
        f,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,orders_enabled=False)
        r=read(f/phase/arm/'result.json');old=read(f/phase/'original_e1/result.json');rows=[];selected=None
        if trade_id is not None:
            try:ident=int(trade_id)
            except (ValueError,TypeError):raise ValueError('Choose a saved SOL trade') from None
            selected=next((p for p in r['trades'] if p['id']==ident),None)
            if selected is None:raise ValueError('Choose a saved SOL trade')
            start=ts(selected['entry_time'])//900*900-3600;end=ts(selected.get('exit_time') or r['last_observed'])//900*900+1800
            with closing(sqlite3.connect((f/phase/arm/'ledger.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
                rows=[{k:v for k,v in json.loads(b).items() if k in ('time','end','t','open','high','low','close','observed_minutes','l1_price','l2_price','stop','remaining','events')} for b, in db.execute('SELECT body FROM ledger WHERE t>=? AND t<? ORDER BY t',(start,end))]
            signal=next((s for s in r['signals'] if s.get('trade_id')==ident and s['decision']=='entry'),{})
            selected={**brief(selected),**{k:selected[k] for k in ('stop_history','case_exit_evidence') if k in selected},'b1_confirmation':signal.get('b1_confirmation')}
        changes=[{**c,'original':brief(c['original']),'refined':brief(c['refined'])} for c in compare(old,r)]
        return dict(available=True,symbol='SOL/USD',version='0.1',status='research_candidate_not_live',arm=arm,phase=phase,
            study_id=s['study_id'],protocol=s['protocol'],start=r['start'],end=r['end'],source_quality=s['source_quality'],
            summaries=[p for p in s['books'] if p['phase']==phase],trades=[brief(p) for p in r['trades']],account={k:v for k,v in r['account'].items() if k!='account_trades'},
            loss_analysis=r['loss_analysis'],changes=changes,selected_trade=selected,rows=rows,
            tape=read(f/'TAPE.json'),control_reproduced=s['control_reproduced'],orders_enabled=False,live_promoted=False)
    def export(self,phase,arm,name):
        f,s=self.current()
        if not s or s['status']!='complete':raise ValueError('SOL study unavailable')
        if name in ('STUDY.json','SUMMARY.csv','TAPE.csv','CHANGES.csv'):return f/name
        if phase not in PHASES or arm not in ARMS or name not in ('TRADES.csv','EXITS.csv','PROTECTION.csv','SIGNALS.csv','LEDGER.csv','EQUITY.csv','result.json'):
            raise ValueError('Choose a saved SOL export')
        return f/phase/arm/name


VIEW=View()
