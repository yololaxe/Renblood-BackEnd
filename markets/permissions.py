import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasMinecraftApiKey(BasePermission):
    message = "A valid Minecraft server API key is required."

    def has_permission(self, request, view):
        expected = self._normalize(getattr(settings, "API_KEY_RENBLOOD", None))
        supplied = request.headers.get("X-API-KEY")
        if not supplied:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                supplied = auth_header.split("Bearer ", 1)[1]
        supplied = self._normalize(supplied)
        return bool(expected and supplied and secrets.compare_digest(str(expected), str(supplied)))

    @staticmethod
    def _normalize(value):
        if value is None:
            return ""
        normalized = str(value).strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {'"', "'"}:
            normalized = normalized[1:-1].strip()
        return normalized
