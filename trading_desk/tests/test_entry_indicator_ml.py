"""Real native VWAP/volume only; causal features and matched ablations."""
import gzip,json,sys,math
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.crypto_transfer import STUDIES
from trading_desk.entry_quality_view import VIEW as OLD
from trading_desk.adaptive_shock import Contexts
from trading_desk.entry_indicator_ml import Indicators,ARMS,names,fit
from scripts.study_entry_indicators import load_native,dataset_for

@pytest.fixture(scope='module')
def actual():
    source=STUDIES/read(STUDIES/'ACTIVE.json')['study_id'];s=read(source/'STUDY.json');inputs={};original={}
    for symbol in ('BTC/USD','SOL/USD'):
        with gzip.open(source/'data'/(symbol.replace('/','_')+'_MINUTES.jsonl.gz'),'rt') as z:inputs[symbol]=[json.loads(x) for x in z]
        original[symbol]=read(source/symbol.replace('/','_')/'E1/result.json')
    native,audit,_=load_native(source,inputs)
    return inputs,native,original,s,audit


def test_native_provider_vwap_and_MA_use_only_prior_actual_observations(actual):
    inputs,native,original,s,audit=actual
    for symbol,bars in inputs.items():
        ind=Indicators(Contexts(bars),bars,native[symbol]);signals={x['id']:x for x in original[symbol]['signals']}
        signal=next(signals[p['signal_id']] for p in original[symbol]['trades'] if ind.feature(symbol,signals[p['signal_id']],'plus_ma_vwap')[0])
        period=ts(signal['time_utc'])//900*900;value=ind.before(period);v=value['vwap'];m=value['ma']
        source=[b for b in bars if v['session_start']<=b['t']<period];trades=[b for b in source if b['volume']>0]
        assert v['vwap']==pytest.approx(sum(native[symbol][b['t']]*b['volume'] for b in trades)/sum(b['volume'] for b in trades))
        closes=[ind.market.bars[t]['close'] for t in range(period-50*900,period,900)]
        assert m['sma20']==pytest.approx(sum(closes[-20:])/20) and m['sma50']==pytest.approx(sum(closes)/50)
        assert m['sma20_three_bars_ago']==pytest.approx(sum(closes[-23:-3])/20)
        prefix=[b for b in bars if b['t']<period];old=Indicators(Contexts(prefix),prefix,{t:x for t,x in native[symbol].items() if t<period})
        assert old.feature(symbol,signal,'plus_ma_vwap')==ind.feature(symbol,signal,'plus_ma_vwap')
        assert v['last_source_minute']+60==period and m['last_source_bar']+900==period
        assert audit[symbol]['positive_missing_native']==0
        missing=Indicators(ind.market,bars,{t:x for t,x in native[symbol].items() if t!=trades[0]['t']})
        assert missing.before(period)['vwap'] is None
        assert missing.feature(symbol,signal,'plus_ma_vwap')[0] is None
        # Quote-only minutes do not need an invented traded VWAP or weight.
        zero=next(b for b in source if b['volume']==0)
        no_quote_vw=Indicators(ind.market,bars,{t:x for t,x in native[symbol].items() if t!=zero['t']})
        assert no_quote_vw.before(period)['vwap']==v


def test_original_model_and_matched_training_cohorts(actual):
    inputs,native,original,s,_=actual;start=ts(s['start']);end=ts(s['end']);datasets={};models={}
    for arm in ARMS:
        rows=[]
        for symbol,bars in inputs.items():
            ind=Indicators(Contexts(bars),bars,native[symbol]);rows.extend(dataset_for(symbol,original[symbol],ind,arm,start,start+14*86400,start+21*86400,end))
        datasets[arm]=rows;models[arm]=fit(rows,start+14*86400,names(arm))
    folder,_=OLD.current();assert models['original_ml']==read(folder/'MODEL_BEFORE_VALIDATION_TEST.json')
    for a,b in [('matched_ma','plus_ma'),('matched_all','plus_ma_vwap')]:
        assert models[a]['training_keys']==models[b]['training_keys']
        assert [(r['key'],r['feature'] is None) for r in datasets[a]]==[(r['key'],r['feature'] is None) for r in datasets[b]]
        cutoff=start+14*86400
        eligible=[r for r in datasets[b] if r['training_eligible']]
        assert fit(eligible,cutoff,names(b))==models[b]


def test_saved_controls_hashes_and_all_matched_masks():
    import hashlib
    from trading_desk.entry_indicator_view import VIEW,BOOKS
    from trading_desk.btc_live import verify_rules
    folder,s=VIEW.current();models=read(folder/'MODELS_BEFORE_VALIDATION_TEST.json')
    assert s['status']=='complete' and s['rule_hashes']==verify_rules()
    assert len(s['controls_reproduced'])==4 and all(s['controls_reproduced'].values())
    assert len(s['original_ml_reproduced'])==4 and all(s['original_ml_reproduced'].values())
    for p,h in {**read(folder/'PRESERVED_BEFORE.json'),**s['code_hashes']}.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    assert models['plus_ma']['train_count']==19 and models['plus_ma_vwap']['train_count']==17
    for symbol,variant in BOOKS:
        base=folder/symbol.replace('/','_')/variant
        for a,b in [('matched_ma','plus_ma'),('matched_all','plus_ma_vwap')]:
            x=read(base/('FIXED_'+a+'.json'));y=read(base/('FIXED_'+b+'.json'))
            assert [(r['key'],r['abstained']) for r in x]==[(r['key'],r['abstained']) for r in y]
            assert models[a]['training_keys']==models[b]['training_keys']
        for arm in ARMS:
            result=read(base/arm/'result.json')
            for p in result['trades']:
                assert sum(l['fraction'] for l in p['legs'])+p['remaining']==pytest.approx(1)
                assert sum(l['net'] for l in p['legs'])==pytest.approx(p['realized_leg_net'])
                q=p['entry_quality'];assert q['accepted'] and (q['probability'] is None or q['probability']>=.5)
                context=(q['feature'] or {}).get('indicator_context')
                if context:
                    period=ts(p['entry_time'])//900*900
                    assert context['ma']['last_source_bar']+900==period
                    if arm in ('matched_all','plus_ma_vwap'):assert context['vwap']['last_source_minute']+60==period


def test_all_phase_partitions_reconcile_and_no_mutating_http():
    import threading,urllib.request,urllib.error
    from http.server import ThreadingHTTPServer
    from trading_desk.entry_indicator_view import VIEW,BOOKS,GROUPS
    from trading_desk.entry_quality import metrics
    for symbol,model in BOOKS:
        for arm in ARMS:
            deltas={}
            for group in GROUPS:
                d=VIEW.snapshot(symbol,model,arm,'test',group);b=next(b for b in d['summaries'] if (b['symbol'],b['model'])==(symbol,model))
                delta=b['arms'][arm]['normalized_10000_realized']-b['control']['normalized_10000_realized']
                assert sum(c['delta_normalized_10000'] for c in d['changes'])==pytest.approx(delta)
                x=next(x for x in d['fixed_summaries'] if x['arm']==arm)
                assert metrics(d['fixed_entries'])==x['metrics'];deltas[group]=delta
            assert deltas['all']==pytest.approx(deltas['no_flagged_gap']+deltas['flagged_gap_or_context'])
    with pytest.raises(ValueError):VIEW.export('all','E1','plus_ma_vwap','../.env')
    with pytest.raises(ValueError):VIEW.snapshot('ETH/USD','E1')
    sys.path.insert(0,str(ROOT/'trading_desk'));import server
    srv=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=srv.serve_forever,daemon=True);t.start();url='http://127.0.0.1:'+str(srv.server_address[1])
    try:
        with urllib.request.urlopen(url+'/api/entry-indicators') as r:d=json.load(r)
        assert d['available'] and not d['orders_enabled'] and not d['live_promoted'] and len(d['summaries'])==4
        req=urllib.request.Request(url+'/api/entry-indicators',data=b'{"operation":"trade"}',headers={'Content-Type':'application/json'})
        with pytest.raises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
        assert e.value.code==404
    finally:srv.shutdown();srv.server_close();t.join(3)
