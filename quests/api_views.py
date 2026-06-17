import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from utils.decorators import admin_required, minecraft_api_key_or_firebase_admin_required

from .contracts import (
    find_npc,
    normalize_implementation,
    normalize_npc_id,
    normalize_objectives,
    quest_payload,
)
from .models import Quest


def _validate_npc_id(npc_id, field):
    if npc_id and not find_npc(npc_id):
        raise ValueError(f"{field}: NPC introuvable: {npc_id}")


def _npc_name(npc_id):
    npc = find_npc(npc_id)
    return npc.name if npc else None


def _quest_values(data, existing=None):
    start_npc_id = normalize_npc_id(
        data.get("startNpcId") or data.get("npcId") or data.get("npc_id") or data.get("npc")
    )
    completion_npc_id = normalize_npc_id(data.get("completionNpcId") or data.get("completionNpc"))
    if existing:
        if not any(key in data for key in ("startNpcId", "npcId", "npc_id", "npc")):
            start_npc_id = existing.startNpcId or existing.npcId or existing.npc
        if not any(key in data for key in ("completionNpcId", "completionNpc")):
            completion_npc_id = existing.completionNpcId

    objectives = normalize_objectives(
        data.get("objectives", existing.objectives if existing else [])
    )
    implementation = normalize_implementation(
        data.get("implementation", existing.implementation if existing else None)
    )

    _validate_npc_id(start_npc_id, "startNpcId")
    _validate_npc_id(completion_npc_id, "completionNpcId")
    for objective in objectives:
        _validate_npc_id(objective.get("target", {}).get("npcId"), "objective.target.npcId")

    return start_npc_id, completion_npc_id, objectives, implementation


@csrf_exempt
def list_quests(request):
    if request.method != "GET":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    quests = Quest.objects.all()
    category = request.GET.get("category")
    if category:
        quests = quests.filter(category=category)
    return JsonResponse([quest_payload(quest) for quest in quests], safe=False)


@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def create_quest(request):
    if request.method != "POST":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    try:
        data = json.loads(request.body)
        for field in ("questId", "name", "category"):
            if not data.get(field):
                return JsonResponse({"error": f"Champ obligatoire manquant : {field}"}, status=400)

        start_npc_id, completion_npc_id, objectives, implementation = _quest_values(data)
        quest = Quest.objects.create(
            questId=data["questId"],
            parentId=data.get("parentId"),
            name=data["name"],
            category=data["category"],
            type=data.get("type", "Solo"),
            npc=start_npc_id,
            npcId=start_npc_id,
            npcName=_npc_name(start_npc_id),
            startNpcId=start_npc_id,
            completionNpcId=completion_npc_id,
            description=data.get("description", {}),
            prerequisitesAll=data.get("prerequisitesAll", []),
            prerequisitesAny=data.get("prerequisitesAny", []),
            objectives=objectives,
            xp=data.get("xp", {}),
            money=data.get("money", 0),
            rewards=data.get("rewards", []),
            beginText=data.get("beginText", {}),
            endText=data.get("endText", {}),
            implementation=implementation,
        )
        return JsonResponse(quest_payload(quest), status=201)
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@csrf_exempt
def quest_detail(request, quest_id):
    quest = get_object_or_404(Quest, questId=quest_id)
    if request.method == "GET":
        return JsonResponse(quest_payload(quest))

    @minecraft_api_key_or_firebase_admin_required
    def protected_view(protected_request):
        if protected_request.method == "DELETE":
            quest.delete()
            return JsonResponse({"message": "Quete supprimee avec succes"})
        if protected_request.method != "PUT":
            return JsonResponse({"error": "Methode non autorisee"}, status=405)
        try:
            data = json.loads(protected_request.body)
            start_npc_id, completion_npc_id, objectives, implementation = _quest_values(data, quest)
            quest.startNpcId = start_npc_id
            quest.completionNpcId = completion_npc_id
            quest.npc = start_npc_id
            quest.npcId = start_npc_id
            quest.npcName = _npc_name(start_npc_id)
            quest.objectives = objectives
            quest.implementation = implementation

            blocked = {
                "questId", "id", "npc", "npcId", "npcName", "npc_id", "npc_name",
                "startNpcId", "completionNpcId", "objectives", "implementation",
            }
            for field, value in data.items():
                if field not in blocked and hasattr(quest, field):
                    setattr(quest, field, value)
            quest.save()
            return JsonResponse(quest_payload(quest))
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=500)

    return protected_view(request)


@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def update_quest_start_npc(request, quest_id):
    if request.method != "PUT":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    try:
        data = json.loads(request.body)
        npc_id = normalize_npc_id(data.get("startNpcId") or data.get("npc"))
        _validate_npc_id(npc_id, "startNpcId")
        quest = get_object_or_404(Quest, questId=quest_id)
        quest.startNpcId = npc_id
        quest.npc = npc_id
        quest.npcId = npc_id
        quest.npcName = _npc_name(npc_id)
        quest.save(update_fields=["startNpcId", "npc", "npcId", "npcName"])
        return JsonResponse(quest_payload(quest))
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
@minecraft_api_key_or_firebase_admin_required
def update_quest_objective_npc(request, quest_id):
    if request.method != "PUT":
        return JsonResponse({"error": "Methode non autorisee"}, status=405)
    try:
        data = json.loads(request.body)
        index = data.get("objective_index")
        npc_id = normalize_npc_id(data.get("npcId") or data.get("npc"))
        _validate_npc_id(npc_id, "objective.target.npcId")
        quest = get_object_or_404(Quest, questId=quest_id)
        objectives = normalize_objectives(quest.objectives)
        if not isinstance(index, int) or index < 0 or index >= len(objectives):
            raise ValueError("Index d'objectif invalide")
        objectives[index]["target"]["npcId"] = npc_id
        quest.objectives = objectives
        quest.save(update_fields=["objectives"])
        return JsonResponse(quest_payload(quest))
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
