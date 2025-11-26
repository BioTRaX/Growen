"""merge_heads

Revision ID: fa50a5cba1bb
Revises: b2d22a7ce889, cf0f6e70fe89
Create Date: 2025-11-25 20:16:13.343521
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'fa50a5cba1bb'
down_revision = ('b2d22a7ce889', 'cf0f6e70fe89')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
