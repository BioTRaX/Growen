#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: clear_db_logs.py
# NG-HEADER: Ubicación: tools/clear_db_logs.py
# NG-HEADER: Descripción: Purga tablas de logs en la base de datos de forma segura.
# NG-HEADER: Lineamientos: Ver AGENTS.md

from __future__ import annotations

"""Herramienta CLI para purgar logs persistidos en la base de datos.

Elimina entradas de las tablas de logging no críticas para negocio:
 - service_logs
 - startup_metrics
 - import_logs
 - image_job_logs

Por defecto NO borra audit_log. Para incluirla, pasar --include-audit.

Uso:
  python -m tools.clear_db_logs              # purga logs estándar
  python -m tools.clear_db_logs --include-audit  # incluye audit_log
"""

import argparse
import asyncio
from typing import Tuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

# Asegurar un event loop compatible en Windows para psycopg async
try:  # pragma: no cover
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
except Exception:
    pass

from db.session import SessionLocal  # usa la config del proyecto (agent_core.config)
from db.models import ServiceLog, StartupMetric, ImportLog, ImageJobLog, AuditLog


async def _purge(session: AsyncSession, include_audit: bool) -> Tuple[int, int, int, int, int]:
    """Ejecuta deletes en tablas de logs. Devuelve conteos (estimados).

    Nota: algunos backends pueden devolver -1 para filas afectadas; en ese caso
    los conteos pueden no ser exactos, pero la operación igualmente se efectúa.
    """
    total_service = (await session.execute(delete(ServiceLog))).rowcount or 0
    total_startup = (await session.execute(delete(StartupMetric))).rowcount or 0
    total_import = (await session.execute(delete(ImportLog))).rowcount or 0
    total_image = (await session.execute(delete(ImageJobLog))).rowcount or 0
    total_audit = 0
    if include_audit:
        total_audit = (await session.execute(delete(AuditLog))).rowcount or 0
    await session.commit()
    return total_service, total_startup, total_import, total_image, total_audit


async def amain(include_audit: bool) -> int:
    async with SessionLocal() as session:
        s, st, imp, img, aud = await _purge(session, include_audit)
        print(f"Purga DB: service_logs={s}, startup_metrics={st}, import_logs={imp}, image_job_logs={img}, audit_log={aud if include_audit else 'skip'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Purga tablas de logs en DB")
    ap.add_argument("--include-audit", action="store_true", help="Incluir audit_log en la purga")
    args = ap.parse_args()
    return asyncio.run(amain(args.include_audit))


if __name__ == "__main__":
    raise SystemExit(main())
