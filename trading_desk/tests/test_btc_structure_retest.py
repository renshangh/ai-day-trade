"""Research invariants using archived real Coinbase observations, not fake bars."""
import csv
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import btc_structure_retest as btc


@pytest.fixture(scope='module')
def observations():
    with (ROOT/'reports/btc_structure_2026_11_08/BTCUSD_15M.csv').open() as f:
        return [dict(t=int(x['t']),**{k:float(x[k]) for k in ('open','high','low','close','volume')})
                for x in csv.DictReader(f)]


def test_exact_limit_ceiling_and_friction():
    # Arithmetic inputs from the manual's explicitly hypothetical worked example.
    e,s,t=75860,75810,75990
    assert btc.reward_risk(e,s,t,0)==2.6
    assert btc.reward_risk(e,s,t,2)<btc.reward_risk(e,s,t,0)
    cap=btc.entry_ceiling(s,t,2,2)
    assert btc.reward_risk(cap,s,t,2)==pytest.approx(2)


def test_real_candles_match_manual_and_data_are_complete(observations):
    assert len(observations)==37*96
    assert all(b['t']-a['t']==900 for a,b in zip(observations,observations[1:]))
    last=observations[-1]
    assert btc.iso(last['t'])=='2026-11-08T15:45:00Z'
    assert (last['open'],last['high'],last['low'],last['close'])==(75978.36,75980.47,75951.58,75966.27)


def test_prefix_replay_does_not_use_future_pivots(observations):
    start=observations[7*96]['t']
    cutoff=observations[2200]['t']+900
    part=btc.replay(observations[:2201],start,cutoff)
    full=btc.replay(observations,start,observations[-1]['t']+900)
    before=[x for x in full['candidates'] if x['signal_t']<cutoff]
    assert part['candidates']==before
    for c in before:
        assert datetime.fromisoformat(c['confirmation_bar_utc'].replace('Z','+00:00')).timestamp()+900<c['signal_t']+900
        assert datetime.fromisoformat(c['l2_time_utc'].replace('Z','+00:00')).timestamp()<c['signal_t']


def test_a_real_missing_interval_resets_context_without_padding(observations):
    start=observations[7*96]['t']
    removed=observations[900]['t']
    shortened=observations[:900]+observations[901:]
    result=btc.replay(shortened,start,observations[-1]['t']+900)
    assert len(result['ledger'])==30*96-1
    assert not any(x['start_utc']==btc.iso(removed) for x in result['ledger'])
    first_after=next(x for x in result['ledger'] if x['start_utc']==btc.iso(removed+900))
    assert first_after['atr'] is None
    fourteen_after=next(x for x in result['ledger'] if x['start_utc']==btc.iso(removed+14*900))
    assert fourteen_after['atr'] is None


def test_dst_keeps_distinct_utc_times_and_offsets(observations):
    fallback=[x for x in observations if btc.local(x['t']).startswith('2026-11-01T01:')]
    assert len(fallback)==8
    assert len({x['t'] for x in fallback})==8
    assert {btc.local(x['t'])[-6:] for x in fallback}=={'-04:00','-05:00'}


def test_cost_cases_do_not_claim_trade_performance(observations):
    result=btc.replay(observations,observations[7*96]['t'],observations[-1]['t']+900)
    assert len(result['candidates'])==114
    assert all(x['reward_risk']<2 for x in result['candidates'])
    assert result['trades']==[] and result['fills']==[] and result['open_position'] is None


def test_adverse_first_exit_model_on_observed_bar(observations):
    # Real observed bar; levels below are hypothetical order parameters only.
    # This tests the execution convention, not a claimed historical trade.
    bar=next(b for b in observations if btc.iso(b['t'])=='2026-11-08T13:15:00Z')
    p=dict(stop=75960,t1=76050,t2=76080,remaining=1,trimmed=False)
    assert btc.exit_intrabar(p,bar)==[('stop',75960,1)]
    p['stop']=75800
    assert btc.exit_intrabar(p,bar)==[('target1',76050,0.5),('target2',76080,0.5)]


def test_unimplemented_pivot_settings_fail_explicitly(observations):
    with pytest.raises(ValueError,match='one-bar pivots'):
        btc.replay(observations,observations[0]['t'],observations[-1]['t']+900,btc.Config(pivot_left_right_bars=2))
