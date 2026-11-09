import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase, override_settings

from . import views


@override_settings(API_KEY_RENBLOOD='fixture-key')
class SupportReceiptTests(SimpleTestCase):
    def setUp(self):
        self.ident = uuid4()
        self.headers = {'HTTP_X_API_KEY': 'fixture-key', 'HTTP_X_MINECRAFT_UUID': 'fixture'}

    def test_citizen_cannot_read_support_receipt(self):
        request = RequestFactory().get('/', **self.headers)
        with patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id='p', rank='Citoyen')), \
                patch('economy.views.get_bank') as get_bank:
            result = views.support_receipt(request, self.ident)
        self.assertEqual(result.status_code, 403)
        get_bank.assert_not_called()

    def test_moderator_reads_status_and_adds_note_without_mutating_receipt(self):
        request = RequestFactory().post('/', {'note': ' À revoir '}, content_type='application/json',
                                        HTTP_IDEMPOTENCY_KEY=str(uuid4()), **self.headers)
        bank = Mock()
        bank.operations.find_one.return_value = {'operation_id': str(self.ident), 'state': 'RESERVED'}
        notes = bank.db.economy_support_notes
        notes.find.return_value.sort.return_value.limit.return_value = []
        with patch('economy.views.Player.objects.get', return_value=SimpleNamespace(id='mod', rank='Moderateur')), \
                patch('economy.views.get_bank', return_value=bank):
            result = views.support_receipt(request, self.ident)
            adjustment = views.admin_operation(request, self.ident, 'compensations')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(adjustment.status_code, 403)
        self.assertEqual(json.loads(result.content)['receipt']['state'], 'RESERVED')
        self.assertEqual(notes.insert_one.call_args.args[0]['note'], 'À revoir')
        bank.operations.update_one.assert_not_called()
