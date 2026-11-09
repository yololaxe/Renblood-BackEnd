from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory
from . import views

class BankEndpointTests(SimpleTestCase):
    def setUp(self): self.factory=RequestFactory()
    def test_anonymous_cannot_read_accounts(self):
        self.assertEqual(views.accounts(self.factory.get('/')).status_code,401)
    def test_invalid_json_rejected_before_mutation(self):
        request=self.factory.post('/',data='[]',content_type='application/json')
        self.assertEqual(views.operations(request).status_code,400)
    @patch('economy.views.Player.objects.get')
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_website_cannot_forge_delivery_or_credit(self,token,player):
        player.return_value=SimpleNamespace(id='owner',rank='Citoyen')
        request=self.factory.post('/',data={'type':'CREDIT','amount':'100','idempotency_key':'fake'},content_type='application/json',HTTP_AUTHORIZATION='Bearer firebase')
        with patch('economy.views.get_bank') as bank:
            self.assertEqual(views.operations(request).status_code,403)
            bank.return_value.prepare.assert_not_called()
    @patch('economy.views.Player.objects.get')
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_receipt_lookup_is_owner_scoped(self,token,player):
        player.return_value=SimpleNamespace(id='owner',rank='Citoyen')
        bank=Mock();bank.operations.find_one.return_value=None
        with patch('economy.views.get_bank',return_value=bank):
            request=self.factory.get('/',HTTP_AUTHORIZATION='Bearer firebase')
            self.assertEqual(views.operation(request,'other-receipt').status_code,404)
            self.assertEqual(bank.operations.find_one.call_args.args[0],{'_id':'other-receipt','$or':[{'owner_id':'owner'},{'participant_owner_ids':'owner'}]})
    @patch('economy.views.Player.objects.get')
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_non_admin_cannot_correct_someone_else(self,token,player):
        player.return_value=SimpleNamespace(id='owner',rank='Citoyen')
        request=self.factory.post('/',data={'type':'CREDIT','amount':'100','reason':'fake'},content_type='application/json',HTTP_AUTHORIZATION='Bearer firebase')
        with patch('economy.views.get_bank') as bank:
            self.assertEqual(views.admin_adjustment(request,'someone-else').status_code,403)
            bank.assert_not_called()
