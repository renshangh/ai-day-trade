"""Real BTC/SOL observations only; no fabricated market bars or training labels."""
import copy,gzip,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.crypto_transfer import STUDIES
from trading_desk.adaptive_shock import Contexts
from trading_desk.entry_quality import features,fit,predict,FEATURES
from scripts.study_entry_quality import record,score_rows

@pytest.fixture(scope='module')
def dataset():
    source=STUDIES/read(STUDIES/'ACTIVE.json')['study_id'];s=read(source/'STUDY.json');start=ts(s['start']);end=ts(s['end']);rows=[];inputs={}
    for symbol in ('BTC/USD','SOL/USD'):
        with gzip.open(source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz'),'rt') as f:bars=[json.loads(l) for l in f]
        r=read(source/symbol.replace('/','_')/'E1/result.json');signals={x['id']:x for x in r['signals']};market=Contexts(bars);inputs[symbol]=(bars,r,signals,market)
        rows.extend(record(symbol,p,signals[p['signal_id']],market,start,start+14*86400,start+21*86400,end) for p in r['trades'])
    return rows,inputs,start+14*86400


def test_feature_prefix_invariance_and_no_entry_minute_finals(dataset):
    rows,inputs,cutoff=dataset
    for symbol,(bars,r,signals,market) in inputs.items():
        p=next(p for p in r['trades'] if features(symbol,signals[p['signal_id']],market)[0]);s=signals[p['signal_id']];now=ts(p['entry_time']);f,_=features(symbol,s,market)
        prefix=Contexts([b for b in bars if b['t']<now//900*900])
        assert features(symbol,s,prefix)[0]==f
        assert set(f['values'])==set(FEATURES) and not f['current_minute_final_values_used']
        assert f['reference_end']<=now and ts(f['D_known_at'])<=now
        missing=Contexts([b for b in bars if b['t']<now and b['t']!=now//900*900-60])
        assert features(symbol,s,missing)[0] is None


def test_training_preprocessing_and_fit_ignore_all_later_rows(dataset):
    rows,_,cutoff=dataset;m=fit(rows,cutoff);assert m['available'] and m['last_training_label']<cutoff
    eligible=[r for r in rows if r['training_eligible']];assert fit(eligible,cutoff)==m
    # Actual later records are explicitly flagged by their timestamp; even an
    # eligibility bit must not admit a label that was unknown at training time.
    later=[dict(r,training_eligible=True) for r in rows if ts(r['entry_time'])>=cutoff]
    assert fit(eligible+later,cutoff)==m
    for r in eligible:
        assert predict(m,r['feature']) is not None
        assert r['key'] in m['training_keys']
    assert not fit([],cutoff)['available'] and predict({'available':False},eligible[0]['feature']) is None


def test_saved_protocol_controls_training_model_and_all_protected_files(dataset):
    import hashlib
    from trading_desk.entry_quality_view import VIEW
    from trading_desk.entry_quality import PROTOCOL
    from trading_desk.btc_live import verify_rules
    folder,s=VIEW.current();m=read(folder/'MODEL_BEFORE_VALIDATION_TEST.json')
    assert s['protocol']==PROTOCOL and s['status']=='complete'
    assert len(s['controls_reproduced'])==4 and all(s['controls_reproduced'].values())
    assert len(s['abstention_controls_reproduced'])==4 and all(s['abstention_controls_reproduced'].values())
    assert s['rule_hashes']==verify_rules()
    for p,h in {**read(folder/'PRESERVED_BEFORE.json'),**s['code_hashes']}.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    assert fit(*[dataset[0],dataset[2]])==m
    assert len(m['training_keys'])==len(set(m['training_keys']))==22
    assert m['features']==list(FEATURES) and m['cutoff']==.5
    for p,source in read(folder/'SOURCE_BUNDLE.json').items():assert hashlib.sha256(source.encode()).hexdigest()==s['code_hashes'][p]


def test_open_trade_has_no_invented_label_and_a_rejection_does_not_consume_history(dataset):
    import sqlite3
    from trading_desk.entry_quality import FilterEarly
    from trading_desk.entry_quality_view import VIEW
    from scripts.btc_structure_retest import Config
    rows,inputs,cutoff=dataset;folder,_=VIEW.current();model=read(folder/'MODEL_BEFORE_VALIDATION_TEST.json')
    # Inspect an actual archived open trade from a different study, not a fake bar.
    source=STUDIES/read(STUDIES/'ACTIVE.json')['study_id'];r=read(source/'ETH_USD/E1/result.json');p=next(p for p in r['trades'] if p['status']=='open')
    assert p.get('net') is None
    # record() accepts only BTC/SOL; the explicit label guard in fit also rejects
    # an unavailable actual outcome even when the eligibility marker is wrong.
    unknown=dict(rows[0],training_eligible=True,label=None,label_known_at=None)
    assert fit(rows+[unknown],cutoff)==model
    symbol='BTC/USD';bars,r,signals,market=inputs[symbol]
    p=next(p for p in r['trades'] if (lambda f: f is not None and predict(model,f)<.5)(features(symbol,signals[p['signal_id']],market)[0]))
    sig=copy.deepcopy(signals[p['signal_id']]);minute=next(b for b in bars if b['t']==ts(p['entry_time']))
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    e=FilterEarly(ts(p['entry_time']),ts(p['entry_time'])+3600,db,Config(first_sale_fraction=.25,resistance_mode='major1h'),early_policy='E1',expanded_b=True,consume_entry_history=True,
        quality_model=model,quality_symbol=symbol,quality_market=market)
    old=e.detector.generation;e.open_signal(minute,sig)
    assert e.position is None and e.entry_history_start is None and e.detector.generation==old
    assert sig['trade_id'] is None and sig['decision']=='entry_quality_rejected'
    assert not any(x['type']=='entry_history_consumed' for x in e.events)
    db.close()


def test_fixed_and_sequential_outcomes_all_partitions_reconcile():
    from trading_desk.entry_quality_view import VIEW,BOOKS,GROUPS
    for symbol,model in BOOKS:
        for phase in ('train','validation','test'):
            differences={}
            for group in GROUPS:
                d=VIEW.snapshot(symbol,model,phase,group);b=next(b for b in d['summaries'] if (b['symbol'],b['model'])==(symbol,model))
                rows=d['fixed_entries'];m=b['fixed']
                assert m['rows']==len(rows)
                assert sum(r['normalized_net'] for r in rows if r['accepted'])==pytest.approx(m['fixed_entry_filtered_normalized_net'])
                assert all(r['label'] in (0,1) and r['phase_label_resolved'] for r in rows)
                difference=b['filtered']['normalized_10000_realized']-b['control']['normalized_10000_realized']
                assert sum(c['delta_normalized_10000'] for c in d['changes'])==pytest.approx(difference)
                differences[group]=difference
                for c in d['changes']:
                    p=c['filtered']
                    if p:
                        q=p['entry_quality'];assert q['accepted'] and (q['probability'] is None or q['probability']>=.5)
                        assert sum(l['fraction'] for l in p['legs'])+p['remaining']==pytest.approx(1)
                        assert sum(l['net'] for l in p['legs'])==pytest.approx(p['realized_leg_net'])
            assert differences['all']==pytest.approx(differences['no_flagged_gap']+differences['flagged_gap_or_context'])
    d=VIEW.snapshot();m=d['prediction_metrics']['test']['all']
    assert m['winners_rejected']==16 and m['losses_rejected']==10
    assert m['auc']<.5 and m['brier']>m['asset_baseline_brier']


def test_get_only_http_and_safe_exports():
    import threading,urllib.request,urllib.error
    from http.server import ThreadingHTTPServer
    from trading_desk.entry_quality_view import VIEW
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    with pytest.raises(ValueError):VIEW.export('all','E1','test_filtered','../.env')
    with pytest.raises(ValueError):VIEW.snapshot('SOL/USD','E2')
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start();base='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(base+'/api/entry-quality') as r:d=json.load(r)
        assert d['available'] and not d['orders_enabled'] and not d['live_promoted'] and len(d['summaries'])==4
        req=urllib.request.Request(base+'/api/entry-quality',data=b'{"operation":"enable"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
