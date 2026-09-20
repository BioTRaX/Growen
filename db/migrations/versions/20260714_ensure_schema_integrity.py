# NG-HEADER: Nombre de archivo: 20260714_ensure_schema_integrity.py
# NG-HEADER: Ubicación: db/migrations/versions/20260714_ensure_schema_integrity.py
# NG-HEADER: Descripción: Garantiza índices y constraints omitidos por ramas históricas de Alembic.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Garantiza objetos críticos omitidos por ramas históricas.

Revision ID: 20260714_schema_integrity
Revises: a1b2c3d4e5f6
Create Date: 2026-07-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260714_schema_integrity"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

CUSTOMERS_DOCUMENT_INDEX = "ux_customers_document_number"
RETURNS_STATUS_CONSTRAINT = "ck_returns_status"
RETURNS_CREATED_INDEX = "ix_returns_created_at"
VALID_RETURN_STATUSES = ("BORRADOR", "REGISTRADA", "ANULADA")


def _unique_document_index_exists(inspector: sa.Inspector) -> bool:
    indexes = inspector.get_indexes("customers")
    if any(item.get("unique") and item.get("column_names") == ["document_number"] for item in indexes):
        return True

    constraints = inspector.get_unique_constraints("customers")
    return any(item.get("column_names") == ["document_number"] for item in constraints)


def _ensure_customers_document_index(bind, inspector: sa.Inspector) -> None:
    if "customers" not in inspector.get_table_names():
        raise RuntimeError("No existe customers; revisar la cadena Alembic anterior")
    if _unique_document_index_exists(inspector):
        return

    duplicates = bind.execute(
        sa.text(
            """
            SELECT document_number
            FROM customers
            WHERE document_number IS NOT NULL
            GROUP BY document_number
            HAVING count(*) > 1
            LIMIT 5
            """
        )
    ).scalars().all()
    if duplicates:
        raise RuntimeError(
            "No se puede crear el índice único de customers.document_number: "
            f"existen valores duplicados ({len(duplicates)} muestra(s))."
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {CUSTOMERS_DOCUMENT_INDEX} "
            "ON customers(document_number) WHERE document_number IS NOT NULL"
        )
    else:
        op.create_index(CUSTOMERS_DOCUMENT_INDEX, "customers", ["document_number"], unique=True)


def _ensure_returns_objects(bind, inspector: sa.Inspector) -> None:
    if "returns" not in inspector.get_table_names():
        raise RuntimeError("No existe returns; revisar la cadena Alembic anterior")

    invalid_statuses = bind.execute(
        sa.text(
            """
            SELECT DISTINCT status
            FROM returns
            WHERE status IS NULL OR status NOT IN ('BORRADOR', 'REGISTRADA', 'ANULADA')
            LIMIT 5
            """
        )
    ).scalars().all()
    if invalid_statuses:
        raise RuntimeError(
            "No se puede crear ck_returns_status: existen estados inválidos "
            f"({len(invalid_statuses)} muestra(s))."
        )

    check_names = {item.get("name") for item in inspector.get_check_constraints("returns")}
    if RETURNS_STATUS_CONSTRAINT not in check_names:
        op.create_check_constraint(
            RETURNS_STATUS_CONSTRAINT,
            "returns",
            "status IN ('BORRADOR','REGISTRADA','ANULADA')",
        )

    index_names = {item.get("name") for item in inspector.get_indexes("returns")}
    if RETURNS_CREATED_INDEX not in index_names:
        op.create_index(RETURNS_CREATED_INDEX, "returns", ["created_at"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _ensure_customers_document_index(bind, inspector)
    _ensure_returns_objects(bind, inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "returns" in tables:
        index_names = {item.get("name") for item in inspector.get_indexes("returns")}
        if RETURNS_CREATED_INDEX in index_names:
            op.drop_index(RETURNS_CREATED_INDEX, table_name="returns")

        check_names = {item.get("name") for item in inspector.get_check_constraints("returns")}
        if RETURNS_STATUS_CONSTRAINT in check_names:
            op.drop_constraint(RETURNS_STATUS_CONSTRAINT, "returns", type_="check")

    if "customers" not in tables:
        return
    if bind.dialect.name == "postgresql":
        op.execute(f"DROP INDEX IF EXISTS {CUSTOMERS_DOCUMENT_INDEX}")
        return

    index_names = {item.get("name") for item in inspector.get_indexes("customers")}
    if CUSTOMERS_DOCUMENT_INDEX in index_names:
        op.drop_index(CUSTOMERS_DOCUMENT_INDEX, table_name="customers")
