"""Measured liquidity/beta/ATR universe; no market data is filled or invented."""
from __future__ import annotations
import gzip
import hashlib
import json
import math
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from trading_desk.btc_data import credentials,iso,read,save
from trading_desk.pattern_library import HOME,ROOT
from trading_desk.universe import all_groups

NY=ZoneInfo('America/New_York')
REPORTS=ROOT/'reports/pattern_discovery'
ETFS={'SPY','QQQ','DIA','IWM','SMH','SOXX','ARKK','XBI','TQQQ','SOXL','SPXL','UPRO','SQQQ','SOXS'}
LEVERAGED={'TQQQ':3,'SOXL':3,'SPXL':3,'UPRO':3,'SQQQ':-3,'SOXS':-3}
EXTRA=set('MSTR COIN HOOD PLTR SOFI RBLX RKLB ASTS MARA RIOT IREN CLSK HIMS RDDT APP SMCI ARM MU AMD NVDA TSLA AXTI LITE COHR FN CRCL RGTI IONQ QBTS QUBT OKLO SMR NBIS CRWV WULF CIFR TERA'.split())
POLICY=dict(min_avg_dollar_volume=500_000_000,min_avg_shares=5_000_000,liquidity_windows=[5,20],
    beta_sessions=63,min_positive_beta=1.25,atr_period=14,min_atr_pct=3.0,
    ranking='Among all gates passed: ATR% descending, then average dollar volume; not expected return',
    selection='BTC/USD plus up to 8 qualified stocks and 4 qualified positive-beta ETFs; inverse ETFs review-only',
    cost_spread_gate='Historical screen only; fresh bid/ask/depth are not verified by this screen')


def pool():
    return sorted({s for g in all_groups().values() for s in g['constituents']}|EXTRA|ETFS)


class Source:
    def __init__(self,folder):self.folder=folder
    def get(self,host,path,params):
        if host not in ('data.alpaca.markets','paper-api.alpaca.markets'):raise ValueError('Unapproved source host')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        req=urllib.request.Request('https://'+host+path+'?'+urllib.parse.urlencode(params),headers=credentials(),method='GET')
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as response:payload=response.read()
        except urllib.error.HTTPError as exc:raise ValueError(f'Alpaca read-only data HTTP {exc.code}') from None
        digest=hashlib.sha256(payload).hexdigest();raw=self.folder/'raw';raw.mkdir(parents=True,exist_ok=True)
        dest=raw/(digest+'.json.gz')
        if not dest.exists():dest.write_bytes(gzip.compress(payload))
        return json.loads(payload)

    def fetch(self,symbols,asof):
        start=datetime.fromtimestamp(asof,timezone.utc)-timedelta(days=180)
        end=datetime.fromtimestamp(asof-16*60,timezone.utc)
        calendar=self.get('paper-api.alpaca.markets','/v2/calendar',dict(start=start.date().isoformat(),end=end.date().isoformat()))
        sessions=[]
        for s in calendar:
            close=datetime.fromisoformat(s['date']+'T'+s['close']).replace(tzinfo=NY)
            if close.timestamp()<=asof-16*60:sessions.append(s['date'])
        if len(sessions)<64 or len(sessions)!=len(set(sessions)):
            raise ValueError('Need at least 64 unique completed exchange-calendar sessions')
        def fetch_chunk(chunk):
            out={};token=None;seen=set()
            while True:
                params=dict(symbols=','.join(chunk),timeframe='1Day',start=start.isoformat(),end=end.isoformat(),
                    feed='sip',adjustment='all',limit=10000,sort='asc')
                if token:params['page_token']=token
                p=self.get('data.alpaca.markets','/v2/stocks/bars',params)
                for symbol,rows in (p.get('bars') or {}).items():out.setdefault(symbol,[]).extend(rows)
                token=p.get('next_page_token')
                if not token:return out
                if token in seen:raise ValueError('Repeated daily history pagination')
                seen.add(token)
        products={};errors=[]
        with ThreadPoolExecutor(max_workers=3) as workers:
            tasks={workers.submit(fetch_chunk,symbols[i:i+60]):symbols[i:i+60] for i in range(0,len(symbols),60)}
            for future in as_completed(tasks):
                try:products.update(future.result())
                except Exception as exc:errors.append(dict(symbols=tasks[future],error=str(exc) if isinstance(exc,ValueError) else type(exc).__name__))
        result=dict(retrieved_at=iso(asof),source='Alpaca consolidated SIP, completed daily bars, split/dividend adjusted',
            sessions=sorted(sessions),products=products,batch_errors=errors)
        save(self.folder/'SOURCE.json',result);return result


def daily(rows,sessions):
    if len(sessions)<64 or len(sessions[-64:])!=len(set(sessions[-64:])):
        raise ValueError('Missing/duplicate reference-calendar sessions')
    wanted=set(sessions[-64:]);found={}
    for b in rows:
        day=datetime.fromisoformat(b['t'].replace('Z','+00:00')).astimezone(NY).date().isoformat()
        if day not in wanted:continue
        if day in found:raise ValueError('Duplicate daily observation')
        o,h,l,c,v=[float(b[k]) for k in ('o','h','l','c','v')]
        if not all(math.isfinite(x) for x in (o,h,l,c,v)) or not 0<l<=min(o,c)<=max(o,c)<=h or v<0:
            raise ValueError('Invalid real daily OHLCV')
        found[day]=dict(day=day,o=o,h=h,l=l,c=c,v=v)
    if set(found)!=wanted:raise ValueError('Missing completed sessions or insufficient listing history; no fill')
    return [found[d] for d in sessions[-64:]]


def measure(symbol,bars,benchmark):
    x=[b['c']/a['c']-1 for a,b in zip(benchmark,benchmark[1:])]
    y=[b['c']/a['c']-1 for a,b in zip(bars,bars[1:])]
    mx=statistics.mean(x);my=statistics.mean(y);variance=sum((v-mx)**2 for v in x)
    if variance<=0:raise ValueError('Benchmark variance unavailable')
    beta=sum((a-mx)*(b-my) for a,b in zip(x,y))/variance
    tr=[max(b['h']-b['l'],abs(b['h']-a['c']),abs(b['l']-a['c'])) for a,b in zip(bars,bars[1:])]
    atr=statistics.mean(tr[:14])
    for value in tr[14:]:atr=(atr*13+value)/14
    last=bars[-1]['c'];atr_pct=atr/last*100
    adv={n:statistics.mean(b['c']*b['v'] for b in bars[-n:]) for n in (5,20)}
    shares={n:statistics.mean(b['v'] for b in bars[-n:]) for n in (5,20)}
    liquid=min(adv.values())>=POLICY['min_avg_dollar_volume'] and min(shares.values())>=POLICY['min_avg_shares']
    positive_beta=beta>=POLICY['min_positive_beta'];active_atr=atr_pct>=POLICY['min_atr_pct']
    reasons=[]
    if not liquid:reasons.append('5/20-session dollar/share volume below minimum')
    if not positive_beta:reasons.append('Positive beta below 1.25; inverse beta is review-only' if beta<0 else 'Beta below 1.25')
    if not active_atr:reasons.append('ATR14 below 3% of price')
    return dict(symbol=symbol,kind='ETF' if symbol in ETFS else 'stock',session=bars[-1]['day'],close=last,
        atr14=atr,atr_pct=atr_pct,beta63=beta,avg_dollar_volume_5=adv[5],avg_dollar_volume_20=adv[20],
        avg_shares_5=shares[5],avg_shares_20=shares[20],liquid=liquid,high_beta=positive_beta,high_atr=active_atr,
        qualifies=liquid and positive_beta and active_atr,reasons=reasons,leverage_daily=LEVERAGED.get(symbol),
        direction='inverse' if beta<0 else 'positive',selected=False,
        notice='Daily leveraged ETF; leverage compounds/reset daily; correlated exposures' if symbol in LEVERAGED else None)


def screen(source,symbols):
    sessions=source['sessions'];benchmark=daily(source['products'].get('SPY',[]),sessions)
    rows=[];omitted=[]
    for symbol in symbols:
        try:rows.append(measure(symbol,daily(source['products'].get(symbol,[]),sessions),benchmark))
        except ValueError as exc:omitted.append(dict(symbol=symbol,reason=str(exc)))
    rows.sort(key=lambda r:(not r['qualifies'],-r['atr_pct'],-r['avg_dollar_volume_20'],r['symbol']))
    selected=[]
    for kind,limit in [('stock',8),('ETF',4)]:
        candidates=[r for r in rows if r['qualifies'] and r['kind']==kind][:limit]
        for r in candidates:r['selected']=True;selected.append(r['symbol'])
    return dict(status='complete',asof=source['retrieved_at'],session=sessions[-1],source=source['source'],
        policy=POLICY,rows=rows,omitted=omitted,universe_size=len(symbols),qualified=sum(r['qualifies'] for r in rows),
        suggested_watchlist=['BTC/USD']+selected,
        benchmarks=[r for r in rows if r['symbol'] in ('SPY','QQQ')],
        disclaimer='Historical daily mobility/liquidity screen; no executable spread/depth check, no predictive pattern validation or orders')


def run(apply=False):
    stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());folder=REPORTS/stamp;folder.mkdir(parents=True,exist_ok=False)
    source=Source(folder).fetch(pool(),time.time());r=screen(source,pool());r['source_file']=str((folder/'SOURCE.json').relative_to(ROOT))
    if apply:
        from trading_desk.pattern_discovery import configure,snapshot
        current=snapshot();held=[x['symbol'] for x in current.get('symbols',[]) if x.get('open_position')]
        chosen=list(dict.fromkeys(r['suggested_watchlist']+held));r['retained_held_symbols']=held
        for _ in range(30):
            try:
                r['applied']=configure(chosen,True);break
            except ValueError as exc:
                if 'in progress' not in str(exc):raise
                time.sleep(1)
        else:raise ValueError('Worker remained busy; saved screen needs application later')
    save(folder/'SCREEN.json',r);save(HOME/'UNIVERSE_SCREEN.json',r);return r
