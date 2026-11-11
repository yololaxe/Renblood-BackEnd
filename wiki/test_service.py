from copy import deepcopy
from types import SimpleNamespace
import unittest
from .service import seed, validate, differences, resolve_changes, WikiError, WikiStore


class Cursor(list):
    def sort(self, key, direction):
        return Cursor(sorted(self, key=lambda item: item.get(key, ''), reverse=direction == -1))
    def limit(self, count): return Cursor(self[:count])


class Collection:
    def __init__(self): self.rows = {}
    def find_one(self, query):
        return next((deepcopy(row) for row in self.rows.values() if all(row.get(key) == value for key, value in query.items())), None)
    def find(self, query, projection=None):
        result = [deepcopy(row) for row in self.rows.values() if all(row.get(key) == value for key, value in query.items())]
        if projection:
            for row in result:
                for key, value in projection.items():
                    if value == 0: row.pop(key, None)
        return Cursor(result)
    def insert_one(self, row): self.rows[row['_id']] = deepcopy(row)
    def update_one(self, query, update, upsert=False):
        row = self.find_one(query)
        if row is None:
            if not upsert: return SimpleNamespace(modified_count=0)
            row = {**query, **deepcopy(update.get('$setOnInsert', {}))}
        row.update(deepcopy(update.get('$set', {})))
        for key, amount in update.get('$inc', {}).items(): row[key] = row.get(key, 0) + amount
        for key, value in update.get('$push', {}).items(): row[key] = (row.get(key, []) + deepcopy(value['$each']))[value['$slice']:]
        self.rows[row['_id']] = row
        return SimpleNamespace(modified_count=1)


class WikiTests(unittest.TestCase):
    def candidate(self):
        package = deepcopy(seed()); package['registry']['people'][0]['biography'] = 'Biographie publique validée.'
        return package
    def test_seed_is_valid_and_private_columns_are_rejected(self):
        self.assertEqual(validate(seed()), seed())
        candidate = self.candidate(); candidate['registry']['people'][0]['secret'] = 'staff'
        with self.assertRaises(WikiError): validate(candidate)
    def test_missing_fields_and_dangling_references_are_rejected(self):
        candidate = self.candidate(); del candidate['registry']['people'][0]['aliases']
        with self.assertRaises(WikiError): validate(candidate)
        candidate = self.candidate(); candidate['registry']['relations'][0]['b'] = 'absent'
        with self.assertRaises(WikiError): validate(candidate)
    def test_cycles_and_duplicate_identities_are_rejected(self):
        candidate = self.candidate(); edge = next(edge for edge in candidate['registry']['relations'] if edge['type'] == 'parent')
        candidate['registry']['relations'].append({'id': 'cycle', 'a': edge['b'], 'b': edge['a'], 'type': 'parent'})
        with self.assertRaises(WikiError): validate(candidate)
        candidate = self.candidate(); candidate['registry']['people'].append(candidate['registry']['people'][0])
        with self.assertRaises(WikiError): validate(candidate)
    def test_each_change_requires_explicit_decision(self):
        changes = differences(seed(), self.candidate()); self.assertEqual(len(changes), 1)
        with self.assertRaises(WikiError): resolve_changes(seed(), self.candidate(), {})
        kept = resolve_changes(seed(), self.candidate(), {changes[0]['key']: 'keep'})
        self.assertEqual(kept, seed())
        accepted = resolve_changes(seed(), self.candidate(), {changes[0]['key']: 'accept'})
        self.assertEqual(accepted, self.candidate())
    def store(self):
        return WikiStore(SimpleNamespace(wiki_state=Collection(), wiki_versions=Collection(), wiki_drafts=Collection()))
    def test_shared_review_publish_restore_and_immutable_versions(self):
        backend = self.store(); backend.initial(); initial, old = backend.current()
        draft = backend.create_draft(self.candidate(), initial['version'], 'admin-a', 'Recette')
        self.assertEqual(backend.preview(draft['_id']), old)
        with self.assertRaises(WikiError): backend.publish(draft['_id'], 0, 'admin-a', 'Recette')
        saved = backend.save(draft['_id'], 0, {draft['changes'][0]['key']: 'accept'})
        self.assertEqual(saved['revision'], 1)
        with self.assertRaises(WikiError): backend.save(draft['_id'], 0, {})
        version = backend.publish(draft['_id'], 1, 'admin-a', 'Recette')
        state, published = backend.current()
        self.assertEqual(state['version'], version); self.assertNotEqual(published, old)
        self.assertEqual(backend.versions.find_one({'_id': initial['version']})['package'], old)
        with self.assertRaises(WikiError): backend.restore(initial['version'], 0, 'admin-b', 'Restauration')
        backend.restore(initial['version'], state['revision'], 'admin-b', 'Restauration')
        self.assertEqual(backend.current()[1], old)
        self.assertEqual(len(backend.current()[0]['history']), 2)
    def test_stale_draft_cannot_overwrite_new_publication(self):
        backend = self.store(); backend.initial(); state, _ = backend.current()
        a = backend.create_draft(self.candidate(), state['version'], 'a', 'A')
        b = backend.create_draft(self.candidate(), state['version'], 'b', 'B')
        for draft in [a, b]: backend.save(draft['_id'], 0, {draft['changes'][0]['key']: 'accept'})
        backend.publish(a['_id'], 1, 'a', 'A')
        with self.assertRaises(WikiError): backend.publish(b['_id'], 1, 'b', 'B')
    def test_interrupted_publication_can_recover_without_losing_approved_decisions(self):
        backend = self.store(); state = backend.initial()
        draft = backend.create_draft(self.candidate(), state['version'], 'admin', 'Recette')
        key = draft['changes'][0]['key']
        backend.save(draft['_id'], 0, {key: 'accept'})
        backend.drafts.update_one({'_id': draft['_id']}, {'$set': {'status': 'PUBLISHING', 'publicationStartedAt': '2000-01-01T00:00:00+00:00', 'publishedVersion': 'never-published'}})
        recovered = backend.draft(draft['_id'])
        self.assertEqual(recovered['status'], 'DRAFT')
        self.assertEqual(recovered['revision'], 2)
        self.assertEqual(recovered['decisions'], {key: 'accept'})
