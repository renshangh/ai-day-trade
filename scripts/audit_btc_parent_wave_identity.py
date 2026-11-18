"""Three entry-time parent/child structure snapshots, without a strategy replay."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso
from trading_desk.btc_live import CONTROLLER,verify_rules
from scripts.audit_btc_parent_hl_losses import bars,pivots

OUT=ROOT/'reports/btc_parent_wave_identity_2026_11_09'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def snapshot(item):
    entry=ts(item['entry_time']);context=copy.deepcopy(item['context'])
    # No observed price from the entry minute or any later candle is used for
    # structure classification. The original entry reference is separate.
    minute=[b for b in item['minutes'] if b['t']<entry]
    fifteen=bars(minute,900);hourly=bars(minute,3600)
    local=pivots(fifteen,900,entry);parents=pivots(hourly,3600,entry)
    d=context['parent'];peak=context['rebound'];low=context['hl']
    after=[]
    for p in parents:
        if p['kind']!='L' or p['time']<=peak['time']:continue
        breach=next((b for b in minute if b['t']>=p['known_at'] and b['low']<=p['price']),None)
        after.append(dict(p,break_time=iso(breach['t']) if breach else None))
    failure=None
    for p in after:
        if not p['break_time']:continue
        lower_high=next((h for h in parents if h['kind']=='H' and h['time']>p['time']
            and p['known_at']<=h['known_at']<=ts(p['break_time'])
            and p['price']<h['price']<peak['price']),None)
        if lower_high:
            failure=dict(high=peak,pullback=p,lower_high=lower_high,break_time=p['break_time'])
            break
    post_HL_highs=[p for p in local if p['kind']=='H' and p['time']>low['time']]
    original_price=(item.get('record') or {}).get('entry') or item['signal']['entry_reference']
    peak_hourly=next((p for p in parents if p['kind']=='H' and p['time']==peak['time']),None)
    by_time={b['t']:b for b in fifteen};triggers=[]
    for period in range(context['known_at']//900*900,entry//900*900+900,900):
        prev=by_time.get(period-900)
        if prev and prev['observed_minutes']==15:
            triggers.append(dict(period=iso(period),previous_bar=iso(prev['t']),
                trigger=prev['high']+.01,known_at=iso(period)))
    return dict(label=item['label'],entry_time=item['entry_time'],original_price_reference=original_price,
        context=context,source_prefix_sha256=hashlib.sha256(str(minute).encode()).hexdigest(),
        last_structure_minute=iso(minute[-1]['t']),
        parent_age_hours=(entry-d['time'])/3600,
        retracement_fraction=(peak['price']-low['price'])/(peak['price']-d['price']),
        post_peak_hourly_lows=after,first_known_hourly_failed_rebound=failure,
        confirmed_15m_highs_after_HL=post_HL_highs,
        original_price_above_latest_post_HL_high=(original_price>post_HL_highs[-1]['price']) if post_HL_highs else None,
        selected_peak_has_hourly_confirmation=bool(peak_hourly),
        trigger_references_known_at_entry=triggers,
        completed_15m_bars=[b for b in fifteen if b['t']+900<=entry and b['observed_minutes']==15],
        completed_1h_bars=[b for b in hourly if b['t']+3600<=entry and b['observed_minutes']==60],
        no_post_entry_outcome_included=True)


def run():
    old=ROOT/'reports/btc_parent_hl_loss_audit_2026_11_09'
    audit=read(old/'AUDIT.json')
    p1=ROOT/'reports/btc_c_p1_confirmation_2026_11_09'
    protected={ROOT/p:h for p,h in read(p1/'PRESERVATION.json')['files'].items()}
    for p in p1.iterdir():
        if p.is_file():protected[p]=sha(p)
    assert all(sha(p)==h for p,h in protected.items());verify_rules();before=CONTROLLER.status()
    selected=[next(x for x in audit['cases'] if x['label']=='baseline-C-13'),audit['benchmark'],
        next(x for x in audit['cases'] if x['label']=='baseline-C-90')]
    result=dict(status='analysis only',monthly_replay=False,rules_changed=False,orders_enabled=False,cases=[])
    for item in selected:
        full=snapshot(item)
        prefix=copy.deepcopy(item);prefix['minutes']=[b for b in item['minutes'] if b['t']<ts(item['entry_time'])]
        assert snapshot(prefix)==full
        result['cases'].append(full)
    first,benchmark,normal=result['cases']
    assert first['first_known_hourly_failed_rebound']['break_time']=='2026-10-13T17:50:00Z'
    assert first['confirmed_15m_highs_after_HL'][-1]['price']==81820.85
    assert first['original_price_above_latest_post_HL_high'] is False
    assert len(first['trigger_references_known_at_entry'])==2
    assert first['trigger_references_known_at_entry'][1]['trigger']<first['trigger_references_known_at_entry'][0]['trigger']
    assert len(benchmark['trigger_references_known_at_entry'])==len(normal['trigger_references_known_at_entry'])==1
    assert not benchmark['post_peak_hourly_lows'] and not normal['post_peak_hourly_lows']
    assert not benchmark['confirmed_15m_highs_after_HL'] and not normal['confirmed_15m_highs_after_HL']
    assert not normal['selected_peak_has_hourly_confirmation']
    OUT.mkdir(parents=True,exist_ok=True);save(OUT/'ENTRY_TIME_EVIDENCE.json',result)
    assert all(sha(p)==h for p,h in protected.items());verify_rules();after=CONTROLLER.status()
    assert before['pid']==after['pid'] and before['session']['id']==after['session']['id'] and not after['orders_enabled']
    save(OUT/'PRESERVATION.json',dict(files={str(p.relative_to(ROOT)):h for p,h in protected.items()},
        worker_pid=after['pid'],session=after['session']['id'],health=after['health'],quote_fresh=after['quote_fresh'],
        monthly_replay=False,rules_changed=False,orders_enabled=False))
    print(dict(cases=[dict(case=x['label'],post_peak_hourly_low_count=len(x['post_peak_hourly_lows']),
        prior_hourly_branch_failed=bool(x['first_known_hourly_failed_rebound']),
        confirmed_highs_after_entry_HL=len(x['confirmed_15m_highs_after_HL']),
        parent_peak_hourly_confirmed=x['selected_peak_has_hourly_confirmation']) for x in result['cases']],
        protected_files=len(protected),live_health=after['health']))


if __name__=='__main__':run()
