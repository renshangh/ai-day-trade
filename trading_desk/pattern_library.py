"""Outcome-selected research examples; the matcher sees entry-time features only."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
from trading_desk.btc_data import STORE,read,save,ts

ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'trading_records/pattern_discovery'
FEATURES=('impulse_atr','extension_atr','reference_range_atr','reference_body_fraction',
          'reference_close_off_low','age_bars')
DEFINITION=dict(name='B1 rapid-decline first stabilization breakout',timeframe='15 minutes',
    setup='Completed bearish new-low impulse >=2 pre-impulse ATR; extended D intact; completed off-low reference',
    trigger='First intraminute cross above previous complete 15-minute high plus $0.01; chase <=0.10 ATR',
    stop='Current extended D minus 0.25 entry ATR; full remainder exits on hard stop',
    exits='Inherited 0.1 profit protection, first 25% target, remaining 75% structural/protection exits',
    matching='Nearest positive versus nearest losing B1 example; accept only strictly closer positive',
    feature_space='log1p positive ATR ratios and age; raw candle fractions; unweighted mean absolute distance',
    target_stocks='Experimental confirmed 15m major pivot: two complete neighbors each side, >=1 ATR prominence',
    limitation='BTC-selected examples; cross-asset transfer and nearest-neighbor gate are unvalidated research drafts')


def features(signal):
    """No current-minute close/range, future bars, exits, or realized P/L."""
    if signal['route']!='B1':raise ValueError('Only reviewed B1 family is defined')
    s=signal['setup_evidence'];b=s['stabilization_bar'];a=s['atr_before_impulse'];atr=signal['atr']
    if min(a,atr)<=0 or b['observed_minutes']!=15:raise ValueError('Incomplete reference or ATR')
    now=ts(signal['time_utc'])
    if max(s['impulse']['t']+900,s['d']['known_at'],b['t']+900)>now:
        raise ValueError('Entry features contain unconfirmed evidence')
    spread=b['high']-b['low']
    if spread<=0:raise ValueError('No measured reference range')
    out=dict(impulse_atr=(max(s['impulse']['open'],s['previous_close'])-s['impulse']['low'])/a,
        extension_atr=(s['impulse']['low']-s['d']['price'])/atr,
        reference_range_atr=spread/atr,
        reference_body_fraction=(b['close']-b['open'])/spread,
        reference_close_off_low=(b['close']-b['low'])/spread,
        age_bars=(now-s['d']['known_at'])/900)
    if not all(math.isfinite(v) for v in out.values()):raise ValueError('Unavailable feature')
    return out


def vector(f):
    return [f[k] if k in ('reference_body_fraction','reference_close_off_low') else
            math.log1p(max(0,f[k])) for k in FEATURES]


def nearest(f,examples):
    v=vector(f)
    return min((dict(example_id=e['example_id'],distance=sum(abs(a-b) for a,b in zip(v,vector(e['features'])))/len(v))
        for e in examples),key=lambda e:(e['distance'],e['example_id']))


def match(f,library):
    positive=nearest(f,[e for e in library['examples'] if e.get('matching_enabled',True)]);negative=nearest(f,library['counterexamples'])
    return dict(accepted=positive['distance']<negative['distance'] and positive['distance']<=library['match_radius'],nearest_positive=positive,
        nearest_negative=negative,margin=negative['distance']-positive['distance'],
        radius=library['match_radius'],within_radius=positive['distance']<=library['match_radius'],
        interpretation='Similarity ranking/draft gate, not a probability or expected profit')


def create_library(path=HOME/'LIBRARY.json'):
    """Select exactly one predeclared baseline, not each trade's best exit model."""
    if path.exists():return read(path)
    release=STORE/'releases/0.2';rid=read(release/'REGISTRY.json')['0.2']['run_ids']['0.1']
    source=release/'results'/rid/'result.json';r=read(source)
    clean=[p for p in r['trades'] if p['net'] is not None and not(p['gap_exposed'] or p['context_partial'])]
    winners=sorted([p for p in r['trades'] if p['net'] is not None and p['net']>0],key=lambda p:(-p['net'],p['entry_time']))[:10]
    # Do not pretend the ten best trades demonstrate ten different patterns.
    if len(winners)!=10 or any(p['entry_rule']!='B1' for p in winners):
        raise ValueError('Top-ten family changed; review before defining a detector')
    losers=[p for p in clean if p['net']<0 and p['entry_rule']=='B1']
    signals={s['id']:s for s in r['signals']}
    def card(p,label,index):
        s=signals[p['signal_id']]
        return dict(example_id=f'{label}-{index:02d}',source_trade_id=p['id'],route=p['entry_rule'],
            entry_time=p['entry_time'],entry=p['entry'],initial_stop=p['initial_stop'],target=p['t1'],
            references=copy.deepcopy(p['references']),features=features(s),
            definition=copy.deepcopy(DEFINITION),setup=copy.deepcopy(s['setup_evidence']),
            quality_flag=bool(p['gap_exposed'] or p['context_partial']),
            matching_enabled=not(p['gap_exposed'] or p['context_partial']),
            outcome=dict(exit_time=p['exit_time'],legs=copy.deepcopy(p['legs']),net=p['net'],net_r=p['net_r']),
            outcome_use='Selection/review label only; excluded from live feature vector')
    library=dict(version='pattern-discovery-draft-2',selection='Top 10 net USD across all 38 frozen 0.2 baseline trades, fixed initial 1 BTC; retain flagged results in ranking',
        selection_bias='Retrospective winner selection. No independent validation or predictive success claim.',
        source_run=rid,source_result=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_minute_sha256=r['source_minute_sha256'],training_start=r['start'],training_end=r['end'],
        features=list(FEATURES),definition=DEFINITION,examples=[card(p,'winner',i+1) for i,p in enumerate(winners)],
        counterexamples=[card(p,'loser',i+1) for i,p in enumerate(losers)],
        orders_enabled=False,broker_paper_orders=False)
    if not losers:raise ValueError('Losing lookalikes required before matching')
    eligible=[e for e in library['examples'] if e['matching_enabled']]
    library['match_radius']=max(nearest(e['features'],[x for x in eligible if x['example_id']!=e['example_id']])['distance'] for e in eligible)
    library['radius_basis']='Maximum leave-one-out nearest-positive distance among unflagged ranked examples; flagged result remains visible but does not enable matching'
    save(path,library);return library


def library_digest(library):
    return hashlib.sha256(json.dumps(library,sort_keys=True).encode()).hexdigest()
