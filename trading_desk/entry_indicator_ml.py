"""Isolated genuine-VWAP/MA feature ablation; no live imports or orders."""
from __future__ import annotations
import copy,math
import numpy as np
from trading_desk.btc_data import ts
from trading_desk.entry_quality import FEATURES as BASE,PROTOCOL as BASE_PROTOCOL,features as base_features
from trading_desk.btc_failed_rebound import FailedReboundReplay
from trading_desk.btc_early_sequential import EarlySequentialReplay

MA=('price_minus_sma20_atr','sma20_minus_sma50_atr','sma20_slope3_atr')
VW=('price_minus_utc_vwap_atr','utc_vwap_slope3_atr')
ARMS=('original_ml','matched_ma','plus_ma','matched_all','plus_ma_vwap')
PROTOCOL=dict(version='entry-indicator-ml-1',
    indicators='15m completed closes: SMA20, SMA50, SMA20 change over 3 candles; UTC-day native-volume VWAP and change over 3 candles. All distances/slopes divided by original pre-entry ATR.',
    vwap='sum(actual positive minute volume * archived native minute VWAP) / sum(actual positive minute volume), from 00:00 UTC through prior complete candle. No OHLC typical-price approximation.',
    coverage='50 consecutive complete 15m bars for MAs; all actual minutes from UTC midnight for VWAP. Missing minutes/native positive-volume VWAP, zero total volume or insufficient same-session slope means unavailable; never interpolate/carry/fill.',
    zero_volume='Actual quote-derived zero-volume bars count for time coverage but contribute zero weight, never fabricated trade volume.',
    arms=list(ARMS),ablation='original 11 features; matched MA base11 vs base11+3MA; matched combined base11 vs base11+3MA+2VWAP. Each pair has identical training and inference availability masks.',
    unchanged='Same ridge penalty 1.0, cutoff .50, first14-day unique E1 training, next7-day diagnostic validation, final9-day test; no period/penalty/cutoff search or refit. Original stops/targets/exits/risk and frozen/live processes unchanged.',
    abstention='Unavailable indicators/model pass original signal through; report scored/abstained counts and matched-control deltas to avoid attributing pass-through gains to ML.',
    limits='Only a few dozen labeled entries and previously studied dates; retrospective ablation, not genuinely unseen validation. No automatic promotion or orders.')

def names(arm):
    if arm not in ARMS:raise ValueError('Choose a declared feature arm')
    return tuple(BASE)+(MA if arm=='plus_ma' else MA+VW if arm=='plus_ma_vwap' else ())

class Indicators:
    def __init__(self,market,minutes,native_vwap):
        self.market=market;self.minutes={b['t']:b for b in minutes};self.native=native_vwap;self.cache={}
    def before(self,period):
        if period in self.cache:return copy.deepcopy(self.cache[period])
        bars=[self.market.bars.get(t) for t in range(period-50*900,period,900)];ma=None;vw=None;reasons={}
        if all(bars):
            closes=[b['close'] for b in bars]
            ma=dict(sma20=sum(closes[-20:])/20,sma50=sum(closes)/50,sma20_three_bars_ago=sum(closes[-23:-3])/20,
                first_source_bar=period-50*900,last_source_bar=period-900,known_at=period)
        else:reasons['ma']='Missing complete consecutive SMA50 context'
        start=period//86400*86400;earlier=period-3*900
        if earlier<=start:reasons['vwap']='Insufficient same-UTC-day three-candle slope history'
        else:
            numerator=volume=0.;old=None;failure=None;positive=zero=0
            for t in range(start,period,60):
                if t==earlier:old=numerator/volume if volume>0 else None
                b=self.minutes.get(t)
                if b is None:failure='Missing actual minute inside UTC VWAP session';break
                if b['volume']<0:raise ValueError('Invalid actual volume')
                if b['volume']==0:zero+=1;continue
                price=self.native.get(t)
                if price is None or not math.isfinite(price) or price<=0:failure='Missing archived native VWAP for positive-volume minute';break
                numerator+=b['volume']*price;volume+=b['volume'];positive+=1
            if not failure and volume>0 and old is not None:
                vw=dict(vwap=numerator/volume,three_bars_ago=old,total_volume=volume,positive_volume_minutes=positive,zero_volume_minutes=zero,
                    session_start=start,last_source_minute=period-60,known_at=period,native_minute_vwap=True)
            else:reasons['vwap']=failure or 'No actual positive volume for both UTC VWAP points'
        result=dict(ma=ma,vwap=vw,reasons=reasons);self.cache[period]=result;return copy.deepcopy(result)
    def feature(self,symbol,signal,arm):
        feature,reason=base_features(symbol,signal,self.market)
        if feature is None:return None,reason
        if arm=='original_ml':return feature,None
        if arm not in ARMS:raise ValueError('Choose a declared arm')
        period=ts(signal['time_utc'])//900*900;context=self.before(period);ma=context['ma'];vw=context['vwap']
        need_vw=arm in ('matched_all','plus_ma_vwap')
        if ma is None or need_vw and vw is None:return None,'; '.join(context['reasons'].values()) or 'Unavailable indicator context'
        atr=signal['atr'];close=self.market.bars[period-900]['close'];values=feature['values']
        if arm in ('plus_ma','plus_ma_vwap'):
            values.update(price_minus_sma20_atr=(close-ma['sma20'])/atr,sma20_minus_sma50_atr=(ma['sma20']-ma['sma50'])/atr,
                sma20_slope3_atr=(ma['sma20']-ma['sma20_three_bars_ago'])/atr)
        if arm=='plus_ma_vwap':values.update(price_minus_utc_vwap_atr=(close-vw['vwap'])/atr,utc_vwap_slope3_atr=(vw['vwap']-vw['three_bars_ago'])/atr)
        feature['indicator_context']=context;feature['feature_arm']=arm
        assert tuple(values)==names(arm)
        return feature,None

def fit(rows,cutoff,feature_names):
    feature_names=tuple(feature_names)
    eligible=[r for r in rows if r.get('training_eligible') and r.get('label') in (0,1) and r.get('label_known_at')
              and ts(r['entry_time'])<cutoff and ts(r['label_known_at'])<cutoff];y=np.array([r['label'] for r in eligible],dtype=float)
    if len(y)<12 or min(int(sum(y)),int(len(y)-sum(y)))<4:
        return dict(available=False,reason='Insufficient training rows/classes; abstain',train_count=len(y),features=list(feature_names))
    x=np.array([[r['feature']['values'][k] for k in feature_names] for r in eligible]);mean=x.mean(0);std=x.std(0);std=np.where(std<1e-12,1.,std)
    z=(x-mean)/std;design=np.column_stack([np.ones(len(y)),z]);weights=np.zeros(design.shape[1]);weights[0]=math.log(float(y.mean())/(1-float(y.mean())))
    penalty=np.diag([0.]+[BASE_PROTOCOL['regularization']]*len(feature_names));converged=False
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
    for i,k in enumerate(feature_names):
        patterns.append(dict(feature=k,winning_train_mean=float(x[y==1,i].mean()),losing_train_mean=float(x[y==0,i].mean()),
            coefficient_per_train_std=float(weights[i+1]),train_mean=float(mean[i]),train_std=float(std[i])))
    return dict(available=True,features=list(feature_names),mean=mean.tolist(),std=std.tolist(),weights=weights.tolist(),
        train_count=len(y),train_winners=int(sum(y)),train_losers=int(len(y)-sum(y)),training_keys=[r['key'] for r in eligible],
        intercept_unpenalized=True,regularization=BASE_PROTOCOL['regularization'],cutoff=.5,iterations=iteration+1,
        training_cutoff=cutoff,last_training_label=max(ts(r['label_known_at']) for r in eligible),
        baseline=baseline,patterns=patterns,converged=converged)


def predict(model,feature):
    if not model.get('available') or feature is None:return None
    feature_names=tuple(model['features'])
    if set(feature['values'])!=set(feature_names):raise ValueError('Feature contract mismatch')
    x=np.array([feature['values'][k] for k in feature_names]);z=(x-np.array(model['mean']))/np.array(model['std'])
    logit=float(model['weights'][0]+z@np.array(model['weights'][1:]));return 1/(1+math.exp(-max(-40,min(40,logit))))

class IndicatorMixin:
    def __init__(self,*args,indicator_model,indicator_symbol,indicators,feature_arm,**kwargs):
        super().__init__(*args,**kwargs);self.indicator_model=indicator_model;self.indicator_symbol=indicator_symbol;self.indicators=indicators;self.feature_arm=feature_arm;self.indicator_decisions=[]
    def open_signal(self,b,s):
        feature,reason=self.indicators.feature(self.indicator_symbol,s,self.feature_arm);p=predict(self.indicator_model,feature);accepted=p is None or p>=.5
        decision=dict(signal_id=s['id'],time_utc=s['time_utc'],route=s['route'],reference=s['entry_reference'],arm=self.feature_arm,
            probability=p,accepted=accepted,abstained=p is None,reason=(reason or 'model unavailable; abstain') if p is None else 'fixed 0.50 quality cutoff',feature=feature)
        self.indicator_decisions.append(decision);s['entry_quality']=copy.deepcopy(decision)
        if not accepted:
            s['decision']='entry_quality_rejected';s['trade_id']=None;self.counter['entry_quality_rejected']+=1
            self.event('entry_quality_rejected',b['t'],signal_id=s['id'],probability=p,entry_rule=s['route'],price=s['entry_reference']);return
        super().open_signal(b,s)
        target=self.position or (self.trades[-1] if self.trades and self.trades[-1].get('signal_id')==s['id'] else None)
        if target is not None:target['entry_quality']=copy.deepcopy(decision)
    def finish(self):
        r=super().finish();r['entry_indicator_protocol']=PROTOCOL;r['indicator_decisions']=copy.deepcopy(self.indicator_decisions);return r
class IndicatorBaseline(IndicatorMixin,FailedReboundReplay):pass
class IndicatorEarly(IndicatorMixin,EarlySequentialReplay):pass
