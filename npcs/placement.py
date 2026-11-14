"""Atomic placement edits for existing decorative/quest NPC incarnations."""
import math
import re
from datetime import datetime, timezone
from pymongo import ReturnDocument
from .native_changes import ChangeLog


class PlacementError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def placement_fields(current, npc, body):
    if not isinstance(body, dict) or body.get('action') not in {'move', 'deactivate'}:
        raise PlacementError('Action attendue : move ou deactivate.')
    if npc.get('type') not in {'DECO', 'QUEST'} or current.get('spawn_rule', 'STATIC') not in {'STATIC', 'ADMIN'}:
        raise PlacementError('Cette commande concerne les PNJ décor et quête fixes.', 409)
    if body['action'] == 'deactivate':
        return {'active': False}
    if not current.get('active', True):
        raise PlacementError('Ce spawn est désactivé. Il ne peut pas être déplacé.', 409)
    world = body.get('world')
    if not isinstance(world, str) or len(world) > 255 or not re.fullmatch(r'[a-z0-9_.-]+:[a-z0-9_./-]+', world):
        raise PlacementError('Dimension Minecraft invalide.')
    values = {'world': world}
    for field in ('x', 'y', 'z', 'yaw', 'pitch'):
        value = body.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise PlacementError('Position et orientation complètes et finies requises.')
        if field in {'x', 'y', 'z'} and abs(value) > 30_000_000:
            raise PlacementError('Position en dehors des limites Minecraft.')
        values[field] = float(value)
    if not -90 <= values['pitch'] <= 90:
        raise PlacementError('Inclinaison invalide.')
    values['yaw'] = (values['yaw'] + 180) % 360 - 180
    return values


class Placements:
    def __init__(self, db):
        self.db = db
        self.changes = ChangeLog(db)

    def edit(self, spawn_id, body, actor):
        self.changes.initialize()

        def write(session):
            spawn = self.db.npc_spawns.find_one({'spawn_id': spawn_id}, session=session)
            if spawn is None:
                raise PlacementError('Spawn PNJ introuvable. Utilise /ns npc info nearest pour retrouver son identifiant.', 404)
            npc = self.db.npcs.find_one({'npc_id': spawn.get('npc_id')}, session=session)
            if npc is None:
                raise PlacementError('La fiche PNJ associée est introuvable.', 409)
            fields = placement_fields(spawn, npc, body)
            if all(spawn.get(key) == value for key, value in fields.items()):
                return spawn
            meta = dict(spawn.get('meta') or {})
            revision = int(meta.get('placement_revision', 0)) + 1
            meta['placement_revision'] = revision
            fields['meta'] = meta
            # Placement, revision and notification commit together. A timed-out
            # identical retry makes no second change and cannot create a copy.
            self.db.npc_spawns.update_one({'_id': spawn['_id']}, {'$set': fields}, session=session)
            counter = self.db.npc_change_counter.find_one_and_update({'_id': 'revision'}, {'$inc': {'value': 1}}, return_document=ReturnDocument.AFTER, session=session)
            self.db.npc_changes.insert_one({'revision': counter['value'], 'entity_type': 'SPAWN', 'entity_id': spawn_id,
                'action': 'UPSERT', 'payload': {'placement_action': body['action'], 'placement_revision': revision, 'actor': actor},
                'created_at': datetime.now(timezone.utc)}, session=session)
            return {**spawn, **fields}

        with self.db.client.start_session() as session:
            return session.with_transaction(write)
