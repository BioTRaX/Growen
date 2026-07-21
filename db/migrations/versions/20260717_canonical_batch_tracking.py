#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260717_canonical_batch_tracking.py
# NG-HEADER: Ubicación: db/migrations/versions/20260717_canonical_batch_tracking.py
# NG-HEADER: Descripción: Persiste el progreso y los resultados del alta masiva canónica.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Persistir seguimiento del alta masiva canónica.

Revision ID: 20260717_canonical_batch_tracking
Revises: c923732e1cab
"""

from alembic import op
import sqlalchemy as sa
import re


revision = "20260717_canonical_batch_tracking"
down_revision = "c923732e1cab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("canonical_batch_jobs"):
        op.create_table(
            "canonical_batch_jobs",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("client_request_id", sa.String(64), nullable=False, unique=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
            sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_canonical_batch_jobs_status", "canonical_batch_jobs", ["status"])
        op.create_index("ix_canonical_batch_jobs_created_by", "canonical_batch_jobs", ["created_by_user_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("canonical_batch_job_items"):
        op.create_table(
            "canonical_batch_job_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.String(64), sa.ForeignKey("canonical_batch_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("source_product_id", sa.Integer(), sa.ForeignKey("supplier_products.id", ondelete="SET NULL"), nullable=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("brand", sa.String(100), nullable=True),
            sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("subcategory_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="SET NULL"), nullable=True),
            sa.Column("requested_sku", sa.String(32), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
            sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="SET NULL"), nullable=True),
            sa.Column("sku_custom", sa.String(32), nullable=True),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("error_message", sa.String(500), nullable=True),
            sa.UniqueConstraint("job_id", "position", name="uq_canonical_batch_job_position"),
        )
        op.create_index("ix_canonical_batch_job_items_status", "canonical_batch_job_items", ["status"])

    # Sincroniza la tabla transaccional con SKUs creados por la lógica histórica
    # basada en MAX(). De este modo el primer alta con el generador común no
    # intenta reutilizar números ya asignados.
    if sa.inspect(bind).has_table("sku_sequences") and sa.inspect(bind).has_table("canonical_products"):
        maxima: dict[str, int] = {}
        pattern = re.compile(r"^([A-Z]{3})_([0-9]{4})_[A-Z0-9]{3}$")
        for value in bind.execute(sa.text("SELECT sku_custom FROM canonical_products WHERE sku_custom IS NOT NULL")).scalars():
            match = pattern.fullmatch(value or "")
            if match:
                prefix, number = match.groups()
                maxima[prefix] = max(maxima.get(prefix, 0), int(number))
        for prefix, maximum in maxima.items():
            current = bind.execute(
                sa.text("SELECT next_seq FROM sku_sequences WHERE category_code = :prefix"),
                {"prefix": prefix},
            ).scalar_one_or_none()
            if current is None:
                bind.execute(
                    sa.text("INSERT INTO sku_sequences(category_code, next_seq) VALUES (:prefix, :next_seq)"),
                    {"prefix": prefix, "next_seq": maximum + 1},
                )
            elif current <= maximum:
                bind.execute(
                    sa.text("UPDATE sku_sequences SET next_seq = :next_seq WHERE category_code = :prefix"),
                    {"prefix": prefix, "next_seq": maximum + 1},
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("canonical_batch_job_items"):
        op.drop_table("canonical_batch_job_items")
    inspector = sa.inspect(bind)
    if inspector.has_table("canonical_batch_jobs"):
        op.drop_table("canonical_batch_jobs")
