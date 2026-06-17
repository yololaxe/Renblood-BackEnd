from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from quests.api_views import _npc_name, _validate_npc_id
from quests.contracts import find_npc
from quests.views import cancel_player_quest, join_multiplayer_quest, update_player_quest_status


class QuestNpcLookupTests(SimpleTestCase):
    @patch("npcs.models.Npc.objects.filter")
    def test_find_npc_uses_djongo_compatible_object_lookup(self, filter_mock):
        npc = SimpleNamespace(npc_id="npc-1", name="NPC One")
        queryset = Mock()
        queryset.first.return_value = npc
        filter_mock.return_value = queryset

        self.assertIs(find_npc("npc-1"), npc)
        filter_mock.assert_called_once_with(npc_id="npc-1")
        queryset.first.assert_called_once_with()

    @patch("quests.api_views.find_npc")
    def test_validate_npc_id_accepts_existing_npc(self, find_npc_mock):
        find_npc_mock.return_value = SimpleNamespace(npc_id="npc-1")

        _validate_npc_id("npc-1", "startNpcId")

    @patch("quests.api_views.find_npc")
    def test_validate_npc_id_rejects_unknown_npc(self, find_npc_mock):
        find_npc_mock.return_value = None

        with self.assertRaisesMessage(ValueError, "startNpcId: NPC introuvable: missing"):
            _validate_npc_id("missing", "startNpcId")

    @patch("quests.api_views.find_npc")
    def test_npc_name_reads_name_from_object(self, find_npc_mock):
        find_npc_mock.return_value = SimpleNamespace(name="NPC One")

        self.assertEqual(_npc_name("npc-1"), "NPC One")


class FakeQuestState(SimpleNamespace):
    def save(self, *args, **kwargs):
        self.saved = True

    def delete(self):
        self.deleted = True


@override_settings(API_KEY_RENBLOOD="secret")
class MinecraftQuestEndpointTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_update_player_quest_status_accepts_minecraft_api_key(self):
        state = FakeQuestState(
            status="IN_PROGRESS",
            startedAt=None,
            completedAt=None,
            members=[],
        )
        request = self.factory.post(
            "/quests/player/firebase-1/update/",
            {"quest_id": "m1.1.1", "status": "COMPLETED"},
            content_type="application/json",
            HTTP_X_API_KEY="secret",
        )

        with patch("quests.views.PlayerQuestState.objects.get_or_create", return_value=(state, False)):
            response = update_player_quest_status(request, "firebase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(state.status, "COMPLETED")
        self.assertIsNotNone(state.completedAt)
        self.assertTrue(state.saved)

    def test_update_player_quest_status_accepts_bearer_server_api_key(self):
        state = FakeQuestState(
            status="IN_PROGRESS",
            startedAt=None,
            completedAt=None,
            members=[],
        )
        request = self.factory.post(
            "/quests/player/firebase-1/update/",
            {"quest_id": "m1.1.1", "status": "COMPLETED"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer secret",
        )

        with patch("quests.views.PlayerQuestState.objects.get_or_create", return_value=(state, False)):
            response = update_player_quest_status(request, "firebase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(state.status, "COMPLETED")

    def test_cancel_player_quest_accepts_minecraft_api_key(self):
        state = FakeQuestState()
        request = self.factory.post(
            "/quests/player/firebase-1/cancel/",
            {"quest_id": "m1.1.1"},
            content_type="application/json",
            HTTP_X_API_KEY="secret",
        )

        with patch("quests.views.PlayerQuestState.objects.get", return_value=state):
            response = cancel_player_quest(request, "firebase-1")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(state.deleted)

    def test_join_multiplayer_quest_accepts_minecraft_api_key(self):
        state = FakeQuestState(status="LOCKED", startedAt=None)
        request = self.factory.post(
            "/quests/m1.1.1/join/",
            {"player_id": "firebase-1"},
            content_type="application/json",
            HTTP_X_API_KEY="secret",
        )

        with patch("quests.views.get_object_or_404", return_value=SimpleNamespace(type="Multi")):
            with patch("quests.views.PlayerQuestState.objects.get_or_create", return_value=(state, False)):
                response = join_multiplayer_quest(request, "m1.1.1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(state.status, "IN_PROGRESS")
        self.assertTrue(state.saved)
