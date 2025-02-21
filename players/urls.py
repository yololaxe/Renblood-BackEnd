from django.urls import path
from .views import create_player, get_player, delete_player, update_player, get_player_jobs, update_player_job, get_players, manage_player_traits_actions

urlpatterns = [
    path('create/', create_player, name="create_player"),
    path('get/<str:player_id>/', get_player, name="get_player"), #Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/get/0kX4gctisIcOKvHDKJmlDRLSLFu2/" -Method GET
    path("get/<str:player_id>/jobs/", get_player_jobs, name="get_player_jobs"), #Invoke-WebRequest -Uri "http://127.0.0.1:8000/players/get/0kX4gctisIcOKvHDKJmlDRLSLFu2/jobs/" -Method GET
    path('delete/<str:player_id>/', delete_player, name="delete_player"),
    path('update/<str:player_id>/', update_player, name="update_player"),
    path("update/<str:player_id>/jobs/<str:job_name>/<str:field>/", update_player_job, name="update_player_job"),
    path("getPlayers/<str:rank>/", get_players, name="get_players"),
    path('list/<str:player_id>/<str:category>/<str:action>/', manage_player_traits_actions, name='manage_traits_actions'),
    
    #path("update/<str:player_id>/jobs/<str:job_name>/<str:field>/<str:new_value>/", update_player_job, name="update_player_job"),
    

   
    
]
