from django.urls import path
from .views import list_npcs, create_npc, npc_detail, list_spawns, create_spawn, get_spawns_by_world

urlpatterns = [
    # NPCs
    path('list/', list_npcs, name='list_npcs'),
    path('create/', create_npc, name='create_npc'),
    path('<str:npc_id>/', npc_detail, name='npc_detail'),
    
    # Spawns
    path('spawns/list/', list_spawns, name='list_spawns'),
    path('spawns/create/', create_spawn, name='create_spawn'),
    path('spawns/world/<str:world_name>/', get_spawns_by_world, name='get_spawns_by_world'),
]
