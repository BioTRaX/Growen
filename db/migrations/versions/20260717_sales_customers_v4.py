#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260717_sales_customers_v4.py
# NG-HEADER: Ubicación: db/migrations/versions/20260717_sales_customers_v4.py
# NG-HEADER: Descripción: Evoluciona cantidades, reservas y cuenta corriente de Clientes y Ventas.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Evolución integral de Clientes y Ventas.

Revision ID: 20260717_sales_customers_v4
Revises: 20260717_canonical_batch_tracking
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_sales_customers_v4"
down_revision = "20260717_canonical_batch_tracking"
branch_labels = None
depends_on = None


QUANTITY_COLUMNS = (
    ("products", "stock"),
    ("inventory", "stock_qty"),
    ("inventory", "min_qty"),
    ("purchase_lines", "qty"),
    ("sale_lines", "qty"),
    ("return_lines", "qty"),
    ("stock_ledger", "delta"),
    ("stock_ledger", "balance_after"),
    ("stock_shortages", "quantity"),
)


def _columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(table) and column.name not in _columns(inspector, table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, column in QUANTITY_COLUMNS:
        if not inspector.has_table(table) or column not in _columns(inspector, table):
            continue
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, type_=sa.Numeric(14, 2), existing_nullable=True)

    _add_column_if_missing("customers", sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True))
    _add_column_if_missing(
        "sales",
        sa.Column("additional_cost_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    _add_column_if_missing("sales", sa.Column("idempotency_key", sa.String(128), nullable=True))
    _add_column_if_missing("sale_lines", sa.Column("unit_cost_snapshot", sa.Numeric(14, 2), nullable=True))
    _add_column_if_missing(
        "sale_lines",
        sa.Column(
            "cost_supplier_product_id",
            sa.Integer(),
            sa.ForeignKey("supplier_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    _add_column_if_missing(
        "sale_lines",
        sa.Column("global_discount_allocated", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )

    inspector = sa.inspect(bind)
    sales_indexes = {item["name"] for item in inspector.get_indexes("sales")}
    if "ux_sales_idempotency_key" not in sales_indexes:
        op.create_index("ux_sales_idempotency_key", "sales", ["idempotency_key"], unique=True)

    if not inspector.has_table("stock_reservations"):
        op.create_table(
            "stock_reservations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("sale_id", sa.Integer(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sale_line_id", sa.Integer(), sa.ForeignKey("sale_lines.id", ondelete="CASCADE"), nullable=False),
            sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
            sa.Column("qty", sa.Numeric(14, 2), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("released_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint(
                "status IN ('ACTIVE','CONSUMED','RELEASED','EXPIRED')",
                name="ck_stock_reservations_status",
            ),
        )
        op.create_index(
            "ix_stock_reservations_product_status",
            "stock_reservations",
            ["product_id", "status", "expires_at"],
        )
        op.create_index("ix_stock_reservations_sale", "stock_reservations", ["sale_id", "status"])
        if bind.dialect.name == "postgresql":
            op.execute(
                "CREATE UNIQUE INDEX ux_stock_reservations_active_line "
                "ON stock_reservations(sale_line_id) WHERE status = 'ACTIVE'"
            )

    inspector = sa.inspect(bind)
    if not inspector.has_table("customer_account_entries"):
        op.create_table(
            "customer_account_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("entry_type", sa.String(24), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("source_type", sa.String(24), nullable=False),
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("correlation_id", sa.String(64), nullable=True),
            sa.CheckConstraint(
                "entry_type IN ('SALE_CHARGE','PAYMENT','RETURN_CREDIT','ANNUL_CREDIT','ADJUSTMENT_DEBIT','ADJUSTMENT_CREDIT')",
                name="ck_customer_account_entries_type",
            ),
            sa.UniqueConstraint("source_type", "source_id", "entry_type", name="uq_customer_account_entry_source"),
        )
        op.create_index(
            "ix_customer_account_entries_customer_date",
            "customer_account_entries",
            ["customer_id", "occurred_at"],
        )

    # Backfill conservador: usa importes históricos persistidos sin reescribir ventas.
    bind.execute(sa.text("""
        INSERT INTO customer_account_entries
            (customer_id, entry_type, amount, source_type, source_id, note, occurred_at, created_by, correlation_id)
        SELECT s.customer_id, 'SALE_CHARGE', s.total_amount, 'sale', s.id,
               'Backfill de venta', s.sale_date, s.created_by, s.correlation_id
        FROM sales s
        WHERE s.customer_id IS NOT NULL AND s.status IN ('CONFIRMADA', 'ENTREGADA')
          AND NOT EXISTS (
              SELECT 1 FROM customer_account_entries e
              WHERE e.source_type = 'sale' AND e.source_id = s.id AND e.entry_type = 'SALE_CHARGE'
          )
    """))
    bind.execute(sa.text("""
        INSERT INTO customer_account_entries
            (customer_id, entry_type, amount, source_type, source_id, note, occurred_at, created_by, correlation_id)
        SELECT s.customer_id, 'PAYMENT', -p.amount, 'payment', p.id,
               p.reference, COALESCE(p.paid_at, p.created_at), s.created_by, s.correlation_id
        FROM sale_payments p JOIN sales s ON s.id = p.sale_id
        WHERE s.customer_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM customer_account_entries e
              WHERE e.source_type = 'payment' AND e.source_id = p.id AND e.entry_type = 'PAYMENT'
          )
    """))
    bind.execute(sa.text("""
        INSERT INTO customer_account_entries
            (customer_id, entry_type, amount, source_type, source_id, note, occurred_at, created_by, correlation_id)
        SELECT s.customer_id, 'RETURN_CREDIT', -r.total_amount, 'return', r.id,
               r.reason, r.created_at, r.created_by, r.correlation_id
        FROM returns r JOIN sales s ON s.id = r.sale_id
        WHERE s.customer_id IS NOT NULL AND r.status = 'REGISTRADA'
          AND NOT EXISTS (
              SELECT 1 FROM customer_account_entries e
              WHERE e.source_type = 'return' AND e.source_id = r.id AND e.entry_type = 'RETURN_CREDIT'
          )
    """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("customer_account_entries", "stock_reservations"):
        if inspector.has_table(table):
            count = bind.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one()
            if count:
                raise RuntimeError(
                    f"No se puede revertir: {table} contiene {count} filas; exportar o migrar los datos primero"
                )

    for table, column in QUANTITY_COLUMNS:
        inspector = sa.inspect(bind)
        if not inspector.has_table(table) or column not in _columns(inspector, table):
            continue
        fractional = bind.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE {column} IS NOT NULL AND {column} <> CAST({column} AS INTEGER)")
        ).scalar_one()
        if fractional:
            raise RuntimeError(f"No se puede convertir {table}.{column} a entero: existen valores fraccionarios")

    inspector = sa.inspect(bind)
    if inspector.has_table("customer_account_entries"):
        op.drop_table("customer_account_entries")
    if inspector.has_table("stock_reservations"):
        op.drop_table("stock_reservations")

    inspector = sa.inspect(bind)
    sales_indexes = {item["name"] for item in inspector.get_indexes("sales")}
    if "ux_sales_idempotency_key" in sales_indexes:
        op.drop_index("ux_sales_idempotency_key", table_name="sales")

    for table, column in (
        ("sale_lines", "global_discount_allocated"),
        ("sale_lines", "cost_supplier_product_id"),
        ("sale_lines", "unit_cost_snapshot"),
        ("sales", "idempotency_key"),
        ("sales", "additional_cost_total"),
        ("customers", "credit_limit"),
    ):
        inspector = sa.inspect(bind)
        if inspector.has_table(table) and column in _columns(inspector, table):
            op.drop_column(table, column)

    for table, column in QUANTITY_COLUMNS:
        inspector = sa.inspect(bind)
        if inspector.has_table(table) and column in _columns(inspector, table):
            with op.batch_alter_table(table) as batch:
                batch.alter_column(column, type_=sa.Integer(), existing_nullable=True)
