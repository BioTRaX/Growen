from alembic import op
import sqlalchemy as sa

revision = "20250114_supplier_price_history_idx"
down_revision = "20250113_import_job_rows_status_idx"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())

def _idx_exists(table: str, name: str) -> bool:
    return any(ix["name"] == name for ix in _insp().get_indexes(table))


def upgrade() -> None:
    if not _idx_exists("supplier_price_history", "ix_sph_product_date"):
        op.create_index(
            "ix_sph_product_date",
            "supplier_price_history",
            ["supplier_product_fk", "as_of_date"],
        )


def downgrade() -> None:
    if _idx_exists("supplier_price_history", "ix_sph_product_date"):
        op.drop_index("ix_sph_product_date", table_name="supplier_price_history")
