from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from .models import Npc, NpcSpawn
import json

@csrf_exempt
def list_npcs(request):
    """
    GET /npcs/list/
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    npcs = Npc.objects.all()
    data = []
    for npc in npcs:
        data.append({
            "npc_id": npc.npc_id,
            "name": npc.name,
            "type": npc.type,
            "skin": npc.skin,
            "dialogue": npc.dialogue,
            "tags": npc.tags,
            "enabled": npc.enabled,
            # Champs spécifiques
            "shop_id": npc.shop_id,
            "quest_ids": npc.quest_ids,
            "dialogue_by_state": npc.dialogue_by_state
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def create_npc(request):
    """
    POST /npcs/create/
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        
        required_fields = ["npc_id", "name", "type"]
        for field in required_fields:
            if field not in data:
                return JsonResponse({"error": f"Champ obligatoire manquant : {field}"}, status=400)

        npc = Npc.objects.create(
            npc_id=data["npc_id"],
            name=data["name"],
            type=data["type"],
            skin=data.get("skin"),
            dialogue=data.get("dialogue", []),
            tags=data.get("tags", []),
            enabled=data.get("enabled", True),
            
            # DECO
            idle_behavior=data.get("idle_behavior"),
            ambient_lines=data.get("ambient_lines", []),
            
            # SHOPKEEPER
            shop_id=data.get("shop_id"),
            currency=data.get("currency"),
            open_message=data.get("open_message"),
            trade_category=data.get("trade_category"),
            
            # QUEST
            quest_giver=data.get("quest_giver", False),
            quest_validator=data.get("quest_validator", False),
            quest_ids=data.get("quest_ids", []),
            dialogue_by_state=data.get("dialogue_by_state", {})
        )
        
        return JsonResponse({"message": "NPC créé avec succès", "npc_id": npc.npc_id}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "Un NPC avec cet ID existe déjà"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def npc_detail(request, npc_id):
    """
    GET /npcs/<npc_id>/
    PUT /npcs/<npc_id>/
    DELETE /npcs/<npc_id>/
    """
    npc = get_object_or_404(Npc, npc_id=npc_id)

    if request.method == "GET":
        data = {
            "npc_id": npc.npc_id,
            "name": npc.name,
            "type": npc.type,
            "skin": npc.skin,
            "dialogue": npc.dialogue,
            "tags": npc.tags,
            "enabled": npc.enabled,
            "idle_behavior": npc.idle_behavior,
            "ambient_lines": npc.ambient_lines,
            "shop_id": npc.shop_id,
            "currency": npc.currency,
            "open_message": npc.open_message,
            "trade_category": npc.trade_category,
            "quest_giver": npc.quest_giver,
            "quest_validator": npc.quest_validator,
            "quest_ids": npc.quest_ids,
            "dialogue_by_state": npc.dialogue_by_state
        }
        return JsonResponse(data)

    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            for field, value in data.items():
                if hasattr(npc, field):
                    setattr(npc, field, value)
            npc.save()
            return JsonResponse({"message": "NPC mis à jour", "npc_id": npc.npc_id})
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON invalide"}, status=400)

    elif request.method == "DELETE":
        npc.delete()
        return JsonResponse({"message": "NPC supprimé"})

    else:
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

# --- SPAWNS ---

@csrf_exempt
def list_spawns(request):
    """
    GET /npcs/spawns/list/
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    spawns = NpcSpawn.objects.all()
    data = []
    for spawn in spawns:
        data.append({
            "spawn_id": spawn.spawn_id,
            "npc_id": spawn.npc.npc_id,
            "world": spawn.world,
            "x": spawn.x,
            "y": spawn.y,
            "z": spawn.z,
            "yaw": spawn.yaw,
            "pitch": spawn.pitch,
            "spawn_rule": spawn.spawn_rule,
            "active": spawn.active,
            "meta": spawn.meta
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def create_spawn(request):
    """
    POST /npcs/spawns/create/
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        
        required_fields = ["spawn_id", "npc_id", "x", "y", "z"]
        for field in required_fields:
            if field not in data:
                return JsonResponse({"error": f"Champ obligatoire manquant : {field}"}, status=400)

        # Gestion explicite de Npc.DoesNotExist
        try:
            npc = Npc.objects.get(npc_id=data["npc_id"])
        except Npc.DoesNotExist:
            return JsonResponse({"error": f"NPC introuvable avec l'ID : {data['npc_id']}"}, status=404)

        # Conversion des coordonnées en float pour éviter les erreurs de type
        try:
            x = float(data["x"])
            y = float(data["y"])
            z = float(data["z"])
            yaw = float(data.get("yaw", 0.0))
            pitch = float(data.get("pitch", 0.0))
        except (ValueError, TypeError):
            return JsonResponse({"error": "Les coordonnées (x, y, z, yaw, pitch) doivent être des nombres"}, status=400)

        spawn = NpcSpawn.objects.create(
            spawn_id=data["spawn_id"],
            npc=npc,
            world=data.get("world", "world"),
            x=x,
            y=y,
            z=z,
            yaw=yaw,
            pitch=pitch,
            spawn_rule=data.get("spawn_rule", "STATIC"),
            active=data.get("active", True),
            meta=data.get("meta", {})
        )
        
        return JsonResponse({"message": "Spawn créé avec succès", "spawn_id": spawn.spawn_id}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "Un spawn avec cet ID existe déjà"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def get_spawns_by_world(request, world_name):
    """
    GET /npcs/spawns/world/<world_name>/
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    spawns = NpcSpawn.objects.filter(world=world_name, active=True)
    data = []
    for spawn in spawns:
        data.append({
            "spawn_id": spawn.spawn_id,
            "npc_id": spawn.npc.npc_id,
            "npc_name": spawn.npc.name,
            "npc_type": spawn.npc.type,
            "npc_skin": spawn.npc.skin,
            "x": spawn.x,
            "y": spawn.y,
            "z": spawn.z,
            "yaw": spawn.yaw,
            "pitch": spawn.pitch,
            "spawn_rule": spawn.spawn_rule,
            "meta": spawn.meta,
            # On peut inclure des données du NPC ici pour éviter une 2ème requête
            "dialogue": spawn.npc.dialogue,
            "quest_ids": spawn.npc.quest_ids
        })
    return JsonResponse(data, safe=False)
