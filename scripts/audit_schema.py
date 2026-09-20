#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: audit_schema.py
# NG-HEADER: Ubicación: scripts/audit_schema.py
# NG-HEADER: Descripción: Auditoría rápida de constraints e índices críticos tras hotfix idempotencia.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Audita presencia de objetos de base de datos claves.

Uso:
    python scripts/audit_schema.py [--url postgresql://...] [--json]

Objetos verificados (si existen las tablas):
  - Tabla products: columna canonical_sku
  - Tabla sku_sequences (para generación canónica)
  - Constraints:
      * ck_returns_status en return_lines o returns (según convención)
      * ck_sales_status en sales
  - Índices esperados:
      * ix_returns_created_at (returns)
      * ix_return_lines_product_id (return_lines)
      * ix_sale_lines_product_id (sale_lines)
      * ix_sales_customer_id (sales)
      * ix_sales_sale_date (sales)
  - Parcial único (Postgres): customers(document_number) ignorando NULL -> idx o constraint detectado

Salida:
  - Texto humano por defecto
  - JSON (--json) para integración CI

Nota: No falla si faltan tablas completas (entorno parcial), solo marca missing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


@dataclass
class CheckResult:
    name: str
    present: bool
    detail: str | None = None
    status: str = "ok"  # ok | missing | skipped


@dataclass
class AuditReport:
    checks: List[CheckResult]

    def as_dict(self):
        return {c.name: {"present": c.present, "detail": c.detail, "status": c.status} for c in self.checks}

    def missing(self):
        return [c.name for c in self.checks if c.status == 'missing']


def _safe_db_url(db_url: str) -> str:
    """Devuelve la URL anonimizada para logs y salida de consola."""
    try:
        return make_url(db_url).render_as_string(hide_password=True)
    except Exception:
        return "<URL inválida>"


def _has_column(inspector, table: str, column: str) -> bool:
    try:
        cols = [c['name'] for c in inspector.get_columns(table)]
        return column in cols
    except Exception:
        return False


def _has_table(inspector, table: str) -> bool:
    try:
        return table in inspector.get_table_names()
    except Exception:
        return False


def _column_is_nullable(inspector, table: str, column: str) -> bool:
    try:
        return next(item for item in inspector.get_columns(table) if item['name'] == column)['nullable']
    except Exception:
        return False


def _has_index(inspector, table: str, index: str) -> bool:
    try:
        for ix in inspector.get_indexes(table):
            if ix.get('name') == index:
                return True
        return False
    except Exception:
        return False


def _constraint_exists_pg(conn, constraint_name: str) -> bool:
    try:
        res = conn.execute(text("""
            SELECT 1 FROM pg_constraint WHERE conname = :c LIMIT 1
        """), {"c": constraint_name})
        return bool(res.first())
    except Exception:
        return False


def _customers_doc_partial_exists_pg(conn) -> bool:
    # Busca índice parcial o constraint (unique) sobre document_number ignorando nulls
    try:
        q = text("""
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = current_schema()
          AND tablename = 'customers'
          AND indexname LIKE '%document_number%'
        LIMIT 1
        """)
        r = conn.execute(q)
        return bool(r.first())
    except Exception:
        return False


def run_audit(db_url: str) -> AuditReport:
    engine = create_engine(db_url)
    insp = inspect(engine)
    checks: List[CheckResult] = []

    # products canonical_sku
    _pc = _has_column(insp, 'products', 'canonical_sku')
    checks.append(CheckResult("products.canonical_sku", _pc, status=("ok" if _pc else "missing")))
    # sku_sequences table
    _ts = _has_table(insp, 'sku_sequences')
    checks.append(CheckResult("table.sku_sequences", _ts, status=("ok" if _ts else "missing")))
    for table in ("canonical_batch_jobs", "canonical_batch_job_items"):
        present = _has_table(insp, table)
        checks.append(CheckResult(f"table.{table}", present, status=("ok" if present else "missing")))
    _sph_file_nullable = _column_is_nullable(insp, 'supplier_price_history', 'file_fk')
    checks.append(CheckResult(
        "supplier_price_history.file_fk_nullable",
        _sph_file_nullable,
        status=("ok" if _sph_file_nullable else "missing"),
    ))

    # constraints
    with engine.connect() as conn:
        dialect = engine.dialect.name
        if dialect == 'postgresql':
            for nm, cn in [("constraint.ck_returns_status", 'ck_returns_status'), ("constraint.ck_sales_status", 'ck_sales_status')]:
                ex = _constraint_exists_pg(conn, cn)
                checks.append(CheckResult(nm, ex, status=("ok" if ex else "missing")))
            part = _customers_doc_partial_exists_pg(conn)
            checks.append(CheckResult("index.customers_document_number_partial", part, status=("ok" if part else "missing")))
        else:
            # sqlite: mark skipped (no introspection real para constraints check parciales)
            checks.append(CheckResult("constraint.ck_returns_status", True, "sqlite: skipped", status="skipped"))
            checks.append(CheckResult("constraint.ck_sales_status", True, "sqlite: skipped", status="skipped"))
            checks.append(CheckResult("index.customers_document_number_partial", True, "sqlite: skipped", status="skipped"))

    # índices
    for tbl, idx in [
        ("returns", "ix_returns_created_at"),
        ("return_lines", "ix_return_lines_product_id"),
        ("sale_lines", "ix_sale_lines_product_id"),
        ("sales", "ix_sales_customer_id"),
        ("sales", "ix_sales_sale_date"),
        ("canonical_batch_jobs", "ix_canonical_batch_jobs_status"),
        ("canonical_batch_jobs", "ix_canonical_batch_jobs_created_by"),
        ("canonical_batch_job_items", "ix_canonical_batch_job_items_status"),
    ]:
        exists_tbl = _has_table(insp, tbl)
        exists_idx = _has_index(insp, tbl, idx) if exists_tbl else False
        if exists_idx:
            checks.append(CheckResult(f"index.{idx}", True, status="ok"))
        else:
            status = "skipped" if engine.dialect.name == 'sqlite' and not exists_tbl else ("missing" if exists_tbl else "skipped")
            detail = None if status != 'skipped' else ("tabla ausente" if not exists_tbl else "sqlite: skipped")
            checks.append(CheckResult(f"index.{idx}", exists_idx, detail=detail, status=status))

    return AuditReport(checks)


def main():
    parser = argparse.ArgumentParser(description="Audita objetos de schema críticos")
    parser.add_argument("--url", dest="url", default=os.getenv("DB_URL", "sqlite:///./dev.db"))
    parser.add_argument("--json", dest="json_out", action="store_true")
    args = parser.parse_args()
    rep = run_audit(args.url)
    if args.json_out:
        print(json.dumps(rep.as_dict(), indent=2, sort_keys=True))
        # Código de salida 2 si faltan objetos
        if rep.missing():
            sys.exit(2)
        return
    print("Auditoría de schema")
    print("DB:", _safe_db_url(args.url))
    for chk in rep.checks:
        if chk.status == 'ok':
            status = 'OK'
        elif chk.status == 'skipped':
            status = 'SKIPPED'
        else:
            status = 'MISSING'
        extra = f" ({chk.detail})" if chk.detail else ""
        print(f" - {chk.name}: {status}{extra}")
    miss = rep.missing()
    if miss:
        print("Objetos faltantes:", ", ".join(miss))
        sys.exit(2)
    else:
        print("Todos los objetos auditados están presentes.")


if __name__ == "__main__":
    main()
