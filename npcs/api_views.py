import json

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from quests.contracts import normalize_implementation, quest_links_by_npc, quest_links_for_npc
from utils.decorators import admin_required, minecraft_api_key_or_firebase_admin_required

from .models import Npc, NpcSpawn, NpcChange
from .change_log import record_change


JSON_DEFAULTS = {
    "dialogue": list,
    "tags": list,
    "met_by": list,
    "ambient_lines": list,
    "dialogue_by_state": dict,
}


def npc_payload(npc, links=None, identities=None):
    from characters.views import public_bindings
    identity=(identities if identities is not None else public_bindings([npc.npc_id])).get(npc.npc_id,{})
    quest_links = quest_links_for_npc(npc.npc_id) if links is None else links.get(npc.npc_id, [])
    return {
        "npc_id": npc.npc_id,
        "name": npc.name,
        "type": npc.type,
        "skin": npc.skin,
        "dialogue": npc.dialogue,
        "tags": npc.tags,
        "configured_enabled": npc.enabled,
        "enabled": npc.enabled and not identity.get("archived",False) and not identity.get("automatic_spawn_blocked",False),
        **identity,
        "description": npc.description,
        "profile_image": npc.profile_image,
        "met_by": npc.met_by,
        "region": npc.region,
        "idle_behavior": npc.idle_behavior,
        "ambient_lines": npc.ambient_lines,
        "shop_id": npc.shop_id,
        "currency": npc.currency,
        "open_message": npc.open_message,
        "trade_category": npc.trade_category,
        "dialogue_by_state": npc.dialogue_by_state,
        "implementation": normalize_implementation(npc.implementation),
        "quest_links": quest_links,
    }


def spawn_payload(spawn, links=None, identities=None):
    from characters.views import public_bindings
    npc = spawn.npc
    identity=(identities if identities is not None else public_bindings([npc.npc_id])).get(npc.npc_id,{})
    return {
        "spawn_id": spawn.spawn_id,
        "npc_id": npc.npc_id,
        "npc_name": npc.name,
        "npc_type": npc.type,
        "npc_skin": npc.skin,
        "world": spawn.world,
        "x": spawn.x,
        "y": spawn.y,
        "z": spawn.z,
        "yaw": spawn.yaw,
        "pitch": spawn.pitch,
        "spawn_rule": spawn.spawn_rule,
        "active": spawn.active and npc.enabled and not identity.get("archived",False) and not identity.get("automatic_spawn_blocked",False),
        **identity,
        "meta": spawn.meta,
        "dialogue": npc.dialogue,
        "quest_links": quest_links_for_npc(npc.npc_id) if links is None else links.get(npc.npc_id, []),
        "implementation": normalize_implementation(npc.implementation),
    }


@csrf_exempt
def npc_changes(request):
    if request.method != "GET":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    try:
        since = max(0, int(request.GET.get("since", 0)))
    except (TypeError, ValueError):
        return JsonResponse({"error": "since doit etre un entier"}, status=400)

    from characters.views import flush_identity_changes, public_bindings
    flush_identity_changes()
    changes = list(NpcChange.objects.filter(revision__gt=since).order_by("revision"))
    latest = changes[-1].revision if changes else since
    npc_ids = {change.entity_id for change in changes if change.entity_type == "NPC" and change.action == "UPSERT"}
    spawn_ids = {change.entity_id for change in changes if change.entity_type == "SPAWN" and change.action == "UPSERT"}
    removed_npcs = {change.entity_id for change in changes if change.entity_type == "NPC" and change.action == "DELETE"}
    removed_spawns = {change.entity_id for change in changes if change.entity_type == "SPAWN" and change.action == "DELETE"}

    if npc_ids:
        spawn_ids.update(NpcSpawn.objects.filter(npc_id__in=npc_ids).values_list("spawn_id", flat=True))

    npcs = list(Npc.objects.filter(npc_id__in=npc_ids))
    spawns = list(NpcSpawn.objects.filter(spawn_id__in=spawn_ids).select_related("npc"))
    identities=public_bindings({n.npc_id for n in npcs}|{s.npc_id for s in spawns})
    from quests.models import Quest

    links = quest_links_by_npc(Quest.objects.all()) if npc_ids or spawn_ids else {}
    return JsonResponse({
        "revision": latest,
        "npcs": [npc_payload(npc, links, identities) for npc in npcs],
        "spawns": [spawn_payload(spawn, links, identities) for spawn in spawns],
        "removed_npcs": sorted(removed_npcs),
        "removed_spawns": sorted(removed_spawns),
    })


@csrf_exempt
def list_npcs(request):
    if request.method != "GET":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    from quests.models import Quest

    links = quest_links_by_npc(Quest.objects.all())
    from characters.views import public_bindings
    npcs=list(Npc.objects.all());identities=public_bindings([n.npc_id for n in npcs])
    return JsonResponse([npc_payload(npc, links, identities) for npc in npcs], safe=False)


@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def create_npc(request):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    try:
        data = json.loads(request.body)
        for field in ("npc_id", "name", "type"):
            if not data.get(field):
                return JsonResponse({"error": f"Champ obligatoire manquant : {field}"}, status=400)
        npc = Npc.objects.create(
            npc_id=data["npc_id"],
            name=data["name"],
            type=data["type"],
            skin=data.get("skin"),
            dialogue=data.get("dialogue", []),
            tags=data.get("tags", []),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            profile_image=data.get("profile_image", "NPCdefault.png"),
            met_by=data.get("met_by", []),
            region=data.get("region", "Royaume de Renblood"),
            idle_behavior=data.get("idle_behavior"),
            ambient_lines=data.get("ambient_lines", []),
            shop_id=data.get("shop_id"),
            currency=data.get("currency"),
            open_message=data.get("open_message"),
            trade_category=data.get("trade_category"),
            dialogue_by_state=data.get("dialogue_by_state", {}),
            implementation=normalize_implementation(data.get("implementation")),
        )
        record_change("NPC", npc.npc_id, "UPSERT")
        return JsonResponse(npc_payload(npc), status=201)
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "Un NPC avec cet ID existe deja"}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def npc_detail(request, npc_id):
    npc = get_object_or_404(Npc, npc_id=npc_id)
    if request.method == "GET":
        return JsonResponse(npc_payload(npc))

    @minecraft_api_key_or_firebase_admin_required
    def protected_view(protected_request):
        if protected_request.method == "DELETE":
            from characters.views import public_bindings
            if quest_links_for_npc(npc_id) or public_bindings([npc_id]).get(npc_id):
                return JsonResponse({"error":"Ce profil est lié à des quêtes ou à une fiche personnage. Archive-le dans le Répertoire pour préserver ses références.","directory":"/admin/characters"},status=409)
            for spawn_id in NpcSpawn.objects.filter(npc=npc).values_list("spawn_id", flat=True):
                record_change("SPAWN", spawn_id, "DELETE")
            record_change("NPC", npc.npc_id, "DELETE")
            npc.delete()
            return JsonResponse({"message": "NPC supprime"})
        if protected_request.method != "PUT":
            return JsonResponse({"error": "Methode non autorisee"}, status=405)
        try:
            data = json.loads(protected_request.body)
            blocked = {"npc_id", "quest_ids", "quest_giver", "quest_validator", "quest_links"}
            for field, value in data.items():
                if field == "implementation":
                    value = normalize_implementation(value)
                if field in JSON_DEFAULTS and value is None:
                    value = JSON_DEFAULTS[field]()
                if field not in blocked and hasattr(npc, field):
                    setattr(npc, field, value)
            npc.save()
            record_change("NPC", npc.npc_id, "UPSERT")
            return JsonResponse(npc_payload(npc))
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)

    return protected_view(request)
