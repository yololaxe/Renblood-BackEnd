"""NPC boutiques use the existing cashbox, stock reservations and receipts.

No money, inventory or market activity is changed by browsing a catalogue.
"""
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid5, NAMESPACE_URL
from .commerce import Commerce
from .domain import EconomyError, money, fingerprint, public
from .store import timestamp


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise EconomyError('INVALID_REQUEST', label + ' invalide.', 400)
    return value


def text(value, maximum, label, empty=False):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()) or any(ord(c) < 32 for c in value):
        raise EconomyError('INVALID_REQUEST', label + ' invalide.', 400)
    return value.strip()


def uuid(value):
    try: return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise EconomyError('INVALID_REQUEST', 'Identifiant de boutique invalide.', 400)


class NpcShops:
    def __init__(self, bank):
        self.bank, self.db = bank, bank.db
        self.commerce = Commerce(bank)

    def metadata(self, city_id=None):
        from markets.npc_clock import refresh_if_due
        refresh_if_due(self.bank)
        cities = list(self.db.market_cities.find({'active': True}, {'_id': 0, 'id': 1, 'name': 1}).sort('name', 1).limit(200))
        if city_id and not any(c['id'] == city_id for c in cities):
            raise EconomyError('INVALID_CITY', 'Ville inconnue ou inactive.', 400)
        references = list(self.db.market_item_references.find({'enabled': True}, {'_id': 0}).limit(2000))
        current = {}
        if city_id:
            query={'city_id': city_id, 'market_type': 'CITY_MARKET'}
            latest=self.db.price_calculation_runs.find_one({'status':'SUCCESS'},sort=[('finished_at',-1)])
            if latest:query['calculation_version']=latest['calculation_version']
            current = {r['item_id']: r for r in self.db.calculated_market_prices.find(query).limit(2000)}
        config = self.db.market_economy_config.find_one({}) or {}
        pressure = {}
        if config.get('dynamic_economy_enabled'):
            for r in self.db.market_activity_modifiers.find({'city_id': None}).sort('period_end', -1).limit(2000):
                pressure.setdefault(r['item_id'], Decimal(str(r.get('activity_modifier', '1'))))
        rows = []
        for ref in references:
            local = current.get(ref['item_id'])
            price = local.get('calculated_price') if local else (ref.get('reference_price') if not city_id else None)
            if price and not city_id:
                ratio = max(Decimal('0.85'), min(Decimal('1.15'), pressure.get(ref['item_id'], Decimal(1))))
                price = int((Decimal(price) * ratio).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                price = max(ref.get('min_price', 1), price)
                if ref.get('max_price') is not None: price = min(price, ref['max_price'])
            rows.append({'item_id': ref['item_id'], 'name': ref.get('display_name', ref['item_id']),
                         'price': str(price) if price else None, 'reference': str(ref['reference_price']),
                         'version': local.get('calculation_version', '') if local else 'common',
                         'category': ref.get('category', 'OTHER')})
        return {'cities': cities, 'references': rows, 'city_id': city_id, 'observed_at': timestamp()}

    def save(self, body, actor):
        ident = uuid(body.get('id')); old = self.db.npc_shops.find_one({'_id': ident})
        expected = integer(body.get('revision', 0), 0, 2147483647, 'Version')
        city = body.get('city_id') or None
        if city and not self.db.market_cities.find_one({'id': city, 'active': True}):
            raise EconomyError('INVALID_CITY', 'Ville inconnue ou inactive.', 400)
        entries = body.get('offers', [])
        if not isinstance(entries, list) or len(entries) > 54:
            raise EconomyError('INVALID_REQUEST', 'Une boutique accepte au maximum 54 articles.', 400)
        prices = {r['item_id']: r for r in self.metadata(city)['references']}
        offers = []; seen = set()
        for entry in entries:
            item = text(entry.get('item_id'), 160, 'Objet')
            if not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', item):
                raise EconomyError('INVALID_REQUEST', 'Objet inconnu.', 400)
            nbt = text(entry.get('nbt'), 2048, 'Objet sérialisé')
            key = fingerprint({'item': item, 'nbt': nbt})[:24]
            if key in seen: raise EconomyError('INVALID_REQUEST', 'Cet article figure déjà dans la boutique.', 400)
            seen.add(key)
            auto = entry.get('automatic', True)
            if type(auto) is not bool: raise EconomyError('INVALID_REQUEST', 'Mode de prix invalide.', 400)
            buy = money(entry.get('buy_price', '0'), zero=True)
            sell = money(entry.get('sell_price', '0'), zero=True)
            if auto and not (prices.get(item) or {}).get('price'):
                # A missing quote is a manual draft, never an executable zero price.
                auto, buy, sell = False, 0, 0
            enabled_buy, enabled_sell = entry.get('buy_enabled', True), entry.get('sell_enabled', False)
            if type(enabled_buy) is not bool or type(enabled_sell) is not bool: raise EconomyError('INVALID_REQUEST', 'Modes de vente invalides.', 400)
            if not auto and enabled_buy and enabled_sell and buy and sell > buy:
                raise EconomyError('INVALID_REQUEST', 'Le prix de rachat dépasse le prix de vente.', 400)
            stock = entry.get('stock')
            if stock is not None: integer(stock, 0, 1000000, 'Stock')
            if entry.get('restock_seconds', 0) not in {0} and entry.get('restock_seconds', 0) < 60:
                raise EconomyError('INVALID_REQUEST', 'Recharge minimale : 60 secondes, ou 0 pour désactiver.', 400)
            offers.append({'id': key, 'item_id': item, 'nbt': nbt, 'name': text(entry.get('name', item), 100, 'Nom article'),
                           'automatic': auto, 'buy_enabled': enabled_buy, 'sell_enabled': enabled_sell,
                           'buy_price': str(buy), 'sell_price': str(sell), 'stock': stock,
                           'lot': integer(entry.get('lot', 1), 1, 64, 'Lot'),
                           'restock_seconds': integer(entry.get('restock_seconds', 0), 0, 86400, 'Réapprovisionnement'),
                           'restock_target': integer(entry.get('restock_target', stock or 0), 0, 1000000, 'Plafond')})
        row = {'_id': ident, 'id': ident, 'name': text(body.get('name'), 64, 'Nom'),
               'skin': text(body.get('skin', 'textures/entity/banker.png'), 256, 'Skin'),
               'city_id': city, 'offers': offers, 'active': body.get('active', True),
               'world': text(body.get('world', 'minecraft:overworld'), 100, 'Dimension'),
               'revision': expected + 1, 'updated_at': timestamp(), 'updated_by': actor}
        if type(row['active']) is not bool: raise EconomyError('INVALID_REQUEST', 'Activation invalide.', 400)
        business = 'npcshop:' + ident
        self.commerce.register(business, 'system:' + business, row['name'], 'MARKET')
        def write(s):
            previous = self.db.npc_shops.find_one({'_id': ident}, session=s)
            if (previous or {}).get('revision', 0) != expected:
                raise EconomyError('VERSION_CONFLICT', 'Boutique modifiée ailleurs. Rechargez avant de remplacer.')
            # Pending physical handovers must retain their exact item and stock.
            pending = self.db.economy_operations.find_one({'business_id': business, 'state': {'$in': ['RESERVED', 'RECONCILIATION_REQUIRED']}}, session=s)
            if pending: raise EconomyError('EXCHANGE_PENDING', 'Un échange est en cours ou doit être rapproché.')
            for offer in offers:
                stock_id = fingerprint({'business': business, 'offer': offer['id']})
                existing = self.db.economy_offers.find_one({'_id': stock_id}, session=s)
                if existing:
                    original = next(e for e in entries if fingerprint({'item': e['item_id'], 'nbt': e['nbt']})[:24] == offer['id'])
                    if 'stock_seen' in original and original['stock_seen'] != existing.get('stock'):
                        raise EconomyError('VERSION_CONFLICT', 'Le stock a changé pendant la modification. Rechargez la boutique.')
                    self.db.economy_offers.update_one({'_id': stock_id}, {'$set': {'stock': offer['stock'], 'opening_stock': offer['stock'], 'restocked_at': timestamp()}}, session=s)
            self.db.npc_shops.replace_one({'_id': ident}, row, upsert=True, session=s)
            self.db.economy_businesses.update_one({'_id': business}, {'$set': {'active': row['active'], 'label': row['name'], 'label_search': row['name'].casefold()}}, session=s)
            self.db.npc_shop_audit.insert_one({'shop_id': ident, 'revision': row['revision'], 'actor': actor, 'at': timestamp(), 'previous': previous}, session=s)
        self.bank.transact(write)
        return self.catalogue(ident, include_inactive=True)

    def catalogue(self, ident, include_inactive=False):
        shop = self.db.npc_shops.find_one({'_id': uuid(ident)})
        if not shop or (not shop['active'] and not include_inactive):
            raise EconomyError('SHOP_UNAVAILABLE', 'Boutique absente ou fermée.', 404)
        metadata = self.metadata(shop.get('city_id')); prices = {r['item_id']: r for r in metadata['references']}
        result = {k: v for k, v in shop.items() if k not in {'_id', 'updated_by'}}; result['offers'] = []
        business = 'npcshop:' + ident
        stored_offers={r['offer_id']:r for r in self.db.economy_offers.find({'business_id':business}).limit(54)}
        for item in shop['offers']:
            current = prices.get(item['item_id']); buy, sell = int(item['buy_price']), int(item['sell_price'])
            automatic = item['automatic'] and bool(current and current['price'])
            available = True
            if item['automatic']:
                available = bool(current and current['price'])
                buy = int(current['price']) if available else 0
                sell = max(1, buy * 80 // 100) if available else 0
            if not item['buy_enabled']: buy = 0
            if not item['sell_enabled']: sell = 0
            buy_available = item['buy_enabled'] and buy > 0
            sell_available = item['sell_enabled'] and sell > 0
            available = available and (buy_available or sell_available)
            price_required = (item['buy_enabled'] and not buy) or (item['sell_enabled'] and not sell)
            price_reason = ('NO_REFERENCE' if not current else 'NO_CITY_QUOTE') if not (current or {}).get('price') else 'MANUAL_PRICE_REQUIRED'
            version = fingerprint({'revision': shop['revision'], 'buy': buy, 'sell': sell, 'id': item['id']})[:32]
            # Admin may inspect suspended shops without registering an executable quote.
            stock_id = fingerprint({'business': business, 'offer': item['id']})
            stored = stored_offers.get(item['id'], {})
            if shop['active'] and stored.get('version')!=version:
                stored=self.commerce.offer(business, item['id'], version, str(buy), str(sell), item['stock'], item['nbt'])
            if shop['active'] and item['stock'] is not None and item['restock_seconds'] >= 60:
                def restock(s):
                    state = self.db.economy_offers.find_one({'_id': stock_id}, session=s)
                    if not state: return
                    last = datetime.fromisoformat(state.get('restocked_at', shop['updated_at']))
                    if (datetime.now(timezone.utc) - last).total_seconds() < item['restock_seconds']: return
                    ceiling = max(0, item['restock_target'] - state.get('reserved_stock', 0) - state.get('incoming_stock', 0))
                    value = max(state['stock'], ceiling)
                    self.db.economy_offers.update_one({'_id': stock_id}, {'$set': {'stock': value, 'restocked_at': timestamp()}}, session=s)
                self.bank.transact(restock)
                stored = self.db.economy_offers.find_one({'_id': stock_id}) or stored
            reference = int(current['reference']) if current else buy
            result['offers'].append({**item, 'automatic': automatic, 'buy_price': str(buy), 'sell_price': str(sell), 'price_version': version,
                                     'auto_available': bool(current and current['price']), 'price_required': bool(price_required),
                                     'price_reason': price_reason if price_required else None,
                                     'buy_available': bool(buy_available), 'sell_available': bool(sell_available),
                                     'available': available, 'stock': stored.get('stock', item['stock']),
                                     'stock_seen': stored.get('stock', item['stock']),
                                     'trend': ('UP' if buy > reference else 'DOWN' if buy < reference else 'STABLE') if buy else 'UNPRICED'})
        result['city_name'] = next((c['name'] for c in metadata['cities'] if c['id'] == shop.get('city_id')), 'Cours commun')
        result['cities'] = metadata['cities']
        result['references'] = metadata['references']
        return result

    def prepare(self, ident, owner, actor, body):
        shop = self.catalogue(ident)
        offer = next((o for o in shop['offers'] if o['id'] == body.get('offer_id')), None)
        if not offer or not offer['available']: raise EconomyError('OFFER_UNAVAILABLE', 'Article indisponible.')
        if body.get('action') not in {'BUY', 'SELL'}: raise EconomyError('INVALID_REQUEST', 'Action invalide.', 400)
        price = offer['buy_price'] if body['action'] == 'BUY' else offer['sell_price']
        if int(price) <= 0:
            raise EconomyError('PRICE_REQUIRED', 'Prix à définir par un administrateur avant cet échange.')
        return self.commerce.prepare(owner, actor, body.get('idempotency_key'), {
            'business_id': 'npcshop:' + ident, 'offer_id': offer['id'], 'price_version': body.get('price_version'),
            'action': body['action'], 'unit_price': body.get('unit_price'), 'quantity': body.get('quantity'), 'payment': 'CASH',
        })

    def record_delivery(self, op, session):
        """Called inside the one successful receipt transition, never on browsing."""
        ident = op['business_id'][8:]; shop = self.db.npc_shops.find_one({'_id': ident}, session=session)
        if not shop: return
        player = self.db.players.find_one({'id': op['owner_id']}, session=session) or {}
        entry = next((e for e in shop['offers'] if e['id'] == op.get('offer_id')), None)
        if not entry: return
        self.db.market_transactions.insert_one({'id': op['_id'], 'operation_id': op['_id'], 'counter_id': ident,
            'city_id': shop.get('city_id'), 'player_uuid': player.get('id_minecraft', ''), 'player_name': player.get('name', op['owner_id']), 'owner_type': 'ADMIN',
            'owner_id': None, 'item_id': entry['item_id'], 'item_display_name': entry['name'],
            'action': op['action'], 'quantity': op['quantity'], 'unit_price': op['unit_price'],
            'total_price': op['amount'], 'owner_gain': op['amount'] if op['action'] == 'BUY' else 0,
            'tax': op['tax'], 'price_version': op['price_version'], 'rule_version': 'npc-shops-v1',
            'created_at': datetime.now(timezone.utc)}, session=session)


def contract_terms(bank, body):
    offer = text(body.get('offer'), 160, 'Contrat')
    if not offer.startswith('contract:'): raise EconomyError('INVALID_REQUEST', 'Contrat requis.', 400)
    city = body.get('city_id') or None
    if city and not bank.db.market_cities.find_one({'id': city, 'active': True}):
        raise EconomyError('INVALID_CITY', 'Ville invalide.', 400)
    items = body.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 4: raise EconomyError('INVALID_REQUEST', 'Lots invalides.', 400)
    rows = []
    for row in items:
        rows.append({'item_id': text(row.get('item_id'), 160, 'Objet'), 'quantity': integer(row.get('quantity'), 1, 64, 'Quantité'), 'price': money(row.get('price'))})
    data = {'_id': offer, 'city_id': city, 'items': rows}
    def save(s):
        previous = bank.db.npc_contract_terms.find_one({'_id': offer}, session=s)
        if previous and previous != data: raise EconomyError('VERSION_CONFLICT', 'Les conditions du contrat sont déjà figées.')
        if not previous: bank.db.npc_contract_terms.insert_one(data, session=s)
    bank.transact(save)
    return {'saved': True}


def record_contract_delivery(db, op, session):
    terms = db.npc_contract_terms.find_one({'_id': op.get('offer_id')}, session=session)
    if not terms: return  # Legacy contracts retain their original accounting.
    for index, row in enumerate(terms['items']):
        db.market_transactions.insert_one({'id': str(uuid5(NAMESPACE_URL, op['_id']+':'+str(index))), 'operation_id': op['_id'],
            'counter_id': None, 'city_id': terms['city_id'], 'player_uuid': '', 'player_name': op['owner_id'],
            'owner_type': 'ADMIN', 'owner_id': None, 'item_id': row['item_id'], 'item_display_name': row['item_id'],
            'action': 'SELL', 'quantity': row['quantity'], 'unit_price': row['price'], 'total_price': row['price']*row['quantity'],
            'owner_gain': 0, 'tax': 0, 'price_version': op['price_version'], 'rule_version': 'npc-contracts-v1',
            'created_at': datetime.now(timezone.utc)}, session=session)
