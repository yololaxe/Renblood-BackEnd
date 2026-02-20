from django.urls import path
from .views import list_quests, create_quest, quest_detail, get_player_quests, update_player_quest_status, list_all_player_quest_states, get_player_active_quests, join_multiplayer_quest, update_quest_start_npc, update_quest_objective_npc

urlpatterns = [
    path('list/', list_quests, name='list_quests'),
    path('create/', create_quest, name='create_quest'),
    path('all_player_states/', list_all_player_quest_states, name='list_all_player_quest_states'),
    path('player/<str:player_id>/', get_player_quests, name='get_player_quests'),
    path('player/<str:player_id>/active/', get_player_active_quests, name='get_player_active_quests'),
    path('player/<str:player_id>/update/', update_player_quest_status, name='update_player_quest_status'),
    path('<str:quest_id>/join/', join_multiplayer_quest, name='join_multiplayer_quest'),
    path('<str:quest_id>/npc/start/', update_quest_start_npc, name='update_quest_start_npc'),
    path('<str:quest_id>/npc/objective/', update_quest_objective_npc, name='update_quest_objective_npc'),
    path('<str:quest_id>/', quest_detail, name='quest_detail'),
]
