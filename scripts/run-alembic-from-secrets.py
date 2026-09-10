#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: run-alembic-from-secrets.py
# NG-HEADER: Ubicación: scripts/run-alembic-from-secrets.py
# NG-HEADER: Descripción: Ejecuta Alembic leyendo la contraseña PostgreSQL desde un secreto montado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Wrapper de migración que evita credenciales en argumentos y logs."""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise RuntimeError(f"required_environment_missing:{name}")
    return value


def _read_password(environment: Mapping[str, str]) -> str:
    path = Path(_required(environment, "DB_PASS_FILE"))
    if not path.is_absolute():
        raise RuntimeError("DB_PASS_FILE_must_be_absolute")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("DB_PASS_FILE_must_be_regular_file")
    password = path.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError("DB_PASS_FILE_is_empty")
    return password


def _database_url(environment: Mapping[str, str]) -> str:
    user = quote(_required(environment, "DB_USER"), safe="")
    password = quote(_read_password(environment), safe="")
    host = _required(environment, "DB_HOST")
    port = int(environment.get("DB_PORT", "5432"))
    database = quote(_required(environment, "DB_NAME"), safe="")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def _wait_for_database(environment: Mapping[str, str]) -> None:
    timeout = float(environment.get("DB_WAIT_TIMEOUT_SECONDS", "120"))
    if timeout <= 0:
        return
    host = _required(environment, "DB_HOST")
    port = int(environment.get("DB_PORT", "5432"))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError("database_not_ready_before_timeout")


def run_upgrade(environment: Mapping[str, str] | None = None) -> int:
    source = dict(os.environ if environment is None else environment)
    _wait_for_database(source)
    child_environment = dict(os.environ)
    child_environment.update(source)
    child_environment.pop("DB_PASS", None)
    child_environment["DB_URL"] = _database_url(source)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), "upgrade", "head"],
        cwd=ROOT,
        env=child_environment,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(run_upgrade())
