"""Fixed-entry ten-case E3 draft-1 study; never runs a strategy or an order."""
from __future__ import annotations
import bisect
import copy
import csv
from datetime import datetime,timezone
import gzip
import hashlib
from html import escape
import json
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import STORE,read,save,ts,iso
from trading_desk.btc_live import LIVE
from trading_desk.btc_engine import aggregate
from trading_desk.btc_parent_memory_view import PARENT_MEMORY_VIEW
from scripts.retest_btc_parent_five import preservation,verify_preserved,CASE_END

OUT=ROOT/'reports/btc_e3_draft1_2026_11_15'
NY=ZoneInfo('America/New_York')
RULE=dict(name='E3_RAPID_SUPPORT_FAILURE',version='draft-1-fixed-ten-cases',
    rapid_drop_atr=1.0,window_seconds=600,bar_seconds=300,
    ATR='Original 14-completed-15m ATR recorded before the first 5m bar; freeze for the entire 10m pair.',
    rapid='A.open - B.close >= 1.0 * frozen pre-window ATR; A/B adjacent complete 5m bars.',
    support='H is the entry-time confirmed 15m HL, fixed for this trade. A.close < H.',
    persistence='B.high < H and B.close < H: entire following 5m never reclaims H, including wick touches.',
    direction='B.close < B.open; B.close <= A.close; neither full-range nor body inside A.',
    after_entry='A starts at/after the next full 5m boundary following the original entry minute.',
    no_profit_gate='Does not require 1R profit, a new high, or a new H-L-LH pattern.',
    execution_delay_seconds=60,
    execution='At B.end + 60 seconds use the exact real 1m open as a model reference; never use B.close or a support threshold as a retrospective fill.',
    missing='No incomplete pair or absent ATR. Missing exact execution minute cancels that attempt; later complete fresh windows may qualify. No fill/price carry-forward.',
    receipt='For the live-prefix case, all signal inputs must have actually arrived before the chosen execution minute. Monthly contemporaneous receipts unavailable: +60s is an explicit model assumption, not observed latency.',
    priority='Original exits through the E3 execution minute retain priority. Preserve any earlier/same-minute 25% leg and sell only current remainder; final original exit at/before due suppresses E3. Flag same-minute ambiguity.',
    fraction='100% of then-remaining shares, no new entries or reentry.',
    friction_bps_per_side=2.0,
    unchanged='Original entries, stop/target formulas, original earlier exits and costs remain; only one independent hypothetical exit overlay is evaluated.',
    selection='Exactly Nov15 01:44 case and the nine prior-audit winners; no new month run, parameter search or live promotion.')


def clock(t):
    if t is None:return '—'
    if isinstance(t,str):t=ts(t)
    return datetime.fromtimestamp(t,NY).strftime('%m/%d %H:%M:%S %Z')


def scan_e3(trade,rows,atr_by_quarter,cutoff,receipts=None):
    """Causal candidate trace on observed inputs; does not alter original data."""
    start=ts(trade['entry_time']);floor=(start//300+1)*300
    h=trade['references']['l2']['price']
    assert ts(trade['references']['l2']['known_at'])<=start
    final=ts(trade['exit_time']) if trade.get('status')=='closed' else cutoff
    limit=min(final,cutoff)
    index={b['t']:b for b in rows};trace=[];selected=None;attempts=[];missing_windows=0
    for bstart in range(floor+300,limit,300):
        astart=bstart-300;known=bstart+300
        if known>limit:break
        group_a=[index[t] for t in range(astart,bstart,60) if t in index]
        group_b=[index[t] for t in range(bstart,known,60) if t in index]
        complete=len(group_a)==5 and len(group_b)==5
        quarter=astart//900*900;atr=atr_by_quarter.get(quarter)
        if not complete:
            missing_windows+=1
            trace.append(dict(window_start=iso(astart),signal_bar=iso(bstart),known_at=iso(known),
                complete=False,observed_minutes=len(group_a)+len(group_b),qualified=False,
                reasons=['missing real minutes; pair discarded'],after_E3=bool(selected)))
            continue
        a=aggregate(group_a,300);b=aggregate(group_b,300)
        full_inside=b['high']<=a['high'] and b['low']>=a['low']
        body_inside=(min(b['open'],b['close'])>=min(a['open'],a['close'])
                     and max(b['open'],b['close'])<=max(a['open'],a['close']))
        drop=a['open']-b['close']
        gates=dict(ATR_known=atr is not None and atr>0,
            rapid=bool(atr and drop>=RULE['rapid_drop_atr']*atr),
            A_close_below_HL=a['close']<h,B_entirely_below_HL=b['high']<h,
            B_close_below_HL=b['close']<h,B_red=b['close']<b['open'],
            B_not_above_previous_close=b['close']<=a['close'],
            B_non_inside=not(full_inside or body_inside))
        qualified=all(gates.values())
        frame=dict(window_start=iso(astart),signal_bar=iso(bstart),known_at=iso(known),
            complete=True,A=a,B=b,H=h,ATR=atr,ATR_known_at=iso(quarter),drop=drop,
            down_atr=drop/atr if atr else None,full_inside=full_inside,body_inside=body_inside,
            gates=gates,qualified=qualified,reasons=[k for k,v in gates.items() if not v],after_E3=bool(selected))
        trace.append(frame)
        if selected or not qualified:continue
        due=known+RULE['execution_delay_seconds']
        frame['execution_due']=iso(due)
        received=max(receipts[t] for t in range(astart,known,60)) if receipts is not None else None
        attempt=dict(signal_at=iso(known),signal_bar=iso(bstart),execution_at=iso(due),
            signal_reference=b['close'],inputs_received_at=iso(received) if received is not None else None,
            receipt_observed=received is not None,H=h,ATR=atr,drop=drop,down_atr=drop/atr,
            gates=copy.deepcopy(gates),A=copy.deepcopy(a),B=copy.deepcopy(b))
        attempts.append(attempt)
        if final<=due:
            attempt['status']='original_final_exit_priority';continue
        if due>=cutoff:
            attempt['status']='execution_after_case_cutoff';continue
        if received is not None and received>due:
            attempt['status']='signal_arrived_after_execution_reference';continue
        execution=index.get(due)
        if execution is None:
            attempt['status']='missing_exact_execution_minute';continue
        before=[copy.deepcopy(l) for l in trade['legs'] if ts(l['time_utc'])<=due]
        remaining=round(1-sum(l['fraction'] for l in before),8)
        if remaining<=0:
            attempt['status']='no_remaining_position';continue
        price=execution['open'];q=RULE['friction_bps_per_side']/10000
        gross=remaining*(price-trade['entry']);cost=remaining*(price+trade['entry'])*q
        leg=dict(time_utc=iso(due),fraction=remaining,price=price,gross=gross,cost=cost,net=gross-cost,
            reason='E3_draft1_hypothetical_remaining',time_basis='Predeclared +60s actual minute-open model reference, not a broker fill')
        attempt.update(status='hypothetical_exit',execution_price=price,remaining=remaining,
            earlier_original_legs=before,leg=leg,net=sum(l['net'] for l in before)+leg['net'],
            same_minute_original_leg=any(ts(l['time_utc'])==due for l in before))
        selected=copy.deepcopy(attempt)
    return dict(selected=selected,attempts=attempts,trace=trace,missing_windows=missing_windows,
                partial_history=missing_windows>0)


def value_case(label,trade,scan,cutoff,baseline_mark=None):
    closed=trade['status']=='closed'
    base=trade['net'] if closed else baseline_mark
    assert base is not None
    realized=sum(l['net'] for l in trade['legs'])
    choice=scan['selected']
    new=choice['net'] if choice else base
    return dict(label=label,trade_id=trade['id'],entry_time=trade['entry_time'],entry=trade['entry'],
        H=trade['references']['l2']['price'],initial_stop=trade['initial_stop'],baseline_status=trade['status'],
        baseline_net=trade.get('net'),baseline_realized=realized,baseline_same_cutoff_net=base,
        baseline_exit=trade.get('exit_time'),baseline_legs=trade['legs'],cutoff=iso(cutoff),
        baseline_marked_not_realized=not closed,E3_selected=choice,
        E3_net=new,E3_status='hypothetical_closed' if choice else trade['status'],
        same_cutoff_delta=new-base,realized_delta=(new-realized if choice else 0),
        triggered=choice is not None,scan=scan,gap_or_partial_context=bool(trade['gap_exposed'] or trade['context_partial']))


def run():
    before=preservation();folder,study=PARENT_MEMORY_VIEW.current()
    evidence=read(ROOT/'reports/btc_e3_feasibility_2026_11_15/AUDIT.json')
    winners=[p['trade_id'] for p in evidence['archived_first_HL_breaks'] if p['original_net']>0]
    assert winners==[6,7,33,39,40,70,78,114,123]
    OUT.mkdir(parents=True,exist_ok=True)
    lock=dict(rule=RULE,winner_ids=winners,model='0.1 retained_combined',source_study=study['study_id'])
    lock_path=OUT/'LOCKED_RULE.json'
    if lock_path.exists():assert read(lock_path)['definition']==lock,'Do not tune draft-1 after results'
    else:save(lock_path,dict(locked_at=datetime.now(timezone.utc).isoformat(),definition=lock))
    protected=[p for p in folder.rglob('*') if p.is_file()]
    protected += [folder.parent/'ACTIVE.json',ROOT/'trading_desk/btc_parent_memory.py',
        ROOT/'trading_desk/btc_parent_five.py',ROOT/'scripts/retest_btc_parent_memory.py',lock_path]
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    save(OUT/'PRESERVED.json',dict(original=before,research_files=hashes))
    archive=[];digest=hashlib.sha256()
    with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:
        for line in f:
            digest.update(line);t,o,h,l,c,v,n,_=json.loads(line)
            archive.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
    assert digest.hexdigest()==study['source_minute_sha256']
    monthly=read(folder/'0.1/retained_combined/result.json')
    with sqlite3.connect((folder/'0.1/retained_combined/ledger.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        atrs={t:json.loads(body)['atr_before'] for t,body in db.execute('SELECT t,body FROM ledger ORDER BY t')}
    times=[b['t'] for b in archive];results=[];inputs=[]
    for ident in winners:
        p=next(p for p in monthly['trades'] if p['id']==ident)
        start,end=ts(p['entry_time']),ts(p['exit_time'])
        # Include the exact execution/open observations when available; the
        # original exit time still bounds the candidate scan independently.
        rows=archive[bisect.bisect_left(times,start):bisect.bisect_right(times,end)]
        scan=scan_e3(p,rows,atrs,end+60)
        results.append(value_case('winner-'+str(ident),p,scan,end+60))
        inputs.append(dict(label='winner-'+str(ident),trade={k:copy.deepcopy(p[k]) for k in (
            'id','entry_time','entry','initial_stop','references','legs','status','net','exit_time','gap_exposed','context_partial')},
            rows=rows,atr_by_quarter=atrs,cutoff=end+60,receipts=None))
    case=read(folder/'CASE.json');retained=case['models']['0.1']['retained']
    p=next(p for p in retained['trades'] if p['entry_time']=='2026-11-15T06:44:00Z')
    src=LIVE/'sessions'/case['source_session']/'observations.sqlite'
    with sqlite3.connect(src.as_uri()+'?mode=ro',uri=True) as db:
        records=db.execute('SELECT body,received FROM minutes WHERE t<? ORDER BY t',(CASE_END,)).fetchall()
    assert hashlib.sha256(json.dumps(records,separators=(',',':')).encode()).hexdigest()==case['source_sha256']
    rows=[json.loads(body) for body,_ in records];receipts={b['t']:r for b,(_,r) in zip(rows,records)}
    case_atrs={b['t']:b['atr_before'] for b in retained['bars']}
    scan=scan_e3(p,rows,case_atrs,CASE_END,receipts)
    example=value_case('Nov15-0144',p,scan,CASE_END,p['marked_net'])
    inputs.append(dict(label='Nov15-0144',trade={k:copy.deepcopy(p[k]) for k in (
        'id','entry_time','entry','initial_stop','references','legs','status','net','gap_exposed','context_partial')},
        rows=[b for b in rows if b['t']>=ts(p['entry_time'])],atr_by_quarter=case_atrs,cutoff=CASE_END,
        receipts={str(b['t']):receipts[b['t']] for b in rows if b['t']>=ts(p['entry_time'])}))
    # Strict prefixes must reproduce each chosen signal and execution reference
    # without the original winner's later recovery or example's later mark.
    for item,source,atr,receipt in [(r,archive,atrs,None) for r in results]+[(example,rows,case_atrs,receipts)]:
        if not item['E3_selected']:continue
        due=ts(item['E3_selected']['execution_at'])
        original=p if item is example else next(q for q in monthly['trades'] if q['id']==item['trade_id'])
        prefix=[b for b in source if b['t']<=due]
        found=scan_e3(original,prefix,atr,due+60,receipt)['selected']
        assert found==item['E3_selected'],item['label']
        item['prefix_verified']=True
    for name,h in hashes.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h,name
    result=dict(rule=RULE,locked_at=read(lock_path)['locked_at'],cohort=winners,
        fixed_entries=True,new_entries=False,month_rerun=False,live_promoted=False,orders_enabled=False,
        example=example,winners=results,
        winners_summary=dict(count=9,triggered=sum(r['triggered'] for r in results),
            original_net=sum(r['baseline_same_cutoff_net'] for r in results),E3_net=sum(r['E3_net'] for r in results),
            delta=sum(r['same_cutoff_delta'] for r in results),
            cut_to_loss=sum(r['triggered'] and r['E3_net']<=0 for r in results)),
        monthly_source_sha256=digest.hexdigest(),case_source_sha256=case['source_sha256'],
        preservation=verify_preserved(before),extra_protected_files=len(hashes),
        scanner_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with gzip.open(OUT/'ACTUAL_INPUTS.json.gz','wt',encoding='utf-8') as f:
        json.dump(inputs,f,ensure_ascii=False,allow_nan=False)
    save(OUT/'RESULT.json',result)
    export_tables(result)
    print(json.dumps(dict(output=str(OUT),example={k:example[k] for k in (
        'triggered','baseline_same_cutoff_net','E3_net','same_cutoff_delta')},
        winners=result['winners_summary'],preservation=result['preservation']),indent=2))


def export_tables(result):
    cases=[result['example']]+result['winners']
    fields=['case','entry_time','entry','support_HL','signal_at','signal_close','execution_at','execution_price',
            'remaining_sold','original_status','original_net_or_historical_mark','E3_net','delta',
            'gap_or_partial_context','missing_windows','inputs_received_at']
    with (OUT/'COMPARISON.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for p in cases:
            s=p['E3_selected'] or {}
            writer.writerow(dict(zip(fields,[p['label'],p['entry_time'],p['entry'],p['H'],s.get('signal_at'),
                s.get('signal_reference'),s.get('execution_at'),s.get('execution_price'),s.get('remaining'),
                p['baseline_status'],p['baseline_same_cutoff_net'],p['E3_net'],p['same_cutoff_delta'],
                p['gap_or_partial_context'],p['scan']['missing_windows'],s.get('inputs_received_at')],strict=True)))
    with (OUT/'BAR_TRACE.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['case','window_start','known_at','A_open','A_close','B_high','B_open','B_close','HL','ATR','drop_ATR','qualified','failed_gates','after_E3']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for p in cases:
            for b in p['scan']['trace']:
                writer.writerow(dict(zip(fields,[p['label'],b['window_start'],b['known_at'],b.get('A',{}).get('open'),
                    b.get('A',{}).get('close'),b.get('B',{}).get('high'),b.get('B',{}).get('open'),b.get('B',{}).get('close'),
                    b.get('H'),b.get('ATR'),b.get('down_atr'),b['qualified'],';'.join(b['reasons']),b['after_E3']],strict=True)))


if __name__=='__main__':run()
