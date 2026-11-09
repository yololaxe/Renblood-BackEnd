"""Compile the production NPC repository/cache/models against minimal Minecraft/logging fixtures.
Reads and writes only a temporary directory, using the production JSON file manager.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

project = Path(__file__).resolve().parents[4]
sources = project / 'mods/NpcShopkeeperDev/NpcShopkeeper/src/main/java'
prefix = 'fr/renblood/npcshopkeeper/'
gson_candidates = sorted((Path.home() / '.gradle/caches/modules-2/files-2.1/com.google.code.gson/gson/2.10.1').glob('*/*gson-2.10.1.jar'))
if not gson_candidates:
    raise RuntimeError('Compile le mod une fois pour préparer Gson dans le cache Gradle.')
gson = gson_candidates[0]
java_home = os.environ.get('JAVA_HOME')
javac = str(Path(java_home) / 'bin/javac.exe') if java_home else shutil.which('javac')
java = str(Path(java_home) / 'bin/java.exe') if java_home else shutil.which('java')
if not javac or not java:
    raise RuntimeError('Configure JAVA_HOME avec le JDK 17.')
fixtures = {
 'org/apache/logging/log4j/Logger.java': 'package org.apache.logging.log4j; public class Logger { public void info(String m,Object... a){} public void error(String m,Object... a){System.err.println(m);for(Object v:a)if(v instanceof Throwable t)t.printStackTrace();} public void warn(String m,Object... a){} public void debug(String m,Object... a){} }',
 'org/apache/logging/log4j/LogManager.java': 'package org.apache.logging.log4j; public class LogManager { public static Logger getLogger(Object... a){return new Logger();} }',
 'net/minecraft/core/BlockPos.java': 'package net.minecraft.core; public record BlockPos(int x,int y,int z){public int getX(){return x;}public int getY(){return y;}public int getZ(){return z;} }',
 'net/minecraft/world/item/Item.java': 'package net.minecraft.world.item; public class Item{}',
 prefix+'manager/npc/GlobalNpcManager.java': 'package fr.renblood.npcshopkeeper.manager.npc; import java.util.*; public class GlobalNpcManager {public static Map<String,Object> getNpcData(String n){return Map.of();}}',
 prefix+'manager/server/OnServerStartedManager.java': 'package fr.renblood.npcshopkeeper.manager.server; public class OnServerStartedManager { public static String PATH,PATH_HISTORY,PATH_CONSTANT,PATH_COMMERCIAL,PATH_NPCS,PATH_PRICE,PATH_XP; }',
}
production = ['data/io/JsonRepository.java','data/io/JsonFileManager.java','manager/data/RuntimeDataCache.java',
 'data/trade/Trade.java','data/trade/TradeHistory.java','data/trade/TradeItem.java','data/trade/TradeResult.java',
 'data/npc/TradeNpc.java','data/price/TradeItemInfo.java']
with tempfile.TemporaryDirectory(prefix='renblood-npc-data-') as directory:
    classes=Path(directory)/'classes';classes.mkdir()
    paths=[]
    for name,text in fixtures.items():
        path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');paths.append(str(path))
    # Compile the actual publication helper with a tiny player/message fixture.
    form_source=(sources/prefix/'procedures/trade/CreateTradeValidationProcedure.java').read_text(encoding='utf-8')
    start=form_source.index('    public static boolean writeNewTradeToFile(')
    opening=form_source.index('{',start);end=opening+1;depth=1
    while depth:
        depth+=(form_source[end]=='{')-(form_source[end]=='}');end+=1
    form='package fr.renblood.npcshopkeeper.procedures.trade;import java.io.IOException;import com.google.gson.*;import net.minecraft.world.entity.player.Player;import net.minecraft.network.chat.Component;public class CreateTradeValidationProcedure{'+form_source[start:end]+'}'
    extra={
      'net/minecraft/ChatFormatting.java':'package net.minecraft;public enum ChatFormatting{RED}',
      'net/minecraft/network/chat/Component.java':'package net.minecraft.network.chat;public record Component(String text){public static Component literal(String text){return new Component(text);}public Component withStyle(net.minecraft.ChatFormatting c){return this;}}',
      'net/minecraft/world/entity/player/Player.java':'package net.minecraft.world.entity.player;import java.util.*;public class Player{public final List<String> messages=new ArrayList<>();public void displayClientMessage(net.minecraft.network.chat.Component c,boolean bar){messages.add(c.text());}}',
      prefix+'procedures/trade/CreateTradeValidationProcedure.java':form,
    }
    for name,text in extra.items():
        path=Path(directory)/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');paths.append(str(path))
    paths.append(str(Path(__file__).with_name('OfferCreationChecks.java')))
    paths += [str(sources/prefix/name) for name in production]
    paths.append(str(Path(__file__).with_name('NpcDataChecks.java')))
    subprocess.run([javac,'-encoding','UTF-8','-cp',str(gson),'-d',str(classes),*paths],check=True)
    subprocess.run([java,'-cp',str(classes)+os.pathsep+str(gson),'NpcDataChecks',str(Path(directory)/'data')],check=True)
    subprocess.run([java,'-cp',str(classes)+os.pathsep+str(gson),'OfferCreationChecks',str(Path(directory)/'offers')],check=True)
