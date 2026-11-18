"""Discovery contracts on archived real candles; no fabricated market data."""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'trading_desk'))
sys.path.insert(0, str(ROOT))
import range_discovery as rd


def real_crypto():
    snapshot = json.loads((ROOT / 'reports/range_trading/NEAR_DOT_REFRESH.json').read_text())
    asof = datetime.fromisoformat(snapshot['retrieved_at'].replace('Z', '+00:00')).timestamp()
    return snapshot, asof


def test_round_up_rule_keeps_dot_but_not_the_three_stocks():
    assert rd.ratio(1.1016, 1.262)[1] == 15
    assert rd.ratio(4.7621, 5.843)[1] == 23
    assert rd.ratio(171.71, 178.08)[1] == 4
    assert rd.ratio(79.695, 84.14)[1] == 6
    assert rd.ratio(339.8, 346.62)[1] == 3
    assert rd.ratio(100, 114)[1] == 14
    assert rd.ratio(100, 115)[1] == 15


@pytest.mark.parametrize('lower,upper', [(0, 1), (2, 1), (None, 1), (1, float('nan')), (True, 2)])
def test_invalid_boundaries_never_produce_a_ratio(lower, upper):
    with pytest.raises(ValueError):
        rd.ratio(lower, upper)


def test_real_dot_passes_requested_one_million_volume_floor_but_is_research_only():
    source, asof = real_crypto()
    row = rd.crypto_row('DOT', source['products']['DOT-USD'], asof, True, days=7)
    assert row['rounded_ratio'] == 15
    # User lowered the crypto dollar-volume minimum from $10M to $1M.
    assert row['liquidity_pass'] is True
    assert row['quality_pass'] is False
    assert row['execution_enabled'] is False
    assert row['paper_supported'] is True


def test_real_near_is_not_implicitly_enabled_for_alpaca():
    source, asof = real_crypto()
    row = rd.crypto_row('NEAR', source['products']['NEAR-USD'], asof, False, days=7)
    assert row['liquidity_pass'] is True
    assert row['quality_pass'] is False
    assert row['paper_supported'] is False


def test_stale_or_missing_candles_do_not_become_discoveries():
    source, asof = real_crypto()
    with pytest.raises(ValueError):
        rd.crypto_row('NEAR', source['products']['NEAR-USD'], asof + 86400)
    item = source['products']['NEAR-USD']
    item['candles'].pop(3)
    with pytest.raises(ValueError):
        rd.crypto_row('NEAR', item, asof)


def test_stock_research_retains_event_and_session_context():
    source = json.loads((ROOT / 'reports/range_trading/SCHWAB_STOCKS_SOURCE.json').read_text())
    row = rd.stock_row('QCOM', source['products']['QCOM'], source['calendar'], source['retrieved_at'], days=7)
    assert row['rounded_ratio'] == 4
    assert row['volume_shares'] > 2_000_000
    assert row['source'] == 'Schwab'
    assert any('Earnings/news' in x for x in row['advisories'])
    assert row['execution_enabled'] is False
    assert row['completed_cycles'] == 2
    assert rd.qualifies(row, 3) is True
    assert rd.qualifies(row, 15) is False


def test_asts_mara_single_downward_move_is_disqualified_by_behavior():
    source = json.loads((ROOT / 'reports/range_trading/ASTS_MARA_SOURCE_2026_10_17.json').read_text())
    for symbol in ('ASTS', 'MARA'):
        row = rd.stock_row(symbol, source['products'][symbol], source['calendar'], source['retrieved_at'], days=7)
        assert row['rounded_ratio'] >= 15
        assert row['liquidity_pass'] is True
        assert row['completed_cycles'] == 0
        assert row['alternating_boundary_visits'] == ['resistance', 'support']
        assert row['last_close'] < row['support']
        assert row['quality_pass'] is False
        assert rd.qualifies(row) is False
        # The outcome depends on evidence rather than a symbol blacklist.
        assert rd.qualifies(dict(row, symbol='OTHER')) is False
        assert rd.qualifies(dict(row, quality_pass=True)) is False


def test_old_saved_badge_without_swing_evidence_is_not_a_candidate(tmp_path):
    review = json.loads((ROOT / 'reports/range_trading/RANGE_QUALITY_REVIEW_2026_10_17.json').read_text())
    old = next(row for row in review['rows'] if row['symbol'] == 'QCOM')
    old.pop('qualification_version')
    path = tmp_path / 'result.json'
    path.write_text(json.dumps({'status': 'complete', 'rows': [old], 'threshold': 3}))
    result = rd.Discovery(path).get()
    assert result['candidates'] == []
    assert result['disqualified'][0]['symbol'] == 'QCOM'


def test_get_does_not_start_provider_requests(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('opening the panel must not fetch market data')
    monkeypatch.setattr(rd, 'fetch_snapshot', forbidden)
    discovery = rd.Discovery(tmp_path / 'result.json')
    assert discovery.get()['status'] == 'idle'


def test_malformed_saved_report_does_not_prevent_startup(tmp_path):
    path = tmp_path / 'result.json'
    for contents in ('[]', '{broken'):
        path.write_text(contents)
        assert rd.Discovery(path).get()['status'] == 'idle'


def test_run_records_real_results_and_persists_for_reload(tmp_path, monkeypatch):
    source, asof = real_crypto()
    monkeypatch.setattr(rd.time, 'time', lambda: asof)
    monkeypatch.setattr(rd, 'CRYPTO_POOL', ('NEAR', 'DOT'))
    monkeypatch.setattr(rd, 'fetch_snapshot', lambda *args: source)
    class NoPaperAccount:
        def __init__(self):
            raise ValueError('no credentials for this offline test')
    monkeypatch.setattr(rd, 'Client', NoPaperAccount)
    path = tmp_path / 'result.json'
    discovery = rd.Discovery(path)
    discovery.state.update(status='running', total=2)
    discovery._run('crypto')
    result = discovery.get()
    assert result['checked'] == 2
    assert result['status'] == 'complete'
    assert [row['symbol'] for row in result['rows']] == ['NEAR', 'DOT']
    assert rd.Discovery(path).get() == result


def test_duplicate_click_reuses_running_scan_and_input_is_bounded(tmp_path, monkeypatch):
    started = []
    class FakeThread:
        def __init__(self, **kwargs):
            pass
        def start(self):
            started.append(True)
    monkeypatch.setattr(rd.threading, 'Thread', FakeThread)
    discovery = rd.Discovery(tmp_path / 'result.json')
    first = discovery.start('crypto', 15)
    assert discovery.start('stocks', 30) == first
    assert len(started) == 1
    for market, threshold in [('all', 15), ('both', 0), ('both', True), ('both', 15.1)]:
        with pytest.raises(ValueError):
            discovery.start(market, threshold)


def test_default_crypto_uses_fourteen_days_and_recent_confirmation():
    source, asof = real_crypto()
    item = source['products']['NEAR-USD']
    row = rd.crypto_row('NEAR', item, asof)
    bars = rd.normalize(item['candles'], 14400, asof)
    from ai_day_trade.range_trading import quantile
    assert row['lookback_days'] == 14
    assert row['support'] == quantile([x['low'] for x in bars[-84:]], .1)
    assert row['resistance'] == quantile([x['high'] for x in bars[-84:]], .9)
    recent = bars[-42:]
    expected, _ = rd.completed_swings([x['close'] for x in recent], row['support'], row['resistance'])
    assert row['recent_completed_cycles'] == expected
    assert row['recent_days'] == 7
    assert row['qualification_version'] == 7
    assert rd.qualifies(dict(row, quality_pass=True, liquidity_pass=True, completed_cycles=2,
                             recent_range_pass=False)) is False


def test_default_stock_rejects_short_archive_instead_of_claiming_forty_five_days():
    source = json.loads((ROOT / 'reports/range_trading/SCHWAB_STOCKS_SOURCE.json').read_text())
    with pytest.raises(ValueError, match='insufficient completed stock sessions'):
        rd.stock_row('QCOM', source['products']['QCOM'], source['calendar'], source['retrieved_at'])


def test_real_thirty_day_stock_history_is_complete_and_liquidity_stays_recent():
    source = json.loads((ROOT / 'reports/range_trading/DISCOVERY_30_DAY_STOCK_SOURCE_2026_10_17.json').read_text())
    from ai_day_trade.schwab_range_screen import screen
    full = screen(source, 30)
    recent = screen(source, 7)
    assert len(full['session_dates']) >= 20
    q = rd.stock_row('QCOM', source['products']['QCOM'], source['calendar'], source['retrieved_at'], days=30)
    assert q['lookback_days'] == 30
    q_full = next(r for r in full['results'] if r['symbol'] == 'QCOM')
    q_recent = next(r for r in recent['results'] if r['symbol'] == 'QCOM')
    assert q['support'] == q_full['support']
    assert q['volume_usd'] == q_recent['average_daily_turnover_proxy']
    assert q_full['bars'] > q_recent['bars']
    for symbol in ('ASTS', 'MARA'):
        row = rd.stock_row(symbol, source['products'][symbol], source['calendar'], source['retrieved_at'], days=30)
        assert row['lookback_days'] == 30
        assert rd.qualifies(row) is False
    broken = json.loads(json.dumps(source))
    broken['products']['QCOM']['candles'].pop(-20)
    with pytest.raises(ValueError, match='incomplete regular-session history'):
        rd.stock_row('QCOM', broken['products']['QCOM'], broken['calendar'], broken['retrieved_at'], days=30)


def test_near_passes_sixty_percent_boundary_limit_without_changing_drift_limit():
    source, asof = real_crypto()
    row = rd.crypto_row('NEAR', source['products']['NEAR-USD'], asof)
    assert .4 < row['stability'] <= .6
    assert row['drift'] <= .4
    assert row['quality_pass'] is True
    assert rd.qualifies(row) is True
    stock = json.loads((ROOT / 'reports/range_trading/DISCOVERY_30_DAY_STOCK_SOURCE_2026_10_17.json').read_text())
    mara = rd.stock_row('MARA', stock['products']['MARA'], stock['calendar'], stock['retrieved_at'], days=30)
    assert mara['drift'] > .4
    assert any('Start-to-end movement' in x for x in mara['advisories'])
    assert not rd.qualifies(mara)


def test_default_stock_uses_complete_real_forty_five_day_window():
    source = json.loads((ROOT / 'reports/range_trading/DISCOVERY_45_DAY_STOCK_SOURCE_2026_10_17.json').read_text())
    from ai_day_trade.schwab_range_screen import screen
    full = screen(source, 45)
    assert len(full['session_dates']) >= 30
    row = rd.stock_row('QCOM', source['products']['QCOM'], source['calendar'], source['retrieved_at'])
    assert row['lookback_days'] == 45
    assert row['support'] == full['results'][0]['support']
    assert row['recent_days'] == 7
    assert rd.CRYPTO_DAYS == 14
    broken = json.loads(json.dumps(source))
    broken['products']['QCOM']['candles'].pop(100)
    with pytest.raises(ValueError, match='incomplete regular-session history'):
        rd.stock_row('QCOM', broken['products']['QCOM'], broken['calendar'], broken['retrieved_at'])


def test_real_one_swing_stocks_are_review_only_and_soft_checks_do_not_reject():
    source = json.loads((ROOT / 'reports/range_trading/STOCK_REVIEW_SOURCE_2026_10_17.json').read_text())
    for symbol in ('COIN', 'MSTR'):
        row = rd.stock_row(symbol, source['products'][symbol], source['calendar'], source['retrieved_at'])
        assert row['completed_cycles'] == 1
        assert row['recent_completed_cycles'] == 0
        assert row['quality_pass'] is True
        assert rd.needs_review(row) is True
        assert rd.qualifies(row) is False
        assert isinstance(row['ranking_score'], float)
        assert not rd.needs_review(dict(row, liquidity_pass=False))
        assert not rd.needs_review(dict(row, recent_range_pass=False))
        assert not rd.needs_review(dict(row, completed_cycles=0))
        if symbol == 'COIN':
            assert row['drift'] > .4
            assert any('Start-to-end' in x for x in row['advisories'])
        else:
            assert any('Wide range' in x for x in row['advisories'])
    for symbol in ('ASTS', 'MARA'):
        row = rd.stock_row(symbol, source['products'][symbol], source['calendar'], source['retrieved_at'])
        assert row['completed_cycles'] == 0
        assert row['last_close'] < row['support']
        assert not rd.qualifies(row) and not rd.needs_review(row)


def test_api_keeps_one_swing_review_separate_from_qualified_and_disqualified(tmp_path):
    review = json.loads((ROOT / 'reports/range_trading/RANGE_QUALITY_REVIEW_V7_2026_10_17.json').read_text())
    path = tmp_path / 'scan.json'
    path.write_text(json.dumps(dict(status='complete', rows=review['rows'], threshold=15)))
    result = rd.Discovery(path).get()
    assert {r['symbol'] for r in result['needs_review']} == {'COIN', 'MSTR'}
    assert {r['symbol'] for r in result['candidates']} == {'NEAR'}
    assert not {'COIN', 'MSTR'} & {r['symbol'] for r in result['disqualified']}
