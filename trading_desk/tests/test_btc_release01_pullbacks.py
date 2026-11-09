"""Real archived cases: distinguish warning, known structure and protective exit."""
import hashlib
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from scripts.audit_btc_release01_pullbacks import review,RUN
from trading_desk.btc_data import STORE,ts,read


@pytest.fixture(scope='module')
def cases():return {c['trade_id']:c for c in review()['cases']}


def candle(cases,i,time):return next(b for b in cases[i]['bars'] if b['time']==time)


def test_three_complete_real_slices_and_frozen_outcomes(cases):
    assert {i:(len(c['bars']),c['source_minutes']) for i,c in cases.items()}=={5:(7,105),32:(35,525),30:(31,465)}
    for c in cases.values():
        assert c['missing_minutes']==0 and all(b['complete'] for b in c['bars'])
        assert sum(l['net'] for l in c['legs'])==pytest.approx(c['net'])
        assert not c['hard_stop_moved']
        assert all(ts(b['close_known_at'])==ts(b['time'])+900 for b in c['bars'])
        assert all(ts(m['close_known_at'])==ts(m['time'])+60 for m in c['minutes'])
    assert cases[5]['net']==pytest.approx(-762.7505927499553)
    assert cases[32]['net']==pytest.approx(-732.6663634999907)
    assert cases[30]['net']==pytest.approx(1454.4912061761684)


def test_trade5_first_warning_is_not_an_early_fifteen_minute_close(cases):
    c=cases[5];first=next(m for m in c['minutes'] if m['time']=='2026-10-15T13:45:00Z')
    assert first['close']==80508.782 and first['close_known_at']=='2026-10-15T13:46:00Z'
    assert first['below_original_trigger'] and not first['d_breached']
    breach=next(m for m in c['minutes'] if ts(m['time'])>=ts(c['entry']['entry_time']) and m['d_breached'])
    assert breach['time']=='2026-10-15T13:53:00Z' and breach['stop_touched']
    b=candle(cases,5,'2026-10-15T13:45:00Z')
    assert b['completed_after_exit'] and b['close_known_at']=='2026-10-15T14:00:00Z'
    assert c['failed_rebound_history']==[]


def test_trade32_lower_pairs_are_warning_not_a_backdated_pivot_exit(cases):
    b=candle(cases,32,'2026-11-05T17:00:00Z') # 12:00 EST, known 12:15.
    assert b['consecutive_lower_pairs']==2 and b['below_original_trigger']
    assert b['close_known_at']=='2026-11-05T17:15:00Z'
    assert not any(e['type']=='failed_rebound_reference' and ts(e['time_utc'])<=ts(b['close_known_at']) for e in cases[32]['failure_events'])
    assert b['d_held_over_full_bar'] and cases[32]['max_known_price_mfe_r']<1
    reclaim=candle(cases,32,'2026-11-05T19:30:00Z') # 14:30 EST.
    assert reclaim['close']>cases[32]['entry']['references']['trigger']
    first=cases[32]['failure_events'][0]
    assert first['type']=='failed_rebound_reference' and first['time_utc']=='2026-11-05T19:15:00Z'
    assert any(e['type']=='failed_rebound_reclaimed' and e['time_utc']=='2026-11-05T19:15:00Z' for e in cases[32]['failure_events'])
    final=cases[32]['final_exit_evidence']['failed_rebound']
    assert final['lower_high']['known_at']==ts('2026-11-05T22:45:00Z')
    assert cases[32]['exit_time']=='2026-11-05T22:47:00Z'
    assert final['price']==75558.5075>cases[32]['original_d']['price']


def test_trade30_red_below_trigger_still_holds_effective_hl(cases):
    c=cases[30];b=candle(cases,30,'2026-11-04T14:15:00Z') # 09:15 EST, known 09:30.
    assert b['close']<b['open'] and b['below_original_trigger'] and b['higher_high_higher_low']
    assert b['active_15m_reference']['price']==78026.42<b['low']
    assert b['active_15m_reference']['effective_at']==ts('2026-11-04T13:15:00Z')
    assert b['close_known_at']=='2026-11-04T14:30:00Z'
    assert c['legs'][0]['time_utc']=='2026-11-04T14:40:00Z' and c['legs'][0]['fraction']==.25
    assert c['legs'][1]['time_utc']=='2026-11-04T19:05:00Z' and c['legs'][1]['fraction']==.75
    assert c['legs'][0]['net']==pytest.approx(103.52637152616256)
    assert c['legs'][1]['net']==pytest.approx(1350.9648346500057)


def test_only_read_only_sidecar_and_no_month_replay(monkeypatch):
    from trading_desk import btc_engine,btc_lab
    paths=[STORE/'latest_run.json',STORE/'releases/ACTIVE.json',STORE/'runs'/RUN/'result.json',STORE/'runs'/RUN/'RESEARCH.xlsx',STORE/'releases/0.1/BTC_STRUCTURE_RELEASE_0.1.zip']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    folders=sorted(p.name for p in (STORE/'runs').iterdir())
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('Monthly replay forbidden'))
    monkeypatch.setattr(btc_engine,'create_replay',lambda *a,**k:pytest.fail('No strategy replay needed'))
    r=review();assert not r['month_rerun'] and not r['new_exit_rule_adopted'] and not r['release_modified']
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert folders==sorted(p.name for p in (STORE/'runs').iterdir())
    detail=btc_lab.Lab().detail(RUN)
    assert [c['trade_id'] for c in detail['pullback_review']['cases']]==[5,32,30]
    assert btc_lab.Lab().detail('20261109T122648Z-30-ab')['pullback_review'] is None
