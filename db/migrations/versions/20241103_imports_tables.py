"""create import tables and price history"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20241103_imports_tables"
down_revision = "20241010_add_stock_column"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _table_exists(name: str) -> bool:
    return _insp().has_table(name)


def _col_exists(table: str, col: str) -> bool:
    return any(c["name"] == col for c in _insp().get_columns(table))


def _fk_exists(table: str, fk_name: str) -> bool:
    return any(fk.get("name") == fk_name for fk in _insp().get_foreign_keys(table))


def _idx_exists(table: str, idx_name: str) -> bool:
    return any(ix.get("name") == idx_name for ix in _insp().get_indexes(table))


def upgrade():
    # --- import_jobs ---
    if not _table_exists("import_jobs"):
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

    # --- import_job_rows ---
    if not _table_exists("import_job_rows"):
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
            sa.Column("codigo", sa.String(128)),
            sa.Column("nombre", sa.Text),
            sa.Column("categoria_path", sa.Text),
            sa.Column("compra_minima", sa.Integer),
            sa.Column("precio_compra", sa.Numeric(12, 2)),
            sa.Column("precio_venta", sa.Numeric(12, 2)),
            sa.Column("delta_compra", sa.Numeric(12, 2)),
            sa.Column("delta_venta", sa.Numeric(12, 2)),
            sa.Column("delta_pct", sa.Numeric(8, 4)),
            sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
            sa.Column("error_msg", sa.Text),
            sa.Column("meta", pg.JSONB(astext_type=sa.Text())),
        )
        op.create_index("ix_import_job_rows_job_idx", "import_job_rows", ["job_id", "row_index"])
        op.create_index("ix_import_job_rows_job_status", "import_job_rows", ["job_id", "status"])

    # --- supplier_price_history ---
    if not _table_exists("supplier_price_history"):
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
            sa.Column("job_id", sa.Integer, sa.ForeignKey("import_jobs.id", ondelete="SET NULL")),
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
    else:
        # existe: asegurar columna, FK e índice
        if not _col_exists("supplier_price_history", "job_id"):
            op.add_column("supplier_price_history", sa.Column("job_id", sa.Integer, nullable=True))
        if not _fk_exists("supplier_price_history", "fk_sph_job"):
            op.create_foreign_key(
                "fk_sph_job",
                "supplier_price_history",
                "import_jobs",
                local_cols=["job_id"],
                remote_cols=["id"],
                ondelete="SET NULL",
            )
        if not _idx_exists("supplier_price_history", "ix_price_hist_supplier_product"):
            op.create_index(
                "ix_price_hist_supplier_product",
                "supplier_price_history",
                ["supplier_id", "product_id"],
            )


def downgrade():
    # bajar en orden seguro y condicional
    if _table_exists("supplier_price_history"):
        if _idx_exists("supplier_price_history", "ix_price_hist_supplier_product"):
            op.drop_index("ix_price_hist_supplier_product", table_name="supplier_price_history")
        # FK puede existir con nombre fijo o con nombre autogenerado; intentar por nombre fijo
        if _fk_exists("supplier_price_history", "fk_sph_job"):
            op.drop_constraint("fk_sph_job", "supplier_price_history", type_="foreignkey")
        op.drop_table("supplier_price_history")

    if _table_exists("import_job_rows"):
        if _idx_exists("import_job_rows", "ix_import_job_rows_job_status"):
            op.drop_index("ix_import_job_rows_job_status", table_name="import_job_rows")
        if _idx_exists("import_job_rows", "ix_import_job_rows_job_idx"):
            op.drop_index("ix_import_job_rows_job_idx", table_name="import_job_rows")
        op.drop_table("import_job_rows")

    if _table_exists("import_jobs"):
        if _idx_exists("import_jobs", "ix_import_jobs_supplier"):
            op.drop_index("ix_import_jobs_supplier", table_name="import_jobs")
        op.drop_table("import_jobs")

