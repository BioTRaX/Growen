#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250913_merge_heads.py
# NG-HEADER: Ubicación: db/migrations/versions/20250913_merge_heads.py
# NG-HEADER: Descripción: Merge de ramas de migraciones (services registry + extend supplier fields)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""merge heads services_registry + extend_supplier_fields

Revision ID: 20250913_merge_heads
Revises: 20250904_services_registry, extend_supplier_fields_20250913
Create Date: 2025-09-13
"""
from __future__ import annotations

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

# revision identifiers, used by Alembic.
revision = '20250913_merge_heads'
down_revision = ('20250904_services_registry', 'extend_supplier_fields_20250913')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema changes; this migration only merges two heads.
    pass


def downgrade() -> None:
    # Downgrade would branch again; keep as noop.
    pass
