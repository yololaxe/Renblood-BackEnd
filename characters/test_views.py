import json
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase,RequestFactory,override_settings
from . import views
from npcs.api_views import npc_payload,spawn_payload
from npcs.models import Npc

class CharacterViewTests(SimpleTestCase):
 def setUp(self):self.factory=RequestFactory()
 def test_directory_requires_real_admin_authentication(self):
  response=views.admin(self.factory.get('/api/characters/v1/admin/'))
  self.assertEqual(response.status_code,401)
 def test_invalid_json_is_rejected_before_a_write(self):
  with self.assertRaises(views.DirectoryError):views.body(self.factory.post('/',data='[]',content_type='application/json'))
 def test_public_payload_suppresses_automatic_spawns_without_exposing_account(self):
  npc=Npc(npc_id='a',name='Player character',type='QUEST',enabled=True)
  identity={'a':{'character_id':'P1','control_mode':'PLAYER','automatic_spawn_blocked':True,'archived':False,'revision':1}}
  result=npc_payload(npc,{},identity)
  self.assertFalse(result['enabled']);self.assertTrue(result['configured_enabled']);self.assertNotIn('player_id',result)
  spawn=SimpleNamespace(npc=npc,spawn_id='spawn',world='world',x=1,y=2,z=3,yaw=0,pitch=0,spawn_rule='STATIC',active=True,meta={})
  self.assertFalse(spawn_payload(spawn,{},identity)['active'])
 def test_archiving_retains_identifiers_and_configured_spawn_state(self):
  npc=Npc(npc_id='quest-id-to-keep',name='Archive',enabled=True)
  row=npc_payload(npc,{'quest-id-to-keep':[{'questId':'keep'}]},{'quest-id-to-keep':{'archived':True}})
  self.assertEqual(row['npc_id'],'quest-id-to-keep');self.assertFalse(row['enabled']);self.assertEqual(len(row['quest_links']),1);self.assertTrue(npc.enabled)
 def test_outbox_is_acknowledged_only_after_notification(self):
  fake=SimpleNamespace(outbox=SimpleNamespace(find=lambda _:SimpleNamespace(sort=lambda *a:SimpleNamespace(limit=lambda n:[{'_id':'op','npc_id':'a'}])),update_one=lambda *a:None))
  with patch('npcs.change_log.record_change',side_effect=RuntimeError('retry')),patch.object(fake.outbox,'update_one') as update:
   with self.assertRaises(RuntimeError):views.flush_identity_changes(fake)
   update.assert_not_called()

 @override_settings(API_KEY_RENBLOOD='fixture-server-key')
 def test_cannot_delete_quest_giver_or_linked_character(self):
  from npcs.api_views import npc_detail
  from unittest.mock import Mock
  npc=Mock(npc_id='quest-giver')
  for quests,bindings in [([{'questId':'keep'}],{}),([] ,{'quest-giver':{'character_id':'P1'}})]:
   request=self.factory.delete('/npcs/quest-giver/',HTTP_X_API_KEY='fixture-server-key')
   with patch('npcs.api_views.get_object_or_404',return_value=npc),patch('npcs.api_views.quest_links_for_npc',return_value=quests),patch('characters.views.public_bindings',return_value=bindings):
    self.assertEqual(npc_detail(request,'quest-giver').status_code,409)
   npc.delete.assert_not_called()
