import logging
import os

import django
from django.conf import settings
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger(__name__)


if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RenbloodBackEnd.settings")
    django.setup()


from django.core.cache import cache


def run_presence_bot():
    if not getattr(settings, "ENABLE_PRESENCE_BOT", False):
        logger.info("Presence bot startup skipped because ENABLE_PRESENCE_BOT is disabled")
        return

    import discord
    from asgiref.sync import sync_to_async
    from discord.ext import commands

    intents = discord.Intents.default()
    intents.members = True
    intents.presences = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    def breakdown_money(amount):
        amount = int(amount)
        gold = amount // (64 ** 3)
        remainder = amount % (64 ** 3)
        silver = remainder // (64 ** 2)
        remainder = remainder % (64 ** 2)
        bronze = remainder // 64
        iron = remainder % 64
        parts = []
        if gold:
            parts.append(f"{gold} gold")
        if silver:
            parts.append(f"{silver} silver")
        if bronze:
            parts.append(f"{bronze} bronze")
        if iron:
            parts.append(f"{iron} iron")
        return " ".join(parts) or "0 iron"

    async def update_online_cache():
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if not guild_id:
            return
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return
        online = [
            member.name
            for member in guild.members
            if member.status is not discord.Status.offline
        ]
        await sync_to_async(cache.set)("discord_online_members", online, timeout=None)
        logger.info("Presence bot refreshed online members cache count=%s", len(online))

    @bot.event
    async def on_ready():
        try:
            await bot.tree.sync()
        except Exception as exc:
            logger.warning("Presence bot slash sync error: %s", exc)
        logger.info("Presence bot connected as %s", bot.user)
        await bot.change_presence(activity=discord.Game(name="sur Renblood"))
        await update_online_cache()

    @bot.event
    async def on_presence_update(before, after):
        await update_online_cache()

    @bot.tree.command(name="info", description="Affiche le lien vers le site web Renblood")
    async def info(interaction: discord.Interaction):
        await interaction.response.send_message(
            "Plus d'informations sur : https://renblood-website.web.app/home",
            ephemeral=True,
        )

    @bot.tree.command(name="link", description="Permet de lier votre compte Discord")
    async def link(interaction: discord.Interaction):
        await interaction.response.send_message(
            "Liez votre compte ici : https://renblood-website.web.app/character",
            ephemeral=True,
        )

    @bot.tree.command(name="me", description="Affiche votre profil complet Renblood")
    async def me(interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        from players.models import Player

        def get_player_sync(discord_identifier):
            return Player.objects.filter(discord_id=discord_identifier).first()

        player = await sync_to_async(get_player_sync)(discord_id)
        if not player:
            await interaction.response.send_message(
                "Votre compte Discord n'est pas lie a Renblood. Utilisez /link sur le site web.",
                ephemeral=False,
            )
            return

        embed = discord.Embed(
            title=f"{player.pseudo_minecraft} - {player.rank}",
            color=discord.Color.green(),
            description=player.description or "_Aucune description_",
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Votre fortune", value=breakdown_money(player.money), inline=False)

        stats = [
            ("Force", "strength"),
            ("Vie", "life"),
            ("Vitesse", "speed"),
            ("Portee", "reach"),
            ("Resistance", "resistance"),
            ("Regeneration", "regeneration"),
            ("Inventaire", "place"),
            ("Competence", "skill"),
            ("Mana", "mana"),
        ]
        for label, key in stats:
            base = getattr(player, key, 0)
            raw = player.real_charact.get(key, [])
            bonuses = raw if isinstance(raw, list) else ([raw] if raw else [])
            bonus = sum(entry.get("count", 0) for entry in bonuses if isinstance(entry, dict))
            value = f"{base} + {bonus} = {base + bonus}" if bonus else str(base)
            embed.add_field(name=label, value=value, inline=True)

        try:
            traits_text = ", ".join(trait["Name"] for trait in (player.traits or [])) or "-"
        except Exception:
            traits_text = "-"
        embed.add_field(name="Traits", value=traits_text, inline=False)

        try:
            actions_text = ", ".join(action["Name"] for action in (player.actions or [])) or "-"
        except Exception:
            actions_text = "-"
        embed.add_field(name="Actions", value=actions_text, inline=False)

        jobs = (player.experiences or {}).get("jobs", {})
        unlocked = []
        for key, data in jobs.items():
            xp = data.get("xp", -1)
            level = data.get("level", 0)
            if xp >= 0:
                unlocked.append(f"Lv {level} {key.replace('_', ' ').title()}")
        if unlocked:
            text = "\n".join(unlocked[:10])
            if len(unlocked) > 10:
                text += "\n..."
            embed.add_field(name="Metiers", value=text, inline=False)

        embed.set_footer(text="Renblood")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN non defini")
    logger.info("Presence bot starting")
    bot.run(token)
