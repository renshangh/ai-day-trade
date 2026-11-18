"""Read saved 90-day results and actual bars; no replay, tuning or worker writes."""
from __future__ import annotations
import bisect,csv,gzip,hashlib,json,statistics,sys
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso
from trading_desk.btc_engine import aggregate
from trading_desk.btc_live import verify_rules
from trading_desk.sol_live import snapshot
from trading_desk.unfiltered_90_view import VIEW

OUT=ROOT/'reports/unfiltered_90_losses_2026_11_10'
NY=ZoneInfo('America/New_York')


def median(values):
    return statistics.median(values) if values else None


def ny(t):
    return datetime.fromtimestamp(ts(t) if isinstance(t,str) else t,NY).isoformat()


def write_csv(name,rows):
    if not rows:return
    columns=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})


def worker_identity():
    s=snapshot()
    return {k:dict(pid=s[k]['pid'],session=s[k]['session']['id'],health=s[k]['health']) for k in ('btc','sol')}


def run():
    folder,study=VIEW.current();assert study['status']=='complete'
    OUT.mkdir(exist_ok=True,parents=True)
    # Include every prior study artifact, not merely strategy source files.
    protected={**read(folder/'PRESERVED_BEFORE.json'),**{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}}
    for p,h in protected.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    before=worker_identity();rules=verify_rules();assert rules==study['rule_hashes']
    result=dict(study_id=study['study_id'],study_path=str(folder),generated_at=datetime.now(timezone.utc).isoformat(),
        method='Read-only saved-trade audit, not a replay or alternative rule test. E1 is the common BTC/SOL exit policy; BTC 0.1/E2 period accounting retained.',
        split=study['original_start'],periods=[],cohorts=[],trades=[],cases=[],pairs=[],workers_before=before,
        observations='Entry and exit references are minute intervals, not verified fills. All displayed 15m bars aggregate only actual observed minutes and list their count. No missing bars or marks are invented.',
        mfe='Maximum observed minute OPEN after the entry minute and strictly before the exit minute, divided by entry minus initial stop; conservative diagnostic excludes ambiguous intraminute highs and exit-minute ordering. Not a new signal or backtest.',
        post_exit='Observed actual minutes in the following 120 minutes; first open at/above entry and extrema are hindsight diagnostics only, never retroactive fills or evidence known at entry.',
        pairing='For each of the five largest E1 fixed-$10k losses per asset, select nearest-in-time positive-net trade of same asset, entry route and early/late period; prefer same gap/context status when available. No parameter selection or causal claim.',
        orders_enabled=False,live_promoted=False)
    cut=ts(study['original_start']);start=ts(study['start']);end=ts(study['end'])
    period_ranges=(('earlier60',start,cut),('final30',cut,end))
    timeline15=[];timeline1=[];ledger_protection=[]
    for symbol in ('BTC/USD','SOL/USD'):
        sym=symbol.replace('/','_')
        with gzip.open(folder/'data'/(sym+'_MINUTES.jsonl.gz'),'rt') as z:bars=[json.loads(l) for l in z]
        times=[b['t'] for b in bars];by={b['t']:b for b in bars};groups={}
        for b in bars:groups.setdefault(b['t']//900*900,[]).append(b)
        def between(a,b):return bars[bisect.bisect_left(times,a):bisect.bisect_left(times,b)]
        for model in (('0.1','E1','E2') if symbol=='BTC/USD' else ('E1',)):
            book=folder/sym/model/'unfiltered90';r=read(book/'result.json')
            with gzip.open(book/'EQUITY.jsonl.gz','rt') as z:points=[json.loads(l) for l in z]
            prior=[p for p in points if ts(p['time_utc'])<=cut];boundary=prior[-1]
            # All four books really are flat here. Never assume this at a split.
            assert boundary['units']==0 and boundary['position_id'] is None
            for label,a,b in period_ranges:
                subset=[p for p in points if a<ts(p['time_utc'])<=b]
                capital=10000. if label=='earlier60' else boundary['equity'];final=subset[-1];peak=capital;dd=0.
                for p in subset:peak=max(peak,p['equity']);dd=max(dd,100*(peak-p['equity'])/peak)
                actual=between(a,b)
                result['periods'].append(dict(symbol=symbol,model=model,period=label,start=iso(a),end_exclusive=iso(b),
                    starting_equity=capital,ending_equity=final['equity'],return_pct=100*(final['equity']/capital-1),
                    max_observed_drawdown_pct=dd,split_position_units=boundary['units'],last_mark=final['time_utc'],
                    expected_minutes=(b-a)//60,actual_minutes=len(actual),coverage_pct=100*len(actual)/((b-a)//60),
                    buyhold_proxy_return_pct=100*(actual[-1]['close']*.9998/(actual[0]['open']*1.0002)-1)))
            if model!='E1':continue
            signals={s['id']:s for s in r['signals']};details={}
            with (book/'PROTECTION.csv').open(encoding='utf-8-sig') as z:protection=list(csv.DictReader(z))
            for p in r['trades']:
                e=ts(p['entry_time']);x=ts(p['exit_time']);risk=p['entry']-p['initial_stop'];assert risk>0
                after_entry=between(e+60,x);peak=max([p['entry']]+[b['open'] for b in after_entry]);future=between(x+60,x+121*60)
                sig=signals[p['signal_id']];ev=sig['setup_evidence'];imp=ev.get('impulse');atr=ev.get('atr_before_impulse');period=e//900*900
                row=dict(symbol=symbol,model=model,trade_id=p['id'],period='earlier60' if e<cut else 'final30',entry_rule=p['entry_rule'],
                    entry_time=p['entry_time'],entry_ny=ny(e),entry_price=p['entry'],initial_stop=p['initial_stop'],initial_price_risk_pct=100*risk/p['entry'],
                    first_target=p['t1'],initial_target_net_r=sig['net_reward_risk'],exit_time=p['exit_time'],exit_ny=ny(x),
                    exit_price=p['legs'][-1]['price'],final_reason=p['legs'][-1]['reason'],held_minutes=(x-e)//60,
                    initial_stop_reference=p['references']['l1'],entry_pullback_reference=p['references'].get('l2'),
                    net_per_coin=p['net'],fixed_10000_net=p['normalized_10000_realized_net'],net_r=p['net_r'],
                    funded_net=p['cash_scenario']['realized_net'],cost_fixed_10000=sum(l['cost'] for l in p['legs'])/p['entry']*10000,
                    max_observed_open_mfe_r=(peak-p['entry'])/risk,max_observed_open_price=peak,
                    gap_exposed=p['gap_exposed'],context_partial=p['context_partial'],flagged=bool(p['gap_exposed'] or p['context_partial']),
                    missing_held_minutes=p['actual_missing_minutes_while_held'],quote_reference_entry=p['quote_reference_entry'],
                    D_just_confirmed_at_entry_period=bool(ev.get('d') and ev['d']['known_at']==period),
                    independent_b1_hold_in_original=r['b1_independent_hold'],target_25_taken=any(l['reason']=='target_25' for l in p['legs']),
                    impulse_time=iso(imp['t']) if imp else None,impulse_range_atr=(imp['high']-imp['low'])/atr if imp and atr else None,
                    impulse_net_drop_atr=(ev['previous_close']-imp['close'])/atr if imp and atr else None,
                    impulse_frozen_downward_atr=(max(imp['open'],ev['previous_close'])-imp['low'])/atr if imp and atr else None,
                    post_exit_observed_minutes=len(future),post_exit_expected_minutes=120,
                    post_exit_120m_max_high=max((b['high'] for b in future),default=None),post_exit_120m_min_low=min((b['low'] for b in future),default=None),
                    post_exit_first_open_at_entry=next((iso(b['t']) for b in future if b['open']>=p['entry']),None),
                    legs=p['legs'],setup_evidence=ev,exit_evidence=p.get('case_exit_evidence',[]),
                    protection=[z for z in protection if int(z['trade_id'])==p['id']])
                details[p['id']]=row;result['trades'].append(row)
            for label,a,b in period_ranges:
                period_trades=[p for p in details.values() if p['period']==label]
                for exposure in ('all','no_flagged_gap','flagged_gap_or_context'):
                    subset=[p for p in period_trades if exposure=='all' or p['flagged']==(exposure=='flagged_gap_or_context')]
                    for outcome in ('all','winners','losers'):
                        ps=[p for p in subset if outcome=='all' or (p['net_per_coin']>0 if outcome=='winners' else p['net_per_coin']<0)]
                        if not ps:
                            result['cohorts'].append(dict(symbol=symbol,period=label,exposure=exposure,outcome=outcome,trades=0));continue
                        result['cohorts'].append(dict(symbol=symbol,period=label,exposure=exposure,outcome=outcome,trades=len(ps),
                            wins=sum(p['net_per_coin']>0 for p in ps),losses=sum(p['net_per_coin']<0 for p in ps),
                            normalized_net=sum(p['fixed_10000_net'] for p in ps),avg_normalized_net=statistics.mean(p['fixed_10000_net'] for p in ps),
                            normalized_cost=sum(p['cost_fixed_10000'] for p in ps),normalized_gross=sum(p['fixed_10000_net']+p['cost_fixed_10000'] for p in ps),
                            median_price_risk_pct=median([p['initial_price_risk_pct'] for p in ps]),median_mfe_open_r=median([p['max_observed_open_mfe_r'] for p in ps]),
                            below_one_r_open_mfe=sum(p['max_observed_open_mfe_r']<1 for p in ps),
                            median_impulse_range_atr=median([p['impulse_range_atr'] for p in ps if p['impulse_range_atr'] is not None]),
                            median_impulse_net_drop_atr=median([p['impulse_net_drop_atr'] for p in ps if p['impulse_net_drop_atr'] is not None]),
                            median_frozen_downward_atr=median([p['impulse_frozen_downward_atr'] for p in ps if p['impulse_frozen_downward_atr'] is not None]),
                            just_confirmed_D=sum(p['D_just_confirmed_at_entry_period'] for p in ps),quote_entries=sum(p['quote_reference_entry'] for p in ps),
                            first_target_hits=sum(p['target_25_taken'] for p in ps),
                            routes={k:dict(count=sum(p['entry_rule']==k for p in ps),normalized_net=sum(p['fixed_10000_net'] for p in ps if p['entry_rule']==k)) for k in sorted({p['entry_rule'] for p in ps})},
                            final_reasons={k:sum(p['final_reason']==k for p in ps) for k in sorted({p['final_reason'] for p in ps})}))
            worst=sorted((p for p in details.values() if p['net_per_coin']<0),key=lambda p:p['fixed_10000_net'])[:5]
            selected={p['trade_id']:{'largest_five_losses'} for p in worst}
            for p in worst:
                pool=[w for w in details.values() if w['net_per_coin']>0 and w['period']==p['period'] and w['entry_rule']==p['entry_rule']]
                matched=[w for w in pool if w['flagged']==p['flagged']];pool=matched or pool
                winner=min(pool,key=lambda w:(abs(ts(w['entry_time'])-ts(p['entry_time'])),w['entry_time'],w['trade_id'])) if pool else None
                result['pairs'].append(dict(symbol=symbol,loss_id=p['trade_id'],winner_id=winner['trade_id'] if winner else None,
                    matched_exposure=bool(matched),pairing='nearest same-route same-period winner; prefer same exposure'))
                if winner:selected.setdefault(winner['trade_id'],set()).add('nearest_same_route_winner')
            for label,_,_ in period_ranges:
                for p in sorted((p for p in details.values() if p['period']==label and p['net_per_coin']>0),key=lambda p:-p['fixed_10000_net'])[:3]:
                    selected.setdefault(p['trade_id'],set()).add('largest_three_winners_'+label)
            for ident,purposes in selected.items():
                p=details[ident];result['cases'].append(dict(**p,review_purposes=sorted(purposes)))
                e=ts(p['entry_time']);x=ts(p['exit_time']);imp=p['setup_evidence'].get('impulse');begin=min(e-3600,imp['t']-1800 if imp else e-3600);stop=min(end,x+7200)
                for b in between(begin,stop):timeline1.append(dict(symbol=symbol,trade_id=ident,time_utc=iso(b['t']),time_ny=ny(b['t']),**b))
                for t in range(begin//900*900,(stop+899)//900*900,900):
                    g=groups.get(t)
                    if not g:continue
                    b=aggregate(g,900);timeline15.append(dict(symbol=symbol,trade_id=ident,time_utc=iso(t),time_ny=ny(t),known_at=iso(t+900),
                        complete=[q['t'] for q in g]==list(range(t,t+900,60)),**b))
                ledger_protection.extend(dict(symbol=symbol,**row) for row in p['protection'])
    for p,h in protected.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    assert verify_rules()==rules
    after=worker_identity();assert all((before[k]['pid'],before[k]['session'])==(after[k]['pid'],after[k]['session']) for k in before)
    result['workers_after']=after;result['preserved_files_verified']=len(protected);result['frozen_source_hashes_verified']=len(rules)
    result['audit_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save(OUT/'BASELINE_HASHES.json',protected);save(OUT/'AUDIT.json',result)
    for name,rows in [('PERIODS.csv',result['periods']),('COHORTS.csv',result['cohorts']),('ALL_E1_TRADES.csv',result['trades']),
                      ('CASES.csv',result['cases']),('WINNER_PAIRS.csv',result['pairs']),('CASE_15MIN.csv',timeline15),('CASE_1MIN.csv',timeline1),('PROTECTION.csv',ledger_protection)]:write_csv(name,rows)
    print(json.dumps(dict(output=str(OUT),period_rows=len(result['periods']),review_cases=len(result['cases']),pairs=len(result['pairs']),minute_rows=len(timeline1),fifteen_minute_rows=len(timeline15),preserved=len(protected),workers=after),indent=2))


if __name__=='__main__':run()
