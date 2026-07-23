#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: generate_chat_keys.py
# NG-HEADER: Ubicación: scripts/generate_chat_keys.py
# NG-HEADER: Descripción: Genera claves locales de identidad sin mostrarlas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Completa claves ausentes de Telegram en .env sin imprimir secretos."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

KEY_NAMES = ("TELEGRAM_IDENTITY_ENCRYPTION_KEY", "TELEGRAM_IDENTITY_HMAC_KEY")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Escribe claves ausentes en .env")
    args = parser.parse_args()
    env_path = Path(__file__).resolve().parents[1] / ".env"
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    configured = {line.split("=", 1)[0].strip() for line in existing.splitlines() if "=" in line and line.split("=", 1)[1].strip()}
    missing = [name for name in KEY_NAMES if name not in configured]
    if not args.write:
        print(f"Claves ausentes: {len(missing)}. Usar --write para generarlas sin mostrarlas.")
        return 0
    if not missing:
        print("Las claves locales ya están configuradas; no se realizaron cambios.")
        return 0
    additions = [f"{name}={base64.urlsafe_b64encode(os.urandom(32)).decode('ascii')}" for name in missing]
    updated = existing.rstrip() + ("\n" if existing.strip() else "") + "\n".join(additions) + "\n"
    temp = env_path.with_suffix(".env.tmp")
    temp.write_text(updated, encoding="utf-8")
    temp.replace(env_path)
    print(f"Se generaron {len(missing)} claves locales sin exponer sus valores.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
