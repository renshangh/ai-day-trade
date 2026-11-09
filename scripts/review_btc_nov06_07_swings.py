"""Four nominated cases only; scan observed minutes, never run monthly engine.

Separates parent-cycle evidence, last-minute wick observations, next-bar
midpoint crossings and original exits. Later signals remain conditional after
an earlier exit; no hindsight choice of a preferred selling time.
"""
from __future__ import annotations
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import ts,iso
from trading_desk.btc_engine import aggregate
from scripts.btc_structure_retest import reward_risk

FOLDER=ROOT/'reports/btc_structure_2026_11_08/entry_examples/hierarchy_review'
FIXTURE_SHA256='be5fc6616d80800cd55c613e887dcbf2cefedba0e32aed195374f587f97738d4'
OWNER_SOURCE_SHA256='37d85900edda50010f460e91cf4b68f94a70e4ea89691770f39040a1c884d139'
SEQUENCE_SOURCE_SHA256='5752b60aa8ad1d38500f12fc36a2fbb1b23b7997dc43fc420ac22bc70192f54c'
NY=ZoneInfo('America/New_York')


def local(t):
    return datetime.fromtimestamp(t,NY).isoformat()


def load(folder=FOLDER):
    payload=(folder/'NOV06_07_ALPACA_OBSERVED.json').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=FIXTURE_SHA256:
        raise ValueError('Preserved source extraction changed')
    fixture=json.loads(payload)
    minutes=[dict(zip(fixture['columns'],row)) for row in fixture['minutes']]
    if len({b['t'] for b in minutes})!=len(minutes):
        raise ValueError('Duplicate observations')
    return fixture,minutes


def groups(minutes,step=900):
    buckets=defaultdict(list)
    for b in minutes:
        buckets[b['t']//step*step].append(b)
    return buckets


def complete(group,step=900):
    return [b['t'] for b in group]==list(range(group[0]['t']//step*step,group[0]['t']//step*step+step,60))


def pnl(entry,price):
    gross=price-entry;cost=(price+entry)*.0002
    return dict(gross=gross,cost=cost,net=gross-cost,normalization='per 1 initial BTC, not ETF actual fills')


def scan_exits(trade,minutes):
    at=ts(trade['entry_time'])
    end=(ts(trade['source_end_exclusive']) if 'source_end_exclusive' in trade else ts(trade['exit_time'])+60)
    selected=[b for b in minutes if at//900*900<=b['t']<end]
    # A same-level new high must exceed the setup H1, not just a tiny
    # post-entry local high. This is explicit review scope, not a tuned threshold.
    peak=trade['references']['h1']['price'];armed=None;events=[]
    for period,group in groups(selected).items():
        contiguous=complete(group)
        for i,b in enumerate(group):
            if b['t']<at:
                continue
            if armed and period==armed['t']+900 and b['low']<armed['mid']:
                price=min(b['open'],armed['mid'])
                events.append(dict(type='next_bar_below_previous_new_high_midpoint',
                    time=local(b['t']),interval_end=local(b['t']+60),
                    reference_bar=local(armed['t']),reference_known_at=local(armed['t']+900),
                    reference_high=armed['high'],reference_low=armed['low'],threshold=armed['mid'],
                    price=price,price_basis='actual minute open if already below threshold, otherwise threshold-crossing model',
                    exact_second_verified=False,fraction_initial=1.0,pnl=pnl(trade['entry'],price)))
                armed=None
            if contiguous and i==14:
                prefix=group[:14]
                h=max(b['open'],max(x['high'] for x in prefix));lo=min(b['open'],min(x['low'] for x in prefix))
                ratio=(h-max(group[0]['open'],b['open']))/(h-lo) if h>lo else None
                if h>peak and ratio is not None and ratio>=.5 and b['open']>trade['entry']:
                    events.append(dict(type='last_minute_new_wave_high_upper_wick',time=local(b['t']),
                        interval_end=local(b['t']+60),reference_bar=local(period),known_prefix_minutes=14,
                        observed_high=h,observed_low=lo,opening_15m=group[0]['open'],upper_wick_fraction=ratio,
                        peak_before=peak,price=b['open'],price_basis='current minute first provider observation; no current final H/L/C',
                        integer_watch_gate=False,exact_second_verified=False,fraction_initial=1.0,pnl=pnl(trade['entry'],b['open'])))
        if contiguous and period>=at:
            bar=aggregate(group,900)
            armed=(dict(t=period,high=bar['high'],low=bar['low'],mid=(bar['high']+bar['low'])/2)
                if bar['high']>peak else None)
            peak=max(peak,bar['high'])
    # Existing protective exit is an independent original-path comparator,
    # not silently recalculated under a new hierarchy.
    original=(dict(type='original_model_exit',time=trade['legs'][-1]['time_ny'],
        price=trade['legs'][-1]['price'],fraction_initial=1.0,pnl=pnl(trade['entry'],trade['legs'][-1]['price']))
        if trade.get('legs') else None)
    ordered=sorted(events+([original] if original else []),key=lambda e:ts(e['time']))
    for i,event in enumerate(ordered):
        event['conditional_after_earlier_exit']=i>0
    return dict(first_candidate=ordered[0] if ordered else None,events=ordered,original_exit=original,
        caveat='Conditional on retaining the frozen entry. Later signals are observations only after the earliest exit. No rule cancels a previous-bar midpoint when the current bar makes another new high; that would need a separate decision.')


def low_confirmation(minutes,low_t):
    hour=low_t//3600*3600;buckets=groups(minutes,3600)
    window=[buckets.get(t,[]) for t in (hour-3600,hour,hour+3600)]
    if any(not g or not complete(g,3600) for g in window):
        return None
    a,p,c=[aggregate(g,3600) for g in window]
    return local(hour+7200) if p['low']<a['low'] and p['low']<c['low'] else None


def lower_swing_candidates(ledger,peak_t,asof):
    """Diagnostic only: completed adjacent-15m troughs, not a new bounce rule.

    The owner specified four independent rebound-confirmed lower swing lows.
    Rebound strength is not yet quantified. Keep these candidates separate
    from that confirmation rather than relabeling four lower-price candles.
    """
    bars=[b for b in ledger if peak_t<=b['t'] and b['t']+900<=asof]
    if not bars:
        return []
    record=bars[0]['low'];out=[]
    for a,p,c in zip(bars,bars[1:],bars[2:]):
        if p['t']!=a['t']+900 or c['t']!=p['t']+900 or any(b['observed_minutes']!=15 for b in (a,p,c)):
            continue
        if p['low']<min(a['low'],c['low'],record):
            out.append(dict(bar_start=local(p['t']),low=p['low'],
                diagnostic_known_at=local(c['t']+900),status='local-trough candidate; not asserted to satisfy an unquantified rebound rule'))
            record=p['low']
    return out


def owner_four_lows(folder,fixture,minutes):
    """Verify owner-marked full-decline waves without resetting at child peaks.

    This is an annotated-case check, not an invented general wave detector.
    A completed rebound bar supplies a conservative known-by time, not a
    claim about the earliest intrabar confirmation. Providers remain separate.
    """
    payload=(folder/'OWNER_FOUR_LOWS_SOURCE.json').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=OWNER_SOURCE_SHA256:
        raise ValueError('Owner-annotated source extraction changed')
    source=json.loads(payload)
    image=folder/source['screenshot_file']
    if hashlib.sha256(image.read_bytes()).hexdigest()!=source['screenshot_sha256']:
        raise ValueError('Original owner chart changed')
    coinbase={b['t']:b for b in source['bars']}
    alpaca={b['t']:b for b in fixture['ledger']}
    rebound_starts=['06:30','07:45','11:00','16:45']
    alpaca_windows=[('06:00','06:45','06:30'),('07:30','08:30','08:15'),
        ('10:30','11:15','11:00'),('16:15','17:00','16:45')]
    def at(clock):
        return ts('2026-11-07T'+clock+':00-05:00')
    evidence=[]
    for number,(anchor,rebound_clock,window) in enumerate(zip(source['owner_selected_lows'],rebound_starts,alpaca_windows),1):
        t=ts(anchor);low=coinbase[t];bounce=coinbase[at(rebound_clock)]
        if not (low['low']<coinbase[t-900]['low'] and low['low']<coinbase[t+900]['low']
                and bounce['close']>bounce['open'] and bounce['low']>low['low']):
            raise ValueError('Owner-marked Coinbase low lacks the recorded completed rebound evidence')
        begin,end,alpaca_bounce=window
        phase=[b for b in minutes if at(begin)<=b['t']<at(end)]
        if [b['t'] for b in phase]!=list(range(at(begin),at(end),60)):
            raise ValueError('Missing minutes in an Alpaca wave; do not fill')
        minimum=min(phase,key=lambda b:b['low']);ab=alpaca[at(alpaca_bounce)]
        if not (ab['observed_minutes']==15 and ab['close']>ab['open'] and ab['low']>minimum['low']):
            raise ValueError('Alpaca phase lacks completed rebound evidence')
        evidence.append(dict(number=number,owner_15m_start=anchor,
            coinbase_low=low['low'],coinbase_rebound_bar=local(bounce['t']),
            coinbase_rebound_ohlc={k:bounce[k] for k in ('open','high','low','close')},
            coinbase_known_by=local(bounce['t']+900),
            alpaca_phase_low=minimum['low'],alpaca_low_minute=local(minimum['t']),
            alpaca_rebound_bar=local(ab['t']),alpaca_known_by=local(ab['t']+900),
            confirmation_status='owner-accepted independent wave, with completed real rebound evidence'))
    for field in ('coinbase_low','alpaca_phase_low'):
        if not all(b[field]<a[field] for a,b in zip(evidence,evidence[1:])):
            raise ValueError('The four marked waves are not successively lower in this provider')
    return dict(count_origin=source['count_origin'],origin_role='full-decline peak, not the 18:45 or 20:00 internal rebound',
        coinbase_origin_high=coinbase[ts(source['count_origin'])]['high'],
        alpaca_origin_high=alpaca[ts(source['count_origin'])]['high'],
        source_sha256=OWNER_SOURCE_SHA256,screenshot_sha256=source['screenshot_sha256'],
        evidence=evidence,confirmed_count=4,known_by=max(e['coinbase_known_by'] for e in evidence),
        alpaca_known_by=max(e['alpaca_known_by'] for e in evidence),
        manual_case_only=True,child_rebounds_do_not_reset_count=True,
        caveat='Owner annotations identify the four waves. The general automated parent-wave selection algorithm is not validated by this one case; no monthly result is changed.')


def owner_ll_lh_sequence(folder,fixture):
    """Audit alternating owner-marked lows and rebound highs on real 15m bars.

    The fourth rebound is HH relative to the prior rebound high, not relative
    to the whole decline's initial peak. Do not force it into an LH label.
    """
    payload=(folder/'OWNER_WAVE_SEQUENCE_SOURCE.json').read_bytes()
    if hashlib.sha256(payload).hexdigest()!=SEQUENCE_SOURCE_SHA256:
        raise ValueError('Preserved wave-sequence source changed')
    source=json.loads(payload);out={}
    def at(clock):
        return ts('2026-11-07T'+clock+':00-05:00')
    periods=[('06:15','07:30'),('07:30','10:45'),('10:45','16:30'),('16:30','21:15')]
    for provider,bars in (('Coinbase',source['bars']),('Alpaca',fixture['ledger'])):
        by_time={b['t']:b for b in bars};prior_peak=by_time[at('04:00')]['high'];rebounds=[]
        for i,(low,next_low) in enumerate(periods,1):
            eligible=[b for b in bars if at(low)+900<=b['t']<at(next_low)]
            peak=max(eligible,key=lambda b:b['high'])
            left=by_time[peak['t']-900];right=by_time[peak['t']+900]
            if not (peak['high']>left['high'] and peak['high']>right['high']):
                raise ValueError('Nominated rebound lacks the recorded completed turn evidence')
            rebounds.append(dict(after_low_number=i,bar_start=local(peak['t']),high=peak['high'],
                previous_rebound_high=prior_peak,label=('LH' if peak['high']<prior_peak else 'HH' if peak['high']>prior_peak else 'equal_high'),
                turn_known_by=local(right['t']+900)))
            prior_peak=peak['high']
        old_high=rebounds[2]['high'];first_break=next(b for b in bars if b['t']>=at('16:45') and b['high']>old_high)
        low=by_time[at('21:15')];base=by_time[at('16:30')]
        if not (low['low']<by_time[at('21:00')]['low'] and low['low']<by_time[at('21:30')]['low']):
            raise ValueError('Later higher low lacks the recorded completed local-turn evidence')
        out[provider]=dict(rebounds=rebounds,first_three_are_lower_highs=all(b['label']=='LH' for b in rebounds[:3]),
            fourth_rebound_label=rebounds[3]['label'],structure_strengthens=rebounds[3]['label']=='HH',
            strength_signal_15m_interval=local(first_break['t']),strength_signal_interval_end=local(first_break['t']+900),
            strength_reference=old_high,strength_highest_reference='previous rebound high, not 04:00 whole-decline peak',
            subsequent_higher_low=dict(bar_start=local(low['t']),low=low['low'],base_low=base['low'],
                higher=low['low']>base['low'],turn_known_by=local(at('21:45'))))
    return dict(timeframe='15Min',owner_confirmed_label_rule='A rebound exceeding the preceding rebound high is structure strengthening (HH), not LH.',
        sequence='LL1 -> LH1 -> LL2 -> LH2 -> LL3 -> LH3 -> LL4 -> HH -> HL -> local breakout',
        providers=out,source_sha256=SEQUENCE_SOURCE_SHA256,monthly_engine_unchanged=True,
        other_timeframes='30Min and 1Hour reserved for later same-source comparisons; not used to relabel this case',
        scope='Owner-annotated in-sample sequence only. Extrema are reviewed within nominated intervals; turn-known-by evidence is reported, not presented as a validated general live wave detector.')


def review(folder=FOLDER):
    fixture,minutes=load(folder);by_time={b['t']:b for b in minutes}
    trades={p['id']:p for p in fixture['trades']}
    cases={str(i):dict(entry=trades[i]['entry'],entry_time=local(ts(trades[i]['entry_time'])),
        original_references=trades[i]['references'],exit_review=scan_exits(trades[i],minutes)) for i in (23,24,25)}
    p=trades[23];old=p['references']['l1'];entry=ts(p['entry_time'])
    before=[b for b in minutes if ts(old['time'])<b['t']<entry]
    breach=next(b for b in before if b['low']<old['price']);new=min(before,key=lambda b:b['low'])
    cases['23']['hierarchy']=dict(original_d=old,first_undercut=local(breach['t']),
        original_d_already_undercut_before_entry=True,new_large_d_candidate=dict(time=local(new['t']),price=new['low'],
            low_bar_end=local(new['t']//900*900+900),hour_pivot_confirmed_at=low_confirmation(minutes,new['t'])),
        qualification='Local entry trigger is retained for the exit exercise. Strict hourly D eligibility is unresolved at entry; no future confirmation is backdated and no existing stop is widened.')
    p=trades[24];h=p['references']['h1'];entry=ts(p['entry_time'])
    hit=next(b for b in minutes if b['t']>=entry and b['high']>h['price'])
    pullback=[b for b in minutes if ts(h['time'])+900<=b['t']<hit['t']]
    lowest=min(pullback,key=lambda b:b['low']);breakout_period=hit['t']//900*900
    atr=next(r['atr_before'] for r in fixture['ledger'] if r['t']==breakout_period)
    cases['24']['hierarchy']=dict(parent_peak=h,first_parent_peak_break=local(hit['t']),
        whole_pullback_low=dict(time=local(lowest['t']),price=lowest['low'],hour_pivot_confirmed_at=low_confirmation(minutes,lowest['t'])),
        internal_low_not_parent=75862.817,internal_low_time='2026-11-07T02:23:00-05:00',
        original_promoted_stop=p['stop'],cycle_stop_candidate=lowest['low']-.25*atr,
        candidate_effective_at=local(breakout_period+900),breakout_atr_before=atr,
        scope='Audit the fixed formation H1 and its complete correction after the frozen entry; this does not prove the original entry D was the only possible ancestor.')
    p=trades[25];held=[b for b in minutes if ts(p['entry_time'])<=b['t']<=ts(p['exit_time'])]
    cases['25']['hierarchy']=dict(parent_d=p['references']['l1'],parent_peak=p['references']['h1'],
        highest_after_entry=max(b['high'] for b in held),parent_peak_broken=False,
        parent_promotions=[],initial_stop=p['initial_stop'],original_stop_exit=p['legs'][-1])
    at=ts('2026-11-07T21:30:00-05:00');bucket=groups(minutes)
    previous=aggregate(bucket[at-900],900);current=aggregate(bucket[at],900)
    root_low=min((b for b in minutes if ts('2026-11-07T16:30:00-05:00')<=b['t']<ts('2026-11-07T16:45:00-05:00')),key=lambda b:b['low'])
    screen=fixture['known_target_screen_2130'];trigger=previous['high']+.01;stop=root_low['low']-.25*screen['atr_before']
    parent_bar=max((r for r in fixture['ledger'] if root_low['t']<r['t'] and r['t']+900<=at),key=lambda r:r['high'])
    later=next(b for b in minutes if b['t']>=at and b['high']>trigger)
    cases['2130']=dict(parent_d=dict(time=local(root_low['t']),price=root_low['low'],confirmed_at=low_confirmation(minutes,root_low['t'])),
        parent_peak=dict(time=local(parent_bar['t']),price=parent_bar['high']),
        internal_d_rejected=dict(time='2026-11-07T19:36:00-05:00',price=75607.5,reason='Internal rebound did not break the retained parent peak'),
        previous_15m=dict(time=local(at-900),high=previous['high'],low=previous['low']),
        candidate_15m=dict(time=local(at),high=current['high'],low=current['low']),
        higher_low_pass=previous['low']>root_low['low']+.1*screen['atr_before'],trigger=trigger,
        own_feed_breakout=False,shortfall_to_previous_high=previous['high']-current['high'],
        later_crossing_minute=local(later['t']),initial_stop_if_triggered=stop,
        unchanged_target=screen['target1'],target_known_at=screen['known_at'],
        hypothetical_net_reward_risk=reward_risk(trigger,stop,screen['target1'],2),
        entry=False,reason='L1 rank correction restores the larger-base higher-low structure, but neither an own-feed breakout nor the unchanged 2R gate passes at 21:30. Do not mix Coinbase highs with Alpaca current prices.')
    next_at=at+900
    prior=current
    next_trigger=prior['high']+.01
    next_hit=next(b for b in minutes if next_at<=b['t']<next_at+900 and b['high']>next_trigger)
    next_atr=next(r['atr_before'] for r in fixture['ledger'] if r['t']==next_at)
    next_price=max(next_trigger,next_hit['open'])
    next_stop=root_low['low']-.25*next_atr
    # This exact resistance zone was already known at 21:30. Only the
    # pre-21:45 ATR buffer changes; no later peak is used as a target.
    next_target=screen['zone']['lower']-.1*next_atr
    cases['2145']=dict(parent_d=cases['2130']['parent_d'],parent_peak=cases['2130']['parent_peak'],
        retained_l2=dict(time=local(at-900),price=previous['low']),
        trigger_bar=dict(time=local(next_at),end=local(next_at+900)),
        previous_15m=dict(time=local(at),high=prior['high'],low=prior['low']),
        trigger=next_trigger,price=next_price,price_signal=True,
        signal_time=local(next_hit['t']),signal_interval_end=local(next_hit['t']+60),
        exact_second_verified=False,quote_reference_minute=next_hit['volume']==0,
        l2_unbroken_before_trigger=all(b['low']>=previous['low'] for b in minutes if at<=b['t']<next_hit['t']),
        legacy_previous_bar_is_pullback_minimum=False,
        legacy_previous_bar_lower_than_older=False,
        atr_before=next_atr,initial_stop_if_triggered=next_stop,target=next_target,
        target_zone_known_at=screen['known_at'],
        gross_reward_risk=(next_target-next_price)/(next_price-next_stop),
        net_reward_risk=reward_risk(next_price,next_stop,next_target,2),
        qualified_under_unchanged_2r=False,
        reason='A real price signal occurs within the 21:45 bar. The frozen engine silently loses it because it requires the immediately preceding bar to be a fresh pullback minimum; the retained L2 remains unbroken. With parent D restored, net 2R still fails. Record the price signal separately from entry eligibility.')
    wave_review=owner_four_lows(folder,fixture,minutes)
    wave_sequence=owner_ll_lh_sequence(folder,fixture)
    cases['2145']['new_four_swing_rule']=dict(required_independent_lower_swings=4,
        consecutive_lower_candles_do_not_count_as_independent_swings=True,
        local_peak=dict(time='2026-11-07T20:00:00-05:00',price=75725.2395),
        local_peak_diagnostic_candidates=lower_swing_candidates(fixture['ledger'],ts('2026-11-07T20:00:00-05:00'),next_hit['t']),
        parent_peak_diagnostic_candidates=lower_swing_candidates(fixture['ledger'],ts(cases['2130']['parent_peak']['time']),next_hit['t']),
        owner_full_decline_review=wave_review,
        owner_ll_lh_sequence=wave_sequence,
        previous_short_scope_conclusion='superseded: counting from child rebound peaks incorrectly discarded earlier waves',
        qualifying_four_swings_demonstrated=True,
        entry=False,
        remaining_entry_block='unchanged net reward/risk is below 2; four-wave condition now passes',
        scope='Owner supplied the count origin and four wave lows, correcting the prior mistaken child-peak reset. Verify each provider separately. General automatic wave ranking remains to be specified; this is an annotated case, not a monthly rerun.')
    cases['2130']['four_swing_gate_passed']=True
    return dict(scope='Only #23, #24, #25 and November 7 21:30/21:45 follow-up; no monthly rerun or engine changes',
        run_id=fixture['run_id'],original_run_sha256=fixture['original_run_sha256'],source_sha256=FIXTURE_SHA256,
        source=fixture['source'],source_observations=len(minutes),
        review_rules=dict(parent='Keep setup parent D/H1; classify internal pullbacks separately. Promote only the lowest point of a whole correction after the retained parent peak breaks, with confirmation available at the time. Broken D is invalid, not frozen forever.',
            new_high='Must exceed frozen formation H1 and all earlier completed post-entry highs; tiny internal post-entry highs do not qualify.',
            midpoint='Next bar trades strictly below the previous completed new-wave-high candle full-range midpoint. No wait for current 15m close. Full remaining exit.',
            wick='At last-minute first observation, >=50% upper wick at a new wave high, above entry; no $1000 gate. Shape-only interpretation, without an unagreed extra resistance filter.',
            costs='Zero commission, 2bps each way; 1 initial BTC; not actual ETF returns'),
        cases=cases)


if __name__=='__main__':
    result=review()
    (FOLDER/'FOUR_CASE_HIERARCHY_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    for ident,case in result['cases'].items():
        print(ident,json.dumps(case.get('exit_review',{}).get('first_candidate',case),ensure_ascii=False))
