#!/usr/bin/env python
# NG-HEADER: Nombre de archivo: 20260718_product_taxonomy_tags_v1.py
# NG-HEADER: Ubicación: db/migrations/versions/20260718_product_taxonomy_tags_v1.py
# NG-HEADER: Descripción: Separa categoría y subcategoría planas y persiste tags del batch canónico.
# NG-HEADER: Lineamientos: Ver AGENTS.md
"""Taxonomía plana y tags persistentes para Productos Vue.

Revision ID: 20260718_product_taxonomy_tags_v1
Revises: 20260718_admin_jsonb_v2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260718_product_taxonomy_tags_v1"
down_revision = "20260718_admin_jsonb_v2"
branch_labels = None
depends_on = None


def _scalar(sql: str) -> int:
    return int(op.get_bind().execute(sa.text(sql)).scalar() or 0)


def upgrade() -> None:
    duplicate_categories = op.get_bind().execute(sa.text("""
        SELECT CASE WHEN parent_id IS NULL THEN 'category' ELSE 'subcategory' END AS kind,
               lower(trim(name)) AS normalized_name,
               count(*) AS total
        FROM categories
        GROUP BY 1, 2
        HAVING count(*) > 1
        LIMIT 1
    """)).first()
    if duplicate_categories:
        raise RuntimeError(
            "No se puede migrar categories: existen nombres duplicados por tipo "
            f"({duplicate_categories.kind}, {duplicate_categories.normalized_name})."
        )

    duplicate_tags = op.get_bind().execute(sa.text("""
        SELECT lower(trim(name)) AS normalized_name, count(*) AS total
        FROM tags
        GROUP BY 1
        HAVING count(*) > 1
        LIMIT 1
    """)).first()
    if duplicate_tags:
        raise RuntimeError(
            "No se puede migrar tags: existen nombres duplicados sin distinguir mayúsculas "
            f"({duplicate_tags.normalized_name})."
        )

    op.add_column(
        "categories",
        sa.Column("kind", sa.String(length=20), nullable=True),
    )
    op.execute("""
        UPDATE categories
        SET kind = CASE WHEN parent_id IS NULL THEN 'category' ELSE 'subcategory' END
    """)
    op.alter_column(
        "categories",
        "kind",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="category",
    )
    op.create_check_constraint(
        "ck_categories_kind",
        "categories",
        "kind IN ('category', 'subcategory')",
    )
    op.create_index(
        "ux_categories_kind_lower_name",
        "categories",
        ["kind", sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ux_tags_lower_name",
        "tags",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.add_column("products", sa.Column("subcategory_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_products_subcategory_id_categories",
        "products",
        "categories",
        ["subcategory_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("""
        WITH RECURSIVE ancestors AS (
            SELECT p.id AS product_id, c.id, c.parent_id, 0 AS depth
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE c.parent_id IS NOT NULL
            UNION ALL
            SELECT a.product_id, parent.id, parent.parent_id, a.depth + 1
            FROM ancestors a
            JOIN categories parent ON parent.id = a.parent_id
        ), roots AS (
            SELECT DISTINCT ON (product_id) product_id, id AS root_id
            FROM ancestors
            WHERE parent_id IS NULL
            ORDER BY product_id, depth DESC
        )
        UPDATE products p
        SET subcategory_id = p.category_id,
            category_id = roots.root_id
        FROM roots
        WHERE p.id = roots.product_id
    """)
    op.add_column(
        "canonical_batch_job_items",
        sa.Column("tag_names", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    if _scalar("SELECT count(*) FROM products WHERE subcategory_id IS NOT NULL"):
        raise RuntimeError("Downgrade bloqueado: existen productos con subcategoría plana.")
    if _scalar("SELECT count(*) FROM canonical_batch_job_items WHERE tag_names IS NOT NULL AND tag_names::text <> '[]'"):
        raise RuntimeError("Downgrade bloqueado: existen batches con tags persistidos.")
    if _scalar("SELECT count(*) FROM categories WHERE kind = 'subcategory' AND parent_id IS NULL"):
        raise RuntimeError("Downgrade bloqueado: existen subcategorías planas sin padre legado.")

    op.drop_column("canonical_batch_job_items", "tag_names")
    op.drop_constraint("fk_products_subcategory_id_categories", "products", type_="foreignkey")
    op.drop_column("products", "subcategory_id")
    op.drop_index("ux_tags_lower_name", table_name="tags")
    op.drop_index("ux_categories_kind_lower_name", table_name="categories")
    op.drop_constraint("ck_categories_kind", "categories", type_="check")
    op.drop_column("categories", "kind")
