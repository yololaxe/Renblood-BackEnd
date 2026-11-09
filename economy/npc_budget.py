"""Run the daily NPC cashbox top-up. The default is a read-only preview."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5

from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from .commerce import Commerce, RULE_VERSION
from .domain import MAX_MONEY, fingerprint, money
from .store import Bank, timestamp


TREASURY = 'treasury:npc'
ACTOR = 'system:npc-daily-budget'
TARGETS = {'npc-contracts': 'Contrats des marchands', 'inn-customers': 'Budget des voyageurs'}


def load_rules(path):
    rules = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(rules, dict) or not rules or rules.keys() - TARGETS.keys():
        raise ValueError('Choisissez les enveloppes npc-contracts ou inn-customers.')
    result = {}
    for target, rule in rules.items():
        if not isinstance(rule, dict) or rule.keys() != {'target_available', 'daily_cap'}:
            raise ValueError(f'Règle invalide pour {target}.')
        result[target] = (money(rule['target_available']), money(rule['daily_cap']))
    return result


def prepare_cashboxes(bank, targets):
    commerce = Commerce(bank)
    commerce.register(TREASURY, 'system:' + TREASURY, 'Trésorerie des PNJ', 'MARKET')
    for target in targets:
        commerce.register(target, 'system:' + target, TARGETS[target], 'NPC')


def replenish(bank, target, floor, daily_cap, *, now=None, apply=False):
    if target not in TARGETS or any(type(value) is not int or not 0 < value <= MAX_MONEY
                                    for value in (floor, daily_cap)):
        raise ValueError('Caisse ou plafond invalide.')
    day = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    key = f'{target}:{day}'
    operation_id = str(uuid5(NAMESPACE_URL, f'renblood/economy/npc-budget/{key}'))

    def run(session):
        previous = bank.operations.find_one({'_id': operation_id}, session=session)
        result = {'business_id': target, 'day_utc': day, 'amount': '0'}
        if previous:
            return {**result, 'state': 'ALREADY_FUNDED', 'amount': str(previous['amount']),
                    'operation_id': operation_id}
        business = bank.db.economy_businesses.find_one({'_id': target}, session=session)
        treasury = bank.db.economy_businesses.find_one({'_id': TREASURY}, session=session)
        source = bank.accounts.find_one({'_id': 'cashbox:' + TREASURY}, session=session)
        dest = bank.accounts.find_one({'_id': 'cashbox:' + target}, session=session)
        if not all((business, treasury, source, dest)):
            return {**result, 'state': 'SETUP_REQUIRED'}
        if (business['kind'] != 'NPC' or dest['owner_id'] != 'system:' + target
                or source['owner_id'] != 'system:' + TREASURY
                or source['pocket'] != 'CASHBOX' or dest['pocket'] != 'CASHBOX'):
            return {**result, 'state': 'ACCOUNT_CONFLICT'}
        if business.get('budget_unlimited'):
            return {**result, 'state': 'UNLIMITED'}
        if not business['active'] or not treasury['active']:
            return {**result, 'state': 'SUSPENDED'}
        effective = dest['available'] + dest.get('incoming', 0)
        capacity = MAX_MONEY - effective - dest['reserved']
        desired = min(floor - effective, daily_cap, capacity)
        if desired <= 0:
            return {**result, 'state': 'ENOUGH_FUNDS' if effective >= floor else 'CAPACITY_LIMIT'}
        amount = min(desired, source['available'])
        if amount <= 0:
            return {**result, 'state': 'TREASURY_EMPTY'}
        result['amount'] = str(amount)
        if not apply:
            return {**result, 'state': 'PREVIEW'}

        stamp = timestamp()
        # Purely financial transfer. Both legs and the receipt commit together.
        for account, delta in ((source, -amount), (dest, amount)):
            bank.accounts.update_one({'_id': account['_id']}, {
                '$inc': {'available': delta, 'revision': 1}, '$set': {'updated_at': stamp},
            }, session=session)
        bank.operations.insert_one({
            '_id': operation_id, 'operation_id': operation_id, 'api_version': '1',
            'owner_id': dest['owner_id'], 'actor_id': ACTOR, 'key': key,
            'request_hash': fingerprint({'business': target, 'day_utc': day}),
            'business_id': target, 'business_owner_id': dest['owner_id'],
            'participant_owner_ids': [source['owner_id'], dest['owner_id']],
            'type': 'COMMERCE', 'action': 'FUND', 'state': 'CONFIRMED', 'revision': 0,
            'amount': amount, 'currency': 'IRON', 'payment': 'BANK', 'quantity': 1, 'tax': 0,
            'tax_bps': 0, 'rule_version': RULE_VERSION, 'business_rule_version': business['rule_version'],
            'reason': 'Réapprovisionnement quotidien des PNJ', 'budget_day_utc': day,
            'legs': [{'account_id': source['_id'], 'direction': 'OUT', 'amount': amount},
                     {'account_id': dest['_id'], 'direction': 'IN', 'amount': amount}],
            'proof_id': 'daily-npc-budget:' + day, 'created_at': stamp, 'updated_at': stamp,
        }, session=session)
        return {**result, 'state': 'FUNDED', 'operation_id': operation_id}

    if not apply:
        return run(None)
    try:
        return bank.transact(run)
    except DuplicateKeyError:
        # A concurrent worker may have completed this exact day.
        result = run(None) if bank.operations.find_one({'_id': operation_id}) else None
        if result is None or result['state'] != 'ALREADY_FUNDED':
            raise
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--rules', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--prepare', action='store_true', help='Create the configured empty cashboxes and exit')
    parser.add_argument('--watch', action='store_true', help='Check each minute')
    args = parser.parse_args()
    if (args.prepare or args.watch) and not args.apply or args.prepare and args.watch:
        parser.error('--prepare and --watch each require --apply and are mutually exclusive.')
    config = dotenv_values(args.env_file)
    if config.get('MONGO_DB_NAME') != args.database:
        parser.error('Database mismatch.')
    rules = load_rules(args.rules)
    with MongoClient(config['MONGO_URI'], serverSelectionTimeoutMS=5000) as client:
        bank = Bank(client[args.database])
        if args.apply:
            bank.initialize()
        if args.prepare:
            prepare_cashboxes(bank, rules)
            print('Trésorerie et enveloppes préparées. Financement requis.')
            return
        last = {}
        while True:
            now = datetime.now(timezone.utc)
            for target, (floor, cap) in rules.items():
                result = replenish(bank, target, floor, cap, now=now, apply=args.apply)
                if last.get(target) != result:
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                    last[target] = result
            if not args.watch:
                break
            time.sleep(60)


if __name__ == '__main__':
    main()
