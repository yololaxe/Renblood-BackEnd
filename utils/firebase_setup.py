import json
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials

from RenbloodBackEnd.environment import load_environment


load_environment(Path(__file__).resolve().parent.parent)


def _get_project_id(credential_data=None):
    return (
        os.getenv("FIREBASE_PROJECT_ID", "").strip()
        or os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        or (credential_data or {}).get("project_id")
    )


def initialize_firebase():
    """Initialize Firebase Admin from production JSON or local credentials."""
    if firebase_admin._apps:
        return

    firebase_json_str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if firebase_json_str:
        try:
            credential_data = json.loads(firebase_json_str)
            project_id = _get_project_id(credential_data)
            if not project_id:
                raise RuntimeError("FIREBASE_PROJECT_ID est requis.")

            credential = credentials.Certificate(credential_data)
            firebase_admin.initialize_app(credential, {"projectId": project_id})
            print("Firebase Admin initialise via JSON (Prod)")
            return
        except Exception as exc:
            raise RuntimeError(
                "Impossible d'initialiser Firebase Admin depuis "
                "FIREBASE_SERVICE_ACCOUNT_JSON."
            ) from exc

    project_id = _get_project_id()
    if not project_id:
        raise RuntimeError(
            "FIREBASE_PROJECT_ID ou GOOGLE_CLOUD_PROJECT est requis."
        )

    try:
        credential = credentials.ApplicationDefault()
        firebase_admin.initialize_app(credential, {"projectId": project_id})
        print("Firebase Admin initialise via Fichier (Local)")
    except Exception as exc:
        raise RuntimeError(
            "Impossible d'initialiser Firebase Admin. Definissez "
            "FIREBASE_PROJECT_ID et GOOGLE_APPLICATION_CREDENTIALS en local."
        ) from exc
