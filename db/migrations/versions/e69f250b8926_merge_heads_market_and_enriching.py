"""merge_heads_market_and_enriching

Revision ID: e69f250b8926
Revises: 20251025_add_products_is_enriching, 20251111_add_market_sources
Create Date: 2025-11-11 19:44:09.569255
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e69f250b8926'
down_revision = ('20251025_add_products_is_enriching', '20251111_add_market_sources')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
