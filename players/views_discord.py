from django.core.cache import cache

import requests
from django.http import HttpResponseRedirect
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from django.conf import settings
import discord
from .models import Player

# URLs Discord OAuth2
DISCORD_OAUTH_AUTHORIZE = "https://discord.com/api/oauth2/authorize"
DISCORD_OAUTH_TOKEN     = "https://discord.com/api/oauth2/token"
DISCORD_API_USER        = "https://discord.com/api/users/@me"

class DiscordViewSet(viewsets.ViewSet):
    renderer_classes = [JSONRenderer]
    permission_classes = []      # ouvert pour tout le monde (on lie via le param state)
    authentication_classes = []  # pas de session requise pour link()

    @action(detail=False, methods=['get'], url_path='link')
    def link(self, request):
        """
        GET /players/discord/link/?state=<UID>
        → ne renvoie plus de 302, mais un JSON {url: …}
        """
        uid = request.query_params.get("state")
        if not uid:
            return Response({"detail": "`state` (UID) manquant"}, status=status.HTTP_400_BAD_REQUEST)

        params = {
            "client_id":     settings.DISCORD_CLIENT_ID,
            "redirect_uri":  settings.DISCORD_REDIRECT_URI,
            "response_type": "code",
            "scope":         "identify",
            "state":         uid,
        }
        url = f"{DISCORD_OAUTH_AUTHORIZE}?{requests.compat.urlencode(params)}"
        return Response({"url": url}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='callback')
    def callback(self, request):
        code = request.query_params.get('code')
        state = request.query_params.get('state')  # notre Firebase UID
        if not code or not state:
            return Response(
                {"detail": "Paramètre `code` ou `state` manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1) Récupérer access_token
        token_data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.DISCORD_REDIRECT_URI,
            "scope": "identify",
        }
        token_res = requests.post(
            DISCORD_OAUTH_TOKEN,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")

        # 2) Récupérer les infos utilisateur Discord
        user_res = requests.get(
            DISCORD_API_USER,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_res.raise_for_status()
        d = user_res.json()
        discord_id = d.get("id")

        # 3) Sauvegarder dans le modèle Player (on utilise `state` comme ID)
        try:
            player = Player.objects.get(id=state)
        except Player.DoesNotExist:
            return Response(
                {"detail": f"Player {state} introuvable"},
                status=status.HTTP_404_NOT_FOUND
            )
        player.discord_id = discord_id
        player.discord_username = d.get("username")
        player.discord_discriminator = d.get("discriminator")
        player.discord_avatar = d.get("avatar")
        player.save()

        # 4) Ajouter le rôle Discord via l’API HTTP
        try:
            guild_id = settings.DISCORD_GUILD_ID
            role_id = settings.DISCORD_ROLE_ID
            bot_token = settings.DISCORD_BOT_TOKEN

            url = (
                f"https://discord.com/api/v10"
                f"/guilds/{guild_id}"
                f"/members/{discord_id}"
                f"/roles/{role_id}"
            )
            headers = {
                "Authorization": f"Bot {bot_token}"
            }
            resp = requests.put(url, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            # En prod, logger l’erreur
            print("⚠️ Impossible d'ajouter le rôle Discord :", e)

        # 5) Redirection finale vers le front
        return HttpResponseRedirect(settings.FRONTEND_URL.rstrip("/") + "/character")

    @action(detail=True, methods=['get'], url_path='me')
    def me(self, request, pk=None):
        """
        GET /players/discord/{pk}/me/
        Renvoie le Discord lié pour le Player {pk}
        """
        try:
            p = Player.objects.get(id=pk)
        except Player.DoesNotExist:
            return Response({"detail": f"Player {pk} introuvable"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "discord_id":            p.discord_id,
            "discord_username":      p.discord_username,
            "discord_discriminator": p.discord_discriminator,
            "discord_avatar":        p.discord_avatar,
        })

    @action(detail=True, methods=['post'], url_path='unlink')
    def unlink(self, request, pk=None):
        """
        POST /players/discord/unlink/
        1) enlève le rôle Discord sur le serveur
        2) vide discord_id, username, discriminator, avatar
        3) renvoie 200 OK
        """

        try:
            player = Player.objects.get(id=pk)
        except Player.DoesNotExist:
            return Response({"detail": "Player introuvable"}, status=status.HTTP_404_NOT_FOUND)

        # 1) enlevez le rôle via votre bot
        if player.discord_id:
            try:
                bot = discord.Client()

                @bot.event
                async def on_ready():
                    guild = await bot.fetch_guild(int(settings.DISCORD_GUILD_ID))
                    member = await guild.fetch_member(int(player.discord_id))
                    await member.remove_roles(discord.Object(id=int(settings.DISCORD_ROLE_ID)))
                    await bot.close()

                bot.run(settings.DISCORD_BOT_TOKEN)
            except Exception:
                # loggez en prod plutôt que passer
                pass

        # 2) videz les champs
        player.discord_id = None
        player.discord_username = None
        player.discord_discriminator = None
        player.discord_avatar = None
        player.save()

        return Response({"detail": "Discord dél ié avec succès"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='online-members')
    def online_members(self, request):
        """
        GET /players/discord/online-members/
        Renvoie la liste des membres online mise en cache par PresenceBot.
        """
        online = cache.get("discord_online_members", [])
        return Response(online)