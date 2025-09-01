#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: debug_migrations.py
# NG-HEADER: Ubicación: scripts/debug_migrations.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Diagnóstico de migraciones de Alembic.

Genera un reporte con la versión actual, los heads y el historial
reciente. También verifica la conexión a la base de datos.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC = [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini")]
LOG_DIR = ROOT / "logs" / "migrations"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT = LOG_DIR / f"report_{TS}.txt"
DETAIL = os.getenv("DEBUG_MIGRATIONS") == "1"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def write(section: str, text: str) -> None:
    header = f"\n== {section} ==\n"
    with REPORT.open("a", encoding="utf-8") as fh:
        fh.write(header + text)
    print(header + text)


def main() -> int:
    # Cargar .env para obtener DB_URL si no está en el entorno
    load_dotenv()
    anomalies = False
    # Conexión a DB
    db_url = os.getenv("DB_URL")
    try:
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        write("DB", "Conexión OK")
    except Exception as exc:  # pragma: no cover - logging
        write("DB", f"Fallo de conexión: {exc}\n")
        return 1

    # current
    cur = run(ALEMBIC + ["current"])
    write("current", cur.stdout + cur.stderr)

    # heads
    heads = run(ALEMBIC + ["heads"])
    write("heads", heads.stdout + heads.stderr)
    lines = [l.strip() for l in heads.stdout.splitlines() if l.strip()]
    if len(lines) > 1:
        anomalies = True
        write("warning", "Se detectaron múltiples heads. Considerar un merge.")

    # history
    limit = "50" if DETAIL else "30"
    hist = run(ALEMBIC + ["history", "--verbose", "-n", limit])
    write("history", hist.stdout + hist.stderr)

    return 1 if anomalies else 0


if __name__ == "__main__":
    raise SystemExit(main())
