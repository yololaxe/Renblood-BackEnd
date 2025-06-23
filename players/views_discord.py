# players/views_discord.py

import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import redirect
from django.conf import settings
import discord
from .models import Player

# URLs Discord OAuth2
DISCORD_OAUTH_AUTHORIZE = "https://discord.com/api/oauth2/authorize"
DISCORD_OAUTH_TOKEN     = "https://discord.com/api/oauth2/token"
DISCORD_API_USER        = "https://discord.com/api/users/@me"

class DiscordViewSet(viewsets.ViewSet):
    """
    1) GET /api/discord/link/     → redirige vers Discord OAuth2
    2) GET /api/discord/callback/ → Discord renvoie ici avec ?code=…
    3) GET /api/discord/me/       → renvoie les infos Discord du player connecté
    """

    @action(detail=False, methods=['get'], url_path='link')
    def link(self, request):
        params = {
            "client_id":     settings.DISCORD_CLIENT_ID,
            "redirect_uri":  settings.DISCORD_REDIRECT_URI,
            "response_type": "code",
            "scope":         "identify",
        }
        url = f"{DISCORD_OAUTH_AUTHORIZE}?{requests.compat.urlencode(params)}"
        return Response({"url": url}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='callback')
    def callback(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({"detail": "Paramètre `code` manquant"}, status=status.HTTP_400_BAD_REQUEST)

        # 1) Échange code contre access_token
        token_data = {
            "client_id":     settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  settings.DISCORD_REDIRECT_URI,
            "scope":         "identify",
        }
        token_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_res = requests.post(DISCORD_OAUTH_TOKEN, data=token_data, headers=token_headers)
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")

        # 2) Récupère les infos utilisateur Discord
        user_res = requests.get(
            DISCORD_API_USER,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_res.raise_for_status()
        d = user_res.json()

        # 3) Sauvegarde dans le modèle Player
        player = Player.objects.get(id=request.user.id)
        player.discord_id            = d.get("id")
        player.discord_username      = d.get("username")
        player.discord_discriminator = d.get("discriminator")
        player.discord_avatar        = d.get("avatar")
        player.save()

        # 4) (Optionnel) Assigne un rôle Discord via ton bot
        try:

            bot = discord.Client()

            @bot.event
            async def on_ready():
                guild  = await bot.fetch_guild(int(settings.DISCORD_GUILD_ID))
                member = await guild.fetch_member(int(d["id"]))
                await member.add_roles(discord.Object(id=int(settings.DISCORD_ROLE_ID)))
                await bot.close()

            bot.run(settings.DISCORD_BOT_TOKEN)
        except Exception:
            # en prod, log plutôt qu’un simple pass
            pass

        # 5) Redirige vers le front
        return redirect(settings.FRONTEND_URL.rstrip("/") + "/character")

    @action(detail=True, methods=['get'], url_path='me')
    def me(self, request, pk=None):
        """
        GET /players/discord/{pk}/me/
        Renvoie les infos Discord du Player dont l’ID est {pk}
        """
        try:
            player = Player.objects.get(id=pk)
        except Player.DoesNotExist:
            return Response(
                {"detail": f"Player {pk} introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response({
            "discord_id":            player.discord_id,
            "discord_username":      player.discord_username,
            "discord_discriminator": player.discord_discriminator,
            "discord_avatar":        player.discord_avatar,
        })
