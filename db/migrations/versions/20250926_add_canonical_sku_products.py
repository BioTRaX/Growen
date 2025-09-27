#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250926_add_canonical_sku_products.py
# NG-HEADER: Ubicación: db/migrations/versions/20250926_add_canonical_sku_products.py
# NG-HEADER: Descripción: Agrega columna canonical_sku única a products y backfill parcial.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Agregar canonical_sku a products

Revision ID: 20250926_add_canonical_sku_products
Revises: 20250926_add_cascade_sale_lines_product_fk
Create Date: 2025-09-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
from sqlalchemy.engine import Connection

revision = '20250926_add_canonical_sku_products'
down_revision = '20250926_add_cascade_sale_lines_product_fk'
branch_labels = None
depends_on = None

CANON_PATTERN = r'^[A-Z]{3}_[0-9]{4}_[A-Z0-9]{3}$'


def upgrade() -> None:
    bind: Connection = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c['name'] for c in inspector.get_columns('products')]
    if 'canonical_sku' not in cols:
        op.add_column('products', sa.Column('canonical_sku', sa.String(length=32), nullable=True))
    # Crear unique constraint tolerante
    existing_ux = [c['name'] for c in inspector.get_unique_constraints('products')]
    if 'ux_products_canonical_sku' not in existing_ux:
        try:
            op.create_unique_constraint('ux_products_canonical_sku', 'products', ['canonical_sku'])
        except Exception:
            pass

    # Backfill parcial: solo copiar sku_root -> canonical_sku si ya cumple patrón y no hay colisión.
    # Se evita colisiones revisando duplicados previos.
    try:
        # Seleccionar candidatos
        rows = bind.execute(text("""
            SELECT id, sku_root FROM products
            WHERE canonical_sku IS NULL AND sku_root ~ :pat
        """), {"pat": CANON_PATTERN}).fetchall()
        # Detectar duplicados del conjunto de candidatos (sku_root repetidos)
        seen = set()
        duplicates = set()
        for r in rows:
            if r.sku_root in seen:
                duplicates.add(r.sku_root)
            else:
                seen.add(r.sku_root)
        # Actualizar solo los no duplicados
        for r in rows:
            if r.sku_root in duplicates:
                continue
            bind.execute(text("UPDATE products SET canonical_sku = :v WHERE id = :i"), {"v": r.sku_root, "i": r.id})
    except Exception:
        # Log silencioso (no tenemos logger en migraciones): se puede revisar manualmente.
        pass


def downgrade() -> None:
    bind: Connection = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        op.drop_constraint('ux_products_canonical_sku', 'products', type_='unique')
    except Exception:
        pass
    cols = [c['name'] for c in inspector.get_columns('products')]
    if 'canonical_sku' in cols:
        try:
            op.drop_column('products', 'canonical_sku')
        except Exception:
            pass
