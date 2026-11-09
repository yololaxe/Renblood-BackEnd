"""Start a throwaway Forge world and exercise native legacy counter saves."""
import hashlib
import gzip
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import queue
import shutil
import socket
import struct
import subprocess
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

HERE = Path(__file__).resolve().parent
DEVELOPMENT = Path('D:/Projets/Projet/DEVELOPPEMENT')
FORGE_RUNTIME = Path('D:/Projets/Projet/localhost_server1.20.1')
JAVA = Path('C:/Program Files/Java/jdk-17/bin/java.exe')
FORGE_ARGS = Path('libraries/net/minecraftforge/forge/1.20.1-47.4.3/win_args.txt')
SERVER = HERE / ('forge-fixture-' + uuid4().hex[:8])
INNS = SERVER / 'phase5-fixture/data/medieval_structures_inns.dat'


def nbt_name(value):
    data = value.encode('ascii')
    return struct.pack('>H', len(data)) + data


def tag(kind, name, payload):
    return bytes([kind]) + nbt_name(name) + payload


def seed_old_inn():
    room = (tag(3, 'Number', struct.pack('>i', 1))
            + tag(6, 'Price', struct.pack('>d', 4.0))
            + tag(1, 'IsBusy', b'\x01')
            + tag(11, 'OccupantUUID', struct.pack('>i', 4) + uuid4().bytes)
            + tag(6, 'Balance', struct.pack('>d', -3.5)) + b'\0')
    inn = (tag(8, 'Name', nbt_name('Fixture inn'))
           + tag(6, 'Balance', struct.pack('>d', 12.5))
           + tag(9, 'Rooms', struct.pack('>Bi', 10, 1) + room) + b'\0')
    data = tag(9, 'Inns', struct.pack('>Bi', 10, 1) + inn) + b'\0'
    INNS.parent.mkdir(parents=True)
    INNS.write_bytes(gzip.compress(tag(10, '', tag(10, 'data', data) + b'\0')))


def check_inn(server):
    server.command('time add 24000')
    server.expect('Set the time to')
    time.sleep(0.25)
    server.command('save-all flush')
    server.expect('Saved the game')
    data = gzip.decompress(INNS.read_bytes())
    for value in (12.5, -3.5):
        assert tag(6, 'Balance', struct.pack('>d', value)) in data
    marker = tag(11, 'EconomyId', struct.pack('>i', 4))
    offset = data.index(marker) + len(marker)
    return data[offset:offset + 16]


class FixtureApi(BaseHTTPRequestHandler):
    calls = Counter()

    def reply(self):
        path = urlsplit(self.path).path
        self.calls[path] += 1
        payload = json.dumps({'revision': 0, 'npcs': [], 'spawns': [], 'changes': [],
                              'cities': [], 'items': [], 'results': [], 'data': []}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = reply
    do_POST = reply

    def log_message(self, *args):
        pass


def prepare_server(api_port):
    SERVER.mkdir()
    # Reuse the installed engine and existing local license acceptance only.
    shutil.copytree(FORGE_RUNTIME / 'libraries', SERVER / 'libraries')
    shutil.copyfile(FORGE_RUNTIME / 'eula.txt', SERVER / 'eula.txt')
    (SERVER / 'mods').mkdir()
    manifest = json.loads((DEVELOPMENT / 'docs/economie/etape-4/build-manifest.json').read_text())
    updates = {'MedievalCoins': '1.0.44', 'NpcShopkeeper': '1.0.34'}
    for entry in manifest:
        jar = Path(entry['jar'])
        if entry['mod'] in updates:
            version = updates[entry['mod']]
            jar = jar.with_name(jar.name.replace(entry['version'], version))
            entry.update(version=version, jar=str(jar), bytes=jar.stat().st_size,
                         sha256=hashlib.sha256(jar.read_bytes()).hexdigest())
        elif hashlib.sha256(jar.read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError(f'Unexpected artifact: {jar.name}')
        shutil.copyfile(jar, SERVER / 'mods' / jar.name)
    config = SERVER / 'config/medieval_coins/server_config.json'
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({'apiUrl': f'http://127.0.0.1:{api_port}', 'apiKey': 'fixture-key',
                                 'apiRetryCount': 0}), encoding='ascii')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    (SERVER / 'server.properties').write_text(
        f'server-ip=127.0.0.1\nserver-port={port}\nlevel-name=phase5-fixture\n'
        'level-type=minecraft:flat\nlevel-seed=20261105\nview-distance=3\n'
        'simulation-distance=3\nenable-query=false\nenable-rcon=false\n'
        'online-mode=true\nwhite-list=true\nspawn-protection=0\n', encoding='ascii')
    seed_old_inn()
    return manifest


class Server:
    def __init__(self, run):
        self.lines = queue.Queue()
        self.log = (HERE / f'forge-run-{run}.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen(
            [str(JAVA), '-Xmx3G', '-Dfile.encoding=UTF-8', '@' + FORGE_ARGS.as_posix(), 'nogui'],
            cwd=SERVER, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.reader = threading.Thread(target=self.read_output, daemon=True)
        self.reader.start()

    def read_output(self):
        for line in self.process.stdout:
            self.log.write(line)
            self.log.flush()
            self.lines.put(line)

    def expect(self, fragment, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self.lines.get(timeout=0.5)
            except queue.Empty:
                if self.process.poll() is not None:
                    break
            else:
                if fragment in line:
                    return line.strip()
        raise RuntimeError(f'Missing console result {fragment!r} in {self.log.name}')

    def command(self, command):
        self.process.stdin.write(command + '\n')
        self.process.stdin.flush()

    def close(self):
        try:
            if self.process.poll() is None:
                self.command('stop')
                self.process.wait(timeout=45)
        finally:
            if self.process.poll() is None:
                self.process.kill()
                self.process.wait(timeout=10)
            self.reader.join(timeout=5)
            self.log.close()


def run_rehearsal(manifest):
    results = []
    first = Server(1)
    try:
        results.append(first.expect('Done (', timeout=180))
        first.command('forceload add 0 0')
        first.expect('Marked chunk')
        stack = '{Slot:0,id:"minecraft:iron_sword",Count:1b,tag:{RepairCost:7}}'
        first.command('setblock 1 80 1 medieval_coins:merchant_counter{CommerceStockMirror:0b,PendingOwnerBalanceInIron:128L,PlayerMarketInventory:{Size:54,Items:[' + stack + ']}}')
        first.expect('Changed the block')
        first.command('setblock 3 80 1 medieval_coins:merchant_counter{CommerceStockMirror:1b,CommerceStock:{"0":1},PlayerMarketInventory:{Size:54,Items:[' + stack + ']}}')
        first.expect('Changed the block')
        inn_id = check_inn(first)
    finally:
        first.close()
    second = Server(2)
    try:
        results.append(second.expect('Done (', timeout=180))
        second.command('data get block 1 80 1 PendingOwnerBalanceInIron')
        results.append(second.expect('128L'))
        second.command('data get block 1 80 1 PlayerMarketInventory.Items[0].tag.RepairCost')
        results.append(second.expect('block data: 7'))
        second.command('setblock 3 80 1 air')
        second.expect('Changed the block')
        second.command('execute unless entity @e[type=minecraft:item,nbt={Item:{id:"minecraft:iron_sword"}}] run say FIXTURE_MIRROR_NO_DROP')
        results.append(second.expect('FIXTURE_MIRROR_NO_DROP'))
        second.command('setblock 1 80 1 air')
        second.expect('Changed the block')
        second.command('execute if entity @e[type=minecraft:item,nbt={Item:{id:"minecraft:iron_sword",Count:1b,tag:{RepairCost:7}}}] run say FIXTURE_LEGACY_NBT_RECOVERED')
        results.append(second.expect('FIXTURE_LEGACY_NBT_RECOVERED'))
        second.command('economie diagnostic')
        results.append(second.expect('Sauvegarde'))
        second.command('forge tps')
        results.append(second.expect('Overall:'))
        assert check_inn(second) == inn_id
        results.append('Legacy inn balance and room debt preserved; stable EconomyId across restart.')
    finally:
        second.close()
    for run in (1, 2):
        log = (HERE / f'forge-run-{run}.log').read_text(encoding='utf-8')
        for failure in ('Could not find parent com/google/gson', 'NoClassDefFoundError', 'Failed to start the minecraft server'):
            assert failure not in log, failure
    assert FixtureApi.calls['/npcs/list/'] >= 2
    assert FixtureApi.calls['/npcs/spawns/list/'] >= 2
    (HERE / 'forge-report.json').write_text(json.dumps({
        'fixture': True, 'forge': '47.4.3', 'minecraft': '1.20.1',
        'mods': [{key: row[key] for key in ('mod', 'version', 'sha256')} for row in manifest],
        'observations': results, 'synthetic_api_calls': dict(FixtureApi.calls),
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    (HERE / 'build-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    print('\n'.join(results))


if __name__ == '__main__':
    with ThreadingHTTPServer(('127.0.0.1', 0), FixtureApi) as api:
        worker = threading.Thread(target=api.serve_forever, daemon=True)
        worker.start()
        try:
            run_rehearsal(prepare_server(api.server_port))
        finally:
            api.shutdown()
