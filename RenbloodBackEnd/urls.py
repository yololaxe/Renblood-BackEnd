
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def home(request):
    return JsonResponse({"message": "Bienvenue sur Renblood API 🎉"})


urlpatterns = [
    path("", home),
    path('admin/', admin.site.urls),
    path('players/', include('players.urls')),
    path('jobs/', include('jobs.urls')),
]
