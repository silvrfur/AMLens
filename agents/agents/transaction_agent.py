from decimal import Decimal
from datetime import timedelta
import pandas as pd
from ..schemas.agent_outputs import TransactionAnalysis, Pattern
from ..services.security import mask_account

# Illustrative USD analysis parameter, NOT a legal or regulatory reporting threshold.
DEMO_THRESHOLD = Decimal('10000')

def analyse(transactions) -> TransactionAnalysis:
    ids = [t.transaction_id for t in transactions]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate transaction IDs')
    if len({t.account_token for t in transactions}) > 1: raise ValueError('Mixed account history')
    stats = {'transaction_count': len(ids)}
    patterns = []
    limitations = ['Observed window only; no historical baseline or proof of criminal activity.',
                   'Threshold clustering uses an illustrative USD parameter, not a regulatory threshold.',
                   'Rapid movement is temporal proximity, not traced ownership or flow of funds.']
    def add(key, description, supporting, metric):
        patterns.append(Pattern(pattern_id=key, description=description,
                                transaction_ids=supporting, metric_key=metric))
    if not transactions:
        return TransactionAnalysis(observed_patterns=[], potential_red_flags=[], supporting_transaction_ids=[], computed_statistics=stats, limitations=limitations+['No transactions provided.'])
    df = pd.DataFrame([t.model_dump() for t in transactions])
    df['time'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values(['time','transaction_id'])
    stats['counterparty_count'] = int(df.counterparty_token.nunique())
    for currency, group in df.groupby('currency'):
        deposits = group[group.transaction_type == 'deposit']
        withdrawals = group[group.transaction_type == 'withdrawal']
        stats[f'{currency}.total'] = str(sum(group.amount, Decimal('0.00')))
        stats[f'{currency}.deposits'] = str(sum(deposits.amount, Decimal('0.00')))
        stats[f'{currency}.withdrawals'] = str(sum(withdrawals.amount, Decimal('0.00')))
        stats[f'{currency}.net'] = str(sum(deposits.amount, Decimal('0.00')) - sum(withdrawals.amount, Decimal('0.00')))
        stats[f'{currency}.deposit_count'] = len(deposits)
        stats[f'{currency}.withdrawal_count'] = len(withdrawals)
        stats[f'{currency}.fan_in'] = int(deposits.counterparty_token.nunique())
        stats[f'{currency}.fan_out'] = int(withdrawals.counterparty_token.nunique())
        stats[f'{currency}.threshold_parameter'] = str(DEMO_THRESHOLD) if currency == 'USD' else 'not_applicable'
        times = [t.to_pydatetime() for t in group.time]
        peak = max(sum(start <= t <= start+timedelta(hours=1) for t in times) for start in times)
        stats[f'{currency}.peak_hour_count'] = peak
        add(f'{currency}.activity', f'Observed transaction activity in {currency}.', group.transaction_id.tolist(), f'{currency}.total')
        if peak >= 3:
            add(f'{currency}.velocity', 'Frequent transactions within an inclusive rolling hour.', group.transaction_id.tolist(), f'{currency}.peak_hour_count')
        rounded = group[group.amount.map(lambda a: a % Decimal('1000') == 0)]
        stats[f'{currency}.round_count'] = len(rounded)
        if len(rounded): add(f'{currency}.round', 'Amounts are multiples of a thousand currency units.', rounded.transaction_id.tolist(), f'{currency}.round_count')
        clustered = deposits[deposits.amount.map(lambda a: DEMO_THRESHOLD*Decimal('.9') <= a < DEMO_THRESHOLD)] if currency == 'USD' else deposits.iloc[:0]
        stats[f'{currency}.cluster_count'] = len(clustered)
        if len(clustered) >= 2:
            add(f'{currency}.cluster', 'Repeated deposits below the illustrative analysis threshold.', clustered.transaction_id.tolist(), f'{currency}.cluster_count')
        rapid_ids = set()
        for dep in deposits.itertuples():
            outgoing = withdrawals[(withdrawals.time >= dep.time) & (withdrawals.time <= dep.time.to_pydatetime()+timedelta(hours=1))]
            if len(outgoing): rapid_ids.update([dep.transaction_id, *outgoing.transaction_id.tolist()])
        stats[f'{currency}.rapid_transaction_count'] = len(rapid_ids)
        if rapid_ids: add(f'{currency}.rapid', 'Deposits and withdrawals occur close together in time.', sorted(rapid_ids), f'{currency}.rapid_transaction_count')
        if len(deposits) >= 2 and len(withdrawals) >= 2:
            add(f'{currency}.in_out', 'Multiple deposits and withdrawals in the observed window.', group.transaction_id.tolist(), f'{currency}.deposit_count')
        if stats[f'{currency}.fan_in'] >= 2 and stats[f'{currency}.fan_out'] >= 2:
            add(f'{currency}.fan', 'Multiple incoming and outgoing counterparties.', group.transaction_id.tolist(), f'{currency}.fan_in')
    return TransactionAnalysis(observed_patterns=patterns,
        potential_red_flags=[p.description + ' Requires contextual human review.' for p in patterns if not p.pattern_id.endswith('.activity')],
        supporting_transaction_ids=ids, computed_statistics=stats, limitations=limitations)

class TransactionAgent:
    def __init__(self, backend): self.backend = backend
    def __call__(self, state):
        bundle = self.backend.get_alert_context(state['alert_id'])
        if bundle.alert.alert_id != state['alert_id']: raise ValueError('Backend alert mismatch')
        anchor = next((t for t in bundle.transactions if t.transaction_id == bundle.alert.transaction_id), None)
        if anchor is None: raise ValueError('Alert transaction absent from history')
        return {'alert_context': bundle.alert, 'transactions': bundle.transactions,
                'account_id': mask_account(anchor.account_token), 'transaction_analysis': analyse(bundle.transactions)}
