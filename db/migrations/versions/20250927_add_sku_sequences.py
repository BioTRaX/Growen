#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250927_add_sku_sequences.py
# NG-HEADER: Ubicación: db/migrations/versions/20250927_add_sku_sequences.py
# NG-HEADER: Descripción: Crea tabla sku_sequences para secuenciar números canónicos por categoría (XXX)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Crear tabla sku_sequences para control de secuencia canónica

Revision ID: 20250927_add_sku_sequences
Revises: 20250926_add_canonical_sku_products
Create Date: 2025-09-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '20250927_add_sku_sequences'
down_revision = '20250926_add_canonical_sku_products'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea tabla sku_sequences.

    category_code: código de 3 letras (PK) que corresponde al bloque XXX del SKU canónico.
    next_seq: próximo entero a asignar (el primer SKU generado usará next_seq y luego incrementará en 1).
    """
    op.create_table(
        'sku_sequences',
        sa.Column('category_code', sa.String(length=3), primary_key=True),
        sa.Column('next_seq', sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('sku_sequences')
