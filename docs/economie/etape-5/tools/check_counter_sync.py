"""Run the production counter sync coordinator against a deterministic fake server/API.

No Minecraft process or remote request. javac uses the production coordinator and
its acknowledgement/comparison methods; dependencies are small in-memory fixtures.
This checks async ordering and retry behavior, not rendering or Forge lifecycle.
"""
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[4]
sources = root / 'mods/CoinMod2025/MedievalCoins/src/main/java'
prefix = 'fr/renblood/medievalcoins/'
block = (sources / prefix / 'market/counter/MerchantCounterBlockEntity.java').read_text(encoding='utf-8')


def method(name, source=block):
    found = re.search(r'^    (?:public|private) (?:static )?[^\n]*\b' + re.escape(name) + r'\(', source, re.M)
    if found is None:
        raise RuntimeError(f'Méthode introuvable : {name}')
    start = found.start()
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


fixtures = {
    'net/minecraft/server/MinecraftServer.java': '''package net.minecraft.server;
import java.util.*;
public class MinecraftServer {
    private final Queue<Runnable> queue = new ArrayDeque<>();
    public void execute(Runnable action) { queue.add(action); }
    public void pump() { while (!queue.isEmpty()) queue.remove().run(); }
}''',
    prefix + 'MedievalCoin.java': '''package fr.renblood.medievalcoins;
public class MedievalCoin {
    public static final Log LOGGER = new Log();
    public static class Log { public void warn(String message, Object... args) { } }
}''',
    prefix + 'market/service/MarketSyncService.java': '''package fr.renblood.medievalcoins.market.service;
public class MarketSyncService { public static void recordBackendReachable(boolean value) { } }''',
    prefix + 'market/counter/CounterItemConfigData.java': '''package fr.renblood.medievalcoins.market.counter;
public record CounterItemConfigData(String itemId, String displayName) { }''',
    prefix + 'market/service/MerchantCounterRegistry.java': '''package fr.renblood.medievalcoins.market.service;
import java.util.*;
import fr.renblood.medievalcoins.market.counter.MerchantCounterBlockEntity;
public class MerchantCounterRegistry {
    public static final Map<String,MerchantCounterBlockEntity> data = new HashMap<>();
    public static MerchantCounterBlockEntity findLoaded(String id) { return data.get(id); }
    public static List<MerchantCounterBlockEntity> loaded() { return List.copyOf(data.values()); }
    public static void idChanged(String old, MerchantCounterBlockEntity row) { data.remove(old); data.put(row.getCounterId(),row); }
}''',
    prefix + 'market/service/MerchantCounterLocalStore.java': '''package fr.renblood.medievalcoins.market.service;
import java.util.*;
import fr.renblood.medievalcoins.market.model.MerchantCounterDto;
public class MerchantCounterLocalStore {
    public static final Map<String,Entry> data = new HashMap<>();
    public static class Entry { public MerchantCounterDto counter; public boolean pendingSync, pendingCreate; }
    public static List<Entry> entries() { return List.copyOf(data.values()); }
    public static void remember(MerchantCounterDto value, boolean pending, boolean create) {
        Entry entry = new Entry(); entry.counter=value; entry.pendingSync=pending; entry.pendingCreate=create; data.put(value.counterId,entry);
    }
    public static void markSynced(String id, MerchantCounterDto backend) { data.remove(id); remember(backend,false,false); }
    public static void remove(String id) { data.remove(id); }
''' + method('markSyncedIfUnchanged', (sources / prefix / 'market/service/MerchantCounterLocalStore.java').read_text(encoding='utf-8')).replace('load().counters', 'data') + '\n}',
    prefix + 'market/counter/MerchantCounterBlockEntity.java': '''package fr.renblood.medievalcoins.market.counter;
import java.util.*;
import fr.renblood.medievalcoins.market.model.MerchantCounterDto;
import fr.renblood.medievalcoins.market.service.*;
import net.minecraft.server.MinecraftServer;
public class MerchantCounterBlockEntity {
    private String counterId;
    private boolean pendingSync, pendingCreate;
    private long syncRevision;
    public MerchantCounterDto value = new MerchantCounterDto();
    public List<CounterItemConfigData> items = List.of();
    public Set<String> removed = Set.of();
    public boolean dirtyItems;
    private final Level level;
    public record Level(MinecraftServer server) { public MinecraftServer getServer() { return server; } }
    public MerchantCounterBlockEntity(MinecraftServer server, String id) { level=new Level(server); counterId=id; value.name="initial"; }
    public Level getLevel() { return level; }
    public boolean isRemoved() { return false; }
    public String getCounterId() { return counterId; }
    public boolean isPendingCreate() { return pendingCreate; }
    public boolean isPendingSync() { return pendingSync; }
    public long getSyncRevision() { return syncRevision; }
    public MerchantCounterDto toDto() {
        MerchantCounterDto dto = new MerchantCounterDto(); dto.counterId=counterId; dto.name=value.name;
        return dto;
    }
    private void apply(MerchantCounterDto dto) { value=dto; counterId=dto.counterId; }
    private void changed() { syncRevision++; MerchantCounterLocalStore.remember(toDto(),pendingSync,pendingCreate); }
    public void edit(String name) { value.name=name; }
    public void editItems(List<CounterItemConfigData> next, Set<String> deleted) { items=next;removed=deleted;dirtyItems=true;changed(); }
    public List<CounterItemConfigData> getConfiguredItems() { return items; }
    public Set<String> getRemovedItemIds() { return removed; }
    public boolean isItemsPendingSync() { return dirtyItems; }
    public void markItemsSynced() { dirtyItems=false;removed=Set.of();changed(); }
    public void applyBackendItems(List<CounterItemConfigData> next) { if(!dirtyItems) {items=next;changed();} }
''' + '\n'.join(method(name) for name in ['markPending', 'applyUploadSynced', 'applyBackendSynced', 'applyBackendValue', 'sameConfiguration']) + '\n}',
    prefix + 'market/service/MarketApiService.java': '''package fr.renblood.medievalcoins.market.service;
import java.util.*;
import java.util.concurrent.*;
import fr.renblood.medievalcoins.market.model.MerchantCounterDto;
import fr.renblood.medievalcoins.market.counter.CounterItemConfigData;
public class MarketApiService {
    public record Write(MerchantCounterDto sent, boolean create, CompletableFuture<MerchantCounterDto> future) { }
    public record ItemWrite(String id, String deleted, CompletableFuture<Void> future) { }
    public static final List<Write> writes = new ArrayList<>();
    public static final List<ItemWrite> itemWrites = new ArrayList<>();
    public static final List<CompletableFuture<List<MerchantCounterDto>>> reads = new ArrayList<>();
    public static final List<CompletableFuture<List<CounterItemConfigData>>> itemReads = new ArrayList<>();
    private static CompletableFuture<MerchantCounterDto> write(MerchantCounterDto dto, boolean create) {
        var future = new CompletableFuture<MerchantCounterDto>(); writes.add(new Write(dto,create,future));return future;
    }
    public static CompletableFuture<MerchantCounterDto> createCounter(MerchantCounterDto dto) { return write(dto,true); }
    public static CompletableFuture<MerchantCounterDto> updateCounter(MerchantCounterDto dto) { return write(dto,false); }
    public static CompletableFuture<List<MerchantCounterDto>> fetchCounters() { var future=new CompletableFuture<List<MerchantCounterDto>>();reads.add(future);return future; }
    public static CompletableFuture<List<CounterItemConfigData>> fetchCounterItems(String id) { var future=new CompletableFuture<List<CounterItemConfigData>>();itemReads.add(future);return future; }
    public static CompletableFuture<Void> upsertCounterItem(String id, CounterItemConfigData item) { var f=new CompletableFuture<Void>();itemWrites.add(new ItemWrite(item.itemId(),null,f));return f; }
    public static CompletableFuture<Void> deleteCounterItem(String id, String item) { var f=new CompletableFuture<Void>();itemWrites.add(new ItemWrite(null,item,f));return f; }
}''',
    'CounterSyncChecks.java': '''import java.util.*;
import fr.renblood.medievalcoins.market.counter.*;
import fr.renblood.medievalcoins.market.service.*;
import net.minecraft.server.MinecraftServer;

public class CounterSyncChecks {
    static void check(boolean condition, String message) { if(!condition) throw new AssertionError(message); }
    static MerchantCounterBlockEntity counter(MinecraftServer server, String id) {
        var c = new MerchantCounterBlockEntity(server,id); MerchantCounterRegistry.data.put(id,c);
        MerchantCounterLocalStore.remember(c.toDto(),false,false); return c;
    }
    static void reset() { MerchantCounterRegistry.data.clear();MerchantCounterLocalStore.data.clear();MarketApiService.writes.clear();MarketApiService.reads.clear();MarketApiService.itemReads.clear();MarketApiService.itemWrites.clear(); }
    static void ack(MinecraftServer s,int n) {var w=MarketApiService.writes.get(n);w.future().complete(w.sent());s.pump();}
    static void coalescedCreate() {
        reset();var s=new MinecraftServer();var c=counter(s,"create");
        MerchantCounterSyncService.counterPlaced(c);
        c.edit("second");MerchantCounterSyncService.counterModified(c);
        c.edit("latest");MerchantCounterSyncService.counterModified(c);
        c.editItems(List.of(new CounterItemConfigData("minecraft:stone","deferred")),Set.of());
        MerchantCounterSyncService.itemsModified(c);
        check(MarketApiService.itemWrites.isEmpty(),"items published before counter creation");
        check(MarketApiService.writes.size()==1,"parallel writes while creating");
        ack(s,0);
        check(c.value.name.equals("latest") && c.isPendingSync(),"old create overwrote latest draft");
        check(MarketApiService.writes.size()==2 && !MarketApiService.writes.get(1).create(),"latest edit not coalesced into update");
        check(MarketApiService.itemWrites.isEmpty(),"items published before updated counter configuration");
        ack(s,1);check(!c.isPendingSync() && !c.isPendingCreate(),"latest acknowledgement not applied");
        check(MarketApiService.itemWrites.size()==1,"deferred items never sent");
        MarketApiService.itemWrites.get(0).future().complete(null);s.pump();
        check(MerchantCounterLocalStore.data.containsKey("create"),"cache entry removed by unchanged ID");
    }
    static void periodicSharesWriteAndRetries() {
        reset();var s=new MinecraftServer();var c=counter(s,"retry");
        c.edit("new");MerchantCounterSyncService.counterModified(c);
        var sync=MerchantCounterSyncService.syncAll(s);s.pump();
        check(MarketApiService.writes.size()==1,"manual sync duplicated in-flight update");
        MarketApiService.writes.get(0).future().completeExceptionally(new RuntimeException("offline"));s.pump();
        MarketApiService.reads.get(0).completeExceptionally(new RuntimeException("offline"));s.pump();
        check(sync.join().errors()==2 && c.isPendingSync(),"failure discarded dirty configuration");
        var retry=MerchantCounterSyncService.syncAll(s);s.pump();
        check(MarketApiService.writes.size()==2,"failed write lane never released");
        ack(s,1);MarketApiService.reads.get(1).complete(List.of(c.toDto()));s.pump();
        check(retry.join().errors()==0 && !c.isPendingSync(),"periodic retry failed");
        MarketApiService.itemReads.get(0).complete(List.of());s.pump();
    }
    static void staleReads() {
        reset();var s=new MinecraftServer();var c=counter(s,"reads");var old=c.toDto();
        var sync=MerchantCounterSyncService.syncAll(s);s.pump();
        c.edit("latest");MerchantCounterSyncService.counterModified(c);ack(s,0);
        MarketApiService.reads.get(0).complete(List.of(old));s.pump();
        check(sync.join().updated()==0 && c.value.name.equals("latest"),"late fetch overwrote acknowledged update");
        var latest=new CounterItemConfigData("minecraft:stone","latest");
        c.editItems(List.of(latest),Set.of());MerchantCounterSyncService.itemsModified(c);
        MarketApiService.itemWrites.get(0).future().complete(null);s.pump();
        MarketApiService.itemReads.get(0).complete(List.of(new CounterItemConfigData("minecraft:stone","old")));s.pump();
        check(c.items.equals(List.of(latest)),"late item fetch overwrote acknowledged items");
    }
    static void itemBatches() {
        reset();var s=new MinecraftServer();var c=counter(s,"items");
        var first=new CounterItemConfigData("minecraft:stone","first");var last=new CounterItemConfigData("minecraft:bread","last");
        c.editItems(List.of(first),Set.of("minecraft:dirt"));MerchantCounterSyncService.itemsModified(c);
        c.editItems(List.of(last),Set.of("minecraft:stone"));MerchantCounterSyncService.itemsModified(c);
        check(MarketApiService.itemWrites.size()==2,"item edits sent concurrently");
        MarketApiService.itemWrites.get(0).future().complete(null);s.pump();
        check(c.dirtyItems,"partial batch cleared dirty state");
        MarketApiService.itemWrites.get(1).future().complete(null);s.pump();
        check(c.dirtyItems && MarketApiService.itemWrites.size()==4,"newer item batch lost");
        MarketApiService.itemWrites.get(2).future().complete(null);MarketApiService.itemWrites.get(3).future().complete(null);s.pump();
        check(!c.dirtyItems && c.items.equals(List.of(last)),"latest item batch not acknowledged");
        c.editItems(List.of(last),Set.of(last.itemId()));MerchantCounterSyncService.itemsModified(c);
        check(MarketApiService.itemWrites.size()==5,"re-added item was also deleted");
        MarketApiService.itemWrites.get(4).future().completeExceptionally(new RuntimeException("offline"));s.pump();
        check(c.dirtyItems,"item failure discarded draft");
        MerchantCounterSyncService.itemsModified(c);MarketApiService.itemWrites.get(5).future().complete(null);s.pump();
        check(!c.dirtyItems,"item failure lane never released");
    }
    static void unloadAndReload() {
        reset();var s=new MinecraftServer();var original=counter(s,"unload");
        MerchantCounterSyncService.counterModified(original);
        MerchantCounterRegistry.data.remove("unload");
        var newer=original.toDto();newer.name="offline draft";MerchantCounterLocalStore.remember(newer,true,false);
        ack(s,0);
        check(MerchantCounterLocalStore.data.get("unload").pendingSync,"unloaded edited entry falsely acknowledged");
        check(MerchantCounterLocalStore.data.get("unload").counter.name.equals("offline draft"),"unloaded edit overwritten");
        var retry=MerchantCounterSyncService.syncAll(s);s.pump();ack(s,1);
        MarketApiService.reads.get(0).complete(List.of());s.pump();
        check(!MerchantCounterLocalStore.data.get("unload").pendingSync && retry.join().errors()==0,"offline snapshot did not sync");
        reset();var previous=counter(s,"reload");MerchantCounterSyncService.counterModified(previous);
        var reloaded=counter(s,"reload");reloaded.edit("reloaded draft");reloaded.markPending(false);ack(s,0);
        check(reloaded.value.name.equals("reloaded draft") && MarketApiService.writes.size()==2,"reload draft replaced by old block response");
        ack(s,1);
    }
    static void staleReadAfterReload() {
        reset();var s=new MinecraftServer();var before=counter(s,"reload-fetch");var old=before.toDto();old.name="obsolete";
        var sync=MerchantCounterSyncService.syncAll(s);s.pump();
        var reloaded=counter(s,"reload-fetch");reloaded.edit("persisted draft");
        check(reloaded.getSyncRevision()==before.getSyncRevision(),"fixture did not reproduce reset revision");
        MarketApiService.reads.get(0).complete(List.of(old));s.pump();
        check(sync.join().updated()==0 && reloaded.value.name.equals("persisted draft"),"stale read accepted for another block instance");
        MarketApiService.itemReads.get(0).complete(List.of());s.pump();
    }
    public static void main(String[] args) {
        coalescedCreate();periodicSharesWriteAndRetries();staleReads();itemBatches();unloadAndReload();staleReadAfterReload();
        System.out.println("Counter sync: 6 deterministic scenarios passed (production coordinator + acknowledgements).");
    }
}''',
}

java_home = os.environ.get('JAVA_HOME')
javac = str(Path(java_home) / 'bin/javac.exe') if java_home else shutil.which('javac')
java = str(Path(java_home) / 'bin/java.exe') if java_home else shutil.which('java')
if not javac or not java:
    raise RuntimeError('Configure JAVA_HOME avec un JDK 17.')

with tempfile.TemporaryDirectory(prefix='renblood-counter-sync-') as directory:
    target = Path(directory)
    paths = []
    for relative, content in fixtures.items():
        file = target / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding='utf-8')
        paths.append(str(file))
    paths += [str(sources / prefix / relative) for relative in (
        'market/service/MerchantCounterSyncService.java', 'market/model/MerchantCounterDto.java',
        'market/model/CounterSyncResult.java')]
    subprocess.run([javac, '-encoding', 'UTF-8', '-d', directory, *paths], check=True)
    subprocess.run([java, '-cp', directory, 'CounterSyncChecks'], check=True)
