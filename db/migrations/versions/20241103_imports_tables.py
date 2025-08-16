"""create import tables and price history"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = 'imports_tables'
down_revision = '20241010_add_stock_column'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer,
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="DRY_RUN",
        ),
    )
    op.create_index("ix_import_jobs_supplier", "import_jobs", ["supplier_id"])

    op.create_table(
        "import_job_rows",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "job_id",
            sa.Integer,
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer, nullable=False),
        sa.Column("codigo", sa.String(128), nullable=True),
        sa.Column("nombre", sa.Text, nullable=True),
        sa.Column("categoria_path", sa.Text, nullable=True),
        sa.Column("compra_minima", sa.Integer, nullable=True),
        sa.Column("precio_compra", sa.Numeric(12, 2), nullable=True),
        sa.Column("precio_venta", sa.Numeric(12, 2), nullable=True),
        sa.Column("delta_compra", sa.Numeric(12, 2), nullable=True),
        sa.Column("delta_venta", sa.Numeric(12, 2), nullable=True),
        sa.Column("delta_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="ok",
        ),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("meta", pg.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_import_job_rows_job_idx",
        "import_job_rows",
        ["job_id", "row_index"],
    )
    op.create_index(
        "ix_import_job_rows_job_status",
        "import_job_rows",
        ["job_id", "status"],
    )

    op.create_table(
        "supplier_price_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "supplier_id",
            sa.Integer,
            sa.ForeignKey("suppliers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("precio_compra", sa.Numeric(12, 2), nullable=False),
        sa.Column("precio_venta", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "job_id",
            sa.Integer,
            sa.ForeignKey("import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_price_hist_supplier_product",
        "supplier_price_history",
        ["supplier_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_price_hist_supplier_product",
        table_name="supplier_price_history",
    )
    op.drop_table("supplier_price_history")
    op.drop_index(
        "ix_import_job_rows_job_status",
        table_name="import_job_rows",
    )
    op.drop_index(
        "ix_import_job_rows_job_idx",
        table_name="import_job_rows",
    )
    op.drop_table("import_job_rows")
    op.drop_index("ix_import_jobs_supplier", table_name="import_jobs")
    op.drop_table("import_jobs")
