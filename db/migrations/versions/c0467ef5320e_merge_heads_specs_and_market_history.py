"""merge_heads_specs_and_market_history

Revision ID: c0467ef5320e
Revises: 20251119_add_product_specs_and_usage, d53f209c03d1
Create Date: 2025-11-25 18:56:00.823420
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c0467ef5320e'
down_revision = ('20251119_add_product_specs_and_usage', 'd53f209c03d1')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
