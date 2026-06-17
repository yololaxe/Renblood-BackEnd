from functools import wraps
import secrets

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from firebase_admin import auth
from players.models import Player
from .firebase_setup import initialize_firebase

# Initialisation de Firebase Admin SDK
initialize_firebase()

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Vérifier la présence du token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authorization header manquant ou invalide'}, status=401)

        id_token = auth_header.split('Bearer ')[1]

        try:
            # 2. Vérifier le token avec Firebase
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token['uid']

            # 3. Récupérer le joueur
            try:
                player = Player.objects.get(id=uid)
            except Player.DoesNotExist:
                return JsonResponse({'error': 'Joueur non trouvé'}, status=403)

            # 4. Vérifier le rang Admin
            if player.rank != 'Admin':
                return JsonResponse({'error': 'Accès refusé. Administrateur requis.'}, status=403)
            
            # Ajoute l'admin authentifié à la requête pour un usage ultérieur si besoin
            request.admin_user = player

        except auth.InvalidIdTokenError:
            return JsonResponse({'error': 'Token Firebase invalide'}, status=401)
        except Exception as e:
            return JsonResponse({'error': f'Erreur de vérification: {str(e)}'}, status=500)

        return view_func(request, *args, **kwargs)
    return _wrapped_view


def _request_api_key(request):
    supplied_api_key = request.headers.get("X-API-KEY")
    if supplied_api_key:
        return supplied_api_key

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split("Bearer ", 1)[1]
    return None


def _has_server_api_key(request):
    expected_api_key = getattr(settings, "API_KEY_RENBLOOD", None)
    supplied_api_key = _request_api_key(request)
    return bool(
        expected_api_key
        and supplied_api_key
        and secrets.compare_digest(str(expected_api_key), str(supplied_api_key))
    )


def minecraft_admin_or_firebase_admin_required(view_func):
    """
    Accept a website Firebase admin or a Minecraft admin authenticated by the
    shared server API key.
    """
    firebase_protected_view = admin_required(view_func)

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        supplied_api_key = _request_api_key(request)

        if _has_server_api_key(request):
            minecraft_identity = (
                request.headers.get("X-Minecraft-UUID")
                or request.headers.get("X-Minecraft-Id")
                or request.headers.get("X-Minecraft-Username")
                or request.headers.get("X-Minecraft-Pseudo")
            )
            if not minecraft_identity:
                return JsonResponse(
                    {
                        "error": (
                            "Identité Minecraft manquante. Utilisez "
                            "X-Minecraft-UUID ou X-Minecraft-Username."
                        )
                    },
                    status=401,
                )

            try:
                player = Player.objects.get(
                    Q(id_minecraft=minecraft_identity)
                    | Q(pseudo_minecraft=minecraft_identity)
                )
            except Player.DoesNotExist:
                return JsonResponse({"error": "Joueur Minecraft non trouvé"}, status=403)

            if player.rank != "Admin":
                return JsonResponse(
                    {"error": "Accès refusé. Administrateur requis."},
                    status=403,
                )

            request.admin_user = player
            return view_func(request, *args, **kwargs)

        if supplied_api_key:
            return JsonResponse({"error": "Clé API Minecraft invalide"}, status=401)

        return firebase_protected_view(request, *args, **kwargs)

    return _wrapped_view


def minecraft_api_key_or_firebase_admin_required(view_func):
    """
    Accept a trusted Minecraft server request authenticated by the shared API
    key, or fall back to a website Firebase admin.
    """
    firebase_protected_view = admin_required(view_func)

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        supplied_api_key = _request_api_key(request)

        if _has_server_api_key(request):
            return view_func(request, *args, **kwargs)

        if supplied_api_key:
            return JsonResponse({"error": "Clé API Minecraft invalide"}, status=401)

        return firebase_protected_view(request, *args, **kwargs)

    return _wrapped_view
