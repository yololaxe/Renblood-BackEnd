from functools import lru_cache, wraps
import json
import logging

from django.conf import settings
from django.http import JsonResponse, HttpResponseNotModified
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.views.decorators.gzip import gzip_page
from pymongo import MongoClient
from utils.decorators import admin_required
from .service import WikiError, WikiStore

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def store():
    client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=10000, maxPoolSize=5)
    return WikiStore(client[settings.MONGO_DB_NAME])


def safe(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try: return view(request, *args, **kwargs)
        except WikiError as error: return JsonResponse({'message': str(error)}, status=error.status)
        except Exception:
            logger.exception('Wiki publication request failed')
            return JsonResponse({'message': 'Les archives sont temporairement indisponibles. Réessayez sans republier à l’aveugle.'}, status=503)
    return wrapped


@require_GET
@gzip_page
@safe
def public(request):
    state, package = store().current()
    etag = '"' + state['version'] + '"'
    validators = request.headers.get('If-None-Match', '').split(',')
    unchanged = any(value.strip().removeprefix('W/') in {etag, '*'} for value in validators)
    response = HttpResponseNotModified() if unchanged else JsonResponse(package)
    response['ETag'] = etag
    response['Cache-Control'] = 'public, max-age=60, must-revalidate'
    return response


def body(request):
    if int(request.META.get('CONTENT_LENGTH') or 0) > 2 * 1024 * 1024: raise WikiError('Le paquet dépasse la limite de 2 Mo.', 413)
    if len(request.body) > 2 * 1024 * 1024: raise WikiError('Le paquet dépasse la limite de 2 Mo.', 413)
    try: value = json.loads(request.body)
    except (ValueError, UnicodeError): raise WikiError('Fichier JSON invalide.')
    if not isinstance(value, dict): raise WikiError('Un objet JSON est requis.')
    return value


@csrf_exempt
@admin_required
@gzip_page
@safe
def admin(request, action='overview', ident=None):
    backend = store()
    if request.method == 'GET':
        if action == 'overview': result = backend.overview()
        elif action == 'draft': result = backend.draft(ident)
        elif action == 'preview': result = backend.preview(ident)
        elif action == 'version':
            record = backend.versions.find_one({'_id': ident})
            if not record: raise WikiError('Version introuvable.', 404)
            result = record['package']
        else: raise WikiError('Action inconnue.', 404)
    elif request.method == 'POST':
        value = body(request); actor = str(request.admin_user.id)
        backend.initial()
        if action in {'draft', 'publish', 'restore'}:
            reason = value.get('reason', '')
            if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 500: raise WikiError('Indiquez un motif de 3 à 500 caractères.')
        if action == 'draft':
            if value.get('publicConfirmed') is not True: raise WikiError('Confirmez que le paquet contient uniquement du lore public.')
            result = backend.create_draft(value.get('package'), value.get('baseVersion'), actor, reason)
        elif action == 'save': result = backend.save(ident, value.get('revision'), value.get('decisions'))
        elif action == 'publish': result = {'version': backend.publish(ident, value.get('revision'), actor, reason)}
        elif action == 'restore': result = {'version': backend.restore(ident, value.get('revision'), actor, reason)}
        else: raise WikiError('Action inconnue.', 404)
    else: raise WikiError('Méthode non autorisée.', 405)
    if isinstance(result, dict) and '_id' in result: result = {**result, 'id': result['_id'], '_id': None}
    response = JsonResponse(result); response['Cache-Control'] = 'no-store'
    return response


urlpatterns = [
    path('public/', public), path('admin/', admin),
    path('admin/drafts/', admin, {'action': 'draft'}),
    path('admin/drafts/<str:ident>/', admin, {'action': 'draft'}),
    path('admin/drafts/<str:ident>/save/', admin, {'action': 'save'}),
    path('admin/drafts/<str:ident>/preview/', admin, {'action': 'preview'}),
    path('admin/drafts/<str:ident>/publish/', admin, {'action': 'publish'}),
    path('admin/versions/<str:ident>/', admin, {'action': 'version'}),
    path('admin/versions/<str:ident>/restore/', admin, {'action': 'restore'}),
]
