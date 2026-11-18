"""Snapshot charts must reproduce actual observed prices and measured bands."""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'trading_desk'))
import range_discovery as rd


def setup(discovery, row, asof):
    scan = rd.iso(asof)
    discovery.state.update(status='complete', started_at=scan, rows=[row])
    return scan


@pytest.mark.parametrize('symbol', ['NEAR', 'DOT'])
def test_crypto_chart_keeps_four_hour_bars_and_does_not_route_as_stock(symbol, tmp_path, monkeypatch):
    source = json.loads((ROOT / 'reports/range_trading/NEAR_DOT_REFRESH.json').read_text())
    asof = datetime.fromisoformat(source['retrieved_at'].replace('Z', '+00:00')).timestamp()
    row = rd.crypto_row(symbol, source['products'][symbol + '-USD'], asof)
    discovery = rd.Discovery(tmp_path / 'scan.json')
    scan = setup(discovery, row, asof)
    monkeypatch.setattr(rd, 'fetch_snapshot', lambda symbols, cutoff: source)
    result = discovery.chart(symbol, 'crypto', scan)
    assert result['asset_type'] == 'crypto'
    assert result['discovery']['interval'] == '4h'
    assert len(result['bars']) == 84
    stamps = [datetime.fromisoformat(b['t'].replace('Z', '+00:00')).timestamp() for b in result['bars']]
    assert all(b - a == 14400 for a, b in zip(stamps, stamps[1:]))
    assert result['bars'][-1]['c'] == row['last_close']
    assert result['discovery']['support'] == row['support']
    with pytest.raises(ValueError, match='unavailable'):
        discovery.chart(symbol, 'stock', scan)


def test_long_chart_uses_actual_ohlcv_and_caches_within_same_scan(tmp_path, monkeypatch):
    path = ROOT / 'reports/range_trading/TWO_YEAR_DAILY_SOURCE_2026_10_17.json'
    source = json.loads(path.read_text())
    asof = datetime.fromisoformat(source['retrieved_at']).timestamp()
    row = rd.long_range_discovery.stock_row('SWKS', source['products']['SWKS'], source['calendar'], asof, rd.QUALITY_VERSION)
    discovery = rd.Discovery(tmp_path / 'scan.json')
    scan = setup(discovery, row, asof)
    monkeypatch.setattr(rd.long_range_discovery, 'SOURCE_PATH', path)
    result = discovery.chart('SWKS', 'stock', scan)
    assert len(result['bars']) == 501
    actual = source['products']['SWKS'][-1]
    assert {k:result['bars'][-1][k] for k in ('o','h','l','c','v')} == {k:actual[k] for k in ('o','h','l','c','v')}
    monkeypatch.setattr(rd.long_range_discovery, 'SOURCE_PATH', tmp_path / 'missing.json')
    assert discovery.chart('SWKS', 'stock', scan) == result


def test_short_stock_chart_uses_observed_thirty_minute_regular_sessions(tmp_path, monkeypatch):
    source = json.loads((ROOT / 'reports/range_trading/DISCOVERY_30_DAY_STOCK_SOURCE_2026_10_17.json').read_text())
    asof = source['retrieved_at']
    item = source['products']['QCOM']
    row = rd.stock_row('QCOM', item, source['calendar'], asof, days=30)
    discovery = rd.Discovery(tmp_path / 'scan.json')
    setup(discovery, row, asof)
    class Calendar:
        def request(self, path):
            return source['calendar']
    monkeypatch.setattr(rd, 'Client', Calendar)
    monkeypatch.setattr(rd.schwab_api, 'load_env', lambda path: None)
    monkeypatch.setattr(rd.schwab_api, 'api', lambda path, params: item)
    result = discovery.chart('QCOM', 'stock')
    expected = set.union(*rd.session_grid(source['calendar'], asof, 30).values())
    assert len(result['bars']) == len(expected)
    assert {datetime.fromisoformat(b['t'].replace('Z', '+00:00')).timestamp() for b in result['bars']} == expected


def test_changed_or_missing_snapshot_cannot_substitute_old_chart_prices(tmp_path, monkeypatch):
    source = json.loads((ROOT / 'reports/range_trading/NEAR_DOT_REFRESH.json').read_text())
    asof = datetime.fromisoformat(source['retrieved_at'].replace('Z', '+00:00')).timestamp()
    row = rd.crypto_row('NEAR', source['products']['NEAR-USD'], asof)
    discovery = rd.Discovery(tmp_path / 'scan.json')
    scan = setup(discovery, row, asof)
    monkeypatch.setattr(rd, 'fetch_snapshot', lambda *args: source)
    with pytest.raises(ValueError, match='scan changed'):
        discovery.chart('NEAR', 'crypto', 'different scan')
    # Alter the advertised boundary, not any source market observations.
    discovery.state['rows'][0]['support'] += .01
    with pytest.raises(ValueError, match='history changed'):
        discovery.chart('NEAR', 'crypto', scan)
    assert discovery.chart_cache == {}
