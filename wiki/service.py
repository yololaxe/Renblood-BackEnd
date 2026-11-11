"""Immutable public wiki versions and optimistic, reviewed publication.

Only compiled public packages are accepted. Raw Sheets are never served here.
"""
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
from uuid import uuid4


class WikiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def stamp():
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def seed():
    return json.loads((Path(__file__).parent / 'seed.json').read_text(encoding='utf-8'))


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def schema(values):
    result = {'types': set(type(value) for value in values)}
    objects = [value for value in values if isinstance(value, dict)]
    if objects:
        keys = set().union(*(value.keys() for value in objects))
        result['fields'] = {key: schema([value[key] for value in objects if key in value]) for key in keys}
        result['required'] = set.intersection(*(set(value) for value in objects))
    arrays = [value for value in values if isinstance(value, list)]
    children = [item for value in arrays for item in value]
    if children:
        result['items'] = schema(children)
    return result


@lru_cache(maxsize=1)
def package_schema():
    return schema([seed()])


def check_shape(value, shape, path='package'):
    # Nulls are allowed for optional public fields, never unknown object keys.
    if value is None and type(None) in shape['types']:
        return
    allowed = shape['types']
    if type(value) not in allowed and not (allowed == {type(None)} and isinstance(value, (str, int, float)) and not isinstance(value, bool)):
        raise WikiError(f'Type de donnée incorrect : {path}.')
    if isinstance(value, str) and len(value) > 30000:
        raise WikiError(f'Texte trop long : {path}.')
    if isinstance(value, (int, float)) and not isinstance(value, bool) and (abs(value) > 9007199254740991 or not math.isfinite(value)):
        raise WikiError(f'Valeur numérique invalide : {path}.')
    if isinstance(value, dict):
        if shape.get('required', set()) - value.keys():
            raise WikiError(f'Champs publics requis manquants : {path}.')
        for key, child in value.items():
            if key not in shape.get('fields', {}):
                raise WikiError(f'Champ non public ou inconnu : {path}.{key}.')
            check_shape(child, shape['fields'][key], f'{path}.{key}')
    if isinstance(value, list):
        if len(value) > 3000:
            raise WikiError(f'Trop d’entrées : {path}.')
        for child in value:
            if 'items' not in shape:
                if value: raise WikiError(f'Liste non prise en charge : {path}.')
            else:
                check_shape(child, shape['items'], path + '[]')


def validate(package):
    if not isinstance(package, dict) or set(package) != {'registry', 'books'}:
        raise WikiError('Importer un paquet public contenant registry et books ; les exports Sheets bruts ne sont pas acceptés.')
    check_shape(package, package_schema())
    data = package['registry']
    if not isinstance(data, dict) or any(key not in data for key in seed()['registry']):
        raise WikiError('Le registre public est incomplet.')
    maps = {}
    for name in ['people', 'families', 'relations', 'guilds', 'roles', 'concepts', 'locations', 'events', 'books', 'seats']:
        rows = data[name]
        if not isinstance(rows, list): raise WikiError(f'Liste requise : {name}.')
        ids = [row.get('id') for row in rows]
        if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
            raise WikiError(f'Identifiants manquants ou en double : {name}.')
        maps[name] = set(ids)
    if not data['people'] or not package['books']:
        raise WikiError('Les personnages et les livres ne peuvent pas être vidés.')
    parents = {}
    for edge in data['relations']:
        if edge.get('a') not in maps['people'] or edge.get('b') not in maps['people'] or edge['a'] == edge['b']:
            raise WikiError('Un lien familial désigne un personnage absent ou lui-même.')
        if edge.get('type') not in {'parent', 'spouse', 'sibling'}:
            raise WikiError('Type de relation inconnu.')
        if edge['type'] == 'parent': parents.setdefault(edge['b'], set()).add(edge['a'])
    visited = set()
    for ident in maps['people']:
        stack = [(ident, False)]
        active = set()
        while stack:
            current, leaving = stack.pop()
            if leaving: active.discard(current); visited.add(current); continue
            if current in active: raise WikiError('Une filiation crée une boucle d’ascendance.')
            if current in visited: continue
            if len(parents.get(current, [])) > 2: raise WikiError('Un personnage a plus de deux parents.')
            active.add(current); stack.append((current, True))
            stack.extend((parent, False) for parent in parents.get(current, []))
    for person in data['people']:
        for key, target in [('familyId', 'families'), ('houseId', 'families')]:
            if person.get(key) and person[key] not in maps[target]: raise WikiError(f'Famille absente pour {person["id"]}.')
        for key, target in [('roleIds', 'roles'), ('guildIds', 'guilds')]:
            if not isinstance(person.get(key), list) or any(ident not in maps[target] for ident in person[key]): raise WikiError(f'Liens invalides pour {person["id"]}.')
        if not isinstance(person.get('name'), str) or not person['name'].strip(): raise WikiError('Un personnage n’a pas de nom.')
        if not isinstance(person.get('aliases'), list): raise WikiError('Liste d’alias requise.')
    for event in data['events']:
        if event.get('personId') not in maps['people']: raise WikiError('Événement associé à un personnage absent.')
    for entry in data['government']:
        if entry.get('personId') and entry['personId'] not in maps['people']: raise WikiError('Membre du gouvernement absent du registre.')
    for place in data['locations']:
        if place.get('leaderId') and place['leaderId'] not in maps['people']: raise WikiError('Dirigeant de lieu absent du registre.')
        if place.get('coords') is not None and (len(place['coords']) != 2 or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in place['coords'])): raise WikiError('Les coordonnées d’un lieu doivent contenir deux nombres.')
    for guild in data['guilds']:
        if guild.get('leaderId') and guild['leaderId'] not in maps['people']: raise WikiError('Dirigeant de guilde absent.')
    for seat in data['seats']:
        if seat.get('personId') and seat['personId'] not in maps['people']: raise WikiError('Titulaire de siège absent.')
    if not isinstance(package['books'], list) or set(book.get('id') for book in package['books']) != maps['books']:
        raise WikiError('Le sommaire et les textes des livres ne correspondent pas.')
    full_ids = [book.get('id') for book in package['books']]
    if len(full_ids) != len(set(full_ids)): raise WikiError('Les textes contiennent un identifiant de livre en double.')
    for book in package['books']:
        index = next(item for item in data['books'] if item['id'] == book['id'])
        chapters = book.get('chapters')
        if not isinstance(chapters, list) or not chapters: raise WikiError('Livre sans chapitre.')
        for rows in [chapters, *(chapter.get('sections', []) for chapter in chapters)]:
            ids = [row.get('id') for row in rows]
            if not ids or len(ids) != len(set(ids)): raise WikiError('Chapitres ou sections invalides.')
        expected = [{**chapter, 'sections': [{'id': section['id'], 'title': section['title']} for section in chapter['sections']]} for chapter in chapters]
        if index['chapters'] != expected: raise WikiError('Les titres et sections du livre divergent de son sommaire.')
        for chapter in chapters:
            for section in chapter['sections']:
                if not isinstance(section.get('paragraphs'), list) or any(not isinstance(p, str) for p in section['paragraphs']): raise WikiError('Paragraphes invalides.')
    return deepcopy(package)


def differences(before, after):
    result = []
    def add(collection, ident, field, old, new, label):
        if old != new:
            change = {'collection': collection, 'id': ident, 'field': field, 'before': old, 'after': new, 'label': label}
            change['key'] = digest(change)[:24]
            result.append(change)
    for collection in before['registry']:
        if collection in {'version', 'publishedOn'}: continue
        left, right = before['registry'][collection], after['registry'][collection]
        if isinstance(left, list) and all(isinstance(item, dict) and 'id' in item for item in left + right):
            old = {item['id']: item for item in left}; new = {item['id']: item for item in right}
            for ident in sorted(old.keys() | new.keys()):
                a, b = old.get(ident), new.get(ident)
                label = (b or a).get('name') or (b or a).get('title') or ident
                if a is None or b is None: add(collection, ident, '$record', a, b, label)
                else:
                    for field in sorted(a.keys() | b.keys()): add(collection, ident, field, a.get(field), b.get(field), label)
        else: add('$registry', collection, '$value', left, right, collection)
    # Full book content is reviewed together with its public table of contents.
    if before['books'] != after['books']: add('$books', 'texts', '$value', before['books'], after['books'], 'Textes complets des livres')
    return result


def resolve_changes(before, after, decisions):
    changes = differences(before, after)
    if not changes: raise WikiError('Cette version ne comporte aucun changement.')
    if not isinstance(decisions, dict) or any(decisions.get(change['key']) not in {'accept', 'keep'} for change in changes):
        raise WikiError('Chaque changement doit être accepté ou conservé à sa valeur actuelle.')
    result = deepcopy(before)
    for change in changes:
        if decisions[change['key']] != 'accept': continue
        collection, ident, field = change['collection'], change['id'], change['field']
        if collection == '$books': result['books'] = deepcopy(change['after'])
        elif collection == '$registry': result['registry'][ident] = deepcopy(change['after'])
        else:
            rows = result['registry'][collection]
            if field == '$record':
                rows[:] = [row for row in rows if row['id'] != ident]
                if change['after'] is not None: rows.append(deepcopy(change['after']))
            else: next(row for row in rows if row['id'] == ident)[field] = deepcopy(change['after'])
    return validate(result)


class WikiStore:
    def __init__(self, db):
        self.states, self.versions, self.drafts = db.wiki_state, db.wiki_versions, db.wiki_drafts

    def initial(self):
        existing = self.states.find_one({'_id': 'public'})
        if existing: return existing
        package = seed(); version = package['registry']['version']
        self.versions.update_one({'_id': version}, {'$setOnInsert': {'package': package, 'createdAt': stamp(), 'actor': 'initial', 'reason': 'Version publique de référence'}}, upsert=True)
        self.states.update_one({'_id': 'public'}, {'$setOnInsert': {'version': version, 'revision': 0, 'history': [], 'publication': None}}, upsert=True)
        return self.states.find_one({'_id': 'public'})

    def current(self):
        state = self.states.find_one({'_id': 'public'})
        if not state: return {'version': seed()['registry']['version'], 'revision': 0, 'history': [], 'publication': None}, deepcopy(seed())
        version = self.versions.find_one({'_id': state['version']})
        if not version: raise WikiError('La version publiée est temporairement indisponible.', 503)
        return state, version['package']

    @staticmethod
    def expired(publication):
        try:
            return (datetime.now(timezone.utc) - datetime.fromisoformat(publication['startedAt'])).total_seconds() > 120
        except (KeyError, TypeError, ValueError):
            return True

    @staticmethod
    def published_event(state, token):
        return next((event for event in reversed(state.get('history', [])) if event.get('publicationToken') == token), None) if token else None

    def release_publication(self, state, token):
        # Revision increments fence an expired worker, including after a restore
        # back to the exact same content version (the ABA case).
        result = self.states.update_one({'_id': 'public', 'revision': state['revision'], 'publication.token': token}, {'$set': {'publication': None}, '$inc': {'revision': 1}})
        return result.modified_count == 1

    def overview(self):
        self.initial()
        # Reconcile recent abandoned reviews before showing their status.
        rows = list(self.drafts.find({}, {'package': 0, 'changes': 0}).sort('updatedAt', -1).limit(10))
        for row in rows:
            if row['status'] == 'PUBLISHING': self.draft(row['_id'])
        state = self.states.find_one({'_id': 'public'})
        pending = state.get('publication')
        if pending and self.expired(pending):
            self.release_publication(state, pending['token'])
            state = self.states.find_one({'_id': 'public'})
        # Only versions which actually went public can be restored. A losing
        # concurrent writer may have prepared an immutable, unpublished version.
        allowed = {state['version'], seed()['registry']['version']} | {event[key] for event in state.get('history', []) for key in ['from', 'to']}
        versions = list(self.versions.find({'$or': [{'published': True}, {'_id': {'$in': list(allowed)}}]}, {'package': 0}).sort('createdAt', -1).limit(30))
        drafts = list(self.drafts.find({}, {'package': 0, 'changes': 0}).sort('updatedAt', -1).limit(10))
        return {'current': state['version'], 'revision': state['revision'], 'history': state.get('history', []), 'publication': state.get('publication'), 'versions': [{**row, 'id': row['_id'], '_id': None} for row in versions], 'drafts': [{**row, 'id': row['_id'], '_id': None} for row in drafts]}

    def create_draft(self, package, base, actor, reason):
        package = validate(package); state, current = self.current()
        if base != state['version']: raise WikiError('La version publiée a changé. Rechargez avant de préparer cet import.', 409)
        changes = differences(current, package)
        if not changes: raise WikiError('Aucun changement à examiner.')
        if len(changes) > 5000: raise WikiError('Import trop important : divisez la mise à jour.')
        draft = {'_id': str(uuid4()), 'package': package, 'baseVersion': base, 'changes': changes, 'decisions': {}, 'revision': 0, 'reason': reason, 'actor': actor, 'updatedAt': stamp(), 'status': 'DRAFT', 'changeCount': len(changes)}
        self.drafts.insert_one(deepcopy(draft))
        return draft

    def save(self, ident, revision, decisions):
        self.draft(ident)
        draft = self.drafts.find_one({'_id': ident})
        keys = {change['key'] for change in draft['changes']}
        if not isinstance(decisions, dict) or any(key not in keys or value not in {'accept', 'keep'} for key, value in decisions.items()): raise WikiError('Décisions invalides.')
        result = self.drafts.update_one({'_id': ident, 'revision': revision, 'status': 'DRAFT'}, {'$set': {'decisions': decisions, 'updatedAt': stamp()}, '$inc': {'revision': 1}})
        if result.modified_count != 1: raise WikiError('Ce brouillon a été modifié par un autre administrateur. Rechargez-le.', 409)
        return self.drafts.find_one({'_id': ident})

    def draft(self, ident):
        result = self.drafts.find_one({'_id': ident})
        if not result: raise WikiError('Brouillon introuvable.', 404)
        if result['status'] != 'PUBLISHING': return result
        state = self.states.find_one({'_id': 'public'}) or {}
        token = result.get('publicationToken')
        query = {'_id': ident, 'revision': result['revision'], 'status': 'PUBLISHING'}
        if token: query['publicationToken'] = token
        event = self.published_event(state, token)
        if event:
            self.versions.update_one({'_id': event['to']}, {'$set': {'published': True}})
            self.drafts.update_one(query, {'$set': {'status': 'PUBLISHED', 'publishedVersion': event['to']}})
        elif not token and state.get('version') == result.get('publishedVersion'):
            # Reconcile reviews created by the previous deployed implementation.
            self.drafts.update_one(query, {'$set': {'status': 'PUBLISHED'}})
        elif self.expired({'startedAt': result.get('publicationStartedAt')}):
            pending = state.get('publication')
            if token and pending and pending.get('token') == token:
                if not self.release_publication(state, token): return self.drafts.find_one({'_id': ident})
                # A committed publication and a release cannot both win the CAS.
            self.drafts.update_one(query, {'$set': {'status': 'DRAFT', 'updatedAt': stamp()}, '$inc': {'revision': 1}})
        return self.drafts.find_one({'_id': ident})

    def preview(self, ident):
        draft = self.draft(ident); state, current = self.current()
        if draft['baseVersion'] != state['version']: raise WikiError('Brouillon dépassé : la version publiée a changé.', 409)
        decisions = {change['key']: draft['decisions'].get(change['key'], 'keep') for change in draft['changes']}
        return resolve_changes(current, draft['package'], decisions)

    def publish(self, ident, revision, actor, reason):
        draft = self.draft(ident)
        if draft['revision'] != revision or draft['status'] != 'DRAFT': raise WikiError('Le brouillon a changé. Rechargez-le.', 409)
        state, before = self.current()
        if draft['baseVersion'] != state['version']: raise WikiError('Brouillon dépassé : la version publiée a changé.', 409)
        pending = state.get('publication')
        if pending:
            if not self.expired(pending): raise WikiError('Une publication est déjà en cours. Actualisez l’atelier avant de réessayer.', 409)
            self.release_publication(state, pending['token'])
            raise WikiError('Une publication interrompue a été libérée. Actualisez l’atelier avant de continuer.', 409)
        package = resolve_changes(before, draft['package'], draft['decisions'])
        if not differences(before, package): raise WikiError('Aucun changement accepté à publier.')
        package['registry']['publishedOn'] = stamp()[:10]
        content = deepcopy(package); content['registry'].pop('version'); content['registry'].pop('publishedOn')
        version = 'wiki-live-' + digest(content)[:16]
        package['registry']['version'] = version
        token = str(uuid4()); started = stamp()
        claim = {'_id': ident, 'revision': revision, 'status': 'PUBLISHING', 'publicationToken': token}
        claimed = self.drafts.update_one({'_id': ident, 'revision': revision, 'status': 'DRAFT'}, {'$set': {'status': 'PUBLISHING', 'publicationStartedAt': started, 'publishedVersion': version, 'publicationToken': token}})
        if claimed.modified_count != 1: raise WikiError('Le brouillon a changé pendant la publication. Rechargez-le.', 409)
        reserved = None
        try:
            publication = {'token': token, 'draftId': ident, 'startedAt': started, 'actor': actor}
            result = self.states.update_one({'_id': 'public', 'revision': state['revision'], 'version': state['version'], 'publication': None}, {'$set': {'publication': publication}, '$inc': {'revision': 1}})
            if result.modified_count != 1: raise WikiError('Une publication concurrente a eu lieu. Rechargez avant de continuer.', 409)
            reserved = {**state, 'revision': state['revision'] + 1, 'publication': publication}
            self.versions.update_one({'_id': version}, {'$setOnInsert': {'package': package, 'createdAt': started, 'actor': actor, 'reason': reason}}, upsert=True)
            self.switch(reserved, version, actor, reason, 'publish', token=token, draft_id=ident)
        except Exception:
            current = self.states.find_one({'_id': 'public'}) or {}
            event = self.published_event(current, token)
            if event:
                self.versions.update_one({'_id': version}, {'$set': {'published': True}})
                self.drafts.update_one(claim, {'$set': {'status': 'PUBLISHED', 'publishedVersion': version}})
                return version
            if reserved and (current.get('publication') or {}).get('token') == token:
                self.release_publication(current, token)
            self.drafts.update_one(claim, {'$set': {'status': 'DRAFT', 'updatedAt': stamp()}, '$inc': {'revision': 1}})
            raise
        self.versions.update_one({'_id': version}, {'$set': {'published': True}})
        self.drafts.update_one(claim, {'$set': {'status': 'PUBLISHED', 'publishedVersion': version}})
        return version

    def switch(self, state, version, actor, reason, action, token=None, draft_id=None):
        event = {'at': stamp(), 'from': state['version'], 'to': version, 'actor': actor, 'reason': reason, 'action': action}
        query = {'_id': 'public', 'revision': state['revision'], 'version': state['version']}
        if token:
            query['publication.token'] = token
            event.update({'publicationToken': token, 'draftId': draft_id})
        result = self.states.update_one(query, {'$set': {'version': version, 'publication': None}, '$inc': {'revision': 1}, '$push': {'history': {'$each': [event], '$slice': -50}}})
        if result.modified_count != 1: raise WikiError('Une publication concurrente a eu lieu. Rechargez avant de continuer.', 409)

    def restore(self, version, revision, actor, reason):
        state = self.initial()
        if state['revision'] != revision: raise WikiError('Une autre publication a eu lieu. Rechargez.', 409)
        target = self.versions.find_one({'_id': version})
        historical = {seed()['registry']['version']} | {event[key] for event in state.get('history', []) for key in ['from', 'to']}
        if not target or not (target.get('published') or version in historical): raise WikiError('Version publiée introuvable.', 404)
        if version == state['version']: raise WikiError('Cette version est déjà publiée.')
        self.switch(state, version, actor, reason, 'restore')
        return version
