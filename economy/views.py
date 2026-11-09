import json
import logging
import re
from uuid import UUID
from pymongo.errors import DuplicateKeyError
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from firebase_admin import auth
from utils.decorators import _has_server_api_key
from players.models import Player
from .domain import EconomyError, fingerprint, public
from .store import get_bank,timestamp
from .commerce import Commerce
from .desk import Desk,page_operations

logger=logging.getLogger(__name__)

def endpoint(view):
    @csrf_exempt
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        try:
            request.economy_server=_has_server_api_key(request)
            request.economy_body={}
            if request.method=='POST':
                if len(request.body)>16384: raise EconomyError('INVALID_REQUEST','Requête trop volumineuse.',400)
                try: request.economy_body=json.loads(request.body)
                except (ValueError,UnicodeError): raise EconomyError('INVALID_REQUEST','JSON invalide.',400)
                if not isinstance(request.economy_body,dict): raise EconomyError('INVALID_REQUEST','Objet JSON requis.',400)
            if request.economy_server:
                mc=request.headers.get('X-Minecraft-UUID')
                if not mc: raise EconomyError('OWNER_NOT_LINKED','Identité Minecraft requise.',401)
                player=Player.objects.get(id_minecraft=mc)
            else:
                token=request.headers.get('Authorization','')
                if not token.startswith('Bearer '): raise EconomyError('AUTH_REQUIRED','Connexion requise.',401)
                try: decoded=auth.verify_id_token(token[7:])
                except Exception: raise EconomyError('AUTH_REQUIRED','Connexion invalide.',401)
                player=Player.objects.get(id=decoded['uid'])
            request.economy_owner=str(player.id); request.economy_actor=('minecraft:'+mc) if request.economy_server else ('web:'+str(player.id))
            request.economy_admin=player.rank=='Admin'
            request.economy_support=player.rank in {'Admin', 'Moderateur'}
            return view(request,*args,**kwargs)
        except Player.DoesNotExist: return JsonResponse({'code':'OWNER_NOT_LINKED','message':'Personnage non relié.','retryable':False},status=403)
        except EconomyError as exc: return JsonResponse({'code':exc.code,'message':str(exc),'retryable':exc.status==503},status=exc.status)
        except Exception:
            logger.exception('Economy request failed')
            return JsonResponse({'code':'SERVICE_UNAVAILABLE','message':'Banque temporairement indisponible. Vérifiez le reçu avant de recommencer.','retryable':True},status=503)
    return wrapped

def method(request,expected):
    if request.method!=expected: raise EconomyError('METHOD_NOT_ALLOWED','Méthode non autorisée.',405)

def receipt_scope(owner):
    return {'$or':[{'owner_id':owner},{'participant_owner_ids':owner}]}

@endpoint
def accounts(request):
    method(request,'GET'); bank=get_bank(); account=bank.account(request.economy_owner)
    boxes=list(bank.accounts.find({'owner_id':request.economy_owner,'pocket':'CASHBOX'}).limit(100))
    labels={row['_id']:row['label'] for row in bank.db.economy_businesses.find({'_id':{'$in':[box['business_id'] for box in boxes]}})}
    boxes=[{**box,'label':labels.get(box['business_id'],box['business_id'])} for box in boxes]
    return JsonResponse({'accounts':[public(account)]+[public(box) for box in boxes]})

@endpoint
def operations(request):
    bank=get_bank()
    if request.method=='GET':
        return JsonResponse(page_operations(bank,request.GET,receipt_scope(request.economy_owner)))
    method(request,'POST')
    if not request.economy_server: raise EconomyError('GAME_REQUIRED','Le dépôt et le retrait se font auprès du banquier en jeu.',403)
    body=request.economy_body
    op=bank.prepare(request.economy_owner,request.economy_actor,request.headers.get('Idempotency-Key') or body.get('idempotency_key'),body.get('type'),body.get('amount'),body.get('reason',''))
    return JsonResponse(public(op))

@endpoint
def operation(request,ident,action=None):
    bank=get_bank()
    op=bank.operations.find_one({'_id':str(ident),**receipt_scope(request.economy_owner)})
    if not op: raise EconomyError('OPERATION_NOT_FOUND','Reçu introuvable.',404)
    if action is None:
        method(request,'GET')
        material=bank.db.economy_quest_rewards.find_one({'operation_id':str(ident)},{'material_state':1})
        return JsonResponse(public({**op,**({'material_state':material['material_state']} if material else {})}))
    method(request,'POST')
    if not request.economy_server: raise EconomyError('GAME_REQUIRED','Preuve du serveur Minecraft requise.',403)
    body=request.economy_body
    service=Commerce(bank) if op['type']=='COMMERCE' else bank
    return JsonResponse(public(service.transition(str(ident),request.economy_actor,action,body.get('revision'),body.get('proof_id'))))


@endpoint
def support_receipt(request, ident):
    if not request.economy_support:
        raise EconomyError('SUPPORT_REQUIRED', 'Accès réservé à l’équipe de modération.', 403)
    if request.method not in {'GET', 'POST'}:
        raise EconomyError('METHOD_NOT_ALLOWED', 'Méthode non autorisée.', 405)

    bank = get_bank()
    receipt_id = str(ident)
    receipt = bank.operations.find_one({'_id': receipt_id}, {
        '_id': 0, 'operation_id': 1, 'state': 1, 'created_at': 1,
        'type': 1, 'action': 1, 'business_id': 1,
    })
    if not receipt:
        raise EconomyError('OPERATION_NOT_FOUND', 'Reçu introuvable.', 404)
    notes = bank.db.economy_support_notes
    if request.method == 'POST':
        text = request.economy_body.get('note')
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 500:
            raise EconomyError('INVALID_REQUEST', 'La note doit contenir entre 1 et 500 caractères.', 400)
        try:
            key = str(UUID(request.headers.get('Idempotency-Key', '')))
        except ValueError:
            raise EconomyError('INVALID_REQUEST', 'Clé de note invalide.', 400)
        note_id = fingerprint({'receipt': receipt_id, 'actor': request.economy_actor, 'key': key})
        entry = {'_id': note_id, 'receipt_id': receipt_id, 'author': request.economy_owner,
                 'note': text.strip(), 'created_at': timestamp()}
        try:
            notes.insert_one(entry)
        except DuplicateKeyError:
            previous = notes.find_one({'_id': note_id}, {'note': 1})
            if not previous or previous['note'] != entry['note']:
                raise EconomyError('IDEMPOTENCY_CONFLICT', 'Cette clé appartient à une autre note.', 409)

    rows = notes.find({'receipt_id': receipt_id}, {'_id': 1, 'note': 1, 'created_at': 1})
    return JsonResponse({'receipt': receipt, 'notes': list(rows.sort([('created_at', -1), ('_id', -1)]).limit(20))})


@endpoint
def admin_operation(request,ident,action=None):
    if not request.economy_admin: raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    bank=get_bank(); op=bank.operations.find_one({'_id':str(ident)})
    if not op: raise EconomyError('OPERATION_NOT_FOUND','Reçu introuvable.',404)
    if action is None:
        method(request,'GET')
        material=bank.db.economy_quest_rewards.find_one({'operation_id':str(ident)},{'material_state':1})
        account=bank.accounts.find_one({'_id':'bank:'+op['owner_id']})
        result=public({**op,**({'material_state':material['material_state']} if material else {})})
        result['owner_account']=public(account) if account else None
        return JsonResponse(result)
    method(request,'POST');body=request.economy_body
    if action=='compensations':
        return JsonResponse(public(bank.compensate(str(ident),request.economy_actor,request.headers.get('Idempotency-Key'),body.get('reason'))))
    if action=='complete-transfer':
        if op['type']!='COMMERCE' or op.get('action')!='FUND' or op.get('payment')!='BANK' or not op['actor_id'].startswith('web:'):
            raise EconomyError('INVALID_TYPE','Seul un approvisionnement bancaire web peut être repris ainsi.',400)
        if op['state']=='CONFIRMED':return JsonResponse(public(op))
        return JsonResponse(public(Commerce(bank).transition(str(ident),op['actor_id'],'delivery',body.get('revision'),'web-transfer:'+str(ident))))
    if action=='review':
        from .commerce import identifier
        reason=identifier(body.get('reason'),'Motif')
        service=Commerce(bank) if op['type']=='COMMERCE' else bank
        return JsonResponse(public(service.transition(str(ident),op['actor_id'],'reconcile',body.get('revision'),reason,reviewer=request.economy_actor)))
    if action=='materials':
        if op['type']!='QUEST_REWARD' or body.get('decision') not in {'DELIVERED','RETRY'}:
            raise EconomyError('INVALID_REQUEST','Choisissez DELIVERED ou RETRY pour une récompense de quête.',400)
        from .commerce import identifier
        reason=identifier(body.get('reason'),'Preuve de vérification')
        def resolve_material(session):
            row=bank.db.economy_quest_rewards.find_one({'operation_id':str(ident)},session=session)
            if not row or row['material_state']=='DELIVERED':raise EconomyError('INVALID_STATE','Cette remise ne nécessite plus de correction.')
            state='PENDING' if body['decision']=='RETRY' else 'DELIVERED'
            changes={'material_state':state,'material_resolution':body['decision'],'reviewed_by':request.economy_actor}
            bank.db.economy_quest_rewards.update_one({'_id':row['_id']},{'$set':changes,'$inc':{'material_revision':1}},session=session)
            from .store import timestamp
            bank.db.economy_material_reviews.insert_one({'operation_id':str(ident),'actor_id':request.economy_actor,
                'reason':reason,'decision':body['decision'],'previous_state':row['material_state'],'created_at':timestamp()},session=session)
            return {**row,**changes}
        return JsonResponse(public(bank.transact(resolve_material)))
    if action=='resolve':
        decision=body.get('decision');reason=body.get('reason')
        if decision not in {'delivery','cancel'} or not isinstance(reason,str) or not reason.strip(): raise EconomyError('INVALID_REQUEST','Décision et preuve de vérification requises.',400)
        if op['state']!='RECONCILIATION_REQUIRED': raise EconomyError('INVALID_STATE','Seul un reçu à rapprocher peut être résolu ici.')
        service=Commerce(bank) if op['type']=='COMMERCE' else bank
        return JsonResponse(public(service.transition(str(ident),op['actor_id'],decision,body.get('revision'),reason,reviewer=request.economy_actor)))
    raise EconomyError('INVALID_ACTION','Action inconnue.',400)


@endpoint
def admin_adjustment(request,owner):
    method(request,'POST')
    if not request.economy_admin: raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    body=request.economy_body
    if body.get('type') not in {'CREDIT','DEBIT'}: raise EconomyError('INVALID_TYPE','Choisissez CREDIT ou DEBIT.',400)
    return JsonResponse(public(get_bank().prepare(owner,request.economy_actor,request.headers.get('Idempotency-Key') or body.get('idempotency_key'),body.get('type'),body.get('amount'),body.get('reason',''))))

@endpoint
def admin_policy(request,business_id):
    method(request,'POST')
    if not request.economy_admin:raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    b=request.economy_body
    return JsonResponse(public(Commerce(get_bank()).policy(business_id,request.economy_actor,b.get('expected_rule_version'),b.get('rule_version'),b.get('tax_bps'),b.get('treasury_account_id'))))

@endpoint
def admin_stock(request,business_id):
    method(request,'POST')
    if not request.economy_admin:raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    b=request.economy_body
    return JsonResponse(public(Commerce(get_bank()).adjust_stock(request.economy_actor,request.headers.get('Idempotency-Key') or b.get('idempotency_key'),
        business_id,b.get('offer_id'),b.get('expected_stock'),b.get('stock'),b.get('reason'))))


def game(request):
    if not request.economy_server:
        raise EconomyError('GAME_REQUIRED','Le serveur de jeu doit valider cet échange.',403)


@endpoint
def business(request):
    method(request,'POST'); game(request); body=request.economy_body
    owner_mc=body.get('owner_minecraft')
    if owner_mc:
        try: owner=str(Player.objects.get(id_minecraft=owner_mc).id)
        except Player.DoesNotExist: raise EconomyError('OWNER_NOT_LINKED','Propriétaire non relié.',409)
    else:
        if body.get('kind') not in {'NPC','MARKET','EXPLORATION'}:
            raise EconomyError('OWNER_REQUIRED','Propriétaire de l’établissement requis.',400)
        owner='system:'+str(body.get('business_id'))
    return JsonResponse(public(Commerce(get_bank()).register(body.get('business_id'),owner,body.get('label'),body.get('kind'))))


@endpoint
def funding_targets(request):
    method(request, 'GET')
    game(request)
    owned = request.GET.get('owned') == '1'
    stock_business = request.GET.get('stock_business')
    if not owned and not request.economy_admin:
        raise EconomyError('ADMIN_REQUIRED', 'Administrateur requis.', 403)
    prefix = request.GET.get('prefix', '')
    if not re.fullmatch(r'[a-z0-9_.:/-]{0,160}', prefix):
        raise EconomyError('INVALID_REQUEST', 'Préfixe d’établissement invalide.', 400)
    query = {'active': True}
    if owned:
        query['owner_id'] = request.economy_owner
    bank = get_bank()
    if stock_business is not None:
        from .commerce import identifier
        query['_id'] = identifier(stock_business)
        # Stock withdrawal is restricted to the owner, including for administrators.
        query['owner_id'] = request.economy_owner
        if not bank.db.economy_businesses.find_one(query, {'_id': 1}):
            return JsonResponse({'targets': []})
        offer_query = {'business_id': stock_business, 'stock': {'$gt': 0}}
        if prefix:
            offer_query['offer_id'] = {'$regex': '^' + re.escape(prefix)}
        rows = bank.db.economy_offers.find(offer_query, {'offer_id': 1, 'stock': 1, '_id': 0})
        targets = [{'business_id': row['offer_id'], 'label': f"{row['stock']} en stock"}
                   for row in rows.sort('offer_id', 1).limit(50).max_time_ms(1500)]
        return JsonResponse({'targets': targets})
    if prefix:
        query['_id'] = {'$regex': '^' + re.escape(prefix)}
    rows = bank.db.economy_businesses.find(query, {'business_id': 1, 'label': 1, '_id': 0})
    return JsonResponse({'targets': list(rows.sort('_id', 1).limit(50).max_time_ms(1500))})


@endpoint
def offer(request):
    if request.method=='GET':
        business_id=request.GET.get('business_id')
        from .commerce import identifier
        identifier(business_id)
        database = get_bank().db
        collection = database.economy_offers
        query = {'business_id': business_id}
        offer_id = request.GET.get('offer_id')
        if offer_id is not None:
            identifier(offer_id)
            query['_id'] = fingerprint({'business': business_id, 'offer': offer_id})
            row = collection.find_one(query, max_time_ms=1500)
            return JsonResponse({'offers': [public(row)] if row else [], 'next_cursor': None})

        scope = request.GET.get('scope', 'all')
        projection = None
        if scope == 'slots':
            query.update({'offer_id': {'$regex': '^slot:'}, '$or': [
                {'stock': {'$gt': 0}}, {'reserved_stock': {'$gt': 0}}, {'incoming_stock': {'$gt': 0}}]})
            projection = {'offer_id': 1, 'stock': 1, 'reserved_stock': 1, 'incoming_stock': 1, 'item_nbt': 1, 'stock_capacity': 1}
        elif scope == 'limited':
            query.update({'offer_id': {'$not': {'$regex': '^slot:'}}, 'stock': {'$gte': 0}})
            projection = {'offer_id': 1, 'stock': 1}
        elif scope != 'all':
            raise EconomyError('INVALID_REQUEST', 'Vue des offres inconnue.', 400)
        cursor = request.GET.get('after')
        if cursor is not None:
            if not re.fullmatch(r'[0-9a-f]{64}', cursor):
                raise EconomyError('INVALID_REQUEST', 'Curseur des offres invalide.', 400)
            query['_id'] = {'$gt': cursor}
        limit = 200 if scope == 'all' else 64
        rows = list(collection.find(query, projection).sort('_id', 1).limit(limit + 1).max_time_ms(2000))
        if scope == 'slots':
            held_ids = [row['_id'] for row in rows[:limit]
                        if row.get('reserved_stock', 0) or row.get('incoming_stock', 0)]
            if held_ids:
                holds = database.economy_operations.find({
                    'stock_id': {'$in': held_ids}, 'state': {'$in': ['RESERVED', 'RECONCILIATION_REQUIRED']}},
                    {'stock_id': 1, 'operation_id': 1}).sort('_id', 1).limit(512).max_time_ms(1500)
                references = {}
                for hold in holds:
                    references.setdefault(hold['stock_id'], hold['operation_id'])
                for row in rows[:limit]:
                    if row['_id'] in references:
                        row['pending_receipt'] = references[row['_id']]
        if scope == 'slots' and not rows and cursor is None:
            if not database.economy_businesses.find_one({'_id': business_id}, {'_id': 1}, max_time_ms=1500):
                scope = 'unregistered'
        return JsonResponse({'offers': [public(row) for row in rows[:limit]], 'scope': scope,
                             'next_cursor': rows[limit - 1]['_id'] if len(rows) > limit else None})
    method(request,'POST'); game(request); b=request.economy_body
    return JsonResponse(public(Commerce(get_bank()).offer(b.get('business_id'),b.get('offer_id'),b.get('price_version'),b.get('buy_price'),b.get('sell_price'),b.get('stock'),b.get('item_nbt'),b.get('stock_capacity'))))


@endpoint
def commerce(request):
    method(request,'POST'); game(request); b=dict(request.economy_body)
    key=request.headers.get('Idempotency-Key') or b.pop('idempotency_key',None)
    return JsonResponse(public(Commerce(get_bank()).prepare(request.economy_owner,request.economy_actor,key,b,request.economy_admin)))


@endpoint
def reward(request,quest_id):
    method(request,'POST'); game(request)
    return JsonResponse(public(Commerce(get_bank()).reward(request.economy_owner,request.economy_actor,quest_id)))

@endpoint
def complete_quest(request,quest_id):
    method(request,'POST');game(request)
    state=Commerce(get_bank()).complete_quest(request.economy_owner,quest_id)
    return JsonResponse({'quest_id':quest_id,'status':state['status'],'destination':'BANK','reward_rule_version':state['reward_snapshot']['rule_version']})

@endpoint
def pending_rewards(request):
    method(request,'GET');game(request)
    return JsonResponse({'quest_ids':Commerce(get_bank()).pending_rewards(request.economy_owner)})


@endpoint
def reward_material(request,quest_id):
    method(request,'POST'); game(request)
    service=Commerce(get_bank()); row=service.reward(request.economy_owner,request.economy_actor,quest_id)
    b=request.economy_body; state=b.get('state'); proof=b.get('proof_id')
    from .commerce import identifier
    identifier(proof,'Preuve')
    # A reservation is never automatically released: a restart may follow delivery.
    if state not in {'PENDING','DELIVERING','DELIVERED','RECONCILIATION_REQUIRED'}:
        raise EconomyError('INVALID_REQUEST','État de remise invalide.',400)
    allowed={'PENDING':['DELIVERING'],'DELIVERING':['PENDING'],'DELIVERED':['DELIVERING'],'RECONCILIATION_REQUIRED':['DELIVERING']}[state]
    query={'_id':row['_id'],'material_state':{'$in':allowed}}
    if state!='DELIVERING': query['material_proof']=proof
    service.db.economy_quest_rewards.update_one(query,{'$set':{'material_state':state,'material_proof':proof}})
    current=service.db.economy_quest_rewards.find_one({'_id':row['_id']})
    if current['material_state']!=state or current.get('material_proof')!=proof:
        raise EconomyError('REWARD_ALREADY_RESERVED','La remise existe déjà. Vérifiez son reçu avant de recommencer.')
    return JsonResponse(public(current))


@endpoint
def admin_desk(request,section):
    method(request,'GET')
    if not request.economy_admin:raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    desk=Desk(get_bank())
    if section=='overview':return JsonResponse(desk.overview())
    if section=='operations':return JsonResponse(page_operations(desk.bank,request.GET))
    if section=='businesses':return JsonResponse(desk.businesses(request.GET))
    raise EconomyError('INVALID_REQUEST','Section inconnue.',404)


@endpoint
def admin_business(request,business_id,action=None):
    if not request.economy_admin:raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    desk=Desk(get_bank())
    if action is None:
        method(request,'GET');result=desk.detail(business_id,request.GET.get('before'))
        source=desk.bank.accounts.find_one({'_id':'bank:'+request.economy_owner})
        result['funding_account']=public(source) if source else None
        return JsonResponse(result)
    method(request,'POST');b=request.economy_body;key=request.headers.get('Idempotency-Key') or b.get('idempotency_key')
    if action=='availability':return JsonResponse(public(desk.suspend(business_id,request.economy_actor,key,b.get('revision'),b.get('active'),b.get('reason'))))
    if action=='schedule':return JsonResponse(public(desk.schedule(business_id,request.economy_actor,key,b)))
    if action=='fund':return JsonResponse(public(desk.fund(request.economy_owner,request.economy_actor,business_id,key,b.get('amount'),b.get('reason'))))
    if action=='budget-mode':return JsonResponse(public(desk.budget_mode(business_id,request.economy_actor,key,b.get('unlimited'))))
    raise EconomyError('INVALID_ACTION','Action inconnue.',400)


@endpoint
def admin_schedule(request,ident):
    method(request,'POST')
    if not request.economy_admin:raise EconomyError('ADMIN_REQUIRED','Administrateur requis.',403)
    return JsonResponse(Desk(get_bank()).cancel_schedule(ident,request.economy_actor))


@endpoint
def business_status(request):
    method(request,'GET');business_id=request.GET.get('business_id')
    from .commerce import identifier
    identifier(business_id)
    bank=get_bank();row=bank.db.economy_businesses.find_one({'_id':business_id})
    if not row:return JsonResponse({'business_id':business_id,'state':'NOT_REGISTERED','observed_at':timestamp()})
    account=bank.accounts.find_one({'_id':'cashbox:'+business_id})
    visible=row['kind']=='NPC' or row['owner_id'].startswith('system:') or row['owner_id']==request.economy_owner or request.economy_admin
    return JsonResponse({'business_id':business_id,'label':row['label'],'active':row['active'],
        'state':'CLOSED' if not row['active'] else ('UNLIMITED' if row.get('budget_unlimited') else ('EMPTY' if not account or account['available']==0 else 'AVAILABLE')),
        'budget':str(account['available']) if account and visible else None,'observed_at':timestamp(),'rule_version':row['rule_version']})

@endpoint
def wallet(request):
    method(request, 'GET')
    bank = get_bank()
    bank_id = 'bank:' + request.economy_owner
    bank_filter = {'pocket': 'BANK', '_id': bank_id}
    box_filter = {'pocket': 'CASHBOX'}
    cursor = request.GET.get('before')
    if cursor:
        from .commerce import identifier
        box_filter['_id'] = {'$gt': identifier(cursor)}
    query = {'owner_id': request.economy_owner, '$or': [bank_filter, box_filter]}
    # BANK sorts before CASHBOX. Reserve one result for the bank when it exists.
    rows = list(bank.accounts.find(query).sort([('pocket', 1), ('_id', 1)]).limit(52))
    account = rows[0] if rows and rows[0]['_id'] == bank_id else None
    boxes = rows[1:] if account else rows[:51]
    business_ids = [box['business_id'] for box in boxes[:50]]
    labels = {}
    if business_ids:
        businesses = bank.db.economy_businesses.find({'_id': {'$in': business_ids}}, {'label': 1, 'active': 1})
        labels = {row['_id']: row for row in businesses}
    return JsonResponse({'bank':public(account) if account else None,'bank_state':'MIGRATED' if account else 'SETUP_REQUIRED',
        'cashboxes':[{**public(box),'label':labels.get(box['business_id'],{}).get('label',box['business_id']),
            'active':labels.get(box['business_id'],{}).get('active')} for box in boxes[:50]],
        'has_more':len(boxes)>50,'next_cursor':boxes[49]['_id'] if len(boxes)>50 else None,'observed_at':timestamp()})
