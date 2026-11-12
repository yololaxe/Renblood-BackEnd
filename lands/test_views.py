from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from . import views


class CadastreEndpointTests(SimpleTestCase):
    def setUp(self): self.factory = RequestFactory()
    def test_anonymous_cannot_read_exploration(self):
        with patch('lands.views.store') as store:
            response = views.map_view(self.factory.get('/'))
            self.assertEqual(response.status_code, 401);self.assertEqual(response['Cache-Control'], 'private, no-store');store.assert_not_called()
    @patch('lands.views.auth.verify_id_token', return_value={'uid': 'player'})
    @patch('lands.views.Player.objects.get', return_value=SimpleNamespace(id='player', rank='Citoyen', id_minecraft='11111111-1111-4111-8111-111111111111'))
    def test_player_cannot_enable_admin_view_or_edit(self, user, token):
        with patch('lands.views.store') as store:
            self.assertEqual(views.map_view(self.factory.get('/?mode=admin', HTTP_AUTHORIZATION='Bearer test')).status_code, 403)
            self.assertEqual(views.commands(self.factory.post('/', data='{}', content_type='application/json', HTTP_AUTHORIZATION='Bearer test')).status_code, 403);store.assert_not_called()
    @patch('lands.views.auth.verify_id_token', return_value={'uid': 'player'})
    @patch('lands.views.Player.objects.get', return_value=SimpleNamespace(id='player', rank='Citoyen', id_minecraft='11111111-1111-4111-8111-111111111111'))
    def test_viewport_is_bounded_and_player_cannot_choose_another_identity(self, user, token):
        with patch('lands.views.store') as store:
            response = views.map_view(self.factory.get('/?minX=0&minZ=0&maxX=96&maxZ=0', HTTP_AUTHORIZATION='Bearer test'))
            self.assertEqual(response.status_code, 400);store.assert_not_called()
            store.return_value.view.return_value = {'known': [], 'plots': []}
            response = views.map_view(self.factory.get('/?minX=0&minZ=0&maxX=10&maxZ=10&minecraft=other', HTTP_AUTHORIZATION='Bearer test'))
            self.assertEqual(response.status_code, 200);self.assertEqual(store.return_value.view.call_args.args[1], '11111111-1111-4111-8111-111111111111')
    @override_settings(API_KEY_RENBLOOD='test-server-key')
    def test_firebase_or_missing_token_cannot_publish_exploration(self):
        with patch('lands.views.store') as store:
            response = views.sync(self.factory.post('/', data='{}', content_type='application/json', HTTP_AUTHORIZATION='Bearer firebase'))
            self.assertEqual(response.status_code, 401);store.assert_not_called()
    @override_settings(API_KEY_RENBLOOD='test-server-key')
    def test_server_sync_accepts_only_server_proof_and_bounded_object(self):
        with patch('lands.views.store') as store:
            store.return_value.sync.return_value = {'command': None}
            response = views.sync(self.factory.post('/', data='{}', content_type='application/json', HTTP_X_API_KEY='test-server-key'))
            self.assertEqual(response.status_code, 200)
            response = views.sync(self.factory.post('/', data='[]', content_type='application/json', HTTP_X_API_KEY='test-server-key'))
            self.assertEqual(response.status_code, 400)
