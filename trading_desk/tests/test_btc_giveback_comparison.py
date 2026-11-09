"""Two-case profit protection hypotheses, causal real bars, no monthly run."""
import hashlib
import json
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
import audit_btc_oct12_giveback as audit
from trading_desk.btc_data import ts,STORE


@pytest.fixture(scope='module')
def reviewed():return audit.review()


def variants(c):return {v['variant']:v for v in c['variants']}


def test_explicit_hypotheses_never_become_approved_parameters(reviewed):
    assert not reviewed['approved_for_execution'] and not reviewed['month_rerun']
    assert reviewed['broker_orders']==0
    assert reviewed['parameters']['minimum_favourable_excursion_initial_r']==1
    assert reviewed['parameters']['giveback_fraction']==.5
    assert not reviewed['parameters']['numeric_search_performed']
    assert len(reviewed['cases'][0]['rows'])==6 and len(reviewed['cases'][1]['rows'])==19


def test_early_exit_conflicts_with_inside_exception_and_rebound_follows(reviewed):
    c=reviewed['cases'][0];v=variants(c)['half_1r'];p=v['trade']
    assert len(p['legs'])==1 and p['legs'][0]['fraction']==1
    assert p['legs'][0]['time_utc']=='2026-10-12T14:06:00Z'
    assert p['legs'][0]['price']==82752.0485
    assert v['realized_net']==pytest.approx(147.6388213)
    event=p['giveback_candidate_exits'][0]
    assert event['body_inside'] and event['inside_exempt']
    assert c['first_intrabar_half_touch']['time_utc']=='2026-10-12T14:05:00Z'
    assert c['first_intrabar_half_touch']['reference_price']==pytest.approx(82760.6725)
    _,m=audit.load()
    later=next(b for b in m if b['t']==ts('2026-10-12T10:06:00-04:00'))
    assert later['close']==82891.8455>p['legs'][0]['price']


def test_inside_respecting_candidate_keeps_first_profit_and_closes_remainder(reviewed):
    c=reviewed['cases'][0];v=variants(c)['half_1r_direction_inside'];p=v['trade']
    assert [l['fraction'] for l in p['legs']]==[.25,.75]
    assert [l['time_utc'] for l in p['legs']]==['2026-10-12T14:11:00Z','2026-10-12T14:19:00Z']
    assert p['legs'][-1]['price']==82754.706
    assert p['legs'][-1]['net']==pytest.approx(112.72184235)
    assert v['realized_net']==pytest.approx(218.89633641039558)
    e=p['giveback_candidate_exits'][0]
    assert e['non_green'] and e['not_above_previous_close'] and not e['inside_exempt']
    assert e['giveback_fraction']==pytest.approx(.6093906774912897)
    # The containing 15m candle later closes GREEN; it was not knowable early.
    row=next(b for b in c['rows'] if b['time_utc']=='2026-10-12T14:15:00Z')
    assert row['completed_colour']=='green'
    assert row['ohlc']['close']==82871.475


def test_last_minute_confirmation_is_later_and_less_profitable_in_this_case(reviewed):
    v=variants(reviewed['cases'][0])
    last=v['lastminute_1r_direction_inside']
    assert last['trade']['legs'][-1]['time_utc']=='2026-10-12T14:44:00Z'
    assert last['trade']['legs'][-1]['price']==82597.8445
    assert last['realized_net']==pytest.approx(101.27374063539627)
    assert v['baseline']['realized_net']==pytest.approx(-104.10726869585321)


def test_evening_all_variants_hold_75_percent_and_no_hidden_intraminute_half_touch(reviewed):
    c=reviewed['cases'][1]
    assert c['maximum_armed_giveback']==pytest.approx(.251321570561709)
    envelope=c['intraminute_giveback_upper_bound']
    assert envelope['fraction']==pytest.approx(.2950026936017272)
    assert envelope['fraction']<.5
    assert envelope['actual_order_known'] is False
    assert c['first_intrabar_half_touch'] is None
    for v in c['variants']:
        assert v['trade']['status']=='open' and v['trade']['remaining']==.75
        assert len(v['trade']['legs'])==1
        assert v['trade']['legs'][0]['time_utc']=='2026-10-13T02:57:00Z'
        assert v['realized_net']==pytest.approx(383.0192816714264)


def test_each_observation_ignores_future_and_unfinished_minute_range(reviewed):
    _,m=audit.load()
    old=json.loads((audit.FOLDER/'B_BRANCH_REVIEW.json').read_text())['cases'][0]['trade']
    now=next(b for b in m if b['t']==ts('2026-10-12T10:05:00-04:00'))
    full=audit.observation(old,now,m)
    prefix=audit.observation(old,now,[b for b in m if b['t']<now['t']])
    assert full==prefix and full['highest_known_price']==82950
    now=next(b for b in m if b['t']==ts('2026-10-12T10:19:00-04:00'))
    full=audit.observation(old,now,m)
    missing=audit.observation(old,now,[b for b in m if b['t']!=ts('2026-10-12T10:18:00-04:00')])
    assert not missing['reference_context_complete']
    assert not audit.qualifies(missing,'half_1r_direction_inside')


def test_missing_case_minute_is_reported_not_filled(monkeypatch):
    source,m=audit.load()
    monkeypatch.setattr(audit,'load',lambda:(source,[b for b in m if b['t']!=ts('2026-10-12T10:18:00-04:00')]))
    with pytest.raises(ValueError,match='Missing minutes'):audit.review()


def test_no_month_or_old_case_is_changed(monkeypatch):
    from trading_desk import btc_engine
    monkeypatch.setattr(btc_engine,'run',lambda *a,**k:pytest.fail('No monthly run authorized'))
    paths=[STORE/'latest_run.json',STORE/'runs'/audit.BASELINE/'result.json',audit.FOLDER/'B_BRANCH_REVIEW.json',
        audit.FOLDER.parent/'oct12_structure_exit/REVIEW.json']
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    dirs=sorted(p.name for p in (STORE/'runs').iterdir())
    audit.review()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in before.items())
    assert dirs==sorted(p.name for p in (STORE/'runs').iterdir())
