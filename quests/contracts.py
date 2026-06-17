IMPLEMENTATION_STATUSES = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE"}


def find_npc(npc_id):
    if not npc_id:
        return None

    from npcs.models import Npc

    # Djongo 1.3.6 crashes on QuerySet.exists() and values_list().first().
    return Npc.objects.filter(npc_id=npc_id).first()


def normalize_npc_id(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("npc_id", "npcId", "id", "value"):
            npc_id = normalize_npc_id(value.get(key))
            if npc_id:
                return npc_id
        return None
    raise ValueError("La reference NPC doit etre un identifiant ou un objet NPC")


def normalize_implementation(value):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("implementation doit etre un objet")

    status = value.get("status", "TODO")
    if status not in IMPLEMENTATION_STATUSES:
        raise ValueError(f"Statut d'implementation invalide: {status}")

    tasks = value.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("implementation.tasks doit etre une liste")

    normalized_tasks = []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError("Chaque tache d'implementation doit etre un objet")
        task_status = task.get("status", "TODO")
        if task_status not in IMPLEMENTATION_STATUSES:
            raise ValueError(f"Statut de tache invalide: {task_status}")
        if not task.get("label"):
            raise ValueError("Chaque tache d'implementation doit avoir un label")

        normalized_tasks.append({
            **task,
            "id": task.get("id") or f"task_{index + 1}",
            "type": task.get("type", "CUSTOM"),
            "status": task_status,
        })

    return {
        **value,
        "status": status,
        "summary": value.get("summary", ""),
        "tasks": normalized_tasks,
    }


def normalize_objectives(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("objectives doit etre une liste")

    normalized = []
    for index, objective in enumerate(value):
        if not isinstance(objective, dict):
            raise ValueError("Chaque objectif doit etre un objet")

        objective_type = objective.get("type")
        if not objective_type:
            raise ValueError("Chaque objectif doit avoir un type")

        target = objective.get("target") or {}
        if not isinstance(target, dict):
            raise ValueError("objective.target doit etre un objet")

        legacy_npc_id = normalize_npc_id(objective.get("npcId") or objective.get("npc_id"))
        if legacy_npc_id and not target.get("npcId"):
            target["npcId"] = legacy_npc_id
        elif target.get("npcId"):
            target["npcId"] = normalize_npc_id(target.get("npcId"))

        normalized.append({
            **objective,
            "id": objective.get("id") or f"objective_{index + 1}",
            "target": target,
        })

    return normalized


def objective_npc_id(objective):
    if not isinstance(objective, dict):
        return None
    target = objective.get("target")
    if isinstance(target, dict) and target.get("npcId"):
        return normalize_npc_id(target["npcId"])
    return normalize_npc_id(objective.get("npcId") or objective.get("npc_id"))


def serialize_objective(objective):
    data = dict(objective)
    npc_id = objective_npc_id(data)
    if npc_id:
        data["npcId"] = npc_id
    return data


def quest_payload(quest):
    start_npc_id = quest.startNpcId or quest.npcId or quest.npc
    completion_npc_id = quest.completionNpcId
    npc_name = quest.npcName
    completion_npc_name = None
    if start_npc_id:
        npc = find_npc(start_npc_id)
        npc_name = npc.name if npc else None
    if completion_npc_id:
        npc = find_npc(completion_npc_id)
        completion_npc_name = npc.name if npc else None
    return {
        "id": quest.questId,
        "questId": quest.questId,
        "parentId": quest.parentId,
        "name": quest.name,
        "category": quest.category,
        "type": quest.type,
        "startNpcId": start_npc_id,
        "startNpcName": npc_name,
        "completionNpcId": completion_npc_id,
        "completionNpcName": completion_npc_name,
        "description": quest.description,
        "prerequisitesAll": quest.prerequisitesAll,
        "prerequisitesAny": quest.prerequisitesAny,
        "objectives": [serialize_objective(item) for item in (quest.objectives or [])],
        "xp": quest.xp,
        "money": quest.money,
        "rewards": quest.rewards,
        "beginText": quest.beginText,
        "endText": quest.endText,
        "implementation": normalize_implementation(quest.implementation),
        # Deprecated aliases kept while clients migrate.
        "npc": start_npc_id,
        "npcId": start_npc_id,
        "npcName": npc_name,
    }


def quest_links_for_npc(npc_id, quests=None):
    from quests.models import Quest

    links = []
    for quest in quests if quests is not None else Quest.objects.all():
        roles = []
        if (quest.startNpcId or quest.npcId or quest.npc) == npc_id:
            roles.append("START")
        if quest.completionNpcId == npc_id:
            roles.append("COMPLETION")
        if any(objective_npc_id(item) == npc_id for item in (quest.objectives or [])):
            roles.append("OBJECTIVE")
        if roles:
            links.append({
                "questId": quest.questId,
                "name": quest.name,
                "roles": roles,
            })
    return links
