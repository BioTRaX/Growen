#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260828_market_pipeline_v2.py
# NG-HEADER: Ubicación: db/migrations/versions/20260828_market_pipeline_v2.py
# NG-HEADER: Descripción: Etapas, cobertura y reconciliación del pipeline automático de Mercado.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260828_market_pipeline_v2"
down_revision = "20260816_chat_rollout_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_update_items",
        sa.Column("stage", sa.String(24), nullable=False, server_default="queued"),
    )
    for name in (
        "competitors_existing",
        "sources_discovered",
        "sources_confirmed",
        "sources_quarantined",
    ):
        op.add_column(
            "market_update_items",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    op.create_check_constraint(
        "ck_market_update_items_stage",
        "market_update_items",
        "stage IN ('queued','discovering','validating','extracting','completed')",
    )
    op.add_column(
        "market_update_source_results",
        sa.Column("operation", sa.String(24), nullable=False, server_default="extraction"),
    )

    # Los items activos previos a este despliegue no poseen un lease recuperable.
    # Se cierran con causa explícita para liberar la unicidad por producto.
    op.execute(sa.text("""
        UPDATE market_update_items
        SET status = 'failed',
            stage = 'completed',
            error_code = 'stale_before_pipeline_v2',
            error_message = 'Trabajo anterior al pipeline v2 cerrado durante la migración',
            completed_at = CURRENT_TIMESTAMP
        WHERE status IN ('queued', 'running')
    """))
    op.execute(sa.text("""
        UPDATE market_update_jobs AS job
        SET status = summary.final_status,
            processed_items = summary.processed,
            success_count = summary.succeeded,
            error_count = summary.failed,
            completed_at = CURRENT_TIMESTAMP,
            error_code = CASE WHEN summary.failed > 0 THEN 'stale_before_pipeline_v2' ELSE job.error_code END
        FROM (
            SELECT job_id,
                   COUNT(*) AS processed,
                   SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS succeeded,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   CASE
                       WHEN SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) = COUNT(*) THEN 'failed'
                       WHEN SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) = COUNT(*) THEN 'succeeded'
                       ELSE 'partial'
                   END AS final_status
            FROM market_update_items
            GROUP BY job_id
        ) AS summary
        WHERE job.id = summary.job_id
          AND job.status IN ('queued', 'running')
    """))


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade bloqueado: eliminaría etapas y cobertura auditable del pipeline de Mercado"
    )
