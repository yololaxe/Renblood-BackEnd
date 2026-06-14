from django.test import SimpleTestCase

from game_sessions.serializers.session_serializer import SessionSerializer


class RelatedCollection:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def count(self):
        return len(self._items)


class DummyPlayer:
    def __init__(self, identifier, name, pseudo_minecraft=None):
        self.id = identifier
        self.name = name
        self.pseudo_minecraft = pseudo_minecraft


class DummyFuture:
    def __init__(self, player):
        self.player = player


class SessionSerializerTests(SimpleTestCase):
    def test_counts_use_prefetched_cache_when_present(self):
        serializer = SessionSerializer()
        players = [DummyPlayer("1", "Arthur", "Perceval"), DummyPlayer("2", "Lancelot")]
        futures = [DummyFuture(players[0])]

        session = type(
            "SessionStub",
            (),
            {
                "players": RelatedCollection(players),
                "futures": RelatedCollection(futures),
                "_prefetched_objects_cache": {
                    "players": players,
                    "futures": futures,
                },
            },
        )()

        self.assertEqual(serializer.get_players_count(session), 2)
        self.assertEqual(serializer.get_futures_count(session), 1)
        self.assertEqual(
            serializer.get_players(session),
            [{"id": "1", "name": "Perceval"}, {"id": "2", "name": "Lancelot"}],
        )
        self.assertEqual(serializer.get_futures_players(session), ["Perceval"])
