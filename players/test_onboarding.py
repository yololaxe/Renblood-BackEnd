"""Real Mongo transactions, isolated database only; no Google account or live player is changed."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import hashlib
import os
import time
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, override_settings
from django.core.management import call_command
from economy.store import Bank
from players.onboarding import Profiles, ProfileError, FIELDS, PORTRAITS
from players import onboarding as views


@unittest.skipUnless(os.getenv("ECONOMY_TEST_URI"), "Requires isolated Mongo test connection")
class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pymongo import MongoClient
        cls.client = MongoClient(os.environ["ECONOMY_TEST_URI"], serverSelectionTimeoutMS=5000)
        cls.database_name = "rb_profiles_test_" + uuid4().hex[:16]
        cls.db = cls.client[cls.database_name]
        cls.bank = Bank(cls.db)
        cls.bank.initialize()
        cls.db.player_registration_link_codes.create_index("code_hash", unique=True)
        cls.db.player_registration_link_codes.create_index("purge_at", expireAfterSeconds=0)
        cls.db.player_registration_attempts.create_index("purge_at", expireAfterSeconds=0)
        cls.service = Profiles(cls.bank)

    @classmethod
    def tearDownClass(cls):
        assert cls.database_name.startswith("rb_profiles_test_") and len(cls.database_name) == 33
        cls.client.drop_database(cls.database_name)
        cls.client.close()

    def setUp(self):
        for name in ("players", "economy_accounts", "economy_operations", "player_registration_profiles",
                     "player_registration_settings", "player_registration_link_codes", "player_registration_links", "player_registration_attempts"):
            self.db[name].delete_many({})
        self.uid = "firebase-" + uuid4().hex
        self.mc = str(uuid4())
        self.service.bootstrap(self.uid)
        self.db.player_registration_servers.replace_one({"_id": "test-server"}, {"_id": "test-server", "enabled": True,
            "key_hash": hashlib.sha256(b"private-game-key").hexdigest()}, upsert=True)
        self.factory = RequestFactory()

    def edit(self, **values):
        return self.service.edit(self.uid, {"revision": self.service.get(self.uid)["revision"], "fields": values})

    def valid(self):
        return self.edit(name="Aliénor", surname="Du Val", description="Une voyageuse.")

    def submit(self):
        return self.service.submit(self.uid, {"revision": self.service.get(self.uid)["revision"]})

    def link(self, uid=None, uuid=None):
        issued = self.service.issue_code(uid or self.uid)
        self.service.confirm_code(issued["code"], uuid or self.mc, "TestPlayer")
        return issued

    def rules(self, **values):
        return self.service.update_settings({"revision": self.service.settings()["revision"], "settings": values}, "admin")

    def review(self, action, **body):
        return self.service.review(self.uid, {"revision": self.service.get(self.uid)["revision"], "action": action, **body}, "admin")

    def test_bootstrap_is_idempotent_without_fake_uuid_or_google_identity(self):
        for _ in range(3): self.service.bootstrap(self.uid)
        self.assertEqual(self.service.profiles.count_documents({}), 1)
        self.assertEqual(self.db.players.count_documents({}), 0)
        self.assertIsNone(self.service.get(self.uid)["minecraft"]["uuid"])
        self.assertEqual(self.service.get(self.uid)["name"], "")

    def test_concurrent_first_login_creates_one_draft(self):
        uid = "another-firebase"
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.service.bootstrap(uid), range(8)))
        self.assertTrue(all(row["id"] == uid for row in results))
        self.assertEqual(self.service.profiles.count_documents({"_id": uid}), 1)

    def test_draft_survives_reload_and_normalizes_whitespace(self):
        self.edit(name="  Aliénor  ", surname=" Du Val ", origin="Vallée du Nord")
        self.assertEqual(self.service.bootstrap(self.uid)["name"], "Aliénor")
        self.assertEqual(self.service.get(self.uid)["origin"], "Vallée du Nord")

    def test_submit_before_minecraft_defers_materialization_then_creates_once(self):
        self.valid()
        result = self.submit()
        self.assertEqual(result["profile"]["status"], "ACTIVE")
        self.assertFalse(result["player_ready"])
        issued = self.link()
        self.service.confirm_code(issued["code"], self.mc, "TestPlayer")
        self.service.submit(self.uid, {"revision": 0})
        player = self.db.players.find_one({"id": self.uid})
        self.assertEqual(player["id_minecraft"], self.mc)
        self.assertEqual(player["rank"], "Citoyen")
        self.assertEqual(player["money"], 0)
        self.assertEqual(len(player["experiences"]["jobs"]), 20)
        self.assertTrue(all(job["xp"] == -1 for job in player["experiences"]["jobs"].values()))
        self.assertEqual(self.db.players.count_documents({}), 1)
        self.assertEqual(self.db.economy_operations.count_documents({"owner_id": self.uid}), 1)
        self.assertTrue(self.service.snapshot(self.uid)["bank_ready"])

    def test_link_before_submit_does_not_activate_an_unfinished_character(self):
        self.link()
        self.assertFalse(self.service.snapshot(self.uid)["player_ready"])
        with self.assertRaises(ProfileError): self.submit()
        self.valid(); self.submit()
        self.assertTrue(self.service.snapshot(self.uid)["player_ready"])

    def test_required_fields_and_protected_game_fields(self):
        for payload in ({"rank": "Admin"}, {"money": "100"}, {"id": "someone"}, {"id_minecraft": self.mc}, {"name": 123}, {"name": "x" * 61}):
            with self.assertRaises(ProfileError): self.edit(**payload)
        with self.assertRaises(ProfileError) as failure: self.submit()
        self.assertIn("name", failure.exception.fields)

    def test_stale_revision_cannot_overwrite_draft(self):
        self.valid()
        with self.assertRaises(ProfileError) as failure:
            self.service.edit(self.uid, {"revision": 0, "fields": {"name": "Remplacé"}})
        self.assertEqual(failure.exception.status, 409)
        self.assertEqual(self.service.get(self.uid)["name"], "Aliénor")

    def test_concurrent_changes_have_one_winner_without_lost_update(self):
        def edit(value):
            try: return self.service.edit(self.uid, {"revision": 0, "fields": {"name": value}})
            except ProfileError as error: return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(edit, ["Premier", "Second"]))
        self.assertEqual(sum(isinstance(row, dict) for row in results), 1)
        self.assertIn(409, results)

    def test_closed_and_moderated_registration(self):
        self.valid(); self.rules(mode="CLOSED")
        with self.assertRaises(ProfileError): self.submit()
        self.rules(mode="MODERATED")
        self.assertEqual(self.submit()["profile"]["status"], "PENDING")
        self.link()
        self.assertFalse(self.service.snapshot(self.uid)["player_ready"])
        self.review("APPROVE_REGISTRATION")
        self.assertTrue(self.service.snapshot(self.uid)["player_ready"])

    def test_mandatory_minecraft_blocks_submission(self):
        self.valid(); self.rules(require_minecraft=True)
        with self.assertRaises(ProfileError) as failure: self.submit()
        self.assertEqual(failure.exception.code, "MINECRAFT_REQUIRED")

    def test_name_request_requires_staff_and_preserves_progress_and_money(self):
        self.valid(); self.link(); self.submit()
        self.db.players.update_one({"id": self.uid}, {"$set": {"money": 777, "strength": 35, "rank": "Noble"}})
        result = self.edit(name="Nouvelle", description="Histoire enrichie")
        self.assertEqual(result["profile"]["name"], "Aliénor")
        self.assertEqual(result["profile"]["pending_changes"]["name"], "Nouvelle")
        self.assertEqual(self.db.players.find_one({"id": self.uid})["description"], "Histoire enrichie")
        self.review("APPROVE_NAME")
        player = self.db.players.find_one({"id": self.uid})
        self.assertEqual((player["name"], player["money"], player["strength"], player["rank"]), ("Nouvelle", 777, 35, "Noble"))

    def test_free_names_and_refusal_reason(self):
        self.valid(); self.submit(); self.rules(name_policy="FREE")
        self.assertEqual(self.edit(name="Libre")["profile"]["name"], "Libre")
        self.rules(name_policy="REVIEW_AFTER_VALIDATION"); self.edit(name="Refusé")
        with self.assertRaises(ProfileError): self.review("REJECT_NAME")
        self.review("REJECT_NAME", reason="Choisissez un autre nom RP.")
        self.assertIsNone(self.service.get(self.uid)["pending_changes"])
        self.assertEqual(self.service.get(self.uid)["history"][-1]["details"]["reason"], "Choisissez un autre nom RP.")

    def test_code_expiry_cooldown_and_one_time_use(self):
        issued = self.service.issue_code(self.uid)
        record = self.service.codes.find_one({"_id": self.uid})
        self.assertNotIn(issued["code"], json.dumps(record, default=str))
        with self.assertRaises(ProfileError): self.service.issue_code(self.uid)
        self.service.codes.update_one({"_id": self.uid}, {"$set": {"expires_at": time.time() - 1}})
        with self.assertRaises(ProfileError): self.service.confirm_code(issued["code"], self.mc, "TestPlayer")
        self.service.codes.update_one({"_id": self.uid}, {"$set": {"expires_at": time.time() + 600}})
        self.service.confirm_code(issued["code"], self.mc, "TestPlayer")
        with self.assertRaises(ProfileError): self.service.confirm_code(issued["code"], str(uuid4()), "SomeoneElse")

    def test_same_minecraft_cannot_be_claimed_by_two_characters(self):
        second = "second-owner"; self.service.bootstrap(second)
        codes = [(self.uid, self.service.issue_code(self.uid)["code"]), (second, self.service.issue_code(second)["code"])]
        def confirm(pair):
            try: self.service.confirm_code(pair[1], self.mc, "TestPlayer"); return True
            except ProfileError: return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(confirm, codes))
        self.assertEqual(sum(results), 1)

    def test_existing_players_are_never_reset_or_automatically_migrated(self):
        old = {"id": "old", "id_minecraft": str(uuid4()), "pseudo_minecraft": "OldPlayer", "name": "Ancien", "surname": "Nom", "rank": "Admin", "money": 300, "experiences": {"jobs": {"miner": {"xp": 4321}}}}
        self.db.players.insert_one(deepcopy(old))
        original = self.db.players.find_one({"id": "old"})
        self.service.bootstrap("old"); self.service.prepare_bank("old")
        self.assertEqual(self.db.players.find_one({"id": "old"}), original)
        self.assertEqual(self.db.economy_accounts.count_documents({}), 0)
        self.assertTrue(self.service.get("old")["minecraft"]["verified"])

    def test_noncanonical_legacy_uuid_cannot_be_claimed(self):
        self.db.players.insert_one({"id": "legacy-owner", "id_minecraft": self.mc.upper().replace("-", "")})
        issued = self.service.issue_code(self.uid)
        with self.assertRaises(ProfileError) as failure:
            self.service.confirm_code(issued["code"], self.mc, "TestPlayer")
        self.assertEqual(failure.exception.code, "MINECRAFT_IN_USE")

    def test_replacement_is_reviewed_and_keeps_firebase_owner_and_bank(self):
        self.valid(); self.link(); self.submit()
        before = self.db.economy_accounts.find_one({"_id": "bank:" + self.uid})
        self.service.codes.update_one({"_id": self.uid}, {"$set": {"issued_at": 0}})
        replacement = str(uuid4()); self.link(uuid=replacement)
        self.assertEqual(self.db.players.find_one({"id": self.uid})["id_minecraft"], self.mc)
        self.review("APPROVE_MINECRAFT")
        self.assertEqual(self.db.players.find_one({"id": self.uid})["id_minecraft"], replacement)
        self.assertEqual(self.db.economy_accounts.find_one({"_id": "bank:" + self.uid}), before)
        self.assertIsNone(self.service.links.find_one({"_id": self.mc}))

    def test_bank_failure_can_be_retried_without_recreating_character(self):
        self.valid(); self.link()
        with patch.object(self.bank, "migrate", side_effect=RuntimeError("simulated bank outage")):
            self.submit()
        self.assertTrue(self.service.snapshot(self.uid)["player_ready"])
        self.assertFalse(self.service.snapshot(self.uid)["bank_ready"])
        self.service.prepare_bank(self.uid)
        self.assertTrue(self.service.snapshot(self.uid)["bank_ready"])
        self.assertEqual(self.db.players.count_documents({}), 1)

    def test_configuration_cannot_grant_admin_and_detects_stale_edits(self):
        for values in ({"starting_rank": "Admin"}, {"starting_rank": []}, {"mode": {}}, {"name_policy": []}, {"portraits": []}, {"required_fields": []}, {"require_minecraft": "false"}):
            with self.assertRaises(ProfileError): self.rules(**values)
        self.rules(mode="MODERATED")
        with self.assertRaises(ProfileError): self.service.update_settings({"revision": 0, "settings": {"mode": "OPEN"}}, "admin")

    def test_name_request_can_be_amended_and_cancelled(self):
        self.valid(); self.submit(); self.edit(name="Nouvelle"); self.edit(surname="Autre")
        request = self.service.get(self.uid)["pending_changes"]
        self.assertEqual((request["name"], request["surname"]), ("Nouvelle", "Autre"))
        self.service.cancel_request(self.uid, {"revision": self.service.get(self.uid)["revision"], "type": "NAME"})
        self.assertIsNone(self.service.get(self.uid)["pending_changes"])
        self.assertEqual(self.service.get(self.uid)["name"], "Aliénor")

    def test_disabling_a_portrait_does_not_revoke_an_existing_selection(self):
        self.valid(); self.submit(); self.rules(portraits=["guard"])
        result = self.edit(description="Histoire complétée")
        self.assertEqual(result["profile"]["portrait"], "wanderer")
        self.assertEqual(result["profile"]["description"], "Histoire complétée")

    def test_cancel_replacement_frees_reservation_without_unlinking_current_account(self):
        self.valid(); self.link(); self.submit()
        self.service.codes.update_one({"_id": self.uid}, {"$set": {"issued_at": 0}})
        replacement = str(uuid4()); self.link(uuid=replacement)
        self.service.cancel_request(self.uid, {"revision": self.service.get(self.uid)["revision"], "type": "MINECRAFT"})
        self.assertIsNone(self.service.links.find_one({"_id": replacement}))
        self.assertEqual(self.service.get(self.uid)["minecraft"]["uuid"], self.mc)

    @override_settings(API_KEY_RENBLOOD="test-api")
    def test_endpoints_use_authenticated_owner_and_require_server_for_link(self):
        with patch("players.onboarding.get_bank", return_value=self.bank), patch("players.onboarding.auth.verify_id_token", return_value={"uid": self.uid}):
            request = self.factory.post("/", {"id": "someone-else"}, content_type="application/json", HTTP_AUTHORIZATION="Bearer token")
            response = views.session_view(request)
            self.assertEqual(json.loads(response.content)["profile"]["id"], self.uid)
            request = self.factory.post("/", {}, content_type="application/json", HTTP_AUTHORIZATION="Bearer token")
            self.assertEqual(views.confirm_view(request).status_code, 401)
            request = self.factory.get("/", HTTP_AUTHORIZATION="Bearer token")
            self.assertEqual(views.settings_view(request).status_code, 403)
            request = self.factory.post("/", [], content_type="application/json", HTTP_AUTHORIZATION="Bearer token")
            self.assertEqual(views.profile_view(request).status_code, 400)

    @override_settings(API_KEY_RENBLOOD="test-api")
    def test_confirmation_endpoint_rate_limits_by_game_identity(self):
        with patch("players.onboarding.get_bank", return_value=self.bank):
            for _ in range(11):
                request = self.factory.post("/", {"code": "AAAAAAAA", "username": "TestPlayer"}, content_type="application/json", HTTP_X_API_KEY="test-api", HTTP_X_MINECRAFT_UUID=self.mc,
                    HTTP_X_RENBLOOD_LINK_SERVER="test-server", HTTP_X_RENBLOOD_LINK_KEY="private-game-key")
                response = views.confirm_view(request)
            self.assertEqual(response.status_code, 429)

    @override_settings(API_KEY_RENBLOOD="test-api")
    def test_shared_browser_api_key_is_not_a_proof_of_game_ownership(self):
        issued = self.service.issue_code(self.uid)
        with patch("players.onboarding.get_bank", return_value=self.bank):
            for extra in ({}, {"HTTP_X_RENBLOOD_LINK_SERVER": "test-server", "HTTP_X_RENBLOOD_LINK_KEY": "wrong"}):
                request = self.factory.post("/", {"code": issued["code"], "username": "TestPlayer"}, content_type="application/json",
                    HTTP_X_API_KEY="test-api", HTTP_X_MINECRAFT_UUID=self.mc, **extra)
                self.assertEqual(views.confirm_view(request).status_code, 401)
        self.assertFalse(self.service.get(self.uid)["minecraft"]["verified"])

    @override_settings(API_KEY_RENBLOOD="test-api")
    def test_server_proof_confirms_authenticated_game_identity(self):
        self.valid(); self.submit(); issued = self.service.issue_code(self.uid)
        with patch("players.onboarding.get_bank", return_value=self.bank):
            request = self.factory.post("/", {"code": issued["code"], "username": "TestPlayer"}, content_type="application/json",
                HTTP_X_API_KEY="test-api", HTTP_X_MINECRAFT_UUID=self.mc, HTTP_X_RENBLOOD_LINK_SERVER="test-server", HTTP_X_RENBLOOD_LINK_KEY="private-game-key")
            self.assertEqual(views.confirm_view(request).status_code, 200)
        self.assertEqual(self.db.players.find_one({"id": self.uid})["id_minecraft"], self.mc)

    def test_server_configuration_is_private_idempotent_and_can_be_rotated(self):
        with TemporaryDirectory(prefix="renblood-profile-proof-") as temporary:
            profile = Path(temporary)
            config = profile / "config/medieval_coins/server_config.json"
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({"apiKey": "legacy-key", "apiUrl": "http://127.0.0.1:8000"}), encoding="utf-8")
            output = StringIO()
            with patch("players.management.commands.configure_player_link.get_bank", return_value=self.bank):
                call_command("configure_player_link", profile=str(profile), label="Test server", stdout=output)
                initial = json.loads(config.read_text(encoding="utf-8"))
                call_command("configure_player_link", profile=str(profile), label="Test server", stdout=output)
                self.assertEqual(json.loads(config.read_text(encoding="utf-8")), initial)
                call_command("configure_player_link", profile=str(profile), label="Test server", rotate=True, stdout=output)
            updated = json.loads(config.read_text(encoding="utf-8"))
            self.assertNotEqual(initial["playerLinkKey"], updated["playerLinkKey"])
            self.assertEqual(updated["apiKey"], "legacy-key")
            self.assertNotIn(initial["playerLinkKey"], output.getvalue())
            record = self.db.player_registration_servers.find_one({"_id": updated["playerLinkServerId"]})
            self.assertEqual(record["key_hash"], hashlib.sha256(updated["playerLinkKey"].encode()).hexdigest())
