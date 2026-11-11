from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from .views import deposit_player, withdraw_player


class FakePlayer(SimpleNamespace):
    def save(self, update_fields=None):
        self.saved_update_fields = update_fields


@override_settings(API_KEY_RENBLOOD="secret")
class MinecraftMoneyEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.player = FakePlayer(
            id="legacy-player",
            id_minecraft="2bf2e638-e140-4370-9dfb-db733fc9cf75",
            money=100,
        )

    def test_withdraw_accepts_minecraft_api_key_without_firebase_token(self):
        request = self.factory.post(
            f"/players/withdraw/{self.player.id_minecraft}/",
            {"coin_type": 1, "amount": 1},
            content_type="application/json",
            HTTP_X_API_KEY="secret",
        )

        bank = Mock()
        bank.db.players.find_one_and_update.return_value = {"money": 36}
        with patch("players.views.Player.objects.get", return_value=self.player), patch("economy.store.get_bank", return_value=bank):
            response = withdraw_player(request, self.player.id_minecraft)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.player.money, 36)
        query, update = bank.db.players.find_one_and_update.call_args.args
        self.assertEqual(query, {"id": "legacy-player", "economy_v1": {"$ne": True}, "money": {"$gte": 64}})
        self.assertEqual(update, {"$inc": {"money": -64}})

    def test_deposit_accepts_minecraft_api_key_without_firebase_token(self):
        request = self.factory.post(
            f"/players/deposit/{self.player.id_minecraft}/",
            {"amount": 25},
            content_type="application/json",
            HTTP_X_API_KEY="secret",
        )

        bank = Mock()
        bank.db.players.find_one_and_update.return_value = {"money": 125}
        with patch("players.views.Player.objects.get", return_value=self.player), patch("economy.store.get_bank", return_value=bank):
            response = deposit_player(request, self.player.id_minecraft)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.player.money, 125)
        query, update = bank.db.players.find_one_and_update.call_args.args
        self.assertEqual(query, {"id": "legacy-player", "economy_v1": {"$ne": True}})
        self.assertEqual(update, {"$inc": {"money": 25}})
