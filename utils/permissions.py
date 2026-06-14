from rest_framework.permissions import BasePermission
from firebase_admin import auth
from players.models import Player
from .firebase_setup import initialize_firebase

# Initialisation de Firebase Admin SDK
initialize_firebase()

class IsRenbloodAdmin(BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return False

        id_token = auth_header.split('Bearer ')[1]

        try:
            decoded_token = auth.verify_id_token(id_token)
            uid = decoded_token['uid']
            
            player = Player.objects.get(id=uid)
            
            return player.rank == 'Admin'
        except Exception:
            return False
