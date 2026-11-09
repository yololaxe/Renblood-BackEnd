"""Deterministic checks of the production delayed-menu opener and loaded spawn-point selector.
Minecraft/Forge dependencies are minimal fixtures. No client or world is launched.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

project=Path(__file__).resolve().parents[4]
sources=project/'mods/NpcShopkeeperDev/NpcShopkeeper/src/main/java'
prefix='fr/renblood/npcshopkeeper/'
api=(sources/prefix/'api/NpcShopkeeperAPI.java').read_text(encoding='utf-8')
start=re.search(r'^    private static BlockPos randomFreePosition\(',api,re.M).start()
opening=api.index('{',start);end=opening+1;depth=1
while depth:
    depth+=(api[end]=='{')-(api[end]=='}');end+=1
selector=api[start:end]
fixtures={
 'org/apache/logging/log4j/Logger.java':'package org.apache.logging.log4j; public class Logger{public void error(String m,Object... a){}public void warn(String m,Object... a){}public void debug(String m,Object... a){}public void info(String m,Object... a){}}',
 'org/apache/logging/log4j/LogManager.java':'package org.apache.logging.log4j; public class LogManager{public static Logger getLogger(Object... a){return new Logger();}}',
 'net/minecraft/ChatFormatting.java':'package net.minecraft;public enum ChatFormatting{RED}',
 'net/minecraft/core/BlockPos.java':'package net.minecraft.core;public record BlockPos(int x,int y,int z){public static BlockPos containing(double x,double y,double z){return new BlockPos((int)x,(int)y,(int)z);}}',
 'net/minecraft/world/level/LevelAccessor.java':'package net.minecraft.world.level;public interface LevelAccessor{}',
 'net/minecraft/network/chat/Component.java':'package net.minecraft.network.chat;import net.minecraft.ChatFormatting;public record Component(String value){public static Component literal(String s){return new Component(s);}public String getString(){return value;}public Component withStyle(ChatFormatting c){return this;}}',
 'net/minecraft/world/entity/Entity.java':'package net.minecraft.world.entity;import net.minecraft.network.chat.Component;public class Entity{public Component getName(){return Component.literal("tester");}}',
 'net/minecraft/world/inventory/AbstractContainerMenu.java':'package net.minecraft.world.inventory;public class AbstractContainerMenu{public int containerId=1;}',
 'net/minecraft/world/entity/player/Player.java':'package net.minecraft.world.entity.player;import net.minecraft.world.entity.Entity;import net.minecraft.world.inventory.AbstractContainerMenu;import net.minecraft.network.chat.Component;public class Player extends Entity{public AbstractContainerMenu containerMenu=new AbstractContainerMenu();public void displayClientMessage(Component c,boolean b){}}',
 'net/minecraft/world/entity/player/Inventory.java':'package net.minecraft.world.entity.player;public class Inventory{}',
 'net/minecraft/server/level/ServerPlayer.java':'package net.minecraft.server.level;public class ServerPlayer extends net.minecraft.world.entity.player.Player{public boolean disconnected;public boolean hasDisconnected(){return disconnected;}}',
 'net/minecraft/network/FriendlyByteBuf.java':'package net.minecraft.network;import java.util.*;import net.minecraft.core.BlockPos;public class FriendlyByteBuf{private final Queue<Object> values=new ArrayDeque<>();public FriendlyByteBuf(Object o){}public FriendlyByteBuf writeBlockPos(BlockPos p){values.add(p);return this;}public FriendlyByteBuf writeUtf(String s){values.add(s);return this;}public BlockPos readBlockPos(){return (BlockPos)values.remove();}public String readUtf(){return (String)values.remove();}}',
 'io/netty/buffer/Unpooled.java':'package io.netty.buffer;public class Unpooled{public static Object buffer(){return new Object();}}',
 'net/minecraft/world/MenuProvider.java':'package net.minecraft.world;import net.minecraft.network.chat.Component;import net.minecraft.world.entity.player.*;import net.minecraft.world.inventory.AbstractContainerMenu;public interface MenuProvider{Component getDisplayName();AbstractContainerMenu createMenu(int id,Inventory inv,Player p);}',
 'net/minecraftforge/network/NetworkHooks.java':'package net.minecraftforge.network;import net.minecraft.server.level.ServerPlayer;import net.minecraft.world.MenuProvider;import net.minecraft.world.entity.player.Inventory;import net.minecraft.network.FriendlyByteBuf;import java.util.function.Consumer;public class NetworkHooks{public static void openScreen(ServerPlayer p,MenuProvider provider,Consumer<FriendlyByteBuf> writer){writer.accept(new FriendlyByteBuf(new Object()));p.containerMenu=provider.createMenu(1,new Inventory(),p);}}',
 prefix+'data/io/JsonRepository.java':'package fr.renblood.npcshopkeeper.data.io;public class JsonRepository<T>{}',
 prefix+'data/trade/Trade.java':'package fr.renblood.npcshopkeeper.data.trade;public class Trade{}',
 prefix+'manager/server/OnServerStartedManager.java':'package fr.renblood.npcshopkeeper.manager.server;public class OnServerStartedManager{}',
 prefix+'manager/data/RuntimeDataCache.java':'package fr.renblood.npcshopkeeper.manager.data;public class RuntimeDataCache{public static Object getTrade(String name){return name.equals("missing")?null:new Object();}}',
 prefix+'Npcshopkeeper.java':'package fr.renblood.npcshopkeeper;import java.util.*;public class Npcshopkeeper{public static final Queue<Runnable> tasks=new ArrayDeque<>();public static void queueServerWork(int n,Runnable r){tasks.add(r);}public static void drain(){while(!tasks.isEmpty())tasks.remove().run();}}',
 prefix+'world/inventory/TradeMenu.java':'package fr.renblood.npcshopkeeper.world.inventory;import net.minecraft.network.FriendlyByteBuf;import net.minecraft.world.entity.player.Inventory;public class TradeMenu extends net.minecraft.world.inventory.AbstractContainerMenu{public String tradeName,npcId;public TradeMenu(int id,Inventory inv,FriendlyByteBuf b){b.readBlockPos();tradeName=b.readUtf();npcId=b.readUtf();b.readUtf();}}',
 prefix+'procedures/trade/TradePrepareProcedure.java':'package fr.renblood.npcshopkeeper.procedures.trade;import java.util.*;import net.minecraft.world.entity.Entity;public class TradePrepareProcedure{public static final List<String> prepared=new ArrayList<>();public static void execute(Entity p,String trade,String npc,String name){prepared.add(trade+":"+npc);}}',
 'NpcMenuChecks.java':"""import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.inventory.AbstractContainerMenu;
import fr.renblood.npcshopkeeper.Npcshopkeeper;
import fr.renblood.npcshopkeeper.procedures.trade.*;
public class NpcMenuChecks{
 static void check(boolean c,String m){if(!c)throw new AssertionError(m);}
 static void reset(){Npcshopkeeper.tasks.clear();TradePrepareProcedure.prepared.clear();}
 static void open(ServerPlayer p,String name){TradeCommandProcedure.execute(null,0,64,0,name,p,name+"-npc","merchant");}
 public static void main(String[] args){
  reset();var p=new ServerPlayer();open(p,"first");Npcshopkeeper.drain();check(TradePrepareProcedure.prepared.equals(java.util.List.of("first:first-npc")),"Normal menu not prepared");
  reset();open(p,"first");open(p,"second");Npcshopkeeper.drain();check(TradePrepareProcedure.prepared.equals(java.util.List.of("second:second-npc")),"Old prepare overwrote new menu");
  reset();open(p,"closed");p.containerMenu=new AbstractContainerMenu();Npcshopkeeper.drain();check(TradePrepareProcedure.prepared.isEmpty(),"Closed menu prepared");
  reset();open(p,"same");open(p,"same");Npcshopkeeper.drain();check(TradePrepareProcedure.prepared.size()==1,"Reopened matching menu accepted old instance");
  reset();open(p,"left");p.disconnected=true;Npcshopkeeper.drain();check(TradePrepareProcedure.prepared.isEmpty(),"Disconnected player prepared");p.disconnected=false;
  reset();var before=p.containerMenu;open(p,"missing");check(before==p.containerMenu&&Npcshopkeeper.tasks.isEmpty(),"Missing trade opened menu");
  System.out.println("NPC menus: normal, replaced, closed, reopened, disconnected and missing-offer scenarios passed.");
 }
}""",
 'InnSpawnPointChecks.java':"""import java.util.*;
public class InnSpawnPointChecks{
 static final Random RANDOM=new Random(12);
 static final String INN_CUSTOMER_TAG="inn";
 record BlockPos(int id){}
 record CommercialRoad(List<BlockPos> positions){List<BlockPos> getPositions(){return positions;}}
 record AABB(BlockPos pos){AABB inflate(double d){return this;}}
 record Tag(boolean customer){boolean getBoolean(String key){return customer;}}
 record TradeNpcEntity(boolean customer){Tag getPersistentData(){return new Tag(customer);}}
 static class ServerLevel{
  Set<BlockPos> loaded=new HashSet<>();Set<BlockPos> occupied=new HashSet<>();int queries;
  boolean hasChunkAt(BlockPos p){return loaded.contains(p);}
  List<TradeNpcEntity> getEntitiesOfClass(Class<?> c,AABB area){if(!loaded.contains(area.pos()))throw new AssertionError("Unloaded point queried");queries++;return occupied.contains(area.pos())?List.of(new TradeNpcEntity(true)):List.of();}
 }
"""+selector+"""
 static void check(boolean c,String m){if(!c)throw new AssertionError(m);}
 public static void main(String[] args){
  var level=new ServerLevel();var a=new BlockPos(1);var b=new BlockPos(2);var c=new BlockPos(3);var road=new CommercialRoad(List.of(a,b,c));
  check(randomFreePosition(level,road)==null&&level.queries==0,"Fully unloaded route queried entities");
  level.loaded.add(b);level.occupied.add(b);check(randomFreePosition(level,road)==null&&level.queries==1,"Occupied loaded point not respected");
  level.loaded.add(c);for(int i=0;i<100;i++)check(randomFreePosition(level,road).equals(c),"Unloaded or occupied point chosen");
  check(randomFreePosition(level,new CommercialRoad(List.of()))==null,"Empty route not handled");
  System.out.println("Inn spawn points: unloaded points never queried; occupied loaded points skipped; loaded free point selected.");
 }
}""",
}
fixtures.update({'net/minecraft/ChatFormatting.java': 'package net.minecraft;public enum '
                                      'ChatFormatting{RED,YELLOW}',
 'com/google/gson/JsonObject.java': 'package com.google.gson;public class JsonObject{}',
 'net/minecraft/world/entity/Entity.java': 'package net.minecraft.world.entity;import '
                                           'java.util.*;import '
                                           'net.minecraft.network.chat.Component;public class '
                                           'Entity{public UUID uuid=UUID.randomUUID();public '
                                           'boolean discarded;public UUID getUUID(){return '
                                           'uuid;}public void discard(){discarded=true;}public '
                                           'Component getName(){return '
                                           'Component.literal("tester");}}',
 'net/minecraft/world/entity/Mob.java': 'package net.minecraft.world.entity;public class Mob '
                                        'extends Entity{}',
 'net/minecraft/world/level/Level.java': 'package net.minecraft.world.level;public class Level{}',
 'net/minecraft/server/level/ServerLevel.java': 'package net.minecraft.server.level;import '
                                                'java.util.*;import '
                                                'net.minecraft.world.entity.Entity;public class '
                                                'ServerLevel extends '
                                                'net.minecraft.world.level.Level{public final '
                                                'Map<UUID,Entity> entities=new HashMap<>();public '
                                                'Entity getEntity(UUID id){return '
                                                'entities.get(id);}}',
 'net/minecraft/server/level/ServerPlayer.java': 'package net.minecraft.server.level;public class '
                                                 'ServerPlayer extends '
                                                 'net.minecraft.world.entity.player.Player{public '
                                                 'boolean disconnected;public int closed;public '
                                                 'final ServerLevel world=new ServerLevel();public '
                                                 'boolean hasDisconnected(){return '
                                                 'disconnected;}public ServerLevel level(){return '
                                                 'world;}public void '
                                                 'closeContainer(){closed++;containerMenu=new '
                                                 'net.minecraft.world.inventory.AbstractContainerMenu();}}',
 'net/minecraft/world/inventory/Slot.java': 'package net.minecraft.world.inventory;public class '
                                            'Slot{public net.minecraft.world.item.ItemStack '
                                            'getItem(){return new '
                                            'net.minecraft.world.item.ItemStack();}}',
 'net/minecraft/world/item/ItemStack.java': 'package net.minecraft.world.item;public class '
                                            'ItemStack{public boolean isEmpty(){return '
                                            'true;}public boolean hasCustomHoverName(){return '
                                            'false;}public net.minecraft.network.chat.Component '
                                            'getHoverName(){return '
                                            'net.minecraft.network.chat.Component.literal("");}}',
 'fr/renblood/npcshopkeeper/data/io/JsonFileManager.java': 'package '
                                                           'fr.renblood.npcshopkeeper.data.io;public '
                                                           'class JsonFileManager{}',
 'fr/renblood/npcshopkeeper/data/io/JsonRepository.java': 'package '
                                                          'fr.renblood.npcshopkeeper.data.io;import '
                                                          'java.nio.file.Path;import '
                                                          'java.util.*;import '
                                                          'java.util.function.*;import '
                                                          'com.google.gson.JsonObject;public class '
                                                          'JsonRepository<T>{public static final '
                                                          'Map<String,List<?>> data=new '
                                                          'HashMap<>();public static int '
                                                          'writes,reads;public static boolean '
                                                          'fail;private final String key;public '
                                                          'JsonRepository(Path p,String '
                                                          'key,Function<JsonObject,T> '
                                                          'd,Function<T,JsonObject> '
                                                          's){this.key=key;}@SuppressWarnings("unchecked")public '
                                                          'List<T> loadAll(){reads++;return new '
                                                          'ArrayList<>((List<T>)data.getOrDefault(key,List.of()));}public '
                                                          'void saveAll(Collection<T> '
                                                          'rows){if(fail)throw new '
                                                          'java.io.UncheckedIOException(new '
                                                          'java.io.IOException("Write fixture '
                                                          'failed"));writes++;data.put(key,new '
                                                          'ArrayList<>(rows));}}',
 'fr/renblood/npcshopkeeper/data/trade/TradeHistory.java': 'package '
                                                           'fr.renblood.npcshopkeeper.data.trade;import '
                                                           'com.google.gson.JsonObject;public '
                                                           'class TradeHistory{public String '
                                                           'id="contract",npcId;public boolean '
                                                           'finished,abandoned;public String '
                                                           'getId(){return id;}public void '
                                                           'setFinished(boolean '
                                                           'b){finished=b;}public void '
                                                           'setAbandoned(boolean '
                                                           'b){abandoned=b;}public String '
                                                           'getNpcId(){return npcId;}public static '
                                                           'TradeHistory fromJson(JsonObject '
                                                           'o){return new TradeHistory();}public '
                                                           'JsonObject toJson(){return new '
                                                           'JsonObject();}}',
 'fr/renblood/npcshopkeeper/data/npc/TradeNpc.java': 'package '
                                                     'fr.renblood.npcshopkeeper.data.npc;import '
                                                     'com.google.gson.JsonObject;public class '
                                                     'TradeNpc{public String id;public boolean '
                                                     'route;public String getNpcId(){return '
                                                     'id;}public boolean isRouteNpc(){return '
                                                     'route;}public static TradeNpc '
                                                     'fromJson(JsonObject o){return new '
                                                     'TradeNpc();}public JsonObject '
                                                     'toJson(){return new JsonObject();}}',
 'fr/renblood/npcshopkeeper/data/commercial/CommercialRoad.java': 'package '
                                                                  'fr.renblood.npcshopkeeper.data.commercial;import '
                                                                  'java.util.*;import '
                                                                  'fr.renblood.npcshopkeeper.entity.TradeNpcEntity;public '
                                                                  'class CommercialRoad{public '
                                                                  'List<TradeNpcEntity> '
                                                                  'entities=new '
                                                                  'ArrayList<>();public int '
                                                                  'persisted;public '
                                                                  'List<TradeNpcEntity> '
                                                                  'getNpcEntities(){return '
                                                                  'entities;}public void '
                                                                  'removeNpcAndPersist(TradeNpcEntity '
                                                                  'entity){persisted++;}}',
 'fr/renblood/npcshopkeeper/entity/TradeNpcEntity.java': 'package '
                                                         'fr.renblood.npcshopkeeper.entity;import '
                                                         'fr.renblood.npcshopkeeper.data.npc.TradeNpc;public '
                                                         'class TradeNpcEntity extends '
                                                         'net.minecraft.world.entity.Mob{public '
                                                         'final TradeNpc model=new '
                                                         'TradeNpc();public '
                                                         'TradeNpcEntity(){model.id=getUUID().toString();}public '
                                                         'TradeNpc getTradeNpc(){return '
                                                         'model;}public String getNpcName(){return '
                                                         '"merchant";}}',
 'fr/renblood/npcshopkeeper/manager/npc/ActiveNpcManager.java': 'package '
                                                                'fr.renblood.npcshopkeeper.manager.npc;public '
                                                                'class ActiveNpcManager{public '
                                                                'static int removed;public static '
                                                                'void '
                                                                'removeActiveNpc(java.util.UUID '
                                                                'id){removed++;}}',
 'fr/renblood/npcshopkeeper/manager/npc/GlobalNpcManager.java': 'package '
                                                                'fr.renblood.npcshopkeeper.manager.npc;public '
                                                                'class GlobalNpcManager{public '
                                                                'static int deactivated;public '
                                                                'static void deactivateNpc(String '
                                                                'name){deactivated++;}}',
 'fr/renblood/npcshopkeeper/manager/npc/NpcSpawnerManager.java': 'package '
                                                                 'fr.renblood.npcshopkeeper.manager.npc;import '
                                                                 'java.util.*;import '
                                                                 'fr.renblood.npcshopkeeper.data.commercial.CommercialRoad;import '
                                                                 'net.minecraft.core.BlockPos;import '
                                                                 'net.minecraft.world.entity.Mob;public '
                                                                 'class NpcSpawnerManager{public '
                                                                 'static final '
                                                                 'Map<CommercialRoad,HashMap<BlockPos,Mob>> '
                                                                 'activeNPCs=new HashMap<>();}',
 'fr/renblood/npcshopkeeper/manager/trade/TradeSessionManager.java': 'package '
                                                                     'fr.renblood.npcshopkeeper.manager.trade;public '
                                                                     'class '
                                                                     'TradeSessionManager{public '
                                                                     'static String id;public '
                                                                     'static String '
                                                                     'getTradeId(java.util.UUID '
                                                                     'p){return id;}public static '
                                                                     'void '
                                                                     'clearTradeId(java.util.UUID '
                                                                     'p){id=null;}}',
 'fr/renblood/npcshopkeeper/manager/server/OnServerStartedManager.java': 'package '
                                                                         'fr.renblood.npcshopkeeper.manager.server;public '
                                                                         'class '
                                                                         'OnServerStartedManager{public '
                                                                         'static String '
                                                                         'PATH_HISTORY="history.json",PATH_NPCS="npcs.json";}',
 'fr/renblood/npcshopkeeper/Npcshopkeeper.java': 'package fr.renblood.npcshopkeeper;import '
                                                 'java.util.*;import '
                                                 'fr.renblood.npcshopkeeper.data.commercial.CommercialRoad;public '
                                                 'class Npcshopkeeper{public static final '
                                                 'Queue<Runnable> tasks=new ArrayDeque<>();public '
                                                 'static List<CommercialRoad> COMMERCIAL_ROADS=new '
                                                 'ArrayList<>();public static void '
                                                 'debugLog(org.apache.logging.log4j.Logger '
                                                 'l,String message){}public static void '
                                                 'queueServerWork(int n,Runnable '
                                                 'r){tasks.add(r);}public static void '
                                                 'drain(){while(!tasks.isEmpty())tasks.remove().run();}}',
 'fr/renblood/npcshopkeeper/world/inventory/TradeMenu.java': 'package '
                                                             'fr.renblood.npcshopkeeper.world.inventory;import '
                                                             'net.minecraft.network.FriendlyByteBuf;import '
                                                             'net.minecraft.world.entity.player.Inventory;public '
                                                             'class TradeMenu extends '
                                                             'net.minecraft.world.inventory.AbstractContainerMenu{public '
                                                             'String tradeName,npcId;public '
                                                             'boolean pending;public boolean '
                                                             'isSettlementPending(){return '
                                                             'pending;}public TradeMenu(int '
                                                             'id,Inventory inv,FriendlyByteBuf '
                                                             'b){b.readBlockPos();tradeName=b.readUtf();npcId=b.readUtf();b.readUtf();}}',
 'NpcCancelChecks.java': 'import java.util.*;\n'
                         'import fr.renblood.npcshopkeeper.Npcshopkeeper;\n'
                         'import fr.renblood.npcshopkeeper.data.io.JsonRepository;\n'
                         'import fr.renblood.npcshopkeeper.data.trade.TradeHistory;\n'
                         'import fr.renblood.npcshopkeeper.entity.TradeNpcEntity;\n'
                         'import fr.renblood.npcshopkeeper.data.commercial.CommercialRoad;\n'
                         'import fr.renblood.npcshopkeeper.manager.npc.*;\n'
                         'import fr.renblood.npcshopkeeper.manager.trade.TradeSessionManager;\n'
                         'import fr.renblood.npcshopkeeper.procedures.trade.*;\n'
                         'import fr.renblood.npcshopkeeper.world.inventory.TradeMenu;\n'
                         'import net.minecraft.server.level.ServerPlayer;\n'
                         'import net.minecraft.core.BlockPos;\n'
                         'public class NpcCancelChecks{\n'
                         ' static void check(boolean condition,String message){if(!condition)throw '
                         'new AssertionError(message);}\n'
                         ' static TradeHistory setup(ServerPlayer player,TradeNpcEntity npc){\n'
                         '  '
                         'JsonRepository.data.clear();JsonRepository.writes=0;JsonRepository.reads=0;JsonRepository.fail=false;\n'
                         '  '
                         'Npcshopkeeper.COMMERCIAL_ROADS.clear();NpcSpawnerManager.activeNPCs.clear();GlobalNpcManager.deactivated=0;ActiveNpcManager.removed=0;\n'
                         '  var history=new '
                         'TradeHistory();history.npcId=npc.getUUID().toString();\n'
                         '  JsonRepository.data.put("history",new '
                         'ArrayList<>(List.of(history)));JsonRepository.data.put("npcs",new '
                         'ArrayList<>(List.of(npc.model)));\n'
                         '  '
                         'TradeSessionManager.id="contract";player.world.entities.put(npc.getUUID(),npc);\n'
                         '  '
                         'TradeCommandProcedure.execute(null,0,64,0,"trade",player,npc.getUUID().toString(),"merchant");\n'
                         '  return history;\n'
                         ' }\n'
                         ' public static void main(String[] args){\n'
                         '  var player=new ServerPlayer();var fixed=new TradeNpcEntity();var '
                         'history=setup(player,fixed);\n'
                         '  CancelProcedure.execute(player);\n'
                         '  check(history.finished&&history.abandoned,"Contract not abandoned");\n'
                         '  '
                         'check(!fixed.discarded&&JsonRepository.data.get("npcs").size()==1,"Fixed '
                         'merchant or model deleted");\n'
                         '  '
                         'check(JsonRepository.writes==1&&GlobalNpcManager.deactivated==0&&ActiveNpcManager.removed==0,"Fixed '
                         'merchant cleanup invoked");\n'
                         '  check(player.closed==1&&TradeSessionManager.id==null,"Abandon did not '
                         'close/clear session");\n'
                         '  player=new ServerPlayer();var temporary=new '
                         'TradeNpcEntity();temporary.model.route=true;setup(player,temporary);CancelProcedure.execute(player);\n'
                         '  '
                         'check(temporary.discarded&&JsonRepository.data.get("npcs").isEmpty(),"Temporary '
                         'merchant not cleaned up");\n'
                         '  '
                         'check(GlobalNpcManager.deactivated==1&&ActiveNpcManager.removed==1,"Temporary '
                         'name/index not released");\n'
                         '  player=new ServerPlayer();var member=new '
                         'TradeNpcEntity();setup(player,member);var road=new '
                         'CommercialRoad();road.entities.add(member);Npcshopkeeper.COMMERCIAL_ROADS.add(road);\n'
                         '  var positions=new '
                         'HashMap<BlockPos,net.minecraft.world.entity.Mob>();positions.put(new '
                         'BlockPos(0,64,0),member);NpcSpawnerManager.activeNPCs.put(road,positions);\n'
                         '  '
                         'CancelProcedure.execute(player);check(member.discarded&&road.persisted==1&&road.entities.isEmpty()&&positions.isEmpty(),"Assigned '
                         'route membership not cleaned up");\n'
                         '  player=new ServerPlayer();var busy=new '
                         'TradeNpcEntity();history=setup(player,busy);((TradeMenu)player.containerMenu).pending=true;\n'
                         '  '
                         'CancelProcedure.execute(player);check(!history.finished&&!busy.discarded&&JsonRepository.reads==0&&JsonRepository.writes==0&&player.closed==0,"Pending '
                         'settlement was abandoned");\n'
                         '  player=new ServerPlayer();var failed=new '
                         'TradeNpcEntity();setup(player,failed);JsonRepository.fail=true;\n'
                         '  '
                         'CancelProcedure.execute(player);check(!failed.discarded&&GlobalNpcManager.deactivated==0&&player.messages.stream().anyMatch(message->message.contains("non '
                         'confirmé")),"Failed cancellation hid persistence error or removed '
                         'NPC");JsonRepository.fail=false;\n'
                         '  System.out.println("NPC cancellation: fixed merchant retained, route '
                         'merchants cleaned up, pending settlement preserved.");\n'
                         ' }\n'
                         '}',
 'net/minecraft/world/entity/player/Player.java': 'package '
                                                  'net.minecraft.world.entity.player;import '
                                                  'net.minecraft.world.entity.Entity;import '
                                                  'net.minecraft.world.inventory.AbstractContainerMenu;import '
                                                  'net.minecraft.network.chat.Component;public '
                                                  'class Player extends Entity{public final '
                                                  'java.util.List<String> messages=new '
                                                  'java.util.ArrayList<>();public '
                                                  'AbstractContainerMenu containerMenu=new '
                                                  'AbstractContainerMenu();public void '
                                                  'displayClientMessage(Component c,boolean '
                                                  'b){messages.add(c.getString());}}'})

java_home=os.environ.get('JAVA_HOME')
javac=str(Path(java_home)/'bin/javac.exe') if java_home else shutil.which('javac')
java=str(Path(java_home)/'bin/java.exe') if java_home else shutil.which('java')
if not javac or not java:raise RuntimeError('Configure JAVA_HOME avec le JDK 17.')
with tempfile.TemporaryDirectory(prefix='renblood-npc-interactions-') as directory:
 paths=[]
 for name,text in fixtures.items():
  path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');paths.append(str(path))
 paths.append(str(sources/prefix/'procedures/trade/TradeCommandProcedure.java'))
 paths.append(str(sources/prefix/'procedures/trade/CancelProcedure.java'))
 subprocess.run([javac,'-encoding','UTF-8','-d',directory,*paths],check=True)
 for check in ['NpcMenuChecks','InnSpawnPointChecks','NpcCancelChecks']:subprocess.run([java,'-cp',directory,check],check=True)
