from functools import wraps
from django.http import JsonResponse
from firebase_admin import auth
from players.models import Player
from .firebase_setup import initialize_firebase

# Initialisation de Firebase Admin SDK
initialize_firebase()

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # 1. Vérifier la présence du token
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authorization header manquant ou invalide'}, status=401)

        id_token = auth_header.split('Bearer ')[1]

        try:
            # 2. Vérifier le token avec Firebase
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token['uid']

            # 3. Récupérer le joueur
            try:
                player = Player.objects.get(id=uid)
            except Player.DoesNotExist:
                return JsonResponse({'error': 'Joueur non trouvé'}, status=403)

            # 4. Vérifier le rang Admin
            if player.rank != 'Admin':
                return JsonResponse({'error': 'Accès refusé. Administrateur requis.'}, status=403)
            
            # Ajoute l'admin authentifié à la requête pour un usage ultérieur si besoin
            request.admin_user = player

        except auth.InvalidIdTokenError:
            return JsonResponse({'error': 'Token Firebase invalide'}, status=401)
        except Exception as e:
            return JsonResponse({'error': f'Erreur de vérification: {str(e)}'}, status=500)

        return view_func(request, *args, **kwargs)
    return _wrapped_view
