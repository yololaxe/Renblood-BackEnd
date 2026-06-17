import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasMinecraftApiKey(BasePermission):
    message = "A valid Minecraft server API key is required."

    def has_permission(self, request, view):
        expected = getattr(settings, "API_KEY_RENBLOOD", None)
        supplied = request.headers.get("X-API-KEY")
        if not supplied:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                supplied = auth_header.split("Bearer ", 1)[1]
        return bool(expected and supplied and secrets.compare_digest(str(expected), str(supplied)))
