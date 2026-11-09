import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from . import views


@override_settings(API_KEY_RENBLOOD='fixture-key')
class BudgetSuggestionsTests(SimpleTestCase):
    def request(self, prefix, **params):
        return RequestFactory().get('/api/economy/v1/commerce/funding-targets', {'prefix': prefix, **params},
                                    HTTP_X_API_KEY='fixture-key', HTTP_X_MINECRAFT_UUID='fixture')

    def test_non_admin_does_not_read_establishments(self):
        with patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id='p', rank='Citoyen')), \
                patch('economy.views.get_bank') as bank:
            result = views.funding_targets(self.request('inn:'))
        self.assertEqual(result.status_code, 403)
        bank.assert_not_called()

    def test_admin_gets_only_ids_and_labels_for_matching_active_businesses(self):
        bank = Mock()
        rows = bank.db.economy_businesses.find.return_value
        rows.sort.return_value.limit.return_value.max_time_ms.return_value = [
            {'business_id': 'inn:fixture', 'label': 'Auberge de recette'},
        ]
        with patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id='p', rank='Admin')), \
                patch('economy.views.get_bank', return_value=bank):
            result = views.funding_targets(self.request('inn:'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads(result.content)['targets'][0]['business_id'], 'inn:fixture')
        bank.db.economy_businesses.find.assert_called_once_with(
            {'active': True, '_id': {'$regex': '^inn:'}}, {'business_id': 1, 'label': 1, '_id': 0})

    def test_player_can_complete_only_their_active_businesses(self):
        bank = Mock()
        rows = bank.db.economy_businesses.find.return_value
        rows.sort.return_value.limit.return_value.max_time_ms.return_value = []
        with patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id='p', rank='Citoyen')), \
                patch('economy.views.get_bank', return_value=bank):
            result = views.funding_targets(self.request('market:', owned='1', owner_id='other'))
        self.assertEqual(result.status_code, 200)
        bank.db.economy_businesses.find.assert_called_once_with(
            {'active': True, 'owner_id': 'p', '_id': {'$regex': '^market:'}},
            {'business_id': 1, 'label': 1, '_id': 0})

    def test_stock_completion_checks_ownership_before_querying_offers(self):
        bank = Mock()
        bank.db.economy_businesses.find_one.return_value = None
        with patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id='p', rank='Admin')), \
                patch('economy.views.get_bank', return_value=bank):
            result = views.funding_targets(self.request('', owned='1', stock_business='market:other'))
        self.assertEqual(json.loads(result.content)['targets'], [])
        bank.db.economy_businesses.find_one.assert_called_once_with(
            {'active': True, 'owner_id': 'p', '_id': 'market:other'}, {'_id': 1})
        bank.db.economy_offers.find.assert_not_called()
