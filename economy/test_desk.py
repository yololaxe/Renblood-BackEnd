import os,unittest,uuid
from datetime import datetime,timezone,timedelta
from .domain import EconomyError
from .store import Bank
from .commerce import Commerce
from .desk import Desk,page_operations

@unittest.skipUnless(os.getenv('ECONOMY_TEST_URI'),'Isolated Mongo required')
class DeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        cls.client=MongoClient(os.environ['ECONOMY_TEST_URI'],serverSelectionTimeoutMS=3000)
        cls.name='rb_econ_test_'+uuid.uuid4().hex[:16];cls.bank=Bank(cls.client[cls.name]);cls.bank.initialize()
    @classmethod
    def tearDownClass(cls):
        assert cls.name.startswith('rb_econ_test_') and len(cls.name)==29
        cls.client.drop_database(cls.name);cls.client.close()
    def setUp(self):
        self.owner=uuid.uuid4().hex;self.actor='web:'+self.owner;self.business=uuid.uuid4().hex
        self.bank.db.players.insert_one({'id':self.owner,'id_minecraft':str(uuid.uuid4()),'money':100})
        self.bank.migrate(self.owner,True);self.desk=Desk(self.bank);self.commerce=Commerce(self.bank)
        self.commerce.register(self.business,self.owner,'Auberge '+self.business,'INN')
    def schedule(self):
        return self.desk.schedule(self.business,self.actor,'plan',{'expected_rule_version':'commerce-v1','rule_version':'pilot-v2',
            'tax_bps':0,'reason':'Pilote sans taxe','effective_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
    def test_suspension_is_reversible_and_replay_is_safe(self):
        row=self.desk.suspend(self.business,self.actor,'close',0,False,'Révision du commerce')
        same=self.desk.suspend(self.business,self.actor,'close',0,False,'Révision du commerce')
        self.assertEqual(row['revision'],same['revision'])
        with self.assertRaises(EconomyError):self.commerce.business(self.business)
        self.desk.suspend(self.business,self.actor,'open',1,True,'Réouverture')
        self.assertTrue(self.commerce.business(self.business)['active'])
    def test_publisher_is_unavailable_without_a_recent_heartbeat(self):
        self.bank.db.economy_services.delete_one({'_id':'policy-publisher'})
        self.assertFalse(self.desk.overview()['publisher_ready'])
        self.bank.db.economy_services.insert_one({'_id':'policy-publisher','last_seen':(datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat()})
        self.assertFalse(self.desk.overview()['publisher_ready'])
    def test_recent_publisher_heartbeat_is_visible_to_admin(self):
        self.bank.db.economy_services.update_one({'_id':'policy-publisher'},{'$set':{'last_seen':datetime.now(timezone.utc).isoformat()}},upsert=True)
        self.assertTrue(self.desk.overview()['publisher_ready'])
    def test_stale_suspension_cannot_overwrite_another_operator(self):
        self.desk.suspend(self.business,self.actor,'close',0,False,'Vérification')
        with self.assertRaises(EconomyError):self.desk.suspend(self.business,self.actor,'open',0,True,'Vue périmée')
    def test_schedule_does_not_publish_early_and_publishes_once(self):
        row=self.schedule();self.assertEqual(self.commerce.business(self.business)['rule_version'],'commerce-v1')
        self.assertEqual(self.desk.publish_due(),[])
        results=self.desk.publish_due(datetime.now(timezone.utc)+timedelta(hours=2))
        self.assertIn({'schedule_id':row['_id'],'state':'PUBLISHED'},results)
        self.assertEqual(self.commerce.business(self.business)['rule_version'],'pilot-v2')
        self.assertEqual(self.desk.publish_due(datetime.now(timezone.utc)+timedelta(hours=2)),[])
    def test_changed_rules_block_scheduled_overwrite(self):
        row=self.schedule();self.commerce.policy(self.business,self.actor,'commerce-v1','manual-v3',0,None)
        self.desk.publish_due(datetime.now(timezone.utc)+timedelta(hours=2))
        self.assertEqual(self.bank.db.economy_policy_schedule.find_one({'_id':row['_id']})['state'],'CONFLICT')
        self.assertEqual(self.commerce.business(self.business)['rule_version'],'manual-v3')
    def test_cancelled_schedule_never_publishes(self):
        row=self.schedule();self.desk.cancel_schedule(row['_id'],self.actor)
        self.desk.publish_due(datetime.now(timezone.utc)+timedelta(hours=2))
        self.assertEqual(self.commerce.business(self.business)['rule_version'],'commerce-v1')
    def test_schedules_require_a_real_timezone_and_valid_rule(self):
        for effective,rate in [('2026-11-04T12:00',0),((datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),0),((datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),0.5)]:
            with self.assertRaises(EconomyError):self.desk.schedule(self.business,self.actor,uuid.uuid4().hex,{'effective_at':effective,'tax_bps':rate,'rule_version':'v2','expected_rule_version':'commerce-v1','reason':'Test'})
    def test_bank_funding_is_conservative_and_once(self):
        row=self.desk.fund(self.owner,self.actor,self.business,'fund','40','Budget du pilote')
        self.desk.fund(self.owner,self.actor,self.business,'fund','40','Budget du pilote')
        self.assertEqual(row['state'],'CONFIRMED');self.assertEqual(self.bank.account(self.owner)['available'],60)
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+self.business})['available'],40)
        with self.assertRaises(EconomyError):self.desk.fund(self.owner,self.actor,self.business,'fund','30','Budget du pilote')
    def test_page_is_bounded_and_does_not_expose_item_nbt(self):
        for i in range(65):
            key=str(uuid.uuid4());self.bank.operations.insert_one({'_id':key,'operation_id':key,'actor_id':self.actor,'owner_id':self.owner,'key':key,
                'state':'CONFIRMED','type':'COMMERCE','business_id':self.business,'created_at':'2026-11-04T12:00:00+00:00','amount':i,'item_nbt':'private-item'})
        page=page_operations(self.bank,{'business_id':self.business})
        self.assertEqual(len(page['operations']),50);self.assertTrue(page['has_more'])
        self.assertNotIn('item_nbt',page['operations'][0])
        next_page=page_operations(self.bank,{'business_id':self.business,'before':page['next_cursor']})
        self.assertEqual(len(next_page['operations']),15)
        self.assertFalse(set(r['operation_id'] for r in page['operations'])&set(r['operation_id'] for r in next_page['operations']))
    def test_cursor_cannot_escape_scope(self):
        other=self.bank.operations.find_one({'owner_id':self.owner})
        with self.assertRaises(EconomyError):page_operations(self.bank,{'before':other['_id']},{'owner_id':'someone-else'})
    def test_business_search_has_an_explicit_prefix(self):
        page=self.desk.businesses({'q':'Auberge '+self.business})
        self.assertEqual(len(page['businesses']),1);self.assertEqual(page['businesses'][0]['business_id'],self.business)
