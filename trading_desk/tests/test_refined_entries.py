"""Lock draft stage behavior on actual saved live evidence before monthly replay."""
import copy
from pathlib import Path
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.btc_data import read,ts
from trading_desk.refined_entries import RefinedDetector,RefinedEarly,PROTOCOL
from trading_desk.btc_shock_branches import expanded_shock_setup,independent_b1_setup
from trading_desk.btc_engine import aggregate

REPORT=ROOT/'reports/live_entry_review_20261110T111101Z'


def case(asset,index,route):
    report=read(REPORT/'REVIEW.json');book=next(r for r in report['results'] if r['asset']==asset)
    p=book['trades'][index-1]
    return p,copy.deepcopy(next(c['setup'] for c in p['review']['candidates'] if c['route']==route)),book


def staged(setup,now):
    d=RefinedDetector();d.shock_chain=copy.deepcopy(setup);d.p1_now=now
    d.shock_chain['refined_d_key']=(setup['d']['time'],setup['d']['price'])
    d.shock_chain['refined_first_hold']=copy.deepcopy(setup.get('rebound'))
    return d


def test_btc_retest_stage_is_b2_not_later_b1_fallback():
    p,setup,_=case('BTC',3,'B1');d=staged(setup,ts(p['entry_time'])//900*900)
    assert [r for r,_ in d.setups()]==['B2']
    assert expanded_shock_setup(d.setups()[0][1],ts(p['entry_time']),'B2')['setup_passed']
    assert d.b_state()['phase']=='B2_HL_available'


def test_first_hold_breakout_window_and_stale_warmup_scope():
    p,setup,_=case('BTC',3,'B1');setup['hl']=None
    d=staged(setup,setup['rebound']['t']+900)
    assert [r for r,_ in d.setups()]==['B1']
    assert independent_b1_setup(d.setups()[0][1],d.p1_now,setup['rebound'])['setup_passed']
    d.p1_now+=900
    assert d.setups()==[] and d.b_state()['phase']=='B1_window_closed_wait_for_B2'
    p,old,_=case('SOL',1,'B1');d=staged(old,ts(p['entry_time'])//900*900)
    assert 'B1' not in [r for r,_ in d.setups()]


def test_d_candle_cannot_be_independent_hold_and_failed_attempt_cannot_roll_d():
    data=read(REPORT/'NEW_SOL_ENTRY.json');s=data['signal'];c=s['setup_evidence']
    d=staged(c,ts(s['time_utc'])//900*900)
    assert not d.setups() # Original 06:15 B1 was its own D candle.
    p,setup,book=case('BTC',3,'B1');d=staged(setup,setup['rebound']['t']+900)
    # Use a later actual BTC observation below the episode D, not a fabricated bar.
    with sqlite3.connect((ROOT/book['actual_source']).as_uri()+'?mode=ro',uri=True) as db:
        body=db.execute("SELECT body FROM minutes WHERE t>? AND json_extract(body,'$.low')<? ORDER BY t LIMIT 1",(ts(p['entry_time']),setup['d']['price'])).fetchone()[0]
    import json
    d.invalidate(json.loads(body));assert d.shock_chain['refined_retired'] and d.setups()==[]


def test_fresh_real_shock_replaces_old_episode_without_resetting_a():
    p,new,book=case('BTC',3,'B1');_,old,_=case('BTC',1,'B1')
    d=staged(old,ts(p['entry_time'])//900*900);d.lowest=new['lowest_before_impulse']
    with sqlite3.connect((ROOT/book['actual_source']).as_uri()+'?mode=ro',uri=True) as db:
        import json
        bars=[json.loads(b) for b, in db.execute('SELECT body FROM minutes WHERE t>=? AND t<? ORDER BY t',(new['impulse']['t']-900,new['impulse']['t']))]
    previous=aggregate(bars,900)
    d.observe(new['impulse'],previous,new['impulse']['t']+900)
    assert d.shock_chain['impulse']['t']==new['impulse']['t'] and d.shock_chain['d']==new['d']
    assert d.shock_chain['refined_first_hold'] is None
    d.observe(new['rebound'],new['impulse'],new['rebound']['t']+900)
    assert d.shock_chain['refined_first_hold']['t']==new['rebound']['t']


def test_p1_independence_thresholds_and_no_new_risk_parameters():
    assert PROTOCOL['A']['post_d_complete_holds']==2
    assert PROTOCOL['A']['rebound_high_atr']==1 and PROTOCOL['A']['completed_close_atr']==.5
    assert PROTOCOL['priority']==['A','B2','B1']
