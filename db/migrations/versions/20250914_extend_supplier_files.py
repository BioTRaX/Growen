#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20250914_extend_supplier_files.py
# NG-HEADER: Ubicación: db/migrations/versions/20250914_extend_supplier_files.py
# NG-HEADER: Descripción: Extiende supplier_files con metadatos de archivo (original_name, content_type, size_bytes)
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""extend supplier files metadata

Revision ID: 20250914_extend_supplier_files
Revises: 20250913_merge_heads
Create Date: 2025-09-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '20250914_extend_supplier_files'
down_revision = '20250913_merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('supplier_files') as batch:
        batch.add_column(sa.Column('original_name', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('content_type', sa.String(length=120), nullable=True))
        batch.add_column(sa.Column('size_bytes', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('supplier_files') as batch:
        batch.drop_column('size_bytes')
        batch.drop_column('content_type')
        batch.drop_column('original_name')
