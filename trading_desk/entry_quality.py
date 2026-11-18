"""Isolated causal entry-pattern classifier; never imported by live workers."""
from __future__ import annotations
import copy,math
import numpy as np
from trading_desk.btc_data import ts
from trading_desk.adaptive_shock import Contexts
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay

FEATURES=('reference_body_fraction','reference_close_position','reference_range_atr','prior4_net_atr',
          'distance_from_D_atr','log_D_age_bars','breakout_chase_atr','pullback_from_prior4_high_atr','asset_SOL','route_A','route_B2')
PROTOCOL=dict(version='entry-quality-logistic-1',features=list(FEATURES),model='Pooled BTC/SOL ridge logistic regression; mean log loss plus 0.5 * 1.0 * sum(non-intercept weights squared)',
    regularization=1.0,cutoff=.5,training='First 14 days, original BTC E1 and SOL E1 entries only, one row per asset/entry; actual fully observed completed unflagged labels available before cutoff',
    label='1 if original E1 net after the fixed cost proxy is positive, else 0. Label is an outcome; excluded from features.',
    preprocessing='Train-only mean/std; no feature imputation. Prior four complete adjacent 15m bars, pre-entry ATR and causal D references only. No entry-minute final OHLCV, targets, exits or P/L inputs.',
    validation='Next 7 days diagnostic only; no hyperparameter, cutoff, feature or model refit after viewing it',
    test='Final 9 days. Fixed-entry evaluation separately from complete flat-start sequential filter replay with original exits/risk unchanged.',
    missing='Abstain and pass through original signal when causal context/features/model are unavailable; no made-up probability or bars',
    rejection='Reject only this emitted candidate; no position, no entry-history reset, no fallback route in the same minute. Inherited emitted-token handling remains; later newly emitted setups may be scored.',
    baseline='Train-only per-asset smoothed win frequency, used as a prediction benchmark; frozen controls remain the P/L benchmark',
    sample_guard='At least 12 labeled train rows and at least 4 of each class, otherwise abstain',
    limitations='Previously studied month; retrospective chronological holdout, not genuinely unseen validation. E1-label transfer to other BTC exits is reported separately. Small sample, no causal-feature or probability-calibration claim.',
    protection='No ATR/weight/entry/exit/risk/target changes to frozen 0.2 or either live worker; no orders or automatic promotion')


def features(symbol,signal,market):
    if symbol not in ('BTC/USD','SOL/USD'):raise ValueError('Choose BTC/USD or SOL/USD')
    now=ts(signal['time_utc']);period=now//900*900;bars=[market.bars.get(t) for t in range(period-4*900,period,900)]
    if signal.get('context_partial') or not all(bars):return None,'missing complete entry context'
    atr=signal.get('atr');d=signal['references']['l1'];known=ts(d['known_at']);age=(now-known)/900
    if not atr or atr<=0 or known>now or age<0:return None,'unavailable pre-entry ATR or unconfirmed D'
    b=bars[-1];spread=b['high']-b['low']
    if spread<=0:return None,'zero-range reference; no feature imputation'
    routes=signal['routes']
    f=dict(reference_body_fraction=(b['close']-b['open'])/spread,reference_close_position=(b['close']-b['low'])/spread,
        reference_range_atr=spread/atr,prior4_net_atr=(b['close']-bars[0]['close'])/atr,
        distance_from_D_atr=(b['close']-d['price'])/atr,log_D_age_bars=math.log1p(age),
        breakout_chase_atr=(signal['entry_reference']-signal['references']['trigger'])/atr,
        pullback_from_prior4_high_atr=(max(x['high'] for x in bars)-b['close'])/atr,
        asset_SOL=float(symbol=='SOL/USD'),route_A=float('A' in routes),route_B2=float('B2' in routes))
    if not all(math.isfinite(v) for v in f.values()):return None,'nonfinite feature; abstain'
    return dict(values=f,known_at=signal['time_utc'],reference_start=bars[0]['t'],reference_end=period,
        D_known_at=d['known_at'],current_minute_final_values_used=False),None


def fit(rows,cutoff):
    eligible=[r for r in rows if r.get('training_eligible') and r.get('label') in (0,1) and r.get('label_known_at')
              and ts(r['entry_time'])<cutoff and ts(r['label_known_at'])<cutoff];y=np.array([r['label'] for r in eligible],dtype=float)
    if len(y)<12 or min(int(sum(y)),int(len(y)-sum(y)))<4:
        return dict(available=False,reason='Insufficient training rows/classes; abstain',train_count=len(y),features=list(FEATURES))
    x=np.array([[r['feature']['values'][k] for k in FEATURES] for r in eligible]);mean=x.mean(0);std=x.std(0);std=np.where(std<1e-12,1.,std)
    z=(x-mean)/std;design=np.column_stack([np.ones(len(y)),z]);weights=np.zeros(design.shape[1]);weights[0]=math.log(float(y.mean())/(1-float(y.mean())))
    penalty=np.diag([0.]+[PROTOCOL['regularization']]*len(FEATURES));converged=False
    for iteration in range(100):
        p=1/(1+np.exp(-np.clip(design@weights,-40,40)));g=design.T@(p-y)/len(y)+penalty@weights
        h=(design.T*(p*(1-p)))@design/len(y)+penalty
        step=np.linalg.solve(h,g);weights-=step
        if float(np.max(np.abs(step)))<1e-10:converged=True;break
    if not converged:raise ValueError('Logistic fit did not converge; no substitute model')
    baseline={}
    for symbol in ('BTC/USD','SOL/USD'):
        ys=[r['label'] for r in eligible if r['symbol']==symbol];baseline[symbol]=(sum(ys)+1)/(len(ys)+2)
    patterns=[]
    for i,k in enumerate(FEATURES):
        patterns.append(dict(feature=k,winning_train_mean=float(x[y==1,i].mean()),losing_train_mean=float(x[y==0,i].mean()),
            coefficient_per_train_std=float(weights[i+1]),train_mean=float(mean[i]),train_std=float(std[i])))
    return dict(available=True,features=list(FEATURES),mean=mean.tolist(),std=std.tolist(),weights=weights.tolist(),
        train_count=len(y),train_winners=int(sum(y)),train_losers=int(len(y)-sum(y)),training_keys=[r['key'] for r in eligible],
        intercept_unpenalized=True,regularization=PROTOCOL['regularization'],cutoff=.5,iterations=iteration+1,
        training_cutoff=cutoff,last_training_label=max(ts(r['label_known_at']) for r in eligible),
        baseline=baseline,patterns=patterns,converged=converged)


def predict(model,feature):
    if not model.get('available') or feature is None:return None
    if model['features']!=list(FEATURES):raise ValueError('Feature contract mismatch')
    x=np.array([feature['values'][k] for k in FEATURES]);z=(x-np.array(model['mean']))/np.array(model['std'])
    logit=float(model['weights'][0]+z@np.array(model['weights'][1:]));return 1/(1+math.exp(-max(-40,min(40,logit))))


def metrics(rows):
    scored=[r for r in rows if r['probability'] is not None];positive=[r for r in scored if r['label']==1];negative=[r for r in scored if r['label']==0]
    def brier(key):return sum((r[key]-r['label'])**2 for r in scored)/len(scored) if scored else None
    auc=sum((a['probability']>b['probability'])+.5*(a['probability']==b['probability']) for a in positive for b in negative)/(len(positive)*len(negative)) if positive and negative else None
    kept=[r for r in scored if r['accepted']];dropped=[r for r in scored if not r['accepted']]
    return dict(rows=len(rows),scored=len(scored),abstained=len(rows)-len(scored),wins=len(positive),losses=len(negative),
        accepted=len(kept),rejected=len(dropped),winners_kept=sum(r['label']==1 for r in kept),winners_rejected=sum(r['label']==1 for r in dropped),
        losses_rejected=sum(r['label']==0 for r in dropped),losses_kept=sum(r['label']==0 for r in kept),
        brier=brier('probability'),asset_baseline_brier=brier('baseline_probability'),auc=auc,
        original_normalized_net=sum(r['normalized_net'] for r in rows),
        fixed_entry_filtered_normalized_net=sum(r['normalized_net'] for r in rows if r['accepted']),
        rejected_winner_normalized_net=sum(r['normalized_net'] for r in dropped if r['label']==1),
        rejected_loss_normalized_net=sum(r['normalized_net'] for r in dropped if r['label']==0))


class FilterMixin:
    def __init__(self,*args,quality_model,quality_symbol,quality_market,**kwargs):
        super().__init__(*args,**kwargs);self.quality_model=quality_model;self.quality_symbol=quality_symbol;self.quality_market=quality_market;self.quality_decisions=[]
    def open_signal(self,b,s):
        feature,reason=features(self.quality_symbol,s,self.quality_market);p=predict(self.quality_model,feature);accepted=p is None or p>=.5
        decision=dict(signal_id=s['id'],time_utc=s['time_utc'],route=s['route'],reference=s['entry_reference'],
            probability=p,accepted=accepted,abstained=p is None,reason=(reason or 'model unavailable; abstain') if p is None else 'fixed 0.50 entry-quality cutoff',feature=feature)
        self.quality_decisions.append(decision);s['entry_quality']=copy.deepcopy(decision)
        if not accepted:
            s['decision']='entry_quality_rejected';s['trade_id']=None;self.counter['entry_quality_rejected']+=1
            self.event('entry_quality_rejected',b['t'],signal_id=s['id'],probability=p,entry_rule=s['route'],price=s['entry_reference']);return
        super().open_signal(b,s)
        target=self.position or (self.trades[-1] if self.trades and self.trades[-1].get('signal_id')==s['id'] else None)
        if target is not None:target['entry_quality']=copy.deepcopy(decision)
    def finish(self):
        r=super().finish();r['entry_quality_protocol']=PROTOCOL;r['entry_quality_decisions']=copy.deepcopy(self.quality_decisions);return r

class FilterBaseline(FilterMixin,FailedReboundReplay):pass
class FilterEarly(FilterMixin,EarlySequentialReplay):pass
