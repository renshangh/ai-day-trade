"""Audit two parent-flagged winners and #13 outside-hour uncertainty only."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso
from scripts.audit_btc_c_blind_review import OUT as BLIND,locked,preservation,load_saved,case_key,blind_case,table
from scripts.audit_btc_parent_hl_losses import bars,pivots,local

OUT=ROOT/'reports/btc_c_parent_flag_winners_2026_11_09'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def outside_hour(prefix,context,hour):
    rows=[b for b in prefix if hour<=b['t']<hour+3600]
    assert len(rows)==60
    high=max(b['high'] for b in rows);low=min(b['low'] for b in rows)
    highs=[b['t'] for b in rows if b['high']==high];lows=[b['t'] for b in rows if b['low']==low]
    later=[b for b in prefix if b['t']>=hour+3600]
    first=next((b for b in later if b['low']<low),None)
    return dict(hour_start=iso(hour),fully_observed_at=iso(hour+3600),high=high,low=low,
        high_minutes=[iso(t) for t in highs],low_minutes=[iso(t) for t in lows],
        extrema_order='high_then_low' if max(highs)<min(lows) else 'low_then_high' if max(lows)<min(highs) else 'same_minute_or_repeated_order_unknown',
        remains_inside_ancestor_D_H=low>context['parent']['price'] and high<context['rebound']['price'],
        later_break_of_outside_low=iso(first['t']) if first else None,
        minutes=rows)


def run():
    locked();before=preservation()
    protected={p:sha(p) for p in BLIND.iterdir() if p.is_file()}
    study,results,source=load_saved();times=[b['t'] for b in source]
    reviews=read(BLIND/'ALL_FIXED_CLASSIFICATIONS.json');findings=[];csv_rows=[]
    for ident in (5,69,13):
        p=next(p for p in results['0.1']['trades'] if p['id']==ident)
        entry=ts(p['entry_time']);exit_time=ts(p['exit_time']);ctx=p['continuation']
        original=reviews[case_key(p)]
        case=blind_case(p,source,times,f'C-{ident}')
        assert original['parent_flag'] and original['trigger_flag']
        failure=original['failed_parent_chain'];assert ts(failure['break_time'])<entry
        assert all(failure[k]['known_at']<entry for k in ('high','pullback','lower_high'))
        start=ctx['hl']['bar_time']-5400
        trace=[b for b in bars(case['minutes'],900) if b['t']>=start and b['t']+900<=entry and b['observed_minutes']==15]
        pre=dict(original_locked_classification=copy.deepcopy(original),
            current_parent_failure_supported=True,selected_parent_scope_not_repaired=True,
            source_prefix=case,reviewed_complete_15m=trace,
            entry_label='failed-parent new-base/reversal probe; not confirmed parent-uptrend continuation')
        # A later hourly turn is recorded separately as hindsight timing, not
        # inserted into the original decision or used to redesign an entry.
        hour=ctx['hl']['time']//3600*3600
        neighbours=bars([b for b in source if hour-3600<=b['t']<hour+7200],3600)
        left,middle,right=neighbours
        low_turn=middle['low']<min(left['low'],right['low'])
        high_turn=middle['high']>max(left['high'],right['high'])
        later_base=dict(time=iso(ctx['hl']['time']),price=ctx['hl']['price'],
            hourly_neighbours=neighbours,hourly_turn_confirmed=low_turn and not high_turn,
            known_at=iso(hour+7200),known_at_original_entry=hour+7200<=entry,
            interpretation='Later timing only; no delayed trade or new P/L computed')
        assert low_turn and not high_turn and hour+7200>entry
        post=[b for b in source if entry<b['t']<=exit_time]
        interior=[b for b in post if b['t']<exit_time]
        peak=max(interior,key=lambda b:b['high'])
        breaches={}
        for name,price in [('near_HL',ctx['hl']['price']),('parent_D',ctx['parent']['price'])]:
            b=next((b for b in post if b['low']<price),None)
            breaches[name]=dict(price=price,first_break=iso(b['t']) if b else None)
        outcome=dict(original_entry=p['entry'],initial_stop=p['initial_stop'],target1=p['t1'],
            price_gap_R=p['entry']-p['initial_stop'],recorded_cost_inclusive_risk=p['initial_risk'],
            highest_observed_interior=peak['high'],peak_minute=iso(peak['t']),
            MFE_excluding_boundary_minutes=peak['high']-p['entry'],
            minimum_interior=min(b['low'] for b in interior),breaches=breaches,
            original_legs=copy.deepcopy(p['legs']),original_net=p['net'],
            original_case_exit_evidence=copy.deepcopy(p.get('case_exit_evidence')),
            original_structure_protection=copy.deepcopy(p.get('structure_history',[])),
            caveat='Outcome explanation only; entry/exit-minute range ordering not inferred')
        outside=None
        if ident==13:
            outside=outside_hour(case['minutes'],ctx,ts('2026-10-14T17:00:00Z'))
            assert outside['extrema_order']=='high_then_low'
            assert outside['later_break_of_outside_low']=='2026-10-14T22:23:00Z'
            assert outside['high']<failure['lower_high']['price']
            pre['manual_outside_adjudication']='This hour cannot erase the earlier confirmed failure: high preceded low, failed LH/H were not reclaimed, and even its potential new base was broken before entry. Original automatic uncertain label remains untouched.'
        findings.append(dict(trade_id=ident,entry_time=p['entry_time'],pre_entry=pre,
            post_entry_outcome=outcome,later_hourly_base_timing=later_base,outside_analysis=outside))
        for b in trace:
            csv_rows.append(dict(trade_id=ident,interval_start_ny=local(b['t']),known_at_ny=local(b['t']+900),
                open=b['open'],high=b['high'],low=b['low'],close=b['close'],observed_minutes=b['observed_minutes'],
                purpose='pre-entry evidence only'))
    OUT.mkdir(parents=True,exist_ok=True)
    save(OUT/'THREE_CASE_AUDIT.json',dict(study_id=study['study_id'],findings=findings,
        trading_rules_changed=False,old_classifications_changed=False,monthly_replay=False,orders_enabled=False))
    table(OUT/'PRE_ENTRY_15M.csv',csv_rows)
    outside=findings[-1]['outside_analysis']
    table(OUT/'OUTSIDE_HOUR_1M.csv',[dict(time_ny=local(b['t']),**{k:b[k] for k in ('open','high','low','close','volume')}) for b in outside['minutes']])
    assert all(sha(p)==h for p,h in protected.items());locked();after=preservation()
    assert after['pid']==before['pid'] and after['session']==before['session']
    save(OUT/'PRESERVATION.json',dict(original_blind_artifacts={str(p.relative_to(ROOT)):h for p,h in protected.items()},
        **after,old_labels_preserved=True,no_trade_change=True,no_monthly_replay=True))
    for f in findings:
        o=f['post_entry_outcome'];print(dict(C=f['trade_id'],entry=local(ts(f['entry_time'])),
            old_flag_supported=f['pre_entry']['current_parent_failure_supported'],net=o['original_net'],
            first_HL_break=o['breaches']['near_HL']['first_break'],
            new_hourly_D_known=f['later_hourly_base_timing']['known_at'],exit=o['original_legs'][0]['reason']))


if __name__=='__main__':run()
