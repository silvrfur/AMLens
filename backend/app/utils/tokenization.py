import hashlib
import hmac
import os

def account_token(bank: str, account: str) -> str:
    secret = os.getenv('TOKEN_SECRET')
    if not secret or len(secret) < 32:
        raise RuntimeError('Set TOKEN_SECRET to at least 32 random characters')
    # Length-prefixed encoding prevents concatenation ambiguity.
    payload = f'{len(str(bank))}:{bank}{len(str(account))}:{account}'.encode('utf-8')
    return 'ACC_' + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()[:24]
