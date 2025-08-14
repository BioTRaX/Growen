"""Handlers de intents de ejemplo."""
from typing import Dict


def handle_help() -> Dict[str, str]:
    """Devuelve texto de ayuda simple."""
    return {
        "message": (
            "Comandos disponibles: /help, /sync pull, /sync push, "
            "/stock adjust, /stock min"
        )
    }
