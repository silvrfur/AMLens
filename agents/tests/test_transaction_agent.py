from decimal import Decimal
import pytest
from agents.agents.transaction_agent import analyse

def test_exact_statistics(state):
    stats = state['transaction_analysis'].computed_statistics
    assert stats['USD.total'] == '57400.00'
    assert stats['USD.deposits'] == '29400.00'
    assert stats['USD.withdrawals'] == '28000.00'
    assert stats['USD.net'] == '1400.00'
    assert stats['USD.peak_hour_count'] == 4
    assert stats['USD.cluster_count'] == 3
    assert stats['USD.fan_in'] == 3 and stats['USD.fan_out'] == 2
    assert stats['USD.round_count'] == 2
    assert stats['USD.rapid_transaction_count'] == 5

def test_currency_separation_and_cents(state):
    tx = state['transactions'][0].model_copy(update={'currency':'EUR','amount':Decimal('0.10')})
    tx2 = tx.model_copy(update={'transaction_id':'CENTS','amount':Decimal('0.20')})
    stats = analyse([tx,tx2,state['transactions'][1]]).computed_statistics
    assert stats['EUR.total'] == '0.30'
    assert stats['USD.total'] == '9700.00'
    assert stats['EUR.cluster_count'] == 0

def test_empty():
    result = analyse([])
    assert result.computed_statistics == {'transaction_count':0}
    assert 'No transactions provided.' in result.limitations

def test_duplicate_and_mixed_account_rejected(state):
    tx = state['transactions'][0]
    with pytest.raises(ValueError): analyse([tx,tx])
    with pytest.raises(ValueError): analyse([tx,tx.model_copy(update={'transaction_id':'OTHER','account_token':'other'})])

def test_no_baseline_claim(state):
    assert any('no historical baseline' in x for x in state['transaction_analysis'].limitations)
