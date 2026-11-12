import os, unittest, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from .store import Bank
from .commerce import Commerce
from .npc_services import NpcShops
from .domain import EconomyError, fingerprint


@unittest.skipUnless(os.environ.get('ECONOMY_TEST_URI'), 'Disposable Mongo transaction database required')
class NpcShopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        cls.client=MongoClient(os.environ['ECONOMY_TEST_URI'],serverSelectionTimeoutMS=5000)
        cls.database='rb_npc_test_'+uuid.uuid4().hex[:16]
        cls.bank=Bank(cls.client[cls.database]);cls.bank.initialize()
    @classmethod
    def tearDownClass(cls):
        assert cls.database.startswith('rb_npc_test_') and len(cls.database)==28
        cls.client.drop_database(cls.database);cls.client.close()
    def setUp(self):
        self.id=str(uuid.uuid4());self.owner=uuid.uuid4().hex;self.actor='minecraft:'+self.owner
        self.bank.db.players.insert_one({'id':self.owner,'id_minecraft':str(uuid.uuid4()),'money':100})
        self.bank.migrate(self.owner,True);self.service=NpcShops(self.bank);self.commerce=Commerce(self.bank)
        self.item='test:'+uuid.uuid4().hex
        self.bank.db.market_item_references.insert_one({'item_id':self.item,'reference_price':10,'display_name':'Torche','enabled':True,'min_price':1,'max_price':100})
    def config(self,**changes):
        row={'item_id':self.item,'name':'Torche','nbt':'{id:"minecraft:torch",Count:1b}','automatic':True,'buy_enabled':True,'sell_enabled':False,'buy_price':'10','sell_price':'8','lot':1,'stock':None,'restock_seconds':0,'restock_target':0}
        row.update(changes)
        return {'id':self.id,'name':'Boutique de recette','revision':0,'skin':'textures/entity/banker.png','world':'minecraft:overworld','active':True,'city_id':None,'offers':[row]}
    def save(self,**changes):return self.service.save(self.config(**changes),'web:admin')
    def buy(self,catalogue,quantity=1,action='BUY',key=None):
        row=catalogue['offers'][0]
        return self.service.prepare(self.id,self.owner,self.actor,{'offer_id':row['id'],'action':action,'price_version':row['price_version'],'unit_price':row['buy_price' if action=='BUY' else 'sell_price'],'quantity':quantity,'idempotency_key':key or str(uuid.uuid4())})
    def finish(self,op,action='delivery'):
        return self.commerce.transition(op['_id'],self.actor,action,op['revision'],str(uuid.uuid4()))
    def test_browsing_does_not_move_money_or_record_activity(self):
        from unittest.mock import patch
        self.save();before=self.bank.operations.count_documents({})
        with patch.object(self.bank,'transact',wraps=self.bank.transact) as write:
            self.service.catalogue(self.id);self.service.catalogue(self.id)
            self.assertEqual(write.call_count,0)
        self.assertEqual(self.bank.operations.count_documents({}),before)
        self.assertEqual(self.bank.db.market_transactions.count_documents({'counter_id':self.id}),0)
    def test_permanent_shop_supports_repeated_cash_purchases(self):
        cat=self.save()
        for _ in range(3):self.assertEqual(self.finish(self.buy(cat))['state'],'CONFIRMED')
        self.assertEqual(self.bank.db.market_transactions.count_documents({'counter_id':self.id}),3)
    def test_last_stock_is_reserved_only_once_under_concurrency(self):
        cat=self.save(stock=1)
        def purchase(_):
            try:return self.buy(cat)
            except EconomyError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(purchase,range(2)))
        self.assertEqual(sum(r is not None for r in rows),1)
        self.finish(next(r for r in rows if r),'cancel')
        self.assertEqual(self.service.catalogue(self.id)['offers'][0]['stock'],1)
    def test_cancelled_trade_does_not_feed_market_activity(self):
        cat=self.save();self.finish(self.buy(cat),'cancel')
        self.assertEqual(self.bank.db.market_transactions.count_documents({'counter_id':self.id}),0)
    def test_delivery_replay_does_not_duplicate_activity(self):
        op=self.buy(self.save());proof=str(uuid.uuid4());first=self.commerce.transition(op['_id'],self.actor,'delivery',0,proof)
        self.assertEqual(self.commerce.transition(op['_id'],self.actor,'delivery',0,proof),first)
        self.assertEqual(self.bank.db.market_transactions.count_documents({'counter_id':self.id}),1)
    def test_unknown_city_is_rejected_without_changing_shop(self):
        original=self.save();body=self.config();body.update(revision=original['revision'],city_id='missing')
        with self.assertRaises(EconomyError):self.service.save(body,'web:admin')
        self.assertIsNone(self.service.catalogue(self.id)['city_id'])
    def test_missing_city_quote_suspends_automatic_item(self):
        city=str(uuid.uuid4());self.bank.db.market_cities.insert_one({'id':city,'name':city,'active':True})
        body=self.config();body['city_id']=city;cat=self.service.save(body,'web:admin')
        self.assertFalse(cat['offers'][0]['available']);self.assertEqual(cat['offers'][0]['buy_price'],'0')
    def test_local_price_is_used_and_old_price_refused(self):
        city=str(uuid.uuid4());self.bank.db.market_cities.insert_one({'id':city,'name':city,'active':True})
        self.bank.db.calculated_market_prices.insert_one({'city_id':city,'market_type':'CITY_MARKET','item_id':self.item,'calculated_price':15,'calculation_version':'v1'})
        body=self.config();body['city_id']=city;cat=self.service.save(body,'web:admin');self.assertEqual(cat['offers'][0]['buy_price'],'15')
        self.bank.db.calculated_market_prices.update_one({'city_id':city},{'$set':{'calculated_price':18}})
        with self.assertRaises(EconomyError) as caught:self.buy(cat)
        self.assertEqual(caught.exception.code,'PRICE_CHANGED')
    def test_manual_prices_ignore_market_changes(self):
        cat=self.save(automatic=False,buy_price='25',sell_price='20');self.assertEqual(cat['offers'][0]['buy_price'],'25')
    def test_inverted_manual_prices_are_rejected(self):
        with self.assertRaises(EconomyError):self.save(automatic=False,sell_enabled=True,buy_price='5',sell_price='6')
    def test_stale_admin_version_cannot_overwrite_newer_shop(self):
        self.save()
        with self.assertRaises(EconomyError) as caught:self.save()
        self.assertEqual(caught.exception.code,'VERSION_CONFLICT')
    def test_pending_delivery_blocks_configuration_changes(self):
        cat=self.save();self.buy(cat);cat['name']='Changed'
        with self.assertRaises(EconomyError) as caught:self.service.save(cat,'web:admin')
        self.assertEqual(caught.exception.code,'EXCHANGE_PENDING')
    def test_restock_respects_target_and_reserved_items(self):
        cat=self.save(stock=2,restock_seconds=60,restock_target=5);op=self.buy(cat)
        sid=fingerprint({'business':'npcshop:'+self.id,'offer':cat['offers'][0]['id']})
        self.bank.db.economy_offers.update_one({'_id':sid},{'$set':{'restocked_at':(datetime.now(timezone.utc)-timedelta(seconds=61)).isoformat()}})
        self.assertEqual(self.service.catalogue(self.id)['offers'][0]['stock'],4)
        self.finish(op,'cancel');self.assertEqual(self.service.catalogue(self.id)['offers'][0]['stock'],5)
    def test_closed_shop_refuses_a_previously_open_catalogue(self):
        cat=self.save();body=dict(cat,active=False);self.service.save(body,'web:admin')
        with self.assertRaises(EconomyError):self.buy(cat)
    def test_cash_travel_refund_is_bound_to_original_owner_and_not_repeated(self):
        business='passage:'+self.id;self.commerce.register(business,'system:'+business,'Traversée','NPC');self.commerce.offer(business,'ticket','v1','10','0')
        body={'business_id':business,'offer_id':'ticket','action':'SERVICE','unit_price':'10','price_version':'v1','payment':'CASH'}
        self.finish(self.commerce.prepare(self.owner,self.actor,'ticket-key',body))
        refund={'business_id':business,'action':'REFUND','original_key':'ticket-key','payment':'CASH'}
        with self.assertRaises(EconomyError):self.commerce.prepare(self.owner,'other-actor','bad-refund',refund)
        op=self.commerce.prepare(self.owner,self.actor,'refund-key',refund);self.assertEqual(op['amount'],10);self.finish(op)
        with self.assertRaises(EconomyError):self.commerce.prepare(self.owner,self.actor,'refund-again',refund)

    def test_buybacks_repeat_until_their_cashbox_is_exhausted(self):
        cat=self.save(automatic=False,sell_enabled=True)
        self.finish(self.commerce.prepare(self.owner,self.actor,'fund-shop',{'business_id':'npcshop:'+self.id,'action':'FUND','amount':'20','payment':'BANK'},administrator=True))
        self.finish(self.buy(cat,action='SELL'));self.finish(self.buy(cat,action='SELL'))
        with self.assertRaises(EconomyError) as caught:self.buy(cat,action='SELL')
        self.assertEqual(caught.exception.code,'INSUFFICIENT_FUNDS')

    def test_stale_stock_cannot_be_reset_by_an_old_editor(self):
        cat=self.save(stock=3);self.finish(self.buy(cat));cat['name']='Old editor'
        with self.assertRaises(EconomyError) as caught:self.service.save(cat,'web:admin')
        self.assertEqual(caught.exception.code,'VERSION_CONFLICT')
        self.assertEqual(self.service.catalogue(self.id)['offers'][0]['stock'],2)

    def test_fulfilled_contract_records_each_lot_once_at_its_frozen_terms(self):
        from .npc_services import contract_terms
        offer='contract:'+self.id
        terms={'offer':offer,'city_id':'','items':[{'item_id':self.item,'quantity':2,'price':'10'}]}
        contract_terms(self.bank,terms);contract_terms(self.bank,terms)
        changed=dict(terms,items=[{'item_id':self.item,'quantity':3,'price':'10'}])
        with self.assertRaises(EconomyError):contract_terms(self.bank,changed)
        business='npc-contracts';self.commerce.register(business,'system:'+business,'Contrats','NPC');self.commerce.offer(business,offer,'v1','20','20')
        self.finish(self.commerce.prepare(self.owner,self.actor,str(uuid.uuid4()),{'business_id':business,'action':'FUND','amount':'20','payment':'BANK'},administrator=True))
        operation=self.commerce.prepare(self.owner,self.actor,str(uuid.uuid4()),{'business_id':business,'offer_id':offer,'price_version':'v1','action':'SELL','unit_price':'20','payment':'CASH'})
        proof=str(uuid.uuid4());self.commerce.transition(operation['_id'],self.actor,'delivery',0,proof);self.commerce.transition(operation['_id'],self.actor,'delivery',0,proof)
        rows=list(self.bank.db.market_transactions.find({'operation_id':operation['_id']}));self.assertEqual(len(rows),1);self.assertEqual(rows[0]['quantity'],2);self.assertEqual(rows[0]['unit_price'],10)

    def test_http_admin_gate_and_version_validation(self):
        from django.test import RequestFactory
        from types import SimpleNamespace
        from unittest.mock import patch
        from . import views,npc_views
        factory=RequestFactory();body=self.config()
        def request():return factory.post('/api/economy/v1/npc/shops',data=__import__('json').dumps(body),content_type='application/json',HTTP_X_MINECRAFT_UUID='fixture')
        with patch.object(views,'_has_server_api_key',return_value=True),patch.object(views.Player.objects,'get',return_value=SimpleNamespace(id=self.owner,rank='Joueur')),patch.object(npc_views,'get_bank',return_value=self.bank):
            self.assertEqual(npc_views.shops(request()).status_code,403)
        with patch.object(views,'_has_server_api_key',return_value=True),patch.object(views.Player.objects,'get',return_value=SimpleNamespace(id=self.owner,rank='Admin')),patch.object(npc_views,'get_bank',return_value=self.bank):
            self.assertEqual(npc_views.shops(request()).status_code,200)
            self.assertEqual(npc_views.shops(request()).status_code,409)

    def test_common_price_pressure_is_bounded_and_not_a_physical_stock(self):
        self.bank.db.market_economy_config.insert_one({'dynamic_economy_enabled':True})
        self.bank.db.market_activity_modifiers.insert_one({'city_id':None,'item_id':self.item,'activity_modifier':'2.0','period_end':datetime.now(timezone.utc)})
        try:
            ref=next(r for r in self.service.metadata()['references'] if r['item_id']==self.item)
            self.assertEqual(ref['price'],'12')  # 10 × 1.15, integer monetary rounding.
        finally:self.bank.db.market_economy_config.delete_many({})

    def test_market_clock_lease_schedules_only_one_refresh(self):
        from django.test import override_settings
        from unittest.mock import patch
        from markets.npc_clock import refresh_if_due
        self.bank.db.market_economy_config.insert_one({'dynamic_economy_enabled':True})
        try:
            with override_settings(MONGO_DB_NAME=self.database),patch('markets.npc_clock.executor.submit') as submit:
                refresh_if_due(self.bank);refresh_if_due(self.bank);refresh_if_due(self.bank)
                self.assertEqual(submit.call_count,1)
        finally:self.bank.db.market_economy_config.delete_many({})

    def test_partial_failed_recalculation_is_not_served_as_a_local_price(self):
        city=str(uuid.uuid4());self.bank.db.market_cities.insert_one({'id':city,'name':city,'active':True})
        self.bank.db.price_calculation_runs.insert_one({'status':'SUCCESS','calculation_version':'successful','finished_at':datetime.now(timezone.utc)})
        self.bank.db.calculated_market_prices.insert_one({'city_id':city,'market_type':'CITY_MARKET','item_id':self.item,'calculated_price':99,'calculation_version':'failed-partial'})
        body=self.config();body['city_id']=city
        try:self.assertFalse(self.service.save(body,'web:admin')['offers'][0]['available'])
        finally:self.bank.db.price_calculation_runs.delete_many({})

    def test_price_publisher_rejects_a_second_simultaneous_calculation(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from markets.price_lock import price_calculation_lease
        from rest_framework.exceptions import ValidationError
        fake=SimpleNamespace(connection=self.bank.db,ensure_connection=lambda:None)
        with patch('markets.price_lock.connection',fake):
            with price_calculation_lease():
                def attempt():
                    try:
                        with price_calculation_lease():return False
                    except ValidationError:return True
                with ThreadPoolExecutor(max_workers=1) as pool:self.assertTrue(pool.submit(attempt).result())
        self.assertIsNone(self.bank.db.economy_services.find_one({'_id':'market-price-publisher'}))

    def test_expired_price_publisher_cannot_publish_after_losing_its_lease(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from markets.price_lock import price_calculation_lease,verify_price_calculation_lease
        from rest_framework.exceptions import ValidationError
        fake=SimpleNamespace(connection=self.bank.db,ensure_connection=lambda:None)
        with patch('markets.price_lock.connection',fake):
            with price_calculation_lease():
                verify_price_calculation_lease()
                self.bank.db.economy_services.update_one({'_id':'market-price-publisher'},{'$set':{'expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}})
                with self.assertRaises(ValidationError):verify_price_calculation_lease()
