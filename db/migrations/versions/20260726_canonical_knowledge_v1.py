#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260726_canonical_knowledge_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260726_canonical_knowledge_v1.py
# NG-HEADER: Descripción: Base de conocimiento canónica y reemplazo de fuentes de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Base de conocimiento canónica y reemplazo de fuentes de Mercado."""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260726_canonical_knowledge_v1"
down_revision = "20260725_canonical_enrichment_v2"
branch_labels = None
depends_on = None


CAPABILITIES = {
    "description": "Descripción",
    "technical_specs": "Datos técnicos",
    "compatibility": "Compatibilidad",
    "images": "Imágenes",
    "manuals": "Manuales",
    "price": "Precio",
    "availability": "Disponibilidad",
    "offers": "Ofertas",
    "seo": "SEO",
    "video": "Video",
    "warranty": "Garantía",
    "certifications": "Certificaciones",
}


def _json_type(bind):
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB(astext_type=sa.Text())
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type(bind)

    op.create_table(
        "knowledge_capabilities",
        sa.Column("code", sa.String(48), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    bind.execute(
        sa.text(
            "INSERT INTO knowledge_capabilities (code, name, is_active) "
            "VALUES (:code, :name, true)"
        ),
        [{"code": code, "name": name} for code, name in CAPABILITIES.items()],
    )

    op.create_table(
        "canonical_knowledge_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("asset_type", sa.String(24), nullable=False, server_default="web"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("origin", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("exclude_from_enrichment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trust_breakdown", json_type, nullable=True),
        sa.Column("ai_trust_adjustment", sa.Float(), nullable=True),
        sa.Column("ai_trust_reason", json_type, nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("asset_type IN ('web','document','image','video')", name="ck_canonical_knowledge_assets_type"),
        sa.CheckConstraint("status IN ('pending','confirmed','archived')", name="ck_canonical_knowledge_assets_status"),
    )
    op.create_index("ix_canonical_knowledge_assets_product_status", "canonical_knowledge_assets", ["canonical_product_id", "status"])

    op.create_table(
        "canonical_knowledge_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("normalized_url", sa.String(2000), nullable=True),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("mime_type", sa.String(160), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('pending','ready','failed','stale','archived')", name="ck_canonical_knowledge_locations_status"),
    )
    op.create_index("ix_canonical_knowledge_locations_asset", "canonical_knowledge_locations", ["asset_id"])
    op.create_index("ix_canonical_knowledge_locations_hash", "canonical_knowledge_locations", ["content_hash"])
    op.create_index(
        "uq_canonical_knowledge_location_url",
        "canonical_knowledge_locations",
        ["asset_id", "normalized_url"],
        unique=True,
        postgresql_where=sa.text("normalized_url IS NOT NULL"),
        sqlite_where=sa.text("normalized_url IS NOT NULL"),
    )

    op.create_table(
        "canonical_knowledge_labels",
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("label", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "label IN ('manufacturer','supplier','market','manual','catalog','msds','official','other')",
            name="ck_canonical_knowledge_labels_value",
        ),
    )
    op.create_table(
        "canonical_knowledge_asset_capabilities",
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("capability_code", sa.String(48), sa.ForeignKey("knowledge_capabilities.code", ondelete="RESTRICT"), primary_key=True),
        sa.Column("origin", sa.String(24), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "canonical_knowledge_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("location_id", "version", name="uq_canonical_knowledge_location_version"),
    )
    op.create_index("ix_canonical_knowledge_versions_asset_created", "canonical_knowledge_versions", ["asset_id", "created_at"])
    op.create_table(
        "canonical_knowledge_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("capability_code", sa.String(48), sa.ForeignKey("knowledge_capabilities.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("fact_key", sa.String(160), nullable=False),
        sa.Column("value_json", json_type, nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="proposed"),
        sa.Column("evidence_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('proposed','confirmed','contradicted','rejected')", name="ck_canonical_knowledge_claims_status"),
    )
    op.create_index("ix_canonical_knowledge_claims_product_key", "canonical_knowledge_claims", ["canonical_product_id", "fact_key"])
    op.create_table(
        "canonical_knowledge_facts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_key", sa.String(160), nullable=False),
        sa.Column("capability_code", sa.String(48), sa.ForeignKey("knowledge_capabilities.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("value_json", json_type, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="confirmed"),
        sa.Column("supporting_claim_ids", json_type, nullable=False, server_default="[]"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("canonical_product_id", "fact_key", name="uq_canonical_knowledge_fact_key"),
    )
    op.create_table(
        "canonical_knowledge_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_canonical_knowledge_events_asset_created", "canonical_knowledge_events", ["asset_id", "created_at"])
    op.create_table(
        "canonical_knowledge_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("canonical_knowledge_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(32), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result_json", json_type, nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_canonical_knowledge_jobs_asset_created", "canonical_knowledge_jobs", ["asset_id", "created_at"])
    op.create_index(
        "uq_canonical_knowledge_jobs_active",
        "canonical_knowledge_jobs",
        ["asset_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running')"),
        sqlite_where=sa.text("status IN ('queued','running')"),
    )

    op.rename_table("market_sources", "canonical_knowledge_market_profiles")
    op.add_column("canonical_knowledge_market_profiles", sa.Column("asset_id", sa.Integer(), nullable=True))

    rows = bind.execute(
        sa.text(
            "SELECT id, product_id, source_name, url, created_by_user_id, created_at, "
            "validation_status FROM canonical_knowledge_market_profiles ORDER BY id"
        )
    ).mappings().all()
    for row in rows:
        trust = 72.0 if row["validation_status"] != "rejected" else 35.0
        assets_table = sa.table(
            "canonical_knowledge_assets",
            sa.column("id", sa.Integer()),
            sa.column("canonical_product_id", sa.Integer()),
            sa.column("title", sa.String()),
            sa.column("asset_type", sa.String()),
            sa.column("status", sa.String()),
            sa.column("origin", sa.String()),
            sa.column("exclude_from_enrichment", sa.Boolean()),
            sa.column("trust_score", sa.Float()),
            sa.column("trust_breakdown", sa.JSON()),
            sa.column("revision", sa.Integer()),
            sa.column("created_by_user_id", sa.Integer()),
            sa.column("created_at", sa.DateTime()),
            sa.column("updated_at", sa.DateTime()),
        )
        created_at = row["created_at"] or datetime.utcnow()
        asset_id = bind.execute(
            sa.insert(assets_table)
            .values(
                canonical_product_id=row["product_id"],
                title=row["source_name"],
                asset_type="web",
                status="confirmed",
                origin="market_backfill",
                exclude_from_enrichment=False,
                trust_score=trust,
                trust_breakdown={"authority": trust, "backfill": True},
                revision=1,
                created_by_user_id=row["created_by_user_id"],
                created_at=created_at,
                updated_at=created_at,
            )
            .returning(assets_table.c.id)
        ).scalar_one()
        bind.execute(
            sa.text("INSERT INTO canonical_knowledge_labels (asset_id, label) VALUES (:id, 'market')"),
            {"id": asset_id},
        )
        for capability in ("price", "availability", "offers"):
            bind.execute(
                sa.text(
                    "INSERT INTO canonical_knowledge_asset_capabilities "
                    "(asset_id, capability_code, origin, confidence, enabled) "
                    "VALUES (:id, :capability, 'market_backfill', :confidence, true)"
                ),
                {"id": asset_id, "capability": capability, "confidence": trust / 100},
            )
        if row["url"]:
            bind.execute(
                sa.text(
                    "INSERT INTO canonical_knowledge_locations "
                    "(asset_id, url, normalized_url, status, is_primary, created_at, updated_at) "
                    "VALUES (:id, :url, :url, 'pending', true, :created_at, :created_at)"
                ),
                {"id": asset_id, "url": row["url"], "created_at": row["created_at"] or datetime.utcnow()},
            )
        bind.execute(
            sa.text("UPDATE canonical_knowledge_market_profiles SET asset_id=:asset_id WHERE id=:id"),
            {"asset_id": asset_id, "id": row["id"]},
        )

    with op.batch_alter_table("canonical_knowledge_market_profiles") as batch:
        batch.alter_column("asset_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_canonical_knowledge_market_profiles_asset",
            "canonical_knowledge_assets",
            ["asset_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint("uq_canonical_knowledge_market_profile_asset", ["asset_id"])
        batch.drop_column("product_id")
        batch.drop_column("source_name")
        batch.drop_column("url")

    with op.batch_alter_table("canonical_enrichment_sources") as batch:
        batch.add_column(sa.Column("knowledge_asset_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("knowledge_version_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_canonical_enrichment_sources_asset",
            "canonical_knowledge_assets",
            ["knowledge_asset_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_canonical_enrichment_sources_version",
            "canonical_knowledge_versions",
            ["knowledge_version_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade bloqueado: reconstruir market_sources perdería activos, capacidades, "
        "versiones, claims y auditoría de conocimiento canónico."
    )
