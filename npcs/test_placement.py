import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.test import RequestFactory, SimpleTestCase, override_settings
from .placement import Placements, PlacementError, placement_fields
from .spawn_admin import manage_spawn


class PlacementValidationTests(unittest.TestCase):
    def setUp(self):
        self.current = {'active': True, 'spawn_rule': 'STATIC'}
        self.npc = {'type': 'QUEST'}
        self.move = {'action': 'move', 'world': 'minecraft:overworld', 'x': -716.5, 'y': 79, 'z': -1300.5, 'yaw': 370, 'pitch': 0}

    def test_only_placement_fields_are_changed(self):
        value = placement_fields(self.current, self.npc, {**self.move, 'npc_id': 'wrong', 'skin': 'wrong', 'active': False})
        self.assertEqual(set(value), {'world', 'x', 'y', 'z', 'yaw', 'pitch'})
        self.assertEqual(value['yaw'], 10)
        self.assertEqual(value['x'], -716.5)

    def test_deletion_does_not_delete_profile(self):
        self.assertEqual(placement_fields(self.current, self.npc, {'action': 'deactivate'}), {'active': False})

    def test_rejects_invalid_positions_and_actions(self):
        for changes in [{'x': float('nan')}, {'x': True}, {'pitch': 91}, {'world': 'bad world'}, {'action': 'create'}, {'x': 30_000_001}]:
            with self.subTest(changes=changes), self.assertRaises(PlacementError):
                placement_fields(self.current, self.npc, {**self.move, **changes})

    def test_move_does_not_resurrect_inactive_or_road_npcs(self):
        for current,npc in [({**self.current,'active':False},self.npc), ({**self.current,'spawn_rule':'ROAD'},self.npc), (self.current,{'type':'SHOPKEEPER'})]:
            with self.assertRaises(PlacementError):placement_fields(current,npc,self.move)


@override_settings(API_KEY_RENBLOOD='placement-test-secret')
class PlacementHttpTests(SimpleTestCase):
    def setUp(self):self.factory=RequestFactory()
    def test_rejects_invalid_key_before_any_data_access(self):
        request=self.factory.post('/npcs/spawns/s/manage/', '{}',content_type='application/json',HTTP_X_API_KEY='wrong')
        with patch('npcs.spawn_admin.change_writer') as writer:
            self.assertEqual(manage_spawn(request,'s').status_code,401);writer.assert_not_called()
    def test_invalid_json_is_a_client_error(self):
        request=self.factory.post('/npcs/spawns/s/manage/', '{',content_type='application/json',HTTP_X_API_KEY='placement-test-secret')
        self.assertEqual(manage_spawn(request,'s').status_code,400)
    def test_not_found_is_not_reported_as_success(self):
        request=self.factory.post('/npcs/spawns/s/manage/',json.dumps({'action':'deactivate'}),content_type='application/json',HTTP_X_API_KEY='placement-test-secret')
        with patch('npcs.spawn_admin.change_writer'),patch('npcs.spawn_admin.Placements') as service:
            service.return_value.edit.side_effect=PlacementError('Spawn introuvable',404)
            response=manage_spawn(request,'s')
        self.assertEqual(response.status_code,404)


@unittest.skipUnless(os.environ.get('ECONOMY_TEST_URI'),'Disposable Mongo transaction database required')
class PlacementMongoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        cls.client=MongoClient(os.environ['ECONOMY_TEST_URI'],serverSelectionTimeoutMS=5000)
        cls.name='rb_placement_test_'+uuid.uuid4().hex[:16]
        cls.db=cls.client[cls.name]
    @classmethod
    def tearDownClass(cls):
        assert cls.name.startswith('rb_placement_test_') and len(cls.name)==34
        cls.client.drop_database(cls.name);cls.client.close()
    def setUp(self):
        for name in self.db.list_collection_names():self.db[name].delete_many({})
        self.db.npcs.insert_one({'npc_id':'n','type':'QUEST','skin':'keep','dialogue':['keep']})
        self.db.npc_spawns.insert_one({'spawn_id':'s','npc_id':'n','world':'minecraft:overworld','x':1.,'y':70.,'z':1.,'yaw':0.,'pitch':0.,'active':True,'spawn_rule':'STATIC','meta':{'keep':True}})
        self.db.players.insert_one({'id':'player','money':12345})
        self.service=Placements(self.db)
        self.move={'action':'move','world':'minecraft:the_nether','x':12.5,'y':80.,'z':-20.5,'yaw':90.,'pitch':0.}
    def test_move_keeps_identity_and_retries_are_idempotent(self):
        self.service.edit('s',self.move,'staff');self.service.edit('s',self.move,'staff')
        result=self.db.npc_spawns.find_one({'spawn_id':'s'})
        self.assertEqual(result['npc_id'],'n');self.assertEqual(result['meta'],{'keep':True,'placement_revision':1})
        self.assertEqual(self.db.npc_changes.count_documents({}),1)
        self.assertEqual(self.db.players.find_one({})['money'],12345)
    def test_deactivate_preserves_profile_and_cannot_be_reactivated_by_move(self):
        self.service.edit('s',{'action':'deactivate'},'staff');self.service.edit('s',{'action':'deactivate'},'staff')
        self.assertFalse(self.db.npc_spawns.find_one({})['active']);self.assertEqual(self.db.npcs.find_one({})['skin'],'keep')
        self.assertEqual(self.db.npc_changes.count_documents({}),1)
        with self.assertRaises(PlacementError):self.service.edit('s',self.move,'staff')
    def test_concurrent_identical_moves_create_one_notification(self):
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:self.service.edit('s',self.move,'staff'),range(2)))
        self.assertEqual(self.db.npc_changes.count_documents({}),1)
        self.assertEqual(self.db.npc_spawns.count_documents({}),1)
