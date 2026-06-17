import json

from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from quests.contracts import normalize_implementation, quest_links_for_npc
from utils.decorators import admin_required, minecraft_api_key_or_firebase_admin_required

from .models import Npc


JSON_DEFAULTS = {
    "dialogue": list,
    "tags": list,
    "met_by": list,
    "ambient_lines": list,
    "dialogue_by_state": dict,
}


def npc_payload(npc, quests=None):
    quest_links = quest_links_for_npc(npc.npc_id, quests)
    return {
        "npc_id": npc.npc_id,
        "name": npc.name,
        "type": npc.type,
        "skin": npc.skin,
        "dialogue": npc.dialogue,
        "tags": npc.tags,
        "enabled": npc.enabled,
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


@csrf_exempt
def list_npcs(request):
    if request.method != "GET":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    from quests.models import Quest

    quests = list(Quest.objects.all())
    return JsonResponse([npc_payload(npc, quests) for npc in Npc.objects.all()], safe=False)


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
            return JsonResponse(npc_payload(npc))
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)

    return protected_view(request)
