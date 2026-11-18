"""Same-source full sequences: reproduced P1+C controls vs parent-only C filter."""
from __future__ import annotations
import copy
import csv
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_engine import export_csv
from trading_desk.btc_parent_filter import POLICY,ParentFilteredBaselineReplay,ParentFilteredEarlyReplay
from trading_desk.btc_live import verify_rules
from scripts.audit_btc_c_blind_review import OUT as BLIND,locked,preservation,load_saved,case_key,table
from scripts.btc_structure_retest import Config
from scripts.retest_btc_e1_e2_sequential import summarize
from scripts.retest_btc_p1_30d import changes

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def make_engine(model,start,end,db,enabled):
    cls=ParentFilteredBaselineReplay if model=='0.1' else ParentFilteredEarlyReplay
    kwargs=dict(expanded_b=True,consume_entry_history=True,b1_independent_hold=False,parent_filter_enabled=enabled)
    if model!='0.1':kwargs['early_policy']=model
    return cls(start,end,db,Config(version='P1+C-parent-filter-'+model,
        first_sale_fraction=.25,resistance_mode='major1h'),**kwargs)


def stats(r):
    groups=summarize(r)
    for group in groups.values():
        # This is closed-trade realized drawdown in fixed-1-BTC dollars, not
        # mark-to-market account equity or a compounded return.
        if group is groups['all']:positions=r['trades']
        elif group is groups['no_flagged_gap']:positions=[p for p in r['trades'] if not(p['gap_exposed'] or p['context_partial'])]
        elif group is groups['gap_or_partial_context']:positions=[p for p in r['trades'] if p['gap_exposed'] or p['context_partial']]
        else:positions=[p for p in r['trades'] if p['gap_exposed']]
        balance=peak=drawdown=0
        for p in positions:
            if p['net'] is None:continue
            balance+=p['net'];peak=max(peak,balance);drawdown=max(drawdown,peak-balance)
        group['max_closed_trade_drawdown_usd']=drawdown
    return groups


def compact_decisions(folder,r):
    rows=[]
    for a in r['parent_filter_audits']:
        rows.append(dict(signal_id=a['signal_id'],time_utc=a['time_utc'],entry_reference=a['entry_reference'],
            parent_flag=a['parent_flag'],trigger_flag_ignored=a['trigger_flag_ignored'],
            uncertainty='; '.join(a['uncertainty']),would_block=a['would_block'],blocked=a['blocked'],
            trade_id=a['trade_id'],prefix_last_minute=a['prefix_last_minute'],prefix_sha256=a['prefix_sha256'],
            parent_D=a['context']['parent']['price'],HL=a['context']['hl']['price']))
    if rows:table(folder/'PARENT_DECISIONS.csv',rows)


def execute(model,original,minutes,folder,ident,enabled):
    folder.mkdir(parents=True,exist_ok=False)
    db=sqlite3.connect(folder/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=make_engine(model,ts(original['start']),ts(original['end']),db,enabled)
    try:
        for i,b in enumerate(minutes,1):
            engine.minute(b)
            if i%10000==0:
                db.commit();print(json.dumps(dict(model=model,filter=enabled,processed=i,time=iso(b['t']))),flush=True)
        r=engine.finish();db.commit()
        if not enabled:
            assert r['trades']==original['trades'],model+' control trade state/path differs'
            assert r['metrics']==original['metrics'],model+' control metrics differ'
            prior=read(BLIND/'ALL_FIXED_CLASSIFICATIONS.json')
            trades={p['id']:p for p in r['trades']}
            for a in r['parent_filter_audits']:
                old=prior[case_key(trades[a['trade_id']])]
                for key in ('parent_flag','uncertainty'):assert a[key]==old[key],(model,a['trade_id'],key)
                assert a['trigger_flag_ignored']==old['trigger_flag']
        for key in ('start','end','warmup_start','days','source','source_minute_sha256','minute_count',
                    'test_data_quality','cost_model','draft_parameters','entry_mode','expanded_b'):
            r[key]=copy.deepcopy(original[key])
        r.update(run_id=folder.name,status='complete',study_id=ident,
            strategy_version='P1+C-parent-only-'+model if enabled else 'P1+C-control-'+model,
            source_frozen_release='0.2',comparison_only=True,orders_enabled=False)
        r['draft_parameters']['parent_failure_filter']=copy.deepcopy(POLICY)
        export_csv(folder,r,db);compact_decisions(folder,r);save(folder/'result.json',r)
        return r
    finally:db.close()


def attribution(old,new,diff):
    blocked={a['time_utc']:a for a in new['parent_filter_audits'] if a['blocked']}
    rows=[]
    for c in diff:
        if c['status']=='unchanged':continue
        a=c['original'];b=c['p1'];t=(a or b)['entry_time']
        old_owners=[p['id'] for p in old['trades'] if ts(p['entry_time'])<=ts(t)
            and (not p.get('exit_time') or ts(t)<ts(p['exit_time']))]
        new_owners=[p['id'] for p in new['trades'] if ts(p['entry_time'])<=ts(t)
            and (not p.get('exit_time') or ts(t)<ts(p['exit_time']))]
        rows.append(dict(status=c['status'],entry_time=t,route=(a or b)['entry_rule'],
            control_id=a['id'] if a else None,variant_id=b['id'] if b else None,
            control_net=a['net'] if a else None,variant_net=b['net'] if b else None,delta=c['delta'],
            directly_parent_blocked=t in blocked and (a or b)['entry_rule']=='C',
            control_occupied_by=old_owners,variant_occupied_by=new_owners,
            reason='direct parent-filter rejection' if t in blocked and a and a['entry_rule']=='C' else
                'control held a position' if b and not a and old_owners else
                'variant held a different position' if a and not b and new_owners else
                'subsequent setup/history/entry-state sequence differs'))
    return rows


def run():
    locked();preservation();verify_rules()
    original_study,originals,minutes=load_saved()
    now=datetime.now(timezone.utc);ident=now.strftime('%Y%m%dT%H%M%SZ')+'-parent-filter-sequential'
    folder=STORE/'parent_filter_studies'/ident;folder.mkdir(parents=True,exist_ok=False)
    protected={ROOT/p:h for p,h in read(BLIND/'PRESERVED_BEFORE.json')['files'].items()}
    for research in ('btc_c_blind_review_2026_11_09','btc_c_parent_flag_winners_2026_11_09'):
        for p in (ROOT/'reports'/research).rglob('*'):
            if p.is_file():protected[p]=sha(p)
    for p in (STORE/'latest_run.json',):
        if p.exists():protected[p]=sha(p)
    assert all(sha(p)==h for p,h in protected.items())
    code={str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'trading_desk/btc_parent_filter.py')}
    s=dict(study_id=ident,status='running',parent_control_study=original_study['study_id'],
        control_run_ids=original_study['run_ids'],run_ids={},controls_reproduced={},
        start=original_study['start'],end=original_study['end'],warmup_start=original_study['warmup_start'],
        source_minute_sha256=original_study['source_minute_sha256'],source_quality=original_study['source_quality'],
        policy=copy.deepcopy(POLICY),locked_classifier_sha256=read(BLIND/'PROTOCOL.json')['code_sha256'],
        experiment_code_sha256=code,summaries={},changes={},attribution={},orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',s);save(folder/'PRESERVED_BEFORE.json',{str(p.relative_to(ROOT)):h for p,h in protected.items()})
    for i,model in enumerate(('0.1','E1','E2')):
        old=execute(model,originals[model],minutes,folder/('control-'+model),ident,False)
        s['controls_reproduced'][model]=True
        n=now+timedelta(seconds=i)
        while (STORE/'runs'/(n.strftime('%Y%m%dT%H%M%SZ')+'-30-ab')).exists():n+=timedelta(seconds=3)
        rid=n.strftime('%Y%m%dT%H%M%SZ')+'-30-ab'
        new=execute(model,originals[model],minutes,STORE/'runs'/rid,ident,True)
        diff=changes(old,new);s['run_ids'][model]=rid
        s['summaries'][model]=dict(control=stats(old),variant=stats(new))
        s['changes'][model]=diff;s['attribution'][model]=attribution(old,new,diff)
        s.setdefault('filter_counts',{})[model]=dict(evaluated=len(new['parent_filter_audits']),
            blocked=sum(a['blocked'] for a in new['parent_filter_audits']),
            uncertain_kept=sum(bool(a['uncertainty']) for a in new['parent_filter_audits']),
            control_would_block=sum(a['would_block'] for a in old['parent_filter_audits']))
        table(folder/f'CHANGES_{model}.csv',[{k:json.dumps(v) if isinstance(v,list) else v for k,v in x.items()} for x in s['attribution'][model]])
        save(folder/'STUDY.json',s)
        print(json.dumps(dict(model=model,complete=True,net=new['metrics']['net_r'],entries=len(new['trades'])),ensure_ascii=False),flush=True)
    assert all(sha(p)==h for p,h in protected.items());locked();verify_rules();live=preservation()
    assert all(sha(ROOT/p)==h for p,h in code.items())
    s.update(status='complete',preserved_files=len(protected),live_verification=live)
    save(folder/'STUDY.json',s)
    save(STORE/'parent_filter_studies/ACTIVE.json',dict(study_id=ident))
    print(json.dumps(dict(study_id=ident,summaries=s['summaries'],filter_counts=s['filter_counts']),indent=2));return s


if __name__=='__main__':run()
