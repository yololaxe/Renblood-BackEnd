"""Admin-only identity directory; public NPC responses contain lore links only."""
from functools import lru_cache, wraps
import json
import logging
from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.gzip import gzip_page
from pymongo import MongoClient
from utils.decorators import admin_required
from wiki.service import WikiError
from .service import Directory, DirectoryError

logger=logging.getLogger(__name__)

@lru_cache(maxsize=1)
def directory():
    client=MongoClient(settings.MONGO_URI,serverSelectionTimeoutMS=3000,connectTimeoutMS=3000,socketTimeoutMS=10000,maxPoolSize=5)
    return Directory(client[settings.MONGO_DB_NAME])

def flush_identity_changes(backend=None):
    """Durable outbox: a failed notification is retried by the next mod poll.

    Repeated UPSERT notifications are safe; never acknowledge before record_change.
    """
    from npcs.change_log import record_change
    backend=backend or directory()
    for row in backend.outbox.find({'sent':False}).sort('created_at',1).limit(30):
        record_change('NPC',row['npc_id'],'UPSERT')
        backend.outbox.update_one({'_id':row['_id']},{'$set':{'sent':True}})

def public_bindings(ids):
    return directory().public_links(ids) if ids else {}

def safe(view):
    @wraps(view)
    def wrapped(request,*args,**kwargs):
        try:response=view(request,*args,**kwargs)
        except (DirectoryError,WikiError) as exc:response=JsonResponse({'message':str(exc)},status=exc.status)
        except Exception:
            logger.exception('Character directory request failed')
            response=JsonResponse({'message':'Répertoire indisponible. Recharge son état avant de renouveler une modification.'},status=503)
        response['Cache-Control']='no-store'
        return response
    return wrapped

def body(request):
    if len(request.body)>100000:raise DirectoryError('Fiche trop volumineuse.',413)
    try:value=json.loads(request.body)
    except (ValueError,UnicodeError):raise DirectoryError('JSON invalide.')
    if not isinstance(value,dict):raise DirectoryError('Un objet JSON est requis.')
    return value

@csrf_exempt
@admin_required
@gzip_page
@safe
def admin(request,action='inventory',ident=None):
    backend=directory()
    if request.method=='GET':
        if action=='inventory':result=backend.inventory()
        elif action=='lore':result=backend.lore(ident)
        else:raise DirectoryError('Méthode non autorisée.',405)
    elif request.method=='POST':
        value=body(request);actor=str(request.admin_user.id)
        if action=='bind':result=backend.bind(value,actor)
        elif action=='create-profile':result=backend.create_profile(value,actor)
        elif action=='prepare':result=backend.prepare_lore(value,actor)
        elif action=='publish':result=backend.publish_lore(value,actor)
        else:raise DirectoryError('Méthode non autorisée.',405)
        if action in ['bind','create-profile']:
            try:flush_identity_changes(backend);result['sync']='queued'
            except Exception:logger.exception('Identity notification pending; outbox will retry')
    else:raise DirectoryError('Méthode non autorisée.',405)
    return JsonResponse(result)

urlpatterns=[path('admin/',admin),path('admin/bind/',admin,{'action':'bind'}),
    path('admin/profiles/',admin,{'action':'create-profile'}),path('admin/lore/<str:ident>/',admin,{'action':'lore'}),
    path('admin/prepare/',admin,{'action':'prepare'}),path('admin/publish/',admin,{'action':'publish'})]
