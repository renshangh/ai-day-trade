"""Audit recorded live A/B labels on actual persisted minutes; no rule changes."""
from __future__ import annotations
import copy
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,iso,ts
from trading_desk import btc_live,sol_live
from trading_desk.btc_early_sequential import EarlySequentialReplay
from trading_desk.btc_entry_rules import four_wave_setup,entry_signal
from trading_desk.btc_shock_branches import expanded_shock_setup,independent_b1_setup
from trading_desk.btc_p1 import P1Detector,P1_RULE
from scripts.btc_structure_retest import Config


def known_targets(engine,entry,h1,t,atr):
    # Copy the resistance state: diagnostic lookups must not prune live/replay
    # state or change the original route priority, signal history or exits.
    peaks=[p for p in engine.large_peaks if p['t']>=t-7*86400 and p['high']>h1 and p['known_at']<=t]
    if not peaks:return None,None
    peak=min(peaks,key=lambda p:p['high']);zones=copy.deepcopy(engine.major).zones(entry,t)
    z=next((z for z in zones if any(x['price']==peak['high'] for x in z['members'])),None)
    if not z:return None,None
    later=next((x for x in zones if x['lower']>z['upper']),None)
    return z['lower']-.1*atr,later['lower']-.1*atr if later else None


class AuditReplay(EarlySequentialReplay):
    def __init__(self,*a,selected,**kw):
        super().__init__(*a,**kw);self.selected=selected;self.reviews={}

    def scan(self,b,can_trade):
        if can_trade and b['t'] in self.selected and b['t'] not in self.reviews:
            candidates=[]
            for route,setup in self.detector.setups():
                state=four_wave_setup(setup,b['t']) if route=='A' else expanded_shock_setup(setup,b['t'],route)
                hl=None if route=='B1' else setup.get('hl')
                h1=setup['hh']['price'] if route=='A' else self.prev['high'] if route=='B1' else setup['rebound']['high']
                target,_=known_targets(self,max(self.prev['high']+.01,b['open']),h1,b['t'],self.atr)
                context=dict(previous_bar=self.prev,minute=b,atr_before_entry=self.atr,atr_known_at=b['t']//900*900,
                    hl_unbroken_before_trigger=not setup['d_broken'] if route=='B1' else not setup['hl_broken'],
                    target=dict(price=target,known_at=b['t']) if target is not None else None)
                check=entry_signal(state,context)
                if b['low']<(hl['price'] if hl else state['d']):
                    check['qualified_candidate']=False
                    check['signal_reasons'].append('support and trigger both crossed within minute; order unknown')
                d_time=setup['lows'][-1]['time'] if route=='A' else setup['d']['time']
                already=(route,d_time,hl['time'] if hl else None) in self.emitted
                extra={}
                if route=='A':
                    p1=P1Detector();p1.p1_bars={x['t']:copy.deepcopy(x) for x in self.recent};p1.p1_now=b['t']//900*900
                    _,extra['p1']=p1.review_scope(copy.deepcopy(setup))
                elif route=='B1':extra['independent_hold']=independent_b1_setup(setup,b['t'],self.prev,d_intact=not setup['d_broken'])
                candidates.append(dict(route=route,state=state,check=check,already_emitted=already,
                    would_qualify_before_route_priority=check['qualified_candidate'] and not already,
                    setup=copy.deepcopy(setup),**extra))
            self.reviews[b['t']]=dict(previous_complete=copy.deepcopy(self.prev),entry_minute=copy.deepcopy(b),
                atr=self.atr,candidates=candidates)
        super().scan(b,can_trade)


def audit(asset,root,controller,folder):
    status=controller.status();session=status['session'];ident=session['id']
    path=root/'sessions'/ident/'observations.sqlite'
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as source:
        signals=[json.loads(b) for b, in source.execute("SELECT body FROM signals WHERE model='E1' AND json_extract(body,'$.decision')='entry' ORDER BY ref DESC LIMIT 3")][::-1]
        events=[json.loads(b) for b, in source.execute("SELECT body FROM events WHERE model='E1' ORDER BY ref,detected")]
        end=max(ts(e['time_utc']) for e in events if e.get('fraction',0)>0)+60
        records=source.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(end,)).fetchall()
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=AuditReplay(session['start'],4102444800,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),
        early_policy='E1',expanded_b=True,consume_entry_history=True,b1_independent_hold=False,
        selected={ts(s['time_utc']) for s in signals})
    digest=hashlib.sha256()
    for body,received in records:
        digest.update((body+'\n').encode());engine.minute(json.loads(body))
    trades=[]
    for s in signals:
        p=next(p for p in engine.trades if p['id']==s['trade_id'])
        replay_signal=next(x for x in engine.signals if x.get('trade_id')==s['trade_id'] and x['decision']=='entry')
        for k in ('route','routes','entry_reference','initial_stop','t1','setup_evidence'):assert replay_signal[k]==s[k],(asset,k)
        recorded_legs=[e for e in events if e.get('trade_id')==p['id'] and e.get('fraction',0)>0]
        assert [(e['time_utc'],e['price'],e['fraction'],e['type']) for e in recorded_legs]==[(l['time_utc'],l['price'],l['fraction'],l['reason']) for l in p['legs']]
        review=engine.reviews[ts(s['time_utc'])]
        gap=sum(1 for a,b in zip(records,records[1:]) if json.loads(b[0])['t']-json.loads(a[0])['t']!=60)
        trades.append(dict(asset=asset,model='E1',trade_id=p['id'],recorded_route=s['route'],entry_time=s['time_utc'],
            detected_at=s['detected_at'],known_no_earlier_than=s['interval_end'],entry=p['entry'],stop=p['initial_stop'],
            target_25=p['t1'],exit_time=p['exit_time'],legs=p['legs'],net=p['net'],references=p['references'],
            quote_reference=s['quote_reference'],context_partial=p['context_partial'],gap_exposed=p['gap_exposed'],
            setup_evidence=s['setup_evidence'],review=review,prefix_gap_transitions=gap))
    out=dict(asset=asset,session=ident,pid=status['pid'],minute_count=len(records),minute_sha256=digest.hexdigest(),
        actual_source=str(path.relative_to(ROOT)),prefix_through=iso(end),trades=trades,
        recorded_entries_and_exits_reproduced=True)
    save(folder/(asset+'_TRADES.json'),out);db.close();return out


def run():
    folder=ROOT/'reports'/('live_entry_review_'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));folder.mkdir(exist_ok=False)
    hashes=btc_live.verify_rules();before={k:dict(pid=c.status()['pid'],session=c.status()['session']['id']) for k,c in [('btc',btc_live.CONTROLLER),('sol',sol_live.CONTROLLER)]}
    results=[audit('BTC',btc_live.LIVE,btc_live.CONTROLLER,folder),audit('SOL',sol_live.HOME,sol_live.CONTROLLER,folder)]
    rows=[]
    for r in results:
        for p in r['trades']:
            rows.append({k:p[k] for k in ('asset','trade_id','recorded_route','entry_time','detected_at','entry','stop','target_25','exit_time','net')})
    with (folder/'TRADES.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    assert btc_live.verify_rules()==hashes
    for key,c in [('btc',btc_live.CONTROLLER),('sol',sol_live.CONTROLLER)]:
        s=c.status();assert dict(pid=s['pid'],session=s['session']['id'])==before[key]
    save(folder/'REVIEW.json',dict(created_at=iso(time.time()),scope='Three original BTC live trades; two SOL E1 cross-checks',
        results=results,p1_rule=P1_RULE,workers=before,rules=hashes,orders_enabled=False,
        live_changed=False,monthly_replay=False))
    print(str(folder))
    for r in results:
        for p in r['trades']:
            print(json.dumps(dict(asset=p['asset'],trade=p['trade_id'],route=p['recorded_route'],entry=p['entry'],time=p['entry_time'],net=p['net'],
                checks=[dict(route=x['route'],qualified=x['would_qualify_before_route_priority'],reasons=x['check']['signal_reasons'],
                    p1_kept=x.get('p1',{}).get('p1_low_count'),p1_pass=x.get('p1',{}).get('passed'),
                    independent_hold=x.get('independent_hold',{}).get('setup_passed')) for x in p['review']['candidates']])) )


if __name__=='__main__':run()
