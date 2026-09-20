#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: generate_chat_keys.py
# NG-HEADER: Ubicación: scripts/generate_chat_keys.py
# NG-HEADER: Descripción: Genera archivos persistentes de claves Chat fuera del repositorio.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
KEY_FILES = {
    "telegram_identity_encryption_key": "TELEGRAM_IDENTITY_ENCRYPTION_KEY_FILE",
    "telegram_identity_hmac_key": "TELEGRAM_IDENTITY_HMAC_KEY_FILE",
}
TELEGRAM_TOKEN_RE = re.compile(r"^[0-9]{6,}:[A-Za-z0-9_-]{20,}$")


def _write_new(path: Path, value: str) -> bool:
    if path.exists():
        return False
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(value)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return True


def _capture_canary_user_id(token: str, timeout_seconds: int) -> str:
    """Espera un `/canary` privado sin mostrar token, payload ni Telegram ID."""
    base_url = f"https://api.telegram.org/bot{token}"
    try:
        with httpx.Client(timeout=timeout_seconds + 10.0) as client:
            webhook = client.get(f"{base_url}/getWebhookInfo")
            webhook.raise_for_status()
            webhook_payload = webhook.json()
            if not webhook_payload.get("ok"):
                raise RuntimeError("telegram_api_rejected")
            if (webhook_payload.get("result") or {}).get("url"):
                raise RuntimeError("telegram_webhook_active")

            updates = client.get(
                f"{base_url}/getUpdates",
                params={
                    "timeout": timeout_seconds,
                    "allowed_updates": json.dumps(["message"]),
                },
            )
            updates.raise_for_status()
            payload = updates.json()
            if not payload.get("ok"):
                raise RuntimeError("telegram_api_rejected")
    except httpx.TimeoutException as exc:
        raise RuntimeError("telegram_capture_timeout") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("telegram_api_unavailable") from exc

    candidates: list[tuple[int, str]] = []
    for update in payload.get("result") or []:
        message = update.get("message") or {}
        text = str(message.get("text") or "").strip().split(maxsplit=1)[0].lower()
        command = text.split("@", 1)[0]
        sender_id = (message.get("from") or {}).get("id")
        if command != "/canary" or (message.get("chat") or {}).get("type") != "private":
            continue
        sender = str(sender_id or "")
        if sender.isascii() and sender.isdigit():
            candidates.append((int(update.get("update_id") or 0), sender))
    if not candidates:
        raise RuntimeError("telegram_canary_message_not_received")
    return max(candidates)[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera claves persistentes sin mostrarlas")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--interactive-telegram",
        action="store_true",
        help="Solicita token del bot y Telegram user ID sin mostrarlos ni incluirlos en argumentos",
    )
    parser.add_argument("--interactive-bot-token", action="store_true", help="Solicita sólo el token del bot")
    parser.add_argument("--interactive-canary", action="store_true", help="Solicita sólo el Telegram user ID del canary")
    parser.add_argument(
        "--capture-canary",
        action="store_true",
        help="Espera /canary por Telegram y guarda su from.id sin mostrarlo",
    )
    parser.add_argument("--capture-timeout", type=int, default=60, help="Long polling para captura, entre 5 y 120 segundos")
    parser.add_argument("--interactive-openai-key", action="store_true", help="Solicita una API key OpenAI sin mostrarla")
    args = parser.parse_args()
    destination = args.output_dir.expanduser().resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise SystemExit("El destino debe estar fuera del workspace")
    destination.mkdir(parents=True, exist_ok=True)
    created = 0
    for filename in KEY_FILES:
        path = destination / filename
        value = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        created += int(_write_new(path, value))
    total = len(KEY_FILES)
    if args.interactive_telegram or args.interactive_bot_token:
        token = getpass.getpass("Token del bot Telegram (entrada oculta): ").strip()
        if not TELEGRAM_TOKEN_RE.fullmatch(token):
            raise SystemExit("El token no cumple el formato esperado de Telegram")
        created += int(_write_new(destination / "telegram_bot_token", token))
        total += 1
    if args.interactive_telegram or args.interactive_canary:
        canary_user_id = getpass.getpass("Telegram user ID del canary (entrada oculta): ").strip()
        if not canary_user_id.isascii() or not canary_user_id.isdigit():
            raise SystemExit("El Telegram user ID del canary debe ser numérico")
        created += int(_write_new(destination / "telegram_canary_user_id", canary_user_id))
        total += 1
    if args.capture_canary:
        if not 5 <= args.capture_timeout <= 120:
            raise SystemExit("El timeout de captura debe estar entre 5 y 120 segundos")
        token_path = destination / "telegram_bot_token"
        canary_path = destination / "telegram_canary_user_id"
        if canary_path.exists():
            raise SystemExit("El archivo telegram_canary_user_id ya existe; se conservó sin cambios")
        try:
            token = token_path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as exc:
            raise SystemExit("No se pudo leer telegram_bot_token en el directorio indicado") from exc
        if not TELEGRAM_TOKEN_RE.fullmatch(token):
            raise SystemExit("El token guardado no cumple el formato esperado de Telegram")
        print("Esperando /canary en un chat privado del bot...")
        try:
            canary_user_id = _capture_canary_user_id(token, args.capture_timeout)
        except RuntimeError as exc:
            raise SystemExit(str(exc)) from None
        created += int(_write_new(canary_path, canary_user_id))
        total += 1
    if args.interactive_openai_key:
        openai_key = getpass.getpass("API key OpenAI (entrada oculta): ").strip()
        if not openai_key or any(character.isspace() for character in openai_key):
            raise SystemExit("La API key OpenAI no puede estar vacía ni contener espacios")
        created += int(_write_new(destination / "openai_api_key", openai_key))
        total += 1
    print(f"Archivos creados: {created}; existentes conservados: {total - created}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
