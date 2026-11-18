"""Build isolated SOL 0.1 research from real saved SOL tape; no live changes."""
from __future__ import annotations
import copy,gzip,hashlib,json,math,sqlite3,statistics,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,save,ts,iso
from trading_desk.btc_live import CONTROLLER as BTC,verify_rules,RULE_FILES
from trading_desk.sol_live import CONTROLLER as SOL
from trading_desk.crypto_transfer import STUDIES as SOURCES,enrich,summarize,csv_table
from trading_desk.btc_engine import export_csv
from trading_desk.unfiltered_90d import funded_account,loss_analysis
from trading_desk.sol_model01 import ARMS,PROTOCOL,make_engine,Contexts
from scripts.retest_refined_entries import signature,compare

STUDIES=ROOT/'trading_records/sol_structure/studies'
RELEASE=ROOT/'trading_records/sol_structure/releases/0.1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(arm,bars,market,quality,start,end,folder,expected=None):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=make_engine(arm,start,end,db,market)
    try:
        for b in bars:engine.minute(b)
        r=engine.finish();db.commit()
        r.update(symbol='SOL/USD',model=arm,start=iso(start),end=iso(end),last_price=engine.last_price,
            status='complete',source_quality=quality,orders_enabled=False,live_promoted=False,sol_protocol=PROTOCOL)
        enrich(r,'SOL/USD',arm,quality);r['summary']=summarize(r);r['loss_analysis']=loss_analysis(r['trades'])
        if expected:
            assert len(r['trades'])==len(expected['trades'])
            assert all(signature(a)==signature(b) and a['entry_time']==b['entry_time'] and a['entry_rule']==b['entry_rule'] for a,b in zip(r['trades'],expected['trades'],strict=True))
            assert r['metrics']==expected['metrics']
        r['account']=funded_account(r['trades'],bars,start,end,folder)
        for p in r['trades']:p['cash_scenario']=r['account']['account_trades'][p['id']]
        if hasattr(engine.detector,'shock_reviews'):r['sol_shock_reviews']=engine.detector.shock_reviews
        export_csv(folder,r,db);save(folder/'result.json',r);return r
    finally:db.close()


def run():
    source=SOURCES/read(SOURCES/'ACTIVE.json')['study_id'];s=read(source/'STUDY.json');prior=read(source/'SOL_USD/E1/result.json')
    path=source/'data/SOL_USD_MINUTES.jsonl.gz';q=s['source_quality']['SOL/USD'];assert sha(path)==q['archive_sha256']
    with gzip.open(path,'rt') as z:all_bars=[json.loads(l) for l in z]
    assert all(b['t']>a['t'] for a,b in zip(all_bars,all_bars[1:]))
    before=BTC.status();sol=SOL.status();assert before['enabled'] and not sol['enabled']
    identity=dict(pid=before['pid'],session=before['session']['id']);rules=verify_rules()
    protected={}
    for base in (source,ROOT/'trading_records/btc_structure/releases/0.2'):
        for p in base.rglob('*'):
            if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
    for p in (SOURCES/'ACTIVE.json',ROOT/'trading_desk/btc_live.py',ROOT/'scripts/run_btc_live.py',ROOT/'trading_desk/btc_live.html',ROOT/'trading_desk/btc_live.js',ROOT/'trading_desk/sol_live.py',ROOT/'scripts/run_sol_live.py'):
        protected[str(p.relative_to(ROOT))]=sha(p)
    code={p:sha(ROOT/p) for p in ('trading_desk/sol_model01.py','scripts/study_sol01.py')}
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-sol01';folder=STUDIES/ident;folder.mkdir(parents=True,exist_ok=False)
    study=dict(study_id=ident,status='running',symbol='SOL/USD',version='0.1',protocol=PROTOCOL,source_study=str(source.relative_to(ROOT)),
        start=s['start'],end=s['end'],source_quality=q,source_sha256=sha(path),code_hashes=code,rule_hashes=rules,
        btc_before=identity,sol_paused=True,orders_enabled=False,live_promoted=False,books=[],control_reproduced=False)
    save(folder/'STUDY.json',study);save(folder/'PROTOCOL_BEFORE_RESULTS.json',PROTOCOL);save(folder/'PRESERVED_BEFORE.json',protected)
    start=ts(s['start']);end=ts(s['end']);d=86400
    windows=(('full30',start,end),('first14',start,start+14*d),('next7',start+14*d,start+21*d),('final9',start+21*d,end))
    # The candidate and four arms are fixed above before their first replay.
    summaries=[];tape=[];full={}
    for phase,a,b in windows:
        bars=[r for r in all_bars if a-7*d<=r['t']<b];market=Contexts(bars)
        for arm in ARMS:
            r=execute(arm,bars,market,q,a,b,folder/phase/arm,prior if phase=='full30' and arm=='original_e1' else None)
            if phase=='full30':full[arm]=r
            ac=r['account'];lo=r['loss_analysis'];row=dict(phase=phase,arm=arm,start=iso(a),end=iso(b),
                trades=len(r['trades']),closed=lo['closed'],wins=lo['wins'],losses=lo['losses'],return_pct=ac['return_pct'],
                max_observed_drawdown_pct=ac['max_observed_drawdown_pct'],fixed_10000_net=r['summary']['all']['normalized_10000_realized'],
                open_fixed_10000=r['summary']['all']['normalized_10000_unrealized'],cash=ac['cash'],open_units=ac['open_units'],
                flagged_trades=sum(p['gap_exposed'] or p['context_partial'] for p in r['trades']))
            summaries.append(row);print(json.dumps(row),flush=True)
        if phase=='full30':study['control_reproduced']=True
        study['books']=summaries;save(folder/'STUDY.json',study)
    market=Contexts(all_bars)
    for p in prior['trades']:
        sig=next(s for s in prior['signals'] if s['id']==p['signal_id']);ev=sig['setup_evidence'];imp=ev.get('impulse');ctx=market.before(imp['t']) if imp else None
        net=(ev['previous_close']-imp['close'])/ctx['atr'] if ctx else None
        tape.append(dict(id=p['id'],entry_rule=p['entry_rule'],entry_time=p['entry_time'],entry=p['entry'],D=p['references']['l1'],L2=p['references'].get('l2'),
            initial_stop=p['initial_stop'],initial_risk_pct=100*(p['entry']-p['initial_stop'])/p['entry'],target=p['t1'],target_net_r=sig['net_reward_risk'],
            exit_time=p.get('exit_time'),legs=p['legs'],net=p['net'],fixed_10000_net=p['normalized_10000_realized_net'],
            context_partial=p['context_partial'],missing_held_minutes=p['actual_missing_minutes_while_held'],quote_reference=p['quote_reference_entry'],
            sol_net_shock_atr=net,shock_context=ctx,original_confirmation_after_D=bool(ev.get('d') and ts(sig['previous_bar_time'])>=ev['d']['known_at']),
            original_signal_id=p['signal_id']))
    changes=compare(full['original_e1'],full['sol_01']);save(folder/'CHANGES.json',changes);save(folder/'TAPE.json',tape)
    csv_table(folder/'TAPE.csv',tape);csv_table(folder/'SUMMARY.csv',summaries)
    csv_table(folder/'CHANGES.csv',[dict(time=c['time'],status=c['status'],original_id=c['original']['id'] if c['original'] else None,
        candidate_id=c['refined']['id'] if c['refined'] else None,delta_fixed_10000=c['delta_normalized_10000']) for c in changes])
    study['change_counts']={k:sum(c['status']==k for c in changes) for k in ('unchanged','changed','relabelled_only','added','removed')}
    for p,h in protected.items():assert sha(ROOT/p)==h,p
    for p,h in code.items():assert sha(ROOT/p)==h,p
    after=BTC.status();assert identity==dict(pid=after['pid'],session=after['session']['id']) and after['enabled']
    assert not SOL.status()['enabled'] and verify_rules()==rules
    study.update(status='complete',btc_after=identity,preserved_files=len(protected));save(folder/'STUDY.json',study)
    if RELEASE.exists():raise ValueError('SOL 0.1 candidate bundle already exists; never overwrite a recorded version')
    (RELEASE/'source').mkdir(parents=True)
    hashes={}
    for name in [*RULE_FILES,*code]:
        dest=RELEASE/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes());hashes[str(dest.relative_to(RELEASE))]=sha(dest)
    save(RELEASE/'MODEL.json',dict(version='0.1',status='research_candidate_not_live',symbol='SOL/USD',protocol=PROTOCOL,study_id=ident,files_sha256=hashes,
        evaluated_arms=list(ARMS),selected_before_results='sol_01',orders_enabled=False,live_promoted=False))
    save(STUDIES/'ACTIVE.json',dict(study_id=ident));print('COMPLETE',ident,flush=True)


if __name__=='__main__':run()
