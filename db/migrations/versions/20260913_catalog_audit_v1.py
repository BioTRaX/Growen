#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260913_catalog_audit_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260913_catalog_audit_v1.py
# NG-HEADER: Descripción: Persistencia e idempotencia del auditor autónomo de catálogo.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Auditor autónomo, feedback versionado y cuarentena canónica."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260913_catalog_audit_v1"
down_revision = "20260909_user_active"
branch_labels = None
depends_on = None


def _json_type(bind):
    return postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name == "postgresql" else sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type(bind)
    op.create_table(
        "catalog_audit_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False, server_default="full"),
        sa.Column("include_orphans", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("enrich_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_fix", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("is_active_slot", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requested_ids", json_type, nullable=True, server_default="[]"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clean_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issue_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("scope IN ('all','pending','selected')", name="ck_catalog_audit_runs_scope"),
        sa.CheckConstraint("mode IN ('full','deterministic_only')", name="ck_catalog_audit_runs_mode"),
        sa.CheckConstraint(
            "status IN ('queued','running','waiting_enrich','completed','completed_with_issues','failed','cancelled')",
            name="ck_catalog_audit_runs_status",
        ),
        sa.CheckConstraint(
            "(status IN ('queued','running','waiting_enrich') AND is_active_slot = true) OR "
            "(status NOT IN ('queued','running','waiting_enrich') AND is_active_slot = false)",
            name="ck_catalog_audit_runs_active_slot",
        ),
    )
    op.create_index(
        "uq_catalog_audit_runs_active", "catalog_audit_runs", ["is_active_slot"], unique=True,
        postgresql_where=sa.text("is_active_slot = true"), sqlite_where=sa.text("is_active_slot = 1"),
    )
    op.create_table(
        "catalog_audit_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=True),
        sa.Column("product_class", sa.String(32), nullable=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload_json", json_type, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('classification','exception','correction')", name="ck_catalog_audit_feedback_kind"),
    )
    op.create_index(
        "ix_catalog_audit_feedback_scope", "catalog_audit_feedback",
        ["canonical_product_id", "product_class", "active"],
    )
    op.create_table(
        "catalog_audit_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("catalog_audit_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("canonical_product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_key", sa.String(80), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("rules_version", sa.String(64), nullable=False),
        sa.Column("feedback_version", sa.String(64), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("product_class", sa.String(32), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("findings_json", json_type, nullable=True),
        sa.Column("corrections_json", json_type, nullable=True, server_default="[]"),
        sa.Column("semantic_json", json_type, nullable=True),
        sa.Column("evidence_json", json_type, nullable=True, server_default="[]"),
        sa.Column("enrichment_job_id", sa.String(64), sa.ForeignKey("canonical_enrichment_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reused_item_id", sa.Integer(), sa.ForeignKey("catalog_audit_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("auto_fix_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution", sa.String(32), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','skipped_unchanged','canonical_required','waiting_enrich','auditing','clean','auto_fixed','needs_review','quarantined','failed','cancelled')",
            name="ck_catalog_audit_items_status",
        ),
        sa.UniqueConstraint("run_id", "target_key", name="uq_catalog_audit_items_run_target"),
    )
    op.create_index("ix_catalog_audit_items_run_status", "catalog_audit_items", ["run_id", "status"])
    op.create_index(
        "ix_catalog_audit_items_identity", "catalog_audit_items",
        ["canonical_product_id", "input_hash", "rules_version"],
    )
    with op.batch_alter_table("canonical_products") as batch:
        batch.add_column(sa.Column("catalog_audit_status", sa.String(24), nullable=False, server_default="unaudited"))
        batch.add_column(sa.Column("last_catalog_audit_item_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("catalog_audited_at", sa.DateTime(), nullable=True))
        batch.create_foreign_key(
            "fk_canonical_products_last_catalog_audit_item", "catalog_audit_items",
            ["last_catalog_audit_item_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("catalog_audit_feedback", "catalog_audit_items", "catalog_audit_runs"):
        if bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError("catalog_audit_downgrade_would_delete_history")
    with op.batch_alter_table("canonical_products") as batch:
        batch.drop_constraint("fk_canonical_products_last_catalog_audit_item", type_="foreignkey")
        batch.drop_column("catalog_audited_at")
        batch.drop_column("last_catalog_audit_item_id")
        batch.drop_column("catalog_audit_status")
    op.drop_index("ix_catalog_audit_items_identity", table_name="catalog_audit_items")
    op.drop_index("ix_catalog_audit_items_run_status", table_name="catalog_audit_items")
    op.drop_table("catalog_audit_items")
    op.drop_index("ix_catalog_audit_feedback_scope", table_name="catalog_audit_feedback")
    op.drop_table("catalog_audit_feedback")
    op.drop_index("uq_catalog_audit_runs_active", table_name="catalog_audit_runs")
    op.drop_table("catalog_audit_runs")
