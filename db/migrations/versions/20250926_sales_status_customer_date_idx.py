#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250926_sales_status_customer_date_idx.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_sales_status_customer_date_idx.py
# NG-HEADER: Descripción: Índices compuestos en sales para status+sale_date y customer_id+sale_date
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""add composite indexes on sales (status,sale_date) and (customer_id,sale_date)

Revision ID: 20250926_sales_status_customer_date_idx
Revises: 20250926_add_sale_kind_and_line_idx
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20250926_sales_status_customer_date_idx"
down_revision = "20250926_add_sale_kind_and_line_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Índices para acelerar listados filtrados y reportes por estado/fecha y cliente/fecha
    try:
        op.create_index("ix_sales_status_date", "sales", ["status", "sale_date"], unique=False)
    except Exception:
        pass
    try:
        op.create_index("ix_sales_customer_date", "sales", ["customer_id", "sale_date"], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    for name in ("ix_sales_customer_date", "ix_sales_status_date"):
        try:
            op.drop_index(name, table_name="sales")
        except Exception:
            pass
