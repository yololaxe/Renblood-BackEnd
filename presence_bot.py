# presence_bot.py

import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from django.core.cache import cache
from asgiref.sync import sync_to_async

from players.models import Player  # Votre modèle Django

load_dotenv()

# ─── Intents & Bot ───────────────────────────────────────
intents = discord.Intents.default()
intents.members   = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ─── Mise à jour du cache des membres en ligne ────────────
async def update_online_cache():
    guild = bot.get_guild(int(os.getenv("DISCORD_GUILD_ID")))
    if not guild:
        return
    online = [m.name for m in guild.members if m.status is not discord.Status.offline]
    cache.set("discord_online_members", online, timeout=None)
    print(f"[BOT] Cache online-members mis à jour : {online}")


@bot.event
async def on_ready():
    # Sync des slash-commands
    await bot.tree.sync()
    print(f"[BOT] Connecté en tant que {bot.user}")
    # Présence
    await bot.change_presence(activity=discord.Game(name="sur Renblood"))
    # Premier peuplement du cache
    await update_online_cache()


@bot.event
async def on_presence_update(before, after):
    # Dès qu’un membre change de statut
    await update_online_cache()


# ─── Helper money breakdown ───────────────────────────────
def breakdown_money(amount: float) -> str:
    """
    Découpe un montant en or/argent/bronze/fer (bases 64).
    Retourne une chaîne du type "22🟡 8⚪ 15🟤 13⚙️"
    """
    # 1) on bosse sur des entiers
    amt = int(amount)

    # 2) on extrait chaque palier
    or_     = amt // (64**3)
    rem     = amt %  (64**3)
    argent  = rem // (64**2)
    rem     = rem %  (64**2)
    bronze  = rem // 64
    fer     = rem %  64

    parts = []
    if or_:    parts.append(f"{or_}🟡")
    if argent: parts.append(f"{argent}⚪")
    if bronze: parts.append(f"{bronze}🟤")
    if fer:    parts.append(f"{fer}⚙️")

    return " ".join(parts) or "0⚙️"


# ─── Slash-command `/info` ───────────────────────────────
@bot.tree.command(
    name="info",
    description="Affiche le lien vers le site web Renblood"
)
async def info(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🌐 Plus d'informations sur : https://renblood-website.web.app/home",
        ephemeral=True
    )


# ─── Slash-command `/link` ───────────────────────────────
@bot.tree.command(
    name="link",
    description="Permet de lier votre compte Discord"
)
async def link(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🔗 Pour lier votre compte, rendez-vous sur : https://renblood-website.web.app/character",
        ephemeral=True
    )


# ─── Slash-command `/me` ─────────────────────────────────
@bot.tree.command(
    name="me",
    description="Affiche votre profil complet Renblood"
)
async def me(interaction: discord.Interaction):
    discord_id = str(interaction.user.id)

    # 1) Récupérer le Player en thread séparé
    try:
        player = await sync_to_async(Player.objects.get)(discord_id=discord_id)
    except Player.DoesNotExist:
        return await interaction.response.send_message(
            "❌ Votre compte Discord n'est pas lié à Renblood. Utilisez `/link` sur le site web.",
            ephemeral=False
        )

    # 2) Construire l’embed
    embed = discord.Embed(
        title=f"{player.pseudo_minecraft} — {player.rank}",
        color=discord.Color.green(),
        description=player.description or "_Aucune description_"
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)

    # 📦 Ressources
    embed.add_field(
        name="💰 Votre fortune",
        value=breakdown_money(player.money),
        inline=False
    )

    # 🛠️ Statistiques de base + bonus
    stats = [
        ("💪 Force",        "strength"),
        ("🛡️ Vie",          "life"),
        ("⚡ Vitesse",       "speed"),
        ("🏹 Portée",       "reach"),
        ("🛡️ Résistance",   "resistance"),
        ("✨ Régénération",  "regeneration"),
        ("📦 Inventaire",   "place"),
        ("🎓 Compétence",   "skill"),
        ("🔮 Mana",         "mana"),
    ]
    for label, key in stats:
        base = getattr(player, key, 0)
        raw = player.real_charact.get(key, [])
        bonuses = raw if isinstance(raw, list) else ([raw] if raw else [])
        bonus = sum(b.get("count", 0) for b in bonuses)
        if bonus:
            embed.add_field(
                name=label,
                value=f"{base} + {bonus} = **{base+bonus}**",
                inline=True
            )
        else:
            embed.add_field(name=label, value=str(base), inline=True)

    # 🧬 Traits & 🎯 Actions
    embed.add_field(
        name="🧬 Traits",
        value=", ".join(t["Name"] for t in player.traits) or "-",
        inline=False
    )
    embed.add_field(
        name="🎯 Actions",
        value=", ".join(a["Name"] for a in player.actions) or "-",
        inline=False
    )

    # 📜 Métiers débloqués (jusqu’à 10 max)
    jobs = player.experiences.get("jobs", {})
    unlocked = []
    for key, data in jobs.items():
        xp  = data.get("xp", -1)
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

    # 3) Envoi public
    await interaction.response.send_message(embed=embed, ephemeral=False)


# ─── Démarrage du bot ─────────────────────────────────────
def run_presence_bot():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN non défini")
    bot.run(token)
