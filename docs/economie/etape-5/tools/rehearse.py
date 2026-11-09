"""Rehearse the economy cutover with a disposable Mongo database and Django routes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from threading import Thread
from tempfile import TemporaryDirectory
from socketserver import ThreadingMixIn
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch
from uuid import uuid4
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from dotenv import dotenv_values
from pymongo import MongoClient

HERE = Path(__file__).resolve().parent
BACKEND = Path('D:/Projets/Projet/DEVELOPPEMENT/Renblood-BackEnd')
PREFIX = '/api/economy/v1/'
FIXTURE_KEY = 'local-economy-rehearsal'
HTTP_BASE = None
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
os.environ.setdefault('DJANGO_ENV', 'local')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'RenbloodBackEnd.settings')

import django
django.setup()
from django.test import Client, override_settings
from players.models import Player
from economy.audit import reconcile
from economy.domain import fingerprint
from economy.store import Bank


def migrate(config, database, report, apply=False, expected=None, selected=()):
    command = [sys.executable, '-m', 'economy.migrate_accounts', '--env-file', str(config),
               '--database', database, '--report', str(report)]
    if apply:
        command.append('--apply')
    if expected:
        command.extend(['--expected-report', str(expected)])
    for owner in selected:
        command.extend(['--player-id', owner])
    subprocess.run(command, check=True, timeout=90)
    return {row['owner_id']: row for row in json.loads(report.read_text())['results']}


@contextmanager
def simulated_identities(bank):
    def lookup(**query):
        row = bank.db.players.find_one(query)
        if row is None:
            raise Player.DoesNotExist
        return SimpleNamespace(**{k: v for k, v in row.items() if k != '_id'})

    players = SimpleNamespace(objects=SimpleNamespace(get=lookup), DoesNotExist=Player.DoesNotExist)
    with override_settings(ALLOWED_HOSTS=['testserver'], API_KEY_RENBLOOD=FIXTURE_KEY), \
         patch('economy.views.get_bank', return_value=bank), \
         patch('economy.store.get_bank', return_value=bank), \
         patch('economy.views.Player', players), \
         patch('players.views.Player', players), \
         patch('economy.views.auth.verify_id_token', side_effect=lambda token: {'uid': token}):
        yield


class FixtureHttpServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def serve_fixture(database, ready):
    from django.core.wsgi import get_wsgi_application
    if not database.startswith('rb_econ_test_') or len(database) != 29:
        raise ValueError('Only the isolated fixture database may be used')
    with MongoClient(os.environ['ECONOMY_REHEARSAL_URI'], serverSelectionTimeoutMS=5000) as connection:
        with simulated_identities(Bank(connection[database])):
            application = get_wsgi_application()
            with make_server('127.0.0.1', 0, application, FixtureHttpServer, QuietHandler) as server:
                Thread(target=lambda: (sys.stdin.readline(), server.shutdown()), daemon=True).start()
                Path(ready).write_text(str(server.server_port), encoding='ascii')
                server.serve_forever()


@contextmanager
def routes(bank):
    global HTTP_BASE
    with TemporaryDirectory(prefix='renblood-economy-http-') as directory:
        ready = Path(directory) / 'port'
        process = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(__file__).resolve()),
                                    '--serve-fixture', bank.db.name, str(ready)],
                                   stdin=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 20
            while not ready.exists() or not ready.stat().st_size:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Fixture HTTP process did not start')
                time.sleep(0.05)
            HTTP_BASE = 'http://127.0.0.1:' + ready.read_text(encoding='ascii')
            yield
        finally:
            HTTP_BASE = None
            if process.poll() is None:
                try:
                    process.communicate('stop\n', timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=10)


def game(path, mc, body=None, key=None, expected=200):
    headers = {'HTTP_X_API_KEY': FIXTURE_KEY, 'HTTP_X_MINECRAFT_UUID': mc}
    if key:
        headers['HTTP_IDEMPOTENCY_KEY'] = key
    return request(PREFIX + path, body, expected, headers)


def request(path, body, expected, headers):
    if HTTP_BASE:
        wire_headers = {key.removeprefix('HTTP_').replace('_', '-'): value for key, value in headers.items()}
        wire_headers['Host'] = 'testserver'
        payload = None if body is None else json.dumps(body).encode('utf-8')
        if payload is not None:
            wire_headers['Content-Type'] = 'application/json'
        try:
            response = urlopen(Request(HTTP_BASE + path, data=payload, headers=wire_headers), timeout=15)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            assert response.status == expected, (path, response.status, data[:300])
            return json.loads(data)
    client = Client()
    response = client.get(path, **headers) if body is None else client.post(path, body, 'application/json', **headers)
    assert response.status_code == expected, (path, response.status_code, response.content[:300])
    return response.json()


def delivery(mc, row):
    return game(f"operations/{row['operation_id']}/delivery", mc,
                {'revision': row['revision'], 'proof_id': 'fixture-save:' + row['operation_id']})


def main():
    env = dotenv_values(BACKEND / '.env.local')
    os.environ['ECONOMY_REHEARSAL_URI'] = env['MONGO_URI']
    client = MongoClient(env['MONGO_URI'], serverSelectionTimeoutMS=5000)
    database = 'rb_econ_test_' + uuid4().hex[:16]
    output = HERE / database
    output.mkdir()
    config = output / 'fixture.env'
    config.write_text(f'MONGO_DB_NAME={database}\nMONGO_URI=${{ECONOMY_REHEARSAL_URI}}\n', encoding='ascii')
    bank = Bank(client[database])
    mc, merchant, admin, shared = [str(uuid4()) for _ in range(4)]
    originals = [
        {'id': 'buyer', 'id_minecraft': mc, 'money': 1024.0, 'rank': 'Citoyen'},
        {'id': 'merchant', 'id_minecraft': merchant, 'money': 512, 'rank': 'Citoyen'},
        {'id': 'admin', 'id_minecraft': admin, 'money': 256, 'rank': 'Admin'},
        {'id': 'fraction', 'id_minecraft': str(uuid4()), 'money': 1.5},
        {'id': 'duplicate-a', 'id_minecraft': shared, 'money': 64},
        {'id': 'duplicate-b', 'id_minecraft': shared, 'money': 64},
        {'id': 'dangling-marker', 'id_minecraft': str(uuid4()), 'money': 42, 'economy_v1': True},
    ]
    report = {'synthetic': True, 'transport': 'Local HTTP, two successive Django processes, simulated identities and real Mongo transactions'}
    try:
        bank.db.players.insert_many(originals)
        before = {p['id']: p['money'] for p in bank.db.players.find({})}
        dry = migrate(config, database, output / 'before.json')
        assert bank.accounts.count_documents({}) == 0
        assert before == {p['id']: p['money'] for p in bank.db.players.find({})}
        blocked = {owner: row['code'] for owner, row in dry.items() if row['status'] == 'blocked'}
        assert blocked == {'fraction': 'MIGRATION_REQUIRED', 'duplicate-a': 'MINECRAFT_LINK_CONFLICT',
                           'duplicate-b': 'MINECRAFT_LINK_CONFLICT', 'dangling-marker': 'MIGRATION_STATE_CONFLICT'}
        eligible = {'buyer', 'merchant', 'admin'}
        bank.db.players.update_one({'id': 'buyer'}, {'$inc': {'money': 1}})
        stale = migrate(config, database, output / 'stale.json', apply=True,
                        expected=output / 'before.json', selected=['buyer'])
        assert stale['buyer']['code'] == 'MIGRATION_BALANCE_CHANGED'
        assert bank.accounts.count_documents({}) == 0
        bank.db.players.update_one({'id': 'buyer'}, {'$inc': {'money': -1}})
        applied = migrate(config, database, output / 'applied.json', apply=True,
                          expected=output / 'before.json', selected=sorted(eligible))
        repeated = migrate(config, database, output / 'repeat.json', apply=True,
                           expected=output / 'before.json', selected=sorted(eligible))
        assert {k for k, v in applied.items() if v['status'] == 'migrated'} == eligible
        assert {k for k, v in repeated.items() if v['status'] == 'already_migrated'} == eligible
        assert bank.operations.count_documents({'type': 'OPENING_BALANCE'}) == 3
        report['migration'] = {'opening_total': '1792', 'accounts': 3, 'blocked': blocked,
                               'duplicate_openings': 0, 'preview_read_only': True, 'stale_balance_refused': True}
        assert reconcile(bank.db)['total_bank_and_cashboxes'] == '1792'
        bank.db.quests.insert_one({'questId': 'legacy-fixture', 'money': 50})
        bank.db.player_quest_states.insert_one({'_id': mc + ':legacy-fixture', 'quest_id': 'legacy-fixture',
                                                'player_id': mc, 'status': 'COMPLETED'})
        with routes(bank):
            legacy = request(f'/players/deposit/{mc}/', {'amount': 50}, 409, {'HTTP_X_API_KEY': FIXTURE_KEY})
            assert legacy['code'] == 'ECONOMY_ROUTE_REQUIRED'
            legacy_quest = game('quests/legacy-fixture/reward', mc, {}, expected=409)
            assert legacy_quest['code'] == 'QUEST_NOT_COMPLETED'
            game('commerce/businesses', merchant, {'business_id': 'market:fixture', 'kind': 'MARKET',
                 'owner_minecraft': merchant, 'label': 'Comptoir de recette'})
            nbt = '{id:"minecraft:iron_sword",Count:1b,tag:{RepairCost:7}}'
            game('commerce/offers', merchant, {'business_id': 'market:fixture', 'offer_id': 'slot-0',
                 'price_version': 'fixture-v1', 'buy_price': '64', 'sell_price': '0', 'stock': 0, 'item_nbt': nbt})
            stock = game('commerce/operations', merchant, {'business_id': 'market:fixture', 'action': 'STOCK_IN',
                         'offer_id': 'slot-0', 'quantity': 1}, 'fixture-stock-in')
            assert delivery(merchant, stock)['state'] == 'CONFIRMED'
            body = {'business_id': 'market:fixture', 'action': 'BUY', 'payment': 'BANK', 'offer_id': 'slot-0',
                    'price_version': 'fixture-v1', 'unit_price': '64', 'quantity': 1}
            purchase = game('commerce/operations', mc, body, 'fixture-purchase')
            withdrawal = game('operations', mc, {'type': 'WITHDRAW', 'amount': '32'}, 'fixture-withdrawal')
            assert purchase['item_nbt'] == nbt
        checkpoint = reconcile(bank.db)
        assert len(checkpoint['pending']) == 2 and not checkpoint['anomalies']
        client.close()
        client = MongoClient(env['MONGO_URI'], serverSelectionTimeoutMS=5000)
        bank = Bank(client[database])
        with routes(bank):
            replay = game('commerce/operations', mc, body, 'fixture-purchase')
            assert replay['operation_id'] == purchase['operation_id']
            assert delivery(mc, purchase)['state'] == 'CONFIRMED'
            assert delivery(mc, purchase)['state'] == 'CONFIRMED'
            game(f"operations/{withdrawal['operation_id']}/reconcile", mc,
                 {'revision': withdrawal['revision'], 'proof_id': 'fixture-unknown-save'})
            viewer = {'HTTP_AUTHORIZATION': 'Bearer buyer'}
            wallet = request(PREFIX + 'wallet', None, 200, viewer)
            assert wallet['bank']['available'] == '928' and wallet['bank']['reserved'] == '32'
            request(PREFIX + 'admin/desk/overview', None, 403, viewer)
            overview = request(PREFIX + 'admin/desk/overview', None, 200, {'HTTP_AUTHORIZATION': 'Bearer admin'})
            assert overview['review'] == 1
            assert request(PREFIX + 'operations/' + purchase['operation_id'], None, 200, viewer)['state'] == 'CONFIRMED'
            measurements = []
            def wallet_read(_):
                start = time.perf_counter()
                request(PREFIX + 'wallet', None, 200, viewer)
                return (time.perf_counter() - start) * 1000
            for concurrency in (1, 10, 30):
                with ThreadPoolExecutor(max_workers=concurrency) as pool:
                    latencies = sorted(pool.map(wallet_read, range(30)))
                measurements.append({'workers': concurrency, 'requests': len(latencies),
                                     'p95_ms': round(latencies[math.ceil(len(latencies) * .95) - 1], 2)})
            game('commerce/businesses', merchant, {'business_id': 'inn:fixture', 'kind': 'INN',
                 'owner_minecraft': merchant, 'label': 'Auberge de recette'})
            game('commerce/offers', merchant, {'business_id': 'inn:fixture', 'offer_id': 'room-1',
                 'price_version': 'fixture-v1', 'buy_price': '16', 'sell_price': '0'})
            rent = game('commerce/operations', mc, {'business_id': 'inn:fixture', 'action': 'SERVICE',
                        'offer_id': 'room-1', 'price_version': 'fixture-v1', 'unit_price': '16'}, 'fixture-rent')
            delivery(mc, rent)
            refund = game('commerce/operations', mc, {'business_id': 'inn:fixture', 'action': 'REFUND',
                          'original_operation_id': rent['operation_id']}, 'fixture-refund')
            delivery(mc, refund)
            game('commerce/businesses', admin, {'business_id': 'npc-contracts', 'kind': 'NPC',
                 'label': 'Contrats de recette'})
            fund = game('commerce/operations', admin, {'business_id': 'npc-contracts', 'action': 'FUND',
                        'amount': '48'}, 'fixture-fund')
            delivery(admin, fund)
            game('commerce/offers', admin, {'business_id': 'npc-contracts', 'offer_id': 'contract',
                 'price_version': 'fixture-v1', 'buy_price': '12', 'sell_price': '12'})
            contract_body = {'business_id': 'npc-contracts', 'action': 'SELL', 'offer_id': 'contract',
                             'price_version': 'fixture-v1', 'unit_price': '12'}
            contract = game('commerce/operations', mc, contract_body, 'fixture-contract')
            delivery(mc, contract)
            replay_contract = game('commerce/operations', mc, contract_body, 'another-contract-key', expected=409)
            assert replay_contract['code'] == 'OFFER_ALREADY_USED'
            bank.db.economy_accounts.insert_many([
                {'_id': f'cashbox:page-{index:02}', 'pocket': 'CASHBOX', 'business_id': f'page-{index:02}',
                 'owner_id': 'merchant', 'available': 0, 'reserved': 0, 'incoming': 0, 'opening_balance': 0}
                for index in range(51)
            ])
            merchant_view = {'HTTP_AUTHORIZATION': 'Bearer merchant'}
            page = request(PREFIX + 'wallet', None, 200, merchant_view)
            tail = request(PREFIX + 'wallet?before=' + page['next_cursor'], None, 200, merchant_view)
            assert page['bank'] == tail['bank'] and page['bank']['account_id'] == 'bank:merchant'
            assert len(page['cashboxes']) == 50 and len(tail['cashboxes']) == 3 and not tail['has_more']
            assert not ({row['account_id'] for row in page['cashboxes']} & {row['account_id'] for row in tail['cashboxes']})
        final = reconcile(bank.db)
        assert final['total_bank_and_cashboxes'] == '1792' and not final['anomalies']
        assert [row['state'] for row in final['pending']] == ['RECONCILIATION_REQUIRED']
        stock_id = fingerprint({'business': 'market:fixture', 'offer': 'slot-0'})
        assert bank.db.economy_offers.find_one({'_id': stock_id})['stock'] == 0
        assert bank.accounts.find_one({'_id': 'cashbox:market:fixture'})['available'] == 64
        bank.db.economy_offers.delete_one({'_id': stock_id})
        bank.accounts.delete_one({'_id': 'cashbox:market:fixture'})
        anomalies = {row['code'] for row in reconcile(bank.db)['anomalies'] if 'code' in row}
        assert {'CONFIRMED_ACCOUNT_MISSING', 'CONFIRMED_STOCK_MISSING'} <= anomalies
        report['settlement'] = {'old_deposit_rejected': True, 'pending_at_checkpoint': 2,
                                'same_purchase_after_reconnect': True, 'total_after': final['total_bank_and_cashboxes'],
                                'review_reserved': '32', 'merchant_cashbox': '64', 'stock_after': 0,
                                'anomalies_before_fault_injection': len(final['anomalies']),
                                'legacy_quest_not_repaid': True, 'inn_refunded_once': True,
                                'npc_contract_paid_once': True,
                                'injected_faults_detected': sorted(anomalies)}
        report['wallet_http_latency'] = measurements
        report['pagination_preserves_bank_without_duplicate_cashboxes'] = True
        (HERE / 'rehearsal-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        assert database.startswith('rb_econ_test_') and len(database) == 29
        client.drop_database(database)
        client.close()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--serve-fixture':
        serve_fixture(sys.argv[2], sys.argv[3])
    else:
        main()
