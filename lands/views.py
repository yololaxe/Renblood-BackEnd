from functools import lru_cache, wraps
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.gzip import gzip_page
from firebase_admin import auth
from pymongo import MongoClient
from players.models import Player
from utils.decorators import _has_server_api_key
from .service import Cadastre, LandError, coordinate, dimension, identity

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def store():
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=10000, maxPoolSize=5)
    backend = Cadastre(client[settings.MONGO_DB_NAME]); backend.initialize()
    return backend


def endpoint(view):
    @csrf_exempt
    @gzip_page
    @wraps(view)
    def wrapped(request):
        try: response = view(request)
        except LandError as error: response = JsonResponse({'message': str(error)}, status=error.status)
        except Exception:
            logger.exception('Cadastre request failed')
            response = JsonResponse({'message': 'Cadastre temporairement indisponible. Vos découvertes restent conservées en jeu.'}, status=503)
        response['Cache-Control'] = 'private, no-store'
        response['Vary'] = 'Authorization, Cookie, Accept-Encoding'
        return response
    return wrapped


def body(request, limit):
    if request.method != 'POST': raise LandError('Méthode non autorisée.', 405)
    if len(request.body) > limit: raise LandError('Requête trop volumineuse.', 413)
    try: value = json.loads(request.body)
    except (ValueError, UnicodeError): raise LandError('JSON invalide.')
    if not isinstance(value, dict): raise LandError('Objet JSON requis.')
    return value


def player(request):
    token = request.headers.get('Authorization', '')
    if not token.startswith('Bearer '): raise LandError('Connectez-vous pour consulter vos découvertes.', 401)
    try: decoded = auth.verify_id_token(token[7:])
    except Exception: raise LandError('Connexion expirée.', 401)
    try: return Player.objects.get(id=decoded['uid'])
    except Player.DoesNotExist: raise LandError('Créez votre personnage avant de consulter le cadastre.', 403)


@endpoint
def sync(request):
    if not _has_server_api_key(request): raise LandError('Accès réservé au serveur Minecraft.', 401)
    return JsonResponse(store().sync(body(request, 2 * 1024 * 1024)))


@endpoint
def map_view(request):
    if request.method != 'GET': raise LandError('Méthode non autorisée.', 405)
    user = player(request)
    admin = request.GET.get('mode') == 'admin'
    if admin and user.rank != 'Admin': raise LandError('Administration du cadastre réservée aux administrateurs.', 403)
    if not admin and not getattr(user, 'id_minecraft', None): raise LandError('Associez votre compte Minecraft pour retrouver les terres découvertes.', 403)
    try: bounds = [coordinate(int(request.GET[name])) for name in ['minX', 'minZ', 'maxX', 'maxZ']]
    except (KeyError, ValueError): raise LandError('Zone de carte invalide.')
    if not 0 <= bounds[2] - bounds[0] < 96 or not 0 <= bounds[3] - bounds[1] < 96: raise LandError('La zone doit mesurer au maximum 96 × 96 chunks.')
    dim = dimension(request.GET.get('dimension', 'minecraft:overworld'))
    return JsonResponse(store().view(request.GET.get('world', 'renblood'), user.id_minecraft, admin, bounds, dim))


@endpoint
def commands(request):
    user = player(request)
    if user.rank != 'Admin': raise LandError('Administration du cadastre réservée aux administrateurs.', 403)
    value = body(request, 65536)
    return JsonResponse(store().enqueue(value.get('world', 'renblood'), value, str(user.id)))


urlpatterns = [path('map/', map_view), path('commands/', commands), path('sync/', sync)]
