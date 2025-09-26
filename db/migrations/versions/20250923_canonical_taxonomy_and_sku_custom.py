# NG-HEADER: Nombre de archivo: 20250923_canonical_taxonomy_and_sku_custom.py
# NG-HEADER: Ubicación: db/migrations/versions/20250923_canonical_taxonomy_and_sku_custom.py
# NG-HEADER: Descripción: Agrega sku_custom único y category_id/subcategory_id a canonical_products.
# NG-HEADER: Lineamientos: Ver AGENTS.md
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection

from db.migrations.util import has_table, has_column, unique_constraint_exists

# revision identifiers, used by Alembic.
revision = '20250923_canonical_taxonomy_and_sku_custom'
down_revision = '20250901_merge_images_and_import_logs'
branch_labels = None
depends_on = None


def upgrade():
    bind: Connection = op.get_bind()
    if not has_table(bind, 'canonical_products'):
        return

    # sku_custom
    if not has_column(bind, 'canonical_products', 'sku_custom'):
        op.add_column('canonical_products', sa.Column('sku_custom', sa.String(length=32), nullable=True))
        # unique
        try:
            op.create_unique_constraint('ux_canonical_products_sku_custom', 'canonical_products', ['sku_custom'])
        except Exception:
            pass
    else:
        # ensure unique exists
        if not unique_constraint_exists(bind, 'canonical_products', 'ux_canonical_products_sku_custom'):
            try:
                op.create_unique_constraint('ux_canonical_products_sku_custom', 'canonical_products', ['sku_custom'])
            except Exception:
                pass

    # category_id
    if not has_column(bind, 'canonical_products', 'category_id'):
        op.add_column('canonical_products', sa.Column('category_id', sa.Integer(), nullable=True))
        try:
            op.create_foreign_key('fk_canon_cat', 'canonical_products', 'categories', ['category_id'], ['id'])
        except Exception:
            pass
    # subcategory_id
    if not has_column(bind, 'canonical_products', 'subcategory_id'):
        op.add_column('canonical_products', sa.Column('subcategory_id', sa.Integer(), nullable=True))
        try:
            op.create_foreign_key('fk_canon_subcat', 'canonical_products', 'categories', ['subcategory_id'], ['id'])
        except Exception:
            pass


def downgrade():
    bind: Connection = op.get_bind()
    if not has_table(bind, 'canonical_products'):
        return
    # Drop FKs then columns
    try:
        op.drop_constraint('fk_canon_cat', 'canonical_products', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_constraint('fk_canon_subcat', 'canonical_products', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_constraint('ux_canonical_products_sku_custom', 'canonical_products', type_='unique')
    except Exception:
        pass
    try:
        op.drop_column('canonical_products', 'sku_custom')
    except Exception:
        pass
    try:
        op.drop_column('canonical_products', 'category_id')
    except Exception:
        pass
    try:
        op.drop_column('canonical_products', 'subcategory_id')
    except Exception:
        pass
