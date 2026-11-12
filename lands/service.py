"""Private cadastral projection. Minecraft remains the authority for every edit."""
from datetime import datetime, timezone
from uuid import UUID
import re
from pymongo import ReplaceOne, UpdateOne
from pymongo.errors import DuplicateKeyError, BulkWriteError

CENTER = {'name': 'Shaleton', 'x': -716, 'z': -1300, 'chunkX': -45, 'chunkZ': -82}
RADIUS = 8
LIMIT = 1875000
TYPES = {'PLAYER', 'CITY', 'GUILD', 'FAMILY', 'RELIGIOUS', 'KINGDOM', 'PUBLIC', 'UNKNOWN', 'SERVER'}


class LandError(Exception):
    def __init__(self, message, status=400): super().__init__(message); self.status = status


def now(): return datetime.now(timezone.utc).isoformat()


def text(value, maximum=128, empty=True):
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise LandError('Texte absent ou trop long.')
    return value.strip()


def identity(value):
    try: return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError): raise LandError('UUID Minecraft invalide.')


def coordinate(value):
    if type(value) is not int or abs(value) > LIMIT: raise LandError('Coordonnée de chunk invalide.')
    return value


def dimension(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', value) or len(value) > 128:
        raise LandError('Dimension invalide.')
    return value


def merge(spans):
    result = []
    for start, end in sorted(spans):
        if result and start <= result[-1][1] + 1: result[-1][1] = max(result[-1][1], end)
        else: result.append([start, end])
    return result


def snapshot(value):
    if not isinstance(value, dict) or not re.fullmatch('[a-f0-9]{64}', str(value.get('hash', ''))):
        raise LandError('Empreinte du cadastre invalide.')
    plots = value.get('plots')
    if not isinstance(plots, list) or len(plots) > 4096: raise LandError('Cadastre trop volumineux.')
    ids, cells, result = set(), set(), []
    for row in plots:
        if not isinstance(row, dict): raise LandError('Parcelle invalide.')
        ident = text(row.get('id'), empty=False)
        if ident.lower() in ids: raise LandError('Identifiant de parcelle dupliqué.')
        ids.add(ident.lower())
        dim = row.get('dimension') or 'minecraft:overworld'
        dimension(dim)
        out = {key: text(row.get(key, ''), 500 if key == 'description' else 128) for key in ['name', 'owner', 'city', 'color', 'description']}
        owner_type = row.get('ownerType') or 'UNKNOWN'
        if owner_type not in TYPES: raise LandError('Type de propriétaire inconnu.')
        out.update(id=ident, dimension=dim, ownerType=owner_type, chunks=[])
        chunks = row.get('chunks', [])
        if not isinstance(chunks, list): raise LandError('Chunks invalides.')
        for chunk in chunks:
            if not isinstance(chunk, dict): raise LandError('Chunk invalide.')
            x, z = coordinate(chunk.get('x')), coordinate(chunk.get('z'))
            key = (dim, x, z)
            if key in cells: raise LandError('Attribution de chunk dupliquée.')
            cells.add(key); out['chunks'].append({'x': x, 'z': z})
            if len(cells) > 50000: raise LandError('Limite de chunks du cadastre atteinte.')
        result.append(out)
    return {'hash': value['hash'], 'plots': result}


def change(value):
    if not isinstance(value, dict): raise LandError('Modification invalide.')
    action = value.get('action')
    if action not in {'create', 'update', 'assign', 'unclaim'}: raise LandError('Action inconnue.')
    ident = text(value.get('plotId'), empty=False)
    if not re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}', ident): raise LandError('Utilisez un identifiant simple pour la parcelle.')
    result = {'action': action, 'plotId': ident, 'dimension': dimension(value.get('dimension'))}
    if action in {'create', 'update'}:
        metadata = value.get('metadata')
        if not isinstance(metadata, dict): raise LandError('Fiche de parcelle requise.')
        result['metadata'] = {key: text(metadata.get(key, ''), 500 if key == 'description' else 128, key != 'name') for key in ['name', 'owner', 'city', 'description']}
        color = metadata.get('color', '')
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color): raise LandError('Couleur hexadécimale requise.')
        owner_type = metadata.get('ownerType')
        if owner_type not in TYPES: raise LandError('Type de propriétaire inconnu.')
        result['metadata'].update(color=color, ownerType=owner_type)
    chunks = value.get('chunks', [])
    if not isinstance(chunks, list) or len(chunks) > 256: raise LandError('Sélectionnez au maximum 256 chunks à la fois.')
    selected = set()
    for chunk in chunks:
        if not isinstance(chunk, dict): raise LandError('Chunk invalide.')
        selected.add((coordinate(chunk.get('x')), coordinate(chunk.get('z'))))
    if action in {'assign', 'unclaim'} and not selected: raise LandError('Sélectionnez au moins un chunk.')
    result['chunks'] = [{'x': x, 'z': z} for x, z in sorted(selected)]
    return result


class Cadastre:
    def __init__(self, database): self.db = database

    def initialize(self):
        self.db.land_discovery.create_index([('world', 1), ('minecraft', 1), ('dimension', 1), ('z', 1)])
        self.db.land_commands.create_index([('world', 1), ('state', 1), ('createdAt', 1)])

    def sync(self, body):
        key = text(body.get('worldKey'), 64, False)
        if not re.fullmatch(r'[a-z0-9_-]+', key): raise LandError('Identifiant de monde invalide.')
        world_id = identity(body.get('worldId'))
        catalogue = snapshot(body['snapshot']) if 'snapshot' in body else None
        # Validate the entire exploration batch before changing stored knowledge.
        rows = body.get('discoveries', [])
        if not isinstance(rows, list) or len(rows) > 128: raise LandError('Lot de découvertes trop volumineux.')
        discovery = []
        for row in rows:
            if not isinstance(row, dict): raise LandError('Découverte invalide.')
            mc, dim, z = identity(row.get('minecraft')), dimension(row.get('dimension')), coordinate(row.get('z'))
            spans = row.get('spans')
            if not isinstance(spans, list) or not 1 <= len(spans) <= 512: raise LandError('Intervalles de découverte invalides.')
            intervals = []
            for span in spans:
                if not isinstance(span, list) or len(span) != 2: raise LandError('Intervalle invalide.')
                start, end = coordinate(span[0]), coordinate(span[1])
                if start > end: raise LandError('Intervalle inversé.')
                intervals.append([start, end])
            discovery.append((mc, dim, z, merge(intervals)))
        results = body.get('results', [])
        if not isinstance(results, list) or len(results) > 1: raise LandError('Résultat de modification invalide.')
        for result in results:
            if not isinstance(result, dict) or result.get('state') not in {'APPLIED', 'CONFLICT', 'REJECTED'}:
                raise LandError('État de modification invalide.')
            identity(result.get('id')); text(result.get('message', ''), 500)
        initial = {'worldId': world_id, 'hash': '', 'plots': [], 'createdAt': now()}
        try: self.db.land_worlds.update_one({'_id': key}, {'$setOnInsert': initial}, upsert=True)
        except DuplicateKeyError: pass
        world = self.db.land_worlds.find_one({'_id': key})
        if world['worldId'] != world_id: raise LandError('Ce nom de cadastre est déjà associé à un autre monde. Utilisez une autre webWorldKey.', 409)
        if not catalogue and not world['hash']: raise LandError('Le premier envoi doit contenir le cadastre.', 409)
        updates = {'syncedAt': now()}
        if catalogue: updates.update(catalogue)
        self.db.land_worlds.update_one({'_id': key, 'worldId': world_id}, {'$set': updates})
        self._merge_rows(world_id, discovery)
        for result in results:
            self.db.land_commands.update_one({'_id': result['id'], 'world': world_id, 'state': 'PENDING'}, {'$set': {
                'state': result['state'], 'message': text(result.get('message', ''), 500), 'completedAt': now()}})
        command = self.db.land_commands.find_one({'world': world_id, 'state': 'PENDING'}, sort=[('createdAt', 1), ('_id', 1)])
        return {'worldId': world_id, 'hash': (catalogue or world)['hash'], 'command': self._command(command) if command else None}

    def _merge_rows(self, world, discovery):
        grouped = {}
        for mc, dim, z, spans in discovery:
            ident = f'{world}:{mc}:{dim}:{z}'
            row = grouped.setdefault(ident, {'_id': ident, 'world': world, 'minecraft': mc, 'dimension': dim, 'z': z, 'spans': []})
            row['spans'] = merge(row['spans'] + spans)
        if not grouped: return
        for _ in range(5):
            current = {row['_id']: row for row in self.db.land_discovery.find({'_id': {'$in': list(grouped)}})}
            operations = []
            for ident, row in grouped.items():
                old = current.get(ident)
                revision = old.get('revision', 0) if old else 0
                combined = merge((old or {}).get('spans', []) + row['spans'])
                if old and combined == old['spans']: continue
                document = {**row, 'spans': combined, 'revision': revision + 1}
                operations.append(ReplaceOne({'_id': ident, 'revision': revision}, document) if old else UpdateOne({'_id': ident}, {'$setOnInsert': document}, upsert=True))
            if not operations: return
            try: self.db.land_discovery.bulk_write(operations, ordered=False)
            except BulkWriteError as error:
                if error.details.get('writeConcernErrors') or any(item.get('code') != 11000 for item in error.details.get('writeErrors', [])): raise
            # Re-read once to verify every row; concurrent extensions are merged, never overwritten.
        raise LandError('Découvertes en cours de synchronisation. Réessayez.', 503)

    def view(self, key, mc, admin, bounds, dim):
        min_x, min_z, max_x, max_z = bounds
        world = self.db.land_worlds.find_one({'_id': key})
        base = {'center': CENTER, 'radius': RADIUS, 'bounds': list(bounds), 'dimension': dim, 'admin': admin,
                'syncedAt': (world or {}).get('syncedAt'), 'hash': (world or {}).get('hash', ''), 'known': [], 'plots': [], 'directory': []}
        if not world: return base
        if admin:
            base['known'] = [{'z': z, 'spans': [[min_x, max_x]]} for z in range(min_z, max_z + 1)]
        else:
            mc = identity(mc)
            rows = self.db.land_discovery.find({'world': world['worldId'], 'minecraft': mc, 'dimension': dim, 'z': {'$gte': min_z, '$lte': max_z}})
            for row in rows:
                spans = [[max(min_x, a), min(max_x, b)] for a, b in row['spans'] if b >= min_x and a <= max_x]
                if spans: base['known'].append({'z': row['z'], 'spans': spans})
        known = {row['z']: row['spans'] for row in base['known']}
        for plot in world['plots']:
            if plot['dimension'] != dim: continue
            visible = [chunk for chunk in plot['chunks'] if min_x <= chunk['x'] <= max_x and min_z <= chunk['z'] <= max_z
                       and any(a <= chunk['x'] <= b for a, b in known.get(chunk['z'], []))]
            if visible: base['plots'].append({**plot, 'chunks': visible})
            if admin: base['directory'].append({k: plot[k] for k in ['id', 'name', 'owner', 'ownerType', 'city', 'color', 'description', 'dimension']})
        if admin:
            base['history'] = [self._command(row) for row in self.db.land_commands.find({'world': world['worldId']}).sort([('createdAt', -1), ('_id', -1)]).limit(20)]
        return base

    def enqueue(self, key, body, actor):
        world = self.db.land_worlds.find_one({'_id': key})
        if not world or not world['hash']: raise LandError('Le serveur Minecraft doit d’abord synchroniser son cadastre.', 409)
        ident = identity(body.get('id'))
        edit = change(body.get('change'))
        reason = text(body.get('reason'), 500, False)
        base_hash = body.get('baseHash')
        old = self.db.land_commands.find_one({'_id': ident})
        if old:
            if old['world'] != world['worldId'] or old['actor'] != actor or old['change'] != edit or old['baseHash'] != base_hash or old['reason'] != reason:
                raise LandError('Cet identifiant appartient à une autre modification.', 409)
            return self._command(old)
        if base_hash != world['hash']: raise LandError('Le cadastre a changé. Actualisez avant de confirmer.', 409)
        row = {'_id': ident, 'world': world['worldId'], 'baseHash': base_hash, 'change': edit, 'actor': actor,
               'reason': reason, 'state': 'PENDING', 'createdAt': now()}
        try: self.db.land_commands.insert_one(row)
        except DuplicateKeyError: return self.enqueue(key, body, actor)
        return self._command(row)

    @staticmethod
    def _command(row):
        return {('id' if k == '_id' else k): v for k, v in row.items() if k != 'world'}
