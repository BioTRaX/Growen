# NG-HEADER: Nombre de archivo: 20250901_merge_images_and_import_logs.py
# NG-HEADER: Ubicación: db/migrations/versions/20250901_merge_images_and_import_logs.py
# NG-HEADER: Descripción: Pendiente de descripción
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""merge heads: images pipeline + import logs

Revision ID: 20250901_merge_images_and_import_logs
Revises: 20250831_images_pipeline_tables, 20250901_import_logs
Create Date: 2025-09-01
"""
from __future__ import annotations

# Alembic directives
revision = "20250901_merge_images_and_import_logs"
down_revision = ("20250831_images_pipeline_tables", "20250901_import_logs")
branch_labels = None
depends_on = None


def upgrade() -> None:  # pragma: no cover
    # Merge-only revision; no operations required.
    pass


def downgrade() -> None:  # pragma: no cover
    # Merge-only revision; no operations required.
    pass
