from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4
from pymongo.errors import DuplicateKeyError
from pymongo import ReplaceOne
from .service import Cadastre, LandError, change, snapshot, merge


def matches(row, query):
    for key, value in query.items():
        current = row.get(key)
        if isinstance(value, dict):
            if '$in' in value and current not in value['$in']: return False
            if '$gte' in value and (current is None or current < value['$gte']): return False
            if '$lte' in value and (current is None or current > value['$lte']): return False
        elif current != value: return False
    return True


class Cursor(list):
    def sort(self, keys):
        values = self
        for key, direction in reversed(keys): values = sorted(values, key=lambda row: row.get(key, ''), reverse=direction == -1)
        return Cursor(values)
    def limit(self, maximum): return Cursor(self[:maximum])


class Collection:
    """In-memory Mongo semantics for deterministic conflict/retry tests; no network."""
    def __init__(self): self.rows = {}
    def create_index(self, *args, **kwargs): pass
    def find(self, query): return Cursor(deepcopy([row for row in self.rows.values() if matches(row, query)]))
    def find_one(self, query, sort=None):
        rows = self.find(query)
        if sort: rows = rows.sort(sort)
        return rows[0] if rows else None
    def insert_one(self, row):
        if row['_id'] in self.rows: raise DuplicateKeyError('duplicate _id')
        self.rows[row['_id']] = deepcopy(row)
    def update_one(self, query, update, upsert=False):
        row = self.find_one(query)
        if not row and not upsert: return SimpleNamespace(matched_count=0)
        if not row: row = {**query, **deepcopy(update.get('$setOnInsert', {}))}
        row.update(deepcopy(update.get('$set', {})));self.rows[row['_id']] = row
        return SimpleNamespace(matched_count=1)
    def replace_one(self, query, row):
        old = self.find_one(query)
        if old: self.rows[old['_id']] = deepcopy(row)
        return SimpleNamespace(matched_count=int(old is not None))
    def bulk_write(self, operations, ordered=False):
        for operation in operations:
            if isinstance(operation, ReplaceOne): self.replace_one(operation._filter, operation._doc)
            else: self.update_one(operation._filter, operation._doc, upsert=operation._upsert)


class CadastreTests(TestCase):
    def setUp(self):
        self.db = SimpleNamespace(land_worlds=Collection(), land_discovery=Collection(), land_commands=Collection())
        self.service = Cadastre(self.db);self.world = str(uuid4());self.mc = str(uuid4());self.other = str(uuid4())
        self.plot = {'id': 'place', 'name': 'Place', 'owner': 'Maison de recette', 'ownerType': 'FAMILY', 'city': 'Shaleton', 'dimension': 'minecraft:overworld', 'color': '#DDBB77', 'description': 'Domaine public de recette', 'chunks': [{'x': -45, 'z': -82}, {'x': -44, 'z': -82}, {'x': 30, 'z': 30}]}
        self.catalogue = {'hash': 'a' * 64, 'plots': [self.plot]}
        self.sync(snapshot=self.catalogue)
    def sync(self, **kwargs): return self.service.sync({'worldKey': 'renblood', 'worldId': self.world, **kwargs})
    def row(self, mc=None, dim='minecraft:overworld', z=-82, spans=None):
        return {'minecraft': mc or self.mc, 'dimension': dim, 'z': z, 'spans': spans or [[-45, -45]]}
    def view(self, mc=None, admin=False): return self.service.view('renblood', mc or self.mc, admin, [-50, -90, 40, 40], 'minecraft:overworld')
    def command(self): return {'id': str(uuid4()), 'baseHash': 'a' * 64, 'reason': 'Recette', 'change': {'action': 'assign', 'plotId': 'place', 'dimension': 'minecraft:overworld', 'chunks': [{'x': -43, 'z': -82}]}}

    def test_unvisited_player_has_neither_geometry_nor_owner_directory(self):
        result = self.view();self.assertEqual(result['known'], []);self.assertEqual(result['plots'], []);self.assertEqual(result['directory'], [])
    def test_partial_discovery_never_reveals_the_rest_of_the_same_plot(self):
        self.sync(discoveries=[self.row()]);result = self.view()
        self.assertEqual(result['plots'][0]['chunks'], [{'x': -45, 'z': -82}]);self.assertEqual(result['plots'][0]['owner'], 'Maison de recette')
        self.assertEqual(result['directory'], []);self.assertNotIn('history', result)
    def test_accounts_and_dimensions_are_isolated(self):
        self.sync(discoveries=[self.row(), self.row(self.other, spans=[[30, 30]]), self.row(dim='minecraft:the_nether', spans=[[0, 0]])])
        self.assertEqual(self.view()['known'], [{'z': -82, 'spans': [[-45, -45]]}])
        self.assertEqual(self.view(self.other)['known'], [{'z': -82, 'spans': [[30, 30]]}])
    def test_retries_merge_intervals_idempotently(self):
        rows = [self.row(spans=[[-48, -46], [-45, -44]])]
        self.sync(discoveries=rows);self.sync(discoveries=rows);self.sync(discoveries=[self.row(spans=[[-43, -40]])])
        self.assertEqual(self.view()['known'][0]['spans'], [[-48, -40]]);self.assertEqual(len(self.db.land_discovery.rows), 1)
    def test_viewport_crops_exploration_and_geometry(self):
        self.sync(discoveries=[self.row(spans=[[-100, 100]])])
        result = self.service.view('renblood', self.mc, False, [-45, -82, -45, -82], 'minecraft:overworld')
        self.assertEqual(result['known'][0]['spans'], [[-45, -45]]);self.assertEqual(len(result['plots'][0]['chunks']), 1)
    def test_admin_can_view_every_parcel_without_marking_it_discovered(self):
        result = self.view(admin=True);self.assertEqual(len(result['plots'][0]['chunks']), 3)
        self.assertEqual(len(result['directory']), 1);self.assertEqual(self.view()['known'], [])
    def test_different_world_cannot_replace_the_bound_cadastre(self):
        with self.assertRaises(LandError): self.service.sync({'worldKey': 'renblood', 'worldId': str(uuid4()), 'snapshot': {'hash': 'b' * 64, 'plots': []}})
        self.assertEqual(self.db.land_worlds.rows['renblood']['hash'], 'a' * 64)
    def test_edit_remains_pending_until_minecraft_acknowledges(self):
        command = self.command();self.service.enqueue('renblood', command, 'admin')
        response = self.sync();self.assertEqual(response['command']['id'], command['id'])
        self.assertEqual(self.db.land_worlds.rows['renblood']['plots'][0]['chunks'], self.plot['chunks'])
        self.sync(results=[{'id': command['id'], 'state': 'APPLIED', 'message': 'Validé'}], snapshot={'hash': 'b' * 64, 'plots': [self.plot]})
        self.assertIsNone(self.sync()['command']);self.assertEqual(self.view(admin=True)['history'][0]['state'], 'APPLIED')
    def test_lost_http_acknowledgement_does_not_duplicate_admin_operation(self):
        command = self.command();a = self.service.enqueue('renblood', command, 'admin');b = self.service.enqueue('renblood', command, 'admin')
        self.assertEqual(a, b);self.assertEqual(len(self.db.land_commands.rows), 1)
        command['reason'] = 'Autre motif'
        with self.assertRaises(LandError): self.service.enqueue('renblood', command, 'admin')
    def test_stale_website_edit_is_refused_before_queueing(self):
        command = self.command();command['baseHash'] = 'b' * 64
        with self.assertRaises(LandError): self.service.enqueue('renblood', command, 'admin')
        self.assertFalse(self.db.land_commands.rows)
    def test_invalid_late_discovery_does_not_partially_publish_earlier_rows(self):
        with self.assertRaises(LandError): self.sync(discoveries=[self.row(), self.row(z=True)])
        self.assertFalse(self.db.land_discovery.rows)
    def test_duplicate_chunks_or_boolean_coordinates_are_rejected(self):
        data = deepcopy(self.catalogue);data['plots'][0]['chunks'].append({'x': -45, 'z': -82})
        with self.assertRaises(LandError): snapshot(data)
        edit = self.command()['change'];edit['chunks'] = [{'x': True, 'z': 0}]
        with self.assertRaises(LandError): change(edit)
    def test_rectangle_limit_and_invalid_metadata_are_rejected(self):
        edit = self.command()['change'];edit['chunks'] = [{'x': x, 'z': 0} for x in range(257)]
        with self.assertRaises(LandError): change(edit)
        self.assertEqual(merge([[-8, 8], [9, 20], [-30, -20]]), [[-30, -20], [-8, 20]])
