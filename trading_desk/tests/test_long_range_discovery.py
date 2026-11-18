"""Two-year mode contracts on archived real daily SIP observations."""
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'trading_desk'))
import range_discovery as rd
import long_range_discovery as long


@pytest.fixture(scope='module')
def source():
    return json.loads((ROOT / 'reports/range_trading/TWO_YEAR_DAILY_SOURCE_2026_10_17.json').read_text())


def row(source, symbol):
    now = datetime.fromisoformat(source['retrieved_at']).timestamp()
    return long.stock_row(symbol, source['products'][symbol], source['calendar'], now, rd.QUALITY_VERSION)


@pytest.mark.parametrize('symbol', ['SWKS', 'IBM', 'SMCI', 'BKNG', 'RIVN', 'META', 'COST'])
def test_real_two_year_matches_keep_measured_evidence(source, symbol):
    result = row(source, symbol)
    assert result['stock_mode'] == 'two_year' and result['lookback_days'] == 730
    assert result['completed_cycles'] == 3
    assert min(result['annual_cycles']) >= 1
    assert len(result['quarter_containment']) == 8
    assert len(result['daily_closes']) == 501
    assert result['execution_enabled'] is False
    assert rd.qualifies(result) and not rd.needs_review(result)


def test_recent_swing_ranks_but_does_not_exclude_long_term_matches(source):
    assert row(source, 'RIVN')['recent_six_month_cycles'] == 0
    assert row(source, 'SWKS')['recent_six_month_cycles'] >= 1
    assert row(source, 'SWKS')['ranking_score'] > row(source, 'RIVN')['ranking_score']
    assert rd.qualifies(row(source, 'RIVN'))


def test_missing_duplicate_and_short_listing_never_gain_fake_history(source):
    now = datetime.fromisoformat(source['retrieved_at']).timestamp()
    bars = source['products']['SWKS']
    with pytest.raises(ValueError, match='Incomplete'):
        long.stock_row('SWKS', bars[:100] + bars[101:], source['calendar'], now, rd.QUALITY_VERSION)
    with pytest.raises(ValueError, match='Duplicate'):
        long.stock_row('SWKS', bars + [bars[-1]], source['calendar'], now, rd.QUALITY_VERSION)
    with pytest.raises(ValueError, match='Incomplete'):
        row(source, 'CRCL')


def test_old_badges_and_one_swing_do_not_bypass_long_term_requirements(source):
    result = row(source, 'SWKS')
    assert not rd.qualifies(dict(result, qualification_version=6))
    assert not rd.qualifies(dict(result, completed_cycles=2))
    assert not rd.qualifies(dict(result, volume_usd_5=1))
    assert not rd.qualifies(dict(result, annual_cycles=[3, 0]))
    assert not rd.qualifies(dict(result, quarter_containment=[1] * 7 + [.4]))
    assert not rd.needs_review(dict(result, completed_cycles=1))


def test_stale_calendar_cannot_claim_fresh_two_year_prices(source):
    now = datetime.fromisoformat(source['retrieved_at']).timestamp()
    with pytest.raises(ValueError, match='stale'):
        long.expected_sessions(source['calendar'], now + 14 * 86400)


def test_two_year_job_uses_broad_pool_and_persists_omissions(source, tmp_path, monkeypatch):
    now = datetime.fromisoformat(source['retrieved_at']).timestamp()
    monkeypatch.setattr(rd.time, 'time', lambda: now)
    monkeypatch.setattr(long, 'stock_pool', lambda pool: ('SWKS', 'CRCL'))
    monkeypatch.setattr(long, 'fetch_snapshot', lambda symbols, asof: source)
    class NoPaper:
        def __init__(self):
            raise ValueError('offline fixture')
    monkeypatch.setattr(rd, 'Client', NoPaper)
    discovery = rd.Discovery(tmp_path / 'scan.json')
    discovery.state.update(status='running', stock_mode='two_year', total=2,
                           lookback_days={'crypto': 14, 'stocks': 730}, rule=rd.LONG_SELECTION_RULE)
    discovery._run('stocks')
    result = discovery.get()
    assert result['checked'] == 2 and result['status'] == 'complete'
    assert [r['symbol'] for r in result['candidates']] == ['SWKS']
    assert result['omitted'][0]['symbol'] == 'CRCL'
    assert rd.Discovery(discovery.path).get() == result


def test_mode_is_bounded_and_pool_includes_new_matches(tmp_path):
    pool = long.stock_pool(rd.STOCK_POOL)
    # Sector/watchlist membership changes; retain the broad-pool contract
    # rather than freezing an incidental historical constituent count.
    expected = set(rd.STOCK_POOL) | set(long.EXTRA)
    expected |= {symbol for group in long.all_groups().values() for symbol in group['constituents']}
    assert set(pool) == expected and tuple(sorted(set(pool))) == pool
    assert {'SWKS', 'IBM', 'BKNG', 'SMCI'} <= set(pool)
    discovery = rd.Discovery(tmp_path / 'scan.json')
    with pytest.raises(ValueError, match='stock_mode'):
        discovery.start('stocks', 15, 'arbitrary')
