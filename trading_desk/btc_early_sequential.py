"""Opt-in E1/E2 sequential overlays on release 0.1, with unchanged entry rules."""
import copy
import json

from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_data import iso,ts
from scripts.audit_btc_release01_early_failure import completed_scan


class EarlySequentialReplay(FailedReboundReplay):
    def __init__(self,*args,early_policy,**kwargs):
        if early_policy not in ('E1','E2'):raise ValueError('Choose E1 or E2')
        super().__init__(*args,**kwargs)
        self.early_policy=early_policy
        self.policy='release-0.1-plus-'+early_policy+'-sequential-v1'

    @staticmethod
    def compact(bar,complete):
        return dict(time=iso(bar['t']),end=iso(bar['t']+900),
            **{k:bar[k] for k in ('open','high','low','close','observed_minutes')},
            complete=complete)

    def open_signal(self,b,s):
        super().open_signal(b,s)
        if self.position:
            self.position['early_exit_bars']=[self.compact(self.prev,self.prev['observed_minutes']==15)]

    def complete(self):
        had=bool(self.minutes)
        super().complete()
        if not had or self.position is None:return
        p=self.position;bar=self.prev;known=bar['t']+900
        complete=[m['t'] for m in self.minutes]==list(range(bar['t'],known,60))
        history=p.setdefault('early_exit_bars',[])
        if not history or ts(history[-1]['time'])!=bar['t']:
            history.append(self.compact(bar,complete))
        scan=completed_scan(dict(entry=p,bars=history,exit_time=iso(self.end+60)),cutoff=known)
        if scan['trace']:
            p.setdefault('early_exit_trace',[]).append(copy.deepcopy(scan['trace'][-1]))
        signal=scan['A' if self.early_policy=='E1' else 'B']
        if signal and ts(signal['confirmed_at'])==known:
            p['early_exit_pending']=copy.deepcopy(signal)
            self.event('early_exit_confirmed',known,trade_id=p['id'],candidate=self.early_policy,
                signal_bar=signal['signal_bar'],execution_at=signal['confirmed_at'],
                reason='complete 15m E1/E2 signal; next exact observed minute opening only')
        row=self.db.execute('SELECT body FROM ledger WHERE t=?',(bar['t'],)).fetchone()
        if row:
            body=json.loads(row[0]);body['events'].extend(self.events)
            body['early_exit_state']=dict(candidate=self.early_policy,
                trace=copy.deepcopy(scan['trace'][-1]) if scan['trace'] else None,
                pending=copy.deepcopy(p.get('early_exit_pending')))
            self.db.execute('UPDATE ledger SET body=? WHERE t=?',
                (json.dumps(body,ensure_ascii=False),bar['t']))
        self.events=[]

    def additional_exit_candidates(self,b):
        options=super().additional_exit_candidates(b)
        p=self.position;signal=p.get('early_exit_pending')
        if not signal:return options
        due=ts(signal['confirmed_at'])
        if b['t']>due:
            self.event('early_exit_observation_missing',b['t'],trade_id=p['id'],
                candidate=self.early_policy,missed_at=signal['confirmed_at'],
                reason='exact next-minute opening absent; signal not filled or carried forward')
            p.pop('early_exit_pending',None)
        elif b['t']==due:
            # Keep existing opening-time protection priority. A known opening
            # still precedes unresolved within-minute thresholds and targets.
            options.append(dict(reason=self.early_policy.lower()+'_exit_remaining',
                price=b['open'],phase=0,priority=25,candidate=self.early_policy,
                confirmed_at=signal['confirmed_at'],signal=copy.deepcopy(signal),
                price_basis='exact following observed minute open; complete-bar direction gates',
                policy=self.policy))
        return options

    def finish(self):
        result=super().finish()
        for p in result['trades']:
            p.pop('early_exit_bars',None)
        result['sequential_exit_policy']=self.early_policy
        return result
