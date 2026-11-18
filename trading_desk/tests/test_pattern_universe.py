"""Daily liquidity/beta/ATR checks against saved observed provider bars."""
import copy
from pathlib import Path
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from trading_desk.pattern_universe import daily,measure,screen,POLICY
from trading_desk.pattern_library import HOME
from trading_desk.btc_data import read

@pytest.fixture(scope='module')
def source():
    s=read(HOME/'UNIVERSE_SCREEN.json')
    if not s:pytest.skip('Requires authorized real daily universe scan')
    return read(ROOT/s['source_file']),s


def test_beta_uses_aligned_real_sessions_and_spy_is_its_own_unit_beta(source):
    raw,saved=source;b=daily(raw['products']['SPY'],raw['sessions']);r=measure('SPY',b,b)
    assert r['beta63']==pytest.approx(1) and r['atr14']>0
    assert r['atr_pct']==pytest.approx(r['atr14']/r['close']*100)
    assert not r['qualifies'] and not r['high_beta']


def test_missing_or_duplicate_sessions_are_never_filled(source):
    raw,_=source;rows=copy.deepcopy(raw['products']['SPY']);chosen=daily(rows,raw['sessions'])
    day=chosen[-3]['day'];missing=[b for b in rows if not b['t'].startswith(day)]
    with pytest.raises(ValueError,match='Missing'):daily(missing,raw['sessions'])
    with pytest.raises(ValueError,match='Duplicate'):daily(rows+[rows[-1]],raw['sessions'])


def test_all_selected_names_pass_every_gate_and_inverse_funds_are_not_auto_selected(source):
    raw,saved=source;r=screen(raw,[x['symbol'] for x in saved['rows']]+[x['symbol'] for x in saved['omitted']])
    selected=[x for x in r['rows'] if x['selected']]
    assert len(selected)==12 and r['suggested_watchlist'][0]=='BTC/USD'
    for x in selected:
        assert x['beta63']>=1.25 and x['atr_pct']>=3
        assert min(x['avg_dollar_volume_5'],x['avg_dollar_volume_20'])>=500_000_000
        assert min(x['avg_shares_5'],x['avg_shares_20'])>=5_000_000
        assert x['direction']=='positive'
    assert all(not x['selected'] for x in r['rows'] if x['symbol'] in ('SQQQ','SOXS'))
    assert sum(x['kind']=='stock' for x in selected)==8 and sum(x['kind']=='ETF' for x in selected)==4
    before={x['symbol']:x for x in saved['rows']}
    for x in r['rows']:
        assert x['beta63']==before[x['symbol']]['beta63'] and x['atr14']==before[x['symbol']]['atr14']
