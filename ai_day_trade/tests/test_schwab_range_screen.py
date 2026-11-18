"""Stock-session tests using archived real Schwab bars and broker calendar."""
import copy
import json
import unittest
from pathlib import Path

from ai_day_trade.schwab_range_screen import screen, session_grid

ROOT = Path(__file__).resolve().parents[2]


class StockRangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / 'reports/range_trading/SCHWAB_STOCKS_SOURCE.json').read_text())

    def test_verified_stock_ranges_and_liquidity(self):
        result = screen(self.source)
        qualified = {row['symbol']: row for row in result['results'] if row['range_qualified']}
        self.assertEqual(set(qualified), {'AAPL', 'WFC', 'QCOM'})
        self.assertEqual(qualified['QCOM']['support'], 171.71)
        self.assertEqual(len(result['session_dates']), 5)
        self.assertTrue(all(row['average_daily_shares'] >= 2_000_000 for row in qualified.values()))
        self.assertTrue(all(not row['entry_authorized'] for row in qualified.values()))

    def test_missing_intraday_bar_withholds_symbol(self):
        source = copy.deepcopy(self.source)
        source['products']['QCOM']['candles'].pop(-3)
        row = next(x for x in screen(source)['results'] if x['symbol'] == 'QCOM')
        self.assertFalse(row['range_qualified'])
        self.assertIn('incomplete regular-session history', row['reasons'][0])

    def test_overnight_and_weekend_are_not_filled(self):
        expected = session_grid(self.source['calendar'], self.source['retrieved_at'], 7)
        self.assertEqual(sum(map(len, expected.values())), 65)
        self.assertTrue(all(len(stamps) == 13 for stamps in expected.values()))

    def test_duplicate_bar_rejected(self):
        source = copy.deepcopy(self.source)
        source['products']['AAPL']['candles'].append(source['products']['AAPL']['candles'][-2])
        row = next(x for x in screen(source)['results'] if x['symbol'] == 'AAPL')
        self.assertFalse(row['range_qualified'])
        self.assertIn('duplicate', row['reasons'][0])


if __name__ == '__main__':
    unittest.main()
