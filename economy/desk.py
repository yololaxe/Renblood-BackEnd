"""Bounded support queries and reversible business administration."""
import re
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from pymongo.errors import DuplicateKeyError
from .commerce import Commerce,identifier
from .domain import EconomyError,fingerprint,public
from .store import timestamp

STATES={'RESERVED','CONFIRMED','CANCELLED','RECONCILIATION_REQUIRED'}
TYPES={'DEPOSIT','WITHDRAW','CREDIT','DEBIT','COMPENSATION','OPENING_BALANCE','COMMERCE','QUEST_REWARD'}


def receipt_filter(params):
    query={}
    for field,allowed in [('state',STATES),('type',TYPES)]:
        value=params.get(field)
        if value:
            if value not in allowed:raise EconomyError('INVALID_FILTER','Filtre de reçu invalide.',400)
            query[field]=value
    if params.get('business_id'):query['business_id']=identifier(params['business_id'])
    if params.get('q'):
        term=identifier(params['q'].strip())
        query['$or']=[{key:term} for key in ['_id','key','owner_id','business_id','actor_id','quest_id']]
    return query


def page_operations(bank,params,scope=None):
    query=receipt_filter(params)
    if scope:query={'$and':[scope,query]}
    before=params.get('before')
    if before:
        cursor=bank.operations.find_one({'$and':[query,{'_id':before}]},{'created_at':1})
        if not cursor:raise EconomyError('INVALID_CURSOR','Rechargez la liste avant de changer de page.',400)
        query={'$and':[query,{'$or':[{'created_at':{'$lt':cursor['created_at']}},
            {'created_at':cursor['created_at'],'_id':{'$lt':before}}]}]}
    rows=list(bank.operations.find(query,{'item_nbt':0}).sort([('created_at',-1),('_id',-1)]).limit(51).max_time_ms(2000))
    visible=rows[:50]
    materials={r['operation_id']:r['material_state'] for r in bank.db.economy_quest_rewards.find({'operation_id':{'$in':[r['_id'] for r in visible]}},{'operation_id':1,'material_state':1})}
    labels={r['_id']:r['label'] for r in bank.db.economy_businesses.find({'_id':{'$in':list({r.get('business_id') for r in visible if r.get('business_id')})}},{'label':1})}
    return {'operations':[public({**r,**({'material_state':materials[r['_id']]} if r['_id'] in materials else {}),
        **({'business_label':labels[r['business_id']]} if r.get('business_id') in labels else {})}) for r in visible],
        'has_more':len(rows)>50,'next_cursor':visible[-1]['_id'] if len(rows)>50 else None,'observed_at':timestamp()}


class Desk:
    def __init__(self,bank):self.bank=bank;self.db=bank.db

    def overview(self):
        pending={'state':{'$in':['RESERVED','RECONCILIATION_REQUIRED']}}
        health=self.db.economy_services.find_one({'_id':'policy-publisher'}) or {}
        seen=health.get('last_seen')
        try:publisher_ready=0<=(datetime.now(timezone.utc)-datetime.fromisoformat(seen)).total_seconds()<120
        except (ValueError,TypeError):publisher_ready=False
        oldest=self.bank.operations.find_one(pending,{'created_at':1,'operation_id':1},sort=[('created_at',1)])
        return {'reserved':self.bank.operations.count_documents({'state':'RESERVED'},maxTimeMS=2000),
            'review':self.bank.operations.count_documents({'state':'RECONCILIATION_REQUIRED'},maxTimeMS=2000),
            'materials':self.db.economy_quest_rewards.count_documents({'material_state':{'$in':['DELIVERING','RECONCILIATION_REQUIRED']}},maxTimeMS=2000),
            'businesses':self.db.economy_businesses.estimated_document_count(maxTimeMS=2000),
            'scheduled':self.db.economy_policy_schedule.count_documents({'state':'SCHEDULED'},maxTimeMS=2000),
            'oldest_pending_at':oldest.get('created_at') if oldest else None,'observed_at':timestamp(),
            'publisher_last_seen':seen,'publisher_ready':publisher_ready}

    def fund(self,owner,actor,business,key,amount,reason):
        identifier(reason,'Motif')
        operation=Commerce(self.bank).prepare(owner,actor,key,{'business_id':business,'action':'FUND',
            'amount':amount,'payment':'BANK','reason':reason},administrator=True)
        if operation['state']=='CONFIRMED':return operation
        if operation['state']!='RESERVED':raise EconomyError('INVALID_STATE','Virement à rapprocher.')
        return Commerce(self.bank).transition(operation['_id'],actor,'delivery',operation['revision'],'web-transfer:'+operation['_id'])

    def budget_mode(self, business_id, actor, key, unlimited):
        identifier(business_id)
        identifier(key, 'Clé')
        if type(unlimited) is not bool:
            raise EconomyError('INVALID_REQUEST', 'Choisissez un budget limité ou illimité.', 400)
        change_id = fingerprint({'actor': actor, 'key': key})

        def run(session):
            changes = self.db.economy_budget_changes
            previous = changes.find_one({'_id': change_id}, session=session)
            if previous:
                if previous['business_id'] != business_id or previous['unlimited'] != unlimited:
                    raise EconomyError('IDEMPOTENCY_CONFLICT', 'Cette demande existe avec un autre contenu.')
                return previous
            business = self.db.economy_businesses.find_one({'_id': business_id}, session=session)
            if not business:
                raise EconomyError('BUSINESS_NOT_FOUND', 'Établissement introuvable.', 404)
            result = {'_id': change_id, 'business_id': business_id, 'actor_id': actor,
                      'unlimited': unlimited, 'previous_unlimited': business.get('budget_unlimited', False),
                      'created_at': timestamp()}
            self.db.economy_businesses.update_one({'_id': business_id}, {
                '$set': {'budget_unlimited': unlimited, 'budget_change_id': change_id}, '$inc': {'revision': 1},
            }, session=session)
            changes.insert_one(result, session=session)
            return result

        return self.bank.transact(run)

    def businesses(self,params):
        query={}
        if params.get('q'):
            term=identifier(params['q'].strip())
            query['$or']=[{'_id':term},{'owner_id':term},{'label_search':{'$regex':'^'+re.escape(term.casefold())}}]
        if params.get('before'):query={'$and':[query,{'_id':{'$gt':identifier(params['before'])}}]}
        rows=list(self.db.economy_businesses.find(query).sort('_id',1).limit(51).max_time_ms(2000))
        balances={r['business_id']:public(r) for r in self.bank.accounts.find({'business_id':{'$in':[r['_id'] for r in rows[:50]]},'pocket':'CASHBOX'})}
        return {'businesses':[{**public(row),'account':balances.get(row['_id'])} for row in rows[:50]],
            'has_more':len(rows)>50,'next_cursor':rows[49]['_id'] if len(rows)>50 else None}

    def detail(self,business,after=None):
        row=self.db.economy_businesses.find_one({'_id':identifier(business)})
        if not row:raise EconomyError('BUSINESS_NOT_FOUND','Établissement introuvable.',404)
        query={'business_id':business}
        if after:query['_id']={'$gt':identifier(after)}
        offers=list(self.db.economy_offers.find(query,{'item_nbt':0}).sort('_id',1).limit(51).max_time_ms(2000))
        account=self.bank.accounts.find_one({'_id':'cashbox:'+business})
        plans=list(self.db.economy_policy_schedule.find({'business_id':business}).sort('created_at',-1).limit(20))
        return {'business':public(row),'account':public(account) if account else None,'offers':[public(r) for r in offers[:50]],
            'has_more':len(offers)>50,'next_cursor':offers[49]['_id'] if len(offers)>50 else None,'plans':[public(r) for r in plans]}

    def suspend(self,business,actor,key,expected,active,reason):
        identifier(key);identifier(reason,'Motif');identifier(business)
        if type(expected) is not int or type(active) is not bool:raise EconomyError('INVALID_REQUEST','Révision et état requis.',400)
        digest=fingerprint({'business':business,'expected':expected,'active':active,'reason':reason})
        def run(s):
            audit_id=fingerprint({'actor':actor,'key':key})
            old=self.db.economy_business_reviews.find_one({'_id':audit_id},session=s)
            if old:
                if old['request_hash']!=digest:raise EconomyError('IDEMPOTENCY_CONFLICT','Cette demande existe avec un autre contenu.')
                return old['result']
            row=self.db.economy_businesses.find_one({'_id':business},session=s)
            if not row:raise EconomyError('BUSINESS_NOT_FOUND','Établissement introuvable.',404)
            if row.get('revision',0)!=expected:raise EconomyError('REVISION_CONFLICT','L’établissement a changé ; rechargez son état.')
            changes={'active':active,'revision':expected+1,'updated_at':timestamp()}
            result={**row,**changes}
            self.db.economy_businesses.update_one({'_id':business},{'$set':changes},session=s)
            self.db.economy_business_reviews.insert_one({'_id':audit_id,'actor_id':actor,'business_id':business,
                'request_hash':digest,'reason':reason,'created_at':timestamp(),'previous_active':row['active'],'result':result},session=s)
            return result
        return self.bank.transact(run)

    def schedule(self,business,actor,key,body):
        identifier(key);identifier(business)
        identifier(body.get('rule_version'));identifier(body.get('expected_rule_version'))
        identifier(body.get('reason'),'Motif')
        rate=body.get('tax_bps')
        if type(rate) is not int or not 0<=rate<=10000:raise EconomyError('INVALID_RULE','Taxe entière de 0 à 10000 points de base requise.',400)
        try:
            due=datetime.fromisoformat(body['effective_at'].replace('Z','+00:00'))
            if due.tzinfo is None:raise ValueError()
            due=due.astimezone(timezone.utc)
        except (ValueError,KeyError,AttributeError):raise EconomyError('INVALID_DATE','Date avec fuseau horaire requise.',400)
        if not datetime.now(timezone.utc)<due<=datetime.now(timezone.utc)+timedelta(days=180):raise EconomyError('INVALID_DATE','Choisissez une date future dans les 180 jours.',400)
        digest=fingerprint({'business':business,'body':body});ident=fingerprint({'actor':actor,'key':key})
        def run(s):
            old=self.db.economy_policy_schedule.find_one({'_id':ident},session=s)
            if old:
                if old['request_hash']!=digest:raise EconomyError('IDEMPOTENCY_CONFLICT','Cette programmation possède un autre contenu.')
                return old
            current=Commerce(self.bank).business(business,s)
            if current['rule_version']!=body['expected_rule_version']:raise EconomyError('REVISION_CONFLICT','Le barème a changé.')
            if body['rule_version']==current['rule_version']:raise EconomyError('NEW_RULE_VERSION_REQUIRED','Donnez une nouvelle version au barème.',400)
            treasury=body.get('treasury_account_id')
            if rate and (treasury=='cashbox:'+business or not self.bank.accounts.find_one({'_id':treasury,'pocket':'CASHBOX'},session=s)):
                raise EconomyError('TREASURY_REQUIRED','Une trésorerie distincte doit exister.',400)
            row={'_id':ident,'schedule_id':ident,'business_id':business,'actor_id':actor,'request_hash':digest,
                'key':key,'state':'SCHEDULED','effective_at':due.isoformat(),'created_at':timestamp(),
                'expected_rule_version':current['rule_version'],'rule_version':body['rule_version'],'tax_bps':rate,
                'treasury_account_id':treasury,'reason':body['reason']}
            self.db.economy_policy_schedule.insert_one(row,session=s);return row
        return self.bank.transact(run)

    def cancel_schedule(self,ident,actor):
        result=self.db.economy_policy_schedule.update_one({'_id':identifier(ident),'state':'SCHEDULED'},
            {'$set':{'state':'CANCELLED','cancelled_by':actor,'updated_at':timestamp()}})
        if not result.modified_count:raise EconomyError('INVALID_STATE','Cette programmation a déjà changé.')
        return {'schedule_id':ident,'state':'CANCELLED'}

    def publish_due(self,now=None):
        now=now or datetime.now(timezone.utc);results=[]
        for row in self.db.economy_policy_schedule.find({'state':'SCHEDULED','effective_at':{'$lte':now.isoformat()}}).sort('effective_at',1).limit(100):
            # The policy and the schedule state change in the same Mongo transaction.
            def run(s):
                current=self.db.economy_policy_schedule.find_one({'_id':row['_id'],'state':'SCHEDULED'},session=s)
                if not current:return None
                business=self.db.economy_businesses.find_one({'_id':current['business_id']},session=s)
                if not business or not business['active'] or business['rule_version']!=current['expected_rule_version']:
                    self.db.economy_policy_schedule.update_one({'_id':row['_id']},{'$set':{'state':'CONFLICT','updated_at':timestamp()}},session=s)
                    return {'schedule_id':row['_id'],'state':'CONFLICT'}
                tax=current['tax_bps'];treasury=current.get('treasury_account_id')
                if tax and not self.bank.accounts.find_one({'_id':treasury,'pocket':'CASHBOX'},session=s):
                    self.db.economy_policy_schedule.update_one({'_id':row['_id']},{'$set':{'state':'CONFLICT','updated_at':timestamp()}},session=s)
                    return {'schedule_id':row['_id'],'state':'CONFLICT'}
                changes={'rule_version':current['rule_version'],'tax_bps':tax,'treasury_account_id':treasury if tax else None}
                self.db.economy_business_rules.insert_one({'_id':fingerprint({'business':business['_id'],'version':current['rule_version']}),
                    'business_id':business['_id'],'actor_id':current['actor_id'],'created_at':timestamp(),
                    'previous_rule_version':business['rule_version'],'schedule_id':row['_id'],**changes},session=s)
                self.db.economy_businesses.update_one({'_id':business['_id']},{'$set':changes},session=s)
                self.db.economy_policy_schedule.update_one({'_id':row['_id']},{'$set':{'state':'PUBLISHED','updated_at':timestamp()}},session=s)
                return {'schedule_id':row['_id'],'state':'PUBLISHED'}
            try:
                result=self.bank.transact(run)
                if result:results.append(result)
            except DuplicateKeyError:
                self.db.economy_policy_schedule.update_one({'_id':row['_id'],'state':'SCHEDULED'},{'$set':{'state':'CONFLICT'}})
                results.append({'schedule_id':row['_id'],'state':'CONFLICT'})
        return results
