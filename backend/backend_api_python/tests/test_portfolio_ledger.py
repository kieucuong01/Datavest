from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.services.portfolio.ledger import normalize_event, replay_ledger

NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
def event(kind, **kw):
    return normalize_event(dict(type=kind, effectiveAt='2026-10-01T02:00:00Z', **kw), 'VND', now=NOW)

def test_weighted_cost_partial_sale_dividend():
    rows = [event('deposit', amount='50000'), event('buy', market='VNStock', symbol='FPT', quantity='100', unitPrice='100', fee='100'), event('buy', market='VNStock', symbol='FPT', quantity='100', unitPrice='120', fee='100'), event('sell', market='VNStock', symbol='FPT', quantity='50', unitPrice='130', fee='50', tax='20'), event('dividend', amount='200')]
    for n, row in enumerate(rows): row['sequence'] = n
    state = replay_ledger(rows)
    assert state['positions'][0]['cost'] == '16650'
    assert state['positions'][0]['quantity'] == '150'
    assert state['positions'][0]['averageCost'] == '111'
    assert state['realizedPnl'] == '880'
    assert state['income'] == '200'
    assert state['cash'] == '34430'
    assert len(state['externalFlows']) == 1

@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', '0.0000000000001', '1e40'])
def test_invalid_amount(value):
    with pytest.raises(ValueError): event('deposit', amount=value)

def test_oversell_and_negative_cash_and_future():
    with pytest.raises(ValueError): replay_ledger([event('withdraw', amount='1')])
    with pytest.raises(ValueError): replay_ledger([event('sell', market='VNStock', symbol='FPT', quantity='1', unitPrice='1')])
    with pytest.raises(ValueError): normalize_event(dict(type='deposit', amount='1', effectiveAt='2030-01-01T00:00:00Z'), 'VND', now=NOW)
    with pytest.raises(ValueError): event('buy', market='Crypto', symbol='BTC/USDT', quantity='1', unitPrice='1')

def test_fractional_and_split_basis():
    rows = [normalize_event(dict(type='deposit', amount='10', effectiveAt='2026-10-01T00:00:00Z'), 'USDT', now=NOW), normalize_event(dict(type='buy', quantity='0.0001', unitPrice='10000', market='Crypto', symbol='BTC/USDT', effectiveAt='2026-10-01T00:00:01Z'), 'USDT', now=NOW), normalize_event(dict(type='split', quantity='0.0002', market='Crypto', symbol='BTC/USDT', effectiveAt='2026-10-01T00:00:02Z'), 'USDT', now=NOW)]
    state = replay_ledger(rows)
    assert Decimal(state['positions'][0]['cost']) == 1
    assert Decimal(state['positions'][0]['quantity']) == Decimal('0.0002')
