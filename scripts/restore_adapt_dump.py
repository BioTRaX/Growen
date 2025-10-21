#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: restore_adapt_dump.py
# NG-HEADER: Ubicación: scripts/restore_adapt_dump.py
# NG-HEADER: Descripción: Restaura un backup .dump a una DB temporal, aplica migraciones Alembic y genera un dump migrado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Restauración y adaptación de un backup PostgreSQL al schema HEAD.

Flujo:
 1. Detectar formato del archivo (.dump custom vs SQL plano).
 2. Crear base temporal (o reutilizar si --reuse-temp) y restaurar contenido.
 3. Ejecutar "alembic upgrade head" sobre la DB temporal.
 4. Ajustar secuencias (setval) si se solicita (--fix-sequences, por defecto sí).
 5. (Opcional) Auditoría rápida de migraciones y schema.
 6. Generar un nuevo dump *_migrated.dump (custom -Fc) si se usa --export.

Uso:
  python scripts/restore_adapt_dump.py --dump backups/pg/auto_20250926_210426.dump \
      --temp-db growen_restore_tmp --final-tag prodready --export

Requisitos:
 - Variables de entorno PGHOST, PGPORT, PGUSER, PGPASSWORD (o .pgpass) para conectarse.
 - Cliente psql/pg_restore disponibles en PATH.
 - Proyecto con alembic.ini en raíz y migraciones presentes.

Notas:
 - No sobreescribe la DB final (responsabilidad del operador hacer swap/rename luego).
 - Idempotencia: si la DB temporal existe se aborta salvo --reuse-temp.
 - Para inspeccionar sin migrar: usar --no-upgrade.

Limitaciones / TODO futuros:
 - Manejo de enums pre-migración (si falla, el usuario debe aplicar ALTER TYPE manual y reintentar).
 - Validación de datos duplicados antes de UNIQUE (mostrar hints si falla migración).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC = [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini")]
DOCKER_DB_CONTAINER = os.getenv("GROWEN_DB_CONTAINER", "growen-postgres")


def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def run(cmd: list[str], check: bool = True, capture: bool = False, env: dict | None = None):
    print("$", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=capture, text=True, env=env)
    if check and res.returncode != 0:
        if capture:
            print(res.stdout)
            print(res.stderr, file=sys.stderr)
        raise SystemExit(f"Comando fallo ({res.returncode}): {' '.join(cmd)}")
    return res


def detect_format(dump_path: Path) -> str:
    with dump_path.open('rb') as fh:
        magic = fh.read(5)
    # Formato custom inicia con 'PGDMP'
    if magic.startswith(b'PGDMP'):
        return 'custom'
    # Heurística simple: si contiene muchas sentencias CREATE TABLE probablemente sea plano
    # (evitamos leer completo)
    return 'plain'


def ensure_db_absent(dbname: str):
    if which("psql"):
        run(["psql", "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {dbname};"])
    else:
        print("psql no encontrado localmente, usando docker exec")
        run(["docker", "exec", DOCKER_DB_CONTAINER, "psql", "-U", os.getenv("PGUSER", "postgres"), "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS {dbname};"])


def create_db(dbname: str):
    if which("psql"):
        run(["psql", "-d", "postgres", "-c", f"CREATE DATABASE {dbname};"])
    else:
        print("psql no encontrado localmente, usando docker exec")
        run(["docker", "exec", DOCKER_DB_CONTAINER, "psql", "-U", os.getenv("PGUSER", "postgres"), "-d", "postgres", "-c", f"CREATE DATABASE {dbname};"])


def grant_permissions(dbname: str, user: str):
    """Otorga permisos básicos al usuario de la app en la nueva DB."""
    print(f"Otorgando permisos a '{user}' en '{dbname}'...")
    if which("psql"):
        run(["psql", "-d", dbname, "-c", f"ALTER DATABASE {dbname} OWNER TO {user};"])
        run(["psql", "-d", dbname, "-c", f"GRANT USAGE, CREATE ON SCHEMA public TO {user};"])
    else:
        print("psql no encontrado localmente, usando docker exec")
        run([
            "docker", "exec", DOCKER_DB_CONTAINER, "psql",
            "-U", os.getenv("PGUSER", "postgres"),
            "-d", dbname,
            "-c", f"ALTER DATABASE {dbname} OWNER TO {user};",
        ])
        run([
            "docker", "exec", DOCKER_DB_CONTAINER, "psql",
            "-U", os.getenv("PGUSER", "postgres"),
            "-d", dbname,
            "-c", f"GRANT USAGE, CREATE ON SCHEMA public TO {user};",
        ])

def restore_dump(dump: Path, db: str, fmt: str, jobs: int):
    if fmt == 'custom':
        if which("pg_restore"):
            run(["pg_restore", "--no-owner", "--no-privileges", f"--jobs={jobs}", f"--dbname={db}", str(dump)])
        else:
            print("pg_restore no encontrado, usando docker exec")
            # Copiamos siempre el dump a /tmp para evitar problemas de rutas Windows no montadas
            container_tmp = f"/tmp/{dump.name}"
            run(["docker", "cp", str(dump), f"{DOCKER_DB_CONTAINER}:{container_tmp}"])
            run(["docker", "exec", DOCKER_DB_CONTAINER, "pg_restore", "-U", os.getenv("PGUSER", "postgres"), "--no-owner", "--no-privileges", f"--jobs={jobs}", f"--dbname={db}", container_tmp])
    else:
        if which("psql"):
            run(["psql", "-d", db, "-f", str(dump)])
        else:
            print("psql no encontrado, usando docker exec")
            container_tmp = f"/tmp/{dump.name}"
            run(["docker", "cp", str(dump), f"{DOCKER_DB_CONTAINER}:{container_tmp}"])
            run(["docker", "exec", DOCKER_DB_CONTAINER, "psql", "-U", os.getenv("PGUSER", "postgres"), "-d", db, "-f", container_tmp])


def alembic_upgrade(db_url: str):
    env = os.environ.copy()
    env['DB_URL'] = db_url
    run(ALEMBIC + ["upgrade", "head"], env=env)


def fix_sequences(db_url: str):
    import sqlalchemy as sa
    from sqlalchemy import text

    engine = sa.create_engine(db_url)
    with engine.connect() as conn:
        print("Ajustando secuencias...")
        # Solo Postgres
        seqs = conn.execute(text("""
            SELECT sequence_schema, sequence_name
            FROM information_schema.sequences
            WHERE sequence_schema = current_schema()
        """)).all()
        for _schema, seq in seqs:
            # Heurística: tabla base si termina en _id_seq
            if seq.endswith('_id_seq'):
                table = seq[:-7]
                # Chequear existencia de la tabla y columna id
                exists = conn.execute(text("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name=:t AND column_name='id' AND table_schema=current_schema() LIMIT 1
                """), {"t": table}).first()
                if not exists:
                    continue
                max_id = conn.execute(text(f"SELECT COALESCE(MAX(id),0) FROM {table}" )) .scalar()
                # setval(next value should be max+1)
                conn.execute(text("SELECT setval(:s, :v, :is_called)"), {"s": seq, "v": max_id + 1, "is_called": False})
                print(f" - {seq} => {max_id + 1}")
        conn.commit()
        print("Secuencias ajustadas.")


def export_dump(dbname: str, original: Path, tag: str | None) -> Path:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = tag or 'migrated'
    out_name = f"{original.stem}_{suffix}_{ts}.dump"
    out_path = original.parent / out_name
    if which("pg_dump"):
        run(["pg_dump", "-Fc", "-d", dbname, "-f", str(out_path)])
    else:
        print("pg_dump no encontrado, usando docker exec")
        # Generar en /tmp del contenedor y luego copiar
        tmp_name = f"/tmp/{out_name}"
        run(["docker", "exec", DOCKER_DB_CONTAINER, "pg_dump", "-U", os.getenv("PGUSER", "postgres"), "-Fc", "-d", dbname, "-f", tmp_name])
        run(["docker", "cp", f"{DOCKER_DB_CONTAINER}:{tmp_name}", str(out_path)])
    print("Dump migrado generado:", out_path)
    return out_path


def parse_args():
    p = argparse.ArgumentParser(description="Restaura un backup y aplica migraciones Alembic")
    p.add_argument("--dump", required=True, help="Ruta al archivo .dump o .sql")
    p.add_argument("--temp-db", required=True, help="Nombre DB temporal a crear")
    p.add_argument("--reuse-temp", action="store_true", help="No dropea / recrea la DB temporal si existe")
    p.add_argument("--jobs", type=int, default=max(1, os.cpu_count() or 1), help="Paralelismo pg_restore")
    p.add_argument("--no-upgrade", action="store_true", help="No ejecuta alembic upgrade (solo restore)")
    p.add_argument("--no-fix-sequences", action="store_true", help="No ajusta secuencias post-upgrade")
    p.add_argument("--export", action="store_true", help="Genera un dump migrado final")
    p.add_argument("--export-tag", help="Sufijo custom para el dump migrado (default migrated)")
    p.add_argument("--audit", action="store_true", help="Ejecuta scripts/check_schema.py y scripts/debug_migrations.py al final")
    p.add_argument("--db-url-template", default="postgresql+psycopg://{user}:{password}@{host}:{port}/{db}", help="Plantilla para DB_URL")
    return p.parse_args()


def build_db_url(dbname: str) -> str:
    host = os.getenv("PGHOST", "127.0.0.1")
    port = os.getenv("PGPORT", "5432")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "postgres")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}"


def main():
    args = parse_args()
    dump_path = Path(args.dump).resolve()
    if not dump_path.exists():
        print("Archivo de dump no encontrado:", dump_path)
        return 2

    fmt = detect_format(dump_path)
    print(f"Formato detectado: {fmt}")

    # Crear / recrear DB temporal
    if not args.reuse_temp:
        ensure_db_absent(args.temp_db)
        create_db(args.temp_db)
        grant_permissions(args.temp_db, os.getenv("PGUSER", "postgres"))
    else:
        print("Reutilizando DB temporal existente (no drop)")

    # Restaurar
    restore_dump(dump_path, args.temp_db, fmt, args.jobs)

    db_url = build_db_url(args.temp_db)

    # Migrar
    if not args.no_upgrade:
        alembic_upgrade(db_url)
    else:
        print("Salteando alembic upgrade (flag --no-upgrade)")

    # Fix secuencias
    if not args.no_fix_sequences and not args.no_upgrade:
        try:
            fix_sequences(db_url)
        except Exception as exc:
            print("WARN: fallo ajustando secuencias:", exc)

    # Auditoría
    if args.audit:
        env = os.environ.copy()
        env['DB_URL'] = db_url
        print("Ejecutando auditorías...")
        run([sys.executable, str(ROOT / 'scripts' / 'check_schema.py')], env=env, check=False)
        run([sys.executable, str(ROOT / 'scripts' / 'debug_migrations.py')], env=env, check=False)

    # Export final
    if args.export:
        export_dump(args.temp_db, dump_path, args.export_tag)

    print("Proceso completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
