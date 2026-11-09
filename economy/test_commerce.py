import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from .commerce import Commerce
from .domain import EconomyError, public
from .store import Bank


@unittest.skipUnless(os.getenv('ECONOMY_TEST_URI'), 'Isolated Mongo integration requires ECONOMY_TEST_URI.')
class CommerceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        cls.client=MongoClient(os.environ['ECONOMY_TEST_URI'],serverSelectionTimeoutMS=3000)
        cls.name='rb_econ_test_'+uuid.uuid4().hex[:16]
        cls.bank=Bank(cls.client[cls.name]); cls.bank.initialize(); cls.service=Commerce(cls.bank)

    @classmethod
    def tearDownClass(cls):
        assert cls.name.startswith('rb_econ_test_') and len(cls.name)==29
        cls.client.drop_database(cls.name); cls.client.close()

    def setUp(self):
        self.owner=uuid.uuid4().hex; self.actor='minecraft:'+self.owner; self.business=uuid.uuid4().hex
        self.mc=str(uuid.uuid4())
        self.bank.db.players.insert_one({'id':self.owner,'id_minecraft':self.mc,'money':100})
        self.bank.migrate(self.owner,True)
        self.service.register(self.business,self.owner,'Comptoir de test','MARKET')
        self.service.offer(self.business,'stone','v1','20','10',1,'{id:"minecraft:stone"}')

    def test_offer_cursor_and_live_stock_exclude_old_empty_slots(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from django.test import RequestFactory, override_settings
        from . import views
        from .domain import fingerprint

        collection = self.bank.db.economy_offers
        rows = [
            {'_id': fingerprint({'business': self.business, 'offer': f'slot:0:old-{i}'}),
             'business_id': self.business, 'offer_id': f'slot:0:old-{i}', 'stock': 0}
            for i in range(205)
        ]
        live = 'slot:0:current'
        rows.append({'_id': fingerprint({'business': self.business, 'offer': live}),
                     'business_id': self.business, 'offer_id': live, 'stock': 12, 'version': 'v2',
                     'item_nbt': '{id:"minecraft:bread"}'})
        for row in rows:
            row.update(opening_stock=row['stock'], reserved_stock=0, incoming_stock=0)
        collection.insert_many(rows)
        self.addCleanup(collection.delete_many, {'_id': {'$in': [row['_id'] for row in rows]}})
        factory = RequestFactory()

        def fetch(**params):
            request = factory.get('/', {'business_id': self.business, **params},
                                  HTTP_X_API_KEY='test-offer-key', HTTP_X_MINECRAFT_UUID=self.mc)
            response = views.offer(request)
            self.assertEqual(response.status_code, 200)
            return json.loads(response.content)

        with override_settings(API_KEY_RENBLOOD='test-offer-key'), \
                patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id=self.owner, rank='Citoyen')), \
                patch('economy.views.get_bank', return_value=self.bank):
            first = fetch()
            second = fetch(after=first['next_cursor'])
            ids = [row['offer_id'] for page in (first, second) for row in page['offers']]
            self.assertEqual(len(ids), 207)
            self.assertEqual(len(set(ids)), len(ids))
            self.assertIsNone(second['next_cursor'])
            exact = fetch(offer_id=live)
            self.assertEqual(exact['offers'][0]['version'], 'v2')
            slots = fetch(scope='slots')
            self.assertEqual(slots['scope'], 'slots')
            self.assertEqual([row['offer_id'] for row in slots['offers']], [live])
            self.assertIsNone(slots['next_cursor'])
            self.assertEqual(fetch(scope='slots', business_id='missing-counter')['scope'], 'unregistered')

    def test_market_slot_stays_owned_until_last_reservation_is_resolved(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Comptoir réservé', 'MARKET')
        self.service.offer(business, 'slot:0:first', 'v1', '1', '0', 1, '{id:"minecraft:stone"}')
        self.service.offer(business, 'slot:0:second', 'v1', '1', '0', 0, '{id:"minecraft:bread"}')
        outgoing = self.service.prepare(self.owner, self.actor, 'reserve-first', {
            'business_id': business, 'action': 'STOCK_OUT', 'offer_id': 'slot:0:first',
            'quantity': 1, 'payment': 'BANK'})
        from types import SimpleNamespace
        from unittest.mock import patch
        from django.test import RequestFactory, override_settings
        from . import views
        request = RequestFactory().get('/', {'business_id': business, 'scope': 'slots'},
            HTTP_X_API_KEY='held-slot-key', HTTP_X_MINECRAFT_UUID=self.mc)
        with override_settings(API_KEY_RENBLOOD='held-slot-key'), \
                patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id=self.owner, rank='Citoyen')), \
                patch('economy.views.get_bank', return_value=self.bank):
            snapshot = views.offer(request)
        self.assertEqual(snapshot.status_code, 200)
        slot = json.loads(snapshot.content)['offers'][0]
        self.assertEqual(slot['stock'], 0)
        self.assertEqual(slot['reserved_stock'], 1)
        self.assertEqual(slot['pending_receipt'], outgoing['operation_id'])
        with self.assertRaises(EconomyError) as failure:
            self.service.prepare(self.owner, self.actor, 'replace-during-reservation', {
                'business_id': business, 'action': 'STOCK_IN', 'offer_id': 'slot:0:second', 'quantity': 1})
        self.assertEqual(failure.exception.code, 'SLOT_OCCUPIED')
        self.service.transition(outgoing['operation_id'], self.actor, 'cancel', 0, 'cancel-first')
        with self.assertRaises(EconomyError):
            self.service.prepare(self.owner, self.actor, 'replace-after-cancellation', {
                'business_id': business, 'action': 'STOCK_IN', 'offer_id': 'slot:0:second', 'quantity': 1})
        outgoing = self.service.prepare(self.owner, self.actor, 'withdraw-first', {
            'business_id': business, 'action': 'STOCK_OUT', 'offer_id': 'slot:0:first', 'quantity': 1})
        self.service.transition(outgoing['operation_id'], self.actor, 'delivery', 0, 'delivered-first')
        incoming = self.service.prepare(self.owner, self.actor, 'replace-empty-slot', {
            'business_id': business, 'action': 'STOCK_IN', 'offer_id': 'slot:0:second', 'quantity': 1})
        self.service.transition(incoming['operation_id'], self.actor, 'delivery', 0, 'delivered-second')

    def test_two_different_items_cannot_claim_the_same_empty_market_slot(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Comptoir concurrent', 'MARKET')
        for suffix in ('first', 'second'):
            self.service.offer(business, 'slot:0:' + suffix, 'v1', '1', '0', 0, '{id:"minecraft:stone"}')
        def claim(suffix):
            try:
                return self.service.prepare(self.owner, self.actor, 'claim-' + suffix, {
                    'business_id': business, 'action': 'STOCK_IN', 'offer_id': 'slot:0:' + suffix,
                    'quantity': 1})
            except EconomyError as failure:
                return failure.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ('first', 'second')))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(sum(result == 'SLOT_OCCUPIED' for result in results), 1)
        accepted = next(result for result in results if isinstance(result, dict))
        self.service.transition(accepted['operation_id'], self.actor, 'cancel', 0, 'cleanup-claim')

    def test_owner_can_recover_exact_legacy_slot_conflict(self):
        from .domain import fingerprint
        from .audit import reconcile
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Comptoir hérité', 'MARKET')
        first = self.service.offer(business, 'slot:0:first', 'v1', '1', '1', 1)
        # Reproduce data written before slot exclusivity was enforced.
        second = {**first, '_id': fingerprint({'business': business, 'offer': 'slot:0:second'}),
                  'offer_id': 'slot:0:second'}
        self.bank.db.economy_offers.insert_one(second)
        body = {'business_id': business, 'offer_id': 'slot:0:first', 'quantity': 1}
        with self.assertRaises(EconomyError) as failure:
            self.service.prepare(self.owner, self.actor, 'blocked-conflict-buy',
                                 {**body, 'action': 'BUY', 'price_version': 'v1', 'unit_price': '1'})
        self.assertEqual(failure.exception.code, 'SLOT_OCCUPIED')
        with self.assertRaises(EconomyError) as failure:
            self.service.prepare('another-owner', self.actor, 'blocked-conflict-theft',
                                 {**body, 'action': 'STOCK_OUT'})
        self.assertEqual(failure.exception.code, 'OWNER_REQUIRED')
        withdrawn = self.service.prepare(self.owner, self.actor, 'recover-legacy-variant',
                                         {**body, 'action': 'STOCK_OUT'})
        self.finish(withdrawn)
        self.finish(withdrawn)  # A repeated delivery cannot remove the other variant.
        self.assertEqual(self.bank.db.economy_offers.find_one({'_id': first['_id']})['stock'], 0)
        self.assertEqual(self.bank.db.economy_offers.find_one({'_id': second['_id']})['stock'], 1)
        self.assertEqual(reconcile(self.bank.db)['anomalies'], [])

    def test_market_slot_capacity_counts_incoming_and_reserved_stock(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Capacité réelle', 'MARKET')
        with self.assertRaises(EconomyError) as failure:
            self.service.offer(business, 'slot:0:stone', 'v1', '1', '1', 65)
        self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        self.service.offer(business, 'slot:0:stone', 'v1', '1', '1', 0)
        incoming = self.service.prepare(self.owner, self.actor, 'fill-slot', {
            'business_id': business, 'offer_id': 'slot:0:stone', 'action': 'STOCK_IN', 'quantity': 64})
        for value in (1, 65):
            with self.assertRaises(EconomyError) as failure:
                self.service.adjust_stock('admin', 'over-capacity-' + str(value), business,
                                          'slot:0:stone', 0, value, 'Capacité de recette')
            self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        self.finish(incoming)
        withdrawn = self.service.prepare(self.owner, self.actor, 'reserved-slot', {
            'business_id': business, 'offer_id': 'slot:0:stone', 'action': 'STOCK_OUT', 'quantity': 1})
        with self.assertRaises(EconomyError) as failure:
            self.service.adjust_stock('admin', 'held-capacity', business, 'slot:0:stone', 63, 64, 'Réservation')
        self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        self.finish(withdrawn, 'cancel')
        with self.assertRaises(EconomyError) as failure:
            self.service.prepare(self.owner, self.actor, 'sell-full-slot', {
                'business_id': business, 'offer_id': 'slot:0:stone', 'action': 'SELL', 'quantity': 1,
                'price_version': 'v1', 'unit_price': '1'})
        self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        from .audit import reconcile
        self.assertEqual(reconcile(self.bank.db)['anomalies'], [])

    def test_official_offer_can_keep_large_stock(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Boutique officielle', 'MARKET')
        offer = self.service.offer(business, 'minecraft:stone', 'v1', '1', '0', 128)
        self.service.adjust_stock('admin', 'large-official-stock', business, 'minecraft:stone', 128, 192,
                                  'Réapprovisionnement officiel')
        self.assertEqual(self.bank.db.economy_offers.find_one({'_id': offer['_id']})['stock'], 192)
        from .audit import reconcile
        self.assertEqual(reconcile(self.bank.db)['anomalies'], [])

    def test_real_stack_capacities_count_all_holds(self):
        for capacity in (1, 16):
            with self.subTest(capacity=capacity):
                business = 'market:' + uuid.uuid4().hex
                self.service.register(business, self.owner, 'Petites piles', 'MARKET')
                self.service.offer(business, 'slot:0:item', 'v1', '1', '1', 0, stock_capacity=capacity)
                body = {'business_id': business, 'offer_id': 'slot:0:item', 'action': 'STOCK_IN', 'quantity': capacity}
                incoming = self.service.prepare(self.owner, self.actor, 'small-in-' + str(capacity), body)
                with self.assertRaises(EconomyError) as failure:
                    self.service.adjust_stock('admin', 'small-adjust-' + str(capacity), business,
                                              'slot:0:item', 0, 1, 'Case déjà réservée')
                self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
                self.finish(incoming)
                with self.assertRaises(EconomyError) as failure:
                    self.service.prepare(self.owner, self.actor, 'small-overflow-' + str(capacity),
                                         {**body, 'quantity': 1})
                self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
                outgoing = self.service.prepare(self.owner, self.actor, 'small-out-' + str(capacity),
                                                {**body, 'action': 'STOCK_OUT', 'quantity': 1})
                with self.assertRaises(EconomyError) as failure:
                    self.service.prepare(self.owner, self.actor, 'small-reserved-' + str(capacity),
                                         {**body, 'quantity': 1})
                self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
                self.finish(outgoing, 'cancel')
                with self.assertRaises(EconomyError) as failure:
                    self.service.prepare(self.owner, self.actor, 'small-sale-' + str(capacity),
                                         {**body, 'action': 'SELL', 'quantity': 1, 'unit_price': '1', 'price_version': 'v1'})
                self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        from .audit import reconcile
        self.assertEqual(reconcile(self.bank.db)['anomalies'], [])

    def test_capacity_survives_legacy_clients_and_cannot_shrink_held_stock(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Compatibilité des piles', 'MARKET')
        offer = self.service.offer(business, 'slot:0:item', 'v1', '1', '0', 0, stock_capacity=16)
        body = {'business_id': business, 'offer_id': 'slot:0:item', 'action': 'STOCK_IN', 'quantity': 12}
        held = self.service.prepare(self.owner, self.actor, 'capacity-held', body)
        legacy = self.service.offer(business, 'slot:0:item', 'v2', '2', '0', 0)
        self.assertEqual(legacy['stock_capacity'], 16)
        with self.assertRaises(EconomyError) as failure:
            self.service.offer(business, 'slot:0:item', 'v2', '2', '0', 0, stock_capacity=8)
        self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        self.assertEqual(self.bank.db.economy_offers.find_one({'_id': offer['_id']})['stock_capacity'], 16)
        self.finish(held, 'cancel')
        updated = self.service.offer(business, 'slot:0:item', 'v2', '2', '0', 0, stock_capacity=8)
        self.assertEqual(updated['stock_capacity'], 8)

    def test_legacy_overfull_stack_is_recoverable_before_adopting_real_capacity(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Anciennes piles', 'MARKET')
        old = self.service.offer(business, 'slot:0:item', 'v1', '1', '0', 48)
        self.bank.db.economy_offers.update_one({'_id': old['_id']}, {'$unset': {'stock_capacity': ''}})
        with self.assertRaises(EconomyError) as failure:
            self.service.offer(business, 'slot:0:item', 'v1', '1', '0', 0, stock_capacity=16)
        self.assertEqual(failure.exception.code, 'STOCK_LIMIT')
        outgoing = self.service.prepare(self.owner, self.actor, 'reduce-legacy-stack', {
            'business_id': business, 'offer_id': 'slot:0:item', 'action': 'STOCK_OUT', 'quantity': 32})
        self.finish(outgoing)
        adopted = self.service.offer(business, 'slot:0:item', 'v1', '1', '0', 0, stock_capacity=16)
        self.assertEqual((adopted['stock'], adopted['stock_capacity']), (16, 16))
        from .audit import reconcile
        self.assertEqual(reconcile(self.bank.db)['anomalies'], [])

    def test_small_stack_concurrent_deposits_respect_capacity(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Piles concurrentes', 'MARKET')
        self.service.offer(business, 'slot:0:item', 'v1', '1', '0', 0, stock_capacity=16)
        def fill(key):
            try:
                return self.service.prepare(self.owner, self.actor, key, {
                    'business_id': business, 'offer_id': 'slot:0:item', 'action': 'STOCK_IN', 'quantity': 16})
            except EconomyError as failure:
                return failure.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(fill, ['small-concurrent-a', 'small-concurrent-b']))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(sum(result == 'STOCK_LIMIT' for result in results), 1)
        self.finish(next(result for result in results if isinstance(result, dict)), 'cancel')

    def test_invalid_stack_capacities_are_rejected(self):
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Capacités invalides', 'MARKET')
        for capacity in (0, 65, -1, True, 16.0, '16'):
            with self.subTest(capacity=capacity), self.assertRaises(EconomyError) as failure:
                self.service.offer(business, 'slot:0:item', 'v1', '1', '0', 0, stock_capacity=capacity)
            self.assertEqual(failure.exception.code, 'INVALID_STOCK')
        with self.assertRaises(EconomyError):
            self.service.offer(business, 'slot:0:item', 'v1', '1', '0', None, stock_capacity=16)
        with self.assertRaises(EconomyError):
            self.service.offer(business, 'minecraft:stone', 'v1', '1', '0', 200, stock_capacity=16)
        self.assertIsNone(self.bank.db.economy_offers.find_one({'business_id': business}))

    def test_capacity_roundtrip_through_game_offer_endpoint(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from django.test import RequestFactory, override_settings
        from . import views
        business = 'market:' + uuid.uuid4().hex
        self.service.register(business, self.owner, 'Capacité API', 'MARKET')
        factory = RequestFactory()
        body = {'business_id': business, 'offer_id': 'slot:0:item', 'price_version': 'v1',
                'buy_price': '1', 'sell_price': '0', 'stock': 1, 'stock_capacity': 1,
                'item_nbt': '{id:"minecraft:iron_sword"}'}
        headers = {'HTTP_X_API_KEY': 'capacity-test-key', 'HTTP_X_MINECRAFT_UUID': self.mc}
        with override_settings(API_KEY_RENBLOOD='capacity-test-key'), \
                patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id=self.owner, rank='Citoyen')), \
                patch('economy.views.get_bank', return_value=self.bank):
            response = views.offer(factory.post('/', json.dumps(body), content_type='application/json', **headers))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content)['stock_capacity'], 1)
            response = views.offer(factory.get('/', {'business_id': business, 'scope': 'slots'}, **headers))
            self.assertEqual(response.status_code, 200)
            row = json.loads(response.content)['offers'][0]
            self.assertEqual((row['stock'], row['stock_capacity']), (1, 1))

    def prepare(self,key,action='BUY',**extra):
        body={'business_id':self.business,'action':action,'payment':'BANK','offer_id':'stone',
              'quantity':1,'price_version':'v1','unit_price':'10' if action=='SELL' else '20',**extra}
        return self.service.prepare(self.owner,self.actor,key,body)

    def finish(self,op,action='delivery'):
        return self.service.transition(op['_id'],self.actor,action,op['revision'],'test:'+op['_id'])

    def fund(self,amount='40'):
        return self.finish(self.prepare('fund','FUND',amount=amount))

    def test_last_stock_has_one_buyer(self):
        def buy(key):
            try:return self.prepare(key)
            except EconomyError as error:return error.code
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(buy,['a','b']))
        self.assertEqual(sum(isinstance(x,dict) for x in results),1)
        self.assertIn('OUT_OF_STOCK',results)
        self.assertEqual(self.bank.account(self.owner)['reserved'],20)

    def test_accepted_price_survives_repricing_and_delivery_is_once(self):
        op=self.prepare('buy'); self.service.offer(self.business,'stone','v2','30','15',999,'{id:"minecraft:stone"}')
        self.finish(op); self.finish(op)
        self.assertEqual(self.bank.account(self.owner)['available'],80)
        box=self.bank.accounts.find_one({'_id':'cashbox:'+self.business})
        self.assertEqual(box['available'],20)
        self.assertEqual(self.bank.db.economy_offers.find_one({'business_id':self.business})['stock'],0)
        with self.assertRaises(EconomyError) as failure:self.prepare('stale')
        self.assertEqual(failure.exception.code,'PRICE_CHANGED')

    def test_cancellation_releases_funds_stock_and_incoming(self):
        op=self.prepare('buy'); self.finish(op,'cancel')
        self.assertEqual(self.bank.account(self.owner)['available'],100)
        offer=self.bank.db.economy_offers.find_one({'business_id':self.business})
        self.assertEqual((offer['stock'],offer['reserved_stock']),(1,0))
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+self.business})['incoming'],0)

    def test_empty_npc_budget_cannot_create_money(self):
        with self.assertRaises(EconomyError):self.prepare('sell','SELL')
        self.fund('10'); self.finish(self.prepare('sell','SELL'))
        with self.assertRaises(EconomyError):self.prepare('sell-again','SELL')
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_concurrent_claim_cannot_overdraw_cashbox(self):
        self.fund()
        def claim(key):
            try:return self.prepare(key,'CLAIM',amount='40')
            except EconomyError:return None
        with ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(claim,['c1','c2']))
        self.assertEqual(sum(x is not None for x in rows),1)
        self.finish(next(x for x in rows if x))
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_uncertain_delivery_keeps_reservations_until_review(self):
        op=self.prepare('uncertain'); receipt=self.finish(op,'reconcile')
        self.assertEqual(self.bank.account(self.owner)['reserved'],20)
        with self.assertRaises(EconomyError):self.finish(receipt,'cancel')
        self.service.transition(op['_id'],self.actor,'cancel',1,'review:verified',reviewer='admin:test')
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_stock_cannot_be_reset_by_server_registration(self):
        op=self.prepare('buy'); self.finish(op)
        self.service.offer(self.business,'stone','v1','20','10',999,'{id:"minecraft:stone"}')
        with self.assertRaises(EconomyError):self.prepare('again')

    def test_bank_transition_cannot_bypass_commerce_settlement(self):
        op=self.prepare('buy')
        with self.assertRaises(EconomyError):self.bank.transition(op['_id'],self.actor,'delivery',0,'forged')

    def test_zero_tax_default_and_safe_wire_amounts(self):
        wire=public(self.prepare('wire'))
        self.assertEqual(wire['tax'],'0');self.assertEqual(wire['unit_price'],'20')
        self.assertEqual(wire['legs'][0]['amount'],'20')

    def test_quest_reward_unique_across_retries_and_actors(self):
        quest=uuid.uuid4().hex
        self.bank.db.quests.insert_one({'questId':quest,'money':25,'name':'Test','rewards':[{'itemId':'minecraft:stone','count':1}]})
        self.bank.db.player_quest_states.insert_one({'_id':self.mc+':'+quest,'quest_id':quest,'player_id':self.mc,'status':'IN_PROGRESS'})
        self.service.complete_quest(self.owner,quest)
        def reward(actor):return self.service.reward(self.owner,actor,quest)
        with ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(reward,[self.actor,'another-server']))
        self.assertEqual(rows[0]['operation_id'],rows[1]['operation_id'])
        self.assertEqual(self.bank.account(self.owner)['available'],125)
        self.assertEqual(rows[0]['material_state'],'PENDING')

    def test_uncompleted_quest_cannot_be_paid(self):
        with self.assertRaises(EconomyError):self.service.reward(self.owner,self.actor,'unknown')

    def test_negative_margin_is_rejected(self):
        with self.assertRaises(EconomyError):self.service.offer(self.business,'bad','v1','10','11')

    def test_real_stock_deposit_and_withdraw_preserve_nbt_and_do_not_emit_money(self):
        self.service.offer(self.business,'slot:0:sword','v1','25','0',0,'{id:"minecraft:iron_sword",tag:{Damage:3}}')
        op=self.prepare('deposit-stock','STOCK_IN',offer_id='slot:0:sword',quantity=3,unit_price='0')
        self.finish(op)
        op=self.prepare('withdraw-stock','STOCK_OUT',offer_id='slot:0:sword',quantity=2,unit_price='0')
        self.assertIn('Damage:3',op['item_nbt']);self.finish(op)
        self.assertEqual(self.bank.db.economy_offers.find_one({'business_id':self.business,'offer_id':'slot:0:sword'})['stock'],1)
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_stock_deposit_capacity_includes_pending_operations(self):
        self.service.offer(self.business,'slot:0','v1','1','0',0)
        self.prepare('stock-a','STOCK_IN',offer_id='slot:0',quantity=64,unit_price='0')
        with self.assertRaises(EconomyError):self.prepare('stock-b','STOCK_IN',offer_id='slot:0',quantity=1,unit_price='0')

    def test_refund_is_backed_by_original_service_and_unique(self):
        service=self.finish(self.prepare('service','SERVICE'))
        refund=self.finish(self.prepare('refund','REFUND',original_operation_id=service['_id']))
        self.assertEqual(refund['amount'],20)
        with self.assertRaises(EconomyError):self.prepare('refund-again','REFUND',original_operation_id=service['_id'])
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_cancelled_refund_can_be_requested_again(self):
        service=self.finish(self.prepare('service','SERVICE'))
        refund=self.prepare('refund','REFUND',original_operation_id=service['_id']);self.finish(refund,'cancel')
        self.finish(self.prepare('refund-next','REFUND',original_operation_id=service['_id']))
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_offline_owner_receives_reconciled_cashbox_proceeds(self):
        buyer=uuid.uuid4().hex
        self.bank.db.players.insert_one({'id':buyer,'id_minecraft':str(uuid.uuid4()),'money':100})
        self.bank.migrate(buyer,True)
        body={'business_id':self.business,'action':'BUY','offer_id':'stone','price_version':'v1','unit_price':'20'}
        op=self.service.prepare(buyer,'minecraft:buyer','offline-sale',body)
        self.service.transition(op['_id'],'minecraft:buyer','delivery',0,'saved:buyer')
        self.assertIn(self.owner,op['participant_owner_ids'])
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+self.business})['available'],20)

    def test_buy_resell_loop_does_not_increase_player_wealth(self):
        self.fund('20')
        initial=self.bank.account(self.owner)['available']
        self.finish(self.prepare('buy-loop'))
        self.finish(self.prepare('sell-loop','SELL'))
        self.assertLessEqual(self.bank.account(self.owner)['available'],initial)

    def test_foreign_owner_cannot_claim_or_take_stock(self):
        for action in ['CLAIM','STOCK_OUT']:
            with self.assertRaises(EconomyError):self.service.prepare('intruder','minecraft:intruder',action,{
                'business_id':self.business,'action':action,'offer_id':'stone','amount':'1'})

    def test_reconciliation_matches_bank_cashbox_and_stock_reservations(self):
        from .audit import reconcile
        op=self.prepare('audit');self.assertEqual(reconcile(self.bank.db)['anomalies'],[])
        self.finish(op,'reconcile');self.assertEqual(reconcile(self.bank.db)['anomalies'],[])

    def test_npc_contract_is_unique_even_with_another_actor(self):
        self.service.register('npc:'+self.business,self.owner,'Marchand','NPC')
        self.service.offer('npc:'+self.business,'contract:1','v1','10','10')
        fund=self.service.prepare(self.owner,self.actor,'fund-npc',{'business_id':'npc:'+self.business,'action':'FUND','amount':'30'})
        self.finish(fund)
        body={'business_id':'npc:'+self.business,'action':'SELL','offer_id':'contract:1','price_version':'v1','unit_price':'10'}
        op=self.service.prepare(self.owner,self.actor,'contract',body);self.finish(op)
        with self.assertRaises(EconomyError):self.service.prepare(self.owner,'another-server','another-key',body)

    def test_cash_contract_releases_budget_after_cancel_and_never_credits_bank(self):
        npc = 'npc:' + self.business
        self.service.register(npc, self.owner, 'Marchand', 'NPC')
        self.service.offer(npc, 'contract:cash', 'v1', '10', '10')
        self.finish(self.service.prepare(self.owner, self.actor, 'fund-cash', {
            'business_id': npc, 'action': 'FUND', 'amount': '30',
        }))
        body = {'business_id': npc, 'action': 'SELL', 'offer_id': 'contract:cash',
                'price_version': 'v1', 'unit_price': '10', 'payment': 'CASH'}
        first = self.service.prepare(self.owner, self.actor, 'full-inventory', body)
        self.assertEqual(first['legs'], [{'account_id': 'cashbox:' + npc, 'direction': 'OUT', 'amount': 10}])
        self.finish(first, 'cancel')
        self.assertEqual(self.bank.accounts.find_one({'_id': 'cashbox:' + npc})['available'], 30)
        second = self.service.prepare(self.owner, self.actor, 'after-cancellation', body)
        self.assertEqual(self.finish(second)['state'], 'CONFIRMED')
        self.assertEqual(self.bank.account(self.owner)['available'], 70)
        self.assertEqual(self.bank.accounts.find_one({'_id': 'cashbox:' + npc})['available'], 20)
        with self.assertRaises(EconomyError):
            self.service.prepare(self.owner, self.actor, 'after-delivery', body)

    def test_unlimited_cash_rebuy_records_only_the_confirmed_shortfall(self):
        from .audit import reconcile
        from .desk import Desk
        npc = 'npc:' + self.business
        self.service.register(npc, self.owner, 'Marchand', 'NPC')
        self.service.offer(npc, 'contract:unlimited', 'v1', '10', '10')
        body = {'business_id': npc, 'action': 'SELL', 'offer_id': 'contract:unlimited',
                'price_version': 'v1', 'unit_price': '10', 'payment': 'CASH'}
        with self.assertRaises(EconomyError):
            self.service.prepare(self.owner, self.actor, 'empty', body)
        desk = Desk(self.bank)
        change = desk.budget_mode(npc, 'web:admin', 'unlimited', True)
        self.assertEqual(desk.budget_mode(npc, 'web:admin', 'unlimited', True), change)
        cancelled = self.service.prepare(self.owner, self.actor, 'cancelled-cash', body)
        self.finish(cancelled, 'cancel')
        self.assertEqual(reconcile(self.bank.db)['unlimited_budget_issued'], '0')
        self.finish(self.service.prepare(self.owner, self.actor, 'fund-partial', {
            'business_id': npc, 'action': 'FUND', 'amount': '3',
        }))
        operation = self.service.prepare(self.owner, self.actor, 'confirm-cash', body)
        self.assertEqual(operation['minted_amount'], 7)
        self.assertEqual(operation['budget_change_id'], change['_id'])
        desk.budget_mode(npc, 'web:admin', 'limited', False)
        self.finish(operation)
        self.finish(operation)
        self.assertEqual(reconcile(self.bank.db)['unlimited_budget_issued'], '7')
        self.assertEqual(reconcile(self.bank.db)['anomalies'], [])
        self.assertEqual(self.bank.account(self.owner)['available'], 97)

    def test_unlimited_inn_budget_is_scoped_to_its_traveller_payments(self):
        from .desk import Desk
        self.service.register('inn-customers', 'system:inn-customers', 'Voyageurs', 'NPC')
        inn = 'inn:' + self.business
        self.service.register(inn, self.owner, 'Auberge', 'INN')
        self.service.offer('inn-customers', 'meal:' + self.business, 'v1', '11', '11')
        Desk(self.bank).budget_mode(inn, 'web:admin', 'unlimited-inn', True)
        operation = self.service.prepare(self.owner, self.actor, 'traveller', {
            'business_id': 'inn-customers', 'action': 'SELL', 'payment': 'BANK',
            'destination_business_id': inn, 'offer_id': 'meal:' + self.business,
            'price_version': 'v1', 'unit_price': '11',
        })
        self.finish(operation)
        self.assertEqual(self.bank.accounts.find_one({'_id': 'cashbox:' + inn})['available'], 11)
        self.assertEqual(self.bank.account(self.owner)['available'], 100)
        self.assertEqual(operation['budget_policy_business_id'], inn)

    def test_closed_counter_cannot_trade_on_a_stale_game_cache(self):
        business='market:'+self.business
        self.service.register(business,self.owner,'Comptoir fermé','MARKET');self.service.offer(business,'stone','v1','20','10',1)
        self.bank.db.merchant_counters.insert_one({'counter_id':self.business,'active':False})
        with self.assertRaises(EconomyError):self.prepare('closed',business_id=business)

    def test_tax_rule_is_versioned_and_frozen_at_acceptance(self):
        treasury='city:'+self.business
        self.service.register(treasury,'system:city','Trésor de la ville','MARKET')
        self.service.policy(self.business,'admin','commerce-v1','pilot-2-percent',200,'cashbox:'+treasury)
        self.service.offer(self.business,'stone','v2','100','70',1,'{id:"minecraft:stone"}')
        op=self.prepare('taxed',price_version='v2',unit_price='100')
        self.service.policy(self.business,'admin','pilot-2-percent','pilot-no-tax',0,None)
        self.finish(op)
        self.assertEqual(op['tax'],2);self.assertEqual(op['business_rule_version'],'pilot-2-percent')
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+self.business})['available'],98)
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+treasury})['available'],2)
        from .audit import reconcile
        self.assertEqual(reconcile(self.bank.db)['anomalies'],[])

    def test_tax_cannot_use_float_or_missing_treasury(self):
        for tax in [1.5,True,-1,10001]:
            with self.assertRaises(EconomyError):self.service.policy(self.business,'admin','commerce-v1','invalid',tax,None)
        with self.assertRaises(EconomyError):self.service.policy(self.business,'admin','commerce-v1','invalid',200,None)

    def test_service_refund_returns_tax_from_the_original_treasury(self):
        treasury='city:'+self.business
        self.service.register(treasury,'system:city','Trésor','MARKET')
        self.service.policy(self.business,'admin','commerce-v1','taxed',1000,'cashbox:'+treasury)
        service=self.finish(self.prepare('service','SERVICE'))
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+treasury})['available'],2)
        refund=self.finish(self.prepare('refund','REFUND',original_operation_id=service['_id']))
        self.assertEqual(refund['refunded_tax'],2)
        self.assertEqual(self.bank.accounts.find_one({'_id':'cashbox:'+treasury})['available'],0)
        self.assertEqual(self.bank.account(self.owner)['available'],100)

    def test_admin_restock_is_traced_and_compare_and_set_protected(self):
        self.service.adjust_stock('admin','stock-change',self.business,'stone',1,10,'Réapprovisionnement de recette')
        self.service.adjust_stock('admin','stock-change',self.business,'stone',1,10,'Réapprovisionnement de recette')
        with self.assertRaises(EconomyError):self.service.adjust_stock('admin','other-stock-change',self.business,'stone',1,20,'Ancienne vue')
        from .audit import reconcile
        self.assertEqual(reconcile(self.bank.db)['anomalies'],[])

    def test_market_history_projects_the_frozen_receipt_once(self):
        business='market:'+self.business
        self.service.register(business,self.owner,'Comptoir','MARKET');self.service.offer(business,'stone','v1','20','10',1)
        counter_id=str(uuid.uuid4())
        self.bank.db.merchant_counters.insert_one({'counter_id':self.business,'id':counter_id,'active':True})
        op=self.prepare('projected',business_id=business);self.finish(op);self.finish(op)
        self.assertEqual(self.bank.db.market_transactions.count_documents({'operation_id':op['_id']}),1)
        tx=self.bank.db.market_transactions.find_one({'operation_id':op['_id']})
        self.assertEqual(tx['counter_id'],counter_id);self.assertEqual(tx['unit_price'],20)

    def test_public_commerce_receipt_matches_contract(self):
        import json
        from pathlib import Path
        from jsonschema import validate,FormatChecker
        schema=json.loads((Path(__file__).resolve().parents[2]/'docs/economie/etape-3/contracts/commerce-receipt-v1.schema.json').read_text(encoding='utf-8'))
        op=self.prepare('wire-contract');validate(public(op),schema,format_checker=FormatChecker())
        validate(public(self.finish(op)),schema,format_checker=FormatChecker())

    def test_completion_freezes_rewards_and_restart_recovers_pending_payout(self):
        quest=uuid.uuid4().hex
        self.bank.db.quests.insert_one({'questId':quest,'money':30,'name':'Récompense acceptée','rewards':[]})
        self.bank.db.player_quest_states.insert_one({'_id':self.mc+':'+quest,'quest_id':quest,'player_id':self.mc,'status':'IN_PROGRESS'})
        self.service.complete_quest(self.owner,quest)
        self.bank.db.quests.delete_one({'questId':quest})
        self.bank.db.player_quest_states.delete_one({'quest_id':quest,'player_id':self.mc})
        self.assertIn(quest,self.service.pending_rewards(self.owner))
        row=self.service.reward(self.owner,self.actor,quest)
        self.assertEqual(row['amount'],30);self.assertEqual(self.bank.account(self.owner)['available'],130)
        self.assertIn(quest,self.service.pending_rewards(self.owner))
        self.bank.db.economy_quest_rewards.update_one({'_id':row['_id']},{'$set':{'material_state':'DELIVERED'}})
        self.assertNotIn(quest,self.service.pending_rewards(self.owner))

    def test_historical_completion_is_never_automatically_paid_again(self):
        quest=uuid.uuid4().hex
        self.bank.db.quests.insert_one({'questId':quest,'money':50})
        self.bank.db.player_quest_states.insert_one({'_id':self.mc+':'+quest,'quest_id':quest,'player_id':self.mc,'status':'COMPLETED'})
        with self.assertRaises(EconomyError):self.service.reward(self.owner,self.actor,quest)
        with self.assertRaises(EconomyError):self.service.complete_quest(self.owner,quest)
        self.assertNotIn(quest,self.service.pending_rewards(self.owner))
        self.assertEqual(self.bank.account(self.owner)['available'],100)
