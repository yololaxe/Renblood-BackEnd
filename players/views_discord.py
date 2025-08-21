from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.conf import settings

import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from .models import Player

# URLs Discord OAuth2 / API
DISCORD_API_BASE         = "https://discord.com/api/v10"
DISCORD_OAUTH_AUTHORIZE  = "https://discord.com/api/oauth2/authorize"
DISCORD_OAUTH_TOKEN      = "https://discord.com/api/oauth2/token"
DISCORD_API_USER         = "https://discord.com/api/users/@me"


class DiscordViewSet(viewsets.ViewSet):
    renderer_classes = [JSONRenderer]
    permission_classes = []      # public (on identifie via `state`)
    authentication_classes = []  # pas de session requise

    @action(detail=False, methods=['get'], url_path='link')
    def link(self, request):
        """
        GET /players/discord/link/?state=<UID>
        → renvoie {url: "..."} pour démarrer l'OAuth
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
        """
        GET /players/discord/callback/?code=...&state=<UID>
        """
        code = request.query_params.get('code')
        state = request.query_params.get('state')  # Firebase UID côté front
        if not code or not state:
            return Response(
                {"detail": "Paramètre `code` ou `state` manquant"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 1) Échange code -> access_token
        token_data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.DISCORD_REDIRECT_URI,
            "scope": "identify",
        }
        try:
            token_res = requests.post(
                DISCORD_OAUTH_TOKEN,
                data=token_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            token_res.raise_for_status()
            access_token = token_res.json().get("access_token")
        except requests.RequestException as e:
            return Response({"detail": "oauth_token_exchange_failed", "error": str(e)}, status=400)

        # 2) /users/@me
        try:
            user_res = requests.get(
                DISCORD_API_USER,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
            user_res.raise_for_status()
            d = user_res.json()
        except requests.RequestException as e:
            return Response({"detail": "discord_users_me_failed", "error": str(e)}, status=400)

        discord_id = d.get("id")
        if not discord_id:
            return Response({"detail": "discord_id_missing_in_users_me"}, status=400)

        # 3) Sauvegarde côté Player (state = id du Player attendu)
        try:
            player = Player.objects.get(id=state)
        except Player.DoesNotExist:
            return Response({"detail": f"Player {state} introuvable"}, status=status.HTTP_404_NOT_FOUND)

        player.discord_id = discord_id
        player.discord_username = d.get("username")
        player.discord_discriminator = d.get("discriminator")
        player.discord_avatar = d.get("avatar")
        player.save()

        # 4) Ajout du rôle via API REST (pas besoin de discord.py)
        try:
            guild_id = str(settings.DISCORD_GUILD_ID)
            role_id = str(settings.DISCORD_ROLE_ID)
            bot_token = settings.DISCORD_BOT_TOKEN

            url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{discord_id}/roles/{role_id}"
            headers = {"Authorization": f"Bot {bot_token}"}
            # PUT = add role
            resp = requests.put(url, headers=headers, timeout=15)
            if resp.status_code not in (200, 204):
                # on loggue mais on ne bloque pas le flow utilisateur
                print("⚠️ Impossible d'ajouter le rôle Discord :", resp.status_code, resp.text)
        except Exception as e:
            print("⚠️ Exception ajout rôle Discord :", e)

        # 5) Redirection vers le front
        return HttpResponseRedirect(settings.FRONTEND_URL.rstrip("/") + "/character")

    @action(detail=True, methods=['get'], url_path='me')
    def me(self, request, pk=None):
        """
        GET /players/discord/{pk}/me/ → infos Discord liées
        """
        try:
            p = Player.objects.get(id=pk)
        except Player.DoesNotExist:
            return Response({"detail": f"Player {pk} introuvable"}, status=404)

        return Response({
            "discord_id":            p.discord_id,
            "discord_username":      p.discord_username,
            "discord_discriminator": p.discord_discriminator,
            "discord_avatar":        p.discord_avatar,
        })

    @action(detail=True, methods=['post'], url_path='unlink')
    def unlink(self, request, pk=None):
        """
        POST /players/discord/{pk}/unlink/
        1) enlève le rôle sur le serveur (REST)
        2) vide les champs Discord sur Player
        """
        try:
            player = Player.objects.get(id=pk)
        except Player.DoesNotExist:
            return Response({"detail": "Player introuvable"}, status=404)

        # 1) retirer le rôle via REST si on a un discord_id
        if player.discord_id:
            try:
                guild_id = str(settings.DISCORD_GUILD_ID)
                role_id = str(settings.DISCORD_ROLE_ID)
                bot_token = settings.DISCORD_BOT_TOKEN
                url = f"{DISCORD_API_BASE}/guilds/{guild_id}/members/{player.discord_id}/roles/{role_id}"
                headers = {"Authorization": f"Bot {bot_token}"}
                # DELETE = remove role
                resp = requests.delete(url, headers=headers, timeout=15)
                if resp.status_code not in (200, 204):
                    print("⚠️ Impossible de retirer le rôle Discord :", resp.status_code, resp.text)
            except Exception as e:
                print("⚠️ Exception retrait rôle Discord :", e)

        # 2) vider les champs
        player.discord_id = None
        player.discord_username = None
        player.discord_discriminator = None
        player.discord_avatar = None
        player.save()

        return Response({"detail": "Discord délié avec succès"}, status=200)

    @action(detail=False, methods=['get'], url_path='online-members')
    def online_members(self, request):
        """
        GET /players/discord/online-members/
        Renvoie la liste des membres online mise en cache par le bot.
        """
        online = cache.get("discord_online_members", [])
        return Response(online)
