"""Explicit links between public lore, gameplay profiles and existing player accounts.

Never copies/reinitializes a player's bank, inventory or progression.
"""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL
from pymongo import ASCENDING
from pymongo.errors import DuplicateKeyError
from wiki.service import WikiStore, WikiError


class DirectoryError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message); self.status=status


def now(): return datetime.now(timezone.utc).isoformat()


def reason_text(body):
    value=body.get('reason','')
    if not isinstance(value,str) or not 3<=len(value.strip())<=500:raise DirectoryError('Indique un motif de 3 à 500 caractères.')
    return value.strip()


def public_link(row):
    if not row:return {'character_id':None,'character_name':None,'control_mode':'NPC','archived':False,'revision':0}
    return {k:row.get(k) for k in ['character_id','character_name','control_mode','archived','revision']}


class Directory:
    def __init__(self, db):
        self.db=db; self.links=db.character_links; self.audit=db.character_link_audit
        self.outbox=db.character_identity_outbox; self.wiki=WikiStore(db); self.initialized=False

    def initialize(self):
        if self.initialized:return
        self.links.create_index([('player_id',ASCENDING)],unique=True,partialFilterExpression={'player_id':{'$type':'string'}})
        self.audit.create_index('operation_id',unique=True)
        self.outbox.create_index([('sent',ASCENDING),('created_at',ASCENDING)])
        self.initialized=True

    def package(self):
        version=self.wiki.public_version(); return version,self.wiki.version_package(version)

    def public_links(self, ids):
        rows=list(self.links.find({'_id':{'$in':list(ids)}}))
        characters=list({r.get('character_id') for r in rows if r.get('character_id')})
        controlled={r['character_id'] for r in self.links.find({'character_id':{'$in':characters},'control_mode':'PLAYER'})}
        return {row['_id']:{**public_link(row),'automatic_spawn_blocked':row.get('control_mode')=='PLAYER' or row.get('character_id') in controlled} for row in rows}

    def inventory(self):
        version,package=self.package(); registry=package['registry']
        links={r['_id']:r for r in self.links.find({})}
        npcs=[]
        for row in self.db.npcs.find({}, {'_id':0,'npc_id':1,'name':1,'type':1,'enabled':1,'skin':1}):
            binding=links.get(row['npc_id'],{})
            npcs.append({**row,**public_link(binding),'player_id':binding.get('player_id')})
        players=[{'id':p['id'],'name':(p.get('name','')+' '+p.get('surname','')).strip(),'minecraft_name':p.get('pseudo_minecraft','')}
                 for p in self.db.players.find({}, {'_id':0,'id':1,'name':1,'surname':1,'pseudo_minecraft':1})]
        return {'version':version,'people':[{k:p.get(k) for k in ['id','name','category','familyId','location']} for p in registry['people']],
                'npcs':npcs,'players':players,'families':registry['families'],'roles':registry['roles'],'guilds':registry['guilds']}

    def _transact(self, fn):
        with self.db.client.start_session() as session:return session.with_transaction(fn)

    def _emit(self, npc, operation, session):
        self.outbox.update_one({'_id':operation+':'+npc},{'$setOnInsert':{'npc_id':npc,'sent':False,'created_at':now()}},upsert=True,session=session)

    def _lock_characters(self, ids, session):
        # Serialize competing creations/bindings without forbidding historical
        # profiles such as the two Carl Sand IDs required by existing quests.
        for ident in sorted(set(filter(None,ids))):
            self.db.character_identity_locks.update_one({'_id':ident},{'$inc':{'revision':1}},upsert=True,session=session)

    def bind(self, body, actor):
        ident=body.get('npc_id'); character=body.get('character_id') or None; player=body.get('player_id') or None
        mode=body.get('control_mode','NPC'); archived=body.get('archived',False); revision=body.get('expected_revision')
        operation=body.get('operation_id');reason=reason_text(body)
        if any(value is not None and (not isinstance(value,str) or len(value)>255) for value in [ident,character,player]):raise DirectoryError('Identifiant de profil, personnage ou joueur invalide.')
        if not isinstance(operation,str) or not 8<=len(operation)<=100:raise DirectoryError('Référence de demande manquante.')
        if not isinstance(ident,str) or not ident:raise DirectoryError('Choisis un profil de jeu.')
        if mode not in ['NPC','PLAYER'] or type(archived) is not bool or type(revision) is not int:raise DirectoryError('Configuration de profil invalide.')
        if (mode=='PLAYER') != bool(player):raise DirectoryError('Le contrôle PLAYER exige un compte joueur ; le mode NPC ne doit pas en conserver.')
        if not 3<=len(reason)<=500:raise DirectoryError('Indique un motif de 3 à 500 caractères.')
        version,package=self.package(); people={p['id']:p for p in package['registry']['people']}
        if character and character not in people:raise DirectoryError('Fiche de lore introuvable.',404)
        if body.get('base_version')!=version:raise DirectoryError('Le registre de lore a changé. Recharge avant de confirmer.',409)
        self.initialize()
        signature={k:body.get(k) for k in ['npc_id','character_id','player_id','control_mode','archived','expected_revision','base_version','reason']}
        def write(session):
            previous=self.audit.find_one({'operation_id':operation},session=session)
            if previous:
                if previous.get('request')!=signature or previous.get('actor')!=actor:raise DirectoryError('Référence déjà utilisée pour une autre demande.',409)
                return previous['result']
            npc=self.db.npcs.find_one({'npc_id':ident},session=session)
            if not npc:raise DirectoryError('PNJ introuvable.',404)
            before=self.links.find_one({'_id':ident},session=session)
            self._lock_characters([character,(before or {}).get('character_id')],session)
            if (before or {}).get('revision',0)!=revision:raise DirectoryError('Ce profil a changé dans une autre session. Recharge-le.',409)
            if player and not self.db.players.find_one({'id':player},session=session):raise DirectoryError('Compte joueur introuvable.',404)
            if mode=='PLAYER' and not character:raise DirectoryError('Associe une fiche de lore avant de choisir le joueur.')
            other=self.links.find_one({'character_id':character,'control_mode':'PLAYER'},session=session) if character and mode=='PLAYER' else None
            if other and other['_id']!=ident:raise DirectoryError('Ce personnage est déjà contrôlé par un joueur. Utilise son profil existant.',409)
            occupied=self.links.find_one({'player_id':player},session=session) if player else None
            if occupied and occupied['_id']!=ident:raise DirectoryError('Ce compte contrôle déjà un autre profil. Délie-le explicitement avant de changer.',409)
            row={'_id':ident,'character_id':character,'character_name':people[character]['name'] if character else None,
                 'control_mode':mode,'archived':archived,'revision':revision+1,'updated_at':now(),'updated_by':actor}
            if player:row['player_id']=player
            result={**public_link(row),'npc_id':ident,'player_id':player,'sync':'pending'}
            if before:self.links.replace_one({'_id':ident,'revision':revision},row,session=session)
            else:self.links.insert_one(row,session=session)
            self.audit.insert_one({'operation_id':operation,'actor':actor,'reason':reason,'before':before,'after':row,'request':signature,'result':result,'created_at':now()},session=session)
            affected={ident}|{r['_id'] for r in self.links.find({'character_id':{'$in':list(filter(None,[character,(before or {}).get('character_id')]))}},session=session)}
            for affected_id in affected:self._emit(affected_id,operation,session)
            return result
        try:return self._transact(write)
        except DuplicateKeyError as exc:raise DirectoryError('Association concurrente ou compte déjà attribué. Recharge avant de réessayer.',409) from exc

    def create_profile(self, body, actor):
        character=body.get('character_id');operation=body.get('operation_id');version,package=self.package()
        person=next((p for p in package['registry']['people'] if p['id']==character),None)
        if not person:raise DirectoryError('Fiche de lore introuvable.',404)
        if version!=body.get('base_version'):raise DirectoryError('Le registre a changé. Recharge avant de créer le profil.',409)
        if not isinstance(operation,str) or not 8<=len(operation)<=100:raise DirectoryError('Référence de demande manquante.')
        reason=reason_text(body)
        if not 3<=len(reason)<=500:raise DirectoryError('Indique le motif de création.')
        self.initialize(); ident='npc_'+uuid5(NAMESPACE_URL,actor+':'+operation).hex
        def write(session):
            prior=self.audit.find_one({'operation_id':operation},session=session)
            if prior:
                if prior.get('actor')!=actor or prior.get('action')!='create-profile' or prior['result']['character_id']!=character:raise DirectoryError('Référence déjà utilisée.',409)
                return prior['result']
            self._lock_characters([character],session)
            if self.links.find_one({'character_id':character,'archived':False},session=session):raise DirectoryError('Ce personnage possède déjà un profil. Ouvre-le au lieu d’en créer un double.',409)
            npc={'npc_id':ident,'name':person['name'],'type':'DECO','skin':None,'dialogue':[],'tags':[],'enabled':True,
                 'description':person.get('biography',''),'profile_image':'NPCdefault.png','met_by':[],'region':person.get('location') or 'Royaume de Renblood',
                 'idle_behavior':'LOOK_AT_PLAYER','ambient_lines':[],'shop_id':None,'currency':None,'open_message':None,'trade_category':None,
                 'quest_ids':[],'quest_giver':False,'quest_validator':False,'dialogue_by_state':{},'implementation':{},
                 'created_at':datetime.now(timezone.utc),'updated_at':datetime.now(timezone.utc)}
            self.db.npcs.insert_one(npc,session=session)
            row={'_id':ident,'character_id':character,'character_name':person['name'],'control_mode':'NPC','archived':False,'revision':1,'updated_at':now(),'updated_by':actor}
            self.links.insert_one(row,session=session);result={**public_link(row),'npc_id':ident,'player_id':None,'sync':'pending'}
            self.audit.insert_one({'operation_id':operation,'action':'create-profile','actor':actor,'reason':reason,'result':result,'created_at':now()},session=session)
            self._emit(ident,operation,session);return result
        try:return self._transact(write)
        except DuplicateKeyError as exc:raise DirectoryError('Création concurrente. Recharge le répertoire avant de réessayer.',409) from exc

    def lore(self, ident):
        version,package=self.package();person=next((p for p in package['registry']['people'] if p['id']==ident),None)
        if not person:raise DirectoryError('Personnage introuvable.',404)
        return {'version':version,'person':person}

    def prepare_lore(self, body, actor):
        version,package=self.package()
        if body.get('base_version')!=version:raise DirectoryError('Le registre a changé. Recharge la fiche.',409)
        if body.get('public_confirmed') is not True:raise DirectoryError('Confirme que le texte est public, sans secrets staff.')
        changes=body.get('fields');reason=reason_text(body)
        allowed={'name','title','occupation','publicOffice','location','county','biography','birth','death','vital','reportedAge','spouseLabel','houseId','familyId','guildIds','roleIds','aliases','category'}
        if not isinstance(changes,dict) or set(changes)-allowed:raise DirectoryError('Champs de fiche inconnus.')
        if not 3<=len(reason)<=500:raise DirectoryError('Indique un motif pour la modification du registre.')
        candidate=deepcopy(package);people=candidate['registry']['people'];ident=body.get('person_id')
        if ident:
            person=next((p for p in people if p['id']==ident),None)
            if not person:raise DirectoryError('Personnage introuvable.',404)
        else:
            ident='C'+uuid4().hex[:16]
            person={'id':ident,'name':'','houseId':None,'familyId':None,'category':'Personnage secondaire','title':'','occupation':'','publicOffice':'',
                    'location':'','county':'','biography':'','birth':None,'death':None,'vital':'unknown','reportedAge':'','spouseLabel':'','reputation':None,
                    'fortune':None,'notable':False,'guildIds':[],'roleIds':[],'aliases':[],'lineage':None};people.append(person)
        person.update(changes)
        if not isinstance(person['name'],str) or not 1<=len(person['name'].strip())<=150:raise DirectoryError('Indique un nom de 1 à 150 caractères.')
        related=body.get('related_to');relation=body.get('relationship')
        if related:
            if related==ident or not any(p['id']==related for p in people):raise DirectoryError('Personnage de référence invalide.')
            if relation not in ['child','parent','spouse','sibling']:raise DirectoryError('Choisis un lien familial explicite.')
            a,b=(ident,related) if relation=='parent' else (related,ident)
            kind='parent' if relation in ['child','parent'] else relation
            if not any(e['type']==kind and ((e['a']==a and e['b']==b) or kind!='parent' and e['a']==b and e['b']==a) for e in candidate['registry']['relations']):
                # Preserve the shape of the public relation format.
                template={'id':'R'+uuid4().hex[:16],'a':a,'b':b,'type':kind}
                candidate['registry']['relations'].append(template)
        draft=self.wiki.create_draft(candidate,version,actor,reason)
        self.wiki.drafts.update_one({'_id':draft['_id']},{'$set':{'editor':'character-directory','person_id':ident}})
        return {'draft_id':draft['_id'],'revision':draft['revision'],'person_id':ident,'changes':draft['changes'],'base_version':version}

    def publish_lore(self, body, actor):
        reason=body.get('reason','')
        if not isinstance(reason,str) or not 3<=len(reason.strip())<=500:raise DirectoryError('Indique un motif de publication de 3 à 500 caractères.')
        draft=self.wiki.draft(body.get('draft_id'))
        if draft.get('editor')!='character-directory':raise DirectoryError('Ce brouillon doit être traité dans son atelier d’origine.',409)
        if draft['status']=='PUBLISHED':return {'version':draft['publishedVersion'],'person_id':draft['person_id'],'already_published':True}
        revision=body.get('revision');decisions={c['key']:'accept' for c in draft['changes']}
        if type(revision) is not int:raise DirectoryError('Révision manquante.')
        if draft['revision']==revision:
            saved=self.wiki.save(draft['_id'],revision,decisions)
        elif draft['revision']==revision+1 and draft.get('decisions')==decisions:
            saved=draft  # Publication interrupted after saving the explicit review.
        else:raise DirectoryError('Le brouillon a changé. Recharge son aperçu.',409)
        version=self.wiki.publish(saved['_id'],saved['revision'],actor,reason)
        return {'version':version,'person_id':draft['person_id']}
