"""Commerce settlements: finite cashboxes, frozen quotes and transactional stock.

Minecraft proves physical delivery; this module never assumes that a timeout
means that an item was not delivered. Uncertain receipts retain reservations.
"""
import re
from uuid import uuid4
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from .domain import EconomyError, MAX_MONEY, money, legacy_money, fingerprint
from .store import timestamp

RULE_VERSION = 'commerce-v1'


def identifier(value, name='Identifiant'):
    if not isinstance(value, str) or not 1 <= len(value) <= 160 or any(ord(c) < 32 for c in value):
        raise EconomyError('INVALID_REQUEST', name + ' invalide.', 400)
    return value


class Commerce:
    def __init__(self, bank):
        self.bank = bank
        self.db = bank.db

    def register(self, business, owner, label, kind):
        """Server registration creates an empty cashbox, never initial money."""
        identifier(business); identifier(owner); identifier(label)
        if kind not in {'MARKET', 'INN', 'NPC', 'EXPLORATION'}:
            raise EconomyError('INVALID_REQUEST', 'Établissement invalide.', 400)
        def run(s):
            old = self.db.economy_businesses.find_one({'_id': business}, session=s)
            if old:
                if old['owner_id'] != owner or old['kind'] != kind:
                    raise EconomyError('OWNER_CONFLICT', 'Le propriétaire doit être rapproché avant transfert.')
                return old
            row = {'_id': business, 'business_id': business, 'owner_id': owner,
                   'label': label, 'label_search':label.casefold(), 'revision':0, 'kind': kind, 'active': True, 'rule_version': RULE_VERSION,
                   'tax_bps': 0, 'created_at': timestamp()}
            self.db.economy_businesses.insert_one(row, session=s)
            self.bank.accounts.insert_one({'_id': 'cashbox:' + business, 'owner_id': owner,
                'business_id': business, 'pocket': 'CASHBOX', 'currency': 'IRON',
                'available': 0, 'reserved': 0, 'incoming': 0, 'revision': 0,
                'opening_balance': 0, 'updated_at': timestamp()}, session=s)
            return row
        try:
            return self.bank.transact(run)
        except DuplicateKeyError:
            return self.register(business, owner, label, kind)

    def _lock_market_slot(self, business, offer_id, session, outgoing=False):
        if not business.startswith('market:') or not offer_id.startswith('slot:'):
            return
        match = re.fullmatch(r'slot:(0|[1-9][0-9]?):(.+)', offer_id)
        if not match or int(match[1]) >= 54:
            raise EconomyError('INVALID_STOCK', 'Emplacement de comptoir invalide.', 400)
        # A shared write forces concurrent slot claims to retry from a fresh snapshot.
        self.db.economy_businesses.update_one({'_id': business}, {'$inc': {'stock_revision': 1}}, session=session)
        if outgoing:
            return  # Exact owner withdrawals can recover conflicting legacy variants.
        occupied = self.db.economy_offers.find_one({
            'business_id': business, 'offer_id': {'$regex': '^slot:' + match[1] + ':'},
            '_id': {'$ne': fingerprint({'business': business, 'offer': offer_id})},
            '$or': [{'stock': {'$gt': 0}}, {'reserved_stock': {'$gt': 0}}, {'incoming_stock': {'$gt': 0}}],
        }, {'_id': 1}, session=session)
        if occupied:
            raise EconomyError('SLOT_OCCUPIED', 'Cet emplacement contient encore un autre article ou une réservation.')

    def offer(self, business, offer_id, version, buy, sell, stock=None, item_nbt=None, stock_capacity=None):
        """Publish a quote without resetting stock held by live receipts.

        The game server supplies the real stack capacity for player market slots.
        Older offers/clients retain the established capacity, defaulting to 64.
        """
        identifier(business); identifier(offer_id); identifier(version)
        buy = money(buy, zero=True); sell = money(sell, zero=True)
        if sell > buy:
            raise EconomyError('INVALID_MARGIN', 'Le prix de rachat dépasse le prix de vente.', 400)
        if stock is not None and (type(stock) is not int or not 0 <= stock <= 2147483647):
            raise EconomyError('INVALID_STOCK', 'Stock invalide.', 400)
        market_slot = business.startswith('market:') and offer_id.startswith('slot:')
        if stock_capacity is not None and (not market_slot or type(stock_capacity) is not int or not 1 <= stock_capacity <= 64):
            raise EconomyError('INVALID_STOCK', 'Capacité de case entière entre 1 et 64 requise.', 400)
        if market_slot and stock is None:
            raise EconomyError('INVALID_STOCK', 'Une case de marché exige un stock limité.', 400)
        if item_nbt is not None and (not isinstance(item_nbt, str) or len(item_nbt) > 8192):
            raise EconomyError('INVALID_ITEM', 'Propriétés de l’objet invalides.', 400)
        ident = fingerprint({'business': business, 'offer': offer_id})
        def run(s):
            self.business(business, s)
            if stock:
                self._lock_market_slot(business, offer_id, s)
            old = self.db.economy_offers.find_one({'_id': ident}, session=s)
            quote = {'version': version, 'buy_price': buy, 'sell_price': sell, 'item_nbt': item_nbt}
            capacity = stock_capacity if stock_capacity is not None else (old.get('stock_capacity', 64) if old else 64)
            if market_slot:
                if old and old['stock'] is None:
                    raise EconomyError('STOCK_AUTHORITY_CONFLICT', 'Cette ancienne case illimitée doit être rapprochée.')
                occupied = old['stock'] + old['reserved_stock'] + old['incoming_stock'] if old else stock
                if occupied is None or occupied > capacity:
                    raise EconomyError('STOCK_LIMIT', 'La capacité de cette case est dépassée. Reprenez le stock excédentaire.')
            if old:
                if (old['stock'] is None) != (stock is None):
                    raise EconomyError('STOCK_AUTHORITY_CONFLICT', 'Le mode de stock ne peut pas changer pendant les échanges.')
                if old.get('item_nbt') != item_nbt:
                    raise EconomyError('ITEM_CONFLICT', 'Utilisez une autre référence pour un objet différent.')
                if old['version'] == version and any(old.get(k) != v for k, v in quote.items()):
                    raise EconomyError('PRICE_VERSION_CONFLICT', 'Cette version contient déjà un autre prix.')
                changes = dict(quote)
                if market_slot:
                    changes['stock_capacity'] = capacity
                if all(old.get(k) == v for k, v in changes.items()): return old
                self.db.economy_offers.update_one({'_id': ident}, {'$set': changes}, session=s)
                return {**old, **changes}
            row = {'_id': ident, 'business_id': business, 'offer_id': offer_id,
                   'stock': stock, 'opening_stock': stock, 'reserved_stock': 0, 'incoming_stock': 0, **quote}
            if market_slot:
                row['stock_capacity'] = capacity
            self.db.economy_offers.insert_one(row, session=s)
            return row
        return self.bank.transact(run)

    def business(self, business, session=None):
        row = self.db.economy_businesses.find_one({'_id': business, 'active': True}, session=session)
        if not row:
            raise EconomyError('BUSINESS_UNAVAILABLE', 'Établissement absent ou fermé.')
        return row

    def policy(self,business,actor,expected,version,tax_bps,treasury):
        identifier(business);identifier(version)
        if type(tax_bps) is not int or not 0<=tax_bps<=10000:
            raise EconomyError('INVALID_RULE','Taxe entière entre 0 et 10000 points de base requise.',400)
        def run(s):
            row=self.business(business,s)
            if row['rule_version']!=expected:raise EconomyError('REVISION_CONFLICT','Le barème a changé.')
            if version==expected:raise EconomyError('NEW_RULE_VERSION_REQUIRED','Une nouvelle version de règle est requise.',400)
            if tax_bps:
                account=self.bank.accounts.find_one({'_id':treasury,'pocket':'CASHBOX'},session=s)
                if not account or treasury=='cashbox:'+business:raise EconomyError('TREASURY_REQUIRED','Une caisse fiscale distincte est requise.',400)
            changes={'rule_version':version,'tax_bps':tax_bps,'treasury_account_id':treasury if tax_bps else None}
            self.db.economy_business_rules.insert_one({'_id':fingerprint({'business':business,'version':version}),
                'business_id':business,'actor_id':actor,'previous_rule_version':expected,'created_at':timestamp(),**changes},session=s)
            self.db.economy_businesses.update_one({'_id':business},{'$set':changes},session=s)
            return {**row,**changes}
        try:return self.bank.transact(run)
        except DuplicateKeyError:raise EconomyError('RULE_VERSION_CONFLICT','Cette version de règle a déjà été utilisée.')

    def _reserve(self, account_id, value, incoming, session):
        account = self.bank.accounts.find_one({'_id': account_id}, session=session)
        if not account:
            raise EconomyError('ACCOUNT_NOT_MIGRATED', 'Compte économique à préparer.')
        if incoming:
            if account['available'] + account['reserved'] + account.get('incoming', 0) > MAX_MONEY - value:
                raise EconomyError('BALANCE_LIMIT', 'La caisse destinataire a atteint sa limite.')
            delta = {'incoming': value}
        else:
            if account['available'] < value:
                raise EconomyError('INSUFFICIENT_FUNDS', 'Budget disponible insuffisant.')
            delta = {'available': -value, 'reserved': value}
        self.bank.accounts.update_one({'_id': account_id}, {'$inc': {**delta, 'revision': 1},
            '$set': {'updated_at': timestamp()}}, session=session)

    def adjust_stock(self,actor,key,business,offer_id,expected,new_stock,reason):
        identifier(key);identifier(reason,'Motif');identifier(business);identifier(offer_id)
        if type(expected) is not int or type(new_stock) is not int or not 0<=new_stock<=2147483647:
            raise EconomyError('INVALID_STOCK','Stock entier positif ou nul requis.',400)
        digest=fingerprint({'business':business,'offer':offer_id,'expected':expected,'stock':new_stock,'reason':reason})
        def run(s):
            old=self.bank.operations.find_one({'actor_id':actor,'key':key},session=s)
            if old:
                if old['request_hash']!=digest:raise EconomyError('IDEMPOTENCY_CONFLICT','Cette clé désigne un autre ajustement.')
                return old
            resource=self.business(business,s)
            offer=self.db.economy_offers.find_one({'business_id':business,'offer_id':offer_id},session=s)
            if not offer or offer['stock'] is None:raise EconomyError('INVALID_STOCK','Offre à stock limité requise.')
            if offer['stock']!=expected:raise EconomyError('REVISION_CONFLICT','Le stock a changé.')
            if new_stock > 0:
                self._lock_market_slot(business, offer_id, s)
            limit = offer.get('stock_capacity', 64) if business.startswith('market:') and offer_id.startswith('slot:') else 2147483647
            if new_stock+offer['reserved_stock']+offer['incoming_stock']>limit:raise EconomyError('STOCK_LIMIT','Capacité de stock dépassée.')
            self.db.economy_offers.update_one({'_id':offer['_id']},{'$set':{'stock':new_stock}},session=s)
            ident=str(uuid4());now=timestamp();delta=new_stock-expected
            op={'_id':ident,'operation_id':ident,'owner_id':resource['owner_id'],'business_owner_id':resource['owner_id'],
                'actor_id':actor,'key':key,'request_hash':digest,'type':'COMMERCE','action':'STOCK_ADJUST',
                'business_id':business,'stock_id':offer['_id'],'offer_id':offer_id,'limited_stock':True,
                'quantity':abs(delta),'stock_delta':delta,'amount':0,'tax':0,'currency':'IRON','legs':[],
                'state':'CONFIRMED','api_version':'1','revision':0,'reason':reason,'rule_version':RULE_VERSION,
                'proof_id':'admin:'+ident,'created_at':now,'updated_at':now}
            self.bank.operations.insert_one(op,session=s);return op
        try:return self.bank.transact(run)
        except DuplicateKeyError:
            previous=self.bank.operations.find_one({'actor_id':actor,'key':key})
            if previous and previous['request_hash']==digest:return previous
            raise EconomyError('IDEMPOTENCY_CONFLICT','Cette clé désigne un autre ajustement.')

    def prepare(self, owner, actor, key, body, administrator=False):
        identifier(key, 'Clé'); business_id = identifier(body.get('business_id'))
        action = body.get('action'); payment = body.get('payment', 'BANK')
        if action not in {'BUY', 'SELL', 'SERVICE', 'CLAIM', 'FUND', 'REFUND', 'STOCK_IN', 'STOCK_OUT'} or payment not in {'BANK', 'CASH'}:
            raise EconomyError('INVALID_REQUEST', 'Règlement invalide.', 400)
        qty = body.get('quantity', 1)
        if type(qty) is not int or not 1 <= qty <= 2304:
            raise EconomyError('INVALID_QUANTITY', 'Quantité invalide.', 400)
        digest = fingerprint({'owner': owner, 'body': body})
        def run(s):
            previous = self.bank.operations.find_one({'actor_id': actor, 'key': key}, session=s)
            if previous:
                if previous['request_hash'] != digest:
                    raise EconomyError('IDEMPOTENCY_CONFLICT', 'Cette clé désigne une autre opération.')
                return previous
            business = self.business(business_id, s); box = 'cashbox:' + business_id
            if type(business.get('tax_bps')) is not int or not 0<=business['tax_bps']<=10000:
                raise EconomyError('INVALID_RULE','Le barème fiscal de cette caisse doit être vérifié.')
            if business_id.startswith('market:') and action in {'BUY','SELL'}:
                counter=self.db.merchant_counters.find_one({'counter_id':business_id[7:]},session=s)
                mode='sell_mode_enabled' if action=='SELL' else 'buy_mode_enabled'
                if counter and (not counter.get('active') or not counter.get(mode,True)):
                    raise EconomyError('BUSINESS_UNAVAILABLE','Le comptoir a été fermé ou cet échange est désactivé.')
            if business_id.startswith('npcshop:') and action in {'BUY', 'SELL'}:
                shop = self.db.npc_shops.find_one({'_id': business_id[8:], 'active': True}, session=s)
                entry = next((e for e in (shop or {}).get('offers', []) if e['id'] == body.get('offer_id')), None)
                if not entry or not entry['buy_enabled' if action == 'BUY' else 'sell_enabled']:
                    raise EconomyError('OFFER_UNAVAILABLE', 'Cet article a été fermé ou retiré.')
            offer = None; tax = 0
            budget_policy = business if action == 'SELL' and business.get('budget_unlimited') else None
            original=None
            if action=='REFUND':
                original_reference={'_id':body.get('original_operation_id')} if body.get('original_operation_id') else {'actor_id':actor,'key':body.get('original_key')}
                original=self.bank.operations.find_one({**original_reference,'type':'COMMERCE',
                    'state':'CONFIRMED','action':'SERVICE','business_id':business_id,'owner_id':owner,'payment':payment},session=s)
                if not original: raise EconomyError('REFUND_NOT_ALLOWED','Service bancaire confirmé requis.')
                if self.bank.operations.find_one({'original_operation_id':original['_id']},session=s):
                    raise EconomyError('ALREADY_REFUNDED','Ce service a déjà été remboursé.')
                if payment not in {'BANK', 'CASH'}: raise EconomyError('INVALID_REQUEST','Mode de remboursement invalide.',400)
                amount=original['amount'];source=box;dest='bank:'+owner if payment=='BANK' else None
            elif action in {'CLAIM', 'FUND'}:
                if business['owner_id'] != owner and not (administrator and action=='FUND'):
                    raise EconomyError('OWNER_REQUIRED', 'Seul le propriétaire peut déplacer cette caisse.', 403)
                if payment != 'BANK':
                    raise EconomyError('INVALID_REQUEST', 'Le transfert de caisse se fait en banque.', 400)
                amount = money(body.get('amount'))
                source, dest = (box, 'bank:' + owner) if action == 'CLAIM' else ('bank:' + owner, box)
            else:
                ident = fingerprint({'business': business_id, 'offer': body.get('offer_id')})
                offer = self.db.economy_offers.find_one({'_id': ident}, session=s)
                if not offer:
                    raise EconomyError('OFFER_UNAVAILABLE', 'Offre indisponible.')
                stock_move=action in {'STOCK_IN','STOCK_OUT'}
                if stock_move and business['owner_id']!=owner:
                    raise EconomyError('OWNER_REQUIRED','Seul le propriétaire peut déplacer ce stock.',403)
                price = 0 if stock_move else (offer['sell_price'] if action == 'SELL' else offer['buy_price'])
                if not price and not stock_move:
                    raise EconomyError('OFFER_UNAVAILABLE', 'Cette offre ne permet pas cet échange.')
                if not stock_move and (body.get('price_version') != offer['version'] or money(body.get('unit_price')) != price):
                    raise EconomyError('PRICE_CHANGED', 'Le prix a changé. Rechargez l’offre avant de confirmer.')
                amount = price * qty
                if amount > MAX_MONEY:
                    raise EconomyError('INVALID_AMOUNT', 'Total hors limites.', 400)
                tax = amount * business['tax_bps'] // 10000 if action != 'SELL' else 0
                source = box if action == 'SELL' else ('bank:' + owner if payment == 'BANK' else None)
                dest = ('bank:' + owner if payment == 'BANK' else None) if action == 'SELL' else box
                if action=='SELL' and body.get('destination_business_id'):
                    destination=self.business(body['destination_business_id'],s)
                    if destination['kind']!='INN': raise EconomyError('INVALID_REQUEST','Caisse d’auberge requise.',400)
                    dest='cashbox:'+destination['_id']
                    if business_id == 'inn-customers' and destination.get('budget_unlimited'):
                        budget_policy = destination
                if stock_move:
                    source=dest=None
                    if offer['stock'] is None:
                        raise EconomyError('INVALID_STOCK','Le stock réel exige une quantité limitée.')
                if offer['stock'] is not None:
                    self._lock_market_slot(business_id, offer['offer_id'], s, outgoing=action == 'STOCK_OUT')
                if action in {'BUY','STOCK_OUT'} and offer['stock'] is not None:
                    if offer['stock'] < qty:
                        raise EconomyError('OUT_OF_STOCK', 'Stock disponible insuffisant.')
                    self.db.economy_offers.update_one({'_id': ident}, {'$inc': {'stock': -qty, 'reserved_stock': qty}}, session=s)
                if action in {'SELL','STOCK_IN'} and offer['stock'] is not None:
                    market_slot = business_id.startswith('market:') and offer['offer_id'].startswith('slot:')
                    limit = offer.get('stock_capacity', 64) if market_slot else (64 if action == 'STOCK_IN' else 2147483647)
                    if offer['stock'] + offer['reserved_stock'] + offer['incoming_stock'] + qty > limit:
                        raise EconomyError('STOCK_LIMIT', 'Stock plein.')
                    self.db.economy_offers.update_one({'_id': ident}, {'$inc': {'incoming_stock': qty}}, session=s)
            legs = []
            if original:
                for old_leg in original['legs']:
                    direction='IN' if old_leg['direction']=='OUT' else 'OUT'
                    self._reserve(old_leg['account_id'],old_leg['amount'],direction=='IN',s)
                    legs.append({**old_leg,'direction':direction})
                source=dest=None
            issued = 0
            if source:
                debit = amount
                if budget_policy is not None:
                    payer = self.bank.accounts.find_one({'_id': source}, session=s)
                    if not payer:
                        raise EconomyError('ACCOUNT_NOT_MIGRATED', 'Caisse économique à préparer.')
                    debit = min(amount, payer['available'])
                    issued = amount - debit
                if debit:
                    self._reserve(source, debit, False, s)
                    legs.append({'account_id': source, 'direction': 'OUT', 'amount': debit})
            if dest:
                self._reserve(dest, amount - tax, True, s); legs.append({'account_id': dest, 'direction': 'IN', 'amount': amount - tax})
            # Taxes are disabled by default. A configured rate requires a real treasury.
            if tax:
                treasury = business.get('treasury_account_id')
                if not treasury:
                    raise EconomyError('TREASURY_REQUIRED', 'Trésorerie fiscale absente.')
                self._reserve(treasury, tax, True, s); legs.append({'account_id': treasury, 'direction': 'IN', 'amount': tax})
            ident = str(uuid4()); now = timestamp()
            op = {'_id': ident, 'operation_id': ident, 'api_version': '1', 'owner_id': owner,
                'actor_id': actor, 'key': key, 'request_hash': digest, 'type': 'COMMERCE',
                'action': action, 'business_id': business_id, 'business_owner_id': business['owner_id'],
                'reason': business['label'], 'amount': amount, 'tax': tax, 'currency': 'IRON',
                'payment': payment, 'legs': legs, 'quantity': qty, 'rule_version': RULE_VERSION,
                'tax_bps': business['tax_bps'], 'business_rule_version': business['rule_version'],
                'state': 'RESERVED', 'revision': 0, 'created_at': now, 'updated_at': now}
            if budget_policy is not None:
                op.update({'budget_mode': 'UNLIMITED', 'budget_policy_business_id': budget_policy['_id'],
                           'budget_change_id': budget_policy['budget_change_id'], 'minted_amount': issued})
            participants={owner,business['owner_id']}
            for leg in legs:
                account=self.bank.accounts.find_one({'_id':leg['account_id']},session=s)
                participants.add(account['owner_id'])
            op['participant_owner_ids']=sorted(participants)
            if offer:
                op.update({'offer_id': offer['offer_id'], 'stock_id': offer['_id'], 'limited_stock': offer['stock'] is not None,
                    'unit_price': price, 'price_version': offer['version'], 'item_nbt': offer.get('item_nbt')})
            if original:
                op['original_operation_id']=original['_id']
                op['refunded_tax']=original['tax']
            if business['kind']=='NPC' and action=='SELL':
                redemption=fingerprint({'business':business_id,'offer':op['offer_id']})
                if self.db.economy_redemptions.find_one({'_id':redemption},session=s):
                    raise EconomyError('OFFER_ALREADY_USED','Ce contrat ou ce service a déjà été réglé.')
                self.db.economy_redemptions.insert_one({'_id':redemption,'operation_id':ident},session=s)
            if body.get('reason'):op['administrative_reason']=identifier(body['reason'],'Motif')
            for field in ['item_id','item_display_name']:
                if field in body: op[field]=identifier(body[field])
            self.bank.operations.insert_one(op, session=s)
            return op
        try:
            return self.bank.transact(run)
        except DuplicateKeyError:
            old = self.bank.operations.find_one({'actor_id': actor, 'key': key})
            if old and old['request_hash'] == digest:
                return old
            raise EconomyError('IDEMPOTENCY_CONFLICT', 'Cette clé désigne une autre opération.')

    def transition(self, ident, actor, action, revision, proof, reviewer=None):
        if action not in {'delivery', 'cancel', 'reconcile'} or type(revision) is not int or revision < 0:
            raise EconomyError('INVALID_REQUEST', 'Transition invalide.', 400)
        identifier(proof, 'Preuve')
        target = {'delivery': 'CONFIRMED', 'cancel': 'CANCELLED', 'reconcile': 'RECONCILIATION_REQUIRED'}[action]
        def run(s):
            op = self.bank.operations.find_one({'_id': ident, 'actor_id': actor, 'type': 'COMMERCE'}, session=s)
            if not op:
                raise EconomyError('OPERATION_NOT_FOUND', 'Reçu introuvable.', 404)
            if op['state'] == target and op.get('proof_id') == proof:
                return op
            if op['revision'] != revision:
                raise EconomyError('REVISION_CONFLICT', 'Le reçu a changé.')
            if op['state'] != 'RESERVED' and not (reviewer and op['state'] == 'RECONCILIATION_REQUIRED'):
                raise EconomyError('INVALID_STATE', 'Règlement déjà terminé ou à rapprocher.')
            if action != 'reconcile':
                if action=='cancel': self.db.economy_redemptions.delete_one({'operation_id':ident},session=s)
                for leg in op['legs']:
                    value = leg['amount']
                    if leg['direction'] == 'OUT':
                        delta = {'reserved': -value}
                        if action == 'cancel': delta['available'] = value
                    else:
                        delta = {'incoming': -value}
                        if action == 'delivery': delta['available'] = value
                    self.bank.accounts.update_one({'_id': leg['account_id']}, {'$inc': {**delta, 'revision': 1}, '$set': {'updated_at': timestamp()}}, session=s)
                    if leg['account_id'].startswith('bank:'):
                        account = self.bank.accounts.find_one({'_id': leg['account_id']}, session=s)
                        self.db.players.update_one({'id': account['owner_id']}, {'$set': {'money': account['available'] + account['reserved']}}, session=s)
                if op.get('limited_stock'):
                    if op['business_id'].startswith('market:') and op['offer_id'].startswith('slot:'):
                        self.db.economy_businesses.update_one({'_id': op['business_id']},
                            {'$inc': {'stock_revision': 1}}, session=s)
                    qty = op['quantity']; delta = {}
                    if op['action'] in {'BUY','STOCK_OUT'}:
                        delta['reserved_stock'] = -qty
                        if action == 'cancel': delta['stock'] = qty
                    elif op['action'] in {'SELL','STOCK_IN'}:
                        delta['incoming_stock'] = -qty
                        if action == 'delivery': delta['stock'] = qty
                    if delta: self.db.economy_offers.update_one({'_id': op['stock_id']}, {'$inc': delta}, session=s)
                if action=='delivery' and op['business_id']=='npc-contracts' and op['action']=='SELL':
                    from .npc_services import record_contract_delivery
                    record_contract_delivery(self.db, op, s)
                if action=='delivery' and op['business_id'].startswith('npcshop:') and op['action'] in {'BUY','SELL'}:
                    from .npc_services import NpcShops
                    NpcShops(self.bank).record_delivery(op, s)
                if action=='delivery' and op['business_id'].startswith('market:') and op['action'] in {'BUY','SELL'}:
                    counter=self.db.merchant_counters.find_one({'counter_id':op['business_id'][7:]},session=s)
                    if counter:
                        player=self.db.players.find_one({'id':op['owner_id']},session=s) or {}
                        self.db.market_transactions.insert_one({'id':op['_id'],'operation_id':op['_id'],'counter_id':counter['id'],
                            'city_id':counter.get('city_id'),'player_uuid':player.get('id_minecraft',''),
                            'player_name':player.get('name',op['owner_id']),'owner_type':counter.get('owner_type','ADMIN'),
                            'owner_id':counter.get('owner_id'),'item_id':op.get('item_id',op['offer_id']),
                            'item_display_name':op.get('item_display_name',op['offer_id']),
                            'action':op['action'],'quantity':op['quantity'],'unit_price':op['unit_price'],
                            'total_price':op['amount'],'owner_gain':op['amount']-op['tax'] if op['action']=='BUY' else 0,
                            'tax':op['tax'],'price_version':op['price_version'],'rule_version':RULE_VERSION,
                            'created_at':datetime.now(timezone.utc)},session=s)
                        self.db.merchant_counters.update_one({'_id':counter['_id']},{'$set':{'last_transaction_at':datetime.now(timezone.utc)}},session=s)
                if action=='delivery' and op['business_id'].startswith('market:') and op['action']=='CLAIM':
                    player=self.db.players.find_one({'id':op['owner_id']},session=s) or {}
                    self.db.market_withdrawals.insert_one({'id':op['_id'],'counter_id':op['business_id'][7:],
                        'owner_uuid':player.get('id_minecraft',''),'owner_name':player.get('name',op['owner_id']),
                        'amount':op['amount'],'withdrawn_at':datetime.now(timezone.utc),'source':'MINECRAFT',
                        'created_at':datetime.now(timezone.utc)},session=s)
            changes = {'state': target, 'proof_id': proof, 'updated_at': timestamp()}
            if reviewer: changes['reviewed_by'] = reviewer
            update={'$set':changes,'$inc':{'revision':1}}
            if action=='cancel' and op['action']=='REFUND':
                changes['cancelled_original_operation_id']=op['original_operation_id']
                update['$unset']={'original_operation_id':''}
                op={k:v for k,v in op.items() if k!='original_operation_id'}
            self.bank.operations.update_one({'_id': ident}, update, session=s)
            return {**op, **changes, 'revision': revision + 1}
        return self.bank.transact(run)

    def complete_quest(self,owner,quest_id):
        """Freeze rewards atomically with completion; historical payouts stay fenced."""
        identifier(quest_id)
        completion_key='quest:'+fingerprint({'owner':owner,'quest':quest_id})
        def run(s):
            accepted=self.db.economy_quest_completions.find_one({'_id':completion_key},session=s)
            if accepted:return accepted
            player=self.db.players.find_one({'id':owner},session=s)
            if not player:raise EconomyError('OWNER_NOT_FOUND','Personnage introuvable.',404)
            states=list(self.db.player_quest_states.find({'quest_id':quest_id,'player_id':{'$in':[owner,player['id_minecraft']]}},session=s).limit(2))
            if len(states)!=1:raise EconomyError('QUEST_STATE_AMBIGUOUS','La progression de cette quête doit être vérifiée.')
            state=states[0]
            if state.get('completedAt') or state['status']=='COMPLETED':
                if state.get('reward_snapshot',{}).get('rule_version')!=RULE_VERSION:
                    raise EconomyError('LEGACY_REWARD_REVIEW','Cette ancienne quête peut déjà avoir été payée. Vérification requise.')
                raise EconomyError('COMPLETION_REVIEW','Le reçu d’accomplissement doit être vérifié avant paiement.')
            if state['status']!='IN_PROGRESS':raise EconomyError('QUEST_NOT_ACTIVE','La quête doit être en cours.')
            quest=self.db.quests.find_one({'questId':quest_id},session=s)
            if not quest:raise EconomyError('QUEST_NOT_FOUND','Quête introuvable.',404)
            snapshot={'rule_version':RULE_VERSION,'money':str(legacy_money(quest.get('money',0))),
                'name':quest.get('name',quest_id),'rewards':quest.get('rewards',[]),'xp':quest.get('xp',{})}
            changes={'status':'COMPLETED','completedAt':datetime.now(timezone.utc),'reward_snapshot':snapshot}
            self.db.player_quest_states.update_one({'_id':state['_id']},{'$set':changes},session=s)
            self.db.economy_quest_completions.insert_one({'_id':completion_key,'owner_id':owner,'quest_id':quest_id,
                'proof_id':str(state['_id']),**changes},session=s)
            return {**state,**changes}
        return self.bank.transact(run)

    def pending_rewards(self,owner):
        rows=self.db.economy_quest_completions.aggregate([
            {'$match':{'owner_id':owner,'status':'COMPLETED','reward_snapshot.rule_version':RULE_VERSION}},
            {'$sort':{'completedAt':1}},
            {'$lookup':{'from':'economy_quest_rewards','localField':'_id','foreignField':'_id','as':'reward'}},
            {'$match':{'reward.material_state':{'$ne':'DELIVERED'}}},
            {'$limit':50},{'$project':{'quest_id':1}}
        ],maxTimeMS=2000)
        return list(dict.fromkeys(row['quest_id'] for row in rows))

    def reward(self, owner, actor, quest_id):
        """One bank credit per authorized completion; amount comes from the quest."""
        identifier(quest_id)
        key = 'quest:' + fingerprint({'owner': owner, 'quest': quest_id})
        def run(s):
            old = self.db.economy_quest_rewards.find_one({'_id': key}, session=s)
            if old: return old
            player = self.db.players.find_one({'id': owner}, session=s)
            if not player: raise EconomyError('OWNER_NOT_FOUND', 'Personnage introuvable.', 404)
            state = self.db.economy_quest_completions.find_one({'_id':key,'owner_id':owner,'status':'COMPLETED'},session=s)
            if not state: raise EconomyError('QUEST_NOT_COMPLETED', 'Accomplissement autorisé requis.')
            quest=state.get('reward_snapshot',{})
            if quest.get('rule_version')!=RULE_VERSION:
                raise EconomyError('LEGACY_REWARD_REVIEW','Cette ancienne quête peut déjà avoir été payée. Vérification requise.')
            value = legacy_money(quest.get('money', 0))
            if value:
                account = self.bank.account(owner, s)
                if account['available'] + account['reserved'] + account.get('incoming', 0) > MAX_MONEY - value:
                    raise EconomyError('BALANCE_LIMIT', 'La récompense dépasserait la limite bancaire.')
                self.bank.accounts.update_one({'_id': account['_id']}, {'$inc': {'available': value, 'revision': 1},'$set':{'updated_at':timestamp()}}, session=s)
                self.db.players.update_one({'id': owner}, {'$set': {'money': account['available'] + account['reserved'] + value}}, session=s)
            ident = str(uuid4()); now = timestamp()
            op = {'_id': ident, 'operation_id': ident, 'owner_id': owner, 'actor_id': actor,
                'key': key, 'request_hash': fingerprint({'quest': quest_id}), 'api_version': '1',
                'type': 'QUEST_REWARD', 'quest_id': quest_id, 'reason': quest.get('name', quest_id),
                'amount': value, 'currency': 'IRON', 'state': 'CONFIRMED', 'revision': 0,
                'rule_version': RULE_VERSION, 'proof_id': state['proof_id'], 'created_at': now, 'updated_at': now,
                'destination': 'BANK', 'rewards': quest.get('rewards', []), 'xp': quest.get('xp', {})}
            self.bank.operations.insert_one(op, session=s)
            row = {'_id': key, **{k: v for k, v in op.items() if k != '_id'}, 'material_state': 'PENDING'}
            self.db.economy_quest_rewards.insert_one(row, session=s)
            return row
        try: return self.bank.transact(run)
        except DuplicateKeyError:
            old = self.db.economy_quest_rewards.find_one({'_id': key})
            if old: return old
            raise
