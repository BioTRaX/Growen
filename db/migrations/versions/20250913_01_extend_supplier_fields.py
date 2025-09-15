#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250913_01_extend_supplier_fields.py
# NG-HEADER: Ubicación: db/migrations/versions/20250913_01_extend_supplier_fields.py
# NG-HEADER: Descripción: Agrega campos extendidos a suppliers (contacto, ubicación, notas)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""extend supplier fields

Revision ID: extend_supplier_fields_20250913
Revises: 20250901_merge_images_and_import_logs
Create Date: 2025-09-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'extend_supplier_fields_20250913'
down_revision = '20250901_merge_images_and_import_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('suppliers', sa.Column('location', sa.String(length=200), nullable=True))
    op.add_column('suppliers', sa.Column('contact_name', sa.String(length=100), nullable=True))
    op.add_column('suppliers', sa.Column('contact_email', sa.String(length=200), nullable=True))
    op.add_column('suppliers', sa.Column('contact_phone', sa.String(length=50), nullable=True))
    op.add_column('suppliers', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('suppliers', sa.Column('extra_json', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('suppliers', 'extra_json')
    op.drop_column('suppliers', 'notes')
    op.drop_column('suppliers', 'contact_phone')
    op.drop_column('suppliers', 'contact_email')
    op.drop_column('suppliers', 'contact_name')
    op.drop_column('suppliers', 'location')
