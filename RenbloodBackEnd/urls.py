from importlib.util import find_spec

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home(request):
    return JsonResponse({"message": "Bienvenue sur Renblood API"})


def health(request):
    return JsonResponse({
        "status": "ok",
        "environment": settings.DJANGO_ENV,
        "database": settings.MONGO_DB_NAME,
    })


urlpatterns = [
    path("ping/", home),
    path("api/health/", health),
    path("admin/", admin.site.urls),
    path("players/", include("players.urls")),
    path("stats/", include("jobs.urls")),
    path("sessions/", include("game_sessions.urls")),
    path("quests/", include("quests.urls")),
    path("npcs/", include("npcs.urls")),
]

if find_spec("markets.urls") is not None:
    urlpatterns.append(path("", include("markets.urls")))
