import json
from types import SimpleNamespace
from unittest.mock import Mock,patch
from django.test import SimpleTestCase,RequestFactory
from economy import views

class DeskEndpointTests(SimpleTestCase):
    def setUp(self):self.factory=RequestFactory()
    def request(self,path='/',post=False):
        return self.factory.post(path,data={'active':False,'revision':0,'reason':'Contrôle'},content_type='application/json',HTTP_AUTHORIZATION='Bearer test') if post else self.factory.get(path,HTTP_AUTHORIZATION='Bearer test')
    @patch('economy.views.Player.objects.get',return_value=SimpleNamespace(id='owner',rank='Citoyen'))
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_admin_routes_refuse_before_database_access(self,*_):
        with patch('economy.views.get_bank') as bank:
            self.assertEqual(views.admin_desk(self.request(),'overview').status_code,403)
            self.assertEqual(views.admin_business(self.request(post=True),'inn:test','availability').status_code,403)
            bank.assert_not_called()
    @patch('economy.views.Player.objects.get',return_value=SimpleNamespace(id='owner',rank='Citoyen'))
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_wallet_can_explain_bank_not_prepared(self,*_):
        bank=Mock();bank.accounts.find_one.return_value=None
        bank.accounts.find.return_value.sort.return_value.limit.return_value=[]
        bank.db.economy_businesses.find.return_value=[]
        with patch('economy.views.get_bank',return_value=bank):result=views.wallet(self.request())
        self.assertEqual(result.status_code,200);self.assertEqual(json.loads(result.content)['bank_state'],'SETUP_REQUIRED')
        bank.db.economy_businesses.find.assert_not_called()
    @patch('economy.views.Player.objects.get',return_value=SimpleNamespace(id='owner',rank='Citoyen'))
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_unregistered_business_has_a_readable_state(self,*_):
        bank=Mock();bank.db.economy_businesses.find_one.return_value=None
        with patch('economy.views.get_bank',return_value=bank):response=views.business_status(self.request('/?business_id=inn:test'))
        self.assertEqual(response.status_code,200);self.assertEqual(json.loads(response.content)['state'],'NOT_REGISTERED')
    @patch('economy.views.Player.objects.get',return_value=SimpleNamespace(id='owner',rank='Citoyen'))
    @patch('economy.views.auth.verify_id_token',return_value={'uid':'owner'})
    def test_customer_does_not_receive_another_players_exact_budget(self,*_):
        bank=Mock();bank.db.economy_businesses.find_one.return_value={'kind':'INN','owner_id':'another','label':'Auberge','active':True,'rule_version':'v1'}
        bank.accounts.find_one.return_value={'available':99}
        with patch('economy.views.get_bank',return_value=bank):response=views.business_status(self.request('/?business_id=inn:test'))
        data=json.loads(response.content);self.assertEqual(data['state'],'AVAILABLE');self.assertIsNone(data['budget'])
