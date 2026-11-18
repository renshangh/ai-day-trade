"""Original BTC live models on actual IBIT RTH tape, isolated from live workers."""
from __future__ import annotations
import copy,gzip,hashlib,json,sqlite3,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso
from trading_desk.btc_live import CONTROLLER as BTC,verify_rules,RULE_FILES
from trading_desk.sol_live import CONTROLLER as SOL
from trading_desk.ibit_model import POLICY,make_engine
from trading_desk.ibit_sessions import Calendar,cash_account
from trading_desk.crypto_transfer import enrich,csv_table
from trading_desk.btc_engine import export_csv
from trading_desk.unfiltered_90d import loss_analysis

STUDIES=ROOT/'trading_records/ibit_structure/studies'
INPUT=ROOT/'trading_records/ibit_structure/inputs/20261003-20261109'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    before=BTC.status();assert before['enabled'];identity=dict(pid=before['pid'],session=before['session']['id'])
    assert not SOL.status()['enabled'];rules=verify_rules()
    files={p:sha(ROOT/p) for p in [*RULE_FILES,'trading_desk/btc_live.py','trading_desk/btc_live.html','trading_desk/btc_live.js','scripts/run_btc_live.py','trading_desk/sol_live.py','scripts/run_sol_live.py']}
    for base in (INPUT,ROOT/'trading_records/btc_structure/releases/0.2',ROOT/'trading_records/sol_structure/releases/0.1'):
        for p in base.rglob('*'):
            if p.is_file():files[str(p.relative_to(ROOT))]=sha(p)
    code={p:sha(ROOT/p) for p in ('trading_desk/ibit_model.py','trading_desk/ibit_sessions.py','scripts/study_ibit.py')}
    start=ts('2026-10-10T00:00:00Z');end=ts('2026-11-09T00:00:00Z');warmup=start-7*86400
    calendar=Calendar(read(INPUT/'CALENDAR.json'),warmup,end)
    with gzip.open(INPUT/'IBIT_MINUTES.jsonl.gz','rt') as z:bars=[json.loads(l) for l in z]
    assert all(b['t'] in calendar.allowed for b in bars)
    assert all(b['t']>a['t'] for a,b in zip(bars,bars[1:]));actual={b['t'] for b in bars}
    quality=read(INPUT/'QUALITY.json')['IBIT'];assert set(quality['missing'])==calendar.allowed-actual
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-ibit-rth';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',policy=POLICY,start=iso(start),end=iso(end),warmup_start=iso(warmup),
        input_path=str(INPUT.relative_to(ROOT)),quality=quality,test_expected=sum(start<=t<end for t in calendar.minutes),
        test_observed=sum(start<=b['t']<end for b in bars),code_hashes=code,rule_hashes=rules,btc_before=identity,
        orders_enabled=False,live_promoted=False,holding_assumption='Carry overnight; no forced daily close',books=[])
    save(folder/'STUDY.json',study);save(folder/'PROTOCOL_BEFORE_RESULTS.json',POLICY);save(folder/'PRESERVED_BEFORE.json',files)
    save(folder/'SOURCE_BUNDLE.json',{p:(ROOT/p).read_text() for p in code})
    summary=[]
    for arm in ('exact_control','session_adapted'):
        for model in ('0.1','E1','E2'):
            book=folder/arm/model;book.mkdir(parents=True);db=sqlite3.connect(book/'ledger.sqlite');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
            engine=make_engine(model,start,end,db,calendar,arm=='session_adapted')
            try:
                for b in bars:engine.minute(b)
                r=engine.finish();db.commit();r.update(symbol='IBIT',model=model,arm=arm,start=iso(start),end=iso(end),status='complete',last_price=engine.last_price,orders_enabled=False,live_promoted=False,source_quality=quality)
                enrich(r,'IBIT',model,quality);r['loss_analysis']=loss_analysis(r['trades'])
                for p in r['trades']:p['units']='share'
                r['account']=cash_account(r['trades'],bars,start,end,calendar,book)
                for p in r['trades']:p['cash_scenario']=r['account']['account_trades'][p['id']]
                r['calendar_closed_intervals']=copy.deepcopy(getattr(engine,'closed_intervals',[]));r['target_reviews']=copy.deepcopy(getattr(engine,'target_reviews',[]))
                r['resistance_diagnostics']=dict(large_peaks=len(engine.rth_resistance.large) if arm=='session_adapted' else len(engine.large_peaks),hour_peaks=len(engine.rth_resistance.peaks) if arm=='session_adapted' else len(engine.major.peaks))
                lo=r['loss_analysis'];a=r['account'];row=dict(arm=arm,model=model,trades=len(r['trades']),wins=lo['wins'],losses=lo['losses'],
                    return_pct=a['return_pct'],observed_drawdown_pct=a['max_observed_drawdown_pct'],
                    fixed_10000_realized=sum(p['normalized_10000_realized_net'] for p in r['trades']),fixed_10000_open=sum(p['normalized_10000_unrealized_net'] for p in r['trades']),
                    open_units=a['open_units'],signals=len(r['signals']),missing_targets=r['signal_counts']['target_missing'],
                    missing_rth_minutes=a['missing_test_minutes'],known_large_peaks=r['resistance_diagnostics']['large_peaks'],
                    scheduled_closures=len(r['calendar_closed_intervals']),clock_missing_counter=r['counts'].get('missing_minutes',0))
                export_csv(book,r,db);save(book/'result.json',r);summary.append(row);study['books']=summary;save(folder/'STUDY.json',study);print(json.dumps(row),flush=True)
            finally:db.close()
    csv_table(folder/'SUMMARY.csv',summary)
    for p,h in files.items():assert sha(ROOT/p)==h,p
    for p,h in code.items():assert sha(ROOT/p)==h,p
    after=BTC.status();assert identity==dict(pid=after['pid'],session=after['session']['id']) and after['enabled']
    assert not SOL.status()['enabled'] and verify_rules()==rules
    study.update(status='complete',btc_after=identity,preserved_files=len(files));save(folder/'STUDY.json',study);save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)


if __name__=='__main__':run()
