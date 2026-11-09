"""Canonical money and protocol errors, independent of Django and Mongo."""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation

MAX_MONEY = 9223372036854775807

class EconomyError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message); self.code=code; self.status=status

def money(value, zero=False):
    if not isinstance(value,str) or not re.fullmatch(r'0|[1-9][0-9]{0,18}',value):
        raise EconomyError('INVALID_AMOUNT','Le montant doit être une chaîne entière en fer.',400)
    amount=int(value)
    if amount>MAX_MONEY or (amount==0 and not zero):
        raise EconomyError('INVALID_AMOUNT','Montant hors limites.',400)
    return amount

def legacy_money(value):
    if isinstance(value,float) and abs(value)>9007199254740991: raise EconomyError('MIGRATION_REQUIRED','Ancien montant flottant trop grand pour une conversion certaine.')
    if isinstance(value,bool): raise EconomyError('MIGRATION_REQUIRED','Solde historique invalide.')
    try: number=Decimal(str(value))
    except InvalidOperation: raise EconomyError('MIGRATION_REQUIRED','Solde historique invalide.')
    if not number.is_finite() or number!=number.to_integral_value() or number<0 or number>MAX_MONEY:
        raise EconomyError('MIGRATION_REQUIRED','Le solde historique nécessite un rapprochement.')
    return int(number)

def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def public(document):
    result={k:v for k,v in document.items() if k not in {'_id','key','request_hash'}}
    if "key" in document: result["idempotency_key"]=document["key"]
    if "pocket" in document and "_id" in document: result["account_id"]=document["_id"]
    for key in ['amount','available','reserved','balance','opening_balance','incoming','tax','refunded_tax','unit_price','buy_price','sell_price','minted_amount']:
        if key in result: result[key]=str(result[key])
    if 'legs' in result: result['legs']=[public(leg) for leg in result['legs']]
    return result
