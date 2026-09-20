#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: secrets.py
# NG-HEADER: Ubicación: agent_core/secrets.py
# NG-HEADER: Descripción: Lectura segura de secretos directos o montados mediante archivos.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Carga secretos sin registrar contenido ni rutas completas."""
from __future__ import annotations

import os
import stat
from pathlib import Path


class SecretConfigurationError(RuntimeError):
    """La configuración de un secreto es ambigua o insegura."""


def read_secret(name: str, *, required: bool = False) -> str | None:
    direct = os.getenv(name)
    file_value = os.getenv(f"{name}_FILE")
    direct = direct if direct else None
    file_value = file_value if file_value else None
    if direct is not None and file_value is not None:
        raise SecretConfigurationError(f"{name.lower()}_value_and_file_conflict")
    if file_value is not None:
        path = Path(file_value)
        if not path.is_absolute():
            raise SecretConfigurationError(f"{name.lower()}_file_not_absolute")
        try:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise SecretConfigurationError(f"{name.lower()}_file_invalid")
            value = path.read_text(encoding="utf-8")
        except SecretConfigurationError:
            raise
        except OSError as exc:
            raise SecretConfigurationError(f"{name.lower()}_file_unreadable") from exc
        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith("\n"):
            value = value[:-1]
    else:
        value = direct
    if value == "":
        value = None
    if required and value is None:
        raise SecretConfigurationError(f"{name.lower()}_missing")
    if os.getenv("ENV", "dev") not in {"dev", "test", "testing"} and direct is not None:
        raise SecretConfigurationError(f"{name.lower()}_file_required")
    return value
