import os
import json
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

from RenbloodBackEnd.environment import load_environment


load_environment(Path(__file__).resolve().parent.parent)

def initialize_firebase():
    """
    Initialise Firebase Admin SDK.
    Essaie d'abord d'utiliser un dictionnaire (depuis une variable d'environnement JSON),
    sinon retombe sur GOOGLE_APPLICATION_CREDENTIALS (fichier local).
    """
    if not firebase_admin._apps:
        # 1. Essayer avec une variable d'environnement contenant le JSON complet (Pour la PROD - Railway)
        firebase_json_str = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        
        if firebase_json_str:
            try:
                # Convertir la string JSON en dictionnaire Python
                cred_dict = json.loads(firebase_json_str)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {
                    'projectId': os.getenv('FIREBASE_PROJECT_ID'),
                })
                print("Firebase Admin initialisé via JSON (Prod)")
                return
            except Exception as e:
                print(f"Erreur lors de l'initialisation Firebase via JSON: {e}")
        
        # 2. Si pas de JSON en variable, on essaie via le fichier (Pour le DEV - Local)
        # GOOGLE_APPLICATION_CREDENTIALS doit pointer vers le fichier .json
        try:
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred, {
                'projectId': os.getenv('FIREBASE_PROJECT_ID'),
            })
            print("Firebase Admin initialisé via Fichier (Local)")
        except Exception as e:
             print(f"Erreur lors de l'initialisation Firebase via ApplicationDefault: {e}")
             print("Assurez-vous que GOOGLE_APPLICATION_CREDENTIALS ou FIREBASE_SERVICE_ACCOUNT_JSON sont définis.")
