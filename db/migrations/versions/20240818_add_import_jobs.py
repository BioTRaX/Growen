"""add import job tables"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240818_import_jobs'
down_revision = '6f8e298d069b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'import_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('supplier_id', sa.Integer(), sa.ForeignKey('suppliers.id'), nullable=False),
        sa.Column('filename', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=True),
    )
    op.create_table(
        'import_job_rows',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('import_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('row_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.String(length=200), nullable=True),
        sa.Column('row_json_normalized', sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('import_job_rows')
    op.drop_table('import_jobs')
