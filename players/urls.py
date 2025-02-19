from django.urls import path
from .views import create_player, get_player, delete_player, update_player

urlpatterns = [
    path('create/', create_player, name="create_player"),
    path('get/<str:player_id>/', get_player, name="get_player"),
    path('delete/<str:player_id>/', delete_player, name="delete_player"),
    path('update/<str:player_id>/', update_player, name="update_player"),
]
