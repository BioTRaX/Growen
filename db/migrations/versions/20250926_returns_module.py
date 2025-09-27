#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250926_returns_module.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_returns_module.py
# NG-HEADER: Descripción: Crea tablas de devoluciones (returns, return_lines)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""returns module

Revision ID: 20250926_returns_module
Revises: 20250925_extend_sales_customers_fields
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250926_returns_module"
down_revision = "20250925_extend_sales_customers_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Idempotente: crea tablas e índices solo si faltan.

    Ajuste debido a ejecuciones múltiples / historial inconsistente donde las tablas
    ya pueden existir. Evita errores DuplicateTable / DuplicateIndex.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def table_has_index(table: str, index_name: str) -> bool:
        if table not in existing_tables:
            return False
        try:
            return any(ix.get('name') == index_name for ix in inspector.get_indexes(table))
        except Exception:
            return False

    # Si ambas tablas existen ya, hacemos noop temprano para evitar tocar constraints y que falle la transacción si algo está corrupto.
    if 'returns' in existing_tables and 'return_lines' in existing_tables:
        # No intentar recrear nada. Registro informativo (op.execute para quedar en log DB).
        try:
            op.execute("-- returns_module noop: tablas ya existen")
        except Exception:
            pass
        return

    # Tabla returns (solo si falta)
    if 'returns' not in existing_tables:
        op.create_table(
            "returns",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="REGISTRADA"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
        )
    # Constraint check (si falta)
    if 'returns' in existing_tables:
        # No hay API directa para introspección de check constraints portable, intentar crear y capturar error.
        try:
            op.create_check_constraint(
                "ck_returns_status", "returns", "status IN ('BORRADOR','REGISTRADA','ANULADA')"
            )
        except Exception:
            pass
    if not table_has_index('returns', 'ix_returns_sale_id'):
        try:
            op.create_index("ix_returns_sale_id", "returns", ["sale_id"], unique=False)
        except Exception:
            pass

    # Tabla return_lines
    if 'return_lines' not in existing_tables:
        op.create_table(
            "return_lines",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("return_id", sa.Integer(), sa.ForeignKey("returns.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sale_line_id", sa.Integer(), sa.ForeignKey("sale_lines.id", ondelete="SET NULL"), nullable=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("qty", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("subtotal", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("note", sa.Text(), nullable=True),
        )
    if not table_has_index('return_lines', 'ix_return_lines_return_id'):
        try:
            op.create_index("ix_return_lines_return_id", "return_lines", ["return_id"], unique=False)
        except Exception:
            pass
    if not table_has_index('return_lines', 'ix_return_lines_product_id'):
        try:
            op.create_index("ix_return_lines_product_id", "return_lines", ["product_id"], unique=False)
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    def safe_drop_index(name: str, table: str):
        if table not in existing_tables:
            return
        try:
            op.drop_index(name, table_name=table)
        except Exception:
            pass

    if 'return_lines' in existing_tables:
        safe_drop_index("ix_return_lines_product_id", 'return_lines')
        safe_drop_index("ix_return_lines_return_id", 'return_lines')
        try:
            op.drop_table('return_lines')
        except Exception:
            pass
    if 'returns' in existing_tables:
        safe_drop_index("ix_returns_sale_id", 'returns')
        try:
            op.drop_constraint("ck_returns_status", "returns", type_="check")
        except Exception:
            pass
        try:
            op.drop_table('returns')
        except Exception:
            pass
