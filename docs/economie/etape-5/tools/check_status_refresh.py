"""Check the production status gate, feedback coordinator and HUD session reset.
The clock, API queue, network and Minecraft surfaces are simulated; no game starts.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project=Path(__file__).resolve().parents[4]
sources=project/'mods/CoinMod2025/MedievalCoins/src/main/java'
prefix='fr/renblood/medievalcoins/'
fixtures={
 'net/minecraft/server/MinecraftServer.java':"""package net.minecraft.server;import java.util.concurrent.*;public class MinecraftServer{private final Thread owner=Thread.currentThread();public final ConcurrentLinkedQueue<Runnable> queue=new ConcurrentLinkedQueue<>();public final Players players=new Players();public Players getPlayerList(){return players;}public static class Players{public final java.util.Map<java.util.UUID,net.minecraft.server.level.ServerPlayer> values=new java.util.HashMap<>();public net.minecraft.server.level.ServerPlayer getPlayer(java.util.UUID id){return values.get(id);}}public boolean isSameThread(){return Thread.currentThread()==owner;}public void execute(Runnable task){queue.add(task);}public void pump(){while(!queue.isEmpty())queue.remove().run();}}""",
 'net/minecraft/server/level/ServerPlayer.java':"""package net.minecraft.server.level;import net.minecraft.server.MinecraftServer;public class ServerPlayer{public final MinecraftServer server;private final String uuid;public boolean disconnected;public ServerPlayer(MinecraftServer server,String uuid){this.server=server;this.uuid=uuid;server.players.values.put(getUUID(),this);}public MinecraftServer getServer(){return server;}public String getStringUUID(){return uuid;}public java.util.UUID getUUID(){return java.util.UUID.nameUUIDFromBytes(uuid.getBytes(java.nio.charset.StandardCharsets.UTF_8));}public boolean hasDisconnected(){return disconnected;}@Override public boolean equals(Object other){return other instanceof ServerPlayer p&&uuid.equals(p.uuid);}@Override public int hashCode(){return uuid.hashCode();}}""",
 'net/minecraftforge/event/server/ServerStoppingEvent.java':'package net.minecraftforge.event.server;public record ServerStoppingEvent(net.minecraft.server.MinecraftServer server){public net.minecraft.server.MinecraftServer getServer(){return server;}}',
 'net/minecraftforge/eventbus/api/SubscribeEvent.java':'package net.minecraftforge.eventbus.api;public @interface SubscribeEvent{}',
 'net/minecraftforge/api/distmarker/Dist.java':'package net.minecraftforge.api.distmarker;public enum Dist{CLIENT,DEDICATED_SERVER}',
 'net/minecraftforge/fml/common/Mod.java':'package net.minecraftforge.fml.common;public class Mod{public @interface EventBusSubscriber{String modid() default "";net.minecraftforge.api.distmarker.Dist[] value() default {};}}',
 'net/minecraftforge/client/event/ClientPlayerNetworkEvent.java':'package net.minecraftforge.client.event;public class ClientPlayerNetworkEvent{public static class LoggingIn{}public static class LoggingOut{}}',
 'net/minecraftforge/network/PacketDistributor.java':'package net.minecraftforge.network;import java.util.function.*;import net.minecraft.server.level.ServerPlayer;public class PacketDistributor{public static final PacketDistributor PLAYER=new PacketDistributor();public Object with(Supplier<ServerPlayer> supplier){return supplier.get();}}',
 prefix+'MedievalCoin.java':"""package fr.renblood.medievalcoins;import java.util.*;import net.minecraft.server.level.ServerPlayer;import fr.renblood.medievalcoins.network.EconomyFeedbackMessage;public class MedievalCoin{public static final String MODID="medieval_coins";public static final Packets PACKET_HANDLER=new Packets();public record Sent(ServerPlayer player,EconomyFeedbackMessage message){}public static class Packets{public final List<Sent> sent=new ArrayList<>();public void send(Object target,EconomyFeedbackMessage message){var player=(ServerPlayer)target;if(!player.getServer().isSameThread())throw new AssertionError("Packet sent from worker");sent.add(new Sent(player,message));}public void sendToServer(Object message){}}}""",
 prefix+'network/EconomyFeedbackMessage.java':'package fr.renblood.medievalcoins.network;public record EconomyFeedbackMessage(String resource,String state,String detail,String value){}',
 prefix+'network/EconomyStatusRequestMessage.java':'package fr.renblood.medievalcoins.network;public record EconomyStatusRequestMessage(String business){}',
 prefix+'network/ApiExecutor.java':"""package fr.renblood.medievalcoins.network;import java.util.*;import java.util.concurrent.*;import java.util.function.*;public class ApiExecutor{public static final Queue<Runnable> jobs=new ArrayDeque<>();public static boolean reject;public static <T> CompletableFuture<T> supply(Supplier<T> supplier){if(reject)throw new RejectedExecutionException("Full test queue");var result=new CompletableFuture<T>();jobs.add(()->{try{result.complete(supplier.get());}catch(Throwable failure){result.completeExceptionally(failure);}});return result;}public static void runNext()throws Exception{Runnable job=jobs.remove();Thread worker=new Thread(job,"Fake status worker");worker.start();worker.join();}}""",
 prefix+'bank/CommerceProtocol.java':"""package fr.renblood.medievalcoins.bank;import java.util.*;public class CommerceProtocol{public static final List<String> calls=new ArrayList<>();public static boolean fail;public static String budget="120";public static class Value{private final String value;Value(String value){this.value=value;}public boolean isJsonNull(){return value==null;}public String getAsString(){return value;}}public static class Wire{public boolean has(String key){return key.equals("state")||key.equals("budget")&&budget!=null;}public Value get(String key){return new Value(key.equals("state")?"AVAILABLE":budget);}}public static Wire get(String uuid,String path)throws Exception{if(!Thread.currentThread().getName().equals("Fake status worker"))throw new AssertionError("HTTP on tick thread");calls.add(path);if(fail){fail=false;throw new java.io.IOException("Offline fixture");}return new Wire();}}""",
 'net/minecraft/Util.java':'package net.minecraft;public class Util{public static long getMillis(){return System.nanoTime()/1000000;}}',
 'net/minecraft/client/gui/Font.java':'package net.minecraft.client.gui;public class Font{public String plainSubstrByWidth(String s,int width){return s;}}',
 'net/minecraft/client/gui/GuiGraphics.java':'package net.minecraft.client.gui;public class GuiGraphics{public String lastText;public void fill(int a,int b,int c,int d,int color){}public void drawString(Font f,String text,int x,int y,int color,boolean shadow){lastText=text;}}',
 'net/minecraft/client/Minecraft.java':'package net.minecraft.client;public class Minecraft{private static final Minecraft INSTANCE=new Minecraft();public static Minecraft getInstance(){return INSTANCE;}public final net.minecraft.client.gui.Font font=new net.minecraft.client.gui.Font();public final Options options=new Options();public static class Options{public Value screenEffectScale(){return new Value();}}public static class Value{public Double get(){return 0.0;}}}',
 'StatusRefreshChecks.java':"""import fr.renblood.medievalcoins.bank.*;
import fr.renblood.medievalcoins.network.*;
import fr.renblood.medievalcoins.MedievalCoin;
import fr.renblood.medievalcoins.client.economy.EconomyHud;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.server.ServerStoppingEvent;
import java.util.concurrent.atomic.AtomicLong;

public class StatusRefreshChecks {
 static void check(boolean condition,String message){if(!condition)throw new AssertionError(message);}
 static void clearPackets(){MedievalCoin.PACKET_HANDLER.sent.clear();}
 static void gate(){
  var clock=new AtomicLong(100);var gate=new StatusRefreshGate<String>(2,10,clock::get);
  var a=gate.begin("a");var b=gate.begin("b");check(a!=null&&b!=null&&gate.begin("a")==null&&gate.begin("c")==null,"Duplicate or unbounded requests admitted");
  clock.addAndGet(1000);check(gate.begin("a")==null&&gate.begin("c")==null,"Running request evicted by age");
  check(gate.complete("a",a)&&!gate.complete("a",a),"Completion not single-use");
  check(gate.begin("a")==null,"Cooldown not applied after completion");
  clock.addAndGet(10);var next=gate.begin("a");check(next!=null&&!gate.complete("a",a),"Stale ticket applied to new request");
  gate.rejected("a",next);check(gate.begin("a")!=null,"Rejected request stuck");
  gate.removeIf(key->key.equals("b"));check(!gate.complete("b",b)&&gate.begin("b")!=null,"Removed request applied");
  var wrapClock=new AtomicLong(Long.MAX_VALUE-3);var wrap=new StatusRefreshGate<String>(1,10,wrapClock::get);var token=wrap.begin("x");wrap.complete("x",token);wrapClock.addAndGet(10);check(wrap.begin("x")!=null,"Monotonic clock overflow broke cooldown");
 }
 static void resourcesAndCoalescing()throws Exception{
  clearPackets();var server=new MinecraftServer();var player=new ServerPlayer(server,"one");
  EconomyFeedback.refresh(player,"market:a");EconomyFeedback.refresh(player,"inn:b");
  for(int i=0;i<100;i++)EconomyFeedback.refresh(player,"market:a");
  check(ApiExecutor.jobs.size()==2,"Different resources suppressed or duplicate backend work queued");
  ApiExecutor.runNext();server.pump();ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.size()==2,"Resources not delivered separately");
  check(MedievalCoin.PACKET_HANDLER.sent.get(0).message().resource().equals("market:a"),"Wrong first resource");
  check(MedievalCoin.PACKET_HANDLER.sent.get(1).message().value().equals("120"),"Budget value lost");
  EconomyFeedback.refresh(player,"market:a");check(ApiExecutor.jobs.isEmpty(),"Completed request immediately repeated");
  EconomyFeedback.onServerStopping(new ServerStoppingEvent(server));
 }
 static void rejectionAndFailure()throws Exception{
  clearPackets();var server=new MinecraftServer();var player=new ServerPlayer(server,"reject");ApiExecutor.reject=true;
  EconomyFeedback.refresh(player,"npc-contracts");check(ApiExecutor.jobs.isEmpty()&&MedievalCoin.PACKET_HANDLER.sent.get(0).message().state().equals("UNKNOWN"),"Queue rejection hidden");
  ApiExecutor.reject=false;CommerceProtocol.fail=true;EconomyFeedback.refresh(player,"npc-contracts");check(ApiExecutor.jobs.size()==1,"Rejected lane retained");ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.get(1).message().state().equals("UNKNOWN"),"Backend failure not delivered");
  EconomyFeedback.onServerStopping(new ServerStoppingEvent(server));EconomyFeedback.refresh(player,"npc-contracts");ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.get(2).message().state().equals("AVAILABLE"),"Failure prevented later refresh");
  EconomyFeedback.onServerStopping(new ServerStoppingEvent(server));
 }
 static void reconnectAndStop()throws Exception{
  clearPackets();var server=new MinecraftServer();var old=new ServerPlayer(server,"same-uuid");var current=new ServerPlayer(server,"same-uuid");
  check(old.equals(current),"Fixture must reproduce logical player equality");
  EconomyFeedback.refresh(old,"market:one");old.disconnected=true;EconomyFeedback.refresh(current,"market:one");
  check(ApiExecutor.jobs.size()==2,"Reconnect reused old session lane");ApiExecutor.runNext();server.pump();ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.size()==1&&MedievalCoin.PACKET_HANDLER.sent.get(0).player()==current,"Response delivered to disconnected session");
  clearPackets();EconomyFeedback.refresh(current,"inn:pending");EconomyFeedback.onServerStopping(new ServerStoppingEvent(server));ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.isEmpty(),"Stopped server applied old reply");
  var nextServer=new MinecraftServer();var nextPlayer=new ServerPlayer(nextServer,"same-uuid");CommerceProtocol.budget=null;
  EconomyFeedback.refresh(nextPlayer,"market:one");ApiExecutor.runNext();nextServer.pump();check(MedievalCoin.PACKET_HANDLER.sent.get(0).message().value().isEmpty(),"Missing budget not supported");CommerceProtocol.budget="120";
  EconomyFeedback.onServerStopping(new ServerStoppingEvent(nextServer));
 }
 static void respawnAndRemovedPlayer()throws Exception{
  clearPackets();var server=new MinecraftServer();var original=new ServerPlayer(server,"respawn");
  EconomyFeedback.refresh(original,"market:respawn");var replacement=new ServerPlayer(server,"respawn");
  EconomyFeedback.refresh(replacement,"market:respawn");ApiExecutor.runNext();server.pump();ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.size()==1&&MedievalCoin.PACKET_HANDLER.sent.get(0).player()==replacement,"Response from pre-respawn player applied to current connection");
  clearPackets();EconomyFeedback.refresh(replacement,"inn:removed");server.players.values.remove(replacement.getUUID());ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.isEmpty(),"Response applied after player list removal");EconomyFeedback.onServerStopping(new ServerStoppingEvent(server));
 }
 static void offThreadAndHud()throws Exception{
  clearPackets();var server=new MinecraftServer();var player=new ServerPlayer(server,"off-thread");
  var worker=new Thread(()->EconomyFeedback.refresh(player,"market:off-thread"));worker.start();worker.join();
  check(ApiExecutor.jobs.isEmpty(),"Off-thread refresh touched API before tick handoff");server.pump();ApiExecutor.runNext();server.pump();
  check(MedievalCoin.PACKET_HANDLER.sent.size()==1,"Tick handoff lost reply");EconomyFeedback.onServerStopping(new ServerStoppingEvent(server));
  EconomyHud.localPending();check(EconomyHud.pending(),"HUD fixture not pending");EconomyHud.onLogout(null);check(!EconomyHud.pending(),"Pending status survived logout");
  EconomyHud.receive(new EconomyFeedbackMessage("market:old","EMPTY","old","0"));EconomyHud.localPending();EconomyHud.onLogin(null);
  var graphics=new net.minecraft.client.gui.GuiGraphics();EconomyHud.draw(graphics,0,0,200,"market:old");
  check(!EconomyHud.pending()&&graphics.lastText.contains("règlements"),"New session reused old business/transaction status");
 }
 public static void main(String[] args)throws Exception{
  gate();resourcesAndCoalescing();rejectionAndFailure();reconnectAndStop();respawnAndRemovedPlayer();offThreadAndHud();
  System.out.println("Status refresh: bounded coalescing, independent resources, cooldown, rejection, failure, reconnect, respawn, shutdown and HUD reset passed.");
 }
}""",
}
java_home=os.environ.get('JAVA_HOME')
javac=str(Path(java_home)/'bin/javac.exe') if java_home else shutil.which('javac')
java=str(Path(java_home)/'bin/java.exe') if java_home else shutil.which('java')
if not javac or not java:raise RuntimeError('Configure JAVA_HOME avec le JDK 17.')
with tempfile.TemporaryDirectory(prefix='renblood-status-') as directory:
 paths=[]
 for name,text in fixtures.items():
  path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');paths.append(str(path))
 paths += [str(sources/prefix/name) for name in ['bank/StatusRefreshGate.java','bank/EconomyFeedback.java','client/economy/EconomyHud.java']]
 subprocess.run([javac,'-encoding','UTF-8','-d',directory,*paths],check=True)
 subprocess.run([java,'-cp',directory,'StatusRefreshChecks'],check=True)
