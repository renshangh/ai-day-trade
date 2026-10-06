"""Offline fixtures for the combined, read-only Schwab portfolio."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'trading_desk'))
import schwab_trade
import schwab_portfolio
import server


def snapshot(label, qty, average, symbol='TEST'):
    return {'ok': True, 'account': label, 'account_type': 'CASH', 'as_of': '2026-10-06T15:00:00Z',
            'balances': {'liquidation_value': 1000, 'cash_balance': 0},
            'positions': [{'symbol': symbol, 'asset_type': 'EQUITY', 'quantity': qty,
                           'long_quantity': qty, 'short_quantity': 0, 'average_price': average,
                           'market_value': qty * 20, 'open_profit_loss': 0, 'current_day_profit_loss': 0}]}


def test_shared_symbols_merge_with_weighted_cost_and_account_provenance():
    book = schwab_portfolio.combine([snapshot('***1111', 10, 5), snapshot('***2222', 30, 15)])
    assert book['account_count'] == 2
    assert len(book['positions']) == 1
    row = book['positions'][0]
    assert row['quantity'] == 40 and row['average_price'] == 12.5
    assert row['market_value'] == 800 and row['open_profit_loss'] == 0
    assert [r['account'] for r in row['account_positions']] == ['***1111', '***2222']
    assert book['balances']['cash_balance'] == 0
    assert 'buying_power' not in book['balances']


def test_distinct_and_empty_accounts_remain_in_one_book():
    a, b = snapshot('***1111', 10, 5), snapshot('***2222', 30, 15, 'OTHER')
    assert len(schwab_portfolio.combine([a,b])['positions']) == 2
    b['positions'] = []
    assert schwab_portfolio.combine([a,b])['account_count'] == 2


def test_missing_cost_and_balances_are_not_defaulted():
    a,b = snapshot('***1111',10,5), snapshot('***2222',30,None)
    b['balances']['cash_balance'] = None
    b['positions'][0]['open_profit_loss'] = None
    book = schwab_portfolio.combine([a,b])
    assert book['positions'][0]['average_price'] is None
    assert book['positions'][0]['open_profit_loss'] is None
    assert book['balances']['cash_balance'] is None


def test_long_and_short_accounts_do_not_produce_fictitious_average():
    a,b = snapshot('***1111',10,5), snapshot('***2222',-5,15)
    b['positions'][0].update(long_quantity=0, short_quantity=5)
    row = schwab_portfolio.combine([a,b])['positions'][0]
    assert row['quantity'] == 5 and row['average_price'] is None


def test_failed_account_cannot_be_reported_as_a_complete_combined_book(monkeypatch):
    accounts = [{'accountNumber':'11111111','hashValue':'offline-a'}, {'accountNumber':'22222222','hashValue':'offline-b'}]
    monkeypatch.setattr(schwab_trade,'status',lambda: {'ok':True,'accounts':[{'label':'***1111'},{'label':'***2222'}]})
    monkeypatch.setattr(schwab_trade,'account_numbers',lambda: accounts)
    def load(account):
        if account == accounts[1]: raise schwab_trade.TradeError('offline failure')
        return snapshot('***1111',10,5)
    monkeypatch.setattr(schwab_trade,'_account_positions',load)
    result = schwab_trade.all_positions()
    assert result['ok'] is False and result['positions'] == []
    assert '22222222' not in str(result) and 'offline-b' not in str(result)
    assert server.get_position_review(broker=result)['error']


def test_combined_review_uses_total_quantity_and_suppresses_unscoped_journal_stop(monkeypatch):
    book=schwab_portfolio.combine([snapshot('***1111',10,5),snapshot('***2222',30,15)])
    rows=[{'status':'open','symbol':'TEST','qty':'40','entry_price':'12.5','stop_current':'10'}]
    held,lots,gaps=server.review_holdings(rows,book)
    assert held['TEST']['qty']==40 and held['TEST']['cost']==500
    assert lots['TEST']==[] and gaps
    monkeypatch.setattr(server,'journal_open_rows',lambda:rows)
    monkeypatch.setattr(server,'_symbol_groups',lambda:{})
    monkeypatch.setattr(server.earnings,'load_event_file',lambda:{})
    monkeypatch.setattr(server,'review_news',lambda *args,**kwargs:[])
    monkeypatch.setattr(server,'cycle_status',lambda:{})
    monkeypatch.setattr(server,'get_stock',lambda *args,**kwargs:{'bars':[{'t':'2026-10-05','c':19},{'t':'2026-10-06','c':20}],'indicators':{},'levels':[]})
    review=server.build_position_review(broker=book)
    assert review['account_count']==2 and len(review['positions'])==1
    assert review['totals']['market_value']==800 and review['totals']['cost']==500
    assert review['positions'][0]['account_positions'][1]['quantity']==30


def test_selecting_one_account_and_trade_account_resolution_remain_explicit():
    assert schwab_trade.build_parser().parse_args(['positions','--all-accounts']).all_accounts
    with pytest.raises(SystemExit):
        schwab_trade.build_parser().parse_args(['positions','--all-accounts','--account-last4','1111'])


def test_failed_read_without_combined_metadata_does_not_reuse_cached_journal(monkeypatch):
    monkeypatch.setitem(server._cache, 'review', {'positions':[{'symbol':'OLD'}]})
    result = server.get_position_review(broker={'ok':False,'error':'connection failed'})
    assert result['positions'] == [] and result['error']
