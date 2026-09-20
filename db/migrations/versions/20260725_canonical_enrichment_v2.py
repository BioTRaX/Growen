#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260725_canonical_enrichment_v2.py
# NG-HEADER: Ubicación: db/migrations/versions/20260725_canonical_enrichment_v2.py
# NG-HEADER: Descripción: Contenido canónico, jobs persistentes y retiro del precio de mercado legacy.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Contenido canónico, jobs persistentes y retiro del precio de mercado legacy."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260725_canonical_enrichment_v2"
down_revision = "20260722_chat_observability_v3"
branch_labels = None
depends_on = None


def _json_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def _plain(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _key(value):
    if value is None or value == "" or value == {}:
        return None
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, default=str)


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type(bind)

    with op.batch_alter_table("canonical_products") as batch:
        batch.add_column(sa.Column("description_html", sa.Text(), nullable=True))
        batch.add_column(sa.Column("weight_kg", sa.Numeric(10, 3), nullable=True))
        batch.add_column(sa.Column("height_cm", sa.Numeric(10, 2), nullable=True))
        batch.add_column(sa.Column("width_cm", sa.Numeric(10, 2), nullable=True))
        batch.add_column(sa.Column("depth_cm", sa.Numeric(10, 2), nullable=True))
        batch.add_column(sa.Column("technical_specs", json_type, nullable=True, server_default="{}"))
        batch.add_column(sa.Column("usage_instructions", json_type, nullable=True, server_default="{}"))
        batch.add_column(sa.Column("content_revision", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_enriched_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("enriched_by", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_canonical_products_enriched_by_users", "users", ["enriched_by"], ["id"], ondelete="SET NULL"
        )

    op.create_table(
        "canonical_enrichment_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_request_id", sa.String(64), nullable=False, unique=True),
        sa.Column("batch_id", sa.String(64), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="full"),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(24), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(40), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("config_snapshot", json_type, nullable=True),
        sa.Column("result_json", json_type, nullable=True),
        sa.Column("applied_fields", json_type, nullable=True, server_default="[]"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','review_required','partially_applied','applied','failed','cancelled','discarded')",
            name="ck_canonical_enrichment_jobs_status",
        ),
        sa.CheckConstraint("scope IN ('full','description','technical')", name="ck_canonical_enrichment_jobs_scope"),
    )
    op.create_index(
        "ix_canonical_enrichment_jobs_canonical_created",
        "canonical_enrichment_jobs",
        ["canonical_product_id", "created_at"],
    )
    op.create_index("ix_canonical_enrichment_jobs_batch_id", "canonical_enrichment_jobs", ["batch_id"])
    op.create_index(
        "uq_canonical_enrichment_jobs_active",
        "canonical_enrichment_jobs",
        ["canonical_product_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running')"),
        sqlite_where=sa.text("status IN ('queued','running')"),
    )

    op.create_table(
        "canonical_enrichment_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("canonical_enrichment_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("evidence_json", json_type, nullable=True),
        sa.Column("accessed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("job_id", "url", name="uq_canonical_enrichment_source_url"),
    )
    op.create_index("ix_canonical_enrichment_sources_job", "canonical_enrichment_sources", ["job_id"])

    op.create_table(
        "canonical_content_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("origin", sa.String(32), nullable=False),
        sa.Column("origin_product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(64), sa.ForeignKey("canonical_enrichment_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", json_type, nullable=False),
        sa.Column("is_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_canonical_content_versions_canonical_created",
        "canonical_content_versions",
        ["canonical_product_id", "created_at"],
    )
    versions_table = sa.table(
        "canonical_content_versions",
        sa.column("canonical_product_id", sa.Integer()),
        sa.column("origin", sa.String()),
        sa.column("origin_product_id", sa.Integer()),
        sa.column("revision", sa.Integer()),
        sa.column("snapshot_json", json_type),
        sa.column("is_applied", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
    )
    canonical_table = sa.table(
        "canonical_products",
        sa.column("id", sa.Integer()),
        sa.column("description_html", sa.Text()),
        sa.column("weight_kg", sa.Numeric(10, 3)),
        sa.column("height_cm", sa.Numeric(10, 2)),
        sa.column("width_cm", sa.Numeric(10, 2)),
        sa.column("depth_cm", sa.Numeric(10, 2)),
        sa.column("technical_specs", json_type),
        sa.column("usage_instructions", json_type),
        sa.column("content_revision", sa.Integer()),
        sa.column("last_enriched_at", sa.DateTime()),
        sa.column("enriched_by", sa.Integer()),
    )

    rows = bind.execute(sa.text(
        """
        SELECT DISTINCT pe.canonical_product_id, p.id AS product_id,
               p.description_html, p.weight_kg, p.height_cm, p.width_cm, p.depth_cm,
               p.technical_specs, p.usage_instructions, p.last_enriched_at, p.enriched_by
        FROM product_equivalences pe
        JOIN supplier_products sp ON sp.id = pe.supplier_product_id
        JOIN products p ON p.id = sp.internal_product_id
        ORDER BY pe.canonical_product_id, p.id
        """
    )).mappings().all()
    grouped: dict[int, list[dict]] = {}
    now = datetime.utcnow()
    for row in rows:
        snapshot = {
            "description_html": row["description_html"],
            "weight_kg": _plain(row["weight_kg"]),
            "height_cm": _plain(row["height_cm"]),
            "width_cm": _plain(row["width_cm"]),
            "depth_cm": _plain(row["depth_cm"]),
            "technical_specs": row["technical_specs"] or {},
            "usage_instructions": row["usage_instructions"] or {},
            "legacy_sources": True,
        }
        if not any(_key(value) for key, value in snapshot.items() if key != "legacy_sources"):
            continue
        grouped.setdefault(int(row["canonical_product_id"]), []).append({
            "product_id": int(row["product_id"]),
            "snapshot": snapshot,
            "last_enriched_at": row["last_enriched_at"],
            "enriched_by": row["enriched_by"],
        })
        bind.execute(
            versions_table.insert().values(
                canonical_product_id=row["canonical_product_id"],
                origin="legacy_product",
                origin_product_id=row["product_id"],
                revision=0,
                snapshot_json=snapshot,
                is_applied=False,
                created_at=now,
            )
        )

    fields = (
        "description_html", "weight_kg", "height_cm", "width_cm", "depth_cm",
        "technical_specs", "usage_instructions",
    )
    for canonical_id, candidates in grouped.items():
        applied: dict = {}
        for field in fields:
            values = {_key(item["snapshot"].get(field)): item["snapshot"].get(field) for item in candidates}
            values.pop(None, None)
            if len(values) == 1:
                applied[field] = next(iter(values.values()))
        if not applied:
            continue
        trace = max(candidates, key=lambda item: item["last_enriched_at"] or datetime.min)
        bind.execute(
            canonical_table.update()
            .where(canonical_table.c.id == canonical_id)
            .values(
                description_html=applied.get("description_html"),
                weight_kg=applied.get("weight_kg"),
                height_cm=applied.get("height_cm"),
                width_cm=applied.get("width_cm"),
                depth_cm=applied.get("depth_cm"),
                technical_specs=applied.get("technical_specs") or {},
                usage_instructions=applied.get("usage_instructions") or {},
                content_revision=1,
                last_enriched_at=trace["last_enriched_at"],
                enriched_by=trace["enriched_by"],
            )
        )
        bind.execute(
            versions_table.insert().values(
                canonical_product_id=canonical_id,
                origin="legacy_backfill",
                origin_product_id=None,
                revision=1,
                snapshot_json=applied,
                is_applied=True,
                created_at=now,
            )
        )

    with op.batch_alter_table("products") as batch:
        batch.drop_column("market_price_reference")


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade bloqueado: products.market_price_reference fue retirado por ser una fuente no confiable."
    )
