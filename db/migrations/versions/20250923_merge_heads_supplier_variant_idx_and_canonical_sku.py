#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250923_merge_heads_supplier_variant_idx_and_canonical_sku.py
# NG-HEADER: Ubicación: db/migrations/versions/20250923_merge_heads_supplier_variant_idx_and_canonical_sku.py
# NG-HEADER: Descripción: Merge heads de supplier_products_internal_variant_idx y canonical_taxonomy_and_sku_custom
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""merge heads supplier_variant_idx + canonical_sku_custom

Revision ID: 20250923_merge_heads_supplier_variant_idx_and_canonical_sku
Revises: 20250922_supplier_products_internal_variant_idx, 20250923_canonical_taxonomy_and_sku_custom
Create Date: 2025-09-23
"""
from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision = '20250923_merge_heads_supplier_variant_idx_and_canonical_sku'
down_revision = ('20250922_supplier_products_internal_variant_idx', '20250923_canonical_taxonomy_and_sku_custom')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Solo merge; sin cambios de esquema.
    pass


def downgrade() -> None:
    # No deshacer: evitamos reintroducir ramas.
    pass
