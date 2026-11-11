from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from . import views


class WikiEndpointTests(SimpleTestCase):
    def setUp(self): self.factory = RequestFactory()
    def test_anonymous_cannot_open_workshop(self):
        with patch('wiki.views.store') as backend:
            self.assertEqual(views.admin(self.factory.get('/')).status_code, 401)
            backend.assert_not_called()
    @patch('utils.decorators.auth.verify_id_token', return_value={'uid': 'reader'})
    @patch('utils.decorators.Player.objects.get', return_value=SimpleNamespace(id='reader', rank='Citoyen'))
    def test_reader_cannot_publish(self, player, token):
        request = self.factory.post('/', data='{}', content_type='application/json', HTTP_AUTHORIZATION='Bearer test')
        with patch('wiki.views.store') as backend:
            self.assertEqual(views.admin(request, action='publish', ident='draft').status_code, 403)
            backend.assert_not_called()
    def test_public_endpoint_exposes_only_package_and_supports_etag(self):
        with patch('wiki.views.store') as backend:
            backend.return_value.current.return_value = ({'version': 'wiki-test', 'history': ['private']}, {'registry': {'version': 'wiki-test'}, 'books': []})
            result = views.public(self.factory.get('/'))
            self.assertNotIn(b'private', result.content)
            self.assertEqual(result['ETag'], '"wiki-test"')
            self.assertEqual(views.public(self.factory.get('/', HTTP_IF_NONE_MATCH='"wiki-test"')).status_code, 304)
