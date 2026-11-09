"""Read-only aggregate staging readiness. No player identities in the report."""
from collections import Counter
import json
from pathlib import Path
import sys

from dotenv import dotenv_values
from pymongo import MongoClient

HERE = Path(__file__).resolve().parent
BACKEND = Path('D:/Projets/Projet/DEVELOPPEMENT/Renblood-BackEnd')
sys.path.insert(0, str(BACKEND))
from economy.audit import reconcile
from economy.domain import EconomyError
from economy.store import Bank


def main():
    cfg = dotenv_values(BACKEND / '.env.local')
    name = 'renblood_mongo_staging'
    if cfg.get('MONGO_DB_NAME') != name:
        raise SystemExit('Staging database mismatch')
    statuses = Counter()
    blockers = Counter()
    ready = 0
    with MongoClient(cfg['MONGO_URI'], serverSelectionTimeoutMS=5000) as client:
        bank = Bank(client[name])
        bank.check_storage()
        for player in bank.db.players.find({}, {'id': 1}):
            owner = player.get('id')
            if not isinstance(owner, str) or not owner:
                blockers['INVALID_OWNER_ID'] += 1
                continue
            try:
                state = bank.migrate(owner, apply=False)
            except EconomyError as failure:
                blockers[failure.code] += 1
            else:
                statuses[state['status']] += 1
                if state['status'] == 'ready':
                    ready += int(state['balance'])
        audit = reconcile(bank.db)
        report = {'database': name, 'read_only': True, 'statuses': dict(statuses),
                  'blockers': dict(blockers), 'eligible_opening_balance': str(ready),
                  'bank_and_cashbox_v1_total': audit['total_bank_and_cashboxes'],
                  'pending_receipts': len(audit['pending']), 'pending_materials': len(audit['pending_material_rewards']),
                  'ledger_anomalies': len(audit['anomalies']),
                  'legacy_market_counters': bank.db.merchant_counters.count_documents({}),
                  'historical_quests_completed': bank.db.player_quest_states.count_documents({'status': 'COMPLETED'})}
    (HERE / 'staging-preflight.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
