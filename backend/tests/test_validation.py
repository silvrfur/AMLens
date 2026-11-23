import pandas as pd
from app.services.validation import validate_frame
from app.utils.tokenization import account_token

def test_validation_and_bad_amount():
    row = {'Timestamp':'2022-09-01 12:00:00','From Bank':'001','Account':'A',
           'To Bank':'002','Account.1':'B','Amount Received':'100',
           'Receiving Currency':'US Dollar','Amount Paid':'-100',
           'Payment Currency':'US Dollar','Payment Format':'ACH',
           'Is Laundering':'0','_source_row':2}
    valid, bad = validate_frame(pd.DataFrame([row]))
    assert not valid
    assert 'invalid_amount:Amount Paid' in bad[0]['reasons']

def test_account_token_is_stable_and_bank_scoped(monkeypatch):
    monkeypatch.setenv('TOKEN_SECRET','x'*40)
    assert account_token('001','A') == account_token('001','A')
    assert account_token('001','A') != account_token('002','A')
