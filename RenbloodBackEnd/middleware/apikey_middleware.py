from django.http import JsonResponse
from django.conf import settings

class APIKeyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 🔐 Exclure les pages d'admin ou d'auth si nécessaire
        if request.path.startswith('/admin') or request.path.startswith('/auth'):
            return self.get_response(request)

        api_key = request.headers.get("X-API-KEY")

        if not api_key or api_key != settings.API_KEY_RENBLOOD:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        return self.get_response(request)
