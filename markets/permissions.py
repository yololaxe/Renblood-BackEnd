import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasMinecraftApiKey(BasePermission):
    message = "A valid Minecraft server API key is required."

    def has_permission(self, request, view):
        expected = getattr(settings, "API_KEY_RENBLOOD", None)
        supplied = request.headers.get("X-API-KEY")
        return bool(expected and supplied and secrets.compare_digest(str(expected), str(supplied)))
