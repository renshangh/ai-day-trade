"""Read-only independent failed-follow-through and net-shock study access."""
import copy
import re
from trading_desk.btc_data import STORE,read
from trading_desk.refined_entry_view import BOOKS,GROUPS,compact

STUDIES=STORE/'followthrough_shock_studies'


class FollowthroughView:
    def __init__(self,home=STUDIES):self.home=home
    def current(self):
        ident=read(self.home/'ACTIVE.json',{}).get('study_id')
        if not isinstance(ident,str) or not re.fullmatch(r'\d{8}T\d{6}Z-followthrough-shock',ident):return None,None
        folder=self.home/ident;return folder,read(folder/'STUDY.json')

    def snapshot(self,symbol='BTC/USD',model='E1',policy='F1',group='all'):
        if (symbol,model) not in BOOKS or policy not in ('F1','F2') or group not in GROUPS:raise ValueError('Choose saved book, F1/F2 and gap group')
        folder,s=self.current()
        if not s or s['status']!='complete':return dict(available=False,read_only=True,orders_enabled=False)
        book=folder/symbol.replace('/','_')/model
        rows=[x for x in read(book/'EXITS.json') if x['policy']==policy and (group=='all' or x['group']==group)]
        def belongs(p):
            flagged=bool(p and (p['gap_exposed'] or p['context_partial']))
            return bool(p and (group=='all' or flagged==(group=='flagged_gap_or_context')))
        changes=[]
        for c in read(book/'SHOCK_CHANGES.json'):
            a=c['original'] if belongs(c['original']) else None;b=c['refined'] if belongs(c['refined']) else None
            if a is None and b is None:continue
            changes.append(dict(time=c['time'],status=c['status'],original=compact(a),steeper=compact(b),
                delta_normalized_10000=(b['normalized_10000_realized_net'] if b else 0)-(a['normalized_10000_realized_net'] if a else 0)))
        summaries=[]
        for b in s['books']:
            summaries.append(dict(symbol=b['symbol'],model=b['model'],exit=b['exit_summaries'][policy][group],
                shock_original=b['shock_original'][group],shock_steeper=b['shock_steeper'][group],
                shock_dd_original=b['shock_original']['max_closed_trade_drawdown_r'],shock_dd_steeper=b['shock_steeper']['max_closed_trade_drawdown_r'],
                change_counts=b['shock_change_counts'],old_episodes=b['old_2atr_episodes'],new_episodes=b['new_3atr_episodes']))
        return dict(available=True,symbol=symbol,model=model,policy=policy,group=group,trades=rows,shock_changes=changes,summaries=summaries,
            cases=copy.deepcopy(s['cases']),study={k:s[k] for k in ('study_id','start','end','exit_protocol','shock_protocol','controls_reproduced','preserved_files')},
            read_only=True,orders_enabled=False,live_promoted=False)

    def export(self,symbol,model,name,sequence='steeper'):
        folder,s=self.current()
        if not s or s['status']!='complete':raise ValueError('Saved study unavailable')
        if symbol=='all':
            if name not in ('STUDY.json','EXIT_SUMMARY.csv','EXIT_TRADES.csv','SHOCK_CHANGES.csv','BTC_USD_0445.json','SOL_USD_0445.json'):raise ValueError('Unknown export')
            path=folder/name
        else:
            if (symbol,model) not in BOOKS:raise ValueError('Choose a saved book')
            base=folder/symbol.replace('/','_')/model
            if name in ('EXITS.json','SHOCK_CHANGES.json'):path=base/name
            else:
                if sequence not in ('shock_control','steeper') or name not in ('result.json','TRADES.csv','EXITS.csv','PROTECTION.csv','LEDGER.csv','SIGNALS.csv'):raise ValueError('Unknown export')
                path=base/sequence/name
        if not path.is_file():raise ValueError('Export unavailable')
        return path


VIEW=FollowthroughView()
