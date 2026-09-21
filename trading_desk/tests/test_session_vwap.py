"""Offline arithmetic and data-integrity tests; fixtures are not market history."""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import session_vwap as v


def instant(hour=11, minute=47, day=14, month=9):
    return datetime(2026, month, day, hour, minute, tzinfo=v.EASTERN)


def bar(hour, minute, volume=100, price=60, close=60):
    return {"t": instant(hour, minute).isoformat(), "v": volume, "vw": price, "c": close}


class SessionVwapTests(unittest.TestCase):
    def setUp(self):
        v._cached = None

    def request(self, url):
        if '/calendar?' in url:
            return [{"date": "2026-09-14", "open": "09:30", "close": "16:00"}]
        symbol = parse_qs(urlparse(url).query)['symbols'][0]
        return {"bars": {symbol: [bar(9, 30), bar(11, 29, 900, 62, 63)]}, "next_page_token": None}

    def test_volume_weighting_and_last_price_same_window(self):
        rows = [bar(9, 29, 10000, 500), bar(9, 30), bar(11, 29, 900, 62, 63), bar(11, 30, 10000, 500)]
        result = v.summarize(rows, instant(9, 30), instant(11, 30))
        self.assertAlmostEqual(result['vwap'], 61.8)
        self.assertEqual(result['volume'], 1000)
        self.assertEqual(result['last'], 63)
        self.assertAlmostEqual(result['difference_pct'], (63 / 61.8 - 1) * 100)
        self.assertEqual(result['bar_count'], 2)  # Missing minutes are never fabricated.

    def test_invalid_or_missing_values_never_become_prices(self):
        for bad in ({'vw': None}, {'vw': float('nan')}, {'v': 0}, {'v': -1}, {'c': float('inf')}):
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                v.summarize([dict(bar(9, 30), **bad)], instant(9, 30), instant(11, 30))
        self.assertIn('error', v.summarize([], instant(9, 30), instant(11, 30)))
        with self.assertRaises(ValueError):
            v.summarize([bar(9, 30), bar(9, 30)], instant(9, 30), instant(11, 30))

    def test_includes_ibit_excludes_sndl_and_deduplicates_lots(self):
        result = v.build(['FN', 'SNDL', 'IBIT', 'FN'], self.request, instant())
        self.assertEqual([r['symbol'] for r in result['rows']], ['FN', 'IBIT'])
        self.assertEqual(result['cutoff_at'], instant(11, 30).isoformat())

    def test_sip_raw_complete_minutes_requested(self):
        calls = []
        def request(url):
            calls.append(url)
            return self.request(url)
        v.build(['FN'], request, instant().replace(second=59))
        params = parse_qs(urlparse(calls[1]).query)
        self.assertEqual(params['feed'], ['sip'])
        self.assertEqual(params['adjustment'], ['raw'])
        self.assertEqual(params['timeframe'], ['1Min'])
        self.assertEqual(datetime.fromisoformat(params['end'][0]), instant(11, 30) - timedelta(microseconds=1))

    def test_calendar_failure_and_holiday_do_not_fetch_bars(self):
        def fail(url):
            raise OSError('offline')
        self.assertIn('error', v.build(['FN'], fail, instant()))
        calls = []
        def holiday(url):
            calls.append(url)
            return []
        result = v.build(['FN'], holiday, instant())
        self.assertEqual(result['rows'], [])
        self.assertIn('closed', result['message'])
        self.assertEqual(len(calls), 1)

    def test_before_delayed_open_never_carries_yesterday_forward(self):
        result = v.build(['FN'], self.request, instant(9, 40))
        self.assertIn('Waiting', result['message'])
        self.assertEqual(result['rows'], [])

    def test_early_close_excludes_after_hours(self):
        def request(url):
            if '/calendar?' in url:
                return [{"date": '2026-09-14', 'open': '09:30', 'close': '13:00'}]
            return {'bars': {'FN': [bar(12, 59, price=62), bar(13, 0, price=900)]}}
        result = v.build(['FN'], request, instant(17))
        self.assertEqual(result['cutoff_at'], instant(13, 0).isoformat())
        self.assertEqual(result['rows'][0]['vwap'], 62)

    def test_dst_and_calendar_date_validation(self):
        def request(url):
            return [{'date': '2026-01-14', 'open': '09:30', 'close': '16:00'}]
        result = v.build(['FN'], request, instant(9, 40, month=1))
        self.assertTrue(result['session_open'].endswith('-05:00'))
        self.assertIn('error', v.build(['FN'], request, instant()))

    def test_pages_all_count_and_incomplete_pages_are_rejected(self):
        def request(url):
            if '/calendar?' in url: return self.request(url)
            params = parse_qs(urlparse(url).query)
            if 'page_token' in params: return {'bars': {'FN': [bar(11, 29, 900, 62)]}}
            return {'bars': {'FN': [bar(9, 30)]}, 'next_page_token': 'page2'}
        self.assertAlmostEqual(v.build(['FN'], request, instant())['rows'][0]['vwap'], 61.8)
        def repeated(url):
            if '/calendar?' in url: return self.request(url)
            return {'bars': {'FN': [bar(9, 30)]}, 'next_page_token': 'same'}
        self.assertIn('error', v.build(['FN'], repeated, instant())['rows'][0])

    def test_symbol_failure_does_not_hide_healthy_symbol_or_fallback_to_iex(self):
        def request(url):
            if '/bars?' in url and parse_qs(urlparse(url).query)['symbols'] == ['FN']:
                raise OSError('unavailable')
            return self.request(url)
        rows = v.build(['FN', 'IBIT'], request, instant())['rows']
        self.assertIn('error', rows[0])
        self.assertIn('vwap', rows[1])

    def test_cache_expires_and_tracks_session_holdings_and_force(self):
        first = v.get(['FN'], self.request, now=instant())
        self.assertIs(v.get(['FN'], self.request, now=instant()), first)
        self.assertIsNot(v.get(['FN'], self.request, force=True, now=instant()), first)
        self.assertEqual(len(v.get(['FN', 'IBIT'], self.request, now=instant())['rows']), 2)
        v._cached = (v._cached[0], v._cached[1] - 121, v._cached[2])
        self.assertIsNot(v.get(['FN'], self.request, now=instant()), first)
        self.assertIn('error', v.get(['FN'], self.request, now=instant(day=15)))


if __name__ == '__main__':
    unittest.main()
