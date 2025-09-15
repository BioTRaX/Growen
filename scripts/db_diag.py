#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: db_diag.py
# NG-HEADER: Ubicación: scripts/db_diag.py
# NG-HEADER: Descripción: Script diagnóstico de conexión a la base de datos PostgreSQL y entorno.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Diagnóstico rápido de conexión a Postgres.

Objetivos:
 1. Cargar .env y mostrar DB_URL (en forma anonimizada).
 2. Verificar parseo de credenciales.
 3. Intentar conexión y reportar causa en detalle.
 4. Validar existencia de la base objetivo y listar roles relevantes.
 5. Imprimir sugerencias accionables según el error.

Uso:
    python scripts/db_diag.py

Salida exit codes:
 0 => éxito / conexión OK
 2 => DB_URL ausente o inválida
 3 => Error de autenticación
 4 => Base de datos no existe
 5 => No se pudo conectar (otras causas de red/socket)
 6 => Dependencias faltantes (psycopg / sqlalchemy)
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from urllib.parse import urlsplit

try:
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] Falta dependency python-dotenv. Instala requirements.")
    sys.exit(6)


def _safe_url(raw: str) -> str:
    try:
        parts = urlsplit(raw)
        netloc = parts.netloc
        if "@" in netloc and ":" in netloc.split("@")[0]:
            user = netloc.split("@")[0].split(":")[0]
            host = netloc.split("@")[1]
            netloc = f"{user}:***@{host}"
        return parts._replace(netloc=netloc).geturl()
    except Exception:
        return "(no se pudo anonimizar)"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    dotenv_path = repo_root / ".env"
    load_dotenv(dotenv_path, override=True)
    db_url = os.getenv("DB_URL")
    if not db_url:
        print("[ERROR] DB_URL no definida en .env")
        return 2
    print(f"[INFO] .env: {dotenv_path} (exists={dotenv_path.exists()})")
    print(f"[INFO] DB_URL (safe): {_safe_url(db_url)}")

    # Parse credenciales
    parts = urlsplit(db_url)
    user = parts.username
    password = parts.password
    hostname = parts.hostname
    database = parts.path.lstrip('/') if parts.path else None
    print(f"[INFO] Usuario: {user}")
    print(f"[INFO] Host: {hostname}")
    print(f"[INFO] Base: {database}")
    if password:
        print(f"[INFO] Password length: {len(password)} (no se imprime)")
    else:
        print("[WARN] Password vacía o no parseada")

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import OperationalError, DBAPIError
    except ImportError:
        print("[ERROR] Faltan dependencias SQLAlchemy/psycopg.")
        return 6

    engine = create_engine(db_url, future=True, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            v = conn.execute(text("select version()" )).scalar()
            one = conn.execute(text("select 1" )).scalar()
            print(f"[OK] select 1 => {one}")
            print(f"[OK] version() => {v}")
            # Existe alembic_version?
            exists = conn.execute(text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name='alembic_version'
                LIMIT 1
            """)).scalar()
            print(f"[INFO] Tabla alembic_version presente: {bool(exists)}")
            return 0
    except OperationalError as e:  # type: ignore[name-defined]
        msg = str(e).lower()
        print(f"[ERROR] OperationalError: {e}")
        if "password" in msg and "fall" in msg:
            print("[SUGERENCIA] Password incorrecta. Ejecuta dentro del contenedor:\n  ALTER USER {user} WITH PASSWORD '<PASSWORD_CORRECTA>';")
            return 3
        if "does not exist" in msg and database:
            print(f"[SUGERENCIA] Crear base:\n  CREATE DATABASE {database} OWNER {user};")
            return 4
        if "could not connect" in msg or "connection refused" in msg:
            print("[SUGERENCIA] Verifica que el contenedor esté 'Up' y el puerto 5432 abierto.")
            return 5
        return 5
    except DBAPIError as e:  # type: ignore[name-defined]
        print(f"[ERROR] DBAPIError: {e}")
        return 5
    except Exception:
        print("[ERROR] Excepción inesperada:\n" + traceback.format_exc())
        return 5


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
