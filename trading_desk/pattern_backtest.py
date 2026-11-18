"""Isolated same-window cross-asset replay of the pinned BTC pattern library."""
from __future__ import annotations
import bisect
import copy
import csv
import gzip
import hashlib
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from trading_desk.btc_data import STORE,iso,ts,read,save,normalize
from trading_desk.btc_engine import export_csv
from trading_desk.pattern_library import HOME,ROOT,library_digest
from trading_desk.pattern_discovery import PatternReplay
from trading_desk.pattern_universe import Source as ArchiveSource
from scripts.btc_structure_retest import Config

NY=ZoneInfo('America/New_York')
BACKTESTS=HOME/'backtests'
POLICY=dict(strategy='Current draft-2 BTC B1 similarity filter; 9 unflagged winners and 17 losing controls',
    stock_targets='Existing PatternReplay prominent 15m stock/ETF target policy, unchanged',
    prices='Stock/ETF: consolidated SIP raw 1m, calendar regular session; in-window split uses vendor split-adjusted 1m on a comparable-share basis; BTC exact frozen source',
    timing='Real minute OHLC model; delivery assumed at minute end with zero extra latency, not actual detection/fills',
    sizing='1 share per equity/ETF trade; 1 BTC for reference; secondary fixed $10,000 entry notional per independent trade',
    costs='Existing 2bps per side ETF spread/slippage proxy; no actual broker commissions/crypto fees',
    exits='Unchanged inherited 0.1: initial D stop, first 25% target, remainder protection/structure exits; no forced window-end sale',
    limits='Independent one-position-per-symbol books; no shared cash, compounding or portfolio-return claim',
    bias='Retrospective same-window transfer test. BTC templates/outcome labels use this period; watchlist chosen using Nov9 data after its end. Not out-of-sample.',
    comparison='Historical SIP stock coverage differs from current forward IEX; not a live fill-parity claim',
    orders_enabled=False,live_promoted=False)


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def grid(calendar,start,end):
    expected=[]
    for s in calendar:
        opening=int(datetime.fromisoformat(s['date']+'T'+s['open']).replace(tzinfo=NY).timestamp())
        closing=int(datetime.fromisoformat(s['date']+'T'+s['close']).replace(tzinfo=NY).timestamp())
        if closing<=opening:raise ValueError('Invalid exchange session')
        expected.extend(t for t in range(opening,closing,60) if start<=t<end)
    if len(expected)!=len(set(expected)):raise ValueError('Duplicate exchange sessions')
    return sorted(expected)


def split_events(raw,adjusted,start,end):
    """Detect within-window split-factor changes, never invent share adjustments."""
    byday=lambda rows:{b['t'][:10]:float(b['c']) for b in rows}
    a=byday(raw);b=byday(adjusted)
    if not a or set(a)!=set(b):raise ValueError('Daily split verification incomplete')
    events=[];common=None
    for day in sorted(a):
        if min(a[day],b[day])<=0:raise ValueError('Invalid split verification prices')
        # Provider adjusted closes are rounded to cents. A constant 1/3 factor
        # moves slightly from day to day after rounding; a relative epsilon
        # mistakes this for repeated splits. Intersect the half-cent rounding
        # bounds instead, without altering either observed price series.
        lo=max(0,b[day]-.005)/(a[day]+.005)
        hi=(b[day]+.005)/(a[day]-.005) if a[day]>.005 else float('inf')
        overlap=(max(common[0],lo),min(common[1],hi)) if common else (lo,hi)
        if overlap[0]>overlap[1]:
            boundary=int(datetime.fromisoformat(day+'T09:30:00').replace(tzinfo=NY).timestamp())
            if start<=boundary<end:events.append(dict(date=day,adjustment_ratio_change=(b[day]/a[day])/((common[0]+common[1])/2)))
            common=(lo,hi)
        else:common=overlap
    return events


def download(folder,symbols,start,end):
    source=ArchiveSource(folder);equities=[s for s in symbols if s!='BTC/USD']
    params=dict(start=iso(start)[:10],end=iso(end)[:10])
    calendar=source.get('paper-api.alpaca.markets','/v2/calendar',params)
    expected=grid(calendar,start,end);allowed=set(expected)
    if not expected:raise ValueError('No real exchange calendar in requested window')
    def chunk(names):
        output={s:[] for s in names};token=None;seen=set()
        while True:
            p=dict(symbols=','.join(names),timeframe='1Min',start=iso(start),end=iso(end),
                feed='sip',adjustment='raw',limit=10000,sort='asc')
            if token:p['page_token']=token
            page=source.get('data.alpaca.markets','/v2/stocks/bars',p)
            for s,bars in (page.get('bars') or {}).items():output.setdefault(s,[]).extend(bars)
            token=page.get('next_page_token')
            if not token:return output
            if token in seen or len(seen)>100:raise ValueError('Repeated/excessive historical pagination')
            seen.add(token)
    products={};errors={}
    with ThreadPoolExecutor(max_workers=3) as workers:
        jobs={workers.submit(chunk,equities[i:i+4]):equities[i:i+4] for i in range(0,len(equities),4)}
        for future in as_completed(jobs):
            try:products.update(future.result());print('Downloaded SIP:',','.join(jobs[future]),flush=True)
            except Exception as exc:
                for symbol in jobs[future]:errors[symbol]=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    daily={}
    for adjustment in ('raw','split'):
        p=dict(symbols=','.join(equities),timeframe='1Day',start=iso(start),end=iso(end),
            feed='sip',adjustment=adjustment,limit=10000,sort='asc')
        if equities:
            try:
                response=source.get('data.alpaca.markets','/v2/stocks/bars',p)
                if response.get('next_page_token'):raise ValueError('Unexpected daily split-verification pagination')
                daily[adjustment]=response.get('bars') or {}
            except Exception:daily[adjustment]={}
    output={};quality={}
    for symbol in equities:
        if symbol in errors:quality[symbol]=dict(status='unavailable',reason='Historical SIP batch unavailable: '+errors[symbol]);continue
        try:
            normalized=normalize(products.get(symbol,[]),start,end)
            bars=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in normalized if t in allowed]
            if not bars:raise ValueError('No observed regular-session minute data')
            events=split_events(daily.get('raw',{}).get(symbol,[]),daily.get('split',{}).get(symbol,[]),start,end)
            basis='raw';adjustment_note=None
            if events:
                # Vendor observations, not local price interpolation or invented
                # shares/fills. The result explicitly uses one comparable
                # adjusted share; it does not claim raw historical fill parity.
                adjusted=chunk_adjusted(source,symbol,start,end)
                normalized=normalize(adjusted,start,end)
                bars=[dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n) for t,o,h,l,c,v,n,vw in normalized if t in allowed]
                if not bars:raise ValueError('Vendor split-adjusted minute series unavailable')
                basis='vendor split-adjusted comparable share'
                adjustment_note='Fixed $0.01 trigger increment applied on vendor adjusted price basis; not raw historical tick/fill equivalence'
            missing=sorted(allowed-{b['t'] for b in bars})
            output[symbol]=bars;quality[symbol]=dict(status='available',observed=len(bars),expected=len(expected),
                missing_count=len(missing),missing=missing,split_events=events,price_basis=basis,adjustment_note=adjustment_note,
                split_check='Raw versus split-adjusted daily factors with half-cent rounding bounds')
        except ValueError as exc:quality[symbol]=dict(status='unavailable',reason=str(exc))
    if 'BTC/USD' in symbols:
        bars=[];sha=hashlib.sha256()
        with gzip.open(STORE/'releases/0.2/data/MINUTES.jsonl.gz','rb') as f:
            for line in f:
                sha.update(line);t,o,h,l,c,v,n,vw=json.loads(line)
                if start<=t<end:bars.append(dict(t=t,open=o,high=h,low=l,close=c,volume=v,n=n))
        expected_btc=set(range(start,end,60));missing=sorted(expected_btc-{b['t'] for b in bars})
        output['BTC/USD']=bars;quality['BTC/USD']=dict(status='available',observed=len(bars),expected=len(expected_btc),
            missing_count=len(missing),missing=missing,source_sha256=sha.hexdigest())
    save(folder/'CALENDAR.json',calendar);save(folder/'QUALITY.json',quality)
    for symbol,bars in output.items():
        with gzip.open(folder/(symbol.replace('/','_')+'_MINUTES.jsonl.gz'),'wt') as f:
            for b in bars:f.write(json.dumps(b,sort_keys=True)+'\n')
    save(folder/'SOURCES.json',dict(start=iso(start),end=iso(end),retrieved_at=iso(time.time()),
        host='data.alpaca.markets',stock_feed='sip',adjustment='raw',calendar_host='paper-api.alpaca.markets',
        raw_pages={p.name:digest(p) for p in (folder/'raw').glob('*.gz')},quality_file='QUALITY.json'))
    return output,quality


def chunk_adjusted(source,symbol,start,end):
    out=[];token=None;seen=set()
    while True:
        params=dict(symbols=symbol,timeframe='1Min',start=iso(start),end=iso(end),feed='sip',adjustment='split',limit=10000,sort='asc')
        if token:params['page_token']=token
        p=source.get('data.alpaca.markets','/v2/stocks/bars',params);out.extend((p.get('bars') or {}).get(symbol,[]))
        token=p.get('next_page_token')
        if not token:return out
        if token in seen or len(seen)>100:raise ValueError('Repeated adjusted-minute pagination')
        seen.add(token)


def enrich(result,symbol,missing,last_price,last_time):
    for p in result['trades']:
        a=ts(p['entry_time']);z=ts(p.get('exit_time') or last_time)
        p['symbol']=symbol;p['actual_missing_minutes_while_held']=bisect.bisect_right(missing,z)-bisect.bisect_left(missing,a)
        p['units']='BTC' if symbol=='BTC/USD' else 'share'
        p['realized_leg_net']=sum(l['net'] for l in p['legs'])
        p['normalized_10000_realized_net']=p['realized_leg_net']/p['entry']*10000
        p['unrealized_net_reference']=p['remaining']*(last_price-p['entry'])-p['remaining']*(last_price+p['entry'])*.0002 if p['remaining'] else 0
        p['normalized_10000_unrealized_net']=p['unrealized_net_reference']/p['entry']*10000
        p['mark_time']=last_time;p['mark_price']=last_price
        for leg in p['legs']:leg['normalized_10000_net']=leg['net']/p['entry']*10000
    return result


def summary(result):
    trades=result['trades'];closed=[p for p in trades if p['status']=='closed']
    return dict(trades=len(trades),closed=len(closed),open=sum(p['remaining']>0 for p in trades),
        wins=sum(p['net']>0 for p in closed),losses=sum(p['net']<=0 for p in closed),
        realized_net=sum(p['realized_leg_net'] for p in trades),closed_net=sum(p['net'] for p in closed),
        unrealized_net=sum(p['unrealized_net_reference'] for p in trades),
        normalized_10000_realized=sum(p['normalized_10000_realized_net'] for p in trades),
        normalized_10000_unrealized=sum(p['normalized_10000_unrealized_net'] for p in trades),
        normalized_10000_no_missing=sum(p['normalized_10000_realized_net'] for p in trades if not p['actual_missing_minutes_while_held']),
        actual_missing_exposed=sum(p['actual_missing_minutes_while_held']>0 for p in trades),
        inherited_gap_flags=sum(p['gap_exposed'] or p['context_partial'] for p in trades),
        pattern_checks=len(result['pattern_decisions']),pattern_accepted=sum(d['accepted'] for d in result['pattern_decisions']),
        rejected_reasons={reason:sum(d['reason']==reason for d in result['pattern_decisions']) for reason in sorted({d['reason'] for d in result['pattern_decisions'] if d['reason']})},
        source_signal_counts=result['signal_counts'],max_closed_trade_drawdown_r=result['metrics']['max_drawdown_r'])


def table(path,rows,empty_fields=('status',)):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        fields=list(rows[0]) if rows else list(empty_fields);w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def execute(symbol,bars,quality,start,end,library,folder):
    folder.mkdir(parents=True,exist_ok=False);db=sqlite3.connect(folder/'ledger.sqlite')
    db.execute('CREATE TABLE ledger(t INTEGER PRIMARY KEY,day TEXT,body TEXT)')
    engine=PatternReplay(start,end,db,Config(version='pattern-draft-2-same-window',first_sale_fraction=.25,resistance_mode='major1h'),symbol=symbol,library=library)
    try:
        for b in bars:
            engine.received_at=b['t']+60 # Declared simulation clock, never an actual receipt claim.
            engine.minute(b)
        r=engine.finish();db.commit()
        r.update(symbol=symbol,start=iso(start),end=iso(end),policy=copy.deepcopy(POLICY),pattern_decisions=engine.decisions,
            orders_enabled=False,source_quality=quality,library_sha256=library_digest(library),status='complete')
        for d in r['pattern_decisions']:d['clock_basis']='assumed completed-minute availability, not actual detection'
        enrich(r,symbol,quality['missing'],engine.last_price,iso(engine.last_t))
        r['summary']=summary(r);export_csv(folder,r,db)
        table(folder/'PATTERN_DECISIONS.csv',[dict(time_utc=d['time_utc'],route=d['route'],reference=d['reference'],
            stop=d['initial_stop'],target=d['target'],accepted=d['accepted'],trade_id=d['trade_id'],reason=d['reason'],
            nearest_winner=d['match']['nearest_positive']['example_id'] if d['match'] else None,
            nearest_loser=d['match']['nearest_negative']['example_id'] if d['match'] else None,
            margin=d['match']['margin'] if d['match'] else None,clock_basis=d['clock_basis']) for d in engine.decisions])
        save(folder/'result.json',r);return r
    finally:db.close()


def preserve():
    from scripts.audit_btc_c_blind_review import locked,preservation
    locked();live=preservation();old=read(HOME/'PRESERVED_BEFORE.json')
    assert all(digest(Path(p))==h for p,h in old['files'].items())
    files=dict(old['files'])
    for name in ('CONFIG.json','LIBRARY.json','UNIVERSE_SCREEN.json'):
        p=HOME/name;files[str(p.relative_to(ROOT))]=digest(p)
    return files,live


def run():
    files,live=preserve();library=read(HOME/'LIBRARY.json');config=read(HOME/'CONFIG.json')
    original=read(ROOT/library['source_result']);assert digest(ROOT/library['source_result'])==library['source_sha256']
    start=ts(library['training_start']);end=ts(library['training_end']);warmup=ts(original['warmup_start'])
    ident=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-patterns-30d';folder=BACKTESTS/ident;folder.mkdir(parents=True,exist_ok=False)
    symbols=config['watchlist'];code={str(p.relative_to(ROOT)):digest(p) for p in
        (Path(__file__),ROOT/'scripts/retest_pattern_watchlist.py',ROOT/'trading_desk/pattern_library.py',ROOT/'trading_desk/pattern_discovery.py')}
    study=dict(study_id=ident,status='downloading',start=iso(start),end=iso(end),warmup_start=iso(warmup),symbols=symbols,
        policy=POLICY,library_sha256=library_digest(library),code_sha256=code,results={},source_quality={},original_live=live,
        watchlist_selection_asof=read(HOME/'UNIVERSE_SCREEN.json')['asof'],orders_enabled=False,live_promoted=False)
    save(folder/'STUDY.json',study);save(folder/'PRESERVED_BEFORE.json',files);save(folder/'LIBRARY.json',library)
    bars,quality=download(folder/'data',symbols,warmup,end)
    assert quality.get('BTC/USD',{}).get('source_sha256',library['source_minute_sha256'])==library['source_minute_sha256']
    study.update(status='replaying',source_quality=quality);save(folder/'STUDY.json',study)
    results={}
    for symbol in symbols:
        if symbol not in bars:
            study['results'][symbol]=dict(status='unavailable',reason=quality[symbol]['reason']);save(folder/'STUDY.json',study);continue
        result=execute(symbol,bars[symbol],quality[symbol],start,end,library,folder/symbol.replace('/','_'))
        results[symbol]=result;study['results'][symbol]=dict(status='complete',summary=result['summary'])
        save(folder/'STUDY.json',study)
        print(json.dumps(dict(symbol=symbol,summary=result['summary'])),flush=True)
    combined=[];legs=[];summaries=[]
    for symbol,r in results.items():
        summaries.append(dict(symbol=symbol,**{k:json.dumps(v) if isinstance(v,dict) else v for k,v in r['summary'].items()}))
        for p in r['trades']:
            combined.append(dict(symbol=symbol,trade_id=p['id'],entry_time=p['entry_time'],entry=p['entry'],
                initial_stop_effective=p['entry_time'],initial_stop=p['initial_stop'],last_stop=p['stop'],target_25=p['t1'],
                exit_time=p.get('exit_time'),status=p['status'],remaining=p['remaining'],net=p.get('net'),
                realized_leg_net=p['realized_leg_net'],unrealized_net_reference=p['unrealized_net_reference'],
                normalized_10000_realized=p['normalized_10000_realized_net'],normalized_10000_unrealized=p['normalized_10000_unrealized_net'],
                actual_missing_minutes_while_held=p['actual_missing_minutes_while_held'],inherited_gap_flag=p['gap_exposed'],
                entry_rule=p['entry_rule'],nearest_example=p.get('pattern_match',{}).get('nearest_positive',{}).get('example_id')))
            legs.extend(dict(symbol=symbol,trade_id=p['id'],**l) for l in p['legs'])
    table(folder/'SUMMARY.csv',summaries);table(folder/'TRADES.csv',combined);table(folder/'EXITS.csv',legs)
    assert all(digest(ROOT/p)==h for p,h in files.items());assert all(digest(ROOT/p)==h for p,h in code.items())
    _,after=preserve();assert after['pid']==live['pid'] and after['session']==live['session']
    study.update(status='complete',preserved_files_verified=len(files));save(folder/'STUDY.json',study)
    save(BACKTESTS/'ACTIVE.json',dict(study_id=ident))
    print('Completed independent study',ident,flush=True);return study
