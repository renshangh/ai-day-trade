"""Use archived Coinbase observations, never synthesized market bars."""
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ai_day_trade.range_trading import Config, assess, normalize, replay, report
from ai_day_trade.alpaca_range_paper import Client, credentials, entry_liquidity, reconcile, rounded, submit

ROOT = Path(__file__).resolve().parents[2]


class RangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((ROOT / 'reports/range_trading/COINBASE_2026_10_17.json').read_text())
        cls.asof = datetime.fromisoformat(cls.snapshot['retrieved_at'].replace('Z', '+00:00')).timestamp()
        cls.raw = cls.snapshot['products']['DOT-USD']['candles']
        cls.bars = normalize(cls.raw, 14400, cls.asof)

    def test_real_dot_range_and_cost_gate(self):
        # Isolate range geometry independently of the configurable volume gate.
        result = assess(self.bars, 14400, Config(lookback_days=14, min_daily_turnover=0), asof=self.asof)
        self.assertTrue(result['eligible'])
        self.assertAlmostEqual(result['lower'], 1.088)
        self.assertFalse(result['entry_signal'])
        self.assertFalse(assess(self.bars, 14400, Config(fee=.04))['eligible'])

    def test_one_million_floor_excludes_atom_but_not_dot_volume(self):
        # The user changed the minimum to $1M; DOT still fails other range gates.
        for pair, volume_fails in (('ATOM-USD', True), ('DOT-USD', False)):
            bars = normalize(self.snapshot['products'][pair]['candles'], 14400, self.asof)
            result = assess(bars, 14400)
            self.assertFalse(result['eligible'])
            self.assertEqual('24h turnover proxy too low' in result['reasons'], volume_fails)

    def test_missing_and_stale_data_fail_closed(self):
        gapped = self.bars[:-5] + self.bars[-4:]
        self.assertFalse(assess(gapped, 14400)['eligible'])
        self.assertFalse(replay(gapped, 14400)['available'])
        self.assertFalse(assess(self.bars, 14400, asof=self.asof + 28800)['eligible'])
        self.assertFalse(assess([], 14400)['eligible'])

    def test_duplicate_and_malformed_observations_rejected(self):
        with self.assertRaises(ValueError):
            normalize(self.raw + [self.raw[0]], 14400, self.asof)
        damaged = copy.deepcopy(self.raw)
        damaged[0]['close'] = 'NaN'
        with self.assertRaises(ValueError):
            normalize(damaged, 14400, self.asof)

    def test_forming_candle_excluded_and_order_irrelevant(self):
        self.assertTrue(all(x['start'] + 14400 <= self.asof for x in self.bars))
        self.assertEqual(self.bars, normalize(list(reversed(self.raw)), 14400, self.asof))
        self.assertLess(len(self.bars), len(self.raw))

    def test_actual_avax_stop_and_risk_sizing(self):
        bars = normalize(self.snapshot['products']['AVAX-USD']['candles'], 14400, self.asof)
        # Preserve the original geometry/risk regression independently of the
        # stricter production liquidity filter added after the first screen.
        result = replay(bars, 14400, Config(lookback_days=14, min_daily_turnover=0))
        self.assertEqual(result['closed_trades'], 1)
        self.assertEqual(result['trades'][0]['reason'], 'stop')
        self.assertAlmostEqual(result['ending_equity'], 9975)
        self.assertLessEqual(result['trades'][0]['entry_time'], result['trades'][0]['exit_time'])

    def test_replay_prefix_is_causal(self):
        bars = normalize(self.snapshot['products']['AVAX-USD']['candles'], 14400, self.asof)
        prefix = replay(bars[:-12], 14400)
        full = replay(bars, 14400)
        self.assertEqual(prefix['equity_curve'], full['equity_curve'][:len(prefix['equity_curve'])])

    def test_unsupported_product_is_explicit(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['products']['UNAVAILABLE'] = {'error': 'not tradable'}
        row = next(x for x in report(snapshot, Config(), 1000)['results'] if x['product'] == 'UNAVAILABLE')
        self.assertFalse(row['eligible'])
        self.assertEqual(row['reasons'], ['not tradable'])

    def test_config_rejects_nonfinite(self):
        for fee in (float('nan'), -1, 1):
            with self.assertRaises(ValueError):
                Config(fee=fee)

    def test_seven_day_focus(self):
        from ai_day_trade.range_trading import UNIVERSE
        self.assertEqual(Config().lookback_days, 7)
        self.assertEqual(UNIVERSE, ('NEAR', 'DOT'))
        # Older observations must not affect the requested seven-day window.
        self.assertEqual(assess(self.bars, 14400), assess(self.bars[-42:], 14400))


class PaperTests(unittest.TestCase):
    def test_paper_guard(self):
        with patch.dict('os.environ', {'ALPACA_IS_PAPER': 'false'}, clear=True):
            with self.assertRaises(ValueError):
                credentials()

    def test_pinned_hosts_and_no_redirects(self):
        with patch('ai_day_trade.alpaca_range_paper.credentials', return_value={}):
            client = Client()
        with self.assertRaises(ValueError):
            client.request('https://api.alpaca.markets/v2/orders', body={})
        with self.assertRaises(ValueError):
            client.request('/v2/account', body={})
        with self.assertRaises(ValueError):
            client.request('/v2/orders', data=True, body={})

    def test_fractional_precision(self):
        self.assertEqual(rounded(1.1372, '.001'), '1.137')
        self.assertEqual(rounded(.1, '.003'), '0.099')

    def test_empty_orderbook_blocks_entry(self):
        class EmptyBook:
            def request(self, path, **kwargs):
                return {'orderbooks': {'DOT/USD': {'t': '2026-10-17T20:00:00Z', 'a': [], 'b': []}}}
        self.assertFalse(entry_liquidity(EmptyBook(), 'DOT/USD', 1792267200, 200))

    def test_ambiguous_submission_keeps_pending_intent(self):
        class UncertainClient:
            def request(self, *args, **kwargs):
                raise TimeoutError('uncertain submission')
        state = {'last_signal': {}}
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            with self.assertRaises(TimeoutError):
                submit(UncertainClient(), state, path, 'DOT/USD', 'buy', '1', 1792267200, candle=1792252800)
            persisted = json.loads(path.read_text())
            self.assertIsNotNone(persisted['pending'])
            self.assertEqual(persisted['last_signal']['DOT/USD'], 1792252800)

    def test_partial_buy_uses_net_broker_units(self):
        class FilledClient:
            def request(self, path):
                if path == '/v2/positions':
                    return [{'symbol': 'DOTUSD', 'qty': '0.9975'}]
                # Execution price from the archived Oct 17 Coinbase quote.
                return {'status': 'canceled', 'filled_qty': '1', 'filled_avg_price': '1.1372'}
        state = dict(cash=1000, fee=.0025, positions={}, journal=[], pending=dict(
            symbol='DOT/USD', side='buy', client_order_id='example-paper-id', created_at=1792267200,
            plan={'stop': 1.0678214285714287, 'target': 1.236155}))
        reconcile(FilledClient(), state)
        self.assertEqual(state['positions']['DOT/USD']['qty'], .9975)
        self.assertAlmostEqual(state['cash'], 998.8628)
        self.assertIsNone(state['pending'])


if __name__ == '__main__':
    unittest.main()
