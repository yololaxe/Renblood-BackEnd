"""Mongo transactions bypass Djongo's incomplete transaction emulation."""
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID, uuid4
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from .domain import EconomyError, MAX_MONEY, money, legacy_money, fingerprint, public

def timestamp(): return datetime.now(timezone.utc).isoformat()

class Bank:
    def __init__(self, database):
        self.db=database; self.accounts=database.economy_accounts; self.operations=database.economy_operations

    def check_storage(self):
        hello=self.db.client.admin.command('hello')
        if not hello.get('setName') and hello.get('msg')!='isdbgrid':
            raise EconomyError('STORAGE_UNAVAILABLE','La banque exige un stockage transactionnel.',503)

    def initialize(self):
        self.check_storage()
        self.operations.create_index([('actor_id',ASCENDING),('key',ASCENDING)],unique=True)
        self.operations.create_index('original_operation_id',unique=True,partialFilterExpression={'original_operation_id':{'$exists':True}})
        self.operations.create_index([('owner_id',ASCENDING),('created_at',-1),('_id',-1)])
        self.operations.create_index([('participant_owner_ids',ASCENDING),('created_at',-1),('_id',-1)])
        self.accounts.create_index([('owner_id', ASCENDING), ('pocket', ASCENDING), ('_id', ASCENDING)])
        self.db.economy_offers.create_index('business_id')
        self.db.merchant_contracts.create_index([('owner_id',1),('state',1),('expires_at',1)])
        self.db.merchant_contracts.create_index([('state',1),('expires_at',1)])
        self.db.merchant_ledger.create_index([('owner_id',1),('created_at',-1)])
        self.db.merchant_ledger.create_index([('owner_id',1),('action',1),('item_id',1),('counterparty',1),('created_at',-1)])
        self.db.economy_quest_rewards.create_index('operation_id',unique=True)
        self.operations.create_index('key')
        self.operations.create_index([('stock_id', 1), ('state', 1), ('_id', 1)])
        self.db.economy_support_notes.create_index([('receipt_id', 1), ('created_at', -1), ('_id', -1)])
        self.operations.create_index([('created_at',-1),('_id',-1)])
        self.operations.create_index([('state',1),('created_at',-1),('_id',-1)])
        self.operations.create_index([('business_id',1),('created_at',-1),('_id',-1)])
        self.db.economy_businesses.create_index('label_search')
        self.db.economy_offers.create_index([('business_id',1),('_id',1)])
        self.db.economy_offers.create_index([('business_id', 1), ('_id', 1)],
            name='available_offer_cursor', partialFilterExpression={'stock': {'$gt': 0}})
        self.db.economy_policy_schedule.create_index([('state',1),('effective_at',1)])
        self.db.economy_policy_schedule.create_index([('business_id',1),('created_at',-1)])
        self.db.economy_quest_completions.create_index([('owner_id',1),('completedAt',1)])
        self.db.economy_quest_rewards.create_index([('material_state',1),('operation_id',1)])

    def transact(self, callback):
        with self.db.client.start_session() as session:
            # with_transaction retries transient conflicts and unknown commit responses.
            return session.with_transaction(callback,read_concern=ReadConcern('snapshot'),write_concern=WriteConcern('majority'))

    def account(self, owner, session=None):
        account=self.accounts.find_one({'_id':'bank:'+owner},session=session)
        if not account: raise EconomyError('ACCOUNT_NOT_MIGRATED','Ce compte bancaire doit être préparé par un administrateur.')
        return account

    def migrate(self, owner, apply=False, expected_balance=None):
        def execute(session):
            players = list(self.db.players.find({'id': owner}, session=session).limit(2))
            if not players:
                raise EconomyError('OWNER_NOT_FOUND', 'Personnage introuvable.', 404)
            if len(players) != 1:
                raise EconomyError('OWNER_NOT_UNIQUE', 'Identifiant de personnage ambigu.')
            player = players[0]
            minecraft_id = player.get('id_minecraft')
            try:
                canonical_id = str(UUID(str(minecraft_id)))
            except (ValueError, TypeError):
                raise EconomyError('OWNER_NOT_LINKED', 'Liaison Minecraft à vérifier.')
            if minecraft_id != canonical_id:
                raise EconomyError('OWNER_NOT_LINKED', 'Liaison Minecraft non canonique, à vérifier.')
            if self.db.players.count_documents({'id_minecraft': canonical_id}, limit=2, session=session) != 1:
                raise EconomyError('MINECRAFT_LINK_CONFLICT', 'UUID Minecraft associé à plusieurs personnages.')
            existing = self.accounts.find_one({'_id': 'bank:' + owner}, session=session)
            if bool(existing) != (player.get('economy_v1') is True):
                raise EconomyError('MIGRATION_STATE_CONFLICT', 'Le marqueur bancaire et le compte doivent être rapprochés.')
            if existing:
                return {'owner_id': owner, 'status': 'already_migrated',
                        'balance': str(existing['available'] + existing['reserved'])}
            amount=legacy_money(player.get('money',0))
            if expected_balance is not None and str(amount) != expected_balance:
                raise EconomyError('MIGRATION_BALANCE_CHANGED', 'Le solde a changé depuis le relevé de migration.')
            if not apply: return {'owner_id':owner,'status':'ready','balance':str(amount)}
            now=timestamp()
            self.accounts.insert_one({'_id':'bank:'+owner,'owner_id':owner,'pocket':'BANK','currency':'IRON','available':amount,'reserved':0,'incoming':0,'revision':0,'updated_at':now,'opening_balance':amount},session=session)
            self.db.players.update_one({'id':owner},{'$set':{'money':amount,'economy_v1':True}},session=session)
            opening_id=str(uuid4())
            self.operations.insert_one({'_id':opening_id,'operation_id':opening_id,'api_version':'1','owner_id':owner,'actor_id':'migration','key':'opening:'+owner,'request_hash':fingerprint({'owner':owner,'amount':str(amount)}),'type':'OPENING_BALANCE','state':'CONFIRMED','amount':amount,'currency':'IRON','revision':0,'rule_version':'bank-v1','proof_id':'legacy-opening:'+owner,'created_at':now,'updated_at':now},session=session)
            return {'owner_id':owner,'status':'migrated','balance':str(amount)}
        return self.transact(execute)

    def prepare(self, owner, actor, key, kind, amount, reason=''):
        value=money(amount)
        if not isinstance(reason,str) or len(reason)>512: raise EconomyError("INVALID_REASON","Motif invalide ou trop long.",400)
        if kind not in {'DEPOSIT','WITHDRAW','CREDIT','DEBIT'}: raise EconomyError('INVALID_TYPE','Type bancaire invalide.',400)
        if not isinstance(key,str) or not 1<=len(key)<=128: raise EconomyError('INVALID_KEY','Clé d’opération requise.',400)
        if kind in {'CREDIT','DEBIT'} and (not isinstance(reason,str) or not reason.strip()): raise EconomyError('REASON_REQUIRED','Motif requis.',400)
        if not reason and kind in {'DEPOSIT','WITHDRAW'}: reason='Dépôt au banquier' if kind=='DEPOSIT' else 'Retrait au banquier'
        digest=fingerprint({'owner':owner,'type':kind,'amount':amount,'reason':reason})
        def execute(session):
            previous=self.operations.find_one({'actor_id':actor,'key':key},session=session)
            if previous:
                if previous['request_hash']!=digest: raise EconomyError('IDEMPOTENCY_CONFLICT','Cette clé désigne une autre opération.')
                return previous
            account=self.account(owner,session)
            available=account['available']; reserved=account['reserved']; incoming=account.get('incoming',0)
            if kind in {'WITHDRAW','DEBIT'}:
                if available<value: raise EconomyError('INSUFFICIENT_FUNDS','Solde bancaire disponible insuffisant.')
                available-=value
                if kind=='WITHDRAW': reserved+=value
            elif kind=='DEPOSIT':
                if available+reserved+incoming>MAX_MONEY-value: raise EconomyError('BALANCE_LIMIT','Ce dépôt dépasserait la limite de solde.')
                incoming+=value
            elif kind=='CREDIT':
                if available+reserved+incoming>MAX_MONEY-value: raise EconomyError('BALANCE_LIMIT','Limite de solde atteinte.')
                available+=value
            now=timestamp(); ident=str(uuid4())
            op={'_id':ident,'operation_id':ident,'api_version':'1','owner_id':owner,'actor_id':actor,'key':key,'request_hash':digest,'type':kind,'amount':value,'currency':'IRON','state':'RESERVED' if kind in {'DEPOSIT','WITHDRAW'} else 'CONFIRMED','revision':0,'created_at':now,'updated_at':now,'rule_version':'bank-v1','reason':reason}
            if kind in {'CREDIT','DEBIT'}: op['proof_id']='system:'+ident
            self.operations.insert_one(op,session=session)
            self.accounts.update_one({'_id':account['_id']},{'$set':{'available':available,'reserved':reserved,'incoming':incoming,'updated_at':now},'$inc':{'revision':1}},session=session)
            self.db.players.update_one({'id':owner},{'$set':{'money':available+reserved}},session=session)
            return op
        try: return self.transact(execute)
        except DuplicateKeyError:
            previous=self.operations.find_one({'actor_id':actor,'key':key})
            if not previous or previous['request_hash']!=digest: raise EconomyError('IDEMPOTENCY_CONFLICT','Cette clé désigne une autre opération.')
            return previous

    def transition(self, ident, actor, action, expected_revision, proof, reviewer=None):
        if action not in {'delivery','cancel','reconcile'}: raise EconomyError('INVALID_ACTION','Action invalide.',400)
        if not isinstance(proof,str) or not 1<=len(proof)<=256: raise EconomyError('PROOF_REQUIRED','Preuve serveur requise.',400)
        if isinstance(expected_revision,bool) or not isinstance(expected_revision,int) or expected_revision<0: raise EconomyError('INVALID_REVISION','Révision invalide.',400)
        target={'delivery':'CONFIRMED','cancel':'CANCELLED','reconcile':'RECONCILIATION_REQUIRED'}[action]
        def execute(session):
            op=self.operations.find_one({'_id':ident,'actor_id':actor,'type':{'$in':['DEPOSIT','WITHDRAW']}},session=session)
            if not op: raise EconomyError('OPERATION_NOT_FOUND','Opération introuvable.',404)
            if op['state']==target and op.get('proof_id')==proof: return op
            if op['revision']!=expected_revision: raise EconomyError('REVISION_CONFLICT','Le reçu a changé ; rechargez son état.')
            if op['state']!='RESERVED' and not (reviewer and op['state']=='RECONCILIATION_REQUIRED'): raise EconomyError('INVALID_STATE','Cette opération ne peut plus être modifiée automatiquement.')
            account=self.account(op['owner_id'],session); available=account['available']; reserved=account['reserved']; incoming=account.get('incoming',0); value=op['amount']
            if action=='delivery' and op['type']=='DEPOSIT':
                if available+reserved>MAX_MONEY-value: raise EconomyError('BALANCE_LIMIT','Limite de solde atteinte ; dépôt à rapprocher.')
                available+=value
            if op['type']=='DEPOSIT' and action in {'delivery','cancel'}: incoming-=value
            if op['type']=='WITHDRAW':
                if action in {'delivery','cancel'}: reserved-=value
                if action=='cancel': available+=value
            now=timestamp()
            self.accounts.update_one({'_id':account['_id']},{'$set':{'available':available,'reserved':reserved,'incoming':incoming,'updated_at':now},'$inc':{'revision':1}},session=session)
            self.db.players.update_one({'id':op['owner_id']},{'$set':{'money':available+reserved}},session=session)
            self.operations.update_one({'_id':ident},{'$set':{'state':target,'proof_id':proof,'updated_at':now,**({'reviewed_by':reviewer} if reviewer else {})},'$inc':{'revision':1}},session=session)
            return {**op,'state':target,'proof_id':proof,'updated_at':now,'revision':op['revision']+1}
        return self.transact(execute)

    def compensate(self, original_id, actor, key, reason):
        if not isinstance(reason,str) or not reason.strip(): raise EconomyError('REASON_REQUIRED','Motif de compensation requis.',400)
        def execute(session):
            original=self.operations.find_one({'_id':original_id,'state':'CONFIRMED','type':{'$in':['CREDIT','DEBIT']}},session=session)
            if not original: raise EconomyError('RECONCILIATION_REQUIRED','Une livraison physique exige un rapprochement avant compensation.')
            digest=fingerprint({'original':original_id,'reason':reason})
            previous=self.operations.find_one({'original_operation_id':original_id},session=session)
            if previous:
                if previous['request_hash']!=digest: raise EconomyError('IDEMPOTENCY_CONFLICT','Une compensation existe déjà pour ce reçu.')
                return previous
            account=self.account(original['owner_id'],session); value=original['amount']
            delta=-value if original['type']=='CREDIT' else value
            available=account['available']+delta
            if available<0: raise EconomyError('INSUFFICIENT_FUNDS','Le crédit ne peut pas être compensé sans créer un découvert.')
            if available+account['reserved']+account.get('incoming',0)>MAX_MONEY: raise EconomyError('BALANCE_LIMIT','Limite de solde atteinte.')
            ident=str(uuid4());now=timestamp()
            op={'_id':ident,'operation_id':ident,'api_version':'1','owner_id':original['owner_id'],'actor_id':actor,'key':'compensation:'+original_id,'request_hash':digest,'type':'COMPENSATION','state':'CONFIRMED','amount':value,'currency':'IRON','revision':0,'rule_version':'bank-v1','proof_id':'admin:'+ident,'original_operation_id':original_id,'reason':reason,'direction':'DEBIT' if delta<0 else 'CREDIT','created_at':now,'updated_at':now}
            self.accounts.update_one({'_id':account['_id']},{'$set':{'available':available,'updated_at':now},'$inc':{'revision':1}},session=session)
            self.db.players.update_one({'id':original['owner_id']},{'$set':{'money':available+account['reserved']}},session=session)
            self.operations.insert_one(op,session=session)
            return op
        try:return self.transact(execute)
        except DuplicateKeyError:
            previous=self.operations.find_one({'original_operation_id':original_id})
            if previous and previous['request_hash']==fingerprint({'original':original_id,'reason':reason}): return previous
            raise EconomyError('IDEMPOTENCY_CONFLICT','Une compensation existe déjà.')


_bank=None
_bank_lock=Lock()
def get_bank():
    global _bank
    if _bank is not None:return _bank
    with _bank_lock:
        if _bank is None:
            from django.conf import settings
            client=MongoClient(settings.MONGO_URI,serverSelectionTimeoutMS=3000,connectTimeoutMS=3000,socketTimeoutMS=10000,maxPoolSize=20)
            try:
                bank=Bank(client[settings.MONGO_DB_NAME]);bank.initialize();_bank=bank
            except Exception:
                client.close();raise
    return _bank
