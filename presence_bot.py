# presence_bot.py

import os
import discord
import asyncio
from dotenv import load_dotenv
from django.core.cache import cache

load_dotenv()

intents = discord.Intents.default()
intents.members   = True
intents.presences = True

bot = discord.Client(intents=intents)

async def update_online_cache():
    """Recalcule et stocke la liste des membres en ligne."""
    guild = bot.get_guild(int(os.getenv("DISCORD_GUILD_ID")))
    if not guild:
        return
    online = [m.name for m in guild.members if m.status != discord.Status.offline]
    cache.set("discord_online_members", online, timeout=None)  # plus de TTL
    print(f"[BOT] Cache online-members mis à jour : {online}")

@bot.event
async def on_ready():
    print(f"[BOT] Connecté en tant que {bot.user}")
    # 1) activité
    await bot.change_presence(activity=discord.Game(name="sur Renblood"))
    # 2) mise à jour initiale
    await update_online_cache()

@bot.event
async def on_presence_update(before, after):
    # Dès qu’un membre change de statut, on recalcule le cache
    await update_online_cache()

def run_presence_bot():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN non défini")
    bot.run(token)
