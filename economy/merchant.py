"""Merchant pilot. All quantities, funds and progression share the receipt transaction.

No scheduler or tick polling: quotas and wholesale stock refill lazily, in real seconds.
An ACCEPTED order can expire; a physical DELIVERING receipt must be reconciled instead.
"""
import re
from datetime import datetime, timezone
from uuid import uuid4
from .domain import EconomyError, fingerprint, money, public, MAX_MONEY
from .store import timestamp

ITEMS = [('bread','Pain'),('wheat','Blé'),('candle','Bougie'),('torch','Torche'),
         ('oak_log','Bûche de chêne'),('stone','Pierre'),('coal','Charbon'),
         ('iron_ingot','Lingot de fer'),('paper','Papier'),('leather','Cuir')]
CITIES = ['Shaleton','Triomphe','Lone','Isvanore','Fyvelune']
ACTIVE = ['ACCEPTED','DELIVERING','RECONCILIATION_REQUIRED']


def integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise EconomyError('INVALID_REQUEST', f'Entier entre {lo} et {hi} requis.', 400)
    return value


def epoch(): return int(datetime.now(timezone.utc).timestamp())


def quota(row, capacity, seconds, now):
    """Preserve fractional time; held units count against capacity."""
    held = row.get('held', 0)
    elapsed = max(0, now-row.get('refilled_at', now))
    steps = elapsed // seconds
    available = min(max(0, capacity-held), row.get('available', capacity)+steps)
    return {**row, 'available': available, 'held': held,
            'refilled_at': now if available+held >= capacity else row.get('refilled_at',now)+steps*seconds}


class Merchant:
    def __init__(self, bank): self.bank, self.db = bank, bank.db

    def defaults(self):
        cities = list(self.db.market_cities.find({'active':True}, {'_id':0,'id':1,'name':1}).limit(250))
        selected=[]
        for name in CITIES:
            found=next((r for r in cities if r['name'].casefold()==name.casefold()), None)
            if found:selected.append({**found,'anchor':({'world':'minecraft:overworld','x':-716,'z':-1300,'radius':32} if name=='Shaleton' else None)})
        rows=[]
        for n,(item,label) in enumerate(ITEMS):
            for i,city in enumerate(selected):
                rows.append({'city_id':city['id'],'item_id':'minecraft:'+item,'name':label,
                    'source':i==n%len(selected),'manual_price':None,'capacity':128,
                    'refill_seconds':300,'supply_capacity':256,'supply_refill_seconds':120,
                    'sell_bps':8000 if i==n%len(selected) else 11000})
        return {'revision':0,'enabled':False,'budget_unlimited':True,'delivery_seconds':172800,
                'cities':selected,'offers':rows,'available_cities':cities}

    def config(self, s=None):
        row=self.db.merchant_config.find_one({'_id':'pilot'},session=s)
        return {k:v for k,v in row.items() if k!='_id'} if row else self.defaults()

    def save(self, body, actor):
        old=self.config()
        if body.get('revision')!=old['revision']:raise EconomyError('REVISION_CONFLICT','Configuration modifiée. Rechargez.')
        if type(body.get('enabled')) is not bool or type(body.get('budget_unlimited')) is not bool:
            raise EconomyError('INVALID_REQUEST','Activation et mode de budget requis.',400)
        duration=integer(body.get('delivery_seconds'),3600,604800)
        cities=body.get('cities'); offers=body.get('offers')
        if not isinstance(cities,list) or not 1<=len(cities)<=10 or not isinstance(offers,list) or len(offers)>100:
            raise EconomyError('INVALID_REQUEST','Entre 1 et 10 villes et 100 références maximum.',400)
        clean=[]; seen=set()
        for c in cities:
            city=self.db.market_cities.find_one({'id':c.get('id'),'active':True})
            if not city or city['id'] in seen:raise EconomyError('INVALID_CITY','Ville absente, inactive ou dupliquée.',400)
            seen.add(city['id']); anchor=c.get('anchor')
            if anchor is not None:
                if not isinstance(anchor,dict) or not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+',str(anchor.get('world',''))):
                    raise EconomyError('INVALID_ANCHOR','Dimension requise.',400)
                anchor={'world':anchor['world'],'x':integer(anchor.get('x'),-30000000,30000000),
                        'z':integer(anchor.get('z'),-30000000,30000000),'radius':integer(anchor.get('radius'),8,128)}
            if body['enabled'] and anchor is None:raise EconomyError('ANCHOR_REQUIRED','Placez un point de commerce dans chaque ville avant activation.',400)
            clean.append({'id':city['id'],'name':city['name'],'anchor':anchor})
        validated=[]; keys=set()
        allowed={'minecraft:'+i for i,_ in ITEMS}
        for o in offers:
            key=(o.get('city_id'),o.get('item_id'))
            if key in keys or key[0] not in seen or key[1] not in allowed:
                raise EconomyError('INVALID_OFFER','Article ou ville invalide, ou doublon.',400)
            keys.add(key)
            manual=o.get('manual_price')
            if manual is not None:manual=str(money(manual))
            if type(o.get('source')) is not bool:raise EconomyError('INVALID_REQUEST','Source requise.',400)
            validated.append({'city_id':key[0],'item_id':key[1], 'name':dict(('minecraft:'+i,n) for i,n in ITEMS)[key[1]],
                'source':o['source'],'manual_price':manual,
                'capacity':integer(o.get('capacity'),1,4096),'refill_seconds':integer(o.get('refill_seconds'),30,86400),
                'supply_capacity':integer(o.get('supply_capacity'),1,4096),
                'supply_refill_seconds':integer(o.get('supply_refill_seconds'),30,86400),
                'sell_bps':integer(o.get('sell_bps'),1000,15000)})
        result={'revision':old['revision']+1,'enabled':body['enabled'],'budget_unlimited':body['budget_unlimited'],
            'delivery_seconds':duration,'cities':clean,'offers':validated,'updated_by':actor,'updated_at':timestamp()}
        def run(s):
            current=self.db.merchant_config.find_one({'_id':'pilot'},session=s)
            if (current or {}).get('revision',0)!=old['revision']:raise EconomyError('REVISION_CONFLICT','Configuration modifiée.')
            self.db.merchant_config.replace_one({'_id':'pilot'},{'_id':'pilot',**result},upsert=True,session=s)
            for city in clean:
                for kind in ['supply','demand']:
                    bid='merchant:'+kind+':'+city['id']
                    self.db.economy_businesses.update_one({'_id':bid},{'$set':{'active':True,'label':('Fournisseur' if kind=='supply' else 'Commandes')+' — '+city['name'],
                        'label_search':('négoce '+city['name']).casefold(),'budget_unlimited':body['budget_unlimited'],
                        'budget_change_id':'merchant-config:'+str(result['revision'])},'$setOnInsert':{'business_id':bid,
                        'owner_id':'system:merchant','kind':'INN','tax_bps':0,'revision':0,'rule_version':'merchant-v1','created_at':timestamp()}},upsert=True,session=s)
                    self.bank.accounts.update_one({'_id':'cashbox:'+bid},{'$setOnInsert':{'owner_id':'system:merchant','business_id':bid,
                        'pocket':'CASHBOX','currency':'IRON','available':0,'reserved':0,'incoming':0,'revision':0,'opening_balance':0,'updated_at':timestamp()}},upsert=True,session=s)
            return result
        return self.bank.transact(run)

    def profile(self, owner, s=None):
        p=self.db.merchant_profiles.find_one({'_id':owner},session=s) or {'xp':0,'branch':'supply'}
        tier=2 if p['xp']>=500 else 1 if p['xp']>=100 else 0
        return {**{k:v for k,v in p.items() if k!='_id'},'tier':tier,
                'rank':['Colporteur','Négociant','Maître marchand'][tier],
                'contract_limit':2+tier+(1 if tier and p['branch']=='supply' else 0),
                'negotiation_bps':min(300,tier*100) if p['branch']=='specialty' else 0}

    def choose(self, owner, branch):
        if branch not in {'supply','shop','specialty'}:raise EconomyError('INVALID_REQUEST','Branche inconnue.',400)
        def run(s):
            p=self.db.merchant_profiles.find_one({'_id':owner},session=s) or {}
            if p.get('branch')!=branch and epoch()-p.get('chosen_at',0)<86400:
                raise EconomyError('BRANCH_COOLDOWN','Une orientation peut changer toutes les 24 heures réelles.')
            self.db.merchant_profiles.update_one({'_id':owner},{'$set':{'branch':branch,'chosen_at':epoch()},'$setOnInsert':{'xp':0}},upsert=True,session=s)
        self.bank.transact(run);return self.profile(owner)

    def quote(self, c, o, owner=None, s=None, context=None):
        if o['manual_price'] is None:
            if context is not None:r=context['prices'].get((o['city_id'],o['item_id']),{})
            else:
                latest=self.db.price_calculation_runs.find_one({'status':'SUCCESS'},sort=[('finished_at',-1)],session=s)
                q={'city_id':o['city_id'],'item_id':o['item_id'],'market_type':'CITY_MARKET'}
                if latest:q['calculation_version']=latest['calculation_version']
                r=self.db.calculated_market_prices.find_one(q,sort=[('updated_at',-1)],session=s) or {}
            base=int(r.get('calculated_price') or 0)
        else:base=int(o['manual_price'])
        if not 0<base<=MAX_MONEY//16000:base=0
        ident=fingerprint({'city':o['city_id'],'item':o['item_id']})
        state=(context['demand'].get(ident) if context is not None else self.db.merchant_demand.find_one({'_id':ident},session=s)) or {}
        state=quota(state,o['capacity'],o['refill_seconds'],epoch())
        # Saturation discounts at most 15%; accepted orders keep their frozen price.
        bps=o['sell_bps']*(8500+1500*state['available']//o['capacity'])//10000
        if owner:bps=bps*(10000+(context['profile'] if context is not None else self.profile(owner,s))['negotiation_bps'])//10000
        city=next(x for x in c['cities'] if x['id']==o['city_id'])
        buy=max(1,base*8000//10000) if base and o['source'] else 0
        sell=max(1,base*bps//10000) if base and not o['source'] else 0
        stock_id=fingerprint({'business':'merchant:supply:'+o['city_id'],'offer':o['item_id']})
        offer=context['supplies'].get(stock_id) if context is not None else self.db.economy_offers.find_one({'_id':stock_id},session=s)
        supply=quota({'available':offer.get('stock',0),'held':offer.get('reserved_stock',0),'refilled_at':offer.get('refilled_at',epoch())},o['supply_capacity'],o['supply_refill_seconds'],epoch()) if offer else {'available':o['supply_capacity'],'refilled_at':epoch()}
        version=fingerprint({'revision':c['revision'],'buy':buy,'sell':sell,'available':state['available'],'item':ident})
        return {**o,'city_name':city['name'],'anchor':city['anchor'],'demand':state['available'],
            'buy_price':str(buy),'sell_price':str(sell),'stock':supply['available'],
            'price_version':version,'price_required':not base,'observed_at':timestamp(),
            'supply_refilled_at':supply['refilled_at'],
            'business_id':'merchant:supply:'+o['city_id'],'nbt':'{id:"'+o['item_id']+'",Count:1b}'}

    def notebook(self, owner):
        self.expire()
        c=self.config()
        profile=self.profile(owner)
        context={'profile':profile,'prices':{},'demand':{},'supplies':{}}
        if c['enabled']:
            latest=self.db.price_calculation_runs.find_one({'status':'SUCCESS'},sort=[('finished_at',-1)])
            q={'city_id':{'$in':[city['id'] for city in c['cities']]},'market_type':'CITY_MARKET',
                'item_id':{'$in':[o['item_id'] for o in c['offers']]}}
            if latest:q['calculation_version']=latest['calculation_version']
            for row in self.db.calculated_market_prices.find(q).sort('updated_at',-1).limit(200):context['prices'].setdefault((row['city_id'],row['item_id']),row)
            ids=[fingerprint({'city':o['city_id'],'item':o['item_id']}) for o in c['offers']]
            context['demand']={row['_id']:row for row in self.db.merchant_demand.find({'_id':{'$in':ids}})}
            bids=['merchant:supply:'+city['id'] for city in c['cities']]
            context['supplies']={row['_id']:row for row in self.db.economy_offers.find({'business_id':{'$in':bids}}).limit(100)}
        rows=[self.quote(c,o,owner,context=context) for o in c['offers']] if c['enabled'] else []
        contracts=list(self.db.merchant_contracts.find({'owner_id':owner}).sort('accepted_at',-1).limit(50))
        ledger=list(self.db.merchant_ledger.find({'owner_id':owner}).sort('created_at',-1).limit(100))
        return {'enabled':c['enabled'],'delivery_seconds':c['delivery_seconds'],'cities':c['cities'],'offers':rows,'profile':profile,
                'contracts':[self.visible(x) for x in contracts],'ledger':[self.visible(x) for x in ledger],
                'observed_at':timestamp()}

    @staticmethod
    def visible(row):
        fields={'amount','cost','profit','unit_price','buy_price','sell_price'}
        return {k:(str(v) if k in fields and v is not None else v) for k,v in row.items() if k not in {'_id','request','actor_id'}}

    def accept(self, owner, key, body):
        from .commerce import Commerce
        if not isinstance(key,str) or not 1<=len(key)<=100:raise EconomyError('INVALID_REQUEST','Clé de réservation requise.',400)
        qty=integer(body.get('quantity'),1,256)
        self.expire()
        ident=fingerprint({'owner':owner,'key':key})
        digest=fingerprint(body)
        def run(s):
            previous=self.db.merchant_contracts.find_one({'_id':ident},session=s)
            if previous:
                if previous['request_hash']!=digest:raise EconomyError('IDEMPOTENCY_CONFLICT','Réservation différente pour cette clé.')
                return self.visible(previous)
            c=self.config(s); o=next((o for o in c['offers'] if o['city_id']==body.get('city_id') and o['item_id']==body.get('item_id')),None)
            if not c['enabled'] or not o or o['source']:raise EconomyError('OFFER_UNAVAILABLE','Cette référence n’est pas un besoin à approvisionner.')
            self.db.merchant_config.update_one({'_id':'pilot'},{'$inc':{'reservation_revision':1}},session=s)
            # Serialize per-owner reservations even when two different cities are accepted concurrently.
            self.db.merchant_profiles.update_one({'_id':owner},{'$inc':{'reservation_revision':1},'$setOnInsert':{'xp':0,'branch':'supply'}},upsert=True,session=s)
            p=self.profile(owner,s)
            if self.db.merchant_contracts.count_documents({'owner_id':owner,'state':{'$in':ACTIVE}},session=s)>=p['contract_limit']:
                raise EconomyError('CONTRACT_LIMIT','Terminez ou annulez une commande avant d’en réserver une autre.')
            q=self.quote(c,o,owner,s)
            if q['price_required']:raise EconomyError('PRICE_REQUIRED','Prix à définir par un administrateur.')
            if body.get('price_version')!=q['price_version']:raise EconomyError('PRICE_CHANGED','Le prix a changé. Actualisez le carnet.')
            did=fingerprint({'city':o['city_id'],'item':o['item_id']})
            d=quota(self.db.merchant_demand.find_one({'_id':did},session=s) or {},o['capacity'],o['refill_seconds'],epoch())
            if d['available']<qty:raise EconomyError('DEMAND_EXHAUSTED','Cette ville n’a plus besoin de cette quantité.')
            self.db.merchant_demand.replace_one({'_id':did},{**d,'_id':did,'available':d['available']-qty,'held':d['held']+qty},upsert=True,session=s)
            player=self.db.players.find_one({'id':owner},session=s) or {}
            mc=player.get('id_minecraft')
            if not mc:raise EconomyError('OWNER_NOT_LINKED','Liez votre compte Minecraft avant de réserver.')
            actor='minecraft:'+mc; bid='merchant:demand:'+o['city_id']; offer='contract:'+ident
            version=q['price_version']; price=int(q['sell_price'])
            self.db.economy_offers.insert_one({'_id':fingerprint({'business':bid,'offer':offer}),'business_id':bid,'offer_id':offer,
                'version':version,'buy_price':price,'sell_price':price,'stock':None,'reserved_stock':0,'incoming_stock':0,'item_nbt':q['nbt']},session=s)
            request={'business_id':bid,'offer_id':offer,'price_version':version,'action':'SELL','unit_price':str(price),
                'quantity':qty,'payment':'CASH','item_id':o['item_id'],'item_display_name':o['name'],'merchant_contract_id':ident}
            opkey=str(uuid4());request['idempotency_key']=opkey
            op=Commerce(self.bank).prepare(owner,actor,opkey,request,session=s,_merchant_internal=True)
            row={'_id':ident,'id':ident,'owner_id':owner,'actor_id':actor,'request_hash':digest,'city_id':o['city_id'],
                'city_name':q['city_name'],'item_id':o['item_id'],'name':o['name'],'anchor':q['anchor'],'nbt':q['nbt'],
                'quantity':qty,'unit_price':price,'amount':price*qty,'state':'ACCEPTED','demand_id':did,
                'accepted_at':timestamp(),'expires_at':epoch()+c['delivery_seconds'],'request':request,'receipt_id':op['_id'],'key':opkey}
            self.db.merchant_contracts.insert_one(row,session=s)
            return self.visible(row)
        return self.bank.transact(run)

    def cancel(self, owner, ident, expired=False):
        from .commerce import Commerce
        def run(s):
            row=self.db.merchant_contracts.find_one({'_id':ident,'owner_id':owner},session=s)
            if not row:raise EconomyError('CONTRACT_NOT_FOUND','Commande introuvable.',404)
            if row['state'] in ['CANCELLED','EXPIRED']:return self.visible(row)
            if row['state']!='ACCEPTED':raise EconomyError('RECEIPT_PENDING','Remise en cours : vérifiez le reçu avant d’annuler.')
            state='EXPIRED' if expired else 'CANCELLED'
            self.db.merchant_contracts.update_one({'_id':ident},{'$set':{'state':state}},session=s)
            op=self.bank.operations.find_one({'_id':row['receipt_id']},session=s)
            if op and op['state']=='RESERVED':Commerce(self.bank).transition(op['_id'],row['actor_id'],'cancel',op['revision'],'merchant-cancel:'+ident,session=s)
            self.db.merchant_demand.update_one({'_id':row['demand_id']},{'$inc':{'available':row['quantity'],'held':-row['quantity']}},session=s)
            return self.visible({**row,'state':state})
        return self.bank.transact(run)

    def expire(self):
        for row in self.db.merchant_contracts.find({'state':'ACCEPTED','expires_at':{'$lte':epoch()}},{'_id':1,'owner_id':1}).limit(10):
            try:self.cancel(row['owner_id'],row['_id'],True)
            except EconomyError as e:
                if e.code!='RECEIPT_PENDING':raise

    def delivery(self, owner, ident):
        row=self.db.merchant_contracts.find_one({'_id':ident,'owner_id':owner})
        if not row or row['state'] not in ACTIVE:raise EconomyError('CONTRACT_NOT_FOUND','Commande inactive.',404)
        if row['state']=='ACCEPTED' and row['expires_at']<=epoch():
            self.cancel(owner,ident,True);raise EconomyError('CONTRACT_EXPIRED','La fenêtre de livraison est terminée.')
        return {**self.visible(row),'request':row['request']}

    def validate_prepare(self, owner, actor, body, s, previous=None):
        """Only called within Commerce's transaction, after the local journal exists."""
        bid=body['business_id']
        if previous and previous['state'] in ['CONFIRMED','CANCELLED','RECONCILIATION_REQUIRED']:return
        if previous and bid.startswith('merchant:supply:'):return
        if bid.startswith('merchant:demand:'):
            row=self.db.merchant_contracts.find_one({'_id':body.get('merchant_contract_id'),'owner_id':owner,'actor_id':actor},session=s)
            if not row or row['state'] not in ['ACCEPTED','DELIVERING']:
                # Historical receipts remain recoverable after confirmation/cancellation.
                if previous and previous['state'] in ['CONFIRMED','CANCELLED','RECONCILIATION_REQUIRED']:return
                raise EconomyError('CONTRACT_NOT_FOUND','Commande indisponible.')
            expected={k:v for k,v in row['request'].items() if k!='idempotency_key'}
            if {k:v for k,v in body.items() if k!='idempotency_key'}!=expected:raise EconomyError('INVALID_CONTRACT','Les termes réservés ont été modifiés.')
            if row['state']=='ACCEPTED' and row['expires_at']<=epoch():raise EconomyError('CONTRACT_EXPIRED','Commande expirée.')
            if not previous and row['state']=='DELIVERING':raise EconomyError('RECEIPT_PENDING','Livraison déjà en cours.')
            if not previous:
                old=self.bank.operations.find_one({'_id':row['receipt_id']},session=s)
                if old and old['state']!='CANCELLED':raise EconomyError('RECEIPT_PENDING','Une remise retient déjà les fonds.')
            self.db.merchant_contracts.update_one({'_id':row['_id']},{'$set':{'state':'DELIVERING'}},session=s)
        elif bid.startswith('merchant:supply:'):
            c=self.config(s);city=bid[len('merchant:supply:'):]
            o=next((o for o in c['offers'] if o['city_id']==city and o['item_id']==body.get('offer_id')),None)
            if not c['enabled'] or not o or not o['source'] or body.get('action')!='BUY' or body.get('payment')!='CASH':
                raise EconomyError('OFFER_UNAVAILABLE','Fournisseur indisponible.')
            q=self.quote(c,o,owner,s)
            if q['price_required'] or q['price_version']!=body.get('price_version') or q['buy_price']!=body.get('unit_price'):
                raise EconomyError('PRICE_CHANGED','Le prix a changé. Actualisez le carnet.')
            if body.get('item_id')!=o['item_id']:raise EconomyError('INVALID_ITEM','Référence incohérente.')
            sid=fingerprint({'business':bid,'offer':o['item_id']})
            old_stock=self.db.economy_offers.find_one({'_id':sid},session=s)
            added=q['stock']-(old_stock.get('stock',0) if old_stock else 0)
            if added>0:self.db.merchant_stock_events.insert_one({'_id':str(uuid4()),'business_id':bid,
                'item_id':o['item_id'],'quantity':added,'reason':'INITIAL_SUPPLY' if not old_stock else 'REAL_TIME_REFILL',
                'created_at':timestamp()},session=s)
            self.db.economy_offers.update_one({'_id':sid},{'$set':{'version':q['price_version'],'buy_price':int(q['buy_price']),
                'sell_price':0,'item_nbt':q['nbt'],'stock':q['stock'],'refilled_at':q['supply_refilled_at']},
                '$setOnInsert':{'business_id':bid,'offer_id':o['item_id'],'reserved_stock':0,'incoming_stock':0,'opening_stock':o['supply_capacity']}},upsert=True,session=s)

    def prepared(self, op, s):
        if op.get('merchant_contract_id'):
            self.db.merchant_contracts.update_one({'_id':op['merchant_contract_id']},{'$set':{'receipt_id':op['_id']}},session=s)

    def settled(self, op, action, s):
        cid=op.get('merchant_contract_id')
        if cid:
            row=self.db.merchant_contracts.find_one({'_id':cid},session=s)
            if action=='cancel' and row['state'] in ['CANCELLED','EXPIRED']:return
            state={'delivery':'DELIVERED','cancel':'ACCEPTED','reconcile':'RECONCILIATION_REQUIRED'}[action]
            self.db.merchant_contracts.update_one({'_id':cid},{'$set':{'state':state,'updated_at':timestamp()}},session=s)
            if action=='delivery':
                self.db.merchant_demand.update_one({'_id':row['demand_id']},{'$inc':{'held':-row['quantity']}},session=s)
                self.gain_xp(op['owner_id'],'city:'+row['city_id'],row['item_id'],op['quantity'],s)
        if action!='delivery' or op['action'] not in ['BUY','SELL'] or not op.get('item_id'):return
        if op['business_id'].startswith('market:') and op.get('business_owner_id')==op['owner_id']:return
        self.record_ledger(op,s,op['owner_id'],op['action'],op['amount'],op['_id'])
        business_owner=op.get('business_owner_id','')
        if op['business_id'].startswith('market:') and business_owner and not business_owner.startswith('system:') and business_owner!=op['owner_id']:
            action='SELL' if op['action']=='BUY' else 'BUY'
            amount=op['amount']-op.get('tax',0) if action=='SELL' else op['amount']
            self.record_ledger(op,s,business_owner,action,amount,op['_id']+':owner')

    def record_ledger(self, op, s, owner, action, amount, ledger_id):
        # Weighted average recorded cost; external goods never get a fictitious zero cost.
        item=op['item_id'];qty=op['quantity'];ident=fingerprint({'owner':owner,'item':item})
        inv=self.db.merchant_cost_basis.find_one({'_id':ident},session=s) or {'quantity':0,'cost':0}
        cost=None;profit=None
        if action=='BUY':
            inv={**inv,'quantity':inv['quantity']+qty,'cost':inv['cost']+amount};cost=amount
        else:
            known=min(qty,inv['quantity']);used=inv['cost']*known//inv['quantity'] if inv['quantity'] else 0
            inv={**inv,'quantity':inv['quantity']-known,'cost':inv['cost']-used}
            if known==qty:cost=used;profit=amount-cost
        if inv['cost']>MAX_MONEY or inv['quantity']>MAX_MONEY:
            # Losing precision is worse than explicitly marking an exceptional cost as unknown.
            inv={'quantity':0,'cost':0};cost=profit=None
        self.db.merchant_cost_basis.replace_one({'_id':ident},{'_id':ident,**inv},upsert=True,session=s)
        self.db.merchant_ledger.insert_one({'_id':ledger_id,'id':ledger_id,'owner_id':owner,'item_id':item,
            'name':op.get('item_display_name',item),'action':action,'quantity':qty,'amount':amount,
            'cost':cost,'profit':profit,'contract_id':op.get('merchant_contract_id'),'business_id':op['business_id'],
            'counterparty':op['owner_id'] if owner!=op['owner_id'] else op.get('business_owner_id'),
            'created_at':timestamp()},session=s)
        if owner!=op['owner_id'] and action=='SELL' and profit is not None and profit>0:
            cutoff=datetime.fromtimestamp(epoch()-86400,timezone.utc).isoformat()
            returned=self.db.merchant_ledger.find_one({'owner_id':owner,'action':'BUY','item_id':item,
                'counterparty':op['owner_id'],'created_at':{'$gte':cutoff}},session=s)
            if not returned:self.gain_xp(owner,'client:'+op['owner_id'],item,qty,s)

    def gain_xp(self, owner, client, item, quantity, s):
        # Cumulative units prevent click splitting. Caps apply per city/client and item in a UTC day.
        bucket=fingerprint({'owner':owner,'client':client,'item':item,'day':epoch()//86400})
        cap=self.db.merchant_xp_caps.find_one({'_id':bucket},session=s) or {'quantity':0}
        total=min(256,cap['quantity']+quantity);gain=total//8-cap['quantity']//8
        self.db.merchant_xp_caps.update_one({'_id':bucket},{'$set':{'quantity':total}},upsert=True,session=s)
        self.db.merchant_profiles.update_one({'_id':owner},{'$inc':{'xp':gain},'$setOnInsert':{'branch':'supply'}},upsert=True,session=s)
        player=self.db.players.find_one({'id':owner},{'experiences.jobs.merchant':1},session=s) or {}
        job=player.get('experiences',{}).get('jobs',{}).get('merchant',{})
        xp=job.get('xp',-1)
        if type(xp) is int and xp>=0:
            from jobs.progression import level_from_xp
            xp=min(2147483647,xp+gain)
            self.db.players.update_one({'id':owner},{'$set':{'experiences.jobs.merchant.xp':xp,
                'experiences.jobs.merchant.level':level_from_xp(xp)}},session=s)
