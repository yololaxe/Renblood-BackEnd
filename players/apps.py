# players/apps.py
import os
import threading
from django.apps import AppConfig

# Garde globale pour éviter tout double-lancement
_bot_started = False
_bot_lock = threading.Lock()

class PlayersConfig(AppConfig):
    default_auto_field = "djongo.models.ObjectIdField"  # si tu utilises Djongo, ok
    name = "players"

    def ready(self):
        """
        Démarre le bot Discord au boot de l'app, une seule fois.
        - Évite le double-lancement dû à l'autoreloader (RUN_MAIN == "true")
        - Permet de désactiver via DISABLE_BOT=1 (migrations/tests)
        - Import paresseux à l'intérieur du thread pour éviter l'import d'aiohttp/discord
          pendant l'initialisation Django.
        """

        # 1) Ne rien faire si désactivé explicitement
        if os.environ.get("DISABLE_BOT") == "1":
            return

        # 2) Éviter les double-lancements du reloader Django (process enfant)
        #    -> RUN_MAIN n'est "true" que dans le vrai process "main" du reloader
        if os.environ.get("RUN_MAIN") != "true" and not os.environ.get("ASGI_WORKER"):
            return

        # 3) Garde thread-safe pour n'initialiser qu'une fois
        global _bot_started
        with _bot_lock:
            if _bot_started:
                return
            _bot_started = True

            def _runner():
                try:
                    # Import paresseux: évite d'importer discord/aiohttp pendant l'init de Django
                    from presence_bot import run_presence_bot
                    run_presence_bot()
                except Exception as e:
                    # Log minimal si besoin; évite d'exploser le process Django
                    print("[presence_bot] Échec du démarrage :", e)

            t = threading.Thread(target=_runner, name="discord-presence-bot", daemon=True)
            t.start()
