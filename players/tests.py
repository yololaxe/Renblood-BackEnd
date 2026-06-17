from types import SimpleNamespace
from unittest.mock import patch

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

        with patch("players.views.Player.objects.get", return_value=self.player):
            response = withdraw_player(request, self.player.id_minecraft)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.player.money, 36)
        self.assertEqual(self.player.saved_update_fields, ["money"])

    def test_deposit_accepts_minecraft_api_key_without_firebase_token(self):
        request = self.factory.post(
            f"/players/deposit/{self.player.id_minecraft}/",
            {"amount": 25},
            content_type="application/json",
            HTTP_X_API_KEY="secret",
        )

        with patch("players.views.Player.objects.get", return_value=self.player):
            response = deposit_player(request, self.player.id_minecraft)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.player.money, 125)
        self.assertEqual(self.player.saved_update_fields, ["money"])
