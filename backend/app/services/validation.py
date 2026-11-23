from decimal import Decimal, InvalidOperation
import pandas as pd

REQUIRED = ['Timestamp', 'From Bank', 'Account', 'To Bank', 'Account.1',
            'Amount Received', 'Receiving Currency', 'Amount Paid',
            'Payment Currency', 'Payment Format', 'Is Laundering']

# IBM AML HI-Small categorical values as described in the supplied EDA.
CURRENCIES = {'US Dollar','Euro','Swiss Franc','Yuan','Shekel','Rupee','UK Pound',
              'Yen','Ruble','Bitcoin','Canadian Dollar','Australian Dollar',
              'Mexican Peso','Saudi Riyal','Brazil Real'}
FORMATS = {'Cheque','Credit Card','ACH','Cash','Reinvestment','Wire','Bitcoin'}

def validate_frame(df: pd.DataFrame):
    missing_columns = sorted(set(REQUIRED) - set(df.columns))
    if missing_columns:
        raise ValueError('Missing required CSV columns: ' + ', '.join(missing_columns))
    accepted, rejected = [], []
    for _, r in df.iterrows():
        rownum = int(r['_source_row'])
        reasons = []
        for c in REQUIRED:
            if pd.isna(r[c]) or not str(r[c]).strip():
                reasons.append(f'missing:{c}')
        ts = pd.to_datetime(r['Timestamp'], errors='coerce')
        if pd.isna(ts):
            reasons.append('invalid_timestamp')
        parsed = {}
        for col in ('Amount Paid','Amount Received'):
            try:
                value = Decimal(str(r[col]))
                if not value.is_finite() or value <= 0:
                    reasons.append(f'invalid_amount:{col}')
                parsed[col] = value
            except (InvalidOperation, TypeError, ValueError):
                reasons.append(f'invalid_amount:{col}')
        for col in ('Payment Currency','Receiving Currency'):
            if str(r[col]).strip() not in CURRENCIES:
                reasons.append(f'invalid_currency:{col}')
        if str(r['Payment Format']).strip() not in FORMATS:
            reasons.append('invalid_payment_format')
        if str(r['Is Laundering']).strip() not in ('0','1'):
            reasons.append('invalid_ground_truth_label')
        if reasons:
            rejected.append({'source_row': rownum, 'reasons': sorted(set(reasons))})
        else:
            item = r.to_dict()
            item['_timestamp'] = ts.to_pydatetime()
            item['_amount_paid'] = parsed['Amount Paid']
            item['_amount_received'] = parsed['Amount Received']
            accepted.append(item)
    return accepted, rejected
