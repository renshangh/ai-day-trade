"""Exchange-calendar metadata and accounting on actual IBIT regular-session bars."""
from __future__ import annotations
import bisect,copy,csv,gzip,json
from datetime import datetime
from zoneinfo import ZoneInfo
from trading_desk.btc_data import ts,iso
from trading_desk.unfiltered_90d import funded_account
from trading_desk.pattern_backtest import grid

NY=ZoneInfo('America/New_York')


class Calendar:
    def __init__(self,sessions,start,end):
        self.minutes=grid(sessions,start,end);self.allowed=set(self.minutes)
        self.periods=sorted({t//900*900 for t in self.minutes});self.period_index={t:i for i,t in enumerate(self.periods)}
        self.sessions=copy.deepcopy(sessions)
    def missing_between(self,a,b):
        return self.minutes[bisect.bisect_right(self.minutes,a):bisect.bisect_left(self.minutes,b)]
    def adjacent_bars(self,a,b):
        return a in self.period_index and b in self.period_index and self.period_index[b]==self.period_index[a]+1
    def partial_context(self,bars,count=14):
        window=list(bars)[-count:]
        return len(window)!=count or any(b['observed_minutes']!=15 for b in window) or any(not self.adjacent_bars(a['t'],b['t']) for a,b in zip(window,window[1:]))


def cash_account(trades,bars,start,end,calendar,folder=None):
    result=funded_account(trades,bars,start,end,folder)
    actual={b['t'] for b in bars if start<=b['t']<end};expected={t for t in calendar.minutes if start<=t<end}
    assert actual<=expected
    result['elapsed_calendar_minutes']=result['expected_test_minutes']
    result['longest_elapsed_gap_minutes']=result.pop('max_observation_gap_minutes')
    result['expected_test_minutes']=len(expected);result['missing_test_minutes']=len(expected-actual)
    ordered=sorted(actual)
    result['max_missing_regular_minutes_between_observations']=max((len(calendar.missing_between(a,b)) for a,b in zip(ordered,ordered[1:])),default=0)
    result['coverage_note']='Only exchange-calendar regular minutes are expected. Nights, weekends and holidays are closed intervals, not fabricated bars or missing observations.'
    if folder:
        # Correct only continuity metadata, never prices, timestamps or equity.
        path=folder/'EQUITY.jsonl.gz'
        with gzip.open(path,'rt') as z:points=[json.loads(line) for line in z]
        previous=None;days={}
        for p in points:
            t=ts(p['minute_start']);actual_missing=len(calendar.missing_between(previous,t)) if previous is not None else 0
            p['closed_minutes_before']=p['missing_minutes_before']-actual_missing;p['missing_minutes_before']=actual_missing
            days[p['minute_start'][:10]]=p;previous=t
        with gzip.open(path,'wt') as z:
            for p in points:z.write(json.dumps(p)+'\n')
        with (folder/'EQUITY.csv').open('w',newline='') as z:
            w=csv.DictWriter(z,fieldnames=list(points[0]));w.writeheader();w.writerows(points)
        from trading_desk.btc_data import save
        save(folder/'DAILY_EQUITY.json',[dict(date_utc=k,**v) for k,v in days.items()])
    return result
