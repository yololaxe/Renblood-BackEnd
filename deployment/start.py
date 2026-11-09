"""ASGI entry point for Railway; never runs destructive seed/migration commands on boot."""
import os
import sys
port = os.environ.get("PORT", "8000")
if not port.isdecimal() or not 1 <= int(port) <= 65535:
    raise RuntimeError("PORT must be a valid TCP port")
os.execvp("daphne", ["daphne", "-b", "0.0.0.0", "-p", port, "RenbloodBackEnd.asgi:application"])
