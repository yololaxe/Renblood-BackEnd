# presence_bot.py

import os
import django
from dotenv import load_dotenv
from django.conf import settings

load_dotenv()

# Ensure Django is setup
if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "RenbloodBackEnd.settings")
    django.setup()

from django.core.cache import cache

def run_presence_bot():
    # Import "paresseux" pour éviter l'import d'aiohttp/discord pendant l'init Django
    import discord
    from discord.ext import commands
    from asgiref.sync import sync_to_async

    # ─── Intents & Bot ─────────────────────────────────────
    intents = discord.Intents.default()
    intents.members = True
    intents.presences = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    # ─── Helpers ──────────────────────────────────────────
    def breakdown_money(amount: float) -> str:
        amt = int(amount)
        or_ = amt // (64**3)
        rem = amt % (64**3)
        argent = rem // (64**2)
        rem = rem % (64**2)
        bronze = rem // 64
        fer = rem % 64
        parts = []
        if or_: parts.append(f"{or_}🟡")
        if argent: parts.append(f"{argent}⚪")
        if bronze: parts.append(f"{bronze}🟤")
        if fer: parts.append(f"{fer}⚙️")
        return " ".join(parts) or "0⚙️"

    async def update_online_cache():
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if not guild_id:
            return
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return
        online = [m.name for m in guild.members if m.status is not discord.Status.offline]
        # Wrap synchronous cache call
        await sync_to_async(cache.set)("discord_online_members", online, timeout=None)
        print(f"[BOT] Cache online-members mis à jour : {online}")

    # ─── Events ───────────────────────────────────────────
    @bot.event
    async def on_ready():
        try:
            await bot.tree.sync()
        except Exception as e:
            print("[BOT] Slash sync error:", e)
        print(f"[BOT] Connecté en tant que {bot.user}")
        await bot.change_presence(activity=discord.Game(name="sur Renblood"))
        await update_online_cache()

    @bot.event
    async def on_presence_update(before, after):
        await update_online_cache()

    # ─── Slash /info ──────────────────────────────────────
    @bot.tree.command(name="info", description="Affiche le lien vers le site web Renblood")
    async def info(interaction: discord.Interaction):
        await interaction.response.send_message(
            "🌐 Plus d'informations sur : https://renblood-website.web.app/home",
            ephemeral=True
        )

    # ─── Slash /link ──────────────────────────────────────
    @bot.tree.command(name="link", description="Permet de lier votre compte Discord")
    async def link(interaction: discord.Interaction):
        await interaction.response.send_message(
            "🔗 Liez votre compte ici : https://renblood-website.web.app/character",
            ephemeral=True
        )

    # ─── Slash /me ────────────────────────────────────────
    @bot.tree.command(name="me", description="Affiche votre profil complet Renblood")
    async def me(interaction: discord.Interaction):
        discord_id = str(interaction.user.id)

        # Import tardif pour éviter cycles au boot
        from players.models import Player

        def get_player_sync(d_id):
            return Player.objects.filter(discord_id=d_id).first()

        player = await sync_to_async(get_player_sync)(discord_id)

        if not player:
            return await interaction.response.send_message(
                "❌ Votre compte Discord n'est pas lié à Renblood. Utilisez `/link` sur le site web.",
                ephemeral=False
            )

        embed = discord.Embed(
            title=f"{player.pseudo_minecraft} — {player.rank}",
            color=discord.Color.green(),
            description=player.description or "_Aucune description_"
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        embed.add_field(name="💰 Votre fortune", value=breakdown_money(player.money), inline=False)

        stats = [
            ("💪 Force", "strength"),
            ("🛡️ Vie", "life"),
            ("⚡ Vitesse", "speed"),
            ("🏹 Portée", "reach"),
            ("🛡️ Résistance", "resistance"),
            ("✨ Régénération", "regeneration"),
            ("📦 Inventaire", "place"),
            ("🎓 Compétence", "skill"),
            ("🔮 Mana", "mana"),
        ]
        for label, key in stats:
            base = getattr(player, key, 0)
            raw = player.real_charact.get(key, [])
            bonuses = raw if isinstance(raw, list) else ([raw] if raw else [])
            bonus = sum(b.get("count", 0) for b in bonuses)
            if bonus:
                embed.add_field(name=label, value=f"{base} + {bonus} = **{base+bonus}**", inline=True)
            else:
                embed.add_field(name=label, value=str(base), inline=True)

        try:
            traits_txt = ", ".join(t["Name"] for t in (player.traits or [])) or "-"
        except Exception:
            traits_txt = "-"
        embed.add_field(name="🧬 Traits", value=traits_txt, inline=False)

        try:
            actions_txt = ", ".join(a["Name"] for a in (player.actions or [])) or "-"
        except Exception:
            actions_txt = "-"
        embed.add_field(name="🎯 Actions", value=actions_txt, inline=False)

        jobs = (player.experiences or {}).get("jobs", {})
        unlocked = []
        for key, data in jobs.items():
            xp = data.get("xp", -1)
            lvl = data.get("level", 0)
            if xp >= 0:
                name = key.replace("_", " ").title()
                unlocked.append(f"Lv **{lvl}** {name}")
        if unlocked:
            text = "\n".join(unlocked[:10])
            if len(unlocked) > 10:
                text += "\n…"
            embed.add_field(name="📜 Métiers", value=text, inline=False)

        embed.set_footer(text="Renblood • Bon jeu !")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # ─── Run ──────────────────────────────────────────────
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN non défini")
    bot.run(token)
