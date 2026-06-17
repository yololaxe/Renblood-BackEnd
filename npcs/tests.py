import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from npcs.views import meet_npc
from utils.decorators import minecraft_admin_or_firebase_admin_required


@override_settings(API_KEY_RENBLOOD="server-secret")
class MinecraftSpawnAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @staticmethod
    @minecraft_admin_or_firebase_admin_required
    def protected_view(request):
        return request.admin_user

    @patch("utils.decorators.Player.objects.get")
    def test_accepts_admin_minecraft_uuid_with_server_api_key(self, get_player):
        admin = SimpleNamespace(rank="Admin")
        get_player.return_value = admin
        request = self.factory.post(
            "/npcs/spawns/create/",
            HTTP_X_API_KEY="server-secret",
            HTTP_X_MINECRAFT_UUID="minecraft-uuid",
        )

        response = self.protected_view(request)

        self.assertIs(response, admin)
        get_player.assert_called_once()

    @patch("utils.decorators.Player.objects.get")
    def test_accepts_admin_minecraft_username_with_server_api_key(self, get_player):
        admin = SimpleNamespace(rank="Admin")
        get_player.return_value = admin
        request = self.factory.post(
            "/npcs/spawns/create/",
            HTTP_X_API_KEY="server-secret",
            HTTP_X_MINECRAFT_USERNAME="AdminPlayer",
        )

        response = self.protected_view(request)

        self.assertIs(response, admin)

    @patch("utils.decorators.Player.objects.get")
    def test_rejects_non_admin_minecraft_player(self, get_player):
        get_player.return_value = SimpleNamespace(rank="Citoyen")
        request = self.factory.post(
            "/npcs/spawns/create/",
            HTTP_X_API_KEY="server-secret",
            HTTP_X_MINECRAFT_UUID="minecraft-uuid",
        )

        response = self.protected_view(request)

        self.assertEqual(response.status_code, 403)

    def test_rejects_api_key_without_minecraft_identity(self):
        request = self.factory.post(
            "/npcs/spawns/create/",
            HTTP_X_API_KEY="server-secret",
        )

        response = self.protected_view(request)

        self.assertEqual(response.status_code, 401)

    def test_rejects_invalid_minecraft_api_key_without_using_firebase(self):
        request = self.factory.post(
            "/npcs/spawns/create/",
            HTTP_X_API_KEY="wrong-secret",
        )

        response = self.protected_view(request)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            json.loads(response.content)["error"],
            "Clé API Minecraft invalide",
        )


class FakeNpc(SimpleNamespace):
    def save(self, *args, **kwargs):
        self.saved = True


@override_settings(API_KEY_RENBLOOD="server-secret")
class MinecraftNpcGameplayAuthenticationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_meet_npc_accepts_minecraft_api_key(self):
        npc = FakeNpc(npc_id="npc-1", met_by=[])
        request = self.factory.post(
            "/npcs/npc-1/meet/",
            {"player_id": "firebase-1"},
            content_type="application/json",
            HTTP_X_API_KEY="server-secret",
        )

        with patch("npcs.views.get_object_or_404", return_value=npc):
            response = meet_npc(request, "npc-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(npc.met_by, ["firebase-1"])
        self.assertTrue(npc.saved)
