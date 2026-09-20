#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260721_market_observability_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260721_market_observability_v1.py
# NG-HEADER: Descripción: Jobs, observaciones, validación y alertas persistentes de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Observabilidad e histórico auditable para Mercado.

Revision ID: 20260721_market_observability_v1
Revises: 20260718_product_taxonomy_tags_v1
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260721_market_observability_v1"
down_revision = "20260718_product_taxonomy_tags_v1"
branch_labels = None
depends_on = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # El tipo extensible evita que cada nuevo método de captura exija alterar
        # un ENUM PostgreSQL y permite usar "manual" en este mismo upgrade.
        op.execute(
            "ALTER TABLE market_sources ALTER COLUMN source_type TYPE VARCHAR(16) "
            "USING source_type::text"
        )
    source_checks = {
        check.get("name")
        for check in sa.inspect(bind).get_check_constraints("market_sources")
    }
    if "ck_market_sources_source_type" not in source_checks:
        op.create_check_constraint(
            "ck_market_sources_source_type",
            "market_sources",
            "source_type IS NULL OR source_type IN ('static','dynamic','manual')",
        )

    if not _has_table("market_update_jobs"):
        op.create_table(
            "market_update_jobs",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("trigger", sa.String(24), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
            sa.Column("config_snapshot", JSON_TYPE, nullable=True),
            sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("processed_items", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('queued','running','partial','succeeded','failed','cancelled')",
                name="ck_market_update_jobs_status",
            ),
        )
        op.create_index("ix_market_update_jobs_status_created", "market_update_jobs", ["status", "created_at"])

    if not _has_table("market_update_items"):
        op.create_table(
            "market_update_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.String(64), sa.ForeignKey("market_update_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sources_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sources_succeeded", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sources_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("market_price_reference", sa.Numeric(12, 2), nullable=True),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('queued','running','partial','succeeded','failed','cancelled')",
                name="ck_market_update_items_status",
            ),
        )
        op.create_index("ix_market_update_items_job_status", "market_update_items", ["job_id", "status"])
        op.create_index("ix_market_update_items_product_created", "market_update_items", ["product_id", "created_at"])
        op.create_index(
            "uq_market_update_items_active_product",
            "market_update_items",
            ["product_id"],
            unique=True,
            postgresql_where=sa.text("status IN ('queued','running')"),
            sqlite_where=sa.text("status IN ('queued','running')"),
        )

    source_columns = [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_status", sa.String(24), nullable=False, server_default="warning"),
        sa.Column("ars_confirmed", sa.Boolean(), nullable=True),
        sa.Column("argentina_delivery_confirmed", sa.Boolean(), nullable=True),
        sa.Column("validation_detail", JSON_TYPE, nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    ]
    for column in source_columns:
        _add_column("market_sources", column)
    if bind.dialect.name == "postgresql":
        op.alter_column("market_sources", "url", existing_type=sa.String(500), nullable=True)
    else:
        with op.batch_alter_table("market_sources") as batch:
            batch.alter_column("url", existing_type=sa.String(500), nullable=True)
    foreign_names = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("market_sources")}
    if "fk_market_sources_created_by" not in foreign_names:
        op.create_foreign_key(
            "fk_market_sources_created_by", "market_sources", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL"
        )

    history_columns = [
        sa.Column("observation_type", sa.String(16), nullable=False, server_default="source"),
        sa.Column("capture_method", sa.String(16), nullable=False, server_default="static"),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.Column("job_item_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
    ]
    for column in history_columns:
        _add_column("market_price_history", column)
    history_fks = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("market_price_history")}
    for name, local, remote_table in (
        ("fk_market_history_job", "job_id", "market_update_jobs"),
        ("fk_market_history_job_item", "job_item_id", "market_update_items"),
        ("fk_market_history_created_by", "created_by_user_id", "users"),
    ):
        if name not in history_fks:
            op.create_foreign_key(name, "market_price_history", remote_table, [local], ["id"], ondelete="SET NULL")

    if not _has_table("market_update_source_results"):
        op.create_table(
            "market_update_source_results",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("market_update_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("market_sources.id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("used_browser", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("observation_id", sa.Integer(), sa.ForeignKey("market_price_history.id", ondelete="SET NULL"), nullable=True),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retryable", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('queued','running','succeeded','failed','skipped')",
                name="ck_market_update_source_results_status",
            ),
        )
        op.create_index(
            "ix_market_update_source_results_item_status", "market_update_source_results", ["item_id", "status"]
        )

    if not _has_table("market_alerts"):
        alert_type = sa.Enum(
            "sale_vs_market", "market_vs_previous", "market_spike", "market_drop", name="market_alert_type_enum"
        )
        severity = sa.Enum("low", "medium", "high", "critical", name="alert_severity_enum")
        op.create_table(
            "market_alerts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("canonical_products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("alert_type", alert_type, nullable=False),
            sa.Column("severity", severity, nullable=False, server_default="medium"),
            sa.Column("old_value", sa.Numeric(12, 2), nullable=True),
            sa.Column("new_value", sa.Numeric(12, 2), nullable=False),
            sa.Column("delta_percentage", sa.Numeric(10, 2), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("job_id", sa.String(64), sa.ForeignKey("market_update_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("job_item_id", sa.Integer(), sa.ForeignKey("market_update_items.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_id", sa.Integer(), sa.ForeignKey("market_sources.id", ondelete="SET NULL"), nullable=True),
            sa.Column("observation_id", sa.Integer(), sa.ForeignKey("market_price_history.id", ondelete="SET NULL"), nullable=True),
            sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("email_sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_market_alerts_product_id", "market_alerts", ["product_id"])
        op.create_index("idx_market_alerts_created_at", "market_alerts", ["created_at"])
        op.create_index("idx_market_alerts_resolved", "market_alerts", ["resolved"])
        op.create_index("idx_market_alerts_product_active", "market_alerts", ["product_id", "resolved"])
    else:
        for column in (
            sa.Column("job_id", sa.String(64), nullable=True),
            sa.Column("job_item_id", sa.Integer(), nullable=True),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("observation_id", sa.Integer(), nullable=True),
        ):
            _add_column("market_alerts", column)
        alert_fks = {fk.get("name") for fk in sa.inspect(bind).get_foreign_keys("market_alerts")}
        for name, local, remote_table in (
            ("fk_market_alerts_job", "job_id", "market_update_jobs"),
            ("fk_market_alerts_job_item", "job_item_id", "market_update_items"),
            ("fk_market_alerts_source", "source_id", "market_sources"),
            ("fk_market_alerts_observation", "observation_id", "market_price_history"),
        ):
            if name not in alert_fks:
                op.create_foreign_key(
                    name,
                    "market_alerts",
                    remote_table,
                    [local],
                    ["id"],
                    ondelete="SET NULL",
                )

    op.execute(sa.text("""
        INSERT INTO market_sources (
            product_id, source_name, url, last_price, last_checked_at, is_mandatory,
            is_active, validation_status, ars_confirmed, argentina_delivery_confirmed,
            currency, source_type, validation_detail, created_at, updated_at
        )
        SELECT cp.id, 'Referencia manual legacy', NULL, cp.market_price_reference,
               cp.market_price_updated_at, false, true, 'warning', true, NULL,
               'ARS', 'manual', '{"origin":"legacy_market_price_reference"}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM canonical_products cp
        WHERE cp.market_price_reference IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM market_sources ms
              WHERE ms.product_id = cp.id AND ms.url IS NULL AND ms.source_name = 'Referencia manual legacy'
          )
    """))
    op.execute(sa.text("""
        INSERT INTO market_price_history (
            product_id, source_id, price, currency, source_name, observation_type,
            capture_method, created_at
        )
        SELECT ms.product_id, ms.id, ms.last_price, 'ARS', ms.source_name, 'source', 'manual',
               COALESCE(ms.last_checked_at, CURRENT_TIMESTAMP)
        FROM market_sources ms
        WHERE ms.source_name = 'Referencia manual legacy'
          AND ms.last_price IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM market_price_history mph
              WHERE mph.source_id = ms.id AND mph.capture_method = 'manual'
          )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    guarded_tables = [
        "market_update_source_results",
        "market_update_items",
        "market_update_jobs",
    ]
    for table in guarded_tables:
        if _has_table(table) and bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar():
            raise RuntimeError(f"Downgrade bloqueado: {table} contiene trazabilidad de Mercado.")
    if bind.execute(sa.text("SELECT count(*) FROM market_price_history WHERE job_id IS NOT NULL OR capture_method = 'manual'")).scalar():
        raise RuntimeError("Downgrade bloqueado: existen observaciones auditables de Mercado.")
    raise RuntimeError(
        "Downgrade bloqueado: la revisión crea market_alerts y cambia la nulabilidad de URLs; revertirla podría perder datos."
    )
