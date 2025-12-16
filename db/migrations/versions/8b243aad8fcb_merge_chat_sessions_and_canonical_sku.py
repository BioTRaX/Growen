"""merge_chat_sessions_and_canonical_sku

Revision ID: 8b243aad8fcb
Revises: 20250126_chat_sessions, c308b8798a79
Create Date: 2025-12-16 18:36:33.239502
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8b243aad8fcb'
down_revision = ('20250126_chat_sessions', 'c308b8798a79')
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
