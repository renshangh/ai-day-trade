"""Read-only Coinbase BTC structure research; never imports a broker/order client.

V1.1 quantifies the manual's unfinished parameters for an initial, unoptimized
30-day experiment. Outputs are OHLC-model estimates, never ETF or real fills.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

STEP = 900
NY = ZoneInfo('America/New_York')
SOURCE = 'https://api.exchange.coinbase.com/products/BTC-USD/candles'


@dataclass(frozen=True)
class Config:
    version: str = 'V1.1-research-2026-11-08'
    pivot_left_right_bars: int = 1
    min_higher_low_atr: float = 0.10
    stop_buffer_atr: float = 0.25
    target_buffer_atr: float = 0.10
    limit_chase_atr: float = 0.10
    setup_expiry_bars: int = 8
    resistance_lookback_bars: int = 672
    atr_period: int = 14
    min_reward_risk: float = 2.0
    one_way_friction_bps: float = 2.0
    first_sale_fraction: float = 0.5
    upper_wick_fraction: float = 0.5


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def local(stamp):
    return datetime.fromtimestamp(stamp, NY).isoformat()


def fetch(start, end, folder):
    """Persist exact responses, then filter the requested half-open interval."""
    folder.mkdir(parents=True, exist_ok=True)
    found, requests, conflicts = {}, [], []
    for a in range(start, end, 280 * STEP):
        b = min(end, a + 280 * STEP)
        url = SOURCE + '?' + urlencode(dict(granularity=STEP, start=iso(a), end=iso(b)))
        payload = None
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={'User-Agent': 'TradingDeskResearch/1.0'}), timeout=25) as response:
                    payload = response.read()
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        rows = json.loads(payload)
        if not isinstance(rows, list):
            raise ValueError('Coinbase did not return a candle array')
        name = f'{a}_{b}.json'
        (folder / name).write_bytes(payload)
        requests.append(dict(url=url, file=name, sha256=hashlib.sha256(payload).hexdigest()))
        for row in rows:
            if len(row) != 6:
                raise ValueError('Unexpected Coinbase OHLCV schema')
            t, low, high, opening, close, volume = row
            if not a <= t < b:
                continue
            if t % STEP or not all(math.isfinite(float(v)) for v in row):
                raise ValueError('Nonfinite or unaligned observation')
            if not (0 < low <= min(opening, close) <= max(opening, close) <= high and volume >= 0):
                raise ValueError('Invalid observed OHLCV')
            bar = dict(t=int(t), open=opening, high=high, low=low, close=close, volume=volume)
            if t in found and found[t] != bar:
                conflicts.append(t)
            found[t] = bar
        time.sleep(0.25)
    if conflicts:
        raise ValueError('Conflicting duplicate observations')
    missing = [t for t in range(start, end, STEP) if t not in found]
    return [found[t] for t in sorted(found)], dict(requests=requests, missing_utc=[iso(t) for t in missing])


def reward_risk(entry, stop, target, bps):
    q = bps / 10000
    risk = entry - stop + q * (entry + stop)
    reward = target - entry - q * (entry + target)
    return reward / risk if risk > 0 else None


def entry_ceiling(stop, target, bps, multiple):
    q = bps / 10000
    return (1-q) * (target + multiple * stop) / ((1+q) * (1+multiple))


def exit_intrabar(position, bar):
    """Adverse-first convention when OHLC cannot establish intrabar ordering.

    Existing stop wins if stop and target both occur. Limits require a strict
    trade-through. Favorable target gaps get no better than the target price.
    """
    if bar['low'] <= position['stop']:
        return [('stop', min(bar['open'], position['stop']), position['remaining'])]
    events = []
    if not position['trimmed'] and bar['high'] > position['t1']:
        events.append(('target1', position['t1'], 0.5))
    if position.get('t2') is not None and bar['high'] > position['t2']:
        events.append(('target2', position['t2'], 0.5 if not position['trimmed'] else position['remaining']))
    return events


def replay(bars, start, end, cfg=Config()):
    if cfg.pivot_left_right_bars != 1 or cfg.first_sale_fraction != 0.5:
        raise ValueError('This research version fixes one-bar pivots and 50% first sales')
    if cfg.one_way_friction_bps < 0 or cfg.min_reward_risk <= 0:
        raise ValueError('Invalid cost or reward/risk setting')
    lows, highs, trs, ledger, candidates, trades, fills = [], [], [], [], [], [], []
    setup = pending = position = None
    prior_t = None
    segment = []
    q = cfg.one_way_friction_bps / 10000
    realized_r = peak_r = max_dd_r = 0.0

    def close_part(b, price, fraction, reason, timing):
        nonlocal position, realized_r
        p = position
        pnl = fraction * (price - p['entry'] - q * (price + p['entry']))
        p['pnl_per_initial_btc'] += pnl
        p['remaining'] = round(p['remaining'] - fraction, 10)
        p['exit_legs'] += 1
        fills.append(dict(trade_id=p['id'], time_utc=iso(b['t']), time_ny=local(b['t']),
                          time_basis=timing, reason=reason, fraction_initial=fraction,
                          model_price=price, pnl_per_initial_btc=pnl, r_contribution=pnl/p['initial_risk']))
        if p['remaining'] == 0:
            result = dict(p)
            result.update(exit_time_utc=iso(b['t']), exit_time_ny=local(b['t']), exit_reason=reason,
                          net_r=p['pnl_per_initial_btc']/p['initial_risk'])
            trades.append(result)
            realized_r += result['net_r']
            position = None

    for i, b in enumerate(bars):
        live_window = start <= b['t'] < end
        contiguous = prior_t is None or b['t'] == prior_t + STEP
        if not contiguous:
            # Never fabricate an unobserved stop/fill across a data gap.
            if position:
                position['unresolved_gap'] = True
                break
            lows, highs, trs, segment = [], [], [], []
            setup = pending = None
        prior_t = b['t']
        if pending and live_window:
            c = pending
            pending = None
            if b['t'] != c['signal_t'] + STEP:
                c['decision'] = 'skipped: missing next bar'
            elif not (c['stop'] < b['open'] < c['t1'] and b['open'] <= c['limit']):
                c['decision'] = 'skipped: next open outside capped entry'
            else:
                risk = b['open'] - c['stop'] + q * (b['open'] + c['stop'])
                position = dict(id=len(trades)+1, entry_time_utc=iso(b['t']), entry_time_ny=local(b['t']),
                                signal_time_utc=c['confirmed_utc'], signal_time_ny=c['confirmed_ny'],
                                entry=b['open'], initial_stop=c['stop'], stop=c['stop'], t1=c['t1'],
                                t2=c['t2'], resistance=c['resistance'], initial_risk=risk, remaining=1.0,
                                trimmed=False, pnl_per_initial_btc=0.0, exit_legs=0, pending_weak_exit=False)
                c['decision'] = 'entered: next-open model'
                c['model_entry'] = b['open']
        if position and live_window:
            if position['pending_weak_exit']:
                # A gap through protection is a stop, not a favorable close fill.
                reason = 'stop_gap' if b['open'] <= position['stop'] else 'wick_failure_next_open'
                close_part(b, b['open'], position['remaining'], reason, 'next bar open')
            else:
                for reason, price, fraction in exit_intrabar(position, b):
                    close_part(b, price, fraction, reason, 'within 15m interval; exact tick unknown')
                    if position is None:
                        break
                    if reason == 'target1':
                        position['trimmed'] = True

        previous_close = segment[-1]['close'] if segment else None
        # Without an observed previous close, true range is unavailable. Do not
        # substitute the current open for a missing prior market observation.
        tr = (max(b['high']-b['low'], abs(b['high']-previous_close), abs(b['low']-previous_close))
              if previous_close is not None else None)
        segment.append(b)
        if tr is not None:
            trs.append(tr)
        # Simple ATR(14), explicitly not Wilder smoothing; only completed bars.
        atr = sum(trs[-cfg.atr_period:])/cfg.atr_period if len(trs) >= cfg.atr_period else None
        pivot_low = None
        if len(segment) >= 3:
            a, p, c = segment[-3:]
            if p['low'] < a['low'] and p['low'] < c['low']:
                pivot_low = dict(t=p['t'], price=p['low'], known_at=b['t']+STEP)
                previous_low = lows[-1] if lows else None
                lows.append(pivot_low)
                if not position and not pending and atr is not None:
                    if previous_low and p['low'] > previous_low['price'] + cfg.min_higher_low_atr*atr:
                        between = [x for x in segment if previous_low['t'] < x['t'] < p['t']]
                        if between:
                            setup = dict(l1=previous_low, l2=pivot_low,
                                         h1=max(x['high'] for x in between), trigger=b['high'],
                                         confirmation_t=b['t'], expiry=b['t']+cfg.setup_expiry_bars*STEP)
                    else:
                        setup = None
            if p['high'] > a['high'] and p['high'] > c['high']:
                highs.append(dict(t=p['t'], price=p['high'], known_at=b['t']+STEP))
        # Prune old resistance observations; do not use highs not yet confirmed.
        highs = [h for h in highs if h['t'] >= b['t']-cfg.resistance_lookback_bars*STEP]
        decision = 'no completed higher-low trigger'
        if position:
            decision = 'manage existing model position'
            if position['trimmed'] and pivot_low and atr:
                proposed = pivot_low['price'] - cfg.stop_buffer_atr*atr
                # New protection becomes effective only on the NEXT bar.
                if proposed < b['close']:
                    position['stop'] = max(position['stop'], proposed)
            span = b['high']-b['low']
            wick = b['high']-max(b['open'], b['close'])
            r = position['resistance']
            if span > 0 and b['high'] >= r and wick/span >= cfg.upper_wick_fraction and b['close'] < r:
                position['pending_weak_exit'] = True
        elif setup and not pending and atr is not None:
            if b['low'] <= setup['l2']['price'] or b['t'] > setup['expiry']:
                decision = 'setup invalidated or expired'
                setup = None
            elif b['t'] > setup['confirmation_t'] and b['close'] > setup['trigger']:
                stop = setup['l2']['price'] - cfg.stop_buffer_atr*atr
                levels = sorted(set([h['price'] for h in highs if h['price'] > b['close']] +
                                    ([setup['h1']] if setup['h1'] > b['close'] else [])))
                resistance = levels[0] if levels else None
                target = resistance-cfg.target_buffer_atr*atr if resistance else None
                ratio = reward_risk(b['close'], stop, target, cfg.one_way_friction_bps) if target else None
                c = dict(signal_t=b['t'], confirmed_utc=iso(b['t']+STEP), confirmed_ny=local(b['t']+STEP),
                         l1_time_utc=iso(setup['l1']['t']), l1=setup['l1']['price'],
                         l2_time_utc=iso(setup['l2']['t']), l2=setup['l2']['price'],
                         confirmation_bar_utc=iso(setup['confirmation_t']), trigger=setup['trigger'],
                         close_reference=b['close'], atr=atr, stop=stop, resistance=resistance,
                         t1=target, t2=levels[1]-cfg.target_buffer_atr*atr if len(levels)>1 else None,
                         reward_risk=ratio, limit=None, model_entry=None, decision='')
                if not levels:
                    c['decision'] = 'rejected: no known overhead resistance'
                elif ratio is None or ratio < cfg.min_reward_risk:
                    c['decision'] = 'rejected: net reward/risk below 2'
                elif not live_window:
                    c['decision'] = 'warmup only'
                else:
                    c['limit'] = min(b['close']+cfg.limit_chase_atr*atr,
                                     entry_ceiling(stop,target,cfg.one_way_friction_bps,cfg.min_reward_risk))
                    c['decision'] = 'pending next open'
                    pending = c
                if live_window:
                    candidates.append(c)
                decision = c['decision']
                setup = None
            else:
                decision = 'await completed close above confirmation high'
        if live_window:
            ledger.append(dict(start_utc=iso(b['t']), end_utc=iso(b['t']+STEP),
                               start_ny=local(b['t']), end_ny=local(b['t']+STEP),
                               open=b['open'], high=b['high'], low=b['low'], close=b['close'],
                               atr=atr, decision=decision, active_stop=position['stop'] if position else None))
            unrealized = 0.0
            if position:
                p=position
                unrealized=(p['pnl_per_initial_btc']+p['remaining']*(b['close']-p['entry']-q*(b['close']+p['entry'])))/p['initial_risk']
            equity_r=realized_r+unrealized
            peak_r=max(peak_r,equity_r)
            max_dd_r=max(max_dd_r,peak_r-equity_r)
            ledger[-1]['equity_r']=equity_r
    if pending:
        pending['decision'] = 'unfilled: sample ended before next open'
    return dict(config=asdict(cfg), candidates=candidates, trades=trades, fills=fills, ledger=ledger,
                open_position=position, summary=dict(closed_trades=len(trades),
                winners=sum(t['net_r']>0 for t in trades), net_closed_r=realized_r,
                marked_equity_r=ledger[-1]['equity_r'] if ledger else None,
                max_drawdown_r=max_dd_r, unresolved_data_gap=bool(position and position.get('unresolved_gap'))))


def write_csv(path, rows, keys=None):
    if not rows and not keys:
        path.write_text('')
        return
    keys=keys or list(rows[0])
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore',lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--as-of',required=True)
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    end=int(datetime.fromisoformat(args.as_of.replace('Z','+00:00')).timestamp())//STEP*STEP
    start=end-args.days*86400
    root=args.output
    root.mkdir(parents=True,exist_ok=True)
    bars,provenance=fetch(start-7*86400,end,root/'raw')
    # No parameter search: same draft at zero, 2bp and 5bp friction each way.
    results=[]
    for bps in (0.0,2.0,5.0):
        result=replay(bars,start,end,Config(one_way_friction_bps=bps))
        results.append(result)
    report=dict(source=SOURCE,retrieved_at_utc=iso(time.time()),start_utc=iso(start),end_utc=iso(end),
                warmup_start_utc=iso(start-7*86400),expected_test_bars=args.days*96,
                observed_test_bars=sum(start<=b['t']<end for b in bars),
                provenance=provenance,runs=results)
    (root/'RETEST.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    write_csv(root/'BTCUSD_15M.csv',[dict(start_utc=iso(b['t']),start_ny=local(b['t']),**b) for b in bars])
    base=results[1]
    for name in ('candidates','trades','fills','ledger'):
        write_csv(root/(name.upper()+'.csv'),base[name])
    print(json.dumps({k:report[k] for k in ('start_utc','end_utc','observed_test_bars','expected_test_bars')}))
    print(json.dumps([dict(bps=r['config']['one_way_friction_bps'],candidates=len(r['candidates']),**r['summary']) for r in results]))


if __name__=='__main__':
    main()
