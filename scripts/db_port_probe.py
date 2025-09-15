"""NG-HEADER
Nombre: scripts/db_port_probe.py
Descripción: Sonda interactiva para diagnosticar qué instancia Postgres responde en el puerto local y validar credenciales.
Uso:
  (.venv) python scripts/db_port_probe.py
Salida:
  - Imprime DB_URL (sanitizada)
  - Intenta conexión psycopg
  - Muestra dirección/puerto real del servidor (inet_server_addr/port)
  - Muestra versión y método de autenticación visto en pg_stat_activity (si rol actual)
Notas:
  - No modifica datos.
  - Código de salida 0 si conexión OK, 2 si fallo de auth, 3 otros errores.
"""
from __future__ import annotations
import os
import sys
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv(override=True)

try:
    import psycopg  # type: ignore
except Exception as e:  # pragma: no cover
    print(f"[FATAL] psycopg no importable: {e}")
    sys.exit(10)

DB_URL = os.getenv("DB_URL")

@dataclass
class Result:
    ok: bool
    code: int
    message: str


def safe_db_url(url: Optional[str]) -> str:
    if not url:
        return "<VACIA>"
    # ocultar password
    if '://' in url:
        head, rest = url.split('://', 1)
        if '@' in rest:
            creds, tail = rest.split('@', 1)
            if ':' in creds:
                user, _ = creds.split(':', 1)
                return f"{head}://{user}:***@{tail}"
    return url


def probe() -> Result:
    if not DB_URL:
        return Result(False, 11, "DB_URL no encontrada en entorno")
    print(f"[INFO] DB_URL={safe_db_url(DB_URL)}")
    # Desarmar manualmente por si el driver necesita campos separados
    import re
    m = re.match(r"postgresql\+psycopg://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)", DB_URL)
    if not m:
        return Result(False, 12, "Formato DB_URL no coincide con patrón esperado")
    user, password, host, port, dbname = m.groups()
    port = port or '5432'
    print(f"[INFO] Intentando conexión -> host={host} port={port} db={dbname} user={user} pass.len={len(password)}")
    try:
        with psycopg.connect(host=host, port=port, dbname=dbname, user=user, password=password) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                print(f"[OK] SELECT 1 => {cur.fetchone()}")
                cur.execute("select inet_server_addr(), inet_server_port(), current_database()")
                addr, real_port, current_db = cur.fetchone()
                print(f"[INFO] Server addr={addr} real_port={real_port} current_db={current_db}")
                with suppress(Exception):
                    cur.execute("select version()")
                    print(f"[INFO] Version => {cur.fetchone()[0]}")
                # Intentar ver método de auth (requiere permisos; puede fallar)
                with suppress(Exception):
                    cur.execute("select usename, application_name, client_addr from pg_stat_activity where pid = pg_backend_pid()")
                    row = cur.fetchone()
                    if row:
                        print(f"[INFO] Sesión => user={row[0]} app={row[1]} client={row[2]}")
        return Result(True, 0, "Conexión exitosa")
    except psycopg.OperationalError as e:
        msg = str(e)
        if 'password' in msg.lower() and 'fall' in msg.lower():  # español 'falló'
            return Result(False, 2, f"Fallo autenticación: {msg}")
        return Result(False, 3, f"OperationalError: {msg}")
    except Exception as e:  # pragma: no cover
        return Result(False, 4, f"Error genérico: {e}")


if __name__ == "__main__":
    res = probe()
    print(f"[RESULT] ok={res.ok} code={res.code} msg={res.message}")
    sys.exit(res.code)
