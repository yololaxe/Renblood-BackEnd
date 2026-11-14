from django.urls import path
from .api_views import list_npcs, create_npc, npc_detail, npc_changes
from .views import list_spawns, create_spawn, get_spawns_by_world, meet_npc

from .spawn_admin import manage_spawn

urlpatterns = [
    # NPCs
    path('list/', list_npcs, name='list_npcs'),
    path('changes/', npc_changes, name='npc_changes'),
    path('create/', create_npc, name='create_npc'),
    path('<str:npc_id>/', npc_detail, name='npc_detail'),
    path('<str:npc_id>/meet/', meet_npc, name='meet_npc'),
    
    # Spawns
    path('spawns/list/', list_spawns, name='list_spawns'),
    path('spawns/create/', create_spawn, name='create_spawn'),
    path('spawns/<str:spawn_id>/manage/', manage_spawn, name='manage_spawn'),
    path('spawns/world/<str:world_name>/', get_spawns_by_world, name='get_spawns_by_world'),
]
