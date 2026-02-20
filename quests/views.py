from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Quest, PlayerQuestState
import json

@csrf_exempt
def list_quests(request):
    """
    GET /quests/list/
    Renvoie la liste de toutes les quêtes.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    quests = Quest.objects.all()
    data = []
    for quest in quests:
        data.append({
            "questId": quest.questId,
            "parentId": quest.parentId,
            "name": quest.name,
            "category": quest.category,
            "type": quest.type,
            "npc": quest.npc,
            "description": quest.description,
            "prerequisitesAll": quest.prerequisitesAll,
            "prerequisitesAny": quest.prerequisitesAny,
            "objectives": quest.objectives,
            "xp": quest.xp,
            "money": quest.money,
            "rewards": quest.rewards,
            "beginText": quest.beginText,
            "endText": quest.endText,
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def create_quest(request):
    """
    POST /quests/create/
    Crée une nouvelle quête.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        
        # Validation basique
        required_fields = ["questId", "name", "category"]
        for field in required_fields:
            if field not in data:
                return JsonResponse({"error": f"Champ obligatoire manquant : {field}"}, status=400)

        quest = Quest.objects.create(
            questId=data["questId"],
            parentId=data.get("parentId"),
            name=data["name"],
            category=data["category"],
            type=data.get("type", "Solo"),
            npc=data.get("npc"),
            description=data.get("description", {}),
            prerequisitesAll=data.get("prerequisitesAll", []),
            prerequisitesAny=data.get("prerequisitesAny", []),
            objectives=data.get("objectives", []),
            xp=data.get("xp", {}),
            money=data.get("money", 0),
            rewards=data.get("rewards", []),
            beginText=data.get("beginText", {}),
            endText=data.get("endText", {})
        )
        
        return JsonResponse({"message": "Quête créée avec succès", "questId": quest.questId}, status=201)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def quest_detail(request, quest_id):
    """
    GET /quests/<quest_id>/ : Récupérer les détails d'une quête
    PUT /quests/<quest_id>/ : Modifier une quête
    DELETE /quests/<quest_id>/ : Supprimer une quête
    """
    quest = get_object_or_404(Quest, questId=quest_id)

    if request.method == "GET":
        data = {
            "questId": quest.questId,
            "parentId": quest.parentId,
            "name": quest.name,
            "category": quest.category,
            "type": quest.type,
            "npc": quest.npc,
            "description": quest.description,
            "prerequisitesAll": quest.prerequisitesAll,
            "prerequisitesAny": quest.prerequisitesAny,
            "objectives": quest.objectives,
            "xp": quest.xp,
            "money": quest.money,
            "rewards": quest.rewards,
            "beginText": quest.beginText,
            "endText": quest.endText,
        }
        return JsonResponse(data)

    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
            
            # Mise à jour des champs
            for field, value in data.items():
                if hasattr(quest, field):
                    setattr(quest, field, value)
            
            quest.save()
            return JsonResponse({"message": "Quête mise à jour avec succès", "questId": quest.questId})
        
        except json.JSONDecodeError:
            return JsonResponse({"error": "JSON invalide"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "DELETE":
        quest.delete()
        return JsonResponse({"message": "Quête supprimée avec succès"})

    else:
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

@csrf_exempt
def get_player_quests(request, player_id):
    """
    GET /quests/player/<player_id>/
    Récupère toutes les quêtes d'un joueur avec leur statut.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    player_quests = PlayerQuestState.objects.filter(player_id=player_id)
    data = []
    for pq in player_quests:
        data.append({
            "quest_id": pq.quest_id,
            "status": pq.status,
            "startedAt": pq.startedAt,
            "completedAt": pq.completedAt,
            "members": pq.members
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def update_player_quest_status(request, player_id):
    """
    POST /quests/player/<player_id>/update/
    Met à jour le statut d'une quête pour un joueur.
    Body: { "quest_id": "m1.1", "status": "IN_PROGRESS" }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        quest_id = data.get("quest_id")
        new_status = data.get("status")

        if not quest_id or not new_status:
            return JsonResponse({"error": "quest_id et status sont requis"}, status=400)

        if new_status not in dict(PlayerQuestState.STATUS_CHOICES):
            return JsonResponse({"error": "Statut invalide"}, status=400)

        # Récupérer ou créer l'état de la quête
        pq_state, created = PlayerQuestState.objects.get_or_create(
            player_id=player_id,
            quest_id=quest_id,
            defaults={"status": new_status}
        )

        # Mise à jour du statut
        pq_state.status = new_status
        
        # Gestion des dates
        if new_status == "IN_PROGRESS" and not pq_state.startedAt:
            pq_state.startedAt = timezone.now()
        elif new_status == "COMPLETED" and not pq_state.completedAt:
            pq_state.completedAt = timezone.now()
            
        # Si c'est une nouvelle entrée, on s'assure que le joueur est dans les membres
        if created and player_id not in pq_state.members:
            pq_state.members.append(player_id)

        pq_state.save()

        return JsonResponse({
            "message": "Statut de la quête mis à jour",
            "quest_id": quest_id,
            "status": new_status,
            "startedAt": pq_state.startedAt,
            "completedAt": pq_state.completedAt
        }, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def list_all_player_quest_states(request):
    """
    GET /quests/all_player_states/
    Récupère tous les états de quêtes de tous les joueurs.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    all_states = PlayerQuestState.objects.all()
    data = []
    for pq in all_states:
        data.append({
            "player_id": pq.player_id,
            "quest_id": pq.quest_id,
            "status": pq.status,
            "startedAt": pq.startedAt,
            "completedAt": pq.completedAt,
            "members": pq.members
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def get_player_active_quests(request, player_id):
    """
    GET /quests/player/<player_id>/active/
    Renvoie les quêtes actives (IN_PROGRESS) du joueur.
    Optionnel: ?category=Main pour filtrer par catégorie.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    category_filter = request.GET.get("category")
    
    # Récupérer les états IN_PROGRESS
    active_states = PlayerQuestState.objects.filter(player_id=player_id, status="IN_PROGRESS")
    
    active_quests = []
    for state in active_states:
        try:
            quest = Quest.objects.get(questId=state.quest_id)
            
            # Filtrage par catégorie si demandé
            if category_filter and quest.category != category_filter:
                continue
                
            active_quests.append({
                "questId": quest.questId,
                "name": quest.name,
                "category": quest.category,
                "type": quest.type,
                "npc": quest.npc,
                "objectives": quest.objectives,
                "startedAt": state.startedAt,
                "members": state.members
            })
        except Quest.DoesNotExist:
            continue # On ignore si la quête n'existe plus

    return JsonResponse(active_quests, safe=False)

@csrf_exempt
def join_multiplayer_quest(request, quest_id):
    """
    POST /quests/<quest_id>/join/
    Ajoute un joueur à une quête multijoueur existante.
    Body: { "player_id": "..." }
    """
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    try:
        data = json.loads(request.body)
        player_id = data.get("player_id")
        
        if not player_id:
            return JsonResponse({"error": "player_id requis"}, status=400)

        quest = get_object_or_404(Quest, questId=quest_id)
        
        if quest.type != "Multi" and quest.type != "Hybrid":
             return JsonResponse({"error": "Cette quête n'est pas multijoueur"}, status=400)

        # Trouver une instance active de cette quête (pour simplifier, on prend la première trouvée où le joueur n'est pas, 
        # ou on pourrait demander l'ID du leader. Ici on suppose qu'on rejoint une quête active quelconque ou celle d'un ami)
        # Pour l'instant, on va chercher si une instance existe déjà avec ce quest_id et IN_PROGRESS
        # Mais attention, PlayerQuestState est unique par (player_id, quest_id).
        # Donc "rejoindre" veut dire créer son propre état mais lié aux autres ? 
        # Ou alors PlayerQuestState devrait être partagé ?
        # Dans le modèle actuel, `members` est une liste. Donc on doit trouver l'instance "principale" ?
        # Mais la PK est player_id:quest_id. Donc chaque joueur a son propre document.
        # Si on veut synchroniser, il faudrait un "GroupQuestState" ou gérer la synchro manuellement.
        # D'après la structure `members : [player_id, ...]`, cela suggère que l'état est partagé ou dupliqué.
        # Si la PK est unique par joueur, alors `members` sert juste à savoir avec qui on est.
        
        # Simplification : On crée/met à jour l'état du joueur pour le mettre IN_PROGRESS et on met à jour la liste des membres
        # pour lui et potentiellement pour les autres membres (ce qui est lourd sans une table de groupe).
        
        # Pour l'instant, on va juste mettre le joueur IN_PROGRESS sur cette quête.
        # Une vraie gestion multi nécessiterait de savoir QUEL groupe on rejoint.
        
        pq_state, created = PlayerQuestState.objects.get_or_create(
            player_id=player_id,
            quest_id=quest_id,
            defaults={"status": "IN_PROGRESS", "startedAt": timezone.now(), "members": [player_id]}
        )
        
        if not created and pq_state.status != "IN_PROGRESS":
            pq_state.status = "IN_PROGRESS"
            pq_state.startedAt = timezone.now()
            pq_state.save()
            
        return JsonResponse({"message": "Quête rejointe", "quest_id": quest_id}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def update_quest_start_npc(request, quest_id):
    """
    PUT /quests/<quest_id>/npc/start/
    Modifie le NPC de départ de la quête.
    Body: { "npc": "npc_id" }
    """
    if request.method != "PUT":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)
        
    try:
        data = json.loads(request.body)
        new_npc = data.get("npc")
        
        if not new_npc:
            return JsonResponse({"error": "npc requis"}, status=400)
            
        quest = get_object_or_404(Quest, questId=quest_id)
        quest.npc = new_npc
        quest.save()
        
        return JsonResponse({"message": "NPC de départ mis à jour", "questId": quest.questId, "npc": new_npc})
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

@csrf_exempt
def update_quest_objective_npc(request, quest_id):
    """
    PUT /quests/<quest_id>/npc/objective/
    Modifie le NPC d'un objectif spécifique.
    Body: { "objective_index": 0, "npc": "npc_id" }
    """
    if request.method != "PUT":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)
        
    try:
        data = json.loads(request.body)
        index = data.get("objective_index")
        new_npc = data.get("npc")
        
        if index is None or not new_npc:
            return JsonResponse({"error": "objective_index et npc requis"}, status=400)
            
        quest = get_object_or_404(Quest, questId=quest_id)
        
        objectives = quest.objectives
        if index < 0 or index >= len(objectives):
            return JsonResponse({"error": "Index d'objectif invalide"}, status=400)
            
        if objectives[index].get("type") != "NPC":
             return JsonResponse({"error": "L'objectif ciblé n'est pas de type NPC"}, status=400)
             
        objectives[index]["npcId"] = new_npc
        quest.objectives = objectives
        quest.save()
        
        return JsonResponse({"message": "NPC d'objectif mis à jour", "questId": quest.questId})
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)
