import fr.renblood.npcshopkeeper.manager.data.RuntimeDataCache;
import fr.renblood.npcshopkeeper.manager.server.OnServerStartedManager;
import fr.renblood.npcshopkeeper.data.io.*;
import fr.renblood.npcshopkeeper.data.trade.*;
import fr.renblood.npcshopkeeper.data.npc.TradeNpc;
import net.minecraft.core.BlockPos;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

public class NpcDataChecks {
    static void check(boolean condition, String message) { if (!condition) throw new AssertionError(message); }
    static JsonRepository<Trade> trades() { return new JsonRepository<>(Path.of(OnServerStartedManager.PATH), "trades", Trade::fromJson, Trade::toJson); }
    static JsonRepository<TradeHistory> histories() { return new JsonRepository<>(Path.of(OnServerStartedManager.PATH_HISTORY), "history", TradeHistory::fromJson, TradeHistory::toJson); }
    static JsonRepository<TradeNpc> npcs() { return new JsonRepository<>(Path.of(OnServerStartedManager.PATH_NPCS), "npcs", TradeNpc::fromJson, TradeNpc::toJson); }
    static Trade trade(String name, String category) { return new Trade(name,category,List.of(),null); }
    static void paths(Path world) throws Exception {
        Files.createDirectories(world);
        OnServerStartedManager.PATH=world.resolve("trade.json").toString();
        OnServerStartedManager.PATH_NPCS=world.resolve("npcs.json").toString();
        OnServerStartedManager.PATH_HISTORY=world.resolve("history.json").toString();
        trades().saveAll(List.of());npcs().saveAll(List.of());histories().saveAll(List.of());
    }
    static void immutableSnapshotsAndHotReads(String id) {
        trades().saveAll(List.of(trade("iron","INDUSTRIE"),trade("bread","food")));
        npcs().saveAll(List.of(new TradeNpc(id,"Ada",Map.of(),"food",new BlockPos(0,64,0))));
        JsonRepository.invalidateAll();RuntimeDataCache.reset();
        check(RuntimeDataCache.getTrade("iron")!=null,"Missing trade");
        check(RuntimeDataCache.getNpc(UUID.fromString(id))!=null,"Missing NPC");
        check(RuntimeDataCache.getOpenHistory(id).isEmpty(),"Unexpected open history");
        long reads=JsonFileManager.getReadCount(),builds=RuntimeDataCache.indexBuildCount();
        for (int i=0;i<1000;i++) {
            RuntimeDataCache.getTrade("iron");RuntimeDataCache.getTradesByCategory("food");
            RuntimeDataCache.getNpc(UUID.fromString(id));RuntimeDataCache.getNpc(new UUID(0,0));RuntimeDataCache.getOpenHistory(id);
        }
        check(JsonFileManager.getReadCount()==reads,"Warm interactions reread JSON");
        check(RuntimeDataCache.indexBuildCount()==builds,"Warm interactions rebuilt indexes");
        var snapshot=trades().snapshot();check(snapshot==trades().snapshot(),"Snapshot copied on each read");
        trades().loadAll().clear();check(trades().snapshot().size()==2,"Mutable loadAll modified repository");
        try { RuntimeDataCache.getTradesByCategory("food").clear();throw new AssertionError("Mutable category list"); }
        catch (UnsupportedOperationException expected) { }
        Locale before=Locale.getDefault();
        try { Locale.setDefault(Locale.forLanguageTag("tr-TR"));check(RuntimeDataCache.getTradesByCategory("INDUSTRIE").size()==1,"Locale-dependent category"); }
        finally {Locale.setDefault(before);}
    }
    static void writesAndHistory(String npc) {
        var snapshot=trades().snapshot();snapshot.get(0).setName("steel");trades().saveAll(snapshot);
        check(RuntimeDataCache.getTrade("steel")!=null && RuntimeDataCache.getTrade("iron")==null,"Saving immutable snapshot left stale index");
        TradeHistory first=new TradeHistory(List.of("tester"),"steel",false,"first",List.of(),1,npc,"Ada");
        TradeHistory abandoned=new TradeHistory(List.of("tester"),"steel",false,true,"abandoned",List.of(),1,npc,"Ada");
        histories().saveAll(List.of(abandoned,first));
        check(RuntimeDataCache.getOpenHistory(npc).orElseThrow().getId().equals("first"),"Abandoned history resumed");
        first.setFinished(true);
        check(RuntimeDataCache.getOpenHistory(npc).isEmpty(),"Mutable finished flag ignored");
        histories().saveAll(List.of(abandoned,first));
        histories().add(new TradeHistory(List.of("tester"),"steel",false,"next",List.of(),1,npc,"Ada"));
        check(RuntimeDataCache.getOpenHistory(npc).orElseThrow().getId().equals("next"),"New history not indexed after add");
        check(RuntimeDataCache.getHistory("first").isFinished(),"History ID lookup stale");
        npcs().saveAll(List.of());check(RuntimeDataCache.getNpc(UUID.fromString(npc))==null,"Removed NPC retained in index");
    }
    static void directEditAndWorldSwitch(Path root, String id) throws Exception {
        JsonObject object=new JsonObject();JsonArray rows=new JsonArray();rows.add(trade("edited","food").toJson());object.add("trades",rows);
        Files.writeString(Path.of(OnServerStartedManager.PATH),object.toString());
        JsonRepository.invalidate(Path.of(OnServerStartedManager.PATH));
        check(RuntimeDataCache.getTrade("edited")!=null && RuntimeDataCache.getTrade("steel")==null,"Explicit invalidation left stale catalog");
        paths(root.resolve("world-b"));
        trades().saveAll(List.of(trade("other-world","food")));
        npcs().saveAll(List.of(new TradeNpc(id,"Bea",Map.of(),"food",new BlockPos(1,64,0))));
        check(RuntimeDataCache.getTrade("edited")==null && RuntimeDataCache.getTrade("other-world")!=null,"Trade cache leaked across worlds");
        check(RuntimeDataCache.getNpc(UUID.fromString(id)).getNpcName().equals("Bea"),"NPC cache leaked across worlds");
        check(RuntimeDataCache.getHistory("next")==null,"History cache leaked across worlds");
    }
    static void concurrentLoadsAndPublication() throws Exception {
        var repo=trades();repo.saveAll(List.of(trade("one","food")));
        JsonRepository.invalidate(Path.of(OnServerStartedManager.PATH));long reads=JsonFileManager.getReadCount();
        var pool=Executors.newFixedThreadPool(8);
        try {
            var start=new CountDownLatch(1);List<Future<List<Trade>>> futures=new ArrayList<>();
            for(int i=0;i<8;i++)futures.add(pool.submit(()->{start.await();return repo.snapshot();}));
            start.countDown();var first=futures.get(0).get();
            for(var future:futures)check(first==future.get(),"Concurrent reads did not share snapshot");
            check(JsonFileManager.getReadCount()==reads+1,"Concurrent misses reread the same file");
            List<Trade> small=new ArrayList<>(),large=new ArrayList<>();
            for(int i=0;i<50;i++)small.add(trade("s"+i,"food"));for(int i=0;i<80;i++)large.add(trade("l"+i,"food"));
            repo.saveAll(small);RuntimeDataCache.getTradesByCategory("food");
            var gate=new CountDownLatch(1);List<Future<?>> readers=new ArrayList<>();
            for(int i=0;i<4;i++)readers.add(pool.submit(()->{gate.await();for(int j=0;j<1000;j++){
                int size=RuntimeDataCache.getTradesByCategory("food").size();check(size==50||size==80,"Partial catalog published");
            }return null;}));
            gate.countDown();for(int i=0;i<20;i++)repo.saveAll(i%2==0?large:small);
            for(var reader:readers)reader.get();
        } finally {pool.shutdownNow();}
    }
    static void failedReadsAndNullRows(Path root) throws Exception {
        Path file=root.resolve("invalid.json");Files.writeString(file,"{}");
        var repo=new JsonRepository<JsonObject>(file,"rows",json->json,json->json);
        check(repo.snapshot().isEmpty(),"Invalid root not empty");
        Files.writeString(file,"{\"rows\":[{\"id\":1}]}");
        check(repo.snapshot().size()==1,"Failed root cached as valid empty collection");
        Path nullable=root.resolve("nullable.json");Files.writeString(nullable,"{\"rows\":[{},{}]}");
        var filtered=new JsonRepository<JsonObject>(nullable,"rows",json->null,json->json);
        check(filtered.snapshot().isEmpty(),"Null deserialization retained");
    }
    static void failedWritesAndConcurrentAdds(Path root) throws Exception {
        Path file=root.resolve("checked-writes.json");
        var repo=new JsonRepository<Trade>(file,"trades",Trade::fromJson,Trade::toJson);
        repo.saveAll(List.of(trade("confirmed","food")));
        var edited=repo.snapshot();edited.get(0).setName("unsaved");
        var invalid=new JsonRepository<Trade>(file,"trades",Trade::fromJson,row->{throw new IllegalArgumentException("Forced serializer failure");});
        try {invalid.saveAll(edited);throw new AssertionError("Serializer failure swallowed");}
        catch(IllegalArgumentException expected){}
        check(repo.snapshot().get(0).getName().equals("confirmed"),"Mutated failed save remained cached");

        Path backup=root.resolve("last-confirmed.json");byte[] bytes=Files.readAllBytes(file);
        Files.move(file,backup);Files.createDirectory(file);Files.writeString(file.resolve("keep"),"owned temporary fixture");
        long writes=JsonFileManager.getWriteCount();
        try {
            try{repo.saveAll(List.of(trade("not-saved","food")));throw new AssertionError("IO failure swallowed");}
            catch(java.io.UncheckedIOException expected){}
            check(JsonFileManager.getWriteCount()==writes,"Failed save counted as success");
            try(var remaining=Files.list(root)) {check(remaining.noneMatch(p->p.getFileName().toString().startsWith("checked-writes.json.")&&p.toString().endsWith(".tmp")),"Failed write left temporary file");}
        } finally {Files.delete(file.resolve("keep"));Files.delete(file);Files.move(backup,file);}
        check(Arrays.equals(Files.readAllBytes(file),bytes),"Last confirmed document changed");
        check(repo.snapshot().get(0).getName().equals("confirmed"),"Unconfirmed collection published after IO failure");

        Path concurrent=root.resolve("concurrent-adds.json");
        var additions=new JsonRepository<Trade>(concurrent,"trades",Trade::fromJson,Trade::toJson);additions.saveAll(List.of());
        var pool=Executors.newFixedThreadPool(8);
        try {
            var start=new CountDownLatch(1);List<Future<?>> futures=new ArrayList<>();
            for(int i=0;i<32;i++){final int id=i;futures.add(pool.submit(()->{start.await();additions.add(trade("offer-"+id,"food"));return null;}));}
            start.countDown();for(var future:futures)future.get();
        } finally {pool.shutdownNow();}
        check(additions.snapshot().size()==32&&additions.snapshot().stream().map(Trade::getName).distinct().count()==32,"Concurrent append lost entries");
        JsonRepository.invalidate(concurrent);check(additions.snapshot().size()==32,"Concurrent append cache differs from disk");

        Path update=root.resolve("edit.json");Files.writeString(update,"{\"schema\":7,\"trades\":[]}");
        JsonFileManager.updateJsonFile(update.toString(),object->object.getAsJsonArray("trades").add(trade("new","food").toJson()));
        var result=JsonParser.parseString(Files.readString(update)).getAsJsonObject();
        check(result.get("schema").getAsInt()==7&&result.getAsJsonArray("trades").size()==1,"Edit dropped unrelated fields");
        Files.writeString(update,"[]");String before=Files.readString(update);
        try {JsonFileManager.updateJsonFile(update.toString(),object->object.add("trades",new JsonArray()));throw new AssertionError("Invalid document replaced");}
        catch(java.io.IOException expected){}
        check(Files.readString(update).equals(before),"Invalid existing document overwritten");
        try {JsonFileManager.writeJsonFileOrThrow(null,new JsonObject());throw new AssertionError("Null path acknowledged");}
        catch(java.io.IOException expected){}
    }

    static void refuseAppendToPartialDocument(Path root) throws Exception {
        Path file=root.resolve("partial-trades.json");
        JsonObject object=new JsonObject();JsonArray rows=new JsonArray();rows.add(trade("valid","food").toJson());rows.add("unreadable row");object.add("trades",rows);
        Files.writeString(file,object.toString());String before=Files.readString(file);
        var repo=new JsonRepository<Trade>(file,"trades",Trade::fromJson,Trade::toJson);
        check(repo.snapshot().size()==1,"Valid rows not available for diagnosis");
        try {repo.add(trade("would-drop-invalid","food"));throw new AssertionError("Append discarded malformed rows");}
        catch(java.io.UncheckedIOException expected){}
        check(Files.readString(file).equals(before),"Partial document overwritten");
        Path invalid=root.resolve("invalid-append.json");Files.writeString(invalid,"{}");
        var invalidRepo=new JsonRepository<Trade>(invalid,"trades",Trade::fromJson,Trade::toJson);
        try {invalidRepo.add(trade("not-saved","food"));throw new AssertionError("Invalid root accepted for append");}
        catch(java.io.UncheckedIOException expected){}
        check(Files.readString(invalid).equals("{}"),"Invalid root overwritten by append");
    }

    static void cachePublicationFollowsWritesAndReset(Path root) throws Exception {
        Path file=root.resolve("loading-race.json");
        var initial=new JsonRepository<Trade>(file,"trades",Trade::fromJson,Trade::toJson);initial.saveAll(List.of(trade("old","food")));JsonRepository.invalidate(file);
        var entered=new CountDownLatch(1);var release=new CountDownLatch(1);
        var slow=new JsonRepository<Trade>(file,"trades",json->{entered.countDown();try{release.await();}catch(InterruptedException e){throw new IllegalStateException(e);}return Trade.fromJson(json);},Trade::toJson);
        var pool=Executors.newFixedThreadPool(2);
        try {
            var loading=pool.submit(slow::snapshot);entered.await();var writerStarted=new CountDownLatch(1);var committed=new CountDownLatch(1);
            var writing=pool.submit(()->{writerStarted.countDown();JsonFileManager.updateJsonFile(file.toString(),object->{var rows=new JsonArray();rows.add(trade("latest","food").toJson());object.add("trades",rows);});committed.countDown();return null;});
            writerStarted.await();check(!committed.await(100,TimeUnit.MILLISECONDS),"Writer bypassed in-progress snapshot load");
            release.countDown();loading.get();writing.get();
            check(initial.snapshot().get(0).getName().equals("latest"),"Old cache load overwrote newer file publication");
        } finally {release.countDown();pool.shutdownNow();}

        JsonRepository.invalidate(file);var blocked=new CountDownLatch(1);var resume=new CountDownLatch(1);
        var resetReader=new JsonRepository<Trade>(file,"trades",json->{blocked.countDown();try{resume.await();}catch(InterruptedException e){throw new IllegalStateException(e);}return Trade.fromJson(json);},Trade::toJson);
        var single=Executors.newSingleThreadExecutor();long reads=JsonFileManager.getReadCount();
        try {var loading=single.submit(resetReader::snapshot);blocked.await();JsonRepository.invalidateAll();resume.countDown();loading.get();initial.snapshot();
            check(JsonFileManager.getReadCount()==reads+2,"Global reset accepted a snapshot loaded before reset");
        } finally {resume.countDown();single.shutdownNow();}
    }

    public static void main(String[] args) throws Exception {
        Path root=Path.of(args[0]);String npc=UUID.randomUUID().toString();paths(root.resolve("world-a"));
        immutableSnapshotsAndHotReads(npc);writesAndHistory(npc);directEditAndWorldSwitch(root,npc);
        concurrentLoadsAndPublication();failedReadsAndNullRows(root);failedWritesAndConcurrentAdds(root);refuseAppendToPartialDocument(root);cachePublicationFollowsWritesAndReset(root);
        System.out.println("NPC data: hot reads, immutable snapshots, invalidation, histories, locale, world switch, concurrent publication, failed writes and 32 concurrent appends passed.");
    }
}
