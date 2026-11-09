from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import unittest
from uuid import uuid4

from pymongo import MongoClient

from .audit import reconcile
from .desk import Desk
from .npc_budget import ACTOR, TREASURY, prepare_cashboxes, replenish
from .store import Bank


@unittest.skipUnless(os.getenv('ECONOMY_TEST_URI'), 'Isolated Mongo required')
class DailyNpcBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MongoClient(os.environ['ECONOMY_TEST_URI'], serverSelectionTimeoutMS=5000)
        cls.name = 'rb_econ_test_' + uuid4().hex[:16]
        cls.bank = Bank(cls.client[cls.name])
        cls.bank.initialize()

    @classmethod
    def tearDownClass(cls):
        assert cls.name.startswith('rb_econ_test_') and len(cls.name) == 29
        cls.client.drop_database(cls.name)
        cls.client.close()

    def setUp(self):
        for collection in ('players', 'economy_accounts', 'economy_operations', 'economy_businesses'):
            self.bank.db[collection].delete_many({})
        self.day = datetime(2026, 11, 5, 7, tzinfo=timezone.utc)
        self.target = 'npc-contracts'
        self.bank.db.players.insert_one({'id': 'admin', 'id_minecraft': str(uuid4()), 'money': 1000})
        self.bank.migrate('admin', apply=True)
        prepare_cashboxes(self.bank, [self.target])
        Desk(self.bank).fund('admin', 'web:admin', TREASURY, 'fixture-fund', '100', 'Test treasury')

    def available(self, business):
        return self.bank.accounts.find_one({'_id': 'cashbox:' + business})['available']

    def run_budget(self, floor=80, cap=60, day=None, apply=True):
        return replenish(self.bank, self.target, floor, cap, now=day or self.day, apply=apply)

    def test_preview_and_daily_receipt_conserve_money(self):
        self.assertEqual(self.run_budget(apply=False)['state'], 'PREVIEW')
        self.assertEqual(self.available(self.target), 0)
        self.assertEqual(self.bank.operations.count_documents({'actor_id': ACTOR}), 0)
        transfer = self.run_budget()
        self.assertEqual(transfer['amount'], '60')
        self.assertEqual(self.run_budget()['operation_id'], transfer['operation_id'])
        self.assertEqual(self.available(TREASURY), 40)
        self.assertEqual(self.available(self.target), 60)
        audit = reconcile(self.bank.db)
        self.assertEqual(audit['total_bank_and_cashboxes'], '1000')
        self.assertEqual(audit['anomalies'], [])

    def test_next_day_only_fills_difference_and_keeps_surplus(self):
        self.run_budget()
        next_day = self.day + timedelta(days=1)
        self.assertEqual(self.run_budget(day=next_day)['amount'], '20')
        self.assertEqual(self.run_budget(floor=50, day=next_day + timedelta(days=1))['state'], 'ENOUGH_FUNDS')
        self.assertEqual(self.available(self.target), 80)

    def test_concurrent_workers_cannot_fund_twice(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.run_budget(), range(2)))
        self.assertEqual({result['state'] for result in results}, {'FUNDED', 'ALREADY_FUNDED'})
        self.assertEqual(self.available(self.target), 60)
        self.assertEqual(self.bank.operations.count_documents({'actor_id': ACTOR}), 1)

    def test_partial_funding_empty_treasury_and_suspension(self):
        self.assertEqual(self.run_budget(floor=200, cap=200)['amount'], '100')
        self.assertEqual(self.run_budget(floor=200, day=self.day + timedelta(days=1))['state'], 'TREASURY_EMPTY')
        self.bank.db.economy_businesses.update_one({'_id': self.target}, {'$set': {'active': False}})
        self.assertEqual(self.run_budget(day=self.day + timedelta(days=2))['state'], 'SUSPENDED')
        self.assertEqual(self.available(self.target), 100)
