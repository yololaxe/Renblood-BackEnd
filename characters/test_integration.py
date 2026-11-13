import os,unittest,uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pymongo import MongoClient
from .service import Directory,DirectoryError

@unittest.skipUnless(os.getenv('RENBLOOD_IDENTITY_TEST_MONGO_URI'),'Requires an explicit URI for isolated integration tests')
class DirectoryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  global db,client,name
  client=MongoClient(os.environ['RENBLOOD_IDENTITY_TEST_MONGO_URI'],serverSelectionTimeoutMS=5000,socketTimeoutMS=15000,maxPoolSize=5,appname='Renblood-isolated-identity-tests')
  name='renblood_identity_test_'+uuid.uuid4().hex[:12];db=client[name]
 @classmethod
 def tearDownClass(cls):
  assert name.startswith('renblood_identity_test_') and len(name)==35
  client.drop_database(name);client.close()
 def setUp(self):
  for collection in db.list_collection_names():db[collection].delete_many({})
  self.s=Directory(db);self.s.wiki.initial();self.version,self.package=self.s.package();self.person=self.package['registry']['people'][0]['id'];self.other=self.package['registry']['people'][1]['id']
  db.npcs.insert_many([{'npc_id':'a','name':'First','enabled':True},{'npc_id':'b','name':'Second','enabled':True}]);db.players.insert_many([{'id':'p1','name':'One','money':123456,'economy_v1':True,'inventory':['keep']},{'id':'p2','name':'Two','money':17}])
 def body(self,npc='a',**kw):return {'npc_id':npc,'character_id':self.person,'control_mode':'NPC','player_id':None,'archived':False,'base_version':self.version,'expected_revision':0,'reason':'Association validée pour la recette','operation_id':uuid.uuid4().hex,**kw}
 def test_preserves_accounts_ids_and_historical_profiles(self):
  old=list(db.players.find({}));self.s.bind(self.body(control_mode='PLAYER',player_id='p1'),'staff');self.s.bind(self.body('b'),'staff')
  self.assertEqual(old,list(db.players.find({})));self.assertEqual(db.npcs.count_documents({}),2)
  links=self.s.public_links(['a','b']);self.assertTrue(links['b']['automatic_spawn_blocked']);self.assertNotIn('player_id',links['a']);self.assertNotIn('updated_by',links['a'])
 def test_idempotent_retry_and_revision_conflict(self):
  body=self.body();first=self.s.bind(body,'staff');self.assertEqual(self.s.bind(body,'staff'),first);self.assertEqual(db.character_link_audit.count_documents({}),1)
  with self.assertRaises(DirectoryError):self.s.bind({**body,'reason':'A different request'},'staff')
  with self.assertRaises(DirectoryError):self.s.bind(self.body(),'staff')
 def test_one_profile_per_account_and_one_controller_per_character(self):
  self.s.bind(self.body(control_mode='PLAYER',player_id='p1'),'staff')
  with self.assertRaises(DirectoryError):self.s.bind(self.body('b',character_id=self.other,control_mode='PLAYER',player_id='p1'),'staff')
  with self.assertRaises(DirectoryError):self.s.bind(self.body('b',control_mode='PLAYER',player_id='p2'),'staff')
 def test_unlink_releases_controller_and_emits_for_legacy_siblings(self):
  self.s.bind(self.body(control_mode='PLAYER',player_id='p1'),'staff');self.s.bind(self.body('b'),'staff')
  body=self.body(expected_revision=1);self.s.bind(body,'staff')
  self.assertFalse(self.s.public_links(['b'])['b']['automatic_spawn_blocked'])
  self.assertEqual(db.character_identity_outbox.count_documents({'_id':body['operation_id']+':b'}),1)
  self.s.bind(self.body('b',expected_revision=1,control_mode='PLAYER',player_id='p1'),'staff')
 def test_archiving_keeps_player_ownership_until_explicit_unlink(self):
  self.s.bind(self.body(control_mode='PLAYER',player_id='p1',archived=True),'staff')
  self.s.bind(self.body('b'),'staff')
  self.assertTrue(self.s.public_links(['b'])['b']['automatic_spawn_blocked'])
  with self.assertRaises(DirectoryError):self.s.bind(self.body('b',expected_revision=1,control_mode='PLAYER',player_id='p2'),'staff')
 def test_transaction_rolls_back_if_audit_notification_fails(self):
  with patch.object(self.s,'_emit',side_effect=RuntimeError('Simulated interruption')):
   with self.assertRaises(RuntimeError):self.s.bind(self.body(),'staff')
  self.assertEqual(db.character_links.count_documents({}),0);self.assertEqual(db.character_link_audit.count_documents({}),0)
 def test_concurrent_player_assignment_has_one_winner(self):
  def attempt(npc):
   try:return self.s.bind(self.body(npc,character_id=self.person if npc=='a' else self.other,control_mode='PLAYER',player_id='p1'),'staff')
   except DirectoryError:return None
  self.s.initialize()
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,['a','b']))
  self.assertEqual(sum(r is not None for r in results),1);self.assertEqual(db.character_links.count_documents({'player_id':'p1'}),1)
 def test_profile_creation_idempotent_and_no_automatic_spawn(self):
  b={'character_id':self.person,'base_version':self.version,'reason':'Création de test','operation_id':uuid.uuid4().hex}
  a=self.s.create_profile(b,'staff');self.assertEqual(self.s.create_profile(b,'staff'),a);self.assertEqual(db.npc_spawns.count_documents({}),0)
  with self.assertRaises(DirectoryError):self.s.create_profile({**b,'operation_id':uuid.uuid4().hex},'staff')
 def test_concurrent_profile_creation_has_one_winner(self):
  self.s.initialize()
  def attempt(_):
   try:return self.s.create_profile({'character_id':self.person,'base_version':self.version,'reason':'Création concurrente','operation_id':uuid.uuid4().hex},'staff')
   except DirectoryError:return None
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[0,1]))
  self.assertEqual(sum(r is not None for r in results),1)
 def test_lore_preview_then_publication_preserves_immutable_previous_version(self):
  draft=self.s.prepare_lore({'base_version':self.version,'fields':{'name':'Enfant de recette'},'related_to':self.person,'relationship':'child','public_confirmed':True,'reason':'Test du lien familial'},'staff')
  self.assertEqual(len(self.s.package()[1]['registry']['people']),len(self.package['registry']['people']))
  body={'draft_id':draft['draft_id'],'revision':draft['revision'],'reason':'Publication du test familial'};result=self.s.publish_lore(body,'staff')
  self.assertEqual(self.s.publish_lore(body,'staff')['version'],result['version']);self.assertEqual(self.s.wiki.version_package(self.version),self.package)
  p=self.s.package()[1];self.assertTrue(any(r['type']=='parent' and r['a']==self.person and r['b']==draft['person_id'] for r in p['registry']['relations']))
 def test_publication_retry_after_review_saved(self):
  draft=self.s.prepare_lore({'person_id':self.person,'base_version':self.version,'fields':{'biography':'Publique, recette'},'public_confirmed':True,'reason':'Recette publication'},'staff')
  body={'draft_id':draft['draft_id'],'revision':draft['revision'],'reason':'Test publication'}
  with patch.object(self.s.wiki,'publish',side_effect=RuntimeError('Worker stopped')):
   with self.assertRaises(RuntimeError):self.s.publish_lore(body,'staff')
  self.assertIn('version',self.s.publish_lore(body,'staff'))
 def test_private_fields_and_stale_registry_rejected(self):
  body={'person_id':self.person,'base_version':self.version,'fields':{'secret':'never public'},'public_confirmed':True,'reason':'Validation des champs'}
  with self.assertRaises(DirectoryError):self.s.prepare_lore(body,'staff')
  with self.assertRaises(DirectoryError):self.s.bind(self.body(base_version='stale'),'staff')
