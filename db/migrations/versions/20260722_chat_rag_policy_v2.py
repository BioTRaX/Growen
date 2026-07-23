#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260722_chat_rag_policy_v2.py
# NG-HEADER: Ubicación: db/migrations/versions/20260722_chat_rag_policy_v2.py
# NG-HEADER: Descripción: Scopes, vigencia y búsqueda híbrida del conocimiento.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Scopes, vigencia y búsqueda híbrida del conocimiento."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260722_chat_rag_policy_v2"
down_revision = "20260722_chat_identity_security_v1"
branch_labels = None
depends_on = None

JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("role_scope", JSON_TYPE, nullable=False, server_default='["admin"]'))
    op.add_column("knowledge_sources", sa.Column("channel_scope", JSON_TYPE, nullable=False, server_default='["web"]'))
    op.add_column("knowledge_sources", sa.Column("visibility", sa.String(24), nullable=False, server_default="internal"))
    op.add_column("knowledge_sources", sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("knowledge_sources", sa.Column("status", sa.String(16), nullable=False, server_default="disabled"))
    op.add_column("knowledge_sources", sa.Column("indexed_at", sa.DateTime(), nullable=True))
    op.add_column("knowledge_sources", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.create_check_constraint("ck_knowledge_sources_status", "knowledge_sources", "status IN ('active','stale','disabled')")
    op.create_index("ix_knowledge_sources_status_expiry", "knowledge_sources", ["status", "expires_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "ix_knowledge_chunks_content_fts",
            "knowledge_chunks",
            [sa.text("to_tsvector('spanish', content)")],
            postgresql_using="gin",
        )


def downgrade() -> None:
    source_count = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM knowledge_sources")
    ).scalar_one()
    if source_count:
        raise RuntimeError(
            "Downgrade bloqueado: existen políticas RAG cuya eliminación perdería trazabilidad"
        )
    if op.get_bind().dialect.name == "postgresql":
        op.drop_index("ix_knowledge_chunks_content_fts", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_sources_status_expiry", table_name="knowledge_sources")
    op.drop_constraint("ck_knowledge_sources_status", "knowledge_sources", type_="check")
    for column in ("expires_at", "indexed_at", "status", "content_version", "visibility", "channel_scope", "role_scope"):
        op.drop_column("knowledge_sources", column)
