"""Locked outcome-blinded C structure review; no strategy, orders or replay."""
from __future__ import annotations
import argparse
import bisect
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_live import CONTROLLER,verify_rules
from scripts.audit_btc_parent_hl_losses import bars,pivots,local
from scripts.audit_btc_parent_wave_identity import snapshot

OUT=ROOT/'reports/btc_c_blind_review_2026_11_09'
SEED='parent-wave-C-blind-2026-11-09-v1'
EXCLUDED=(3,13,22,60,90,95,112,124)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

PROTOCOL=dict(version=1,seed=SEED,sample='10 positive and 10 nonpositive baseline C results; SHA256 selection within each stratum; no threshold search',
    excluded_baseline_ids=list(EXCLUDED),blinding='Program classifier receives no exit, P/L, or entry-minute/future OHLC. Selection uses outcome strata; not independent human blinding or out-of-sample validation.',
    parent_check='Selected D/H fixed. Complete adjacent 1h L after H, later complete 1h LH between L and H, then strict observed break of L after both references known. New selected D starts a new scope. An available newer low not adopted by C does not reset the old scope.',
    parent_repair='Observed reclaim above selected H after failure makes parent ownership uncertain, not automatically repaired or rejected.',
    trigger_check='Initial structural-known reference is preceding complete 15m high + 0.01. Flag only when reference lowers, original price is below initial line and latest confirmed post-HL 15m peak, initial line was not crossed before entry minute, and no new complete confirmed HL exists after that peak.',
    trigger_warning='A lower reference alone is a warning, not a rejection. Initial reference is structural, not proof that all original risk/target checks passed then.',
    uncertainty='Missing prefix minutes, post-H hourly outside turns, or post-HL 15m outside turns => insufficient evidence; do not count as screen candidates.',
    category='If clear: parent failure, then local failed-rebound reentry, then higher 15m low plus higher selected rebound peak => normal continuation candidate; otherwise parent-support retest probe. No category claims a guaranteed reversal.',
    screen='Diagnostic candidate only when evidence is clear and either parent or trigger check flags. No saved trade actually removed.',
    invariants='Original entries/exits/risk/fees fixed; P1/C/frozen0.2/live unchanged; no monthly sequential replay; no orders; no parameter changes after reveal.')


def code_hashes():
    return {str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),
        ROOT/'scripts/audit_btc_parent_wave_identity.py',ROOT/'scripts/audit_btc_parent_hl_losses.py')}


def locked():
    protocol=read(OUT/'PROTOCOL.json')
    assert protocol['definitions']==PROTOCOL and protocol['code_sha256']==code_hashes(),'Locked protocol/code changed'
    return protocol


def protect():
    proof=read(ROOT/'reports/btc_parent_wave_identity_2026_11_09/PRESERVATION.json')
    files={ROOT/p:h for p,h in proof['files'].items()}
    for folder in ('btc_parent_wave_identity_2026_11_09',):
        for p in (ROOT/'reports'/folder).iterdir():
            if p.is_file():files[p]=sha(p)
    for v in ('0.1','0.2'):
        p=STORE/'releases'/v/f'BTC_STRUCTURE_RELEASE_{v}.zip';files[p]=sha(p)
    assert all(sha(p)==h for p,h in files.items());verify_rules()
    live=CONTROLLER.status()
    return dict(files={str(p.relative_to(ROOT)):h for p,h in files.items()},
        live_pid=live['pid'],session=live['session']['id'])


def preservation():
    proof=read(OUT/'PRESERVED_BEFORE.json')
    assert all(sha(ROOT/p)==h for p,h in proof['files'].items());verify_rules()
    live=CONTROLLER.status()
    assert live['pid']==proof['live_pid'] and live['session']['id']==proof['session'] and not live['orders_enabled']
    return dict(files_verified=len(proof['files']),pid=live['pid'],session=live['session']['id'],
        health=live['health'],quote_fresh=live['quote_fresh'],orders_enabled=False)


def receipt(phase,paths):
    with (OUT/'STAGES.jsonl').open('a') as f:
        f.write(json.dumps(dict(stage=phase,time_utc=datetime.now(timezone.utc).isoformat(),
            files={p.name:sha(p) for p in paths},preservation=preservation()))+'\n')


def load_saved():
    study=read(STORE/'parent_hl_studies'/read(STORE/'parent_hl_studies/ACTIVE.json')['study_id']/'STUDY.json')
    results={m:read(STORE/'runs'/rid/'result.json') for m,rid in study['run_ids'].items()}
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:raw=f.read()
    assert hashlib.sha256(raw).hexdigest()==study['source_minute_sha256']
    source=[dict(zip(('t','open','high','low','close','volume','n','vw'),json.loads(l))) for l in raw.splitlines()]
    return study,results,source


def case_key(p):return digest([p['entry_time'],p['continuation']])


def blind_case(p,source,times,label):
    context={k:{x:v for x,v in p['continuation'][k].items() if x in ('price','time','bar_time','known_at')}
        for k in ('parent','rebound','hl')}
    context['known_at']=max(context[k]['known_at'] for k in ('parent','rebound','hl'))
    start=context['parent']['bar_time']-7200;end=ts(p['entry_time'])
    observed=source[bisect.bisect_left(times,start):bisect.bisect_left(times,end)]
    return dict(label=label,entry_time=p['entry_time'],context=context,
        signal=dict(entry_reference=p['entry']),minutes=observed)


def classify(case):
    assert set(case)=={'label','entry_time','context','signal','minutes'},'Outcome fields forbidden'
    assert set(case['signal'])=={'entry_reference'}
    entry=ts(case['entry_time']);observed=case['minutes']
    assert all(b['t']<entry for b in observed),'Entry-minute/future market data forbidden'
    assert all(set(b)<=set(('t','open','high','low','close','volume','n','vw')) for b in observed)
    assert all(case['context'][k]['known_at']<=entry for k in ('parent','rebound','hl'))
    s=snapshot(case);ctx=s['context'];peak=ctx['rebound'];hl=ctx['hl'];parent=ctx['parent']
    fifteen=bars(observed,900);hourly=bars(observed,3600)
    lp=pivots(fifteen,900,entry);hp=pivots(hourly,3600,entry)
    expected=(entry-(parent['bar_time']-7200))//60;missing=expected-len(observed)
    parent_outside=[p for p in hp if p['kind']=='outside' and p['time']>peak['time']]
    local_outside=[p for p in lp if p['kind']=='outside' and p['time']>hl['time']]
    failure=s['first_known_hourly_failed_rebound']
    reclaim=next((b for b in observed if failure and b['t']>ts(failure['break_time']) and b['high']>peak['price']),None)
    refs=s['trigger_references_known_at_entry'];initial=refs[0]['trigger'];latest=refs[-1]['trigger']
    high=s['confirmed_15m_highs_after_HL'][-1] if s['confirmed_15m_highs_after_HL'] else None
    newer_low=next((p for p in reversed(lp) if high and p['kind']=='L' and p['time']>high['time']
        and p['price']>hl['price']),None)
    old_line_crossed=any(b['high']>initial for b in observed if b['t']>=ctx['known_at'])
    lower_line=latest<initial
    raw_trigger=bool(lower_line and not old_line_crossed and high and not newer_low
        and s['original_price_reference']<min(initial,high['price']))
    uncertainty=[]
    if missing:uncertainty.append('missing_prefix_minutes')
    if parent_outside:uncertainty.append('hourly_outside_turn_in_parent_pullback')
    if local_outside:uncertainty.append('15m_outside_turn_after_HL')
    if reclaim:uncertainty.append('parent_high_reclaimed_after_old_failure; ownership_needs_review')
    parent_flag=bool(failure and not reclaim);trigger_flag=raw_trigger
    earlier_lows=[p for p in lp if p['kind']=='L' and parent['time']<p['time']<hl['time']]
    earlier_highs=[p for p in lp if p['kind']=='H' and parent['time']<p['time']<peak['time']]
    upward=bool(earlier_lows and earlier_highs and hl['price']>earlier_lows[-1]['price'] and peak['price']>earlier_highs[-1]['price'])
    category=('evidence_insufficient' if uncertainty else 'failed_parent_branch_rebound' if parent_flag else
        'failed_local_rebound_reentry' if trigger_flag else 'normal_continuation_candidate' if upward else 'parent_support_retest_probe')
    return dict(label=case['label'],entry_time=case['entry_time'],category=category,
        parent_flag=parent_flag,trigger_flag=trigger_flag,lower_reference_warning=bool(lower_line and not raw_trigger),
        screen_candidate=bool(not uncertainty and (parent_flag or trigger_flag)),uncertainty=uncertainty,
        initial_reference=initial,latest_reference=latest,initial_reference_crossed_before_entry=old_line_crossed,
        new_confirmed_HL_after_rebound=newer_low,confirmed_post_HL_peak=high,
        failed_parent_chain=failure,missing_minutes=missing,parent_outside=parent_outside,local_outside=local_outside,
        evidence=s,input_sha256=digest(case),no_post_entry_outcome_used=True)


def table(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def flat(review,outcome=None):
    row={k:review[k] for k in ('label','category','parent_flag','trigger_flag','lower_reference_warning','screen_candidate')}
    row.update(entry_ny=local(ts(review['entry_time'])),uncertainty='; '.join(review['uncertainty']),
        initial_reference=review['initial_reference'],entry_reference=review['evidence']['original_price_reference'],
        latest_reference=review['latest_reference'],parent_D=review['evidence']['context']['parent']['price'],
        parent_H=review['evidence']['context']['rebound']['price'],HL=review['evidence']['context']['hl']['price'],
        HL_known_ny=local(review['evidence']['context']['hl']['known_at']))
    if outcome:
        row.update(model=outcome['model'],original_trade_id=outcome['id'],original_net=outcome['net'],
            original_exit_ny=local(ts(outcome['exit_time'])),original_initial_stop=outcome['initial_stop'],
            original_T1=outcome['t1'],outcome='win' if outcome['net']>0 else 'loss')
    return row


def summarize(reviews,outcomes):
    summary={}
    for group in ('parent_flag','trigger_flag','either_clear','unflagged_or_uncertain'):
        ids=[k for k,r in reviews.items() if (r['screen_candidate'] if group=='either_clear' else
            not r['screen_candidate'] if group=='unflagged_or_uncertain' else r[group] and not r['uncertainty'])]
        items=[outcomes[k] for k in ids]
        summary[group]=dict(count=len(items),wins=sum(p['net']>0 for p in items),losses=sum(p['net']<=0 for p in items),
            original_winning_net=sum(p['net'] for p in items if p['net']>0),
            original_losing_net=sum(p['net'] for p in items if p['net']<=0),
            original_net=sum(p['net'] for p in items),labels=ids)
    summary['uncertain_count']=sum(bool(r['uncertainty']) for r in reviews.values())
    summary['lower_reference_warning_only']=sum(r['lower_reference_warning'] for r in reviews.values())
    return summary


def prepare():
    OUT.mkdir(parents=True,exist_ok=False)
    # Lock the definitions and implementation before selecting or classifying.
    save(OUT/'PROTOCOL.json',dict(definitions=PROTOCOL,code_sha256=code_hashes(),created_at=datetime.now(timezone.utc).isoformat()))
    save(OUT/'PRESERVED_BEFORE.json',protect())
    study,results,source=load_saved();times=[b['t'] for b in source]
    pool=[p for p in results['0.1']['trades'] if p['entry_rule']=='C' and p['id'] not in EXCLUDED]
    choose=lambda rows:sorted(rows,key=lambda p:digest([SEED,'selection',p['entry_time']]))[:10]
    selected=choose([p for p in pool if p['net']>0])+choose([p for p in pool if p['net']<=0])
    assert len(selected)==20 and sum(p['net']>0 for p in selected)==10
    selected.sort(key=lambda p:digest([SEED,'blind-code',p['entry_time']]))
    blind=[];sealed={}
    for i,p in enumerate(selected,1):
        label=f'S{i:02d}';blind.append(blind_case(p,source,times,label))
        sealed[label]=dict(model='0.1',**{k:p[k] for k in ('id','entry_time','entry','initial_stop','t1','exit_time','net','legs')},key=case_key(p))
    save(OUT/'BLIND_CASES.json',blind);save(OUT/'SEALED_OUTCOMES.json',sealed)
    save(OUT/'PREPARED.json',dict(study_id=study['study_id'],source_minute_sha256=study['source_minute_sha256'],
        pool=len(pool),samples=20,strata=dict(wins=10,losses=10),
        protocol_sha256=sha(OUT/'PROTOCOL.json'),blind_sha256=sha(OUT/'BLIND_CASES.json'),sealed_sha256=sha(OUT/'SEALED_OUTCOMES.json')))
    receipt('prepared_before_classification',[OUT/n for n in ('PROTOCOL.json','PREPARED.json','BLIND_CASES.json','SEALED_OUTCOMES.json')])
    print('Locked protocol; prepared 20 new coded cases. Outcomes not disclosed.')


def classify_stage():
    locked();prepared=read(OUT/'PREPARED.json');assert sha(OUT/'BLIND_CASES.json')==prepared['blind_sha256']
    assert not (OUT/'CLASSIFICATIONS.json').exists()
    # This phase never opens SEALED_OUTCOMES or saved strategy result files.
    reviews={case['label']:classify(case) for case in read(OUT/'BLIND_CASES.json')}
    save(OUT/'CLASSIFICATIONS.json',reviews);table(OUT/'BLIND_CLASSIFICATIONS.csv',[flat(r) for r in reviews.values()])
    save(OUT/'REVIEW_LOCK.json',dict(classification_sha256=sha(OUT/'CLASSIFICATIONS.json'),
        blind_sha256=prepared['blind_sha256'],protocol_sha256=sha(OUT/'PROTOCOL.json')))
    receipt('classified_before_outcome_reveal',[OUT/n for n in ('CLASSIFICATIONS.json','BLIND_CLASSIFICATIONS.csv','REVIEW_LOCK.json')])
    print(dict(cases=len(reviews),categories={c:sum(r['category']==c for r in reviews.values()) for c in sorted({r['category'] for r in reviews.values()})},outcomes_read=False))


def reveal():
    locked();lock=read(OUT/'REVIEW_LOCK.json');prepared=read(OUT/'PREPARED.json')
    assert sha(OUT/'CLASSIFICATIONS.json')==lock['classification_sha256']
    assert sha(OUT/'SEALED_OUTCOMES.json')==prepared['sealed_sha256']
    reviews=read(OUT/'CLASSIFICATIONS.json');outcomes=read(OUT/'SEALED_OUTCOMES.json')
    table(OUT/'REVEALED_20.csv',[flat(r,outcomes[k]) for k,r in reviews.items()])
    summary=summarize(reviews,outcomes);save(OUT/'REVEALED_20_SUMMARY.json',summary)
    receipt('outcomes_revealed_after_labels_locked',[OUT/'REVEALED_20.csv',OUT/'REVEALED_20_SUMMARY.json'])
    print(json.dumps(summary,ensure_ascii=False,indent=2))


def all_fixed():
    locked();assert (OUT/'REVEALED_20_SUMMARY.json').exists()
    lock=read(OUT/'REVIEW_LOCK.json');assert sha(OUT/'CLASSIFICATIONS.json')==lock['classification_sha256']
    study,results,source=load_saved();times=[b['t'] for b in source]
    blind_reviews=read(OUT/'CLASSIFICATIONS.json');sample=read(OUT/'SEALED_OUTCOMES.json')
    sampled_keys={p['key']:label for label,p in sample.items()}
    # Classify every unique saved entry/context first. Outcome attribution is
    # a separate pass; original trade paths never change.
    unique={}
    for model,result in results.items():
        for p in result['trades']:
            if p['entry_rule']!='C':continue
            key=case_key(p)
            if key not in unique:
                case=blind_case(p,source,times,key[:12]);unique[key]=classify(case)
                if key in sampled_keys:
                    old=copy.deepcopy(blind_reviews[sampled_keys[key]]);new=copy.deepcopy(unique[key])
                    for x in (old,new):x.pop('label');x['evidence'].pop('label');x.pop('input_sha256')
                    assert old==new,'Full audit changed a previously blinded classification'
    save(OUT/'ALL_FIXED_CLASSIFICATIONS.json',unique)
    summaries={};rows=[]
    for model,result in results.items():
        reviews={};outcomes={}
        for p in result['trades']:
            if p['entry_rule']!='C':continue
            key=case_key(p);review=unique[key];ident=f'{model}-C-{p["id"]}'
            reviews[ident]=review;outcomes[ident]=dict(p,model=model)
            row=flat(review,outcomes[ident]);row['was_blinded_sample']=key in sampled_keys;row['sample_code']=sampled_keys.get(key,'')
            rows.append(row)
        summaries[model]=summarize(reviews,outcomes)
        summaries[model]['original_C_net']=sum(p['net'] for p in outcomes.values())
        summaries[model]['original_C_count']=len(outcomes)
    table(OUT/'ALL_FIXED_C_TRADES.csv',rows);save(OUT/'ALL_FIXED_SUMMARY.json',dict(models=summaries,
        unique_entry_contexts=len(unique),model_trade_rows=len(rows),no_replay=True,no_changed_trade_paths=True,
        interpretation='Original fixed-trade attribution only, not screened strategy returns; no replacement opportunities simulated'))
    receipt('all_saved_C_fixed_entry_attribution',[OUT/n for n in ('ALL_FIXED_CLASSIFICATIONS.json','ALL_FIXED_C_TRADES.csv','ALL_FIXED_SUMMARY.json')])
    print(json.dumps(dict(unique_contexts=len(unique),rows=len(rows),models={m:{k:s[k] for k in ('original_C_count','original_C_net','either_clear','uncertain_count')} for m,s in summaries.items()}),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','classify','reveal','all'))
    args=parser.parse_args();{'prepare':prepare,'classify':classify_stage,'reveal':reveal,'all':all_fixed}[args.phase]()
