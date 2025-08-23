from alembic import op
import sqlalchemy as sa

from db.migrations.util import has_column, index_exists

revision = "20250114_supplier_price_history_idx"
down_revision = "20250113_import_job_rows_status_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if (
        has_column(bind, "supplier_price_history", "supplier_product_fk")
        and has_column(bind, "supplier_price_history", "as_of_date")
        and not index_exists(bind, "supplier_price_history", "ix_sph_product_date")
    ):
        op.create_index(
            "ix_sph_product_date",
            "supplier_price_history",
            ["supplier_product_fk", "as_of_date"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if index_exists(bind, "supplier_price_history", "ix_sph_product_date"):
        op.drop_index("ix_sph_product_date", table_name="supplier_price_history")
