# NG-HEADER: Nombre de archivo: cf0f6e70fe89_add_rag_knowledge_tables.py
# NG-HEADER: Ubicación: db/migrations/versions/cf0f6e70fe89_add_rag_knowledge_tables.py
# NG-HEADER: Descripción: Conserva como no-op una revisión RAG autogenerada y descartada.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Conserva la rama RAG autogenerada como revisión descartada.

Revision ID: cf0f6e70fe89
Revises: c0467ef5320e
Create Date: 2025-11-25 18:58:01.516760

La versión original incluía cientos de operaciones autogeneradas ajenas a RAG,
entre ellas eliminaciones de tablas, columnas, constraints e índices. La rama
paralela ``b2d22a7ce889`` contiene la implementación manual y acotada de las
tablas de conocimiento. Esta revisión se conserva como no-op para no romper el
grafo histórico ni el merge ``fa50a5cba1bb``.
"""

revision = "cf0f6e70fe89"
down_revision = "c0467ef5320e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No aplica cambios; la implementación RAG vive en ``b2d22a7ce889``."""


def downgrade() -> None:
    """No revierte cambios porque esta revisión no crea objetos."""
