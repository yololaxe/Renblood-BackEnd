import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from utils.decorators import minecraft_api_key_or_firebase_admin_required
from .placement import Placements, PlacementError
from .change_log import change_writer
from .models import NpcSpawn
from .api_views import spawn_payload


@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def manage_spawn(request, spawn_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    try:
        body = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'error': 'JSON invalide'}, status=400)
    try:
        actor = request.headers.get('X-Minecraft-UUID') or 'web:admin'
        Placements(change_writer().db).edit(spawn_id, body, actor)
        spawn = NpcSpawn.objects.select_related('npc').get(spawn_id=spawn_id)
        return JsonResponse(spawn_payload(spawn))
    except PlacementError as error:
        return JsonResponse({'error': str(error)}, status=error.status)
