import os, unittest, uuid
from concurrent.futures import ThreadPoolExecutor
from .store import Bank
from .commerce import Commerce
from .merchant import Merchant, quota, epoch
from .domain import EconomyError

@unittest.skipUnless(os.environ.get('ECONOMY_TEST_URI'),'Disposable transaction database required')
class MerchantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        cls.client=MongoClient(os.environ['ECONOMY_TEST_URI'],serverSelectionTimeoutMS=5000)
        cls.database='rb_merchant_test_'+uuid.uuid4().hex[:16]
        cls.bank=Bank(cls.client[cls.database]);cls.bank.initialize()
    @classmethod
    def tearDownClass(cls):
        assert cls.database.startswith('rb_merchant_test_') and len(cls.database)==33
        cls.client.drop_database(cls.database);cls.client.close()
    def setUp(self):
        for collection in self.bank.db.list_collection_names():self.bank.db[collection].delete_many({})
        self.owner='player';self.mc=str(uuid.uuid4());self.actor='minecraft:'+self.mc
        self.bank.db.players.insert_one({'id':self.owner,'id_minecraft':self.mc,'money':1000,'experiences':{'jobs':{'merchant':{'xp':0}}}})
        self.bank.migrate(self.owner,True)
        for n,name in enumerate(['Shaleton','Triomphe','Lone','Isvanore','Fyvelune']):
            self.bank.db.market_cities.insert_one({'id':str(n),'name':name,'active':True})
        self.service=Merchant(self.bank);self.commerce=Commerce(self.bank)
        c=self.service.defaults();c['enabled']=True
        for city in c['cities']:city['anchor']={'world':'minecraft:overworld','x':int(city['id'])*500,'z':0,'radius':32}
        for offer in c['offers']:offer['manual_price']='10'
        self.service.save(c,'web:admin')
    def quote(self, city='1', item='minecraft:bread'):
        c=self.service.config();o=next(o for o in c['offers'] if o['city_id']==city and o['item_id']==item)
        return self.service.quote(c,o,self.owner)
    def accept(self, quantity=16,city='1',key=None,quote=None):
        q=quote or self.quote(city)
        return self.service.accept(self.owner,key or str(uuid.uuid4()),{'city_id':city,'item_id':'minecraft:bread','quantity':quantity,'price_version':q['price_version']})
    def claim(self, contract,key=None):
        d=self.service.delivery(self.owner,contract['id']);body=d['request'].copy()
        key=key or body['idempotency_key'];body['idempotency_key']=key
        return self.commerce.prepare(self.owner,self.actor,key,body)
    def finish(self,op,action='delivery',proof=None):
        return self.commerce.transition(op['_id'],self.actor,action,op['revision'],proof or str(uuid.uuid4()))
    def purchase(self,qty=16,key=None):
        q=self.quote('0');key=key or str(uuid.uuid4())
        body={'business_id':q['business_id'],'offer_id':q['item_id'],'item_id':q['item_id'],'item_display_name':q['name'],
            'price_version':q['price_version'],'action':'BUY','unit_price':q['buy_price'],'quantity':qty,'payment':'CASH','idempotency_key':key}
        return self.commerce.prepare(self.owner,self.actor,key,body)
    def test_reserved_budget_and_demand_without_physical_payment(self):
        c=self.accept();self.assertEqual(c['state'],'ACCEPTED')
        self.assertEqual(self.bank.operations.count_documents({'state':'RESERVED'}),1)
        self.assertEqual(self.quote()['demand'],112)
        self.assertEqual(self.bank.db.merchant_ledger.count_documents({}),0)
    def test_last_shared_demand_concurrency(self):
        q=self.quote()
        def accept(_):
            try:return self.accept(100,quote=q)
            except EconomyError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(accept,range(2)))
        self.assertEqual(sum(r is not None for r in rows),1)
    def test_accept_replay_freezes_terms_and_limits_funds_once(self):
        key=str(uuid.uuid4());q=self.quote();first=self.accept(key=key,quote=q)
        self.assertEqual(self.accept(key=key,quote=q),first)
        self.assertEqual(self.quote()['demand'],112)
        with self.assertRaises(EconomyError):self.accept(24,key=key,quote=q)
    def test_accept_limit_under_concurrency(self):
        def accept(city):
            try:return self.accept(city=city)
            except EconomyError:return None
        with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(accept,['1','2','3']))
        self.assertEqual(sum(r is not None for r in rows),2)
    def test_cancel_releases_quota_and_funds_once(self):
        c=self.accept();self.service.cancel(self.owner,c['id']);self.service.cancel(self.owner,c['id'])
        self.assertEqual(self.quote()['demand'],128)
        self.assertEqual(self.bank.operations.find_one({'type':'COMMERCE'})['state'],'CANCELLED')
    def test_web_cancel_cannot_cross_physical_delivery(self):
        c=self.accept();op=self.claim(c)
        with self.assertRaises(EconomyError):self.service.cancel(self.owner,c['id'])
        self.finish(op);self.assertEqual(self.bank.db.merchant_contracts.find_one({})['state'],'DELIVERED')
    def test_failed_inventory_keeps_contract_retryable(self):
        c=self.accept();op=self.claim(c);self.finish(op,'cancel')
        self.assertEqual(self.bank.db.merchant_contracts.find_one({})['state'],'ACCEPTED')
        retry=self.claim(c,str(uuid.uuid4()));self.finish(retry)
        self.assertEqual(self.bank.db.merchant_contracts.find_one({})['state'],'DELIVERED')
        self.assertEqual(self.bank.db.merchant_ledger.count_documents({}),1)
    def test_ambiguous_delivery_never_expires(self):
        c=self.accept();self.finish(self.claim(c),'reconcile')
        self.bank.db.merchant_contracts.update_one({'id':c['id']},{'$set':{'expires_at':0}})
        self.service.expire()
        self.assertEqual(self.bank.db.merchant_contracts.find_one({})['state'],'RECONCILIATION_REQUIRED')
    def test_expiration_on_other_player_refresh(self):
        c=self.accept();self.bank.db.merchant_contracts.update_one({'id':c['id']},{'$set':{'expires_at':0}})
        self.service.notebook('someone-else')
        self.assertEqual(self.bank.db.merchant_contracts.find_one({})['state'],'EXPIRED')
        self.assertEqual(self.quote()['demand'],128)
    def test_fixed_price_after_configuration_change(self):
        c=self.accept();config=self.service.config()
        for o in config['offers']:o['manual_price']='20'
        self.service.save(config,'web:admin')
        op=self.claim(c);self.assertEqual(op['amount'],c['quantity']*int(c['unit_price']))
        self.finish(op)
    def test_foreign_owner_and_modified_terms_rejected(self):
        c=self.accept()
        with self.assertRaises(EconomyError):self.service.cancel('other',c['id'])
        d=self.service.delivery(self.owner,c['id']);body=d['request'];body['quantity']=1
        with self.assertRaises(EconomyError):self.commerce.prepare(self.owner,self.actor,d['key'],body)
    def test_wholesale_stock_cancellation_and_replay(self):
        op=self.purchase();self.assertEqual(self.quote('0')['stock'],240)
        self.finish(op,'cancel');self.assertEqual(self.quote('0')['stock'],256)
    def test_receipt_recovery_after_reference_removed(self):
        op=self.purchase();self.finish(op)
        config=self.service.config();config['enabled']=False;self.service.save(config,'web:admin')
        # A confirmed receipt must remain recoverable even if today's offers are disabled.
        self.assertEqual(self.bank.operations.find_one({'_id':op['_id']})['state'],'CONFIRMED')
    def test_profit_uses_confirmed_purchase_cost(self):
        self.finish(self.purchase());c=self.accept();op=self.claim(c);proof=str(uuid.uuid4())
        self.finish(op,proof=proof);self.commerce.transition(op['_id'],self.actor,'delivery',0,proof)
        sale=self.bank.db.merchant_ledger.find_one({'action':'SELL'})
        self.assertEqual(sale['cost'],128);self.assertEqual(sale['profit'],48)
        self.assertEqual(self.service.profile(self.owner)['xp'],2)
        self.assertEqual(self.bank.db.players.find_one({'id':self.owner})['experiences']['jobs']['merchant']['xp'],2)
    def test_external_goods_do_not_claim_zero_cost(self):
        self.finish(self.claim(self.accept()))
        row=self.bank.db.merchant_ledger.find_one({});self.assertIsNone(row['cost']);self.assertIsNone(row['profit'])
    def test_no_same_city_wholesale_contract_loop(self):
        with self.assertRaises(EconomyError):self.accept(city='0')
    def test_finite_budget_is_preserved_and_refuses_unfunded_contract(self):
        config=self.service.config();config['budget_unlimited']=False;self.service.save(config,'web:admin')
        with self.assertRaises(EconomyError) as caught:self.accept()
        self.assertEqual(caught.exception.code,'INSUFFICIENT_FUNDS');self.assertEqual(self.quote()['demand'],128)
    def test_unpriced_references_stay_disabled(self):
        config=self.service.config()
        for o in config['offers']:o['manual_price']=None
        self.service.save(config,'web:admin')
        self.assertTrue(self.quote()['price_required'])
        with self.assertRaises(EconomyError):self.accept()
    def test_activation_requires_points_and_valid_revision(self):
        config=self.service.config();config['cities'][0]['anchor']=None
        with self.assertRaises(EconomyError):self.service.save(config,'web:admin')
        config=self.service.config();config['revision']=0
        with self.assertRaises(EconomyError):self.service.save(config,'web:admin')
    def test_refill_real_seconds_preserves_fraction_and_held_capacity(self):
        r=quota({'available':2,'held':6,'refilled_at':100},10,30,145)
        self.assertEqual(r['available'],3);self.assertEqual(r['refilled_at'],130)
        r=quota(r,10,30,1000);self.assertEqual(r['available'],4)
    def test_branch_cooldown_and_modest_bonus(self):
        self.service.choose(self.owner,'specialty')
        with self.assertRaises(EconomyError):self.service.choose(self.owner,'shop')
        self.bank.db.merchant_profiles.update_one({'_id':self.owner},{'$set':{'xp':500}})
        self.assertEqual(self.service.profile(self.owner)['negotiation_bps'],200)

    def test_store_owner_tracks_net_sales_and_capped_reputation(self):
        self.finish(self.purchase())
        op={'_id':'store-sale','owner_id':'customer','business_owner_id':self.owner,'business_id':'market:store',
            'action':'BUY','quantity':16,'item_id':'minecraft:bread','item_display_name':'Pain','amount':192,'tax':16}
        self.bank.transact(lambda s:self.service.settled(op,'delivery',s))
        row=self.bank.db.merchant_ledger.find_one({'_id':'store-sale:owner'})
        self.assertEqual(row['amount'],176);self.assertEqual(row['cost'],128);self.assertEqual(row['profit'],48)
        self.assertEqual(self.service.profile(self.owner)['xp'],2)

    def test_store_return_to_same_supplier_never_rewards_a_round_trip(self):
        op={'_id':'store-purchase','owner_id':'customer','business_owner_id':self.owner,'business_id':'market:store',
            'action':'SELL','quantity':16,'item_id':'minecraft:bread','item_display_name':'Pain','amount':128,'tax':0}
        self.bank.transact(lambda s:self.service.settled(op,'delivery',s))
        op={**op,'_id':'store-resale','action':'BUY','amount':176}
        self.bank.transact(lambda s:self.service.settled(op,'delivery',s))
        self.assertEqual(self.service.profile(self.owner)['xp'],0)

    def test_splitting_deliveries_cannot_multiply_xp(self):
        self.bank.transact(lambda s:self.service.gain_xp(self.owner,'same-client','minecraft:bread',7,s))
        self.assertEqual(self.service.profile(self.owner)['xp'],0)
        self.bank.transact(lambda s:self.service.gain_xp(self.owner,'same-client','minecraft:bread',1,s))
        self.assertEqual(self.service.profile(self.owner)['xp'],1)
        for _ in range(3):self.bank.transact(lambda s:self.service.gain_xp(self.owner,'same-client','minecraft:bread',256,s))
        self.assertEqual(self.service.profile(self.owner)['xp'],32)

    def test_ordinary_http_user_cannot_configure_or_deliver_inventory(self):
        from django.test import Client
        from unittest.mock import patch
        from types import SimpleNamespace
        player=SimpleNamespace(id=self.owner,rank='Joueur')
        with patch('economy.views._has_server_api_key',return_value=False),patch('economy.views.auth.verify_id_token',return_value={'uid':self.owner}),patch('economy.views.Player',SimpleNamespace(objects=SimpleNamespace(get=lambda **kwargs:player),DoesNotExist=type('MissingPlayer',(Exception,),{}))),patch('economy.merchant_views.get_bank',return_value=self.bank):
            client=Client(HTTP_HOST='localhost',HTTP_AUTHORIZATION='Bearer fixture')
            self.assertEqual(client.get('/api/economy/v1/merchant/config').status_code,403)
            self.assertEqual(client.get('/api/economy/v1/merchant/contracts/anything/delivery').status_code,403)
            response=client.get('/api/economy/v1/merchant/notebook');self.assertEqual(response.status_code,200,response.content.decode())

    def test_notebook_batches_catalogue_queries(self):
        from unittest.mock import patch
        with patch.object(self.service,'profile',wraps=self.service.profile) as profile:
            notebook=self.service.notebook(self.owner)
            self.assertEqual(len(notebook['offers']),50);self.assertEqual(profile.call_count,1)



    def test_job_level_and_reputation_are_updated_atomically(self):
        self.bank.db.players.update_one({'id':self.owner},{'$set':{'experiences.jobs.merchant.xp':19}})
        self.bank.transact(lambda s:self.service.gain_xp(self.owner,'client','minecraft:bread',8,s))
        job=self.bank.db.players.find_one({'id':self.owner})['experiences']['jobs']['merchant']
        self.assertEqual(job['xp'],20);self.assertEqual(job['level'],1)

    def test_unselected_job_is_not_activated_by_basic_trading(self):
        self.bank.db.players.update_one({'id':self.owner},{'$set':{'experiences.jobs.merchant.xp':-1}})
        self.bank.transact(lambda s:self.service.gain_xp(self.owner,'client','minecraft:bread',8,s))
        self.assertEqual(self.bank.db.players.find_one({'id':self.owner})['experiences']['jobs']['merchant']['xp'],-1)
        self.assertEqual(self.service.profile(self.owner)['xp'],1)
