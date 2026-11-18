"""Read complete exit histories for the last three entries, never bounded UI events."""
from contextlib import closing
import json
import re
import sqlite3
from trading_desk import btc_live,sol_live


def recent(state):
    rows=[];unavailable=[]
    for key,asset,model,root in (('btc','BTC/USD','0.1',btc_live.LIVE),('sol','SOL/USD','E1',sol_live.HOME)):
        ident=state[key].get('session',{}).get('id')
        if not ident:continue
        if not isinstance(ident,str) or not re.fullmatch(r'[0-9TZ-]+',ident):
            unavailable.append(asset);continue
        path=root/'sessions'/ident/'observations.sqlite'
        if not path.exists():unavailable.append(asset);continue
        try:
            with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)) as db:
                # One read transaction keeps entries and their legs on the same
                # snapshot while an independent worker appends new observations.
                db.execute('BEGIN')
                signals=[json.loads(b) for b, in db.execute("SELECT body FROM signals WHERE model=? AND json_extract(body,'$.decision')='entry' ORDER BY ref DESC LIMIT 3",(model,))]
                found=[]
                for s in signals:
                    legs=[json.loads(b) for b, in db.execute("SELECT body FROM events WHERE model=? AND json_extract(body,'$.trade_id')=? AND json_extract(body,'$.fraction')>0 ORDER BY ref,detected",(model,s['trade_id']))]
                    if sum(l['fraction'] for l in legs)>1.000001:raise ValueError('Invalid exit fractions')
                    net=sum(l['fraction']*((l['price']-s['entry_reference'])-(l['price']+s['entry_reference'])*.0002) for l in legs)
                    found.append(dict(asset=asset,model=model,entry_signal=s,legs=legs,realized_net=net))
                rows.extend(found)
        except (sqlite3.Error,ValueError,KeyError,TypeError):unavailable.append(asset)
    return dict(trades=sorted(rows,key=lambda p:p['entry_signal']['time_utc'],reverse=True),unavailable=unavailable,
        source='Complete persisted event history for the latest three entries per asset/model',orders_enabled=False)
