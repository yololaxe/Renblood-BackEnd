"""Domain tests and opt-in transactions on an isolated, disposable Mongo database."""
import os, unittest, uuid
from concurrent.futures import ThreadPoolExecutor
from .domain import money, legacy_money, EconomyError, MAX_MONEY

class MoneyTests(unittest.TestCase):
    def test_exact_int64(self): self.assertEqual(money(str(MAX_MONEY)),MAX_MONEY)
    def test_reject_lossy_values(self):
        for value in [1,1.5,True,'01','-1','1.1','1e2','0',str(MAX_MONEY+1)]:
            with self.assertRaises(EconomyError): money(value)
    def test_large_legacy_float_is_not_trusted(self):
        with self.assertRaises(EconomyError): legacy_money(float(2**53+2))

    def test_no_silent_rounding(self):
        self.assertEqual(legacy_money(64.0),64)
        for value in ['NaN',1.5,-1,True]:
            with self.assertRaises(EconomyError): legacy_money(value)

@unittest.skipUnless(os.getenv('ECONOMY_TEST_URI'),'Set ECONOMY_TEST_URI for isolated Mongo integration tests.')
class BankIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        from .store import Bank
        cls.client=MongoClient(os.environ['ECONOMY_TEST_URI'],serverSelectionTimeoutMS=3000)
        cls.name='rb_econ_test_'+uuid.uuid4().hex[:16]
        cls.bank=Bank(cls.client[cls.name]);cls.bank.initialize()
    @classmethod
    def tearDownClass(cls):
        # Only this class's randomly generated isolated database can be removed.
        assert cls.name.startswith('rb_econ_test_') and len(cls.name)==29
        cls.client.drop_database(cls.name);cls.client.close()
    def setUp(self):
        self.owner=uuid.uuid4().hex;self.actor='minecraft:'+self.owner
        self.bank.db.players.insert_one({'id':self.owner,'id_minecraft':str(uuid.uuid4()),'money':100.0})
        self.bank.migrate(self.owner,True)
    def prepare(self,key,kind='WITHDRAW',amount='60'):
        return self.bank.prepare(self.owner,self.actor,key,kind,amount)
    def test_public_receipt_matches_wire_schema(self):
        import json
        from pathlib import Path
        from jsonschema import validate, FormatChecker
        from .domain import public
        schema=json.loads((Path(__file__).resolve().parents[2]/'docs/economie/etape-2/contracts/bank-receipt-v1.schema.json').read_text(encoding='utf-8'))
        op=self.prepare('wire')
        validate(public(op),schema,format_checker=FormatChecker())
        receipt=self.bank.transition(op['_id'],self.actor,'delivery',0,'saved-wire')
        validate(public(receipt),schema,format_checker=FormatChecker())

    def test_retry_and_delivery_are_once(self):
        op=self.prepare('same');self.assertEqual(self.prepare('same')['_id'],op['_id'])
        self.bank.transition(op['_id'],self.actor,'delivery',0,'saved:1')
        self.bank.transition(op['_id'],self.actor,'delivery',0,'saved:1')
        account=self.bank.account(self.owner)
        self.assertEqual((account['available'],account['reserved']),(40,0))
        self.assertEqual(self.bank.db.players.find_one({'id':self.owner})['money'],40)
    def test_conflicting_payload_rejected(self):
        self.prepare('same')
        with self.assertRaises(EconomyError):self.prepare('same',amount='10')
    def test_concurrent_withdrawals_cannot_overdraw(self):
        def call(key):
            try:self.prepare(key);return True
            except EconomyError:return False
        with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(call,['a','b']))
        self.assertEqual(sum(result),1)
        self.assertEqual(self.bank.account(self.owner)['reserved'],60)
    def test_cancel_releases_and_cannot_confirm(self):
        op=self.prepare('cancel');self.bank.transition(op['_id'],self.actor,'cancel',0,'not-delivered')
        with self.assertRaises(EconomyError):self.bank.transition(op['_id'],self.actor,'delivery',1,'saved')
        self.assertEqual(self.bank.account(self.owner)['available'],100)
    def test_deposit_needs_delivery(self):
        op=self.prepare('deposit','DEPOSIT','25')
        self.assertEqual(self.bank.account(self.owner)['available'],100)
        self.bank.transition(op['_id'],self.actor,'delivery',0,'removed:25')
        self.assertEqual(self.bank.account(self.owner)['available'],125)
    def test_uncertain_operation_stays_reserved(self):
        op=self.prepare('uncertain');self.bank.transition(op['_id'],self.actor,'reconcile',0,'ambiguous')
        self.assertEqual(self.bank.account(self.owner)['reserved'],60)
        with self.assertRaises(EconomyError):self.bank.transition(op['_id'],self.actor,'delivery',1,'retry')
    def test_migration_repeat_does_not_reset(self):
        self.prepare('spent');self.bank.migrate(self.owner,True)
        self.assertEqual(self.bank.account(self.owner)['available'],40)
    def test_compensation_cannot_double_refund_across_admins(self):
        op=self.bank.prepare(self.owner,self.actor,'grant','CREDIT','20','Quest reward')
        first=self.bank.compensate(op['_id'],'admin:a','first','Correction')
        second=self.bank.compensate(op['_id'],'admin:b','second','Correction')
        self.assertEqual(first['_id'],second['_id'])
        self.assertEqual(self.bank.account(self.owner)['available'],100)
    def test_admin_resolves_without_repeating_inventory_step(self):
        op=self.prepare('review')
        self.bank.transition(op['_id'],self.actor,'reconcile',0,'ambiguous')
        self.bank.transition(op['_id'],self.actor,'cancel',1,'Inventory checked: no delivery',reviewer='admin:a')
        self.assertEqual(self.bank.account(self.owner)['available'],100)
        self.assertEqual(self.bank.operations.find_one({'_id':op['_id']})['reviewed_by'],'admin:a')
    def test_overflow_is_rejected_before_inventory_removal(self):
        self.bank.accounts.update_one({'_id':'bank:'+self.owner},{'$set':{'available':MAX_MONEY}})
        with self.assertRaises(EconomyError):self.prepare('overflow','DEPOSIT','1')
        self.assertIsNone(self.bank.operations.find_one({'actor_id':self.actor,'key':'overflow'}))
        self.assertEqual(self.bank.account(self.owner)['available'],MAX_MONEY)
    def test_incoming_deposits_reserve_capacity_not_spendable_funds(self):
        self.bank.accounts.update_one({'_id':'bank:'+self.owner},{'$set':{'available':MAX_MONEY-1}})
        op=self.prepare('incoming','DEPOSIT','1')
        with self.assertRaises(EconomyError):self.prepare('other-incoming','DEPOSIT','1')
        self.assertEqual(self.bank.account(self.owner)['available'],MAX_MONEY-1)
        self.bank.transition(op['_id'],self.actor,'cancel',0,'not removed')
        self.assertEqual(self.bank.account(self.owner)['incoming'],0)
        self.prepare('retry-incoming','DEPOSIT','1')

    def test_dry_run_is_read_only(self):
        owner=uuid.uuid4().hex;self.bank.db.players.insert_one({'id':owner,'id_minecraft':str(uuid.uuid4()),'money':5.0})
        self.assertEqual(self.bank.migrate(owner)['status'],'ready')
        self.assertIsNone(self.bank.accounts.find_one({'_id':'bank:'+owner}))

    def test_fractional_migration_does_not_write(self):
        owner=uuid.uuid4().hex;self.bank.db.players.insert_one({'id':owner,'id_minecraft':str(uuid.uuid4()),'money':1.5})
        with self.assertRaises(EconomyError):self.bank.migrate(owner,True)
        self.assertIsNone(self.bank.accounts.find_one({'_id':'bank:'+owner}))

if __name__=='__main__':unittest.main()
